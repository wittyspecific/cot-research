from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .mt5_account import MT5Config
from .mt5_history import HistoryRequest, MT5HistoryError, history_batch
from .mt5_history_cache import load_cached_bars, merge_missing_requests, missing_intervals, store_history_segment
from .trade_journal import list_trade_plans, upsert_trade_outcome


TRACKER_VERSION = "1.2"
PRIMARY_TIMEFRAME = "H1"
RESOLUTION_TIMEFRAMES = ("M5", "M1")
FORWARD_DAYS = (1, 3, 5, 10, 20, 40, 60)

_TIMEFRAME_FREQ = {"M1": "min", "M5": "5min", "H1": "h", "D1": "D"}
_TIMEFRAME_DELTA = {
    "M1": pd.Timedelta(minutes=1),
    "M5": pd.Timedelta(minutes=5),
    "H1": pd.Timedelta(hours=1),
    "D1": pd.Timedelta(days=1),
}


def _utc(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _iso(value: Any | None) -> str | None:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return None
    return _utc(value).isoformat()


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _timeframe_freq(timeframe: str) -> str:
    tf = str(timeframe or "").upper()
    if tf not in _TIMEFRAME_FREQ:
        raise ValueError(f"Nicht unterstützter Outcome-Timeframe: {tf}")
    return _TIMEFRAME_FREQ[tf]


def _timeframe_delta(timeframe: str) -> pd.Timedelta:
    tf = str(timeframe or "").upper()
    if tf not in _TIMEFRAME_DELTA:
        raise ValueError(f"Nicht unterstützter Outcome-Timeframe: {tf}")
    return _TIMEFRAME_DELTA[tf]


def _prepare_bars(bars: pd.DataFrame, created_at: Any, timeframe: str) -> pd.DataFrame:
    if bars is None or bars.empty:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "_plan_start_partial"])
    out = bars.copy()
    out["time"] = pd.to_datetime(out["time"], utc=True, errors="coerce")
    for col in ["open", "high", "low", "close"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["time", "open", "high", "low", "close"]).sort_values("time")

    # Keep the bar that contains the save timestamp. If that partial bar touches a
    # decision level, OHLC alone cannot prove whether the touch happened before or
    # after the plan was saved; the caller must refine to a smaller timeframe.
    created = _utc(created_at)
    floor = created.floor(_timeframe_freq(timeframe))
    out = out[out["time"] >= floor].reset_index(drop=True)
    out["_plan_start_partial"] = False
    if not out.empty and created > floor:
        out.loc[out["time"] == floor, "_plan_start_partial"] = True
    return out


def _touches_entry(side: str, row: pd.Series, entry: float) -> bool:
    return float(row["low"]) <= entry if side == "LONG" else float(row["high"]) >= entry


def _touches_stop(side: str, row: pd.Series, stop: float) -> bool:
    return float(row["low"]) <= stop if side == "LONG" else float(row["high"]) >= stop


def _touches_target(side: str, row: pd.Series, target: float | None) -> bool:
    if target is None:
        return False
    return float(row["high"]) >= target if side == "LONG" else float(row["low"]) <= target


def _bar_r_extremes(side: str, row: pd.Series, entry: float, risk: float) -> tuple[float, float]:
    if side == "LONG":
        favorable = (float(row["high"]) - entry) / risk
        adverse = (float(row["low"]) - entry) / risk
    else:
        favorable = (entry - float(row["low"])) / risk
        adverse = (entry - float(row["high"])) / risk
    return favorable, adverse


