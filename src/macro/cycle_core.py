
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from .config import MacroConfig


PHASES = {
    "EXPANSION",
    "SLOWDOWN",
    "CONTRACTION",
    "RECOVERY",
    "UNCERTAIN",
}


def raw_phase(
    leading_distance: float,
    leading_slope: float,
    coincident_distance: float,
    coincident_slope: float,
    threshold: float,
) -> str:
    values = (
        leading_distance,
        coincident_distance,
    )
    if any(v is None or not np.isfinite(float(v)) for v in values):
        return "UNCERTAIN"

    ld = float(leading_distance)
    cd = float(coincident_distance)
    ls = float(leading_slope) if np.isfinite(leading_slope) else 0.0
    cs = float(coincident_slope) if np.isfinite(coincident_slope) else 0.0
    t = abs(float(threshold))

    # Recovery is intentionally detected before Contraction:
    # leading turns upward first while coincident activity can remain weak.
    if cd < -t and ld > 0 and ls > 0:
        return "RECOVERY"

    if cd < -t and cs <= 0:
        return "CONTRACTION"

    if ld < -t and cd >= -t:
        return "SLOWDOWN"

    if ld >= -t and cd >= -t:
        return "EXPANSION"

    if ld > t and cd < 0 and ls > 0:
        return "RECOVERY"

    return "UNCERTAIN"


def classify_cycle_history(
    cycle_frame: pd.DataFrame,
    config: MacroConfig,
) -> pd.DataFrame:
    if cycle_frame.empty:
        return pd.DataFrame()

    threshold = float(
        config.section("equilibrium").get(
            "distance_threshold",
            5.0,
        )
    )
    p_cfg = config.section("phase")
    window = int(p_cfg.get("persistence_weeks", 4))
    required = int(p_cfg.get("persistence_required", 3))

    out = cycle_frame.copy()

    raw = []
    for _, row in out.iterrows():
        raw.append(
            raw_phase(
                row.get("leading_distance"),
                row.get("leading_slope_13w"),
                row.get("coincident_distance"),
                row.get("coincident_slope_13w"),
                threshold,
            )
        )

    out["raw_phase"] = raw

    confirmed = []
    for i in range(len(out)):
        start = max(0, i - window + 1)
        sample = [
            x
            for x in out["raw_phase"].iloc[start:i + 1].tolist()
            if x != "UNCERTAIN"
        ]
        if not sample:
            confirmed.append("UNCERTAIN")
            continue

        phase, count = Counter(sample).most_common(1)[0]
        confirmed.append(
            phase if count >= min(required, len(sample)) else "UNCERTAIN"
        )

    out["cycle_phase"] = confirmed
    return out


def phase_divergence(cycle_frame: pd.DataFrame) -> str:
    if cycle_frame.empty:
        return "N/V"

    row = cycle_frame.iloc[-1]
    ld = row.get("leading_distance")
    cd = row.get("coincident_distance")

    try:
        ld = float(ld)
        cd = float(cd)
    except (TypeError, ValueError):
        return "N/V"

    if not np.isfinite(ld) or not np.isfinite(cd):
        return "N/V"

    if ld < 0 <= cd:
        return "EXPECTED_SLOWDOWN_DIVERGENCE"
    if ld > 0 >= cd:
        return "EXPECTED_RECOVERY_DIVERGENCE"
    if (ld >= 0 and cd >= 0) or (ld <= 0 and cd <= 0):
        return "ALIGNED"
    return "TRANSITIONAL"


def phase_confidence(
    cycle_history: pd.DataFrame,
    *,
    data_coverage: float,
) -> float:
    if cycle_history.empty:
        return 0.0

    current = str(
        cycle_history.iloc[-1].get("cycle_phase", "UNCERTAIN")
    )
    if current == "UNCERTAIN":
        persistence = 0.35
    else:
        tail = cycle_history["cycle_phase"].tail(8)
        persistence = float((tail == current).mean())

    row = cycle_history.iloc[-1]
    magnitudes = []

    for key in ("leading_distance", "coincident_distance"):
        try:
            value = abs(float(row.get(key)))
        except (TypeError, ValueError):
            continue
        if np.isfinite(value):
            magnitudes.append(value)

    separation = (
        min(1.0, float(np.mean(magnitudes)) / 30.0)
        if magnitudes
        else 0.0
    )

    return float(
        np.clip(
            0.55 * float(np.clip(data_coverage, 0.0, 1.0))
            + 0.30 * persistence
            + 0.15 * separation,
            0.0,
            1.0,
        )
    )
