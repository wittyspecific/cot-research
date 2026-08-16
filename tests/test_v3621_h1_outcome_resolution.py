from __future__ import annotations

import pandas as pd
import pytest

import src.outcome_tracker as tracker
from src.mt5_account import MT5Config


def _plan(**updates):
    base = {
        "trade_id": "trade-1",
        "created_at_utc": "2026-08-16T10:00:00Z",
        "plan_type": "SIMULATION",
        "order_type": "LIMIT",
        "expiry_at_utc": None,
        "cfd_symbol": "XAUUSD",
        "side": "LONG",
        "entry": 100.0,
        "stop": 95.0,
        "target": 110.0,
        "entry_triggered": 0,
    }
    base.update(updates)
    return base


def _bars(rows):
    return pd.DataFrame(rows, columns=["time", "open", "high", "low", "close"])


def test_swing_tracker_uses_h1_as_primary_timeframe():
    assert tracker.PRIMARY_TIMEFRAME == "H1"
    assert tracker.RESOLUTION_TIMEFRAMES == ("M5", "M1")


def test_partial_h1_start_entry_touch_requires_refinement():
    plan = _plan(created_at_utc="2026-08-16T10:17:00Z")
    h1 = _bars([
        ("2026-08-16T10:00:00Z", 105, 106, 99, 104),
        ("2026-08-16T11:00:00Z", 104, 106, 103, 105),
    ])
    out = tracker.evaluate_trade_path(plan, h1, timeframe="H1", now="2026-08-16T12:00:00Z")
    assert out["lifecycle_status"] == "AMBIGUOUS"
    assert out["ambiguity_reason"] == "ENTRY_TOUCH_IN_PARTIAL_START_BAR"


def test_entry_touch_in_h1_expiry_bar_requires_refinement():
    plan = _plan(expiry_at_utc="2026-08-16T11:30:00Z")
    h1 = _bars([
        ("2026-08-16T10:00:00Z", 105, 106, 102, 104),
        ("2026-08-16T11:00:00Z", 104, 105, 99, 101),
    ])
    out = tracker.evaluate_trade_path(plan, h1, timeframe="H1", now="2026-08-16T12:00:00Z")
    assert out["lifecycle_status"] == "AMBIGUOUS"
    assert out["ambiguity_reason"] == "ENTRY_TOUCH_IN_EXPIRY_BAR"


def test_sync_uses_only_h1_when_path_is_unambiguous(monkeypatch):
    plans = pd.DataFrame([_plan()])
    calls: list[list[str]] = []
    saved: dict[str, dict] = {}

    def fake_history(_config, requests, timeout_seconds=12.0):
        reqs = list(requests)
        calls.append([r.timeframe for r in reqs])
        out = {}
        for r in reqs:
            if r.timeframe == "H1":
                out[r.request_id] = _bars([
                    ("2026-08-16T10:00:00Z", 105, 106, 101, 103),
                    ("2026-08-16T11:00:00Z", 103, 104, 100, 101),
                    ("2026-08-16T12:00:00Z", 101, 111, 100, 110),
                ])
            elif r.timeframe == "D1":
                out[r.request_id] = _bars([])
            else:
                raise AssertionError(f"Unexpected finer request: {r.timeframe}")
        return out

    monkeypatch.setattr(tracker, "list_trade_plans", lambda **kwargs: plans)
    monkeypatch.setattr(tracker, "history_batch", fake_history)
    monkeypatch.setattr(tracker, "upsert_trade_outcome", lambda trade_id, outcome, **kwargs: saved.setdefault(trade_id, outcome))

    result = tracker.sync_trade_outcomes(MT5Config(mode="bridge"), now="2026-08-16T13:00:00Z")
    assert calls[0] == ["H1"]
    assert not any("M5" in call or "M1" in call for call in calls)
    assert saved["trade-1"]["data_timeframe"] == "H1"
    assert saved["trade-1"]["lifecycle_status"] == "CLOSED"
    assert result["ambiguous"] == 0