def evaluate_trade_path(plan: Mapping[str, Any], bars: pd.DataFrame, *, timeframe: str = PRIMARY_TIMEFRAME, now: Any | None = None) -> dict[str, Any]:
    """Chronologically evaluate one immutable plan against OHLC bars.

    If entry and exit, or stop and target, occur inside the same bar, the result is
    AMBIGUOUS so the caller can rerun the whole path with a finer timeframe.
    """
    side = str(plan.get("side", "")).upper()
    order_type = str(plan.get("order_type", "LIMIT") or "LIMIT").upper()
    entry = float(plan["entry"])
    stop = float(plan["stop"])
    target = _finite(plan.get("target"))
    risk = abs(entry - stop)
    if risk <= 0:
        raise ValueError("Entry und Stop müssen verschieden sein.")
    created = _utc(plan["created_at_utc"])
    expiry_raw = plan.get("expiry_at_utc")
    expiry = _utc(expiry_raw) if expiry_raw not in (None, "") and not pd.isna(expiry_raw) else None
    now_ts = _utc(now or datetime.now(timezone.utc))
    data = _prepare_bars(bars, created, timeframe)

    base = {
        "tracker_version": TRACKER_VERSION,
        "lifecycle_status": "PLANNED",
        "entry_triggered": 0,
        "entry_time_utc": None,
        "stop_time_utc": None,
        "target_time_utc": None,
        "exit_time_utc": None,
        "first_exit": None,
        "result_r": None,
        "mae_r": None,
        "mfe_r": None,
        "holding_minutes": None,
        "ambiguity_reason": None,
        "ambiguous_bar_time_utc": None,
        "data_timeframe": timeframe,
        "last_bar_time_utc": _iso(data.iloc[-1]["time"]) if not data.empty else None,
        "plus_1r_time_utc": None,
        "plus_2r_time_utc": None,
        "plus_3r_time_utc": None,
    }

    if data.empty:
        if expiry is not None and now_ts >= expiry:
            base["lifecycle_status"] = "EXPIRED"
        return base

    first_partial = bool(data.iloc[0].get("_plan_start_partial", False))
    bar_delta = _timeframe_delta(timeframe)

    if order_type == "MARKET":
        entry_idx = 0
        entry_time = created
        if first_partial and timeframe != "M1":
            base.update({
                "lifecycle_status": "AMBIGUOUS",
                "ambiguity_reason": "MARKET_ENTRY_IN_PARTIAL_START_BAR",
                "ambiguous_bar_time_utc": _iso(data.iloc[0]["time"]),
                "entry_triggered": 1,
                "entry_time_utc": _iso(created),
            })
            return base
        if first_partial and timeframe == "M1":
            first = data.iloc[0]
            if _touches_stop(side, first, stop) or _touches_target(side, first, target):
                base.update({
                    "lifecycle_status": "AMBIGUOUS",
                    "ambiguity_reason": "MARKET_EXIT_IN_PARTIAL_M1_BAR",
                    "ambiguous_bar_time_utc": _iso(first["time"]),
                    "entry_triggered": 1,
                    "entry_time_utc": _iso(created),
                })
                return base
    else:
        entry_idx = None
        entry_time = None
        for idx, row in data.iterrows():
            bar_time = _utc(row["time"])
            if expiry is not None and bar_time > expiry:
                break
            if not _touches_entry(side, row, entry):
                continue

            # The first bar can contain price action from before plan creation.
            if bool(row.get("_plan_start_partial", False)):
                base.update({
                    "lifecycle_status": "AMBIGUOUS",
                    "ambiguity_reason": "ENTRY_TOUCH_IN_PARTIAL_START_BAR",
                    "ambiguous_bar_time_utc": _iso(bar_time),
                })
                return base

            # A bar that straddles the expiry can contain an entry touch after the
            # order should already have expired. Refine instead of assuming.
            if expiry is not None and bar_time <= expiry < (bar_time + bar_delta):
                base.update({
                    "lifecycle_status": "AMBIGUOUS",
                    "ambiguity_reason": "ENTRY_TOUCH_IN_EXPIRY_BAR",
                    "ambiguous_bar_time_utc": _iso(bar_time),
                })
                return base

            entry_idx = int(idx)
            entry_time = bar_time
            # OHLC cannot prove that an exit touched in the same bar happened after the limit entry.
            if _touches_stop(side, row, stop) or _touches_target(side, row, target):
                base.update({
                    "lifecycle_status": "AMBIGUOUS",
                    "ambiguity_reason": "ENTRY_AND_EXIT_SAME_BAR",
                    "ambiguous_bar_time_utc": _iso(bar_time),
                    "entry_triggered": 1,
                    "entry_time_utc": _iso(bar_time),
                })
                return base
            break
        if entry_idx is None:
            if expiry is not None and now_ts >= expiry:
                base["lifecycle_status"] = "EXPIRED"
            return base

    base.update({
        "lifecycle_status": "ACTIVE",
        "entry_triggered": 1,
        "entry_time_utc": _iso(entry_time),
        "mfe_r": 0.0,
        "mae_r": 0.0,
    })

    mfe = 0.0
    mae = 0.0
    exit_time = None
    stop_time = None
    target_time = None
    first_exit = None
    result_r = None
    milestone_times: dict[int, str | None] = {1: None, 2: None, 3: None}

    # For a LIMIT order, the entry bar contains price action from before the fill.
    # If no exit threshold was touched there, skip its extrema rather than polluting
    # MAE/MFE with pre-entry movement. Same-bar exits were already marked ambiguous.
    loop_start = int(entry_idx) + (1 if order_type == "LIMIT" else (1 if first_partial else 0))
    for idx in range(loop_start, len(data)):
        row = data.iloc[idx]
        bar_time = _utc(row["time"])
        stop_hit = _touches_stop(side, row, stop)
        target_hit = _touches_target(side, row, target)
        if stop_hit and target_hit:
            base.update({
                "lifecycle_status": "AMBIGUOUS",
                "ambiguity_reason": "STOP_AND_TARGET_SAME_BAR",
                "ambiguous_bar_time_utc": _iso(bar_time),
                "mfe_r": float(mfe),
                "mae_r": float(mae),
            })
            return base

        favorable, adverse = _bar_r_extremes(side, row, entry, risk)
        mfe = max(mfe, favorable)
        mae = min(mae, adverse)
        for level in (1, 2, 3):
            if milestone_times[level] is None and favorable >= level:
                milestone_times[level] = _iso(bar_time)

        if stop_hit:
            exit_time = bar_time
            stop_time = bar_time
            first_exit = "STOP"
            result_r = -1.0
            break
        if target_hit:
            exit_time = bar_time
            target_time = bar_time
            first_exit = "TARGET"
            result_r = ((target - entry) / risk) if side == "LONG" else ((entry - target) / risk)
            break

    base.update({
        "mfe_r": float(mfe),
        "mae_r": float(mae),
        "plus_1r_time_utc": milestone_times[1],
        "plus_2r_time_utc": milestone_times[2],
        "plus_3r_time_utc": milestone_times[3],
    })
    if exit_time is not None:
        base.update({
            "lifecycle_status": "CLOSED",
            "exit_time_utc": _iso(exit_time),
            "stop_time_utc": _iso(stop_time),
            "target_time_utc": _iso(target_time),
            "first_exit": first_exit,
            "result_r": float(result_r),
            "holding_minutes": max(0.0, (exit_time - _utc(entry_time)).total_seconds() / 60.0),
        })
    else:
        base["holding_minutes"] = max(0.0, (now_ts - _utc(entry_time)).total_seconds() / 60.0)
    return base


