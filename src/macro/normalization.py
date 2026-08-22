
from __future__ import annotations

import numpy as np
import pandas as pd


def robust_zscore_pit(
    series: pd.Series,
    *,
    window: int,
    min_periods: int,
) -> pd.Series:
    """
    Prior-only rolling robust z-score.

    The current observation never enters its own reference distribution.
    """
    x = pd.to_numeric(series, errors="coerce").astype(float)
    history = x.shift(1)

    median = history.rolling(
        int(window),
        min_periods=int(min_periods),
    ).median()

    def _mad(values):
        values = np.asarray(values, dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return np.nan
        med = np.median(values)
        return np.median(np.abs(values - med))

    mad = history.rolling(
        int(window),
        min_periods=int(min_periods),
    ).apply(_mad, raw=True)

    robust_scale = mad / 0.6744897501960817
    fallback = history.rolling(
        int(window),
        min_periods=int(min_periods),
    ).std(ddof=0)

    scale = robust_scale.where(
        robust_scale.abs() > 1e-12,
        fallback,
    )

    # If both robust and standard deviation are zero because the complete
    # prior history is flat, use a tiny prior-only epsilon. This keeps a real
    # break from a flat regime finite instead of returning NaN.
    epsilon = median.abs().mul(1e-6).clip(lower=1e-6)
    scale = scale.where(
        scale.abs() > 1e-12,
        epsilon,
    )

    return (x - median) / scale


def z_to_score(
    z: pd.Series | float,
    *,
    clip: float = 3.5,
):
    def _one(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return np.nan
        if not np.isfinite(value):
            return np.nan
        value = float(np.clip(value, -float(clip), float(clip)))
        return float(100.0 * np.tanh(value / 1.8))

    if isinstance(z, pd.Series):
        return z.map(_one)
    return _one(z)


def direct_centered_score(
    series: pd.Series,
    *,
    center: float,
    scale: float,
    orientation: float = 1.0,
) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce").astype(float)
    denom = max(abs(float(scale)), 1e-9)
    return (
        ((x - float(center)) / denom)
        * 50.0
        * float(orientation)
    ).clip(-100.0, 100.0)


def weighted_row_mean(
    frame: pd.DataFrame,
    weights: dict[str, float],
) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=float)

    available_cols = [
        c
        for c in frame.columns
        if c in weights and float(weights[c]) > 0
    ]
    if not available_cols:
        return pd.Series(np.nan, index=frame.index, dtype=float)

    values = frame[available_cols].apply(
        pd.to_numeric,
        errors="coerce",
    )
    weight_series = pd.Series(
        {c: float(weights[c]) for c in available_cols}
    )

    weighted = values.mul(weight_series, axis=1)
    denom = values.notna().mul(weight_series, axis=1).sum(axis=1)
    numer = weighted.sum(axis=1, skipna=True)

    return numer.div(denom.replace(0.0, np.nan)).clip(-100.0, 100.0)
