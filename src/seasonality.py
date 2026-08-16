
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd


FIXED_HISTORY_WINDOWS = (5, 10, 15, 20, 30)
FIXED_HORIZONS = (10, 20, 40, 60)


def _clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if prices is None or prices.empty or "close" not in prices.columns:
        return pd.DataFrame()

    out = prices[["close"]].copy()
    out.index = pd.to_datetime(out.index)
    if getattr(out.index, "tz", None) is not None:
        out.index = out.index.tz_localize(None)

    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna().sort_index()
    out["year"] = out.index.year
    return out


def _iqr_bounds(values: np.ndarray, factor: float = 2.75) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 4:
        return (-np.inf, np.inf)

    q1 = float(np.quantile(arr, 0.25))
    q3 = float(np.quantile(arr, 0.75))
    iqr = q3 - q1
    return q1 - factor * iqr, q3 + factor * iqr


def _historical_years(prices: pd.DataFrame, years: int) -> list[int]:
    if prices.empty:
        return []

    current_year = int(prices.index.max().year)
    completed = sorted(int(y) for y in prices["year"].unique() if int(y) < current_year)
    return completed[-int(years):]


def current_trading_day_index(prices: pd.DataFrame) -> int | None:
    p = _clean_prices(prices)
    if p.empty:
        return None

    current_year = int(p.index.max().year)
    current = p[p["year"] == current_year]
    if current.empty:
        return None

    return int(len(current) - 1)


def _historical_anchor_positions(
    prices: pd.DataFrame,
    years: int,
) -> list[tuple[int, int]]:
    """
    Return (year, global_index_position) pairs for the same trading-day
    position in prior completed years.

    Global index positions are used so forward horizons can cross year-end.
    """
    p = _clean_prices(prices)
    if p.empty:
        return []

    anchor_idx = current_trading_day_index(p)
    if anchor_idx is None:
        return []

    positions = []
    for year in _historical_years(p, years):
        y = p[p["year"] == year]
        if len(y) <= anchor_idx:
            continue

        anchor_date = y.index[anchor_idx]
        pos = int(p.index.get_indexer([anchor_date])[0])
        if pos >= 0:
            positions.append((year, pos))

    return positions


def _all_phase_returns(prices: pd.DataFrame, horizon: int) -> np.ndarray:
    """
    Baseline distribution across all possible calendar phases of the market.

    These returns overlap by construction. The resulting base rate is therefore
    descriptive; it is a market-specific comparison probability, not an
    independent Bernoulli trial series.
    """
    p = _clean_prices(prices)
    if p.empty or len(p) <= int(horizon):
        return np.asarray([], dtype=float)

    close = p["close"].to_numpy(dtype=float)
    h = int(horizon)
    base = close[:-h]
    future = close[h:]

    valid = (
        np.isfinite(base)
        & np.isfinite(future)
        & (base > 0)
    )
    return future[valid] / base[valid] - 1.0


def _exact_binomial_two_sided(k: int, n: int, p0: float) -> float:
    """
    Exact two-sided binomial p-value using the probability-ordering definition
    used by common statistical packages.
    """
    if n <= 0 or not np.isfinite(p0):
        return np.nan

    p0 = float(np.clip(p0, 0.0, 1.0))

    if p0 == 0.0:
        return 1.0 if k == 0 else 0.0
    if p0 == 1.0:
        return 1.0 if k == n else 0.0

    def pmf(i: int) -> float:
        return (
            math.comb(n, i)
            * (p0 ** i)
            * ((1.0 - p0) ** (n - i))
        )

    observed = pmf(int(k))
    probs = [pmf(i) for i in range(n + 1)]
    return float(min(1.0, sum(prob for prob in probs if prob <= observed + 1e-15)))