def add_forward_returns(outcome: dict[str, Any], plan: Mapping[str, Any], daily_bars: pd.DataFrame) -> dict[str, Any]:
    result = dict(outcome)
    if not result.get("entry_triggered") or not result.get("entry_time_utc") or daily_bars is None or daily_bars.empty:
        return result
    entry = float(plan["entry"])
    side = str(plan["side"]).upper()
    bars = daily_bars.copy()
    bars["time"] = pd.to_datetime(bars["time"], utc=True, errors="coerce")
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")
    bars = bars.dropna(subset=["time", "close"]).sort_values("time")
    entry_date = _utc(result["entry_time_utc"]).date()
    after = bars[bars["time"].dt.date > entry_date].reset_index(drop=True)
    for days in FORWARD_DAYS:
        value = None
        if len(after) >= days:
            close = float(after.iloc[days - 1]["close"])
            raw = close / entry - 1.0
            value = raw if side == "LONG" else -raw
        result[f"forward_{days}d"] = value
    return result




def _blank_cache_stats() -> dict[str, Any]:
    return {
        "remote_requests": 0,
        "cache_only_requests": 0,
        "bars_loaded": 0,
        "bars_loaded_by_timeframe": {},
        "remote_requests_by_timeframe": {},
        "remote_symbols": set(),
    }


