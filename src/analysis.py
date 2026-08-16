
from __future__ import annotations

import numpy as np
import pandas as pd

from .publication import backtest_available_date, publication_info
from .prices import align_prices_to_cot


def cot_index(series: pd.Series, weeks: int) -> pd.Series:
    rolling_min = series.rolling(weeks, min_periods=weeks).min()
    rolling_max = series.rolling(weeks, min_periods=weeks).max()
    span = (rolling_max - rolling_min).replace(0, np.nan)
    return (100 * (series - rolling_min) / span).clip(0, 100)


def _last_percentile(values) -> float:
    """Percentile rank of the most recent value using only the supplied trailing window."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return np.nan
    last = arr[-1]
    return float(np.mean(arr <= last) * 100.0)


def rolling_percentile(series: pd.Series, weeks: int) -> pd.Series:
    return series.rolling(weeks, min_periods=weeks).apply(_last_percentile, raw=True)


def enrich_cot(
    df: pd.DataFrame,
    weeks: int = 26,
    validation_weeks: int = 156,
    range_weeks: int = 26,
) -> pd.DataFrame:
    out = df.copy()

    out["commercial_net"] = out["commercial_long"] - out["commercial_short"]
    out["retail_net"] = out["retail_long"] - out["retail_short"]
    out["noncommercial_net"] = out["noncommercial_long"] - out["noncommercial_short"]
    out["noncommercial_gross"] = out["noncommercial_long"].abs() + out["noncommercial_short"].abs()

    # Stage 1: fast COT index regime.
    out["commercial_index"] = cot_index(out["commercial_net"], weeks)
    out["retail_index"] = cot_index(out["retail_net"], weeks)

    # Raw net positioning.
    oi = out["open_interest_all"].replace(0, np.nan)
    out["commercial_net_oi"] = out["commercial_net"] / oi
    out["retail_net_oi"] = out["retail_net"] / oi

    # Stage 2: independent, longer-horizon validation of absolute net positioning.
    out["commercial_net_percentile"] = rolling_percentile(
        out["commercial_net"], validation_weeks
    )
    out["retail_net_percentile"] = rolling_percentile(
        out["retail_net"], validation_weeks
    )
    out["noncommercial_net_percentile"] = rolling_percentile(
        out["noncommercial_net"], validation_weeks
    )

    # Open-interest participation context. It is deliberately not used as
    # a directional signal yet; it remains a descriptive layer.
    out["open_interest_change_4w"] = out["open_interest_all"].diff(4)
    out["open_interest_change_4w_pct"] = out["open_interest_all"].pct_change(4) * 100.0
    out["open_interest_change_4w_percentile"] = rolling_percentile(
        out["open_interest_change_4w"], validation_weeks
    )

    # OI-normalised percentiles are shown as secondary structural context.
    out["commercial_net_oi_percentile"] = rolling_percentile(
        out["commercial_net_oi"], validation_weeks
    )
    out["retail_net_oi_percentile"] = rolling_percentile(
        out["retail_net_oi"], validation_weeks
    )

    # Commercial extreme range: actual contract values, not only a 0-100 index.
    out["commercial_range_high"] = out["commercial_net"].rolling(
        range_weeks, min_periods=range_weeks
    ).max()
    out["commercial_range_low"] = out["commercial_net"].rolling(
        range_weeks, min_periods=range_weeks
    ).min()
    out["commercial_range_width"] = (
        out["commercial_range_high"] - out["commercial_range_low"]
    )
    out["commercial_distance_to_high"] = (
        out["commercial_range_high"] - out["commercial_net"]
    )
    out["commercial_distance_to_low"] = (
        out["commercial_net"] - out["commercial_range_low"]
    )
    width = out["commercial_range_width"].replace(0, np.nan)
    out["commercial_distance_high_pct"] = (
        out["commercial_distance_to_high"] / width * 100.0
    )
    out["commercial_distance_low_pct"] = (
        out["commercial_distance_to_low"] / width * 100.0
    )

    # Positioning velocity. Raw contract changes are deliberately retained;
    # the percentile answers whether a 4W change is historically unusual.
    for group in ("commercial", "retail", "noncommercial"):
        net = out[f"{group}_net"]
        out[f"{group}_change_1w"] = net.diff(1)
        out[f"{group}_change_4w"] = net.diff(4)
        out[f"{group}_change_8w"] = net.diff(8)
        # Recent 4W change minus the preceding 4W change.
        out[f"{group}_acceleration_4w"] = (
            2.0 * out[f"{group}_change_4w"] - out[f"{group}_change_8w"]
        )
        out[f"{group}_change_4w_percentile"] = rolling_percentile(
            out[f"{group}_change_4w"], validation_weeks
        )

    return out


def current_signal(row: pd.Series, upper: float = 80, lower: float = 20) -> str:
    if row["commercial_index"] >= upper and row["retail_index"] <= lower:
        return "BULLISH"
    if row["commercial_index"] <= lower and row["retail_index"] >= upper:
        return "BEARISH"
    return "NEUTRAL"


def net_validation(
    row: pd.Series,
    signal: str,
    upper: float = 80,
    lower: float = 20,
) -> dict:
    comm = row.get("commercial_net_percentile", np.nan)
    retail = row.get("retail_net_percentile", np.nan)

    if signal == "NEUTRAL" or not np.isfinite(comm) or not np.isfinite(retail):
        return {
            "status": "NO CONFIRMATION",
            "commercial_confirmed": False,
            "retail_confirmed": False,
        }

    if signal == "BULLISH":
        commercial_confirmed = comm >= upper
        retail_confirmed = retail <= lower
    else:
        commercial_confirmed = comm <= lower
        retail_confirmed = retail >= upper

    if commercial_confirmed and retail_confirmed:
        status = "CONFIRMED"
    elif commercial_confirmed or retail_confirmed:
        status = "PARTIAL"
    else:
        status = "UNCONFIRMED"

    return {
        "status": status,
        "commercial_confirmed": bool(commercial_confirmed),
        "retail_confirmed": bool(retail_confirmed),
    }



def commercial_range_state(row: pd.Series) -> dict:
    high = float(row.get("commercial_range_high", np.nan))
    low = float(row.get("commercial_range_low", np.nan))
    current = float(row.get("commercial_net", np.nan))
    d_high = float(row.get("commercial_distance_high_pct", np.nan))
    d_low = float(row.get("commercial_distance_low_pct", np.nan))

    if not all(np.isfinite(v) for v in [high, low, current, d_high, d_low]):
        return {"state": "NO RANGE DATA", "nearest": "—", "distance_pct": np.nan}

    if d_high <= 2.0:
        state = "AT / NEAR RANGE HIGH"
        nearest = "HIGH"
        distance = d_high
    elif d_low <= 2.0:
        state = "AT / NEAR RANGE LOW"
        nearest = "LOW"
        distance = d_low
    elif d_high <= 15.0:
        state = "UPPER RANGE"
        nearest = "HIGH"
        distance = d_high
    elif d_low <= 15.0:
        state = "LOWER RANGE"
        nearest = "LOW"
        distance = d_low
    else:
        state = "MID RANGE"
        if d_high <= d_low:
            nearest, distance = "HIGH", d_high
        else:
            nearest, distance = "LOW", d_low

    return {"state": state, "nearest": nearest, "distance_pct": float(distance)}


def positioning_velocity_state(row: pd.Series, direction: int = 0) -> dict:
    c1 = float(row.get("commercial_change_1w", np.nan))
    c4 = float(row.get("commercial_change_4w", np.nan))
    c8 = float(row.get("commercial_change_8w", np.nan))
    accel = float(row.get("commercial_acceleration_4w", np.nan))
    pct = float(row.get("commercial_change_4w_percentile", np.nan))

    if not all(np.isfinite(v) for v in [c1, c4, c8, accel, pct]):
        return {"state": "NO VELOCITY DATA", "confirmation": "—"}

    if c4 > 0:
        state = "COMMERCIAL NET RISING"
        if accel > 0:
            state += " · ACCELERATING"
    elif c4 < 0:
        state = "COMMERCIAL NET FALLING"
        if accel < 0:
            state += " · ACCELERATING"
    else:
        state = "COMMERCIAL NET FLAT"

    if direction > 0:
        confirmation = "CONFIRMING BULLISH" if c4 > 0 else "NOT CONFIRMING BULLISH"
    elif direction < 0:
        confirmation = "CONFIRMING BEARISH" if c4 < 0 else "NOT CONFIRMING BEARISH"
    else:
        confirmation = "NO ACTIVE DIRECTION"

    return {
        "state": state,
        "confirmation": confirmation,
        "change_1w": c1,
        "change_4w": c4,
        "change_8w": c8,
        "acceleration_4w": accel,
        "change_4w_percentile": pct,
    }


def hedger_cycle_state(
    cot: pd.DataFrame,
    upper: float = 80,
    lower: float = 20,
    release_active_weeks: int = 6,
) -> dict:
    """Track entering, persistence, and release of Commercial COT extremes."""
    valid = cot.dropna(subset=["commercial_index", "commercial_net"]).copy().reset_index(drop=True)
    if len(valid) < 2:
        return {
            "state": "NO CYCLE DATA", "direction": 0, "phase": "NONE",
            "extreme_duration": 0, "weeks_since_release": np.nan,
            "extreme_index": np.nan, "extreme_net": np.nan,
            "entry_date": None, "release_date": None,
        }

    idx = valid["commercial_index"].to_numpy(dtype=float)
    zones = np.where(idx >= upper, 1, np.where(idx <= lower, -1, 0))
    last = len(valid) - 1
    current_zone = int(zones[last])

    def episode(start_end_index: int, zone: int):
        end = start_end_index
        start = end
        while start > 0 and int(zones[start - 1]) == zone:
            start -= 1
        ep = valid.iloc[start:end + 1]
        if zone == 1:
            extreme_index = float(ep["commercial_index"].max())
            extreme_net = float(ep["commercial_net"].max())
        else:
            extreme_index = float(ep["commercial_index"].min())
            extreme_net = float(ep["commercial_net"].min())
        return start, end, ep, extreme_index, extreme_net

    if current_zone != 0:
        start, end, ep, extreme_index, extreme_net = episode(last, current_zone)
        duration = len(ep)
        if current_zone == 1:
            phase = "ENTERING BULLISH EXTREME" if duration == 1 else "BULLISH EXTREME · PERSISTENCE"
        else:
            phase = "ENTERING BEARISH EXTREME" if duration == 1 else "BEARISH EXTREME · PERSISTENCE"
        return {
            "state": phase,
            "phase": "EXTREME",
            "direction": current_zone,
            "extreme_duration": int(duration),
            "weeks_since_release": np.nan,
            "extreme_index": extreme_index,
            "extreme_net": extreme_net,
            "entry_date": valid.iloc[start]["report_date"],
            "release_date": None,
            "current_net_distance": float(valid.iloc[-1]["commercial_net"] - extreme_net),
        }

    # Current row is outside extremes. Find the most recent completed extreme episode.
    last_extreme = None
    for j in range(last - 1, -1, -1):
        if int(zones[j]) != 0:
            last_extreme = j
            break

    if last_extreme is None:
        return {
            "state": "NO ACTIVE CYCLE", "phase": "NONE", "direction": 0,
            "extreme_duration": 0, "weeks_since_release": np.nan,
            "extreme_index": np.nan, "extreme_net": np.nan,
            "entry_date": None, "release_date": None,
        }

    z = int(zones[last_extreme])
    start, end, ep, extreme_index, extreme_net = episode(last_extreme, z)
    weeks_since_release = last - end - 1
    release_date = valid.iloc[end + 1]["report_date"] if end + 1 <= last else None

    if weeks_since_release <= release_active_weeks:
        if z == 1:
            state = "BULLISH RELEASE" if weeks_since_release == 0 else "BULLISH RELEASE · ACTIVE"
        else:
            state = "BEARISH RELEASE" if weeks_since_release == 0 else "BEARISH RELEASE · ACTIVE"
        direction = z
        phase = "RELEASE"
    else:
        state = "POST-RELEASE / NO ACTIVE CYCLE"
        direction = 0
        phase = "POST-RELEASE"

    return {
        "state": state,
        "phase": phase,
        "direction": direction,
        "extreme_duration": int(len(ep)),
        "weeks_since_release": int(weeks_since_release),
        "extreme_index": extreme_index,
        "extreme_net": extreme_net,
        "entry_date": valid.iloc[start]["report_date"],
        "release_date": release_date,
        "current_net_distance": float(valid.iloc[-1]["commercial_net"] - extreme_net),
    }


def hedger_release_state(
    cot: pd.DataFrame,
    upper: float = 80,
    lower: float = 20,
    recent_extreme_weeks: int = 6,
) -> dict:
    """Backward-compatible wrapper around the full Hedger Cycle state."""
    cycle = hedger_cycle_state(
        cot, upper=upper, lower=lower, release_active_weeks=recent_extreme_weeks
    )
    return {
        "state": cycle["state"],
        "direction": cycle["direction"] if cycle["phase"] == "RELEASE" else 0,
        "weeks_since_extreme": cycle.get("weeks_since_release", np.nan),
    }


def historical_hedger_releases(
    cot: pd.DataFrame,
    prices: pd.DataFrame,
    upper: float = 80,
    lower: float = 20,
    horizons=(4, 8),
) -> pd.DataFrame:
    """Event study starting on the first COT report after Commercials leave an extreme."""
    x = cot.dropna(subset=["commercial_index", "commercial_net"]).copy().reset_index(drop=True)
    if len(x) < 2 or prices.empty:
        return pd.DataFrame()

    pidx = prices.index

    def price_strictly_after(ts):
        pos = pidx.searchsorted(pd.Timestamp(ts), side="right")
        if pos >= len(pidx):
            return np.nan, pd.NaT
        return float(prices.iloc[pos]["close"]), pd.Timestamp(pidx[pos])

    def price_on_or_after(ts):
        pos = pidx.searchsorted(pd.Timestamp(ts))
        if pos >= len(pidx):
            return np.nan
        return float(prices.iloc[pos]["close"])

    rows = []
    for i in range(1, len(x)):
        prev_i = float(x.iloc[i-1]["commercial_index"])
        cur_i = float(x.iloc[i]["commercial_index"])
        if prev_i >= upper and cur_i < upper:
            direction, state = 1, "BULLISH RELEASE"
        elif prev_i <= lower and cur_i > lower:
            direction, state = -1, "BEARISH RELEASE"
        else:
            continue

        # Determine duration and actual net extreme of the episode that just ended.
        zone_test = (lambda v: v >= upper) if direction == 1 else (lambda v: v <= lower)
        j = i - 1
        start = j
        while start > 0 and zone_test(float(x.iloc[start-1]["commercial_index"])):
            start -= 1
        ep = x.iloc[start:i]
        extreme_net = float(ep["commercial_net"].max() if direction == 1 else ep["commercial_net"].min())
        extreme_index = float(ep["commercial_index"].max() if direction == 1 else ep["commercial_index"].min())

        event_date = x.iloc[i]["report_date"]
        available_date = backtest_available_date(event_date)
        entry, trade_date = price_strictly_after(available_date)
        if not np.isfinite(entry):
            continue

        pub = publication_info(event_date)
        rec = {
            "event_date": event_date,
            "publication_date": pub["publication_date"],
            "publication_status": pub["publication_status"],
            "trade_date": trade_date,
            "release": state,
            "direction": direction,
            "extreme_duration": int(len(ep)),
            "extreme_index": extreme_index,
            "extreme_net": extreme_net,
            "release_commercial_net": float(x.iloc[i]["commercial_net"]),
        }
        for h in horizons:
            px = price_on_or_after(trade_date + pd.Timedelta(weeks=int(h)))
            raw = px / entry - 1.0 if np.isfinite(px) else np.nan
            rec[f"return_{h}w"] = raw
            rec[f"aligned_return_{h}w"] = raw * direction if np.isfinite(raw) else np.nan
        rows.append(rec)

    return pd.DataFrame(rows)


def summarize_releases(events: pd.DataFrame, horizons=(4, 8)) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    rows = []
    for name, subset in [
        ("ALL RELEASES", events),
        ("BULLISH RELEASES", events[events["direction"] == 1]),
        ("BEARISH RELEASES", events[events["direction"] == -1]),
    ]:
        for h in horizons:
            vals = subset[f"aligned_return_{h}w"].dropna()
            rows.append({
                "group": name,
                "horizon": f"{h}W",
                "events": int(len(vals)),
                "hit_rate": float((vals > 0).mean()) if len(vals) else np.nan,
                "mean_return": float(vals.mean()) if len(vals) else np.nan,
                "median_return": float(vals.median()) if len(vals) else np.nan,
            })
    return pd.DataFrame(rows)


def classify_positioning_bias(
    row: pd.Series,
    upper: float = 80,
    lower: float = 20,
    validation_upper: float = 80,
    validation_lower: float = 20,
) -> dict:
    """
    Less binary directional state than the original strict 80/20 gate.

    A strict signal requires Commercial + Retail index opposition.
    A net-backed bias can still exist when the Commercial COT index is extreme
    and the longer-horizon Commercial/Retail net percentiles confirm it.
    """
    ci = float(row.get("commercial_index", np.nan))
    ri = float(row.get("retail_index", np.nan))
    cp = float(row.get("commercial_net_percentile", np.nan))
    rp = float(row.get("retail_net_percentile", np.nan))

    if not all(np.isfinite(v) for v in [ci, ri, cp, rp]):
        return {"state": "NEUTRAL", "direction": 0, "strict": False, "net_backed": False}

    strict_bull = ci >= upper and ri <= lower
    strict_bear = ci <= lower and ri >= upper

    net_bull = ci >= upper and cp >= validation_upper and rp <= validation_lower
    net_bear = ci <= lower and cp <= validation_lower and rp >= validation_upper

    if strict_bull and net_bull:
        return {"state": "BULLISH CONFIRMED", "direction": 1, "strict": True, "net_backed": True}
    if strict_bear and net_bear:
        return {"state": "BEARISH CONFIRMED", "direction": -1, "strict": True, "net_backed": True}
    if net_bull:
        return {"state": "BULLISH BIAS", "direction": 1, "strict": strict_bull, "net_backed": True}
    if net_bear:
        return {"state": "BEARISH BIAS", "direction": -1, "strict": strict_bear, "net_backed": True}
    if strict_bull:
        return {"state": "BULLISH INDEX EXTREME", "direction": 1, "strict": True, "net_backed": False}
    if strict_bear:
        return {"state": "BEARISH INDEX EXTREME", "direction": -1, "strict": True, "net_backed": False}

    # Commercial-only watch state: useful before Retail reaches the opposite 20/80.
    if ci >= upper:
        return {"state": "BULLISH WATCH", "direction": 1, "strict": False, "net_backed": False}
    if ci <= lower:
        return {"state": "BEARISH WATCH", "direction": -1, "strict": False, "net_backed": False}

    return {"state": "NEUTRAL", "direction": 0, "strict": False, "net_backed": False}


def attach_cot_prices(cot: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Compatibility wrapper around the audited Tuesday/COT price alignment."""
    return align_prices_to_cot(cot, prices)


