
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import MacroConfig
from .features import FeatureFrame
from .types import AtomicModelResult


def _signal(score: float | None, threshold: float) -> str:
    if score is None:
        return "N/V"
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "N/V"
    if not np.isfinite(value):
        return "N/V"
    if value <= -abs(threshold):
        return "RISK_OFF"
    if value >= abs(threshold):
        return "RISK_ON"
    return "NEUTRAL"


def build_atomic_models(
    weekly_scores: pd.DataFrame,
    weekly_raw: pd.DataFrame,
    features: dict[str, FeatureFrame],
    config: MacroConfig,
) -> list[AtomicModelResult]:
    if weekly_scores.empty:
        return []

    threshold = float(
        config.section("breadth").get(
            "atomic_threshold",
            20.0,
        )
    )

    results = []

    for name, item in features.items():
        if name not in weekly_scores.columns:
            continue

        score_series = pd.to_numeric(
            weekly_scores[name],
            errors="coerce",
        )
        clean = score_series.dropna()

        if clean.empty:
            continue

        score = float(clean.iloc[-1])
        signal = _signal(score, threshold)

        tail = score_series.dropna().tail(13)
        if signal == "RISK_OFF":
            persistence = float((tail <= -threshold).mean()) if not tail.empty else 0.0
        elif signal == "RISK_ON":
            persistence = float((tail >= threshold).mean()) if not tail.empty else 0.0
        else:
            persistence = 0.0

        raw_value = None
        if name in weekly_raw.columns:
            raw_clean = pd.to_numeric(
                weekly_raw[name],
                errors="coerce",
            ).dropna()
            if not raw_clean.empty:
                raw_value = float(raw_clean.iloc[-1])

        confidence = float(
            np.clip(abs(score) / 75.0, 0.0, 1.0)
        )

        results.append(
            AtomicModelResult(
                name=name,
                tier=item.spec.tier,
                family=item.spec.family,
                score=score,
                signal=signal,
                confidence=confidence,
                persistence_13w=persistence,
                raw_value=raw_value,
                description=item.spec.description,
            )
        )

    return results
