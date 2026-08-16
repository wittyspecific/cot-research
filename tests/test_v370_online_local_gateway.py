from __future__ import annotations

from pathlib import Path
import json
import threading

import numpy as np
import pandas as pd

from gateway import journal_gateway as gw
from src.deployment_mode import LOCAL, REMOTE_GATEWAY, deployment_config_from_mapping
from src.journal_gateway_client import JournalGatewayClient, JournalGatewayConfig
from src.trade_journal import create_trade_plan, get_trade_events, initialize_journal
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
        "requested_risk_pct": 0.0025,
        "zone_freshness": "FRESH",
        "retest_count": 0,
        "quality_grade": "A",
        "notes": "gateway test",
    }


def _start_gateway(tmp_path: Path, monkeypatch):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    key = "K" * 48
    secrets_path = tmp_path / "secrets.toml"
    secrets_path.write_text(
        f'''[journal]\ndb_path = "{db}"\n\n[gateway]\nshared_key = "{key}"\nsession_hours = 12\n\n[mt5]\nmode = "bridge"\n'''
    )
    state = gw.GatewayState(secrets_path=secrets_path)
    server = gw.build_server("127.0.0.1", 0, state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    client = JournalGatewayClient(JournalGatewayConfig(base_url=base_url, shared_key=key, timeout_seconds=3.0))
    return db, server, thread, client


def test_deployment_modes():
    assert deployment_config_from_mapping({}).mode == LOCAL
    assert deployment_config_from_mapping({"mode": "remote_gateway"}).mode == REMOTE_GATEWAY
    assert deployment_config_from_mapping({"mode": "gateway"}).is_remote


def test_remote_login_create_trade_and_read_back(tmp_path: Path, monkeypatch):
    db, server, thread, client = _start_gateway(tmp_path, monkeypatch)
    try:
        trader = create_trader(username="max", display_name="Max", password="Password123!", db_path=db)
        auth = client.login("max", "Password123!")
        authed = client.with_token(auth["token"])
        assert authed.me()["trader_id"] == trader["trader_id"]

        private_snapshot = {
            "meta": {"builder_version": "test"},
            "account": {"login": 123456, "equity": 99999},
            "portfolio": {"open_positions": [{"symbol": "SECRET"}]},
            "risk": {"available": True, "pretrade_approval": {"status": "GREEN"}},
            "research": {"available": True, "signal": "TEST"},
        }
        saved = authed.create_trade_plan(_plan(), private_snapshot)
        assert saved["trade_id"]
        assert "db_path" not in saved

        rows = authed.list_trade_plans(limit=10)
        assert len(rows) == 1
        assert rows.iloc[0]["trader_id"] == trader["trader_id"]

        remote_snapshot = authed.get_trade_snapshot(saved["trade_id"])
        assert remote_snapshot["account"]["scope"] == "LOCAL_ONLY"
        assert remote_snapshot["portfolio"]["open_positions"] == []
        assert remote_snapshot["risk"]["scope"] == "LOCAL_ONLY"
        assert remote_snapshot["research"]["signal"] == "TEST"
        assert "123456" not in str(remote_snapshot)
        assert "SECRET" not in str(remote_snapshot)

        events = get_trade_events(saved["trade_id"], db_path=db)
        assert "REMOTE_GATEWAY_INGEST" in set(events["event_type"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_non_admin_cannot_query_another_traders_journal(tmp_path: Path, monkeypatch):
    db, server, thread, client = _start_gateway(tmp_path, monkeypatch)
    try:
        a = create_trader(username="alice", display_name="Alice", password="Password123!", db_path=db)
        b = create_trader(username="bob", display_name="Bob", password="Password123!", db_path=db)
        create_trade_plan(plan=_plan("XAUUSD"), snapshot_payload={"owner": "A"}, trader_id=a["trader_id"], db_path=db)
        create_trade_plan(plan=_plan("XAGUSD"), snapshot_payload={"owner": "B"}, trader_id=b["trader_id"], db_path=db)

        auth = client.login("alice", "Password123!")
        authed = client.with_token(auth["token"])
        rows = authed.list_trade_plans(limit=10, trader_id=b["trader_id"])
        assert len(rows) == 1
        assert rows.iloc[0]["trader_id"] == a["trader_id"]
        assert rows.iloc[0]["cfd_symbol"] == "XAUUSD"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_planner_context_has_symbol_metadata_but_no_live_quotes(tmp_path: Path, monkeypatch):
    db, server, thread, client = _start_gateway(tmp_path, monkeypatch)
    try:
        create_trader(username="max", display_name="Max", password="Password123!", db_path=db)
        monkeypatch.setattr(gw, "mt5_config_from_mapping", lambda mapping: object())
        monkeypatch.setattr(
            gw,
            "get_mt5_snapshot",
            lambda cfg: {
                "source": "bridge",
                "captured_at": "2026-08-16T10:00:00+00:00",
                "market_time": "2026-08-16T10:00:00+00:00",
                "account": {"login": 123456, "equity": 99999},
                "positions": pd.DataFrame([{"symbol": "PRIVATE"}]),
                "symbol_catalog": pd.DataFrame([
                    {
                        "symbol": "XAUUSD",
                        "description": "Gold",
                        "can_open": True,
                        "digits": 2,
                        "bid": 3350.10,
                        "ask": 3350.30,
                        "last": 3350.20,
                        "tick_size": 0.01,
                        "tick_value": 1.0,
                    }
                ]),
            },
        )
        auth = client.login("max", "Password123!")
        context = client.with_token(auth["token"]).planner_context()
        assert context["privacy_scope"] == "SYMBOL_METADATA_ONLY_NO_LIVE_QUOTES"
        assert context["account"] == {}
        assert context["positions"].empty
        assert context["symbol_catalog"].iloc[0]["symbol"] == "XAUUSD"
        assert pd.isna(context["symbol_catalog"].iloc[0]["bid"])
        assert pd.isna(context["symbol_catalog"].iloc[0]["ask"])
        assert pd.isna(context["symbol_catalog"].iloc[0]["last"])
        assert "123456" not in str(context)
        assert "PRIVATE" not in str(context)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_remote_create_trade_normalizes_non_finite_snapshot_values_to_null(tmp_path: Path, monkeypatch):
    db, server, thread, client = _start_gateway(tmp_path, monkeypatch)
    try:
        trader = create_trader(username="nantrader", display_name="NaN Trader", password="Password123!", db_path=db)
        auth = client.login("nantrader", "Password123!")
        authed = client.with_token(auth["token"])

        snapshot = {
            "research": {
                "missing_float": float("nan"),
                "positive_inf": float("inf"),
                "negative_inf": float("-inf"),
                "numpy_nan": np.float64(np.nan),
                "nested": [1.0, np.float64(np.nan), {"pd_missing": pd.NA}],
            },
            "meta": {"captured_at": pd.Timestamp("2026-08-16T10:00:00Z")},
        }
        # The exact payload sent by the client must be strict JSON compliant.
        from src.journal_gateway_client import _json_safe
        json.dumps(_json_safe({"plan": _plan(), "snapshot_payload": snapshot}), allow_nan=False)

        saved = authed.create_trade_plan(_plan(), snapshot)
        assert saved["trade_id"]
        remote_snapshot = authed.get_trade_snapshot(saved["trade_id"])
        research = remote_snapshot["research"]
        assert research["missing_float"] is None
        assert research["positive_inf"] is None
        assert research["negative_inf"] is None
        assert research["numpy_nan"] is None
        assert research["nested"][1] is None
        assert research["nested"][2]["pd_missing"] is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