def _directional_weeks(series: pd.Series, lookback: int, up: bool) -> int:
    values = series.dropna().tail(lookback + 1).to_numpy(dtype=float)
    if len(values) < lookback + 1:
        return 0
    diffs = np.diff(values)
    return int(np.sum(diffs > 0)) if up else int(np.sum(diffs < 0))


def nc_divergence_legacy(
    cot_with_prices: pd.DataFrame,
    lookback_weeks: int = 4,
    min_confirming_weeks: int = 3,
    min_active_leg_weeks: int = 2,
    min_price_move_pct: float = 1.0,
    min_net_change_pct: float = 1.0,
    min_active_leg_pct: float = 0.5,
    active_leg_share: float = 0.55,
) -> dict:
    """
    Python translation of the user's TradingView Non-Commercial divergence logic.

    Price and NC positioning are compared over the same COT-week horizon.
    NC changes are scaled by prior Non-Commercial gross positioning.
    """
    required = [
        "cot_price", "noncommercial_long", "noncommercial_short",
        "noncommercial_net",
    ]
    x = cot_with_prices.dropna(subset=required).copy()

    if len(x) < lookback_weeks + 1:
        return {
            "status": "NOT ENOUGH DATA",
            "direction": 0,
            "score": 0.0,
            "price_move_pct": np.nan,
            "net_change_pct": np.nan,
            "long_change_pct": np.nan,
            "short_change_pct": np.nan,
            "net_confirming_weeks": 0,
            "active_leg_weeks": 0,
            "active_share": np.nan,
        }

    cur = x.iloc[-1]
    prior = x.iloc[-(lookback_weeks + 1)]

    price_prior = float(prior["cot_price"])
    price_current = float(cur["cot_price"])

    long_prior = float(prior["noncommercial_long"])
    short_prior = float(prior["noncommercial_short"])
    long_current = float(cur["noncommercial_long"])
    short_current = float(cur["noncommercial_short"])

    gross_prior = abs(long_prior) + abs(short_prior)
    if price_prior == 0 or gross_prior == 0:
        return {
            "status": "INVALID BASE",
            "direction": 0,
            "score": 0.0,
            "price_move_pct": np.nan,
            "net_change_pct": np.nan,
            "long_change_pct": np.nan,
            "short_change_pct": np.nan,
            "net_confirming_weeks": 0,
            "active_leg_weeks": 0,
            "active_share": np.nan,
        }

    price_move_pct = (price_current / price_prior - 1.0) * 100.0
    long_delta_pct = (long_current - long_prior) / gross_prior * 100.0
    short_delta_pct = (short_current - short_prior) / gross_prior * 100.0

    net_prior = long_prior - short_prior
    net_current = long_current - short_current
    net_delta_pct = (net_current - net_prior) / gross_prior * 100.0

    net_up_weeks = _directional_weeks(x["noncommercial_net"], lookback_weeks, True)
    net_down_weeks = _directional_weeks(x["noncommercial_net"], lookback_weeks, False)
    long_up_weeks = _directional_weeks(x["noncommercial_long"], lookback_weeks, True)
    long_down_weeks = _directional_weeks(x["noncommercial_long"], lookback_weeks, False)
    short_up_weeks = _directional_weeks(x["noncommercial_short"], lookback_weeks, True)
    short_down_weeks = _directional_weeks(x["noncommercial_short"], lookback_weeks, False)

    bullish_pressure = max(long_delta_pct, 0.0) + max(-short_delta_pct, 0.0)
    bearish_pressure = max(-long_delta_pct, 0.0) + max(short_delta_pct, 0.0)

    active_long_share = (
        max(long_delta_pct, 0.0) / bullish_pressure
        if bullish_pressure > 0 else 0.0
    )
    active_short_share = (
        max(short_delta_pct, 0.0) / bearish_pressure
        if bearish_pressure > 0 else 0.0
    )

    bullish_raw = (
        price_move_pct <= -min_price_move_pct
        and net_delta_pct >= min_net_change_pct
        and net_up_weeks >= min_confirming_weeks
    )
    bearish_raw = (
        price_move_pct >= min_price_move_pct
        and net_delta_pct <= -min_net_change_pct
        and net_down_weeks >= min_confirming_weeks
    )

    bullish_active_long = (
        bullish_raw
        and long_delta_pct >= min_active_leg_pct
        and active_long_share >= active_leg_share
        and long_up_weeks >= min_active_leg_weeks
    )
    bullish_short_covering = (
        bullish_raw
        and not bullish_active_long
        and short_delta_pct < 0.0
        and short_down_weeks >= min_active_leg_weeks
    )

    bearish_active_short = (
        bearish_raw
        and short_delta_pct >= min_active_leg_pct
        and active_short_share >= active_leg_share
        and short_up_weeks >= min_active_leg_weeks
    )
    bearish_mixed_distribution = (
        bearish_raw
        and not bearish_active_short
        and short_delta_pct > 0.0
        and short_up_weeks >= min_active_leg_weeks
    )
    bearish_profit_taking = (
        bearish_raw
        and not bearish_active_short
        and not bearish_mixed_distribution
        and long_delta_pct < 0.0
        and long_down_weeks >= min_active_leg_weeks
    )

    if bullish_active_long:
        status, direction, score = "BULLISH · ACTIVE LONG BUILD", 1, 100.0
        active_weeks, share = long_up_weeks, active_long_share
    elif bullish_short_covering:
        status, direction, score = "BULLISH · SHORT COVERING", 1, 65.0
        active_weeks, share = short_down_weeks, 1.0 - active_long_share
    elif bullish_raw:
        status, direction, score = "BULLISH · NET BUILD", 1, 50.0
        active_weeks, share = net_up_weeks, np.nan
    elif bearish_active_short:
        status, direction, score = "BEARISH · ACTIVE SHORT BUILD", -1, -100.0
        active_weeks, share = short_up_weeks, active_short_share
    elif bearish_mixed_distribution:
        status, direction, score = "BEARISH · MIXED DISTRIBUTION", -1, -65.0
        active_weeks, share = short_up_weeks, active_short_share
    elif bearish_profit_taking:
        status, direction, score = "LONG LIQUIDATION / PROFIT TAKING", -1, -25.0
        active_weeks, share = long_down_weeks, np.nan
    elif bearish_raw:
        status, direction, score = "BEARISH · NET REDUCTION", -1, -40.0
        active_weeks, share = net_down_weeks, np.nan
    else:
        status, direction, score = "NO DIVERGENCE", 0, 0.0
        active_weeks, share = 0, np.nan

    return {
        "status": status,
        "direction": direction,
        "score": score,
        "price_move_pct": float(price_move_pct),
        "net_change_pct": float(net_delta_pct),
        "long_change_pct": float(long_delta_pct),
        "short_change_pct": float(short_delta_pct),
        "net_confirming_weeks": int(net_up_weeks if direction >= 0 else net_down_weeks),
        "active_leg_weeks": int(active_weeks),
        "active_share": float(share) if np.isfinite(share) else np.nan,
    }


