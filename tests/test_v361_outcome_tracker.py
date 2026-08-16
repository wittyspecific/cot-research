from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.outcome_tracker import add_forward_returns, evaluate_trade_path
from src.trade_journal import create_trade_plan, initialize_journal, list_trade_plans, upsert_trade_outcome


def _plan(**updates):
    base = {
        "trade_id": "x",
        "created_at_utc": "2026-08-16T10:01:00+00:00",
        "plan_type": "SIMULATION",
        "order_type": "LIMIT",
        "expiry_at_utc": None,
        "cfd_symbol": "XAUUSD",
        "side": "LONG",
        "entry": 100.0,
        "stop": 95.0,
        "target": 110.0,
    }
    base.update(updates)
    return base


def _bars(rows):
    return pd.DataFrame(rows, columns=["time", "open", "high", "low", "close"])


def test_limit_waits_until_entry_is_reached():
    bars = _bars([
        ("2026-08-16T10:05:00Z", 105, 106, 101, 103),
        ("2026-08-16T10:10:00Z", 103, 104, 100.0, 101),
        ("2026-08-16T10:15:00Z", 101, 111, 100, 110),
    ])
    out = evaluate_trade_path(_plan(), bars, timeframe="M5", now="2026-08-16T11:00:00Z")
    assert out["entry_triggered"] == 1
    assert out["lifecycle_status"] == "CLOSED"
    assert out["first_exit"] == "TARGET"
    assert out["result_r"] == pytest.approx(2.0)


def test_untriggered_limit_can_expire():
    bars = _bars([("2026-08-16T10:05:00Z", 105, 106, 102, 104)])
    out = evaluate_trade_path(
        _plan(expiry_at_utc="2026-08-16T10:30:00Z"),
        bars,
        timeframe="M5",
        now="2026-08-16T11:00:00Z",
    )
    assert out["entry_triggered"] == 0
    assert out["lifecycle_status"] == "EXPIRED"


def test_stop_before_target_is_minus_one_r():
    bars = _bars([
        ("2026-08-16T10:05:00Z", 102, 103, 99, 101),
        ("2026-08-16T10:10:00Z", 100, 104, 94, 96),
        ("2026-08-16T10:15:00Z", 96, 112, 96, 111),
    ])
    out = evaluate_trade_path(_plan(), bars, timeframe="M5", now="2026-08-16T11:00:00Z")
    assert out["first_exit"] == "STOP"
    assert out["result_r"] == -1.0


def test_same_bar_stop_and_target_is_never_guessed():
    bars = _bars([
        ("2026-08-16T10:05:00Z", 102, 103, 99, 101),
        ("2026-08-16T10:10:00Z", 100, 111, 94, 102),
    ])
    out = evaluate_trade_path(_plan(), bars, timeframe="M5", now="2026-08-16T11:00:00Z")
    assert out["lifecycle_status"] == "AMBIGUOUS"
    assert out["ambiguity_reason"] == "STOP_AND_TARGET_SAME_BAR"


def test_entry_and_exit_same_bar_is_ambiguous_for_limit_order():
    bars = _bars([("2026-08-16T10:05:00Z", 108, 111, 99, 109)])
    out = evaluate_trade_path(_plan(), bars, timeframe="M5", now="2026-08-16T11:00:00Z")
    assert out["lifecycle_status"] == "AMBIGUOUS"
    assert out["ambiguity_reason"] == "ENTRY_AND_EXIT_SAME_BAR"


def test_mfe_mae_and_r_milestones_are_recorded():
    bars = _bars([
        ("2026-08-16T10:05:00Z", 101, 102, 99, 101),
        ("2026-08-16T10:10:00Z", 101, 106, 98, 105),
        ("2026-08-16T10:15:00Z", 105, 111, 104, 110),
    ])
    out = evaluate_trade_path(_plan(), bars, timeframe="M5", now="2026-08-16T11:00:00Z")
    assert out["mfe_r"] >= 2.0
    assert out["mae_r"] <= -0.4
    assert out["plus_1r_time_utc"] is not None
    assert out["plus_2r_time_utc"] is not None


def test_forward_returns_are_direction_adjusted_trading_day_closes():
    daily = _bars([
        ("2026-08-16T00:00:00Z", 100, 101, 99, 100),
        ("2026-08-17T00:00:00Z", 100, 103, 99, 102),
        ("2026-08-18T00:00:00Z", 102, 105, 101, 104),
        ("2026-08-19T00:00:00Z", 104, 106, 103, 105),
    ])
    out = add_forward_returns({"entry_triggered": 1, "entry_time_utc": "2026-08-16T10:05:00Z"}, _plan(), daily)
    assert out["forward_1d"] == pytest.approx(0.02)
    assert out["forward_3d"] == pytest.approx(0.05)


def test_persistent_schema_migrates_and_stores_tracker_fields(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    saved = create_trade_plan(
        plan={
            "plan_type": "SIMULATION", "order_type": "LIMIT", "expiry_at_utc": "2026-08-30T00:00:00Z",
            "cfd_symbol": "XAUUSD", "side": "LONG", "zone_type": "DEMAND", "timeframe": "4H",
            "entry": 100, "stop": 95, "target": 110,
        },
        snapshot_payload={"test": 1}, db_path=db,
    )
    upsert_trade_outcome(saved["trade_id"], {"lifecycle_status": "ACTIVE", "entry_triggered": 1, "data_timeframe": "M5"}, db_path=db)
    row = list_trade_plans(db_path=db).iloc[0]
    assert row["order_type"] == "LIMIT"
    assert row["lifecycle_status"] == "ACTIVE"
