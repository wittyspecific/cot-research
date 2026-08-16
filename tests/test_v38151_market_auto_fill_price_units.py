from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from src.live_execution import resolve_live_entry
from src.outcome_tracker import evaluate_trade_path, resolve_market_fill
from src.price_units import mt5_price_to_plan, plan_price_to_mt5, price_factor_to_mt5
from src.prop_desk import get_prop_allocation
from src.trade_journal import activate_simulation_trade_live, create_trade_plan, initialize_journal, validate_plan
from src.trader_auth import create_trader


def _market_plan(**overrides):
    plan = {
        "plan_type": "SIMULATION",
        "order_type": "MARKET",
        "asset_class": "Metals",
        "market_name": "Copper",
        "cot_symbol": "HG",
        "cfd_symbol": "XCUUSD",
        "side": "SHORT",
        "zone_type": "SUPPLY",
        "timeframe": "4H",
        "zone_low": 6.60,
        "zone_high": 6.70,
        "entry": None,
        "stop": 6.931,
        "target": 5.680,
        "requested_risk_pct": 0.005,
        "zone_freshness": "FRESH",
        "retest_count": 0,
        "quality_grade": "A",
        "notes": "market auto fill test",
    }
    plan.update(overrides)
    return plan


def _snapshot():
    return {
        "meta": {"test": True},
        "mt5_symbol": {
            "spec": {
                "symbol": "XCUUSD",
                "tick_size": 0.01,
                "tick_value": 1.0,
                "tick_value_loss": 1.0,
                "volume_min": 0.01,
                "volume_max": 100.0,
                "volume_step": 0.01,
            }
        },
        "research": {"available": False},
    }


def test_xcuusd_price_factor_round_trip():
    assert price_factor_to_mt5("XCUUSD") == 100.0
    assert price_factor_to_mt5("XCUUSD.c") == 100.0
    assert plan_price_to_mt5("XCUUSD", 6.931) == pytest.approx(693.10)
    assert mt5_price_to_plan("XCUUSD", 661.91) == pytest.approx(6.6191)


def test_market_plan_needs_no_manual_entry_and_has_no_planned_rr():
    plan = validate_plan(_market_plan())
    assert plan["market_entry_auto"] is True
    assert plan["entry"] == pytest.approx(6.65)  # schema-only zone-mid reference
    assert plan["planned_rr"] is None


def test_xcuusd_market_short_fills_next_fresh_bid_without_using_reference_entry():
    plan = _market_plan(created_at_utc="2026-08-17T00:00:00Z")
    quote = {
        "bid": 661.91,
        "ask": 662.45,
        "exported_at_utc": "2026-08-17T00:00:03Z",
        "tick_age_seconds": 1,
        "trade_mode": 4,
        "can_open": 1,
    }
    fill = resolve_live_entry(plan, quote, now="2026-08-17T00:00:04Z")
    assert fill is not None
    assert fill["lifecycle_status"] == "ACTIVE"
    assert fill["execution_price"] == pytest.approx(661.91)
    assert fill["live_trigger"] == "MARKET_NEXT_QUOTE"


def test_xcuusd_limit_touch_uses_mt5_scaled_entry():
    base = _market_plan(order_type="LIMIT", entry=6.637, created_at_utc="2026-08-17T00:00:00Z")
    quote_no_touch = {
        "bid": 662.00, "ask": 662.40, "exported_at_utc": "2026-08-17T00:00:03Z",
        "tick_age_seconds": 1, "trade_mode": 4, "can_open": 1,
    }
    assert resolve_live_entry(base, quote_no_touch, now="2026-08-17T00:00:04Z") is None
    quote_touch = dict(quote_no_touch, bid=664.00, ask=664.20)
    fill = resolve_live_entry(base, quote_touch, now="2026-08-17T00:00:04Z")
    assert fill is not None
    assert fill["execution_price"] == pytest.approx(664.00)


def test_market_prop_sizing_waits_for_actual_fill_then_freezes_lots(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    trader = create_trader(username="copper", display_name="Copper", password="Password123!", db_path=db)
    saved = create_trade_plan(
        plan=_market_plan(), snapshot_payload=_snapshot(), trader_id=trader["trader_id"], db_path=db
    )
    allocation = saved["prop_allocation"]
    assert allocation["sizing_status"] == "PENDING_FILL"
    assert math.isnan(float(allocation["lots"]))
    assert allocation["risk_budget"] == pytest.approx(1000.0)

    fill = {
        "tracker_version": "3.8.1.5.1",
        "lifecycle_status": "ACTIVE",
        "entry_triggered": 1,
        "entry_time_utc": "2026-08-17T00:00:03+00:00",
        "execution_price": 661.91,
        "fill_timeframe": "LIVE_TICK",
        "data_timeframe": "LIVE_TICK",
        "mae_r": 0.0,
        "mfe_r": 0.0,
        "holding_minutes": 0.0,
        "live_trigger": "MARKET_NEXT_QUOTE",
    }
    assert activate_simulation_trade_live(saved["trade_id"], fill, db_path=db) is True
    finalized = get_prop_allocation(saved["trade_id"], db_path=db)
    assert finalized["sizing_status"] == "SIZED"
    assert finalized["execution_sizing"]["execution_price"] == pytest.approx(661.91)
    assert finalized["execution_sizing"]["stop_price_mt5"] == pytest.approx(693.10)
    assert finalized["lots"] > 0
    assert finalized["actual_risk"] <= finalized["risk_budget"] + 1e-9


def test_history_market_fill_and_exit_use_scaled_stop_target():
    plan = _market_plan(created_at_utc="2026-08-17T00:00:00Z")
    m1 = pd.DataFrame([
        {"time": "2026-08-17T00:00:00Z", "open": 661.91, "high": 662.5, "low": 661.5, "close": 662.0},
    ])
    fill = resolve_market_fill(plan, m1, timeframe="M1", now="2026-08-17T00:02:00Z")
    assert fill["lifecycle_status"] == "ACTIVE"
    assert fill["execution_price"] == pytest.approx(661.91)

    effective = dict(plan)
    effective.update({
        "entry": 661.91,
        "_price_units": "MT5",
        "_resolved_entry_fill": True,
        "_entry_fill_source": "LIVE_TICK",
        "created_at_utc": "2026-08-17T00:00:00Z",
        "stop": 693.10,
        "target": 568.0,
    })
    h1 = pd.DataFrame([
        {"time": "2026-08-17T00:00:00Z", "open": 662.0, "high": 694.0, "low": 650.0, "close": 690.0},
    ])
    outcome = evaluate_trade_path(effective, h1, timeframe="H1", now="2026-08-17T02:00:00Z")
    assert outcome["lifecycle_status"] in {"CLOSED", "AMBIGUOUS"}
    if outcome["lifecycle_status"] == "CLOSED":
        assert outcome["first_exit"] == "STOP"