def historical_nc_divergences_legacy(
    cot_with_prices: pd.DataFrame,
    lookback_weeks: int = 4,
    min_confirming_weeks: int = 3,
    min_active_leg_weeks: int = 2,
    min_price_move_pct: float = 1.0,
    min_net_change_pct: float = 1.0,
    min_active_leg_pct: float = 0.5,
    active_leg_share: float = 0.55,
) -> pd.DataFrame:
    rows = []
    for end in range(lookback_weeks, len(cot_with_prices)):
        window = cot_with_prices.iloc[: end + 1]
        d = nc_divergence_legacy(
            window,
            lookback_weeks=lookback_weeks,
            min_confirming_weeks=min_confirming_weeks,
            min_active_leg_weeks=min_active_leg_weeks,
            min_price_move_pct=min_price_move_pct,
            min_net_change_pct=min_net_change_pct,
            min_active_leg_pct=min_active_leg_pct,
            active_leg_share=active_leg_share,
        )
        if d["direction"] != 0:
            rows.append({
                "event_date": cot_with_prices.iloc[end]["report_date"],
                **d,
            })
    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows).sort_values("event_date")
    # De-duplicate consecutive same-direction weekly divergence observations.
    out["new_episode"] = (
        (out["direction"] != out["direction"].shift(1))
        | (out["event_date"].diff().dt.days > 8)
    )
    return out[out["new_episode"]].drop(columns=["new_episode"]).reset_index(drop=True)


