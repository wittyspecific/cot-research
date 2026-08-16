from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from src.ftmo_risk import FTMORiskConfig
from src.trade_journal import create_trade_plan, initialize_journal, list_trade_plans, journal_summary, build_feature_matrix
from src.trade_snapshot import collect_trade_snapshot
from src.trader_auth import (
    authenticate_trader,
    create_trader,
    list_traders,
    set_trader_active,
    trader_count,
    unassigned_plan_count,
)


def _plan(symbol="XAUUSD"):
    return {
        "plan_type": "SIMULATION",
        "order_type": "LIMIT",
        "cfd_symbol": symbol,
        "side": "LONG",
        "zone_type": "DEMAND",
        "timeframe": "4H",
        "entry": 100.0,
        "stop": 95.0,
        "target": 110.0,
        "requested_risk_pct": 0.0025,
    }


def test_first_admin_claims_existing_legacy_plans(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    legacy = create_trade_plan(plan=_plan(), snapshot_payload={"x": 1}, db_path=db)
    assert unassigned_plan_count(db_path=db) == 1
    admin = create_trader(
        username="kevin",
        display_name="Kevin",
        password="LongEnoughPassword!",
        role="ADMIN",
        claim_legacy_trades=True,
        db_path=db,
    )
    assert unassigned_plan_count(db_path=db) == 0
    row = list_trade_plans(db_path=db).iloc[0]
    assert row["trader_id"] == admin["trader_id"]
    assert row["trade_id"] == legacy["trade_id"]


def test_password_is_hashed_and_authentication_returns_public_identity(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    trader = create_trader(
        username="alice",
        display_name="Alice",
        password="SecretPassword123!",
        db_path=db,
    )
    with sqlite3.connect(db) as con:
        row = con.execute("SELECT password_hash, password_salt FROM traders WHERE trader_id=?", (trader["trader_id"],)).fetchone()
    assert row[0] != "SecretPassword123!"
    assert "SecretPassword123!" not in row[0]
    assert authenticate_trader("ALICE", "SecretPassword123!", db_path=db)["trader_id"] == trader["trader_id"]
    assert authenticate_trader("alice", "wrong", db_path=db) is None


def test_trade_plans_and_summary_can_be_filtered_by_trader(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    a = create_trader(username="a_user", display_name="A", password="PasswordA123", db_path=db)
    b = create_trader(username="b_user", display_name="B", password="PasswordB123", db_path=db)
    create_trade_plan(plan=_plan("XAUUSD"), snapshot_payload={"feature": {"x": 1}}, trader_id=a["trader_id"], db_path=db)
    create_trade_plan(plan=_plan("XAGUSD"), snapshot_payload={"feature": {"x": 2}}, trader_id=b["trader_id"], db_path=db)
    assert len(list_trade_plans(db_path=db, trader_id=a["trader_id"])) == 1
    assert journal_summary(db_path=db, trader_id=b["trader_id"])["plans"] == 1
    matrix = build_feature_matrix(db_path=db, trader_id=a["trader_id"])
    assert len(matrix) == 1
    assert matrix.iloc[0]["trader_id"] == a["trader_id"]


def test_non_admin_snapshot_omits_ftmo_account_and_open_positions():
    snapshot = {
        "source": "bridge",
        "account": {"login": 123456, "balance": 100000, "equity": 99900, "currency": "USD"},
        "positions": pd.DataFrame([{"symbol": "XAUUSD", "volume": 1.0, "profit": 123.0}]),
        "symbol_catalog": pd.DataFrame([{
            "symbol": "TESTCFD", "bid": 100.0, "ask": 100.2, "digits": 2,
            "tick_size": 0.1, "tick_value": 1.0, "currency_base": "", "currency_profit": "USD",
        }]),
    }
    payload = collect_trade_snapshot(
        plan={"cfd_symbol": "TESTCFD", "side": "LONG", "entry": 100.0, "stop": 95.0, "requested_risk_pct": 0.0025},
        mt5_snapshot=snapshot,
        risk_cfg=FTMORiskConfig(),
        context_override={"mode": "NONE"},
        include_private_risk=False,
    )
    assert payload["account"]["scope"] == "ADMIN_ONLY"
    assert payload["portfolio"]["open_positions"] == []
    assert payload["risk"]["available"] is False
    text = str(payload)
    assert "123456" not in text
    assert "100000" not in text


def test_last_active_admin_cannot_be_disabled(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    admin = create_trader(username="admin", display_name="Admin", password="Password123!", role="ADMIN", db_path=db)
    with pytest.raises(ValueError, match="letzte aktive ADMIN"):
        set_trader_active(admin["trader_id"], False, db_path=db)


def test_app_hides_ftmo_risk_pages_for_trader_role():
    app = (Path(__file__).parents[1] / "app.py").read_text()
    assert 'if is_admin:' in app
    trader_branch = app.split('else:\n    pages = {', 1)[1]
    assert 'pages/risk_cockpit.py' not in trader_branch
    assert 'pages/portfolio_risk.py' not in trader_branch
    assert 'pages/trader_admin.py' not in trader_branch
