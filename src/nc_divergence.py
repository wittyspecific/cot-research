from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    NC_DIV_FLOW_WINDOW_W,
    NC_DIV_PATH_WINDOW_W,
    NC_DIV_PRICE_WINDOW_W,
    NC_DIV_STANDARDIZE_HIST_W,
    NC_DIV_USE_OI_NORM,
    NC_DIV_Z_THRESHOLD,
    NC_MIN_ACTIVE_BUILD_SHARE,
    NC_MIN_ACTIVE_LEG_GROSS_PCT,
)


def _finite_array(values) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    return arr[np.isfinite(arr)]


def robust_iqr_scale(values) -> float:
    """Robust scale comparable to standard deviation under a normal reference.

    The IQR is divided by 1.349. This is a methodological convention, not a
    fitted parameter. If the IQR collapses to zero, no robust z-score is emitted.
    """
    arr = _finite_array(values)
    if arr.size < 2:
        return np.nan
    q25, q75 = np.quantile(arr, [0.25, 0.75])
    scale = (q75 - q25) / 1.349
    if not np.isfinite(scale) or scale <= 0:
        return np.nan
    return float(scale)


def robust_z_from_prior_history(series: pd.Series, history_weeks: int) -> pd.Series:
    """Robust z-score against the previous N *valid reported* observations.

    The current observation never enters its own reference distribution. Missing
    values are not interpolated; they are skipped when assembling the historical
    reference sample. This avoids turning one missing COT week into 156 weeks of
    unavailable z-scores while still making the missing 4W/8W signal itself NaN.
    """
    s = pd.to_numeric(series, errors="coerce")
    values = s.to_numpy(dtype=float)
    result = pd.Series(np.nan, index=s.index, dtype=float)
    hist = int(history_weeks)
    prior_valid: list[float] = []

    for i, cur in enumerate(values):
        if np.isfinite(cur) and len(prior_valid) >= hist:
            window = np.asarray(prior_valid[-hist:], dtype=float)
            med = float(np.median(window))
            scale = robust_iqr_scale(window)
            if np.isfinite(scale) and scale > 0:
                result.iloc[i] = (cur - med) / scale
        if np.isfinite(cur):
            prior_valid.append(float(cur))

    return result


def historical_percentile_from_prior_history(
    series: pd.Series,
    history_weeks: int,
) -> pd.Series:
    """Percentile of current value against the previous N valid observations."""
    s = pd.to_numeric(series, errors="coerce")
    result = pd.Series(np.nan, index=s.index, dtype=float)
    hist = int(history_weeks)
    prior_valid: list[float] = []

    for i, cur in enumerate(s.to_numpy(dtype=float)):
        if np.isfinite(cur) and len(prior_valid) >= hist:
            previous = np.asarray(prior_valid[-hist:], dtype=float)
            result.iloc[i] = float(np.mean(previous <= cur) * 100.0)
        if np.isfinite(cur):
            prior_valid.append(float(cur))

    return result


def robust_z_from_prior_time_history(
    dates: pd.Series,
    series: pd.Series,
    history_weeks: int,
) -> pd.Series:
    """Robust z-score over the exact preceding calendar window.

    The window is [t-history_weeks, t). Current t is excluded. Missing reports
    inside the window are simply absent; nothing is interpolated. A value is
    emitted only once the available series actually reaches back at least the
    full requested number of calendar weeks.
    """
    d = pd.to_datetime(dates, errors="coerce")
    v = pd.to_numeric(series, errors="coerce")
    out = pd.Series(np.nan, index=v.index, dtype=float)
    valid_dates = d.dropna()
    if valid_dates.empty:
        return out
    first_date = valid_dates.min()

    for i, (dt, cur) in enumerate(zip(d, v)):
        if pd.isna(dt) or not np.isfinite(cur):
            continue
        start = pd.Timestamp(dt) - pd.Timedelta(weeks=int(history_weeks))
        if first_date > start:
            continue
        mask = (d >= start) & (d < pd.Timestamp(dt)) & v.notna()
        hist = v[mask].to_numpy(dtype=float)
        hist = hist[np.isfinite(hist)]
        if len(hist) < 4:
            continue
        scale = robust_iqr_scale(hist)
        if not np.isfinite(scale) or scale <= 0:
            continue
        out.iloc[i] = (float(cur) - float(np.median(hist))) / scale
    return out