# Backward-compatible aliases. New code should use the explicit *_legacy names.
noncommercial_divergence = nc_divergence_legacy
historical_nc_divergences = historical_nc_divergences_legacy


def combined_direction_state(
    positioning: dict,
    release: dict,
    nc_divergence: dict,
) -> str:
    pdir = int(positioning.get("direction", 0))
    rdir = int(release.get("direction", 0))
    ndir = int(nc_divergence.get("direction", 0))

    # Highest priority: release + non-commercial confirmation.
    if rdir == 1 and ndir == 1:
        return "BULLISH RELEASE + NC CONFIRMATION"
    if rdir == -1 and ndir == -1:
        return "BEARISH RELEASE + NC CONFIRMATION"

    # Positioning regime + NC divergence.
    if pdir == 1 and ndir == 1:
        return "BULLISH · NC CONFIRMED"
    if pdir == -1 and ndir == -1:
        return "BEARISH · NC CONFIRMED"

    # Release itself is actionable context even without NC divergence.
    if rdir == 1:
        return "BULLISH RELEASE"
    if rdir == -1:
        return "BEARISH RELEASE"

    return positioning.get("state", "NEUTRAL")

def build_events(
    cot: pd.DataFrame,
    prices: pd.DataFrame,
    upper=80,
    lower=20,
    validation_upper=80,
    validation_lower=20,
    horizons=(4, 8),
) -> pd.DataFrame:
    required = [
        "commercial_index",
        "retail_index",
        "commercial_net_percentile",
        "retail_net_percentile",
    ]
    x = cot.dropna(subset=required).copy()
    if x.empty or prices.empty:
        return pd.DataFrame()

    conditions = [
        (x["commercial_index"] >= upper) & (x["retail_index"] <= lower),
        (x["commercial_index"] <= lower) & (x["retail_index"] >= upper),
    ]
    x["signal"] = np.select(
        conditions,
        ["BULLISH", "BEARISH"],
        default="NEUTRAL",
    )

    # Only the first week when entering a new bullish/bearish extreme episode.
    x["is_event"] = (
        (x["signal"] != "NEUTRAL")
        & (x["signal"] != x["signal"].shift(1))
    )
    events = x[x["is_event"]].copy()

    if events.empty:
        return pd.DataFrame()

    price_index = prices.index

    def price_strictly_after(ts):
        pos = price_index.searchsorted(pd.Timestamp(ts), side="right")
        if pos >= len(price_index):
            return np.nan, pd.NaT
        return float(prices.iloc[pos]["close"]), pd.Timestamp(price_index[pos])

    def price_on_or_after(ts):
        pos = price_index.searchsorted(pd.Timestamp(ts))
        if pos >= len(price_index):
            return np.nan
        return float(prices.iloc[pos]["close"])

    rows = []

    for _, event in events.iterrows():
        available_date = backtest_available_date(event["report_date"])
        entry, trade_date = price_strictly_after(available_date)
        if not np.isfinite(entry):
            continue

        pub = publication_info(event["report_date"])
        validation = net_validation(
            event,
            event["signal"],
            upper=validation_upper,
            lower=validation_lower,
        )

        rec = {
            "event_date": event["report_date"],
            "publication_date": pub["publication_date"],
            "publication_status": pub["publication_status"],
            "trade_date": trade_date,
            "signal": event["signal"],
            "validation": validation["status"],
            "commercial_index": event["commercial_index"],
            "retail_index": event["retail_index"],
            "commercial_net": event["commercial_net"],
            "retail_net": event["retail_net"],
            "commercial_net_percentile": event["commercial_net_percentile"],
            "retail_net_percentile": event["retail_net_percentile"],
            "commercial_net_oi_percentile": event["commercial_net_oi_percentile"],
            "retail_net_oi_percentile": event["retail_net_oi_percentile"],
            "entry_price": entry,
        }

        sign = 1 if event["signal"] == "BULLISH" else -1

        for h in horizons:
            target = trade_date + pd.Timedelta(weeks=int(h))
            px = price_on_or_after(target)
            raw = px / entry - 1 if np.isfinite(px) else np.nan
            rec[f"return_{h}w"] = raw
            rec[f"aligned_return_{h}w"] = (
                raw * sign if np.isfinite(raw) else np.nan
            )

        rows.append(rec)

    return pd.DataFrame(rows)


def summarize_events(events: pd.DataFrame, horizons=(4, 8)) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()

    groups = [
        ("ALL INDEX SIGNALS", events),
        ("NET CONFIRMED", events[events["validation"] == "CONFIRMED"]),
        ("PARTIAL", events[events["validation"] == "PARTIAL"]),
        ("UNCONFIRMED", events[events["validation"] == "UNCONFIRMED"]),
        ("BULLISH", events[events["signal"] == "BULLISH"]),
        ("BEARISH", events[events["signal"] == "BEARISH"]),
    ]

    rows = []
    for group_name, subset in groups:
        for h in horizons:
            col = f"aligned_return_{h}w"
            vals = (
                subset[col].dropna()
                if col in subset.columns
                else pd.Series(dtype=float)
            )
            rows.append({
                "group": group_name,
                "horizon": f"{h}W",
                "events": int(len(vals)),
                "hit_rate": float((vals > 0).mean()) if len(vals) else np.nan,
                "mean_return": float(vals.mean()) if len(vals) else np.nan,
                "median_return": float(vals.median()) if len(vals) else np.nan,
            })

    return pd.DataFrame(rows)
