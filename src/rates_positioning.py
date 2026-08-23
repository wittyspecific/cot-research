from __future__ import annotations

from typing import Any

import numpy as np


RATE_KEYS = (
    "treasury2y",
    "treasury5y",
    "treasury10y",
    "treasury30y",
)


def _finite(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def _weighted(values: dict[str, float | None], weights: dict[str, float]) -> tuple[float | None, float]:
    numerator = 0.0
    denominator = 0.0
    total = sum(max(0.0, float(weight)) for weight in weights.values())

    for key, weight in weights.items():
        value = values.get(key)
        if value is None:
            continue
        weight = max(0.0, float(weight))
        numerator += float(value) * weight
        denominator += weight

    if denominator <= 0:
        return None, 0.0

    return numerator / denominator, denominator / total if total else 0.0


def _direction_breadth(
    cot_states: dict[str, dict[str, Any]],
    weights: dict[str, float],
    field: str,
    direction: str,
) -> float | None:
    numerator = 0.0
    denominator = 0.0

    for key, weight in weights.items():
        state = cot_states.get(key, {})
        if not state.get("available"):
            continue
        value = str(state.get(field, "N/V")).upper()
        if value == "N/V":
            continue
        denominator += float(weight)
        if value == direction:
            numerator += float(weight)

    return numerator / denominator if denominator > 0 else None


def evaluate_rates_positioning(
    cot_states: dict[str, dict[str, Any]],
    *,
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Aggregate 2Y/5Y/10Y/30Y Treasury COT into one duration regime.

    The component uses already-computed structural COT states, so it does not
    create a parallel COT model. In TFF those structural states are based on
    Asset Manager positioning. Individual Treasury contracts do not vote
    separately in cross-asset breadth; this aggregate contributes one rates vote.
    """

    cfg = config.get("rates", {})
    weights = {
        str(key): float(value)
        for key, value in cfg.get(
            "contract_weights",
            {
                "treasury2y": 0.30,
                "treasury5y": 0.25,
                "treasury10y": 0.25,
                "treasury30y": 0.20,
            },
        ).items()
    }

    minimum_coverage = float(cfg.get("minimum_coverage", 0.50))
    lean = float(cfg.get("breadth_lean", 0.45))
    strong = float(cfg.get("breadth_strong", 0.60))
    persistence_threshold = float(cfg.get("persistence_threshold", 0.65))
    active_build_threshold = float(cfg.get("active_build_threshold", 0.55))
    directional_threshold = float(config.get("cot", {}).get("state_directional_threshold", 18.0))

    scores = {}
    persistence_values = {}
    active_build_values = {}
    contract_rows = []

    bullish_weight = 0.0
    bearish_weight = 0.0
    directional_weight = 0.0

    for key, weight in weights.items():
        state = cot_states.get(key, {})
        available = bool(state.get("available"))
        score = _finite(state.get("score")) if available else None
        persistence = _finite(state.get("persistence")) if available else None
        active_build = _finite(state.get("active_build_share")) if available else None

        scores[key] = score
        persistence_values[key] = persistence
        active_build_values[key] = active_build

        if score is not None:
            directional_weight += float(weight)
            if score >= directional_threshold:
                bullish_weight += float(weight)
            elif score <= -directional_threshold:
                bearish_weight += float(weight)

        contract_rows.append(
            {
                "key": key,
                "label": str(state.get("label", key)),
                "available": available,
                "state": str(state.get("state", "INSUFFICIENT DATA")),
                "score": score,
                "direction_2w": str(state.get("direction_2w", "N/V")),
                "direction_4w": str(state.get("direction_4w", "N/V")),
                "persistence": persistence,
                "active_build_share": active_build,
            }
        )

    score, coverage = _weighted(scores, weights)
    persistence, _ = _weighted(persistence_values, weights)
    active_build, _ = _weighted(active_build_values, weights)

    bullish_breadth = bullish_weight / directional_weight if directional_weight > 0 else None
    bearish_breadth = bearish_weight / directional_weight if directional_weight > 0 else None

    bullish_2w = _direction_breadth(cot_states, weights, "direction_2w", "BULLISH")
    bullish_4w = _direction_breadth(cot_states, weights, "direction_4w", "BULLISH")
    bearish_2w = _direction_breadth(cot_states, weights, "direction_2w", "BEARISH")
    bearish_4w = _direction_breadth(cot_states, weights, "direction_4w", "BEARISH")

    if coverage < minimum_coverage or score is None:
        state_name = "INSUFFICIENT DATA"
    else:
        broad_bullish = bool(
            bullish_breadth is not None
            and bullish_breadth >= strong
            and bullish_2w is not None
            and bullish_2w >= strong
            and bullish_4w is not None
            and bullish_4w >= strong
            and persistence is not None
            and persistence >= persistence_threshold
        )

        broad_bearish = bool(
            bearish_breadth is not None
            and bearish_breadth >= strong
            and bearish_2w is not None
            and bearish_2w >= strong
            and bearish_4w is not None
            and bearish_4w >= strong
            and persistence is not None
            and persistence >= persistence_threshold
        )

        if broad_bullish and active_build is not None and active_build >= active_build_threshold:
            state_name = "BROAD DURATION ACCUMULATION"
        elif broad_bullish:
            state_name = "BULLISH DURATION"
        elif broad_bearish and active_build is not None and active_build >= active_build_threshold:
            state_name = "BROAD DURATION DISTRIBUTION"
        elif broad_bearish:
            state_name = "BEARISH DURATION"
        elif bullish_breadth is not None and bullish_breadth >= lean:
            state_name = "BULLISH DURATION LEAN"
        elif bearish_breadth is not None and bearish_breadth >= lean:
            state_name = "BEARISH DURATION LEAN"
        else:
            state_name = "MIXED DURATION"

    return {
        "available": bool(coverage >= minimum_coverage and score is not None),
        "state": state_name,
        "score": score,
        "coverage": float(np.clip(coverage, 0.0, 1.0)),
        "contracts_available": sum(bool(row["available"]) for row in contract_rows),
        "contracts_expected": len(weights),
        "bullish_breadth": bullish_breadth,
        "bearish_breadth": bearish_breadth,
        "bullish_2w_breadth": bullish_2w,
        "bullish_4w_breadth": bullish_4w,
        "bearish_2w_breadth": bearish_2w,
        "bearish_4w_breadth": bearish_4w,
        "persistence": persistence,
        "active_build_share": active_build,
        "risk_off_confirmed": bool(
            state_name in {
                "BROAD DURATION ACCUMULATION",
                "BULLISH DURATION",
                "BULLISH DURATION LEAN",
            }
        ),
        "risk_on_confirmed": bool(
            state_name in {
                "BROAD DURATION DISTRIBUTION",
                "BEARISH DURATION",
                "BEARISH DURATION LEAN",
            }
        ),
        "contracts": contract_rows,
        "methodology": (
            "2Y/5Y/10Y/30Y Treasury structural COT aggregated once. "
            "Broad accumulation requires multi-tenor 2W/4W persistence; "
            "active position building is distinguished from unwinding."
        ),
    }