def percentile_from_prior_time_history(
    dates: pd.Series,
    series: pd.Series,
    history_weeks: int,
) -> tuple[pd.Series, pd.Series]:
    """Percentile and reference-n against prior values in the exact time window."""
    d = pd.to_datetime(dates, errors="coerce")
    v = pd.to_numeric(series, errors="coerce")
    pct = pd.Series(np.nan, index=v.index, dtype=float)
    ref_n = pd.Series(0, index=v.index, dtype=int)
    valid_dates = d.dropna()
    if valid_dates.empty:
        return pct, ref_n
    first_date = valid_dates.min()

    for i, (dt, cur) in enumerate(zip(d, v)):
        if pd.isna(dt) or not np.isfinite(cur):
            continue
        start = pd.Timestamp(dt) - pd.Timedelta(weeks=int(history_weeks))
        if first_date > start:
            continue
        mask = (d >= start) & (d < pd.Timestamp(dt)) & v.notna()
        hist = v[mask].to_numpy(dtype=float)
        hist = hist[np.isfinite(hist)]
        ref_n.iloc[i] = int(len(hist))
        if len(hist) == 0:
            continue
        pct.iloc[i] = float(np.mean(hist <= float(cur)) * 100.0)
    return pct, ref_n


def exact_week_lag(
    dates: pd.Series,
    values: pd.Series,
    weeks: int,
) -> pd.Series:
    """Return the value exactly N calendar weeks earlier.

    This deliberately does not use positional ``shift``. If a COT report week is
    missing, the lagged value is NaN instead of silently stretching a 4W window
    into 5W or more.
    """
    d = pd.to_datetime(dates, errors="coerce")
    v = pd.to_numeric(values, errors="coerce")
    mapping = {
        pd.Timestamp(dt).normalize(): val
        for dt, val in zip(d, v)
        if pd.notna(dt) and np.isfinite(val)
    }
    targets = d - pd.Timedelta(weeks=int(weeks))
    return pd.Series(
        [mapping.get(pd.Timestamp(t).normalize(), np.nan) if pd.notna(t) else np.nan for t in targets],
        index=dates.index,
        dtype=float,
    )


def _spearman_rank_corr(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) != len(y) or len(x) < 3:
        return np.nan
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        return np.nan
    rx = pd.Series(x).rank(method="average").to_numpy(dtype=float)
    ry = pd.Series(y).rank(method="average").to_numpy(dtype=float)
    if np.nanstd(rx) == 0 or np.nanstd(ry) == 0:
        return np.nan
    return float(np.corrcoef(rx, ry)[0, 1])


def exact_path_spearman(
    dates: pd.Series,
    price: pd.Series,
    net_oi: pd.Series,
    window_weeks: int,
) -> pd.Series:
    """Spearman correlation over an exact weekly path of N weeks = N+1 points."""
    d = pd.to_datetime(dates, errors="coerce")
    p = pd.to_numeric(price, errors="coerce")
    n = pd.to_numeric(net_oi, errors="coerce")

    records = {
        pd.Timestamp(dt).normalize(): (pv, nv)
        for dt, pv, nv in zip(d, p, n)
        if pd.notna(dt) and np.isfinite(pv) and np.isfinite(nv)
    }

    out = []
    for dt in d:
        if pd.isna(dt):
            out.append(np.nan)
            continue
        end = pd.Timestamp(dt).normalize()
        points = []
        complete = True
        for lag in range(int(window_weeks), -1, -1):
            key = end - pd.Timedelta(weeks=lag)
            pair = records.get(key)
            if pair is None:
                complete = False
                break
            points.append(pair)
        if not complete:
            out.append(np.nan)
            continue
        arr = np.asarray(points, dtype=float)
        out.append(_spearman_rank_corr(arr[:, 0], arr[:, 1]))

    return pd.Series(out, index=dates.index, dtype=float)


