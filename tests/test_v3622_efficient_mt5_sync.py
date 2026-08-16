from __future__ import annotations

from pathlib import Path

import pandas as pd

import src.outcome_tracker as tracker
from src.mt5_account import MT5Config
from src.mt5_history import HistoryRequest
from src.mt5_history_cache import load_cached_bars, missing_intervals
from src.trade_journal import initialize_journal, journal_connection


def _plan(trade_id: str, *, symbol: str = "XAUUSD", **updates) -> dict:
    plan = {
        "trade_id": trade_id,
        "created_at_utc": "2026-08-16T10:00:00Z",
        "plan_type": "SIMULATION",
        "order_type": "LIMIT",
        "expiry_at_utc": None,
        "cfd_symbol": symbol,
        "side": "LONG",
        "entry": 100.0,
        "stop": 95.0,
        "target": 110.0,
        "entry_triggered": 0,
        "lifecycle_status": "PLANNED",
    }
    plan.update(updates)
    return plan


def _h1_waiting() -> pd.DataFrame:
    return pd.DataFrame([
        ("2026-08-16T10:00:00Z", 105, 106, 102, 104),
        ("2026-08-16T11:00:00Z", 104, 105, 101, 103),
        ("2026-08-16T12:00:00Z", 103, 104, 101, 102),
    ], columns=["time", "open", "high", "low", "close"])


def test_sync_requests_only_planned_and_active(monkeypatch, tmp_path: Path):
    captured = {}

    def fake_list(**kwargs):
        captured.update(kwargs)
        return pd.DataFrame()

    monkeypatch.setattr(tracker, "list_trade_plans", fake_list)
    result = tracker.sync_trade_outcomes(MT5Config(mode="bridge"), db_path=tmp_path / "j.sqlite3")
    assert tuple(captured["lifecycle_statuses"]) == ("PLANNED", "ACTIVE")
    assert result["checked"] == 0


