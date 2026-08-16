from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .trade_journal import initialize_journal, journal_connection


CACHE_TIMEFRAMES = {"M1", "M5", "M15", "H1", "D1"}
BAR_COLUMNS = ["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]


def _utc(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _iso(value: Any) -> str:
    return _utc(value).isoformat()


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip()


def _normalize_timeframe(timeframe: str) -> str:
    tf = str(timeframe or "").upper()
    if tf not in CACHE_TIMEFRAMES:
        raise ValueError(f"Nicht unterstützter Cache-Timeframe: {tf}")
    return tf


def _merge_intervals(intervals: Iterable[tuple[pd.Timestamp, pd.Timestamp]]) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    rows = sorted(((_utc(a), _utc(b)) for a, b in intervals if _utc(b) > _utc(a)), key=lambda x: x[0])
    if not rows:
        return []
    merged: list[list[pd.Timestamp]] = [[rows[0][0], rows[0][1]]]
    for start, end in rows[1:]:
        current = merged[-1]
        if start <= current[1]:
            current[1] = max(current[1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def cached_coverage(
    symbol: str,
    timeframe: str,
    *,
    db_path: str | Path | None = None,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    path = initialize_journal(db_path)
    symbol = _normalize_symbol(symbol)
    timeframe = _normalize_timeframe(timeframe)
    with journal_connection(path) as con:
        rows = con.execute(
            """
            SELECT start_utc, end_utc
            FROM mt5_history_coverage
            WHERE symbol=? AND timeframe=?
            ORDER BY start_utc
            """,
            (symbol, timeframe),
        ).fetchall()
    return _merge_intervals([(_utc(row["start_utc"]), _utc(row["end_utc"])) for row in rows])


def missing_intervals(
    symbol: str,
    timeframe: str,
    start: Any,
    end: Any,
    *,
    db_path: str | Path | None = None,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    start_ts = _utc(start)
    end_ts = _utc(end)
    if end_ts <= start_ts:
        return []
    coverage = cached_coverage(symbol, timeframe, db_path=db_path)
    missing: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    cursor = start_ts
    for cov_start, cov_end in coverage:
        if cov_end <= cursor:
            continue
        if cov_start >= end_ts:
            break
        if cov_start > cursor:
            missing.append((cursor, min(cov_start, end_ts)))
        cursor = max(cursor, cov_end)
        if cursor >= end_ts:
            break
    if cursor < end_ts:
        missing.append((cursor, end_ts))
    return [(a, b) for a, b in missing if b > a]


def load_cached_bars(
    symbol: str,
    timeframe: str,
    start: Any,
    end: Any,
    *,
    db_path: str | Path | None = None,
) -> pd.DataFrame:
    path = initialize_journal(db_path)
    symbol = _normalize_symbol(symbol)
    timeframe = _normalize_timeframe(timeframe)
    start_ts = _utc(start)
    end_ts = _utc(end)
    if end_ts <= start_ts:
        return pd.DataFrame(columns=BAR_COLUMNS)
    with journal_connection(path) as con:
        df = pd.read_sql_query(
            """
            SELECT time_utc AS time, open, high, low, close, tick_volume, spread, real_volume
            FROM mt5_history_bars
            WHERE symbol=? AND timeframe=? AND time_utc>=? AND time_utc<?
            ORDER BY time_utc
            """,
            con,
            params=[symbol, timeframe, _iso(start_ts), _iso(end_ts)],
        )
    if df.empty:
        return pd.DataFrame(columns=BAR_COLUMNS)
    df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
    return df[BAR_COLUMNS]


def store_history_segment(
    symbol: str,
    timeframe: str,
    start: Any,
    end: Any,
    bars: pd.DataFrame,
    *,
    db_path: str | Path | None = None,
) -> int:
    """Persist one checked half-open interval [start, end), including empty ranges.

    Coverage is stored even when MT5 returned zero bars, so weekends/market closures
    are not requested again on every manual sync.
    """
    path = initialize_journal(db_path)
    symbol = _normalize_symbol(symbol)
    timeframe = _normalize_timeframe(timeframe)
    start_ts = _utc(start)
    end_ts = _utc(end)
    if end_ts <= start_ts:
        return 0

    frame = bars.copy() if bars is not None else pd.DataFrame()
    if not frame.empty:
        frame["time"] = pd.to_datetime(frame["time"], utc=True, errors="coerce")
        for col in ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]:
            if col not in frame.columns:
                frame[col] = pd.NA
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame = frame.dropna(subset=["time", "open", "high", "low", "close"])
        frame = frame[(frame["time"] >= start_ts) & (frame["time"] < end_ts)]
        frame = frame.sort_values("time").drop_duplicates(subset=["time"], keep="last")

    now_iso = datetime.now(timezone.utc).isoformat()
    with journal_connection(path) as con:
        if not frame.empty:
            rows = []
            for _, row in frame.iterrows():
                rows.append((
                    symbol, timeframe, _iso(row["time"]), float(row["open"]), float(row["high"]),
                    float(row["low"]), float(row["close"]),
                    None if pd.isna(row["tick_volume"]) else float(row["tick_volume"]),
                    None if pd.isna(row["spread"]) else float(row["spread"]),
                    None if pd.isna(row["real_volume"]) else float(row["real_volume"]),
                    now_iso,
                ))
            con.executemany(
                """
                INSERT INTO mt5_history_bars(
                    symbol,timeframe,time_utc,open,high,low,close,tick_volume,spread,real_volume,cached_at_utc
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(symbol,timeframe,time_utc) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
                    tick_volume=excluded.tick_volume, spread=excluded.spread,
                    real_volume=excluded.real_volume, cached_at_utc=excluded.cached_at_utc
                """,
                rows,
            )

        overlaps = con.execute(
            """
            SELECT coverage_id, start_utc, end_utc
            FROM mt5_history_coverage
            WHERE symbol=? AND timeframe=? AND end_utc>=? AND start_utc<=?
            """,
            (symbol, timeframe, _iso(start_ts), _iso(end_ts)),
        ).fetchall()
        merged_start = start_ts
        merged_end = end_ts
        ids: list[int] = []
        for row in overlaps:
            ids.append(int(row["coverage_id"]))
            merged_start = min(merged_start, _utc(row["start_utc"]))
            merged_end = max(merged_end, _utc(row["end_utc"]))
        if ids:
            con.execute(
                f"DELETE FROM mt5_history_coverage WHERE coverage_id IN ({','.join(['?'] * len(ids))})",
                ids,
            )
        con.execute(
            """
            INSERT INTO mt5_history_coverage(symbol,timeframe,start_utc,end_utc,synced_at_utc)
            VALUES(?,?,?,?,?)
            """,
            (symbol, timeframe, _iso(merged_start), _iso(merged_end), now_iso),
        )
    return int(len(frame))


def merge_missing_requests(
    intervals_by_key: dict[tuple[str, str], list[tuple[pd.Timestamp, pd.Timestamp]]]
) -> dict[tuple[str, str], list[tuple[pd.Timestamp, pd.Timestamp]]]:
    return {key: _merge_intervals(intervals) for key, intervals in intervals_by_key.items()}