def classify_positioning_legs(
    frame: pd.DataFrame,
    long_col: str,
    short_col: str,
    lookback_weeks: int = 4,
    min_active_leg_weeks: int = 2,
    min_active_leg_pct: float = NC_MIN_ACTIVE_LEG_GROSS_PCT,
    active_leg_share: float = NC_MIN_ACTIVE_BUILD_SHARE,
) -> dict:
    """Legacy long/short-leg decomposition, kept separate from divergence.

    The original thresholds and labels are retained. The classification now uses
    the sign of the 4W net flow as its context instead of requiring the legacy
    price-divergence flag first. Missing report weeks invalidate the 4W leg path.
    """
    required = ["report_date", long_col, short_col]
    x = frame.dropna(subset=required).copy().sort_values("report_date").reset_index(drop=True)
    if x.empty:
        return {
            "flow_type": "NO LEG DATA",
            "long_change_pct": np.nan,
            "short_change_pct": np.nan,
            "active_share": np.nan,
        }

    cur_date = pd.Timestamp(x.iloc[-1]["report_date"]).normalize()
    path_dates = [cur_date - pd.Timedelta(weeks=i) for i in range(int(lookback_weeks), -1, -1)]
    by_date = {
        pd.Timestamp(row["report_date"]).normalize(): row
        for _, row in x.iterrows()
    }
    if any(dt not in by_date for dt in path_dates):
        return {
            "flow_type": "MISSING COT WEEK",
            "long_change_pct": np.nan,
            "short_change_pct": np.nan,
            "active_share": np.nan,
        }

    path = pd.DataFrame([by_date[dt] for dt in path_dates])
    prior = path.iloc[0]
    cur = path.iloc[-1]

    long_prior = float(prior[long_col])
    short_prior = float(prior[short_col])
    long_current = float(cur[long_col])
    short_current = float(cur[short_col])
    gross_prior = abs(long_prior) + abs(short_prior)
    if not np.isfinite(gross_prior) or gross_prior == 0:
        return {
            "flow_type": "INVALID BASE",
            "long_change_pct": np.nan,
            "short_change_pct": np.nan,
            "active_share": np.nan,
        }

    long_delta_pct = (long_current - long_prior) / gross_prior * 100.0
    short_delta_pct = (short_current - short_prior) / gross_prior * 100.0
    net_delta_pct = long_delta_pct - short_delta_pct

    long_diff = pd.to_numeric(path[long_col], errors="coerce").diff().dropna()
    short_diff = pd.to_numeric(path[short_col], errors="coerce").diff().dropna()
    long_up_weeks = int((long_diff > 0).sum())
    long_down_weeks = int((long_diff < 0).sum())
    short_up_weeks = int((short_diff > 0).sum())
    short_down_weeks = int((short_diff < 0).sum())

    bullish_pressure = max(long_delta_pct, 0.0) + max(-short_delta_pct, 0.0)
    bearish_pressure = max(-long_delta_pct, 0.0) + max(short_delta_pct, 0.0)
    active_long_share = max(long_delta_pct, 0.0) / bullish_pressure if bullish_pressure > 0 else 0.0
    active_short_share = max(short_delta_pct, 0.0) / bearish_pressure if bearish_pressure > 0 else 0.0

    if net_delta_pct > 0:
        if (
            long_delta_pct >= min_active_leg_pct
            and active_long_share >= active_leg_share
            and long_up_weeks >= min_active_leg_weeks
        ):
            flow_type = "BULLISH · ACTIVE LONG BUILD"
            share = active_long_share
        elif short_delta_pct < 0.0 and short_down_weeks >= min_active_leg_weeks:
            flow_type = "BULLISH · SHORT COVERING"
            share = 1.0 - active_long_share
        else:
            flow_type = "BULLISH · NET BUILD"
            share = np.nan
    elif net_delta_pct < 0:
        if (
            short_delta_pct >= min_active_leg_pct
            and active_short_share >= active_leg_share
            and short_up_weeks >= min_active_leg_weeks
        ):
            flow_type = "BEARISH · ACTIVE SHORT BUILD"
            share = active_short_share
        elif short_delta_pct > 0.0 and short_up_weeks >= min_active_leg_weeks:
            flow_type = "BEARISH · MIXED DISTRIBUTION"
            share = active_short_share
        elif long_delta_pct < 0.0 and long_down_weeks >= min_active_leg_weeks:
            flow_type = "LONG LIQUIDATION / PROFIT TAKING"
            share = np.nan
        else:
            flow_type = "BEARISH · NET REDUCTION"
            share = np.nan
    else:
        flow_type = "MIXED / LOW ACTIVITY"
        share = np.nan

    return {
        "flow_type": flow_type,
        "long_change_pct": float(long_delta_pct),
        "short_change_pct": float(short_delta_pct),
        "active_share": float(share) if np.isfinite(share) else np.nan,
        "long_up_weeks": long_up_weeks,
        "long_down_weeks": long_down_weeks,
        "short_up_weeks": short_up_weeks,
        "short_down_weeks": short_down_weeks,
    }


