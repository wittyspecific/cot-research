from __future__ import annotations

from pathlib import Path

import pandas as pd

import src.outcome_tracker as tracker
from src.mt5_account import MT5Config
from src.mt5_history import HistoryRequest
from src.prop_desk import _effective_entry, _effective_risk_usd, _floating_pnl
from src.trade_journal import initialize_journal, journal_connection


def _bars(rows):
    return pd.DataFrame(rows, columns=["time", "open", "high", "low", "close"])


def _market_plan(trade_id="market-1", **updates):
    plan = {
        "trade_id": trade_id,
        "created_at_utc": "2026-08-16T10:17:42Z",
        "plan_type": "SIMULATION",
        "order_type": "MARKET",
        "expiry_at_utc": None,
        "cfd_symbol": "XAUUSD",
        "side": "LONG",
        "entry": 100.0,
        "stop": 95.0,
        "target": 110.0,
        "entry_triggered": 0,
        "execution_price": None,
        "fill_timeframe": None,
        "lifecycle_status": "PLANNED",
    }
    plan.update(updates)
    return plan


def _limit_plan(trade_id="limit-1", **updates):
    plan = _market_plan(trade_id, order_type="LIMIT")
    plan.update(updates)
    return plan


def test_market_fill_after_closed_market_uses_first_future_m15_open():
    plan = _market_plan(created_at_utc="2026-08-16T17:30:00Z", side="SHORT", stop=2700.0, target=2500.0, entry=2640.0)
    bars = _bars([
        ("2026-08-17T00:00:00Z", 2658.0, 2662.0, 2650.0, 2654.0),
        ("2026-08-17T00:15:00Z", 2654.0, 2656.0, 2648.0, 2650.0),
    ])
    out = tracker.resolve_market_fill(plan, bars, timeframe="M15", now="2026-08-17T00:30:00Z")
    assert out["lifecycle_status"] == "ACTIVE"
    assert out["execution_price"] == 2658.0
    assert pd.Timestamp(out["entry_time_utc"]) == pd.Timestamp("2026-08-17T00:00:00Z")
    assert out["fill_timeframe"] == "M15"


def test_market_history_safety_net_uses_direct_m1_fill(monkeypatch):
    plans = pd.DataFrame([_market_plan()])
    calls: list[list[str]] = []
    saved = {}

    def fake_history(_config, requests, timeout_seconds=12.0):
        reqs = list(requests)
        calls.append([r.timeframe for r in reqs])
        out = {}
        for r in reqs:
            if r.timeframe == "M15":
                out[r.request_id] = _bars([("2026-08-16T10:15:00Z", 100.0, 101.0, 99.0, 100.4)])
            elif r.timeframe == "M5":
                out[r.request_id] = _bars([
                    ("2026-08-16T10:15:00Z", 100.0, 100.7, 99.8, 100.3),
                    ("2026-08-16T10:20:00Z", 100.3, 100.8, 100.1, 100.5),
                ])
            elif r.timeframe == "M1":
                out[r.request_id] = _bars([
                    ("2026-08-16T10:17:00Z", 100.10, 100.30, 100.00, 100.20),
                    ("2026-08-16T10:18:00Z", 100.25, 100.50, 100.20, 100.40),
                    ("2026-08-16T10:19:00Z", 100.40, 100.60, 100.30, 100.50),
                ])
            elif r.timeframe == "H1":
                out[r.request_id] = _bars([("2026-08-16T10:00:00Z", 100.0, 104.0, 96.0, 102.0)])
            else:
                out[r.request_id] = _bars([])
        return out

    monkeypatch.setattr(tracker, "list_trade_plans", lambda **kwargs: plans)
    monkeypatch.setattr(tracker, "history_batch", fake_history)
    monkeypatch.setattr(tracker, "upsert_trade_outcome", lambda trade_id, outcome, **kwargs: saved.setdefault(trade_id, outcome))

    tracker.sync_trade_outcomes(MT5Config(mode="bridge"), db_path=None, now="2026-08-16T11:00:00Z")
    flat = [tf for batch in calls for tf in batch]
    assert flat[:2] == ["M1", "H1"]
    assert saved["market-1"]["lifecycle_status"] == "ACTIVE"
    assert saved["market-1"]["execution_price"] == 100.25
    assert pd.Timestamp(saved["market-1"]["entry_time_utc"]) == pd.Timestamp("2026-08-16T10:18:00Z")
    assert saved["market-1"]["fill_timeframe"] == "M1"


