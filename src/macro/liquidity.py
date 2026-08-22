
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .config import MacroConfig
from .features import FeatureFrame


def _mean(values):
    clean = [
        float(v)
        for v in values
        if v is not None and np.isfinite(float(v))
    ]
    return float(np.mean(clean)) if clean else np.nan


def evaluate_liquidity(
    weekly_scores: pd.DataFrame,
    features: dict[str, FeatureFrame],
    config: MacroConfig,
    *,
    cycle_phase: str,
) -> dict[str, Any]:
    if weekly_scores.empty:
        return {
            "state": "N/V",
            "score": None,
            "channels": {},
            "cycle_phase": cycle_phase,
        }

    row = weekly_scores.iloc[-1]

    grouped: dict[str, list[float]] = {
        "policy": [],
        "credit": [],
        "market": [],
    }

    family_to_channel = {
        "policy_liquidity": "policy",
        "credit_liquidity": "credit",
        "market_liquidity": "market",
    }

    for name, item in features.items():
        if item.spec.tier != "liquidity":
            continue
        channel = family_to_channel.get(item.spec.family)
        if channel is None or name not in weekly_scores.columns:
            continue

        value = row.get(name)
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if np.isfinite(value):
            grouped[channel].append(value)

    channel_scores = {
        key: _mean(values)
        for key, values in grouped.items()
    }

    weights = {
        str(k): float(v)
        for k, v in config.section("liquidity_weights").items()
    }

    numer = 0.0
    denom = 0.0

    for channel, score in channel_scores.items():
        if not np.isfinite(score):
            continue
        weight = float(weights.get(channel, 1.0))
        numer += score * weight
        denom += weight

    score = numer / denom if denom else np.nan

    if not np.isfinite(score):
        state = "N/V"
    elif score >= 20:
        state = "SUPPORTIVE"
    elif score <= -20:
        state = "RESTRICTIVE"
    else:
        state = "NEUTRAL"

    if cycle_phase == "SLOWDOWN" and state == "SUPPORTIVE":
        interpretation = (
            "Supportive liquidity may delay recognition or extend market overshoot; "
            "it does not reverse the slowdown regime."
        )
    elif cycle_phase == "CONTRACTION" and state == "SUPPORTIVE":
        interpretation = (
            "Supportive liquidity is treated as stabilization during contraction, "
            "not as proof that contraction has ended."
        )
    elif cycle_phase == "RECOVERY" and state == "SUPPORTIVE":
        interpretation = (
            "Supportive liquidity can amplify recovery after leading momentum has turned."
        )
    else:
        interpretation = (
            "Liquidity modifies timing, amplitude and persistence only; "
            "the Business Cycle Core remains the regime anchor."
        )

    return {
        "state": state,
        "score": float(score) if np.isfinite(score) else None,
        "channels": {
            key: (
                float(value)
                if np.isfinite(value)
                else None
            )
            for key, value in channel_scores.items()
        },
        "cycle_phase": cycle_phase,
        "interpretation": interpretation,
    }