def _merge_cache_stats(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    target["remote_requests"] += int(source.get("remote_requests", 0) or 0)
    target["cache_only_requests"] += int(source.get("cache_only_requests", 0) or 0)
    target["bars_loaded"] += int(source.get("bars_loaded", 0) or 0)
    target["remote_symbols"].update(source.get("remote_symbols", set()) or set())
    for field in ("bars_loaded_by_timeframe", "remote_requests_by_timeframe"):
        for key, value in dict(source.get(field, {}) or {}).items():
            target[field][key] = target[field].get(key, 0) + int(value or 0)


def _cached_history_batch(
    config: MT5Config,
    requests: list[HistoryRequest],
    *,
    db_path: str | Path | None,
    timeout_seconds: float,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Return requested bars while querying MT5 only for uncovered local ranges.

    The persistent cache uses half-open coverage ranges [start, end). Empty market
    intervals are cached as coverage as well, preventing repeated weekend requests.
    When no db_path is supplied (mostly low-level tests), behavior stays compatible
    with the pre-cache tracker and delegates directly to MT5.
    """
    normalized = [request.normalized() for request in requests]
    stats = _blank_cache_stats()
    if not normalized:
        return {}, stats
    if db_path is None:
        remote = history_batch(config, normalized, timeout_seconds=timeout_seconds)
        stats["remote_requests"] = len(normalized)
        stats["cache_only_requests"] = 0
        for req in normalized:
            frame = remote.get(req.request_id, pd.DataFrame())
            count = int(len(frame))
            stats["bars_loaded"] += count
            stats["bars_loaded_by_timeframe"][req.timeframe] = stats["bars_loaded_by_timeframe"].get(req.timeframe, 0) + count
            stats["remote_requests_by_timeframe"][req.timeframe] = stats["remote_requests_by_timeframe"].get(req.timeframe, 0) + 1
            stats["remote_symbols"].add(req.symbol)
        return remote, stats

    missing_by_key: dict[tuple[str, str], list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    request_missing: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    for req in normalized:
        gaps = missing_intervals(req.symbol, req.timeframe, req.start_utc, req.end_utc, db_path=db_path)
        request_missing[req.request_id] = gaps
        if not gaps:
            stats["cache_only_requests"] += 1
        else:
            missing_by_key.setdefault((req.symbol, req.timeframe), []).extend(gaps)

    merged = merge_missing_requests(missing_by_key)
    fetch_requests: list[HistoryRequest] = []
    fetch_meta: dict[str, tuple[str, str, pd.Timestamp, pd.Timestamp]] = {}
    sequence = 0
    for (symbol, timeframe), intervals in merged.items():
        for start, end in intervals:
            sequence += 1
            rid = f"cache_{timeframe.lower()}_{sequence:04d}"
            fetch_requests.append(HistoryRequest(symbol, start, end, timeframe, rid))
            fetch_meta[rid] = (symbol, timeframe, start, end)

    if fetch_requests:
        remote = history_batch(config, fetch_requests, timeout_seconds=timeout_seconds)
        stats["remote_requests"] = len(fetch_requests)
        for req in fetch_requests:
            symbol, timeframe, start, end = fetch_meta[req.request_id]
            frame = remote.get(req.request_id, pd.DataFrame())
            loaded = store_history_segment(symbol, timeframe, start, end, frame, db_path=db_path)
            stats["bars_loaded"] += loaded
            stats["bars_loaded_by_timeframe"][timeframe] = stats["bars_loaded_by_timeframe"].get(timeframe, 0) + loaded
            stats["remote_requests_by_timeframe"][timeframe] = stats["remote_requests_by_timeframe"].get(timeframe, 0) + 1
            stats["remote_symbols"].add(symbol)

    results: dict[str, pd.DataFrame] = {}
    for req in normalized:
        results[req.request_id] = load_cached_bars(
            req.symbol, req.timeframe, req.start_utc, req.end_utc, db_path=db_path
        )
    return results, stats


def _completed_boundary(value: Any, timeframe: str) -> pd.Timestamp:
    """Half-open end boundary that excludes the still-forming current bar."""
    ts = _utc(value)
    return ts.floor(_timeframe_freq(timeframe))


def _history_window(
    plan: Mapping[str, Any],
    now: pd.Timestamp,
    timeframe: str,
    *,
    force_full: bool = False,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    freq = _timeframe_freq(timeframe)
    delta = _timeframe_delta(timeframe)
    start = _utc(plan["created_at_utc"]).floor(freq)
    expiry_raw = plan.get("expiry_at_utc")
    expiry = _utc(expiry_raw) if expiry_raw not in (None, "") and not pd.isna(expiry_raw) else None
    # For a previously untriggered LIMIT plan we normally only need one bar beyond
    # expiry. A finer fallback is always requested through `now`, because the coarse
    # ambiguous bar may in fact contain a valid entry before expiry and the trade can
    # still be active afterwards.
    end = now
    triggered_raw = plan.get("entry_triggered")
    was_triggered = False if triggered_raw is None or pd.isna(triggered_raw) else bool(triggered_raw)
    if expiry is not None and not was_triggered and not force_full:
        end = min(now, expiry + delta)
    return start, max(start + delta, end)


def sync_trade_outcomes(
    config: MT5Config,
    *,
    db_path: str | Path | None = None,
    max_trades: int = 250,
    timeout_seconds: float = 12.0,
    now: Any | None = None,
    trader_id: str | None = None,
) -> dict[str, Any]:
    """Catch up journal outcomes from MT5 history. No order/trade operation is used."""
    now_ts = _utc(now or datetime.now(timezone.utc))
    plans = list_trade_plans(
        db_path=db_path, limit=max_trades, trader_id=trader_id,
        lifecycle_statuses=("PLANNED", "ACTIVE"),
    )
    if plans.empty:
        return {
            "checked": 0, "updated": 0, "ambiguous": 0, "errors": [],
            "symbols_checked": 0, "remote_requests": 0, "cache_only_requests": 0,
            "bars_loaded": 0, "bars_loaded_by_timeframe": {},
            "remote_requests_by_timeframe": {},
        }

    requests: list[HistoryRequest] = []
    request_to_trade: dict[str, str] = {}
    plan_by_trade: dict[str, dict[str, Any]] = {}
    no_completed_bar_trades: list[str] = []
    completed_h1_end = _completed_boundary(now_ts, PRIMARY_TIMEFRAME)
    for _, row in plans.iterrows():
        plan = row.to_dict()
        trade_id = str(plan["trade_id"])
        plan_by_trade[trade_id] = plan
        start, end = _history_window(plan, now_ts, PRIMARY_TIMEFRAME)
        end = min(end, completed_h1_end)
        if end <= start:
            no_completed_bar_trades.append(trade_id)
            continue
        request_id = f"h1_{trade_id.replace('-', '')[:20]}"
        requests.append(HistoryRequest(str(plan["cfd_symbol"]), start, end, PRIMARY_TIMEFRAME, request_id))
        request_to_trade[request_id] = trade_id

    cache_stats = _blank_cache_stats()
    primary, primary_stats = _cached_history_batch(
        config, requests, db_path=db_path, timeout_seconds=timeout_seconds
    )
    _merge_cache_stats(cache_stats, primary_stats)
    outcomes: dict[str, dict[str, Any]] = {}
    for trade_id in no_completed_bar_trades:
        outcomes[trade_id] = evaluate_trade_path(
            plan_by_trade[trade_id], pd.DataFrame(), timeframe=PRIMARY_TIMEFRAME, now=now_ts
        )
    for request_id, trade_id in request_to_trade.items():
        plan = plan_by_trade[trade_id]
        outcomes[trade_id] = evaluate_trade_path(
            plan, primary.get(request_id, pd.DataFrame()), timeframe=PRIMARY_TIMEFRAME, now=now_ts
        )

    # Only ambiguous paths are requested again. H1 is the normal Swing timeframe;
    # M5 and then M1 are technical resolution layers, never the default data feed.
    for resolution_tf in RESOLUTION_TIMEFRAMES:
        unresolved = [
            trade_id for trade_id, outcome in outcomes.items()
            if outcome.get("lifecycle_status") == "AMBIGUOUS"
        ]
        if not unresolved:
            break
        resolution_requests: list[HistoryRequest] = []
        resolution_to_trade: dict[str, str] = {}
        for trade_id in unresolved:
            plan = plan_by_trade[trade_id]
            start, end = _history_window(plan, now_ts, resolution_tf, force_full=True)
            end = min(end, _completed_boundary(now_ts, resolution_tf))
            if end <= start:
                continue
            rid = f"{resolution_tf.lower()}_{trade_id.replace('-', '')[:20]}"
            resolution_requests.append(
                HistoryRequest(str(plan["cfd_symbol"]), start, end, resolution_tf, rid)
            )
            resolution_to_trade[rid] = trade_id
        resolved, resolution_stats = _cached_history_batch(
            config, resolution_requests, db_path=db_path, timeout_seconds=timeout_seconds
        )
        _merge_cache_stats(cache_stats, resolution_stats)
        for request_id, trade_id in resolution_to_trade.items():
            plan = plan_by_trade[trade_id]
            outcomes[trade_id] = evaluate_trade_path(
                plan, resolved.get(request_id, pd.DataFrame()), timeframe=resolution_tf, now=now_ts
            )

    daily_requests: list[HistoryRequest] = []
    daily_to_trade: dict[str, str] = {}
    for trade_id, outcome in outcomes.items():
        if not outcome.get("entry_triggered") or not outcome.get("entry_time_utc"):
            continue
        start = _utc(outcome["entry_time_utc"]).floor("D") - pd.Timedelta(days=1)
        end = _completed_boundary(now_ts, "D1")
        if end <= start:
            continue
        rid = f"d1_{trade_id.replace('-', '')[:20]}"
        daily_requests.append(HistoryRequest(str(plan_by_trade[trade_id]["cfd_symbol"]), start, end, "D1", rid))
        daily_to_trade[rid] = trade_id
    if daily_requests:
        daily, daily_stats = _cached_history_batch(
            config, daily_requests, db_path=db_path, timeout_seconds=timeout_seconds
        )
        _merge_cache_stats(cache_stats, daily_stats)
        for request_id, trade_id in daily_to_trade.items():
            outcomes[trade_id] = add_forward_returns(outcomes[trade_id], plan_by_trade[trade_id], daily.get(request_id, pd.DataFrame()))

    updated = 0
    ambiguous = 0
    status_counts: dict[str, int] = {}
    for trade_id, outcome in outcomes.items():
        status = str(outcome.get("lifecycle_status", "PLANNED"))
        status_counts[status] = status_counts.get(status, 0) + 1
        ambiguous += int(status == "AMBIGUOUS")
        upsert_trade_outcome(trade_id, outcome, db_path=db_path)
        updated += 1

    return {
        "checked": len(plans),
        "updated": updated,
        "ambiguous": ambiguous,
        "status_counts": status_counts,
        "errors": [],
        "symbols_checked": len({str(value) for value in plans["cfd_symbol"].dropna().tolist()}),
        "remote_requests": int(cache_stats["remote_requests"]),
        "cache_only_requests": int(cache_stats["cache_only_requests"]),
        "bars_loaded": int(cache_stats["bars_loaded"]),
        "bars_loaded_by_timeframe": dict(cache_stats["bars_loaded_by_timeframe"]),
        "remote_requests_by_timeframe": dict(cache_stats["remote_requests_by_timeframe"]),
        "remote_symbols": sorted(cache_stats["remote_symbols"]),
    }
