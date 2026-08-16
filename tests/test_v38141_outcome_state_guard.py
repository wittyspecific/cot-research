from __future__ import annotations

import pandas as pd

import src.outcome_tracker as tracker
from src.mt5_account import MT5Config


def _active_market_row():
    return {
        "trade_id": "active-market-1",
        "created_at_utc": "2026-08-17T00:17:00Z",
        "plan_type": "SIMULATION",
        "order_type": "MARKET",
        "expiry_at_utc": None,
        "cfd_symbol": "XAUUSD",
        "side": "LONG",
        "entry": 100.0,
        "stop": 95.0,
        "target": 110.0,
        "lifecycle_status": "ACTIVE",
        "entry_triggered": 1,
        "entry_time_utc": "2026-08-17T00:18:00Z",
        "execution_price": 100.25,
        "fill_timeframe": "M1",
        "mae_r": -0.1,
        "mfe_r": 0.4,
    }


def test_existing_active_market_cannot_regress_to_planned_before_first_h1(monkeypatch):
    plans = pd.DataFrame([_active_market_row()])
    saved = {}
    previous = {
        "lifecycle_status": "ACTIVE",
        "entry_triggered": 1,
        "entry_time_utc": "2026-08-17T00:18:00Z",
        "execution_price": 100.25,
        "fill_timeframe": "M1",
        "mae_r": -0.1,
        "mfe_r": 0.4,
        "plus_1r_time_utc": None,
        "payload": {
            "lifecycle_status": "ACTIVE",
            "entry_triggered": 1,
            "entry_time_utc": "2026-08-17T00:18:00Z",
            "execution_price": 100.25,
            "fill_timeframe": "M1",
            "mae_r": -0.1,
            "mfe_r": 0.4,
        },
    }

    monkeypatch.setattr(tracker, "list_trade_plans", lambda **kwargs: plans)
    monkeypatch.setattr(tracker, "get_trade_outcome", lambda *args, **kwargs: previous)
    calls = []
    def fake_history(_config, requests, timeout_seconds=12.0):
        reqs = list(requests)
        calls.extend(r.timeframe for r in reqs)
        return {r.request_id: pd.DataFrame() for r in reqs}
    monkeypatch.setattr(tracker, "history_batch", fake_history)
    monkeypatch.setattr(
        tracker,
        "upsert_trade_outcome",
        lambda trade_id, outcome, **kwargs: saved.setdefault(trade_id, outcome),
    )

    result = tracker.sync_trade_outcomes(
        MT5Config(mode="bridge"), db_path=None, now="2026-08-17T00:28:00Z"
    )

    out = saved["active-market-1"]
    assert out["lifecycle_status"] == "ACTIVE"
    assert out["entry_triggered"] == 1
    assert out["execution_price"] == 100.25
    assert pd.Timestamp(out["entry_time_utc"]) == pd.Timestamp("2026-08-17T00:18:00Z")
    # No completed H1 exists yet; only optional D1 forward-return maintenance may run.
    assert "H1" not in calls
    assert out["mfe_r"] == 0.4
    assert result["state_regressions_blocked"] == 0




def test_active_to_planned_is_blocked_and_preserves_previous_outcome(monkeypatch):
    previous = {
        "lifecycle_status": "ACTIVE",
        "entry_triggered": 1,
        "entry_time_utc": "2026-08-17T00:18:00Z",
        "execution_price": 100.25,
        "fill_timeframe": "LIVE_TICK",
        "mfe_r": 0.4,
        "payload": {
            "lifecycle_status": "ACTIVE",
            "entry_triggered": 1,
            "entry_time_utc": "2026-08-17T00:18:00Z",
            "execution_price": 100.25,
            "fill_timeframe": "LIVE_TICK",
            "mfe_r": 0.4,
        },
    }
    monkeypatch.setattr(tracker, "get_trade_outcome", lambda *args, **kwargs: previous)
    guarded, blocked = tracker._guard_active_state_regression(
        "t1", "ACTIVE", {"lifecycle_status": "PLANNED", "entry_triggered": 0}, db_path=None
    )
    assert blocked is True
    assert guarded["lifecycle_status"] == "ACTIVE"
    assert guarded["entry_triggered"] == 1
    assert guarded["execution_price"] == 100.25
    assert guarded["mfe_r"] == 0.4

def test_active_to_expired_is_blocked_and_preserves_previous_outcome(monkeypatch):
    previous = {
        "lifecycle_status": "ACTIVE",
        "entry_triggered": 1,
        "entry_time_utc": "2026-08-17T00:18:00Z",
        "execution_price": 100.25,
        "fill_timeframe": "M1",
        "payload": {
            "lifecycle_status": "ACTIVE",
            "entry_triggered": 1,
            "entry_time_utc": "2026-08-17T00:18:00Z",
            "execution_price": 100.25,
            "fill_timeframe": "M1",
        },
    }
    monkeypatch.setattr(tracker, "get_trade_outcome", lambda *args, **kwargs: previous)
    guarded, blocked = tracker._guard_active_state_regression(
        "t1", "ACTIVE", {"lifecycle_status": "EXPIRED", "entry_triggered": 0}, db_path=None
    )
    assert blocked is True
    assert guarded["lifecycle_status"] == "ACTIVE"
    assert guarded["entry_triggered"] == 1
    assert guarded["execution_price"] == 100.25


def test_active_may_progress_to_closed_or_ambiguous(monkeypatch):
    monkeypatch.setattr(
        tracker,
        "get_trade_outcome",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("guard should not fetch previous")),
    )
    closed, blocked_closed = tracker._guard_active_state_regression(
        "t1", "ACTIVE", {"lifecycle_status": "CLOSED", "result_r": 2.0}, db_path=None
    )
    ambiguous, blocked_ambiguous = tracker._guard_active_state_regression(
        "t1", "ACTIVE", {"lifecycle_status": "AMBIGUOUS"}, db_path=None
    )
    assert blocked_closed is False and closed["lifecycle_status"] == "CLOSED"
    assert blocked_ambiguous is False and ambiguous["lifecycle_status"] == "AMBIGUOUS"