def build_divergence_history(
    cot_with_prices: pd.DataFrame,
    long_col: str,
    short_col: str,
    oi_col: str = "open_interest_all",
    price_col: str = "cot_price",
    report_date_col: str = "report_date",
    price_window_weeks: int = NC_DIV_PRICE_WINDOW_W,
    flow_window_weeks: int = NC_DIV_FLOW_WINDOW_W,
    path_window_weeks: int = NC_DIV_PATH_WINDOW_W,
    history_weeks: int = NC_DIV_STANDARDIZE_HIST_W,
    z_threshold: float = NC_DIV_Z_THRESHOLD,
    use_oi_norm: bool = NC_DIV_USE_OI_NORM,
) -> pd.DataFrame:
    """Build the no-look-ahead divergence time series.

    4W price/flow changes use exact report-date lags. Missing COT weeks therefore
    become NaN rather than being interpolated or replaced by the fourth previous
    row. The robust reference distribution uses the exact preceding 156-calendar-
    week window and explicitly excludes t.
    """
    required = [report_date_col, price_col, long_col, short_col]
    if use_oi_norm:
        required.append(oi_col)
    missing = [c for c in required if c not in cot_with_prices.columns]
    if missing:
        raise KeyError(f"Divergenz-Spalten fehlen: {missing}")

    out = cot_with_prices.copy().sort_values(report_date_col).reset_index(drop=True)
    out[report_date_col] = pd.to_datetime(out[report_date_col], errors="coerce")
    out[price_col] = pd.to_numeric(out[price_col], errors="coerce")
    out[long_col] = pd.to_numeric(out[long_col], errors="coerce")
    out[short_col] = pd.to_numeric(out[short_col], errors="coerce")

    out["spec_net"] = out[long_col] - out[short_col]
    if use_oi_norm:
        oi = pd.to_numeric(out[oi_col], errors="coerce").replace(0, np.nan)
        out["spec_net_oi"] = out["spec_net"] / oi
    else:
        out["spec_net_oi"] = out["spec_net"]

    price_prior = exact_week_lag(
        out[report_date_col], out[price_col], int(price_window_weeks)
    )
    valid_price = (out[price_col] > 0) & (price_prior > 0)
    out["r_4w"] = np.where(
        valid_price,
        np.log(out[price_col] / price_prior),
        np.nan,
    )

    raw_flow_prior = exact_week_lag(
        out[report_date_col], out["spec_net"], int(flow_window_weeks)
    )
    out["d_flow_raw_4w"] = out["spec_net"] - raw_flow_prior

    flow_prior = exact_week_lag(
        out[report_date_col], out["spec_net_oi"], int(flow_window_weeks)
    )
    out["d_flow_4w"] = out["spec_net_oi"] - flow_prior

    out["z_price"] = robust_z_from_prior_time_history(
        out[report_date_col], out["r_4w"], int(history_weeks)
    )
    out["z_flow"] = robust_z_from_prior_time_history(
        out[report_date_col], out["d_flow_4w"], int(history_weeks)
    )
    out["rho"] = exact_path_spearman(
        out[report_date_col],
        out[price_col],
        out["spec_net_oi"],
        int(path_window_weeks),
    )

    # Strength is attached to an actual divergence flag, not turned into a
    # general-purpose weekly score. The percentile is therefore compared only
    # with prior divergence strengths in the same 156W calendar window.
    thr = float(z_threshold)
    out["bullish_divergence"] = (
        (out["z_price"] <= -thr)
        & (out["z_flow"] >= thr)
        & (out["rho"] < 0)
    )
    out["bearish_divergence"] = (
        (out["z_price"] >= thr)
        & (out["z_flow"] <= -thr)
        & (out["rho"] < 0)
    )
    out["direction"] = np.select(
        [out["bullish_divergence"], out["bearish_divergence"]],
        [1, -1],
        default=0,
    ).astype(int)
    out["status"] = np.select(
        [out["bullish_divergence"], out["bearish_divergence"]],
        ["BULLISH DIVERGENCE", "BEARISH DIVERGENCE"],
        default="NO DIVERGENCE",
    )

    insufficient = out[["z_price", "z_flow", "rho"]].isna().any(axis=1)
    out.loc[insufficient, "direction"] = 0
    out.loc[insufficient, "status"] = "NOT ENOUGH DATA"

    out["divergence_strength"] = np.where(
        out["direction"] != 0,
        np.minimum(out["z_price"].abs(), out["z_flow"].abs()) * out["rho"].abs(),
        np.nan,
    )
    (
        out["divergence_strength_percentile"],
        out["divergence_strength_reference_n"],
    ) = percentile_from_prior_time_history(
        out[report_date_col],
        out["divergence_strength"],
        int(history_weeks),
    )

    if "cot_price_alignment_ok" in out.columns:
        bad_alignment = ~out["cot_price_alignment_ok"].fillna(False)
        out.loc[bad_alignment, [
            "r_4w", "z_price", "rho", "divergence_strength",
            "divergence_strength_percentile",
        ]] = np.nan
        out.loc[bad_alignment, "direction"] = 0
        out.loc[bad_alignment, "status"] = "PRICE ALIGNMENT INVALID"

    return out


