
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import MacroConfig
from .features import FeatureFrame
from .normalization import weighted_row_mean
from .types import TierSnapshot


def build_family_indices(
    weekly_scores: pd.DataFrame,
    features: dict[str, FeatureFrame],
) -> pd.DataFrame:
    if weekly_scores.empty:
        return pd.DataFrame(index=weekly_scores.index)

    family_map: dict[str, list[str]] = {}
    tier_map: dict[str, str] = {}

    for name, item in features.items():
        if name not in weekly_scores.columns:
            continue
        key = f"{item.spec.tier}:{item.spec.family}"
        family_map.setdefault(key, []).append(name)
        tier_map[key] = item.spec.tier

    family_frame = pd.DataFrame(index=weekly_scores.index)

    for key, columns in family_map.items():
        family_frame[key] = (
            weekly_scores[columns]
            .apply(pd.to_numeric, errors="coerce")
            .mean(axis=1, skipna=True)
        )

    return family_frame


def build_tier_indices(
    family_frame: pd.DataFrame,
    config: MacroConfig,
) -> pd.DataFrame:
    out = pd.DataFrame(index=family_frame.index)

    for tier in ("leading", "coincident", "lagging"):
        prefix = f"{tier}:"
        cols = [
            c
            for c in family_frame.columns
            if c.startswith(prefix)
        ]

        weights = config.nested(
            "tier_family_weights",
            tier,
        )
        full_weights = {
            f"{tier}:{family}": float(weight)
            for family, weight in weights.items()
        }

        out[tier] = weighted_row_mean(
            family_frame[cols] if cols else pd.DataFrame(index=family_frame.index),
            full_weights,
        )

    return out


def add_equilibrium(
    tier_indices: pd.DataFrame,
    config: MacroConfig,
) -> pd.DataFrame:
    cfg = config.section("equilibrium")
    lookback = int(cfg.get("lookback_weeks", 520))
    min_weeks = int(cfg.get("min_weeks", 156))
    slope_weeks = int(cfg.get("slope_weeks", 13))

    out = tier_indices.copy()

    for tier in ("leading", "coincident", "lagging"):
        series = pd.to_numeric(
            out.get(tier),
            errors="coerce",
        )
        equilibrium = (
            series.shift(1)
            .rolling(lookback, min_periods=min_weeks)
            .median()
        )

        # Feature scores are themselves prior-normalized around zero. Zero is
        # therefore a valid fallback until a sufficiently long composite
        # history exists.
        equilibrium = equilibrium.fillna(0.0)

        out[f"{tier}_equilibrium"] = equilibrium
        out[f"{tier}_distance"] = series - equilibrium
        out[f"{tier}_slope_13w"] = series.diff(slope_weeks)

    return out


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def tier_snapshot(
    cycle_frame: pd.DataFrame,
    family_frame: pd.DataFrame,
    tier: str,
) -> TierSnapshot:
    if cycle_frame.empty:
        return TierSnapshot(tier, None, None, None, None, 0.0, 0)

    row = cycle_frame.iloc[-1]
    distance = _finite(row.get(f"{tier}_distance"))

    signal = 0
    if distance is not None:
        signal = 1 if distance > 0 else -1 if distance < 0 else 0

    tail = pd.to_numeric(
        cycle_frame.get(f"{tier}_distance"),
        errors="coerce",
    ).dropna().tail(13)

    if signal == 0 or tail.empty:
        persistence = 0.0
    else:
        persistence = float(
            ((tail > 0) if signal > 0 else (tail < 0)).mean()
        )

    families_available = sum(
        (
            c.startswith(f"{tier}:")
            and family_frame[c].dropna().shape[0] > 0
        )
        for c in family_frame.columns
    )

    return TierSnapshot(
        tier=tier,
        index=_finite(row.get(tier)),
        equilibrium=_finite(row.get(f"{tier}_equilibrium")),
        distance=distance,
        slope_13w=_finite(row.get(f"{tier}_slope_13w")),
        persistence=persistence,
        families_available=int(families_available),
    )
