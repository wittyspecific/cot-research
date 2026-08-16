from __future__ import annotations

from pathlib import Path
import threading

import pandas as pd

from gateway import journal_gateway as gw
from src.journal_gateway_client import JournalGatewayClient, JournalGatewayConfig
from src.trade_journal import initialize_journal, upsert_trade_outcome
from src.trader_auth import create_trader


def _start(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    key = "P" * 48
    secrets = tmp_path / "secrets.toml"
    secrets.write_text(
        f'''[journal]\ndb_path = "{db}"\n\n[gateway]\nshared_key = "{key}"\nsession_hours = 12\n\n[mt5]\nmode = "bridge"\n'''
    )
    state = gw.GatewayState(secrets_path=secrets)
    server = gw.build_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = JournalGatewayClient(
        JournalGatewayConfig(base_url=f"http://127.0.0.1:{server.server_address[1]}", shared_key=key, timeout_seconds=3.0)
    )
    return db, server, thread, client


def _plan():
    return {
        "plan_type": "SIMULATION", "order_type": "LIMIT", "cfd_symbol": "TESTUSD", "side": "LONG",
        "zone_type": "DEMAND", "timeframe": "4H", "zone_low": 99.0, "zone_high": 101.0,
        "entry": 100.0, "stop": 90.0, "target": 120.0, "requested_risk_pct": 0.005,
        "zone_freshness": "FRESH", "retest_count": 0, "quality_grade": "A", "notes": "gateway prop",
    }


def _snapshot():
    return {
        "mt5_symbol": {"spec": {
            "symbol": "TESTUSD", "tick_size": 1.0, "tick_value": 1.0, "tick_value_loss": 1.0,
            "volume_min": 1.0, "volume_max": 10000.0, "volume_step": 1.0,
        }},
        "research": {"available": True},
    }


def test_remote_prop_desk_uses_local_quotes_without_exposing_ftmo_account(tmp_path, monkeypatch):
    db, server, thread, client = _start(tmp_path)
    try:
        trader = create_trader(username="max", display_name="Max", password="Password123!", db_path=db)
        monkeypatch.setattr(gw, "mt5_config_from_mapping", lambda mapping: object())
        monkeypatch.setattr(gw, "get_mt5_snapshot", lambda cfg: {
            "captured_at": "2026-08-16T12:00:00+00:00",
            "account": {"login": 999999, "equity": 123456.0},
            "positions": pd.DataFrame([{"symbol": "PRIVATE_REAL"}]),
            "symbol_catalog": pd.DataFrame([{"symbol": "TESTUSD", "bid": 105.0, "ask": 106.0, "last": 105.5}]),
        })
        auth = client.login("max", "Password123!")
        authed = client.with_token(auth["token"])
        prop_info = authed.prop_account()
        assert prop_info["account"]["starting_capital"] == 200000.0
        saved = authed.create_trade_plan(_plan(), _snapshot())
        upsert_trade_outcome(saved["trade_id"], {"lifecycle_status": "ACTIVE", "entry_triggered": 1}, db_path=db)
        state = authed.prop_desk()
        assert state["summary"]["equity"] == 200500.0
        assert state["open_positions"][0]["floating_pnl"] == 500.0
        assert "login" not in state["account"]
        assert all(row.get("symbol") != "PRIVATE_REAL" for row in state.get("open_positions", []))
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_non_admin_prop_desk_ignores_other_trader_filter(tmp_path):
    db, server, thread, client = _start(tmp_path)
    try:
        alice = create_trader(username="alice", display_name="Alice", password="Password123!", db_path=db)
        bob = create_trader(username="bob", display_name="Bob", password="Password123!", db_path=db)
        auth = client.login("alice", "Password123!")
        authed = client.with_token(auth["token"])
        state = authed.prop_desk(trader_id=bob["trader_id"])
        assert state["account"]["trader_id"] == alice["trader_id"]
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