def _flow_label(z_flow: float, d_flow: float, threshold: float) -> str:
    if not np.isfinite(d_flow):
        return "NO FLOW DATA"
    if np.isfinite(z_flow):
        if z_flow >= threshold:
            return "STRONGLY BULLISH FLOW"
        if z_flow <= -threshold:
            return "STRONGLY BEARISH FLOW"
    if d_flow > 0:
        return "BULLISH FLOW"
    if d_flow < 0:
        return "BEARISH FLOW"
    return "NEUTRAL FLOW"


def current_divergence(
    cot_with_prices: pd.DataFrame,
    long_col: str,
    short_col: str,
    group_label: str,
    **kwargs,
) -> dict:
    hist = build_divergence_history(
        cot_with_prices,
        long_col=long_col,
        short_col=short_col,
        **kwargs,
    )
    if hist.empty:
        return {
            "status": "NOT ENOUGH DATA",
            "direction": 0,
            "group_label": group_label,
            "flow_label": "NO FLOW DATA",
        }

    row = hist.iloc[-1]
    legs = classify_positioning_legs(
        cot_with_prices,
        long_col=long_col,
        short_col=short_col,
        lookback_weeks=int(kwargs.get("flow_window_weeks", NC_DIV_FLOW_WINDOW_W)),
    )
    return {
        "status": str(row.get("status", "NO DIVERGENCE")),
        "direction": int(row.get("direction", 0) or 0),
        "group_label": group_label,
        "flow_label": _flow_label(
            float(row.get("z_flow", np.nan)),
            float(row.get("d_flow_4w", np.nan)),
            float(kwargs.get("z_threshold", NC_DIV_Z_THRESHOLD)),
        ),
        "r_4w": float(row.get("r_4w", np.nan)),
        "d_flow_raw_4w": float(row.get("d_flow_raw_4w", np.nan)),
        "d_flow_4w": float(row.get("d_flow_4w", np.nan)),
        "z_price": float(row.get("z_price", np.nan)),
        "z_flow": float(row.get("z_flow", np.nan)),
        "rho": float(row.get("rho", np.nan)),
        "divergence_strength": float(row.get("divergence_strength", np.nan)),
        "divergence_strength_percentile": float(row.get("divergence_strength_percentile", np.nan)),
        "divergence_strength_reference_n": int(row.get("divergence_strength_reference_n", 0) or 0),
        "net_oi": float(row.get("spec_net_oi", np.nan)),
        "net_raw": float(row.get("spec_net", np.nan)),
        **legs,
    }


