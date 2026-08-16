from __future__ import annotations

import math

import pandas as pd
import pytest

from src.prop_desk import (
    ensure_prop_account,
    get_prop_allocation,
    prop_desk_ranking,
    prop_desk_state,
    update_prop_account,
)
from src.trade_journal import create_trade_plan, initialize_journal, upsert_trade_outcome
from src.trader_auth import create_trader


def _plan(*, plan_type="SIMULATION", symbol="TESTUSD", side="LONG", risk=0.005):
    return {
        "plan_type": plan_type,
        "order_type": "LIMIT",
        "cfd_symbol": symbol,
        "side": side,
        "zone_type": "DEMAND" if side == "LONG" else "SUPPLY",
        "timeframe": "4H",
        "zone_low": 99.0,
        "zone_high": 101.0,
        "entry": 100.0,
        "stop": 90.0 if side == "LONG" else 110.0,
        "target": 120.0 if side == "LONG" else 80.0,
        "requested_risk_pct": risk,
        "zone_freshness": "FRESH",
        "retest_count": 0,
        "quality_grade": "A",
        "notes": "prop desk test",
    }


def _snapshot(symbol="TESTUSD"):
    return {
        "meta": {"test": True},
        "mt5_symbol": {
            "spec": {
                "symbol": symbol,
                "tick_size": 1.0,
                "tick_value": 1.0,
                "tick_value_loss": 1.0,
                "volume_min": 1.0,
                "volume_max": 10000.0,
                "volume_step": 1.0,
            }
        },
        "research": {"available": False},
    }


def _trader(tmp_path, username="alice"):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    trader = create_trader(username=username, display_name=username.title(), password="Password123!", db_path=db)
    return db, trader


def test_default_prop_account_and_simulation_allocation(tmp_path):
    db, trader = _trader(tmp_path)
    account = ensure_prop_account(trader["trader_id"], db_path=db)
    assert account["starting_capital"] == 200_000.0
    assert account["default_risk_pct"] == 0.005

    saved = create_trade_plan(
        plan=_plan(), snapshot_payload=_snapshot(), trader_id=trader["trader_id"], db_path=db
    )
    allocation = saved["prop_allocation"]
    assert allocation["sizing_status"] == "SIZED"
    assert allocation["balance_at_plan"] == 200_000.0
    assert allocation["risk_budget"] == 1_000.0
    assert allocation["lots"] == 100.0
    assert allocation["actual_risk"] == 1_000.0
    assert get_prop_allocation(saved["trade_id"], db_path=db)["lots"] == 100.0


def test_closed_trade_updates_virtual_balance_and_next_trade_sizing(tmp_path):
    db, trader = _trader(tmp_path)
    first = create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), trader_id=trader["trader_id"], db_path=db)
    upsert_trade_outcome(
        first["trade_id"],
        {"lifecycle_status": "CLOSED", "result_r": 2.0, "exit_time_utc": "2026-08-10T12:00:00+00:00", "first_exit": "TARGET"},
        db_path=db,
    )
    state = prop_desk_state(trader["trader_id"], db_path=db)
    assert state["summary"]["realized_pnl"] == 2_000.0
    assert state["summary"]["balance"] == 202_000.0
    assert state["summary"]["equity"] == 202_000.0

    second = create_trade_plan(plan=_plan(symbol="NEXTUSD"), snapshot_payload=_snapshot("NEXTUSD"), trader_id=trader["trader_id"], db_path=db)
    allocation = second["prop_allocation"]
    assert allocation["balance_at_plan"] == 202_000.0
    assert allocation["risk_budget"] == pytest.approx(1_010.0)
    assert allocation["lots"] == 101.0
    assert allocation["actual_risk"] == 1_010.0


def test_active_position_uses_liquidation_side_quote_for_floating_pnl(tmp_path):
    db, trader = _trader(tmp_path)
    saved = create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), trader_id=trader["trader_id"], db_path=db)
    upsert_trade_outcome(
        saved["trade_id"],
        {"lifecycle_status": "ACTIVE", "entry_triggered": 1, "entry_time_utc": "2026-08-10T10:00:00+00:00"},
        db_path=db,
    )
    mt5 = {
        "captured_at": "2026-08-16T12:00:00+00:00",
        "symbol_catalog": pd.DataFrame([{"symbol": "TESTUSD", "bid": 105.0, "ask": 106.0, "last": 105.5}]),
    }
    state = prop_desk_state(trader["trader_id"], db_path=db, mt5_snapshot=mt5)
    pos = state["open_positions"][0]
    assert pos["mark"] == 105.0  # LONG is marked at bid
    assert pos["floating_pnl"] == 500.0
    assert pos["current_r"] == 0.5
    assert state["summary"]["equity"] == 200_500.0


