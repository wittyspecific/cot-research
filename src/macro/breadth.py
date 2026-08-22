
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from .config import MacroConfig
from .features import FeatureFrame


@dataclass
class FamilyVote:
    tier: str
    family: str
    signal: str
    agreement: float
    active_models: int
    risk_off_models: int
    risk_on_models: int
    neutral_models: int

    def to_dict(self):
        return asdict(self)


def _classify(value, threshold):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/V"

    if not np.isfinite(value):
        return "N/V"
    if value <= -abs(threshold):
        return "RISK_OFF"
    if value >= abs(threshold):
        return "RISK_ON"
    return "NEUTRAL"


def family_votes_at(
    weekly_scores: pd.DataFrame,
    features: dict[str, FeatureFrame],
    config: MacroConfig,
    *,
    offset_weeks: int = 0,
) -> list[FamilyVote]:
    if weekly_scores.empty or len(weekly_scores) <= offset_weeks:
        return []

    cfg = config.section("breadth")
    threshold = float(cfg.get("atomic_threshold", 20.0))
    family_threshold = float(
        cfg.get("family_agreement_threshold", 0.60)
    )

    row = weekly_scores.iloc[-1 - int(offset_weeks)]

    grouped: dict[tuple[str, str], list[str]] = {}
    for name, item in features.items():
        if name not in weekly_scores.columns:
            continue
        if item.spec.tier not in {
            "leading",
            "coincident",
            "lagging",
            "imminent",
        }:
            continue
        grouped.setdefault(
            (item.spec.tier, item.spec.family),
            [],
        ).append(name)

    votes = []

    for (tier, family), names in sorted(grouped.items()):
        signals = [
            _classify(row.get(name), threshold)
            for name in names
        ]
        signals = [s for s in signals if s != "N/V"]

        if not signals:
            votes.append(
                FamilyVote(tier, family, "N/V", 0.0, 0, 0, 0, 0)
            )
            continue

        ro = signals.count("RISK_OFF")
        ri = signals.count("RISK_ON")
        ne = signals.count("NEUTRAL")
        active = len(signals)
        dominant = max(ro, ri)
        agreement = dominant / active if active else 0.0

        if ro > ri and agreement >= family_threshold:
            signal = "RISK_OFF"
        elif ri > ro and agreement >= family_threshold:
            signal = "RISK_ON"
        else:
            signal = "MIXED"

        votes.append(
            FamilyVote(
                tier=tier,
                family=family,
                signal=signal,
                agreement=float(agreement),
                active_models=active,
                risk_off_models=ro,
                risk_on_models=ri,
                neutral_models=ne,
            )
        )

    return votes


def _breadth_for_tier(
    votes: list[FamilyVote],
    tier: str,
    confirm_threshold: float,
) -> dict[str, Any]:
    available = [
        v
        for v in votes
        if v.tier == tier and v.signal != "N/V"
    ]

    denom = max(len(available), 1)
    ro = sum(v.signal == "RISK_OFF" for v in available)
    ri = sum(v.signal == "RISK_ON" for v in available)
    mixed = sum(v.signal == "MIXED" for v in available)

    ro_b = ro / denom
    ri_b = ri / denom

    if ro_b >= confirm_threshold:
        state = "RISK_OFF_CONFIRMED"
    elif ri_b >= confirm_threshold:
        state = "RISK_ON_CONFIRMED"
    elif ro_b > ri_b:
        state = "RISK_OFF_LEAN"
    elif ri_b > ro_b:
        state = "RISK_ON_LEAN"
    else:
        state = "MIXED"

    return {
        "tier": tier,
        "state": state,
        "risk_off_breadth": float(ro_b),
        "risk_on_breadth": float(ri_b),
        "risk_off_families": int(ro),
        "risk_on_families": int(ri),
        "mixed_families": int(mixed),
        "available_families": int(len(available)),
        "confirmation_threshold": float(confirm_threshold),
    }


def evaluate_breadth(
    weekly_scores: pd.DataFrame,
    features: dict[str, FeatureFrame],
    config: MacroConfig,
) -> dict[str, Any]:
    cfg = config.section("breadth")
    confirm = float(
        cfg.get("family_confirmation_threshold", 0.70)
    )

    current_votes = family_votes_at(
        weekly_scores,
        features,
        config,
        offset_weeks=0,
    )

    tiers = {
        tier: _breadth_for_tier(current_votes, tier, confirm)
        for tier in ("leading", "coincident", "lagging", "imminent")
    }

    history = {}
    for label, offset in (("NOW", 0), ("4W", 4), ("13W", 13)):
        votes = family_votes_at(
            weekly_scores,
            features,
            config,
            offset_weeks=offset,
        )
        history[label] = {
            tier: _breadth_for_tier(votes, tier, confirm)
            for tier in ("leading", "coincident", "imminent")
        }

    return {
        "tiers": tiers,
        "history": history,
        "family_votes": [v.to_dict() for v in current_votes],
        "note": (
            "Breadth is diagnostic. It never overrides the Business Cycle Core. "
            "Leading/Coincident disagreement can be expected sequencing rather than conflict."
        ),
    }
