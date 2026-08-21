from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_GRID = 252
DEFAULT_HORIZONS = (5, 10, 20, 40, 60)
DEFAULT_WINDOWS = (10, 15, 20, 30)


def _clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if prices is None or prices.empty or "close" not in prices.columns:
        return pd.DataFrame()

    out = prices[["close"]].copy()
    out.index = pd.to_datetime(out.index)
    if getattr(out.index, "tz", None) is not None:
        out.index = out.index.tz_localize(None)

    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna().sort_index()
    out = out[~out.index.duplicated(keep="last")]
    out["year"] = out.index.year
    return out


def _completed_years(prices: pd.DataFrame, years: int) -> list[int]:
    p = _clean_prices(prices)
    if p.empty:
        return []

    current_year = int(p.index.max().year)
    available = sorted(
        int(year)
        for year in p["year"].unique()
        if int(year) < current_year
    )
    return available[-int(years):]


def _year_path(
    year_prices: pd.Series,
    grid_size: int = DEFAULT_GRID,
) -> np.ndarray:
    s = pd.to_numeric(year_prices, errors="coerce").dropna()
    if len(s) < 40:
        return np.asarray([], dtype=float)

    values = s.to_numpy(dtype=float)
    if not np.isfinite(values[0]) or values[0] <= 0:
        return np.asarray([], dtype=float)

    log_path = np.log(values / values[0]) * 100.0
    x_old = np.linspace(0.0, 1.0, len(log_path))
    x_new = np.linspace(0.0, 1.0, int(grid_size))
    return np.interp(x_new, x_old, log_path)


def seasonal_template(
    prices: pd.DataFrame,
    *,
    years: int = 20,
    grid_size: int = DEFAULT_GRID,
) -> pd.DataFrame:
    """Median full-year seasonal path across completed years.

    Each completed year is normalized to a common 252-point phase grid.
    The median is used as the central tendency; q25/q75 expose dispersion.
    """
    p = _clean_prices(prices)
    if p.empty:
        return pd.DataFrame()

    paths = []
    used_years = []

    for year in _completed_years(p, years):
        path = _year_path(
            p.loc[p["year"].eq(year), "close"],
            grid_size=grid_size,
        )
        if len(path) != int(grid_size):
            continue
        paths.append(path)
        used_years.append(year)

    if len(paths) < 5:
        return pd.DataFrame()

    matrix = np.vstack(paths)
    return pd.DataFrame(
        {
            "phase_day": np.arange(int(grid_size), dtype=int),
            "median_pct": np.nanmedian(matrix, axis=0),
            "q25_pct": np.nanquantile(matrix, 0.25, axis=0),
            "q75_pct": np.nanquantile(matrix, 0.75, axis=0),
            "sample_size": len(paths),
            "history_years": len(paths),
            "first_year": min(used_years),
            "last_year": max(used_years),
        }
    )


def current_phase_day(
    prices: pd.DataFrame,
    grid_size: int = DEFAULT_GRID,
) -> int | None:
    p = _clean_prices(prices)
    if p.empty:
        return None

    current_year = int(p.index.max().year)
    current = p[p["year"].eq(current_year)]
    if current.empty:
        return None

    idx = len(current) - 1
    return int(np.clip(idx, 0, int(grid_size) - 1))