def test_real_and_skipped_plans_do_not_touch_prop_account(tmp_path):
    db, trader = _trader(tmp_path)
    real = create_trade_plan(plan=_plan(plan_type="REAL"), snapshot_payload=_snapshot(), trader_id=trader["trader_id"], db_path=db)
    skipped_plan = _plan(plan_type="SKIPPED", symbol="SKIPUSD")
    skipped_plan["skip_reason"] = "test"
    skipped = create_trade_plan(plan=skipped_plan, snapshot_payload=_snapshot("SKIPUSD"), trader_id=trader["trader_id"], db_path=db)
    assert real["prop_allocation"] is None
    assert skipped["prop_allocation"] is None
    assert get_prop_allocation(real["trade_id"], db_path=db) == {}
    assert get_prop_allocation(skipped["trade_id"], db_path=db) == {}


def test_starting_capital_locked_after_first_allocation_but_risk_can_change(tmp_path):
    db, trader = _trader(tmp_path)
    create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), trader_id=trader["trader_id"], db_path=db)
    with pytest.raises(ValueError, match="Startkapital"):
        update_prop_account(trader["trader_id"], starting_capital=250_000.0, db_path=db)
    updated = update_prop_account(
        trader["trader_id"], default_risk_pct=0.004, max_risk_pct=0.008, db_path=db
    )
    assert updated["starting_capital"] == 200_000.0
    assert updated["default_risk_pct"] == 0.004
    assert updated["max_risk_pct"] == 0.008


def test_risk_above_prop_limit_is_saved_but_not_financially_sized(tmp_path):
    db, trader = _trader(tmp_path)
    saved = create_trade_plan(
        plan=_plan(risk=0.02), snapshot_payload=_snapshot(), trader_id=trader["trader_id"], db_path=db
    )
    allocation = saved["prop_allocation"]
    assert allocation["sizing_status"] == "BLOCKED"
    assert math.isnan(float(allocation["actual_risk"]))
    state = prop_desk_state(trader["trader_id"], db_path=db)
    assert state["summary"]["balance"] == 200_000.0


def test_admin_ranking_keeps_traders_separate(tmp_path):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    a = create_trader(username="alice", display_name="Alice", password="Password123!", db_path=db)
    b = create_trader(username="bob", display_name="Bob", password="Password123!", db_path=db)
    ta = create_trade_plan(plan=_plan(symbol="AUSD"), snapshot_payload=_snapshot("AUSD"), trader_id=a["trader_id"], db_path=db)
    tb = create_trade_plan(plan=_plan(symbol="BUSD"), snapshot_payload=_snapshot("BUSD"), trader_id=b["trader_id"], db_path=db)
    upsert_trade_outcome(ta["trade_id"], {"lifecycle_status": "CLOSED", "result_r": 1.0, "exit_time_utc": "2026-08-10T12:00:00+00:00"}, db_path=db)
    upsert_trade_outcome(tb["trade_id"], {"lifecycle_status": "CLOSED", "result_r": -1.0, "exit_time_utc": "2026-08-10T13:00:00+00:00"}, db_path=db)
    ranking = prop_desk_ranking(db_path=db)
    by_name = ranking.set_index("display_name")
    assert by_name.loc["Alice", "equity"] == 201_000.0
    assert by_name.loc["Bob", "equity"] == 199_000.0


def test_prop_desk_backfills_legacy_simulation_without_allocation(tmp_path):
    db, trader = _trader(tmp_path)
    saved = create_trade_plan(plan=_plan(), snapshot_payload=_snapshot(), trader_id=trader["trader_id"], db_path=db)
    from src.trade_journal import journal_connection
    with journal_connection(db) as con:
        con.execute("DROP TRIGGER IF EXISTS no_delete_prop_trade_allocations")
        con.execute("DELETE FROM prop_trade_allocations WHERE trade_id=?", (saved["trade_id"],))
    assert get_prop_allocation(saved["trade_id"], db_path=db) == {}
    state = prop_desk_state(trader["trader_id"], db_path=db)
    assert state["summary"]["starting_capital"] == 200000.0
    assert get_prop_allocation(saved["trade_id"], db_path=db)["sizing_status"] == "SIZED"