def _wilson_interval(
    k: int,
    n: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Wilson score interval for the observed positive-return proportion.
    More stable than the naive normal interval for small n.
    """
    if n <= 0:
        return (np.nan, np.nan)

    z = NormalDist().inv_cdf(0.5 + float(confidence) / 2.0)
    phat = float(k) / float(n)
    z2 = z * z
    denom = 1.0 + z2 / n

    center = (phat + z2 / (2.0 * n)) / denom
    half = (
        z
        * math.sqrt(
            phat * (1.0 - phat) / n
            + z2 / (4.0 * n * n)
        )
        / denom
    )

    return (
        float(max(0.0, center - half)),
        float(min(1.0, center + half)),
    )


def seasonal_forward_path(
    prices: pd.DataFrame,
    years: int,
    max_forward_days: int = 60,
    outlier_factor: float = 2.75,
) -> pd.DataFrame:
    """
    Adaptation of the supplied Pine indicator logic.

    The same trading-day position in prior years is used as the anchor.
    Daily forward moves are pooled across those historical years, winsorised
    by an IQR rule and averaged by forward-day offset. The average daily moves
    are compounded into a synthetic seasonal tendency beginning at 0%.

    This is a visual tendency curve only. Inferential/descriptive statistics
    are calculated separately from the unmodified realised forward returns.
    """
    p = _clean_prices(prices)
    if p.empty:
        return pd.DataFrame()

    anchors = _historical_anchor_positions(p, int(years))
    if len(anchors) < 3:
        return pd.DataFrame()

    close = p["close"].to_numpy(dtype=float)
    daily = p["close"].pct_change().to_numpy(dtype=float) * 100.0

    pooled = []
    sequences = {}

    for year, pos in anchors:
        seq = []
        for offset in range(1, int(max_forward_days) + 1):
            idx = pos + offset
            if idx >= len(daily):
                seq.append(np.nan)
            else:
                value = daily[idx]
                seq.append(float(value) if np.isfinite(value) else np.nan)

        sequences[year] = np.asarray(seq, dtype=float)
        finite = sequences[year][np.isfinite(sequences[year])]
        pooled.extend(finite.tolist())

    if len(pooled) < 10:
        return pd.DataFrame()

    lower, upper = _iqr_bounds(np.asarray(pooled), outlier_factor)

    avg_moves = []
    samples = []

    for offset in range(int(max_forward_days)):
        vals = []
        for seq in sequences.values():
            if offset < len(seq) and np.isfinite(seq[offset]):
                vals.append(float(np.clip(seq[offset], lower, upper)))

        if vals:
            avg_moves.append(float(np.mean(vals)))
            samples.append(int(len(vals)))
        else:
            avg_moves.append(np.nan)
            samples.append(0)

    path = [0.0]
    level = 1.0

    for move in avg_moves:
        if np.isfinite(move):
            level *= 1.0 + move / 100.0
        path.append((level - 1.0) * 100.0)

    return pd.DataFrame({
        "handelstage_voraus": np.arange(0, int(max_forward_days) + 1),
        "saisonale_rendite_pct": path,
        "stichprobe": [len(anchors)] + samples,
        "historienfenster_jahre": int(years),
    })


def forward_statistics(
    prices: pd.DataFrame,
    history_windows=FIXED_HISTORY_WINDOWS,
    horizons=FIXED_HORIZONS,
) -> pd.DataFrame:
    """
    Real historical forward-return statistics for the same trading-day
    position in prior years.

    Added calibration:
    - market-specific positive-return base rate across all calendar phases
    - difference to that base rate in percentage points
    - exact two-sided binomial p-value against the base rate
    - 95% Wilson confidence interval for the observed positive proportion

    No outlier capping is applied to these realised returns.
    """
    p = _clean_prices(prices)
    if p.empty:
        return pd.DataFrame()

    close = p["close"].to_numpy(dtype=float)

    baseline = {}
    for horizon in horizons:
        all_phase = _all_phase_returns(p, int(horizon))
        if len(all_phase):
            baseline[int(horizon)] = {
                "rate": float(np.mean(all_phase > 0)),
                "n": int(len(all_phase)),
                "median": float(np.median(all_phase)),
            }
        else:
            baseline[int(horizon)] = {
                "rate": np.nan,
                "n": 0,
                "median": np.nan,
            }

    rows = []

    for years in history_windows:
        anchors = _historical_anchor_positions(p, int(years))

        for horizon in horizons:
            h = int(horizon)
            returns = []

            for _, pos in anchors:
                target = pos + h
                if target >= len(close):
                    continue

                p0 = float(close[pos])
                p1 = float(close[target])

                if p0 > 0 and np.isfinite(p0) and np.isfinite(p1):
                    returns.append(p1 / p0 - 1.0)

            arr = np.asarray(returns, dtype=float)
            arr = arr[np.isfinite(arr)]

            base_rate = baseline[h]["rate"]
            base_n = baseline[h]["n"]
            base_median = baseline[h]["median"]

            if len(arr) == 0:
                rows.append({
                    "historie_jahre": int(years),
                    "horizont_tage": h,
                    "stichprobe": 0,
                    "positive_jahre": 0,
                    "trefferquote_positiv": np.nan,
                    "ki95_unten": np.nan,
                    "ki95_oben": np.nan,
                    "basisrate_positiv": base_rate,
                    "basisrate_stichprobe": base_n,
                    "basis_median_rendite": base_median,
                    "abstand_basisrate_pp": np.nan,
                    "binomial_p": np.nan,
                    "median_rendite": np.nan,
                    "mittel_rendite": np.nan,
                    "standardabweichung": np.nan,
                    "minimum": np.nan,
                    "maximum": np.nan,
                })
                continue

            n = int(len(arr))
            k = int(np.sum(arr > 0))
            hit = float(k / n)
            ci_low, ci_high = _wilson_interval(k, n, confidence=0.95)

            rows.append({
                "historie_jahre": int(years),
                "horizont_tage": h,
                "stichprobe": n,
                "positive_jahre": k,
                "trefferquote_positiv": hit,
                "ki95_unten": ci_low,
                "ki95_oben": ci_high,
                "basisrate_positiv": base_rate,
                "basisrate_stichprobe": base_n,
                "basis_median_rendite": base_median,
                "abstand_basisrate_pp": (
                    (hit - base_rate) * 100.0
                    if np.isfinite(base_rate)
                    else np.nan
                ),
                "binomial_p": _exact_binomial_two_sided(k, n, base_rate),
                "median_rendite": float(np.median(arr)),
                "mittel_rendite": float(np.mean(arr)),
                "standardabweichung": (
                    float(np.std(arr, ddof=1))
                    if len(arr) > 1
                    else np.nan
                ),
                "minimum": float(np.min(arr)),
                "maximum": float(np.max(arr)),
            })

    return pd.DataFrame(rows)


def _window_direction(row: pd.Series) -> int:
    """
    Direction is descriptive and relative to the market's own base rate.

    Bullish:
      median > 0 AND seasonal positive rate > market base rate
    Bearish:
      median < 0 AND seasonal positive rate < market base rate

    No significance threshold is used to label the window.
    """
    med = row.get("median_rendite", np.nan)
    hit = row.get("trefferquote_positiv", np.nan)
    base = row.get("basisrate_positiv", np.nan)

    if not all(np.isfinite(v) for v in [med, hit, base]):
        return 0

    if med > 0 and hit > base:
        return 1
    if med < 0 and hit < base:
        return -1
    return 0


def seasonal_consistency(
    stats: pd.DataFrame,
    primary_horizon: int = 10,
    required_windows=FIXED_HISTORY_WINDOWS,
    reference_years: int = 30,
) -> dict:
    """
    No 'robust' label and no score.

    The output reports how many of the fixed nested history windows point in
    the same direction. These windows are explicitly not independent tests.
    """
    if stats is None or stats.empty:
        return {
            "status": "KEINE DATEN",
            "direction": 0,
            "detail": "Keine ausreichende Preishistorie",
            "window_detail": "—",
            "reference_detail": "—",
            "available_windows": 0,
            "bullish_windows": 0,
            "bearish_windows": 0,
        }

    s = stats[
        (stats["horizont_tage"] == int(primary_horizon))
        & (stats["historie_jahre"].isin([int(x) for x in required_windows]))
        & (stats["stichprobe"] >= 3)
    ].copy()

    if s.empty:
        return {
            "status": "KEINE DATEN",
            "direction": 0,
            "detail": "Keine ausreichende Stichprobe",
            "window_detail": "—",
            "reference_detail": "—",
            "available_windows": 0,
            "bullish_windows": 0,
            "bearish_windows": 0,
        }

    s["richtung"] = s.apply(_window_direction, axis=1)

    bullish = int((s["richtung"] == 1).sum())
    bearish = int((s["richtung"] == -1).sum())
    available = int(len(s))

    if bullish > bearish:
        direction = 1
        status = f"BULLISCH IN {bullish} VON {available} FENSTERN"
    elif bearish > bullish:
        direction = -1
        status = f"BÄRISCH IN {bearish} VON {available} FENSTERN"
    else:
        direction = 0
        status = f"GEMISCHT · {bullish} BULLISCH / {bearish} BÄRISCH"

    arrows = {1: "↑", -1: "↓", 0: "·"}
    window_parts = []
    for years in required_windows:
        row = s[s["historie_jahre"] == int(years)]
        if row.empty:
            window_parts.append(f"{years}J n/v")
        else:
            d = int(row.iloc[0]["richtung"])
            window_parts.append(f"{years}J {arrows[d]}")
    window_detail = " · ".join(window_parts)

    # Compact evidence line: prefer 10Y because it is intuitive, but never
    # describe it as robust. If unavailable, use the largest available window.
    preferred = s[s["historie_jahre"] == 10]
    if preferred.empty:
        preferred = s.sort_values("historie_jahre", ascending=False).head(1)

    row = preferred.iloc[0]
    k = int(row["positive_jahre"])
    n = int(row["stichprobe"])
    hit = float(row["trefferquote_positiv"])
    base = float(row["basisrate_positiv"])
    delta = float(row["abstand_basisrate_pp"])
    pval = float(row["binomial_p"])
    ci_low = float(row["ki95_unten"])
    ci_high = float(row["ki95_oben"])

    detail = (
        f"{int(row['historie_jahre'])}J: {k}/{n} positiv · "
        f"Basisrate {base:.0%} · Δ {delta:+.0f} Pp. · "
        f"p={pval:.2f} · 95%-KI {ci_low:.0%}–{ci_high:.0%}"
    )

    reference = s[s["historie_jahre"] == int(reference_years)]
    if reference.empty:
        reference = s.sort_values("historie_jahre", ascending=False).head(1)

    rr = reference.iloc[0]
    reference_detail = (
        f"{int(rr['historie_jahre'])}J-Referenz: "
        f"Median {rr['median_rendite']:+.2%} · "
        f"{int(rr['positive_jahre'])}/{int(rr['stichprobe'])} positiv · "
        f"Basisrate {rr['basisrate_positiv']:.0%}"
    )

    return {
        "status": status,
        "direction": direction,
        "detail": detail,
        "window_detail": window_detail,
        "reference_detail": reference_detail,
        "available_windows": available,
        "bullish_windows": bullish,
        "bearish_windows": bearish,
    }


# Backwards-compatible alias for older app code during upgrades.
seasonal_consensus = seasonal_consistency
