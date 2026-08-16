from __future__ import annotations

from pathlib import Path
import threading

import pandas as pd
import pytest

from gateway import journal_gateway as gw
from src.journal_gateway_client import JournalGatewayClient, JournalGatewayConfig, JournalGatewayError
from src.prop_desk import prop_desk_state
from src.trade_journal import (
    build_feature_matrix,
    create_trade_plan,
    get_trade_events,
    get_trade_outcome,
    initialize_journal,
    journal_summary,
    list_trade_plans,
    upsert_trade_outcome,
    void_trade_plan,
)
from src.trader_auth import create_trader


def _plan(symbol: str = "XAUUSD") -> dict:
    return {
        "plan_type": "SIMULATION",
        "order_type": "LIMIT",
        "cfd_symbol": symbol,
        "side": "LONG",
        "zone_type": "DEMAND",
        "timeframe": "4H",
        "zone_low": 99.0,
        "zone_high": 101.0,
        "entry": 100.0,
        "stop": 95.0,
        "target": 110.0,
        "requested_risk_pct": 0.005,
    }


def _snapshot(symbol: str = "XAUUSD") -> dict:
    return {
        "research": {"score": 7.0},
        "mt5_symbol": {"spec": {
            "symbol": symbol, "tick_size": 1.0, "tick_value": 1.0,
            "volume_min": 1.0, "volume_max": 10000.0, "volume_step": 1.0,
        }},
    }


def _start_gateway(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    key = "V" * 48
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text(
        f'''[journal]\ndb_path = "{db}"\n\n[gateway]\nshared_key = "{key}"\nsession_hours = 12\n\n[mt5]\nmode = "bridge"\n'''
    )
    state = gw.GatewayState(secrets_path=secrets_path)
    server = gw.build_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = JournalGatewayClient(JournalGatewayConfig(
        base_url=f"http://127.0.0.1:{server.server_address[1]}", shared_key=key, timeout_seconds=3.0
    ))
    return db, server, thread, client


def test_owner_can_void_planned_trade_and_audit_remains(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    trader = create_trader(username="alice", display_name="Alice", password="Password123!", db_path=db)
    saved = create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), trader_id=trader["trader_id"], db_path=db)

    result = void_trade_plan(
        saved["trade_id"], reason="Falsches Asset", actor_trader_id=trader["trader_id"], db_path=db
    )
    assert result["lifecycle_status"] == "VOID"
    outcome = get_trade_outcome(saved["trade_id"], db_path=db)
    assert outcome["lifecycle_status"] == "VOID"
    assert outcome["entry_triggered"] == 0
    events = get_trade_events(saved["trade_id"], db_path=db)
    assert "PLAN_VOIDED" in set(events["event_type"])
    assert "Falsches Asset" in events.iloc[-1]["payload_json"]

    plans = list_trade_plans(db_path=db)
    assert len(plans) == 1  # audit row still exists
    assert plans.iloc[0]["lifecycle_status"] == "VOID"


def test_voided_trade_is_excluded_from_summary_ml_and_prop_desk(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    trader = create_trader(username="alice", display_name="Alice", password="Password123!", db_path=db)
    saved = create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), trader_id=trader["trader_id"], db_path=db)
    void_trade_plan(saved["trade_id"], reason="Doppelter Eintrag", actor_trader_id=trader["trader_id"], db_path=db)

    summary = journal_summary(db_path=db, trader_id=trader["trader_id"])
    assert summary["plans"] == 0
    assert summary["voided"] == 1
    assert summary["planned"] == 0

    matrix = build_feature_matrix(db_path=db, trader_id=trader["trader_id"])
    assert matrix.empty
    audit_matrix = build_feature_matrix(db_path=db, trader_id=trader["trader_id"], include_voided=True)
    assert len(audit_matrix) == 1

    state = prop_desk_state(trader["trader_id"], db_path=db)
    assert state["summary"]["open_positions"] == 0
    assert state["summary"]["closed_trades"] == 0
    assert state["summary"]["balance"] == pytest.approx(200000.0)


def test_active_or_triggered_trade_cannot_be_voided(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    trader = create_trader(username="alice", display_name="Alice", password="Password123!", db_path=db)
    active = create_trade_plan(plan=_plan("ACTIVEUSD"), snapshot_payload=_snapshot("ACTIVEUSD"), trader_id=trader["trader_id"], db_path=db)
    upsert_trade_outcome(active["trade_id"], {"lifecycle_status": "ACTIVE", "entry_triggered": 1}, db_path=db)
    with pytest.raises(ValueError, match="Nur PLANNED"):
        void_trade_plan(active["trade_id"], reason="Fehler", actor_trader_id=trader["trader_id"], db_path=db)

    triggered = create_trade_plan(plan=_plan("TRIGGERUSD"), snapshot_payload=_snapshot("TRIGGERUSD"), trader_id=trader["trader_id"], db_path=db)
    upsert_trade_outcome(triggered["trade_id"], {"lifecycle_status": "PLANNED", "entry_triggered": 1}, db_path=db)
    with pytest.raises(ValueError, match="Nur PLANNED"):
        void_trade_plan(triggered["trade_id"], reason="Fehler", actor_trader_id=trader["trader_id"], db_path=db)


def test_trader_cannot_void_another_traders_plan_but_admin_can(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    alice = create_trader(username="alice", display_name="Alice", password="Password123!", db_path=db)
    bob = create_trader(username="bob", display_name="Bob", password="Password123!", db_path=db)
    admin = create_trader(username="admin", display_name="Admin", password="Password123!", role="ADMIN", db_path=db)
    saved = create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), trader_id=alice["trader_id"], db_path=db)

    with pytest.raises(PermissionError):
        void_trade_plan(saved["trade_id"], reason="Falsches Asset", actor_trader_id=bob["trader_id"], db_path=db)
    result = void_trade_plan(saved["trade_id"], reason="Admin Korrektur", actor_trader_id=admin["trader_id"], db_path=db)
    assert result["lifecycle_status"] == "VOID"


def test_remote_gateway_voids_only_owned_planned_trade(tmp_path: Path):
    db, server, thread, client = _start_gateway(tmp_path)
    try:
        alice = create_trader(username="alice", display_name="Alice", password="Password123!", db_path=db)
        bob = create_trader(username="bob", display_name="Bob", password="Password123!", db_path=db)
        a_trade = create_trade_plan(plan=_plan("XAUUSD"), snapshot_payload=_snapshot("XAUUSD"), trader_id=alice["trader_id"], db_path=db)
        b_trade = create_trade_plan(plan=_plan("XAGUSD"), snapshot_payload=_snapshot("XAGUSD"), trader_id=bob["trader_id"], db_path=db)

        auth = client.login("alice", "Password123!")
        authed = client.with_token(auth["token"])
        out = authed.void_trade_plan(a_trade["trade_id"], "Falsches Asset")
        assert out["lifecycle_status"] == "VOID"
        with pytest.raises(JournalGatewayError, match="Kein Zugriff"):
            authed.void_trade_plan(b_trade["trade_id"], "Falsches Asset")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_ui_exposes_safe_void_not_delete():
    text = (Path(__file__).parents[1] / "pages" / "trading_journal.py").read_text()
    assert "Fehleintrag verwerfen" in text
    assert "void_trade_plan" in text
    assert "PLAN_CANCELLED" not in text
