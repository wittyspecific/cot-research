from pathlib import Path

import pandas as pd

from src.mt5_history_cache import (
    ensure_history_time_basis,
    load_cached_bars,
    missing_intervals,
    store_history_segment,
)


def test_bridge_converts_utc_requests_to_server_time_and_back():
    root = Path(__file__).resolve().parents[1]
    source = (root / "mt5" / "MT5ReadOnlyBridge.mq5").read_text(encoding="utf-8")

    assert '#property version   "3.81' in source
    assert "MeasuredServerUtcOffsetSeconds" in source
    assert "HistoryServerUtcOffsetSecondsAt" in source
    assert "UtcUnixToServerDatetime" in source
    assert "ServerDatetimeToUtcUnix" in source
    assert "server_from=UtcUnixToServerDatetime(from_unix)" in source
    assert "server_to=UtcUnixToServerDatetime(to_unix)" in source
    assert "CopyRates(symbol, timeframe, server_from, server_to, rates)" in source
    assert "ServerDatetimeToUtcUnix(rates[i].time)" in source
    assert "IsUsDstUtc" in source
    assert "3*3600 : 2*3600" in source


def test_timezone_upgrade_invalidates_old_bar_and_coverage_cache_once(tmp_path):
    db = tmp_path / "journal.sqlite3"
    bars = pd.DataFrame([
        {
            "time": "2026-08-14T12:00:00Z",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "tick_volume": 10,
            "spread": 2,
            "real_volume": 0,
        }
    ])
    start = pd.Timestamp("2026-08-14T12:00:00Z")
    end = pd.Timestamp("2026-08-14T13:00:00Z")
    assert store_history_segment("XAUUSD", "M15", start, end, bars, db_path=db) == 1
    assert len(load_cached_bars("XAUUSD", "M15", start, end, db_path=db)) == 1
    assert missing_intervals("XAUUSD", "M15", start, end, db_path=db) == []

    assert ensure_history_time_basis(db_path=db) is True
    assert load_cached_bars("XAUUSD", "M15", start, end, db_path=db).empty
    assert missing_intervals("XAUUSD", "M15", start, end, db_path=db) == [(start, end)]

    # The reset marker makes the migration one-shot; newly rebuilt cache survives.
    assert store_history_segment("XAUUSD", "M15", start, end, bars, db_path=db) == 1
    assert ensure_history_time_basis(db_path=db) is False
    assert len(load_cached_bars("XAUUSD", "M15", start, end, db_path=db)) == 1