def test_sync_falls_back_h1_to_m5_only_when_needed(monkeypatch):
    plans = pd.DataFrame([_plan()])
    calls: list[list[str]] = []
    saved: dict[str, dict] = {}

    def fake_history(_config, requests, timeout_seconds=12.0):
        reqs = list(requests)
        calls.append([r.timeframe for r in reqs])
        out = {}
        for r in reqs:
            if r.timeframe == "H1":
                # Entry and target occur somewhere in the same H1 bar -> ambiguous.
                out[r.request_id] = _bars([
                    ("2026-08-16T10:00:00Z", 105, 106, 101, 103),
                    ("2026-08-16T11:00:00Z", 103, 111, 99, 108),
                ])
            elif r.timeframe == "M5":
                out[r.request_id] = _bars([
                    ("2026-08-16T10:00:00Z", 105, 106, 101, 103),
                    ("2026-08-16T10:55:00Z", 103, 104, 101, 102),
                    ("2026-08-16T11:00:00Z", 102, 103, 100, 101),
                    ("2026-08-16T11:05:00Z", 101, 104, 100, 103),
                    ("2026-08-16T11:10:00Z", 103, 111, 102, 110),
                ])
            elif r.timeframe == "D1":
                out[r.request_id] = _bars([])
            elif r.timeframe == "M1":
                raise AssertionError("M1 must not be requested when M5 resolves the path")
        return out

    monkeypatch.setattr(tracker, "list_trade_plans", lambda **kwargs: plans)
    monkeypatch.setattr(tracker, "history_batch", fake_history)
    monkeypatch.setattr(tracker, "upsert_trade_outcome", lambda trade_id, outcome, **kwargs: saved.setdefault(trade_id, outcome))

    tracker.sync_trade_outcomes(MT5Config(mode="bridge"), now="2026-08-16T13:00:00Z")
    assert calls[0] == ["H1"]
    assert calls[1] == ["M5"]
    assert not any("M1" in call for call in calls)
    assert saved["trade-1"]["data_timeframe"] == "M5"
    assert saved["trade-1"]["first_exit"] == "TARGET"


def test_sync_uses_m1_only_if_m5_is_still_ambiguous(monkeypatch):
    plans = pd.DataFrame([_plan()])
    calls: list[list[str]] = []
    saved: dict[str, dict] = {}

    def fake_history(_config, requests, timeout_seconds=12.0):
        reqs = list(requests)
        calls.append([r.timeframe for r in reqs])
        out = {}
        for r in reqs:
            if r.timeframe == "H1":
                out[r.request_id] = _bars([
                    ("2026-08-16T10:00:00Z", 105, 106, 101, 103),
                    ("2026-08-16T11:00:00Z", 103, 111, 94, 102),
                ])
            elif r.timeframe == "M5":
                out[r.request_id] = _bars([
                    ("2026-08-16T10:00:00Z", 105, 106, 101, 103),
                    ("2026-08-16T11:00:00Z", 103, 104, 100, 101),
                    ("2026-08-16T11:05:00Z", 101, 111, 94, 102),
                ])
            elif r.timeframe == "M1":
                out[r.request_id] = _bars([
                    ("2026-08-16T10:00:00Z", 105, 106, 101, 103),
                    ("2026-08-16T11:00:00Z", 101, 103, 100, 102),
                    ("2026-08-16T11:01:00Z", 102, 104, 100, 103),
                    ("2026-08-16T11:02:00Z", 103, 106, 102, 105),
                    ("2026-08-16T11:03:00Z", 105, 111, 104, 110),
                ])
            elif r.timeframe == "D1":
                out[r.request_id] = _bars([])
        return out

    monkeypatch.setattr(tracker, "list_trade_plans", lambda **kwargs: plans)
    monkeypatch.setattr(tracker, "history_batch", fake_history)
    monkeypatch.setattr(tracker, "upsert_trade_outcome", lambda trade_id, outcome, **kwargs: saved.setdefault(trade_id, outcome))

    tracker.sync_trade_outcomes(MT5Config(mode="bridge"), now="2026-08-16T13:00:00Z")
    assert calls[0] == ["H1"]
    assert calls[1] == ["M5"]
    assert calls[2] == ["M1"]
    assert saved["trade-1"]["data_timeframe"] == "M1"
    assert saved["trade-1"]["first_exit"] == "TARGET"