def test_same_symbol_multiple_trades_are_deduplicated_to_one_mt5_h1_request(monkeypatch, tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    plans = pd.DataFrame([_plan("trade-a"), _plan("trade-b")])
    calls = []

    def fake_history(_config, requests, timeout_seconds=12.0):
        reqs = list(requests)
        calls.append(reqs)
        return {r.request_id: _h1_waiting() if r.timeframe == "H1" else pd.DataFrame() for r in reqs}

    monkeypatch.setattr(tracker, "list_trade_plans", lambda **kwargs: plans)
    monkeypatch.setattr(tracker, "history_batch", fake_history)
    monkeypatch.setattr(tracker, "upsert_trade_outcome", lambda *args, **kwargs: None)

    result = tracker.sync_trade_outcomes(
        MT5Config(mode="bridge"), db_path=db, now="2026-08-16T13:00:00Z"
    )
    assert len(calls) == 1
    assert len(calls[0]) == 1
    assert calls[0][0].symbol == "XAUUSD"
    assert calls[0][0].timeframe == "H1"
    assert result["remote_requests"] == 1
    assert result["symbols_checked"] == 1
    assert result["bars_loaded_by_timeframe"]["H1"] == 3


def test_second_sync_same_range_is_served_entirely_from_local_cache(monkeypatch, tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    plans = pd.DataFrame([_plan("trade-a")])
    calls = []

    def first_history(_config, requests, timeout_seconds=12.0):
        reqs = list(requests)
        calls.append(reqs)
        return {r.request_id: _h1_waiting() for r in reqs}

    monkeypatch.setattr(tracker, "list_trade_plans", lambda **kwargs: plans)
    monkeypatch.setattr(tracker, "history_batch", first_history)
    monkeypatch.setattr(tracker, "upsert_trade_outcome", lambda *args, **kwargs: None)
    tracker.sync_trade_outcomes(MT5Config(mode="bridge"), db_path=db, now="2026-08-16T13:00:00Z")
    assert len(calls) == 1

    def must_not_call(*args, **kwargs):
        raise AssertionError("MT5 must not be queried when the requested range is fully cached")

    monkeypatch.setattr(tracker, "history_batch", must_not_call)
    result = tracker.sync_trade_outcomes(MT5Config(mode="bridge"), db_path=db, now="2026-08-16T13:00:00Z")
    assert result["remote_requests"] == 0
    assert result["cache_only_requests"] >= 1


def test_empty_checked_range_is_cached_so_weekend_is_not_requested_repeatedly(monkeypatch, tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    request = HistoryRequest(
        "XAUUSD", "2026-08-16T00:00:00Z", "2026-08-16T12:00:00Z", "H1", "weekend"
    )
    calls = []

    def empty_history(_config, requests, timeout_seconds=12.0):
        reqs = list(requests)
        calls.append(reqs)
        return {r.request_id: pd.DataFrame() for r in reqs}

    monkeypatch.setattr(tracker, "history_batch", empty_history)
    result, stats = tracker._cached_history_batch(
        MT5Config(mode="bridge"), [request], db_path=db, timeout_seconds=5.0
    )
    assert result["weekend"].empty
    assert stats["remote_requests"] == 1
    assert missing_intervals("XAUUSD", "H1", request.start_utc, request.end_utc, db_path=db) == []

    monkeypatch.setattr(tracker, "history_batch", lambda *a, **k: (_ for _ in ()).throw(AssertionError("repeat request")))
    _, stats2 = tracker._cached_history_batch(
        MT5Config(mode="bridge"), [request], db_path=db, timeout_seconds=5.0
    )
    assert stats2["remote_requests"] == 0
    assert stats2["cache_only_requests"] == 1



def test_later_sync_fetches_only_the_missing_h1_tail(monkeypatch, tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    plans = pd.DataFrame([_plan("trade-a")])
    calls: list[list[HistoryRequest]] = []

    def fake_history(_config, requests, timeout_seconds=12.0):
        reqs = list(requests)
        calls.append(reqs)
        out = {}
        for r in reqs:
            start = pd.Timestamp(r.start_utc)
            end = pd.Timestamp(r.end_utc)
            times = pd.date_range(start, end, freq="h", inclusive="left")
            out[r.request_id] = pd.DataFrame({
                "time": times,
                "open": [105.0] * len(times),
                "high": [106.0] * len(times),
                "low": [101.0] * len(times),
                "close": [104.0] * len(times),
            })
        return out

    monkeypatch.setattr(tracker, "list_trade_plans", lambda **kwargs: plans)
    monkeypatch.setattr(tracker, "history_batch", fake_history)
    monkeypatch.setattr(tracker, "upsert_trade_outcome", lambda *args, **kwargs: None)

    tracker.sync_trade_outcomes(MT5Config(mode="bridge"), db_path=db, now="2026-08-16T13:00:00Z")
    assert pd.Timestamp(calls[0][0].start_utc) == pd.Timestamp("2026-08-16T10:00:00Z")
    assert pd.Timestamp(calls[0][0].end_utc) == pd.Timestamp("2026-08-16T13:00:00Z")

    calls.clear()
    result = tracker.sync_trade_outcomes(MT5Config(mode="bridge"), db_path=db, now="2026-08-16T15:00:00Z")
    assert len(calls) == 1
    assert len(calls[0]) == 1
    assert pd.Timestamp(calls[0][0].start_utc) == pd.Timestamp("2026-08-16T13:00:00Z")
    assert pd.Timestamp(calls[0][0].end_utc) == pd.Timestamp("2026-08-16T15:00:00Z")
    assert result["bars_loaded_by_timeframe"]["H1"] == 2


def test_incomplete_current_h1_bar_is_not_requested_or_cached(monkeypatch, tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    plans = pd.DataFrame([_plan("trade-now", created_at_utc="2026-08-16T10:17:00Z")])

    monkeypatch.setattr(tracker, "list_trade_plans", lambda **kwargs: plans)
    monkeypatch.setattr(tracker, "history_batch", lambda *a, **k: (_ for _ in ()).throw(AssertionError("current partial H1 must not be fetched")))
    monkeypatch.setattr(tracker, "upsert_trade_outcome", lambda *args, **kwargs: None)

    result = tracker.sync_trade_outcomes(MT5Config(mode="bridge"), db_path=db, now="2026-08-16T10:30:00Z")
    assert result["remote_requests"] == 0
    assert result["status_counts"]["PLANNED"] == 1

def test_history_cache_schema_is_persistent_and_bars_are_queryable(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    initialize_journal(db)
    with journal_connection(db) as con:
        names = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "mt5_history_bars" in names
    assert "mt5_history_coverage" in names


def test_trading_journal_defaults_to_manual_sync():
    source = Path("pages/trading_journal.py").read_text()
    assert 'Beim ersten Öffnen des Journals automatisch nachholen", value=False' in source


def test_journal_status_filter_returns_only_open_plans(tmp_path: Path):
    from src.trade_journal import create_trade_plan, list_trade_plans, upsert_trade_outcome

    db = tmp_path / "journal.sqlite3"
    ids = []
    for symbol in ["XAUUSD", "AUDJPY", "NATGAS.cash"]:
        saved = create_trade_plan(
            plan={
                "plan_type": "SIMULATION", "order_type": "LIMIT", "cfd_symbol": symbol,
                "side": "LONG", "zone_type": "DEMAND", "timeframe": "4H",
                "entry": 100.0, "stop": 95.0, "target": 110.0,
            },
            snapshot_payload={"test": symbol}, db_path=db,
        )
        ids.append(saved["trade_id"])
    upsert_trade_outcome(ids[1], {"lifecycle_status": "ACTIVE", "entry_triggered": 1}, db_path=db)
    upsert_trade_outcome(ids[2], {"lifecycle_status": "CLOSED", "entry_triggered": 1, "result_r": 2.0}, db_path=db)

    open_plans = list_trade_plans(db_path=db, lifecycle_statuses=("PLANNED", "ACTIVE"))
    assert set(open_plans["cfd_symbol"]) == {"XAUUSD", "AUDJPY"}
