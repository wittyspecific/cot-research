from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from .analysis import rolling_percentile
from .research_lab import forward_return_from_report


DEFAULT_WINDOWS = (104, 156, 208)
DEFAULT_THRESHOLDS = (70, 75, 80, 85, 90, 95)
DEFAULT_HORIZONS = (1, 2, 4, 8, 12)
FLOW_LAGS = (1, 2, 4)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def add_positioning_dynamics_features(
    enriched: pd.DataFrame,
    group_key: str,
    *,
    windows: Sequence[int] = DEFAULT_WINDOWS,
) -> pd.DataFrame:
    """Create research-only state/flow features for one CFTC group.

    Raw contracts and net/open-interest are retained in parallel. Velocity is
    expressed per week so 1W/2W/4W are directly comparable. Acceleration is
    fast 1W velocity minus slower 4W velocity. No production rule is changed.
    """
    out = enriched.copy()
    raw_col = f"{group_key}_net"
    oi_col = f"{group_key}_net_oi"
    if raw_col not in out.columns:
        raise KeyError(f"Spalte fehlt: {raw_col}")
    if oi_col not in out.columns:
        raise KeyError(f"Spalte fehlt: {oi_col}")

    out[raw_col] = _numeric(out[raw_col])
    out[oi_col] = _numeric(out[oi_col])

    for basis, col in (("raw", raw_col), ("net_oi", oi_col)):
        series = _numeric(out[col])
        for lag in FLOW_LAGS:
            delta = series.diff(int(lag))
            out[f"{group_key}_{basis}_delta_{lag}w"] = delta
            out[f"{group_key}_{basis}_velocity_{lag}w"] = delta / float(lag)

        out[f"{group_key}_{basis}_acceleration_1v4"] = (
            out[f"{group_key}_{basis}_velocity_1w"]
            - out[f"{group_key}_{basis}_velocity_4w"]
        )

        for window in windows:
            window = int(window)
            pct_col = f"{group_key}_{basis}_pct_{window}w"
            out[pct_col] = rolling_percentile(series, window)
            pct = _numeric(out[pct_col])
            for lag in FLOW_LAGS:
                delta = pct.diff(int(lag))
                out[f"{pct_col}_delta_{lag}w"] = delta
                out[f"{pct_col}_velocity_{lag}w"] = delta / float(lag)
            out[f"{pct_col}_acceleration_1v4"] = (
                out[f"{pct_col}_velocity_1w"]
                - out[f"{pct_col}_velocity_4w"]
            )
    return out


def extreme_zone(percentile: pd.Series, *, upper: float, lower: float) -> pd.Series:
    values = _numeric(percentile)
    zone = np.where(values >= float(upper), 1, np.where(values <= float(lower), -1, 0))
    result = pd.Series(zone, index=percentile.index, dtype="int64")
    result[values.isna()] = 0
    return result


def extract_percentile_episodes(
    report_dates: pd.Series,
    percentile: pd.Series,
    *,
    upper: float = 80.0,
    lower: float = 20.0,
) -> pd.DataFrame:
    """Extract independent upper/lower percentile episodes and releases."""
    dates = pd.to_datetime(report_dates).reset_index(drop=True)
    pct = _numeric(percentile).reset_index(drop=True)
    zones = extreme_zone(pct, upper=upper, lower=lower).to_numpy(dtype=int)

    rows: list[dict] = []
    i = 0
    while i < len(pct):
        zone = int(zones[i])
        if zone == 0:
            i += 1
            continue
        start = i
        while i + 1 < len(pct) and int(zones[i + 1]) == zone:
            i += 1
        end = i
        release_pos = end + 1 if end + 1 < len(pct) else np.nan
        release_date = dates.iloc[int(release_pos)] if np.isfinite(release_pos) else pd.NaT
        ep = pct.iloc[start : end + 1]
        extreme = float(ep.max()) if zone > 0 else float(ep.min())
        boundary = float(upper) if zone > 0 else float(lower)
        depth = extreme - boundary if zone > 0 else boundary - extreme
        rows.append(
            {
                "zone": zone,
                "entry_pos": int(start),
                "end_pos": int(end),
                "release_pos": release_pos,
                "entry_report_date": dates.iloc[start],
                "last_extreme_report_date": dates.iloc[end],
                "release_report_date": release_date,
                "duration_weeks": int(end - start + 1),
                "extreme_percentile": extreme,
                "extreme_depth": float(max(depth, 0.0)),
            }
        )
        i += 1
    return pd.DataFrame(rows)


