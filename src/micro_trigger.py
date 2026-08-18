from __future__ import annotations

import numpy as np
import pandas as pd

MICRO_TRIGGER_UPPER = 90.0
MICRO_TRIGGER_LOWER = 10.0
MICRO_TRIGGER_FRESH_WEEKS = 2


def latest_micro_trigger(
    cot: pd.DataFrame,
    *,
    upper: float = MICRO_TRIGGER_UPPER,
    lower: float = MICRO_TRIGGER_LOWER,
    fresh_weeks: int = MICRO_TRIGGER_FRESH_WEEKS,
) -> dict:
    """Most recent 26W Commercial COT-index ENTRY into a strict 90/10 zone."""
    empty = {
        "direction": 0,
        "label": "—",
        "age_weeks": -1,
        "fresh": False,
        "trigger_value": np.nan,
        "current_value": np.nan,
        "trigger_report_date": pd.NaT,
    }
    if cot is None or cot.empty or "commercial_index" not in cot.columns:
        return dict(empty)

    frame = cot.copy()
    frame["commercial_index"] = pd.to_numeric(
        frame["commercial_index"], errors="coerce"
    )
    frame = frame.dropna(subset=["commercial_index"]).reset_index(drop=True)
    if frame.empty:
        return dict(empty)

    values = frame["commercial_index"].to_numpy(dtype=float)
    current_value = float(values[-1])
    last_event = None

    for i in range(1, len(values)):
        previous = float(values[i - 1])
        current = float(values[i])
        if previous < float(upper) and current >= float(upper):
            last_event = (i, 1, current)
        elif previous > float(lower) and current <= float(lower):
            last_event = (i, -1, current)

    if last_event is None:
        out = dict(empty)
        out["current_value"] = current_value
        return out

    event_index, direction, trigger_value = last_event
    age_weeks = int((len(values) - 1) - event_index)
    report_date = pd.NaT
    if "report_date" in frame.columns:
        report_date = pd.to_datetime(
            frame.iloc[event_index]["report_date"], errors="coerce"
        )

    return {
        "direction": int(direction),
        "label": "BULLISH TRIGGER" if direction > 0 else "BEARISH TRIGGER",
        "age_weeks": age_weeks,
        "fresh": bool(age_weeks <= max(0, int(fresh_weeks))),
        "trigger_value": float(trigger_value),
        "current_value": current_value,
        "trigger_report_date": report_date,
    }
