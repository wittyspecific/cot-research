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
from .mt5_history_cache import ensure_history_time_basis, load_cached_bars, merge_missing_requests, missing_intervals, store_history_segment
from .price_units import plan_to_mt5_units
from .trade_journal import get_trade_outcome, list_trade_plans, upsert_trade_outcome


TRACKER_VERSION = "1.3"
PRIMARY_TIMEFRAME = "H1"
MARKET_FILL_TIMEFRAMES = ("M1",)
MARKET_FILL_SUPPORTED = {"M15", "M5", "M1"}
RESOLUTION_TIMEFRAMES = ("M5", "M1")
FORWARD_DAYS = (1, 3, 5, 10, 20, 40, 60)

_TIMEFRAME_FREQ = {"M1": "min", "M5": "5min", "M15": "15min", "H1": "h", "D1": "D"}
_TIMEFRAME_DELTA = {
    "M1": pd.Timedelta(minutes=1),
    "M5": pd.Timedelta(minutes=5),
    "M15": pd.Timedelta(minutes=15),
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


def resolve_market_fill(
    plan: Mapping[str, Any],
    bars: pd.DataFrame,
    *,
    timeframe: str = "M15",
    now: Any | None = None,
) -> dict[str, Any]:
    """Resolve a simulated MARKET fill from completed MT5 bars.

    M15 is the normal fill layer. If the plan timestamp lies inside that bar, the
    result is AMBIGUOUS so the caller can refine to M5 and then M1. At M1 we use
    the first *full* minute beginning after the save timestamp when the save happened
    mid-minute. For a closed-market gap, the first future bar open is the fill.
    """
    tf = str(timeframe or "M15").upper()
    if tf not in MARKET_FILL_SUPPORTED:
        raise ValueError(f"Nicht unterstützter MARKET-Fill-Timeframe: {tf}")
    if str(plan.get("order_type", "LIMIT") or "LIMIT").upper() != "MARKET":
        raise ValueError("resolve_market_fill ist nur für MARKET-Pläne gedacht.")

    plan = plan_to_mt5_units(plan)
    created = _utc(plan["created_at_utc"])
    now_ts = _utc(now or datetime.now(timezone.utc))
    data = _prepare_bars(bars, created, tf)
    base = {
        "tracker_version": TRACKER_VERSION,
        "lifecycle_status": "PLANNED",
        "entry_triggered": 0,
        "entry_time_utc": None,
        "execution_price": None,
        "fill_timeframe": None,
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
        "data_timeframe": tf,
        "last_bar_time_utc": _iso(data.iloc[-1]["time"]) if not data.empty else None,
        "plus_1r_time_utc": None,
        "plus_2r_time_utc": None,
        "plus_3r_time_utc": None,
    }
    if data.empty:
        return base

    first = data.iloc[0]
    first_time = _utc(first["time"])
    if first_time < created:
        if tf != "M1":
            base.update({
                "lifecycle_status": "AMBIGUOUS",
                "ambiguity_reason": f"MARKET_FILL_IN_PARTIAL_{tf}_BAR",
                "ambiguous_bar_time_utc": _iso(first_time),
            })
            return base
        # A plan saved at e.g. 23:17:42 cannot safely use the 23:17 M1 open.
        # Use the next complete minute open instead; maximum timing error < 60 sec.
        next_full = created.ceil("min")
        candidates = data[data["time"] >= next_full]
        if candidates.empty:
            return base
        first = candidates.iloc[0]
        first_time = _utc(first["time"])

    execution = float(first["open"])
    stop = float(plan["stop"])
    target = _finite(plan.get("target"))
    side = str(plan.get("side", "")).upper()
    if (side == "LONG" and execution <= stop) or (side == "SHORT" and execution >= stop):
        base.update({
            "lifecycle_status": "AMBIGUOUS",
            "ambiguity_reason": "MARKET_FILL_INVALIDATES_STOP",
            "ambiguous_bar_time_utc": _iso(first_time),
            "execution_price": execution,
            "fill_timeframe": tf,
        })
        return base
    if target is not None and ((side == "LONG" and execution >= target) or (side == "SHORT" and execution <= target)):
        base.update({
            "lifecycle_status": "AMBIGUOUS",
            "ambiguity_reason": "MARKET_FILL_BEYOND_TARGET",
            "ambiguous_bar_time_utc": _iso(first_time),
            "execution_price": execution,
            "fill_timeframe": tf,
        })
        return base

    base.update({
        "lifecycle_status": "ACTIVE",
        "entry_triggered": 1,
        "entry_time_utc": _iso(first_time),
        "execution_price": execution,
        "fill_timeframe": tf,
        "mae_r": 0.0,
        "mfe_r": 0.0,
        "holding_minutes": max(0.0, (now_ts - first_time).total_seconds() / 60.0),
    })
    return base


def _effective_resolved_entry_plan(plan: Mapping[str, Any], fill: Mapping[str, Any]) -> dict[str, Any]:
    """Replay exits from an already-resolved live/history entry without re-triggering it."""
    effective = plan_to_mt5_units(plan)
    effective["entry"] = float(fill["execution_price"])
    effective["created_at_utc"] = str(fill["entry_time_utc"])
    effective["_resolved_entry_fill"] = True
    effective["_entry_fill_source"] = str(fill.get("fill_timeframe") or "")
    if str(plan.get("order_type", "LIMIT") or "LIMIT").upper() == "MARKET":
        effective["_resolved_market_fill"] = True
        effective["_market_fill_timeframe"] = str(fill.get("fill_timeframe") or "")
    return effective


def _effective_market_plan(plan: Mapping[str, Any], fill: Mapping[str, Any]) -> dict[str, Any]:
    return _effective_resolved_entry_plan(plan, fill)


def evaluate_trade_path(plan: Mapping[str, Any], bars: pd.DataFrame, *, timeframe: str = PRIMARY_TIMEFRAME, now: Any | None = None) -> dict[str, Any]:
    """Chronologically evaluate one immutable plan against OHLC bars.

    If entry and exit, or stop and target, occur inside the same bar, the result is
    AMBIGUOUS so the caller can rerun the whole path with a finer timeframe.
    """
    plan = plan_to_mt5_units(plan)
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
        "execution_price": None,
        "fill_timeframe": None,
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

    resolved_fill = bool(plan.get("_resolved_entry_fill", False) or plan.get("_resolved_market_fill", False))
    resolved_source = str(plan.get("_entry_fill_source") or plan.get("_market_fill_timeframe") or "") or None

    if data.empty:
        if resolved_fill:
            base.update({
                "lifecycle_status": "ACTIVE",
                "entry_triggered": 1,
                "entry_time_utc": _iso(created),
                "execution_price": entry,
                "fill_timeframe": resolved_source,
                # With no new completed bar there is no new excursion information.
                # Preserve already accumulated values instead of silently resetting them.
                "mae_r": _finite(plan.get("mae_r")) if _finite(plan.get("mae_r")) is not None else 0.0,
                "mfe_r": _finite(plan.get("mfe_r")) if _finite(plan.get("mfe_r")) is not None else 0.0,
                "holding_minutes": max(
                    _finite(plan.get("holding_minutes")) or 0.0,
                    max(0.0, (now_ts - created).total_seconds() / 60.0),
                ),
            })
        elif expiry is not None and now_ts >= expiry:
            base["lifecycle_status"] = "EXPIRED"
        return base

    first_partial = bool(data.iloc[0].get("_plan_start_partial", False))
    bar_delta = _timeframe_delta(timeframe)

    if resolved_fill:
        entry_idx = 0
        entry_time = created
        base["execution_price"] = entry
        base["fill_timeframe"] = resolved_source
        # A coarse bar containing an already-resolved live/history fill can also
        # contain pre-fill price action. Refine only when an exit level is touched.
        if first_partial:
            first = data.iloc[0]
            if _touches_stop(side, first, stop) or _touches_target(side, first, target):
                base.update({
                    "lifecycle_status": "AMBIGUOUS",
                    "ambiguity_reason": "RESOLVED_ENTRY_EXIT_IN_PARTIAL_START_BAR",
                    "ambiguous_bar_time_utc": _iso(first["time"]),
                    "entry_triggered": 1,
                    "entry_time_utc": _iso(created),
                })
                return base
    elif order_type == "MARKET":
        entry_idx = 0
        entry_time = created
        if not resolved_fill:
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
            base["execution_price"] = entry
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
            base["execution_price"] = entry
            base["fill_timeframe"] = timeframe
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
    if resolved_fill:
        loop_start = int(entry_idx) + (1 if first_partial else 0)
    elif order_type == "LIMIT":
        loop_start = int(entry_idx) + 1
    else:
        loop_start = int(entry_idx) + (1 if first_partial else 0)
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
    plan = plan_to_mt5_units(plan)
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


def _guard_active_state_regression(
    trade_id: str,
    previous_status: Any,
    candidate: Mapping[str, Any],
    *,
    db_path: str | Path | None = None,
) -> tuple[dict[str, Any], bool]:
    """Never let missing/incomplete history demote a confirmed ACTIVE trade.

    Outcome sync is a reconstruction pass. A temporary lack of completed bars must
    not erase a previously confirmed fill. ACTIVE may progress to CLOSED or to an
    explicit AMBIGUOUS result, but it may never regress to PLANNED/EXPIRED.
    """
    old = str(previous_status or "PLANNED").upper()
    new = str(candidate.get("lifecycle_status", "PLANNED") or "PLANNED").upper()
    if old != "ACTIVE" or new not in {"PLANNED", "EXPIRED"}:
        return dict(candidate), False

    previous = get_trade_outcome(trade_id, db_path=db_path)
    payload = previous.get("payload") if isinstance(previous, Mapping) else None
    preserved: dict[str, Any] = dict(payload) if isinstance(payload, Mapping) else {}
    if isinstance(previous, Mapping):
        for key, value in previous.items():
            if key in {"payload", "payload_json", "trade_id", "last_evaluated_at_utc"}:
                continue
            if value is not None and not (isinstance(value, float) and pd.isna(value)):
                preserved[key] = value

    preserved.setdefault("execution_price", candidate.get("execution_price"))
    preserved.setdefault("entry_time_utc", candidate.get("entry_time_utc"))
    preserved.setdefault("fill_timeframe", candidate.get("fill_timeframe"))
    preserved["tracker_version"] = TRACKER_VERSION
    preserved["lifecycle_status"] = "ACTIVE"
    preserved["entry_triggered"] = 1
    preserved["state_guard_reason"] = f"BLOCKED_ACTIVE_TO_{new}"
    return preserved, True


def sync_trade_outcomes(
    config: MT5Config,
    *,
    db_path: str | Path | None = None,
    max_trades: int = 250,
    timeout_seconds: float = 12.0,
    now: Any | None = None,
    trader_id: str | None = None,
) -> dict[str, Any]:
    """Catch up journal outcomes from MT5 history. No order/trade operation is used.

    LIMIT plans use H1 as the primary Swing timeframe. MARKET plans are normally
    filled by the local live-tick watcher; if that watcher was offline, the history
    safety net resolves the first executable fill with M1 before rejoining H1.
    """
    now_ts = _utc(now or datetime.now(timezone.utc))
    cache_time_basis_reset = False
    if db_path is not None and str(config.mode or "").lower() == "bridge":
        cache_time_basis_reset = ensure_history_time_basis(db_path=db_path)
    plans = list_trade_plans(
        db_path=db_path, limit=max_trades, trader_id=trader_id,
        lifecycle_statuses=("PLANNED", "ACTIVE"),
    )
    if plans.empty:
        return {
            "checked": 0, "updated": 0, "ambiguous": 0, "errors": [],
            "symbols_checked": 0, "remote_requests": 0, "cache_only_requests": 0,
            "bars_loaded": 0, "bars_loaded_by_timeframe": {},
            "cache_time_basis_reset": cache_time_basis_reset,
            "remote_requests_by_timeframe": {},
        }

    cache_stats = _blank_cache_stats()
    plan_by_trade: dict[str, dict[str, Any]] = {}
    effective_plan_by_trade: dict[str, dict[str, Any]] = {}
    outcomes: dict[str, dict[str, Any]] = {}
    market_pending: set[str] = set()

    for _, row in plans.iterrows():
        plan = row.to_dict()
        trade_id = str(plan["trade_id"])
        plan_by_trade[trade_id] = plan
        order_type = str(plan.get("order_type", "LIMIT") or "LIMIT").upper()
        execution = _finite(plan.get("execution_price"))
        entry_time = plan.get("entry_time_utc")
        triggered_raw = plan.get("entry_triggered")
        triggered = False if triggered_raw is None or pd.isna(triggered_raw) else bool(triggered_raw)
        if triggered and execution is not None and entry_time not in (None, "") and not pd.isna(entry_time):
            fill = {
                "execution_price": execution,
                "entry_time_utc": str(entry_time),
                "fill_timeframe": str(plan.get("fill_timeframe") or ("M15" if order_type == "MARKET" else PRIMARY_TIMEFRAME)),
            }
            effective_plan_by_trade[trade_id] = _effective_resolved_entry_plan(plan, fill)
        elif order_type == "MARKET":
            market_pending.add(trade_id)
        else:
            effective_plan_by_trade[trade_id] = plan

    # MARKET history safety net: direct M1. The normal real-time path is LIVE_TICK;
    # M1 is used only if the watcher was offline or missed the entry.
    for fill_tf in MARKET_FILL_TIMEFRAMES:
        unresolved = sorted(market_pending)
        if not unresolved:
            break
        fill_requests: list[HistoryRequest] = []
        request_to_trade: dict[str, str] = {}
        no_completed: set[str] = set()
        completed_end = _completed_boundary(now_ts, fill_tf)
        for trade_id in unresolved:
            plan = plan_by_trade[trade_id]
            start = _utc(plan["created_at_utc"]).floor(_timeframe_freq(fill_tf))
            end = completed_end
            if end <= start:
                no_completed.add(trade_id)
                continue
            rid = f"fill_{fill_tf.lower()}_{trade_id.replace('-', '')[:16]}"
            fill_requests.append(HistoryRequest(str(plan["cfd_symbol"]), start, end, fill_tf, rid))
            request_to_trade[rid] = trade_id

        fetched, stats = _cached_history_batch(
            config, fill_requests, db_path=db_path, timeout_seconds=timeout_seconds
        )
        _merge_cache_stats(cache_stats, stats)

        next_pending: set[str] = set()
        for trade_id in unresolved:
            if trade_id in no_completed:
                outcomes[trade_id] = resolve_market_fill(
                    plan_by_trade[trade_id], pd.DataFrame(), timeframe=fill_tf, now=now_ts
                )
                # Wait for the first completed M1 bar after the plan timestamp.
                continue
            rid = next((key for key, value in request_to_trade.items() if value == trade_id), None)
            fill = resolve_market_fill(
                plan_by_trade[trade_id], fetched.get(rid, pd.DataFrame()) if rid else pd.DataFrame(),
                timeframe=fill_tf, now=now_ts,
            )
            outcomes[trade_id] = fill
            if fill.get("lifecycle_status") == "ACTIVE":
                effective_plan_by_trade[trade_id] = _effective_market_plan(plan_by_trade[trade_id], fill)
            elif fill.get("lifecycle_status") == "AMBIGUOUS" and fill_tf != "M1" and str(fill.get("ambiguity_reason", "")).startswith("MARKET_FILL_IN_PARTIAL_"):
                next_pending.add(trade_id)
        market_pending = next_pending

    # H1 is the normal path for LIMIT plans and for MARKET plans after their fill
    # has been resolved. If no full H1 exists yet after a MARKET fill, keep ACTIVE.
    requests: list[HistoryRequest] = []
    request_to_trade: dict[str, str] = {}
    no_completed_h1: set[str] = set()
    completed_h1_end = _completed_boundary(now_ts, PRIMARY_TIMEFRAME)
    for trade_id, plan in effective_plan_by_trade.items():
        start, end = _history_window(plan, now_ts, PRIMARY_TIMEFRAME)
        end = min(end, completed_h1_end)
        if end <= start:
            no_completed_h1.add(trade_id)
            continue
        request_id = f"h1_{trade_id.replace('-', '')[:20]}"
        requests.append(HistoryRequest(str(plan["cfd_symbol"]), start, end, PRIMARY_TIMEFRAME, request_id))
        request_to_trade[request_id] = trade_id

    primary, primary_stats = _cached_history_batch(
        config, requests, db_path=db_path, timeout_seconds=timeout_seconds
    )
    _merge_cache_stats(cache_stats, primary_stats)

    for trade_id in no_completed_h1:
        plan = effective_plan_by_trade[trade_id]
        if str(plan.get("order_type", "LIMIT")).upper() == "MARKET" and trade_id in outcomes and outcomes[trade_id].get("entry_triggered"):
            continue
        outcomes[trade_id] = evaluate_trade_path(plan, pd.DataFrame(), timeframe=PRIMARY_TIMEFRAME, now=now_ts)
    for request_id, trade_id in request_to_trade.items():
        plan = effective_plan_by_trade[trade_id]
        outcomes[trade_id] = evaluate_trade_path(
            plan, primary.get(request_id, pd.DataFrame()), timeframe=PRIMARY_TIMEFRAME, now=now_ts
        )

    # H1 ambiguities are resolved with M5 and then M1. MARKET fill resolution is
    # already complete at this point; these layers resolve only post-fill exits.
    for resolution_tf in RESOLUTION_TIMEFRAMES:
        unresolved = [
            trade_id for trade_id, outcome in outcomes.items()
            if outcome.get("lifecycle_status") == "AMBIGUOUS" and trade_id in effective_plan_by_trade
        ]
        if not unresolved:
            break
        resolution_requests: list[HistoryRequest] = []
        resolution_to_trade: dict[str, str] = {}
        for trade_id in unresolved:
            plan = effective_plan_by_trade[trade_id]
            start, end = _history_window(plan, now_ts, resolution_tf, force_full=True)
            end = min(end, _completed_boundary(now_ts, resolution_tf))
            if end <= start:
                continue
            rid = f"{resolution_tf.lower()}_{trade_id.replace('-', '')[:20]}"
            resolution_requests.append(HistoryRequest(str(plan["cfd_symbol"]), start, end, resolution_tf, rid))
            resolution_to_trade[rid] = trade_id
        resolved, resolution_stats = _cached_history_batch(
            config, resolution_requests, db_path=db_path, timeout_seconds=timeout_seconds
        )
        _merge_cache_stats(cache_stats, resolution_stats)
        for request_id, trade_id in resolution_to_trade.items():
            plan = effective_plan_by_trade[trade_id]
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
        symbol = str(plan_by_trade[trade_id]["cfd_symbol"])
        daily_requests.append(HistoryRequest(symbol, start, end, "D1", rid))
        daily_to_trade[rid] = trade_id
    if daily_requests:
        daily, daily_stats = _cached_history_batch(
            config, daily_requests, db_path=db_path, timeout_seconds=timeout_seconds
        )
        _merge_cache_stats(cache_stats, daily_stats)
        for request_id, trade_id in daily_to_trade.items():
            eval_plan = effective_plan_by_trade.get(trade_id, plan_by_trade[trade_id])
            outcomes[trade_id] = add_forward_returns(
                outcomes[trade_id], eval_plan, daily.get(request_id, pd.DataFrame())
            )

    updated = 0
    ambiguous = 0
    regressions_blocked = 0
    status_counts: dict[str, int] = {}
    for trade_id, outcome in outcomes.items():
        previous_status = plan_by_trade.get(trade_id, {}).get("lifecycle_status", "PLANNED")
        outcome, blocked = _guard_active_state_regression(
            trade_id, previous_status, outcome, db_path=db_path
        )
        regressions_blocked += int(blocked)
        status = str(outcome.get("lifecycle_status", "PLANNED"))
        status_counts[status] = status_counts.get(status, 0) + 1
        ambiguous += int(status == "AMBIGUOUS")
        upsert_trade_outcome(trade_id, outcome, db_path=db_path)
        updated += 1

    return {
        "checked": len(plans),
        "updated": updated,
        "ambiguous": ambiguous,
        "state_regressions_blocked": regressions_blocked,
        "status_counts": status_counts,
        "errors": [],
        "symbols_checked": len({str(value) for value in plans["cfd_symbol"].dropna().tolist()}),
        "remote_requests": int(cache_stats["remote_requests"]),
        "cache_only_requests": int(cache_stats["cache_only_requests"]),
        "bars_loaded": int(cache_stats["bars_loaded"]),
        "bars_loaded_by_timeframe": dict(cache_stats["bars_loaded_by_timeframe"]),
        "cache_time_basis_reset": cache_time_basis_reset,
        "remote_requests_by_timeframe": dict(cache_stats["remote_requests_by_timeframe"]),
        "remote_symbols": sorted(cache_stats["remote_symbols"]),
    }