def historical_divergence_events(
    cot_with_prices: pd.DataFrame,
    long_col: str,
    short_col: str,
    group_label: str,
    **kwargs,
) -> pd.DataFrame:
    hist = build_divergence_history(
        cot_with_prices,
        long_col=long_col,
        short_col=short_col,
        **kwargs,
    )
    if hist.empty:
        return pd.DataFrame()

    events = hist[hist["direction"] != 0].copy()
    if events.empty:
        return pd.DataFrame()

    events["new_episode"] = (
        (events["direction"] != events["direction"].shift(1))
        | (events["report_date"].diff().dt.days > 8)
    )
    events = events[events["new_episode"]].copy()
    events["group_label"] = group_label
    return events[[
        "report_date", "group_label", "status", "direction", "r_4w",
        "d_flow_4w", "z_price", "z_flow", "rho", "divergence_strength",
        "divergence_strength_percentile", "divergence_strength_reference_n",
    ]].rename(columns={"report_date": "event_date"}).reset_index(drop=True)


def _pearson(a: pd.Series, b: pd.Series) -> float:
    x = pd.to_numeric(a, errors="coerce")
    y = pd.to_numeric(b, errors="coerce")
    valid = x.notna() & y.notna()
    if valid.sum() < 3:
        return np.nan
    xv = x[valid].to_numpy(dtype=float)
    yv = y[valid].to_numpy(dtype=float)
    if np.std(xv) == 0 or np.std(yv) == 0:
        return np.nan
    return float(np.corrcoef(xv, yv)[0, 1])


def _linear_residual(y: pd.Series, x: pd.Series) -> tuple[pd.Series, float, float]:
    yy = pd.to_numeric(y, errors="coerce")
    xx = pd.to_numeric(x, errors="coerce")
    valid = yy.notna() & xx.notna()
    residual = pd.Series(np.nan, index=yy.index, dtype=float)
    if valid.sum() < 3:
        return residual, np.nan, np.nan
    X = np.column_stack([np.ones(valid.sum()), xx[valid].to_numpy(dtype=float)])
    yv = yy[valid].to_numpy(dtype=float)
    beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
    fitted = X @ beta
    resid = yv - fitted
    residual.loc[valid] = resid
    total_var = float(np.var(yv, ddof=1)) if len(yv) > 1 else np.nan
    resid_var = float(np.var(resid, ddof=1)) if len(resid) > 1 else np.nan
    if not np.isfinite(total_var) or total_var <= 0:
        return residual, np.nan, np.nan
    explained = max(0.0, min(1.0, 1.0 - resid_var / total_var))
    residual_share = max(0.0, min(1.0, resid_var / total_var))
    return residual, explained, residual_share