def _smooth(values: np.ndarray, span: int = 5) -> np.ndarray:
    s = pd.Series(values, dtype=float)
    min_periods = max(2, int(span) // 2)
    return (
        s.rolling(
            int(span),
            center=True,
            min_periods=min_periods,
        )
        .median()
        .interpolate(limit_direction="both")
        .to_numpy(dtype=float)
    )


def seasonal_turns(
    template: pd.DataFrame,
    *,
    smooth_span: int = 5,
    min_separation: int = 8,
) -> pd.DataFrame:
    if template is None or template.empty:
        return pd.DataFrame()

    y = pd.to_numeric(
        template["median_pct"],
        errors="coerce",
    ).to_numpy(dtype=float)

    if len(y) < 20:
        return pd.DataFrame()

    ys = _smooth(y, smooth_span)
    d = np.diff(ys)

    raw = []
    for i in range(1, len(d)):
        left = d[i - 1]
        right = d[i]
        if not np.isfinite(left) or not np.isfinite(right):
            continue

        if left < 0 <= right:
            kind = "BOTTOM"
        elif left > 0 >= right:
            kind = "TOP"
        else:
            continue

        idx = int(i)
        lo = max(0, idx - 10)
        hi = min(len(ys), idx + 11)
        local = ys[lo:hi]

        if kind == "BOTTOM":
            swing = float(np.nanmax(local) - ys[idx])
        else:
            swing = float(ys[idx] - np.nanmin(local))

        raw.append(
            {
                "phase_day": idx,
                "turn_type": kind,
                "seasonal_level_pct": float(ys[idx]),
                "local_swing_pct": swing,
            }
        )

    if not raw:
        return pd.DataFrame()

    # Collapse clusters of same-type turns; keep the stronger local swing.
    kept = []
    for row in raw:
        if (
            kept
            and row["turn_type"] == kept[-1]["turn_type"]
            and row["phase_day"] - kept[-1]["phase_day"] < int(min_separation)
        ):
            if row["local_swing_pct"] > kept[-1]["local_swing_pct"]:
                kept[-1] = row
        else:
            kept.append(row)

    return pd.DataFrame(kept)


def nearest_turn_context(
    template: pd.DataFrame,
    phase_day: int | None,
    *,
    search_back: int = 20,
    search_forward: int = 40,
) -> dict:
    empty = {
        "turn_type": "N/V",
        "turn_phase_day": None,
        "distance_days": None,
        "local_swing_pct": np.nan,
        "window_state": "N/V",
    }
    if phase_day is None:
        return empty

    turns = seasonal_turns(template)
    if turns.empty:
        return empty

    work = turns.copy()
    work["distance_days"] = work["phase_day"].astype(int) - int(phase_day)
    work = work[
        work["distance_days"].between(
            -int(search_back),
            int(search_forward),
        )
    ].copy()

    if work.empty:
        return empty

    # Prefer closest turn; if tied, prefer the larger local swing.
    work["abs_distance"] = work["distance_days"].abs()
    work = work.sort_values(
        ["abs_distance", "local_swing_pct"],
        ascending=[True, False],
    )
    row = work.iloc[0]

    dist = int(row["distance_days"])
    if abs(dist) <= 5:
        state = "ACTIVE TURN WINDOW"
    elif dist > 5:
        state = "APPROACHING TURN"
    else:
        state = "POST-TURN"

    return {
        "turn_type": str(row["turn_type"]),
        "turn_phase_day": int(row["phase_day"]),
        "distance_days": dist,
        "local_swing_pct": float(row["local_swing_pct"]),
        "window_state": state,
    }


def seasonal_dynamics(
    template: pd.DataFrame,
    phase_day: int | None,
) -> dict:
    out = {
        "slope_5d": np.nan,
        "slope_10d": np.nan,
        "acceleration": np.nan,
        "direction": "N/V",
    }
    if template is None or template.empty or phase_day is None:
        return out

    y = pd.to_numeric(
        template["median_pct"],
        errors="coerce",
    ).to_numpy(dtype=float)
    i = int(np.clip(phase_day, 0, len(y) - 1))

    def slope(span: int, end: int) -> float:
        start = end - int(span)
        if start < 0:
            return np.nan
        a, b = y[start], y[end]
        if not np.isfinite(a) or not np.isfinite(b):
            return np.nan
        return float((b - a) / float(span))

    s5 = slope(5, i)
    s10 = slope(10, i)
    prev5 = slope(5, i - 5) if i >= 10 else np.nan
    accel = (
        float(s5 - prev5)
        if np.isfinite(s5) and np.isfinite(prev5)
        else np.nan
    )

    if np.isfinite(s10):
        if s10 > 0.02:
            direction = "RISING"
        elif s10 < -0.02:
            direction = "FALLING"
        else:
            direction = "FLAT"
    else:
        direction = "N/V"

    return {
        "slope_5d": s5,
        "slope_10d": s10,
        "acceleration": accel,
        "direction": direction,
    }


def _historical_anchor_positions(
    prices: pd.DataFrame,
    years: int,
) -> list[tuple[int, int]]:
    p = _clean_prices(prices)
    if p.empty:
        return []

    current_year = int(p.index.max().year)
    current = p[p["year"].eq(current_year)]
    if current.empty:
        return []

    anchor_idx = int(len(current) - 1)
    positions = []

    for year in _completed_years(p, years):
        frame = p[p["year"].eq(year)]
        if len(frame) <= anchor_idx:
            continue
        anchor_date = frame.index[anchor_idx]
        pos = int(p.index.get_indexer([anchor_date])[0])
        if pos >= 0:
            positions.append((year, pos))

    return positions


def _baseline_return_stats(
    prices: pd.DataFrame,
    horizon: int,
) -> dict:
    p = _clean_prices(prices)
    if p.empty or len(p) <= int(horizon):
        return {
            "hit_rate": np.nan,
            "median_return": np.nan,
            "n": 0,
        }

    close = p["close"].to_numpy(dtype=float)
    h = int(horizon)
    base = close[:-h]
    future = close[h:]
    valid = (
        np.isfinite(base)
        & np.isfinite(future)
        & (base > 0)
    )
    arr = future[valid] / base[valid] - 1.0
    arr = arr[np.isfinite(arr)]

    if len(arr) == 0:
        return {
            "hit_rate": np.nan,
            "median_return": np.nan,
            "n": 0,
        }

    return {
        "hit_rate": float(np.mean(arr > 0)),
        "median_return": float(np.median(arr)),
        "n": int(len(arr)),
    }


def offset_forward_surface(
    prices: pd.DataFrame,
    *,
    years: int = 20,
    offsets=tuple(range(-20, 21, 5)),
    horizons=DEFAULT_HORIZONS,
) -> pd.DataFrame:
    """Forward returns when entering before/after the current seasonal phase.

    This is the key turn-window study: a useful seasonal effect should normally
    survive a small timing perturbation instead of existing on one exact day.
    """
    p = _clean_prices(prices)
    if p.empty:
        return pd.DataFrame()

    anchors = _historical_anchor_positions(p, years)
    if len(anchors) < 5:
        return pd.DataFrame()

    close = p["close"].to_numpy(dtype=float)
    baseline = {
        int(h): _baseline_return_stats(p, int(h))
        for h in horizons
    }

    rows = []
    for offset in offsets:
        for horizon in horizons:
            h = int(horizon)
            returns = []

            for _, anchor in anchors:
                start = int(anchor) + int(offset)
                target = start + h
                if start < 0 or target >= len(close):
                    continue

                p0 = float(close[start])
                p1 = float(close[target])
                if (
                    p0 > 0
                    and np.isfinite(p0)
                    and np.isfinite(p1)
                ):
                    returns.append(p1 / p0 - 1.0)

            arr = np.asarray(returns, dtype=float)
            arr = arr[np.isfinite(arr)]
            base = baseline[h]

            if len(arr) == 0:
                continue

            hit = float(np.mean(arr > 0))
            med = float(np.median(arr))
            rows.append(
                {
                    "offset_days": int(offset),
                    "horizon_days": h,
                    "sample_size": int(len(arr)),
                    "positive_rate": hit,
                    "median_return": med,
                    "q25_return": float(np.quantile(arr, 0.25)),
                    "q75_return": float(np.quantile(arr, 0.75)),
                    "base_positive_rate": base["hit_rate"],
                    "base_median_return": base["median_return"],
                    "hit_rate_edge_pp": (
                        (hit - base["hit_rate"]) * 100.0
                        if np.isfinite(base["hit_rate"])
                        else np.nan
                    ),
                    "median_edge": (
                        med - base["median_return"]
                        if np.isfinite(base["median_return"])
                        else np.nan
                    ),
                }
            )

    return pd.DataFrame(rows)


def phase_shift_match(
    prices: pd.DataFrame,
    *,
    years: int = 20,
    lookbacks=(10, 20, 40),
    max_shift: int = 30,
    grid_size: int = DEFAULT_GRID,
) -> pd.DataFrame:
    """Compare the recent realized path with nearby positions on the template.

    No composite score is produced. Each lookback reports its own best shift,
    correlation and standardized shape error.
    """
    p = _clean_prices(prices)
    template = seasonal_template(
        p,
        years=years,
        grid_size=grid_size,
    )
    phase = current_phase_day(p, grid_size=grid_size)

    if template.empty or phase is None:
        return pd.DataFrame()

    current_year = int(p.index.max().year)
    current = p.loc[p["year"].eq(current_year), "close"].dropna()
    template_y = template["median_pct"].to_numpy(dtype=float)

    rows = []
    for lookback in lookbacks:
        lb = int(lookback)
        if len(current) < lb + 1:
            continue

        recent = current.iloc[-(lb + 1):].to_numpy(dtype=float)
        if np.any(~np.isfinite(recent)) or recent[0] <= 0:
            continue

        realized = np.log(recent / recent[0]) * 100.0

        candidates = []
        for shift in range(-int(max_shift), int(max_shift) + 1):
            end = int(phase) + int(shift)
            start = end - lb
            if start < 0 or end >= len(template_y):
                continue

            candidate = template_y[start:end + 1].copy()
            candidate = candidate - candidate[0]

            if np.std(realized) <= 1e-12 or np.std(candidate) <= 1e-12:
                corr = np.nan
            else:
                corr = float(np.corrcoef(realized, candidate)[0, 1])

            rz = (
                (realized - np.mean(realized)) / np.std(realized)
                if np.std(realized) > 1e-12
                else np.zeros_like(realized)
            )
            cz = (
                (candidate - np.mean(candidate)) / np.std(candidate)
                if np.std(candidate) > 1e-12
                else np.zeros_like(candidate)
            )
            rmse = float(np.sqrt(np.mean((rz - cz) ** 2)))

            candidates.append(
                {
                    "lookback_days": lb,
                    "phase_shift_days": int(shift),
                    "correlation": corr,
                    "shape_rmse": rmse,
                }
            )

        if not candidates:
            continue

        c = pd.DataFrame(candidates)
        c["_corr_sort"] = c["correlation"].fillna(-2.0)
        best = c.sort_values(
            ["_corr_sort", "shape_rmse"],
            ascending=[False, True],
        ).iloc[0]

        rows.append(
            {
                "lookback_days": lb,
                "phase_shift_days": int(best["phase_shift_days"]),
                "correlation": float(best["correlation"]),
                "shape_rmse": float(best["shape_rmse"]),
            }
        )

    return pd.DataFrame(rows)


def phase_shift_consensus(matches: pd.DataFrame) -> dict:
    out = {
        "consensus_shift_days": None,
        "agreement": "N/V",
        "usable_windows": 0,
    }
    if matches is None or matches.empty:
        return out

    work = matches[
        pd.to_numeric(
            matches["correlation"],
            errors="coerce",
        ).ge(0.30)
    ].copy()

    if work.empty:
        return out

    shifts = work["phase_shift_days"].astype(int).to_numpy()
    median_shift = int(round(float(np.median(shifts))))
    spread = int(np.max(shifts) - np.min(shifts)) if len(shifts) > 1 else 0

    if len(shifts) >= 2 and spread <= 10:
        agreement = "CONSISTENT"
    elif len(shifts) >= 2:
        agreement = "MIXED"
    else:
        agreement = "ONE WINDOW"

    return {
        "consensus_shift_days": median_shift,
        "agreement": agreement,
        "usable_windows": int(len(shifts)),
    }


def stability_table(
    prices: pd.DataFrame,
    *,
    history_windows=DEFAULT_WINDOWS,
    horizons=(10, 20, 40, 60),
) -> pd.DataFrame:
    rows = []
    for years in history_windows:
        surface = offset_forward_surface(
            prices,
            years=int(years),
            offsets=(0,),
            horizons=horizons,
        )
        if surface.empty:
            continue

        for _, row in surface.iterrows():
            med = float(row["median_return"])
            hit_edge = float(row["hit_rate_edge_pp"])
            if (
                np.isfinite(med)
                and np.isfinite(hit_edge)
                and med > 0
                and hit_edge > 0
            ):
                direction = "BULLISH"
            elif (
                np.isfinite(med)
                and np.isfinite(hit_edge)
                and med < 0
                and hit_edge < 0
            ):
                direction = "BEARISH"
            else:
                direction = "MIXED"

            rows.append(
                {
                    "history_years": int(years),
                    "horizon_days": int(row["horizon_days"]),
                    "sample_size": int(row["sample_size"]),
                    "direction": direction,
                    "positive_rate": float(row["positive_rate"]),
                    "base_positive_rate": float(row["base_positive_rate"]),
                    "hit_rate_edge_pp": hit_edge,
                    "median_return": med,
                    "base_median_return": float(row["base_median_return"]),
                    "median_edge": float(row["median_edge"]),
                }
            )

    return pd.DataFrame(rows)


def positioning_flow_context(
    enriched: pd.DataFrame,
    report_type: str,
) -> dict:
    if enriched is None or enriched.empty:
        return {"available": False}

    primary = "producer" if report_type == "disaggregated" else "dealer"
    if len(enriched) < 5:
        return {"available": False, "primary_key": primary}

    latest = enriched.iloc[-1]

    out = {
        "available": True,
        "primary_key": primary,
        "primary_label": (
            "Producer / Merchant"
            if report_type == "disaggregated"
            else "Dealer / Intermediary"
        ),
        "directional_interpretation": report_type == "disaggregated",
        "report_date": latest.get("report_date"),
        "net_oi_percentile": latest.get(
            f"{primary}_net_oi_percentile",
            np.nan,
        ),
    }

    for weeks in (1, 2, 4):
        prior = enriched.iloc[-1 - weeks]
        out[f"net_delta_{weeks}w"] = (
            float(latest.get(f"{primary}_net", np.nan))
            - float(prior.get(f"{primary}_net", np.nan))
        )
        out[f"net_oi_delta_{weeks}w"] = (
            float(latest.get(f"{primary}_net_oi", np.nan))
            - float(prior.get(f"{primary}_net_oi", np.nan))
        )
        out[f"long_delta_{weeks}w"] = (
            float(latest.get(f"{primary}_long", np.nan))
            - float(prior.get(f"{primary}_long", np.nan))
        )
        out[f"short_delta_{weeks}w"] = (
            float(latest.get(f"{primary}_short", np.nan))
            - float(prior.get(f"{primary}_short", np.nan))
        )

    return out


def transition_hypothesis(
    turn: dict,
    dynamics: dict,
    positioning: dict,
) -> dict:
    """Transparent hypothesis label; deliberately not a production score."""
    if not positioning.get("available"):
        return {
            "label": "NO COT CONTEXT",
            "detail": "Keine ausreichende Positionierungshistorie.",
        }

    if not positioning.get("directional_interpretation"):
        return {
            "label": "CONTEXT ONLY",
            "detail": (
                "TFF Dealer/Intermediary wird nicht automatisch als physischer "
                "Hedger interpretiert. Flow wird gezeigt, aber nicht directional gerankt."
            ),
        }

    kind = str(turn.get("turn_type", "N/V"))
    distance = turn.get("distance_days")
    if distance is None or abs(int(distance)) > 15:
        return {
            "label": "OUTSIDE TURN WINDOW",
            "detail": "Kein nahes saisonales Top/Bottom innerhalb ±15 Handelstagen.",
        }

    net4 = float(positioning.get("net_oi_delta_4w", np.nan))
    long4 = float(positioning.get("long_delta_4w", np.nan))
    short4 = float(positioning.get("short_delta_4w", np.nan))
    slope10 = float(dynamics.get("slope_10d", np.nan))

    if kind == "BOTTOM":
        if net4 > 0 and long4 > 0:
            label = "BULLISH TRANSITION CANDIDATE"
            leg = "aktiver Long-Aufbau"
        elif net4 > 0 and short4 < 0:
            label = "BULLISH COVERING CANDIDATE"
            leg = "Netto verbessert sich primär durch Short-Abbau"
        else:
            label = "BOTTOM WITHOUT COT CONFIRMATION"
            leg = "kein bestätigender 4W-Producer-Flow"
    elif kind == "TOP":
        if net4 < 0 and short4 > 0:
            label = "BEARISH TRANSITION CANDIDATE"
            leg = "aktiver Short-Aufbau"
        elif net4 < 0 and long4 < 0:
            label = "BEARISH LIQUIDATION CANDIDATE"
            leg = "Netto verschlechtert sich primär durch Long-Abbau"
        else:
            label = "TOP WITHOUT COT CONFIRMATION"
            leg = "kein bestätigender 4W-Producer-Flow"
    else:
        label = "NO TURN HYPOTHESIS"
        leg = "kein saisonaler Turn klassifiziert"

    slope_text = (
        f"10T Saison-Slope {slope10:+.3f} %-Pkt/Tag"
        if np.isfinite(slope10)
        else "10T Saison-Slope n/v"
    )
    return {
        "label": label,
        "detail": f"{leg} · {slope_text}",
    }