def release_directional_value(value, zone: int) -> float:
    """Orient a change so positive always means movement out of the extreme."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return np.nan
    if not np.isfinite(value) or int(zone) == 0:
        return np.nan
    return float(-int(zone) * value)


def _feature_at(frame: pd.DataFrame, pos, column: str):
    if column not in frame.columns:
        return np.nan
    if pos is None or (isinstance(pos, float) and not np.isfinite(pos)):
        return np.nan
    p = int(pos)
    if p < 0 or p >= len(frame):
        return np.nan
    value = pd.to_numeric(pd.Series([frame.iloc[p][column]]), errors="coerce").iloc[0]
    return float(value) if np.isfinite(value) else np.nan


def build_positioning_episode_dataset(
    enriched: pd.DataFrame,
    group_key: str,
    *,
    prices: pd.DataFrame | None = None,
    state_basis: str = "raw",
    windows: Sequence[int] = DEFAULT_WINDOWS,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    polarity: int = 0,
) -> pd.DataFrame:
    """Build one research row per independent percentile extreme episode."""
    frame = add_positioning_dynamics_features(enriched, group_key, windows=windows).reset_index(drop=True)
    if "report_date" not in frame.columns:
        raise KeyError("Spalte fehlt: report_date")

    rows: list[dict] = []
    for window in windows:
        window = int(window)
        pct_col = f"{group_key}_{state_basis}_pct_{window}w"
        if pct_col not in frame.columns:
            raise KeyError(f"Spalte fehlt: {pct_col}")

        for threshold in thresholds:
            threshold = float(threshold)
            lower = 100.0 - threshold
            if not (50.0 < threshold < 100.0):
                raise ValueError("threshold muss zwischen 50 und 100 liegen")

            episodes = extract_percentile_episodes(
                frame["report_date"], frame[pct_col], upper=threshold, lower=lower
            )
            for _, ep in episodes.iterrows():
                release_pos = ep["release_pos"]
                release_date = ep["release_report_date"]
                zone = int(ep["zone"])
                release_sign = -zone
                rec = {
                    "group_key": str(group_key),
                    "state_basis": str(state_basis),
                    "window_weeks": window,
                    "threshold_upper": threshold,
                    "threshold_lower": lower,
                    "zone": zone,
                    "expected_direction": int(zone) * int(polarity) if int(polarity) else np.nan,
                    "entry_report_date": ep["entry_report_date"],
                    "last_extreme_report_date": ep["last_extreme_report_date"],
                    "release_report_date": release_date,
                    "duration_weeks": int(ep["duration_weeks"]),
                    "extreme_percentile": float(ep["extreme_percentile"]),
                    "extreme_depth": float(ep["extreme_depth"]),
                    "release_available": bool(pd.notna(release_date)),
                    "percentile_at_release": _feature_at(frame, release_pos, pct_col),
                }

                for lag in FLOW_LAGS:
                    pairs = {
                        "pct": (f"{pct_col}_delta_{lag}w", f"{pct_col}_velocity_{lag}w"),
                        "raw": (f"{group_key}_raw_delta_{lag}w", f"{group_key}_raw_velocity_{lag}w"),
                        "net_oi": (f"{group_key}_net_oi_delta_{lag}w", f"{group_key}_net_oi_velocity_{lag}w"),
                    }
                    for prefix, (delta_col, vel_col) in pairs.items():
                        delta = _feature_at(frame, release_pos, delta_col)
                        velocity = _feature_at(frame, release_pos, vel_col)
                        rec[f"{prefix}_delta_{lag}w"] = delta
                        rec[f"{prefix}_velocity_{lag}w"] = velocity
                        rec[f"{prefix}_release_pressure_{lag}w"] = release_directional_value(delta, zone)
                        rec[f"{prefix}_release_velocity_{lag}w"] = release_directional_value(velocity, zone)

                for prefix, acc_col in {
                    "pct": f"{pct_col}_acceleration_1v4",
                    "raw": f"{group_key}_raw_acceleration_1v4",
                    "net_oi": f"{group_key}_net_oi_acceleration_1v4",
                }.items():
                    acc = _feature_at(frame, release_pos, acc_col)
                    rec[f"{prefix}_acceleration_1v4"] = acc
                    rec[f"{prefix}_release_acceleration"] = (
                        float(release_sign * acc) if np.isfinite(acc) else np.nan
                    )

                if prices is not None and not prices.empty and pd.notna(release_date):
                    for horizon in horizons:
                        horizon = int(horizon)
                        fwd = forward_return_from_report(prices, release_date, horizon)
                        rec[f"trade_date_{horizon}w"] = fwd["trade_date"]
                        rec[f"return_{horizon}w"] = fwd["return"]
                        rec[f"directional_return_{horizon}w"] = (
                            float(fwd["return"]) * float(rec["expected_direction"])
                            if int(polarity) and np.isfinite(fwd["return"])
                            else np.nan
                        )
                rows.append(rec)
    return pd.DataFrame(rows)


def summarize_window_threshold_grid(events: pd.DataFrame, *, horizon_weeks: int = 8) -> pd.DataFrame:
    """Compare lookback windows and threshold pairs on identical metrics."""
    if events is None or events.empty:
        return pd.DataFrame()
    horizon = int(horizon_weeks)
    directional_col = f"directional_return_{horizon}w"
    raw_col = f"return_{horizon}w"
    rows = []
    for keys, subset in events.groupby(["window_weeks", "threshold_upper", "threshold_lower"], dropna=False):
        window, upper, lower = keys
        directional = _numeric(subset[directional_col]).dropna() if directional_col in subset else pd.Series(dtype=float)
        raw = _numeric(subset[raw_col]).dropna() if raw_col in subset else pd.Series(dtype=float)
        rows.append(
            {
                "window_weeks": int(window),
                "threshold_upper": float(upper),
                "threshold_lower": float(lower),
                "episodes": int(len(subset)),
                "releases": int(subset["release_available"].sum()),
                "median_duration_weeks": float(_numeric(subset["duration_weeks"]).median()),
                "median_extreme_depth": float(_numeric(subset["extreme_depth"]).median()),
                f"n_{horizon}w": int(len(directional) if len(directional) else len(raw)),
                f"median_directional_return_{horizon}w": float(directional.median()) if len(directional) else np.nan,
                f"hit_rate_{horizon}w": float((directional > 0).mean()) if len(directional) else np.nan,
                f"median_raw_return_{horizon}w": float(raw.median()) if len(raw) else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(["window_weeks", "threshold_upper"]).reset_index(drop=True)


def quantile_effect_study(
    events: pd.DataFrame,
    feature: str,
    *,
    horizon_weeks: int = 8,
    quantiles: int = 4,
) -> pd.DataFrame:
    """Test whether increasing feature intensity is associated with better outcomes."""
    if events is None or events.empty or feature not in events.columns:
        return pd.DataFrame()
    ret_col = f"directional_return_{int(horizon_weeks)}w"
    if ret_col not in events.columns:
        return pd.DataFrame()
    work = events[[feature, ret_col]].copy()
    work[feature] = _numeric(work[feature])
    work[ret_col] = _numeric(work[ret_col])
    work = work.dropna()
    if len(work) < max(8, int(quantiles) * 2):
        return pd.DataFrame()
    try:
        work["bucket"] = pd.qcut(work[feature], q=int(quantiles), duplicates="drop")
    except ValueError:
        return pd.DataFrame()

    rows = []
    for bucket, subset in work.groupby("bucket", observed=True):
        returns = _numeric(subset[ret_col]).dropna()
        rows.append(
            {
                "feature": feature,
                "bucket": str(bucket),
                "n": int(len(returns)),
                "feature_median": float(_numeric(subset[feature]).median()),
                "directional_return_median": float(returns.median()),
                "directional_return_mean": float(returns.mean()),
                "hit_rate": float((returns > 0).mean()),
            }
        )
    return pd.DataFrame(rows)


def compare_flow_measures(
    events: pd.DataFrame,
    *,
    horizon_weeks: int = 8,
    lag_weeks: int = 2,
    quantiles: int = 4,
) -> pd.DataFrame:
    """Compare percentile, raw-contract and OI-normalized flow families."""
    lag = int(lag_weeks)
    measures = (
        f"pct_release_velocity_{lag}w",
        f"raw_release_velocity_{lag}w",
        f"net_oi_release_velocity_{lag}w",
        "pct_release_acceleration",
        "raw_release_acceleration",
        "net_oi_release_acceleration",
    )
    frames = []
    for feature in measures:
        study = quantile_effect_study(
            events, feature, horizon_weeks=horizon_weeks, quantiles=quantiles
        )
        if not study.empty:
            frames.append(study)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def research_question_coverage() -> pd.DataFrame:
    """Document which open questions V3.11A can answer already."""
    rows = [
        ("104W vs 156W vs 208W", "JA", "window_weeks + identische Forward-Metriken"),
        ("80/20 vs strengere Extreme", "JA", "threshold grid 70..95"),
        ("Extremtiefe 99 vs 81", "JA", "extreme_depth kontinuierlich / Quantile"),
        ("Extreme Duration", "JA", "duration_weeks"),
        ("Δ1W / Δ2W / Δ4W", "JA", "weeklyized release velocity"),
        ("Acceleration vs Velocity", "JA", "1W velocity minus 4W velocity"),
        ("Raw vs Net/OI", "JA", "beide Flow-Familien parallel"),
        ("Bestes Entry-Fenster", "TEILWEISE", "Release + Forward 1/2/4/8/12W; Early-Trigger folgt V3.11B"),
        ("Asset Manager / Leveraged Funds Mehrwert", "NEIN", "Cross-Group Event-Matching folgt V3.11B"),
        ("Kosten voller Cross-Group-Bestätigung", "NEIN", "Confirmation-Timestamps folgen V3.11B"),
        ("Too late / extended", "NEIN", "ATR/MFE-Maturity folgt V3.11B"),
    ]
    return pd.DataFrame(rows, columns=["research_question", "v311a", "measurement"])
