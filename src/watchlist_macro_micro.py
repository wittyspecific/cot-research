from __future__ import annotations

from typing import Any, Mapping

import numpy as np


UPPER = 80.0
LOWER = 20.0


def _finite(value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return np.nan
    return x if np.isfinite(x) else np.nan


def _direction_from_row(row: Mapping[str, Any]) -> int:
    for key in (
        "expected_direction",
        "context_direction",
        "extreme_direction",
        "dual_156w_direction",
    ):
        value = _finite(row.get(key))
        if np.isfinite(value) and value != 0:
            return int(np.sign(value))
    return 0


def macro_156w_state(row: Mapping[str, Any]) -> dict:
    """Slow structural context.

    Important hierarchy:
    - EXTREME is a warning / setup context, not an active macro trade bias.
    - TRANSITION is still pre-release.
    - RELEASE activates the macro direction.
    - CONFIRMED is the existing hard regime (stage >= 4).
    """
    direction = _direction_from_row(row)
    stage_value = _finite(row.get("regime_stage"))
    stage = max(0, int(stage_value)) if np.isfinite(stage_value) else 0
    cycle_phase = str(row.get("cycle_phase", "") or "").upper()
    transition = str(row.get("transition_state", "") or "").upper()
    dual_direction_value = _finite(row.get("dual_156w_direction"))
    dual_direction = (
        int(np.sign(dual_direction_value))
        if np.isfinite(dual_direction_value)
        else 0
    )

    if stage >= 4 and direction != 0:
        phase = "CONFIRMED"
        active = True
    elif cycle_phase == "RELEASE" and direction != 0:
        phase = "RELEASE"
        active = True
    elif "EARLY RELEASE" in transition and direction != 0:
        phase = "TRANSITION"
        active = False
    elif (
        cycle_phase == "EXTREME"
        or dual_direction != 0
    ) and direction != 0:
        phase = "EXTREME"
        active = False
    else:
        phase = "NEUTRAL"
        active = False
        direction = 0

    direction_text = (
        "BULLISH" if direction > 0
        else "BEARISH" if direction < 0
        else "NEUTRAL"
    )

    label = (
        f"{direction_text} {phase}"
        if phase != "NEUTRAL"
        else "NEUTRAL"
    )

    return {
        "direction": int(direction),
        "phase": phase,
        "label": label,
        "active": bool(active),
    }


def micro_26w_state(
    row: Mapping[str, Any],
    *,
    upper: float = 90.0,
    lower: float = 10.0,
) -> dict:
    """Event-based 26W Commercial micro timing.

    Production rows carry the real last 90/10 ENTRY event from full history.
    Only 0-2W old triggers are trade-active. For isolated unit/snapshot rows
    without trigger metadata, current 90/10 is treated as a same-week fallback.
    """
    has_metadata = "micro_trigger_direction" in row

    if has_metadata:
        direction_value = _finite(row.get("micro_trigger_direction"))
        direction = (
            int(np.sign(direction_value))
            if np.isfinite(direction_value)
            else 0
        )
        age_value = _finite(row.get("micro_trigger_age_weeks"))
        age_weeks = int(age_value) if np.isfinite(age_value) else -1
        fresh = bool(row.get("micro_trigger_fresh", False))
        trigger_value = _finite(row.get("micro_trigger_value"))
        current_value = _finite(row.get("micro_current_index_26w"))
        if not np.isfinite(current_value):
            current_value = _finite(row.get("commercial_index"))
    else:
        current_value = _finite(row.get("dual_commercial_index_26w"))
        if not np.isfinite(current_value):
            current_value = _finite(row.get("commercial_index"))
        if np.isfinite(current_value) and current_value >= upper:
            direction, age_weeks, fresh, trigger_value = 1, 0, True, current_value
        elif np.isfinite(current_value) and current_value <= lower:
            direction, age_weeks, fresh, trigger_value = -1, 0, True, current_value
        else:
            direction, age_weeks, fresh, trigger_value = 0, -1, False, np.nan

    fresh = bool(fresh and direction != 0 and 0 <= age_weeks <= 2)

    if direction == 0:
        return {
            "direction": 0,
            "trade_direction": 0,
            "label": "—",
            "age_weeks": -1,
            "fresh": False,
            "value": current_value,
            "trigger_value": np.nan,
        }

    return {
        "direction": int(direction),
        "trade_direction": int(direction if fresh else 0),
        "label": "BULLISH TRIGGER" if direction > 0 else "BEARISH TRIGGER",
        "age_weeks": int(age_weeks),
        "fresh": fresh,
        "value": current_value,
        "trigger_value": trigger_value,
    }



def classify_macro_micro_trade(row: Mapping[str, Any]) -> dict:
    """Macro leads after RELEASE; only a fresh 90/10 micro trigger leads before it."""
    macro = macro_156w_state(row)
    micro = micro_26w_state(row)

    macro_dir = int(macro["direction"])
    micro_dir = int(micro.get("trade_direction", 0) or 0)

    if macro["active"] and macro_dir != 0:
        if micro_dir == macro_dir:
            bias = "LONG" if macro_dir > 0 else "SHORT"
            plan = "Longs suchen" if macro_dir > 0 else "Shorts suchen"
            signal = "ALIGNED"
            bias_direction = macro_dir
        elif micro_dir == -macro_dir:
            bias = "LONG BIAS" if macro_dir > 0 else "SHORT BIAS"
            plan = "Korrektur abwarten" if macro_dir > 0 else "Anstieg abwarten"
            signal = "WATCH"
            bias_direction = macro_dir
        else:
            bias = "LONG BIAS" if macro_dir > 0 else "SHORT BIAS"
            plan = "Frischen Mikro-Trigger abwarten"
            signal = "WATCH"
            bias_direction = macro_dir

    elif micro_dir != 0:
        bias_direction = micro_dir
        bias = "LONG" if micro_dir > 0 else "SHORT"

        if macro_dir == -micro_dir and macro["phase"] in {"EXTREME", "TRANSITION"}:
            plan = (
                "Anstieg handeln · Release beobachten"
                if micro_dir > 0
                else "Korrektur handeln · Release beobachten"
            )
        elif macro_dir == micro_dir and macro["phase"] in {"EXTREME", "TRANSITION"}:
            plan = (
                "Longs suchen · Makro noch Watch"
                if micro_dir > 0
                else "Shorts suchen · Makro noch Watch"
            )
        else:
            plan = "Longs suchen" if micro_dir > 0 else "Shorts suchen"
        signal = "WATCH"

    else:
        bias_direction = 0
        bias = "WAIT"
        plan = (
            "Frischen Mikro-Trigger abwarten"
            if macro["phase"] in {"EXTREME", "TRANSITION"}
            else "Warten"
        )
        signal = "NEUTRAL"

    return {
        "macro": macro,
        "micro": micro,
        "bias": bias,
        "bias_direction": int(bias_direction),
        "plan": plan,
        "signal": signal,
    }