def test_market_history_safety_net_does_not_request_m15_or_m5(monkeypatch):
    plans = pd.DataFrame([_market_plan(created_at_utc="2026-08-16T10:15:00Z")])
    calls = []
    saved = {}

    def fake_history(_config, requests, timeout_seconds=12.0):
        reqs = list(requests)
        calls.extend(r.timeframe for r in reqs)
        out = {}
        for r in reqs:
            if r.timeframe == "M1":
                out[r.request_id] = _bars([("2026-08-16T10:15:00Z", 100.2, 101.0, 99.5, 100.5)])
            elif r.timeframe == "H1":
                out[r.request_id] = _bars([("2026-08-16T10:00:00Z", 100.0, 104.0, 96.0, 102.0)])
            else:
                out[r.request_id] = _bars([])
        return out

    monkeypatch.setattr(tracker, "list_trade_plans", lambda **kwargs: plans)
    monkeypatch.setattr(tracker, "history_batch", fake_history)
    monkeypatch.setattr(tracker, "upsert_trade_outcome", lambda trade_id, outcome, **kwargs: saved.setdefault(trade_id, outcome))

    tracker.sync_trade_outcomes(MT5Config(mode="bridge"), db_path=None, now="2026-08-16T11:00:00Z")
    assert calls[0] == "M1"
    assert "M15" not in calls and "M5" not in calls
    assert saved["market-1"]["execution_price"] == 100.2
    assert saved["market-1"]["fill_timeframe"] == "M1"


def test_market_waits_until_first_m1_bar_is_complete(monkeypatch):
    plans = pd.DataFrame([_market_plan()])
    saved = {}
    monkeypatch.setattr(tracker, "list_trade_plans", lambda **kwargs: plans)
    monkeypatch.setattr(tracker, "history_batch", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no completed M15 -> no MT5 request")))
    monkeypatch.setattr(tracker, "upsert_trade_outcome", lambda trade_id, outcome, **kwargs: saved.setdefault(trade_id, outcome))

    result = tracker.sync_trade_outcomes(MT5Config(mode="bridge"), db_path=None, now="2026-08-16T10:17:50Z")
    assert result["remote_requests"] == 0
    assert saved["market-1"]["lifecycle_status"] == "PLANNED"


def test_limit_plans_still_start_with_h1_and_never_request_m15(monkeypatch):
    plans = pd.DataFrame([_limit_plan()])
    calls = []

    def fake_history(_config, requests, timeout_seconds=12.0):
        reqs = list(requests)
        calls.extend(r.timeframe for r in reqs)
        return {r.request_id: _bars([("2026-08-16T10:00:00Z", 105.0, 106.0, 101.0, 104.0)]) if r.timeframe == "H1" else _bars([]) for r in reqs}

    monkeypatch.setattr(tracker, "list_trade_plans", lambda **kwargs: plans)
    monkeypatch.setattr(tracker, "history_batch", fake_history)
    monkeypatch.setattr(tracker, "upsert_trade_outcome", lambda *args, **kwargs: None)

    tracker.sync_trade_outcomes(MT5Config(mode="bridge"), db_path=None, now="2026-08-16T11:00:00Z")
    assert calls[0] == "H1"
    assert "M15" not in calls


def test_prop_desk_uses_resolved_market_fill_for_pnl_and_stop_risk():
    row = {
        "side": "LONG", "entry": 100.0, "execution_price": 102.0, "stop": 95.0,
        "lots": 2.0, "tick_size": 1.0, "tick_value": 10.0, "actual_risk": 100.0,
    }
    assert _effective_entry(row) == 102.0
    assert _effective_risk_usd(row) == 140.0
    assert _floating_pnl(row, 105.0) == 60.0


def test_m15_supported_by_history_bridge_cache_and_outcome_schema(tmp_path: Path):
    req = HistoryRequest("XAUUSD", "2026-08-16T10:00:00Z", "2026-08-16T11:00:00Z", "M15", "m15").normalized()
    assert req.timeframe == "M15"
    source = Path("mt5/MT5ReadOnlyBridge.mq5").read_text()
    assert 'if(text=="M15") return PERIOD_M15;' in source

    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    with journal_connection(db) as con:
        cols = {row[1] for row in con.execute("PRAGMA table_info(trade_outcomes)").fetchall()}
    assert {"execution_price", "fill_timeframe"}.issubset(cols)
