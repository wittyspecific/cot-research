from __future__ import annotations

import numpy as np
import pandas as pd


def _finite(value) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return np.nan
    return x if np.isfinite(x) else np.nan


def _micro_direction(value, *, upper: float, lower: float) -> int:
    x = _finite(value)
    if not np.isfinite(x):
        return 0
    if x >= float(upper):
        return 1
    if x <= float(lower):
        return -1
    return 0


def micro_status_age_weeks(
    cot: pd.DataFrame,
    *,
    upper: float = 80.0,
    lower: float = 20.0,
) -> int:
    """Consecutive COT weeks in the current 26W Commercial-index state."""
    if cot is None or cot.empty or "commercial_index" not in cot.columns:
        return 0

    values = pd.to_numeric(
        cot["commercial_index"],
        errors="coerce",
    ).dropna()
    if values.empty:
        return 0

    current = _micro_direction(
        values.iloc[-1],
        upper=upper,
        lower=lower,
    )

    age = 0
    for value in reversed(values.tolist()):
        if _micro_direction(value, upper=upper, lower=lower) != current:
            break
        age += 1
    return int(age)


def _transition_toward_release(
    pct: np.ndarray,
    index: int,
    zone: int,
) -> bool:
    if index < 0 or index >= len(pct) or zone == 0:
        return False

    current = pct[index]
    if not np.isfinite(current):
        return False

    d1 = (
        float(current - pct[index - 1])
        if index >= 1 and np.isfinite(pct[index - 1])
        else np.nan
    )
    d4 = (
        float(current - pct[index - 4])
        if index >= 4 and np.isfinite(pct[index - 4])
        else np.nan
    )

    if zone > 0:
        return (
            (np.isfinite(d1) and d1 < 0)
            or (np.isfinite(d4) and d4 < 0)
        )

    return (
        (np.isfinite(d1) and d1 > 0)
        or (np.isfinite(d4) and d4 > 0)
    )


def transition_status_age_weeks(
    cot: pd.DataFrame,
    *,
    upper: float = 80.0,
    lower: float = 20.0,
    extreme_direction: int = 0,
) -> int:
    """Consecutive EARLY RELEASE weeks inside the same 156W extreme."""
    if (
        cot is None
        or cot.empty
        or "commercial_net_percentile" not in cot.columns
    ):
        return 0

    valid = cot.dropna(
        subset=["commercial_net_percentile"]
    ).reset_index(drop=True)
    if valid.empty:
        return 0

    pct = pd.to_numeric(
        valid["commercial_net_percentile"],
        errors="coerce",
    ).to_numpy(dtype=float)

    last = len(pct) - 1
    current = pct[last]
    if not np.isfinite(current):
        return 0

    current_zone = (
        1
        if current >= float(upper)
        else -1
        if current <= float(lower)
        else 0
    )
    wanted = int(np.sign(extreme_direction or current_zone))

    if wanted == 0 or current_zone != wanted:
        return 0

    age = 0
    for i in range(last, -1, -1):
        value = pct[i]
        zone = (
            1
            if np.isfinite(value) and value >= float(upper)
            else -1
            if np.isfinite(value) and value <= float(lower)
            else 0
        )

        if zone != wanted:
            break
        if not _transition_toward_release(pct, i, wanted):
            break

        age += 1

    return int(age)


def macro_status_age_weeks(
    cot: pd.DataFrame,
    cycle: dict,
    *,
    upper: float = 80.0,
    lower: float = 20.0,
) -> int:
    """Age of the current Commercial macro phase.

    EXTREME -> uninterrupted 156W extreme episode.
    TRANSITION -> uninterrupted EARLY RELEASE run.
    RELEASE -> release week counts as week 1.

    CONFIRMED contains later cross-group/price context, so the watchlist
    intentionally displays the underlying Commercial release age there.
    """
    cycle = dict(cycle or {})
    phase = str(cycle.get("phase", "") or "").upper()
    transition = str(cycle.get("transition", "") or "").upper()

    if phase == "RELEASE":
        weeks = _finite(cycle.get("weeks_since_release"))
        if np.isfinite(weeks):
            return max(1, int(weeks) + 1)
        return 1

    if phase == "EXTREME" and "EARLY RELEASE" in transition:
        return transition_status_age_weeks(
            cot,
            upper=upper,
            lower=lower,
            extreme_direction=int(
                cycle.get("extreme_direction", 0) or 0
            ),
        )

    if phase == "EXTREME":
        duration = _finite(cycle.get("extreme_duration"))
        if np.isfinite(duration):
            return max(0, int(duration))

    return 0