def redundancy_metrics(
    frame: pd.DataFrame,
    hedger_key: str,
    speculative_key: str,
    nonreportable_key: str = "nonreportable",
    flow_weeks: int = 4,
) -> dict:
    """Mechanical-overlap diagnostics for one report data source."""
    x = frame.copy().sort_values("report_date").reset_index(drop=True)
    oi = pd.to_numeric(x["open_interest_all"], errors="coerce").replace(0, np.nan)

    def net(key: str) -> pd.Series:
        return pd.to_numeric(x[f"{key}_long"], errors="coerce") - pd.to_numeric(x[f"{key}_short"], errors="coerce")

    h_net = net(hedger_key)
    s_net = net(speculative_key)
    nr_net = net(nonreportable_key) if f"{nonreportable_key}_long" in x.columns else pd.Series(np.nan, index=x.index)

    h_lag = exact_week_lag(x["report_date"], h_net, flow_weeks)
    s_lag = exact_week_lag(x["report_date"], s_net, flow_weeks)
    nr_lag = exact_week_lag(x["report_date"], nr_net, flow_weeks)
    h_d = h_net - h_lag
    s_d = s_net - s_lag
    nr_d = nr_net - nr_lag

    h_oi = h_net / oi
    s_oi = s_net / oi
    h_oi_lag = exact_week_lag(x["report_date"], h_oi, flow_weeks)
    s_oi_lag = exact_week_lag(x["report_date"], s_oi, flow_weeks)
    h_d_oi = h_oi - h_oi_lag
    s_d_oi = s_oi - s_oi_lag

    residual, explained, residual_share = _linear_residual(s_d, h_d)
    pair_difference = s_d + h_d
    nr_corr = _pearson(pair_difference, -nr_d)
    nr_difference_r2 = nr_corr ** 2 if np.isfinite(nr_corr) else np.nan

    raw_corr = _pearson(h_d, s_d)
    oi_corr = _pearson(h_d_oi, s_d_oi)

    if np.isfinite(raw_corr) and abs(raw_corr) > 0.85:
        interpretation = "WEITGEHEND REDUNDANT"
    elif np.isfinite(raw_corr) and abs(raw_corr) < 0.60:
        interpretation = "ZUSÄTZLICHER INFORMATIONSANTEIL PLAUSIBEL"
    else:
        interpretation = "TEILWEISE GEKOPPELT"

    return {
        "pearson_raw": raw_corr,
        "pearson_oi": oi_corr,
        "explained_variance": explained,
        "residual_variance": residual_share,
        "nonreportable_difference_r2": nr_difference_r2,
        "n": int((h_d.notna() & s_d.notna()).sum()),
        "interpretation": interpretation,
    }


def compare_legacy_and_new_events(
    legacy_events: pd.DataFrame,
    new_events: pd.DataFrame,
) -> dict:
    """Structural comparison only; deliberately no forward-return evaluation."""
    old_dates = set(pd.to_datetime(legacy_events.get("event_date", pd.Series(dtype="datetime64[ns]"))).dt.normalize())
    new_dates = set(pd.to_datetime(new_events.get("event_date", pd.Series(dtype="datetime64[ns]"))).dt.normalize())
    union = old_dates | new_dates
    overlap = old_dates & new_dates
    return {
        "legacy_signals": len(old_dates),
        "new_signals": len(new_dates),
        "overlap_weeks": len(overlap),
        "overlap_share_union": (len(overlap) / len(union)) if union else np.nan,
        "overlap_share_legacy": (len(overlap) / len(old_dates)) if old_dates else np.nan,
        "overlap_share_new": (len(overlap) / len(new_dates)) if new_dates else np.nan,
    }


def yearly_signal_counts(
    legacy_events: pd.DataFrame,
    new_events: pd.DataFrame,
) -> pd.DataFrame:
    frames = []
    for label, events in (("Legacy", legacy_events), ("Neu", new_events)):
        if events is None or events.empty or "event_date" not in events.columns:
            continue
        x = events.copy()
        x["Jahr"] = pd.to_datetime(x["event_date"]).dt.year
        counts = x.groupby("Jahr").size().rename(label)
        frames.append(counts)
    if not frames:
        return pd.DataFrame(columns=["Jahr", "Legacy", "Neu"])
    out = pd.concat(frames, axis=1).fillna(0).astype(int).reset_index()
    return out.sort_values("Jahr")
