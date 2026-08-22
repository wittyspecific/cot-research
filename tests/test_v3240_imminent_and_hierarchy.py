
from pathlib import Path

import pandas as pd

from src.macro.config import load_config
from src.macro.imminent_recession import (
    evaluate_imminent_recession,
)


def _frames():
    idx = pd.date_range(
        "2024-01-05",
        periods=120,
        freq="W-FRI",
    )

    scores = pd.DataFrame(
        {
            "US2Y Change 13W": [-80.0] * len(idx),
            "Initial Claims 4W": [-70.0] * len(idx),
            "Initial Claims 13W": [-70.0] * len(idx),
            "Unemployment 6M Change": [-60.0] * len(idx),
            "Continuing Claims 13W": [-60.0] * len(idx),
            "Payroll 3M Average Change": [-60.0] * len(idx),
            "High Yield OAS 13W": [-60.0] * len(idx),
            "NFCI 13W Change": [-60.0] * len(idx),
        },
        index=idx,
    )

    raw = pd.DataFrame(
        {
            "10Y-2Y Yield Spread": (
                [-1.0] * 60
                + [0.0] * 20
                + [0.8] * 40
            ),
            "10Y-3M Yield Spread": (
                [-1.2] * 60
                + [-0.1] * 20
                + [0.7] * 40
            ),
        },
        index=idx,
    )

    cycle = pd.DataFrame(
        {
            "coincident_distance": [5.0] * len(idx),
            "coincident_slope_13w": [-10.0] * len(idx),
        },
        index=idx,
    )

    return scores, raw, cycle


def test_imminent_cluster_is_disabled_outside_slowdown():
    cfg = load_config(
        Path("/definitely/missing.toml")
    )
    scores, raw, cycle = _frames()

    result = evaluate_imminent_recession(
        cycle_phase="EXPANSION",
        weekly_scores=scores,
        weekly_raw=raw,
        cycle_history=cycle,
        config=cfg,
    )

    assert result["phase_gate_active"] is False
    assert result["active_count"] == 0
    assert result["observed_count"] >= 4
    assert result["state"] == "INACTIVE_OUTSIDE_SLOWDOWN"


def test_imminent_cluster_activates_during_slowdown():
    cfg = load_config(
        Path("/definitely/missing.toml")
    )
    scores, raw, cycle = _frames()

    result = evaluate_imminent_recession(
        cycle_phase="SLOWDOWN",
        weekly_scores=scores,
        weekly_raw=raw,
        cycle_history=cycle,
        config=cfg,
    )

    assert result["phase_gate_active"] is True
    assert result["active_count"] >= 5
    assert result["state"] == "IMMINENT"
