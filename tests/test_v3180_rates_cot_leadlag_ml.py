from pathlib import Path
import ast

import numpy as np
import pandas as pd

from src.rates_cot_ml import (
    _attach_targets,
    _episode_baseline,
    _historical_move_stats_asof,
)


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "rates_cot_ml.py"
PAGE = ROOT / "pages" / "forex_matrix.py"
REQ = ROOT / "requirements.txt"


def test_historical_rates_percentile_is_asof_and_ignores_future_spike():
    idx = pd.date_range("2020-01-01", periods=1400, freq="B")
    values = pd.Series(np.arange(1400, dtype=float) * 0.001, index=idx)
    values.iloc[-1] += 10.0

    earlier = _historical_move_stats_asof(values, idx[-50], 20)
    latest = _historical_move_stats_asof(values, idx[-1], 20)

    assert np.isfinite(earlier["percentile"])
    assert np.isfinite(latest["percentile"])
    assert latest["percentile"] >= earlier["percentile"]


def test_targets_only_use_future_cot_states():
    dates = pd.date_range("2025-01-07", periods=12, freq="7D")
    history = pd.DataFrame(
        {
            "currency": ["NZD"] * len(dates),
            "available_date": dates,
            "cot_phase": [
                "RELEASE", "RELEASE", "RELEASE", "TRANSITION",
                "TRANSITION", "RELEASE", "RELEASE", "RELEASE",
                "RELEASE", "RELEASE", "RELEASE", "RELEASE",
            ],
            "cot_direction": [
                1, 1, 1, -1, -1, -1,
                -1, -1, -1, -1, -1, -1,
            ],
        }
    )
    events = pd.DataFrame(
        [
            {
                "currency": "NZD",
                "available_date": dates[0],
                "rates_direction": -1,
                "relation": "CONFLICT",
            }
        ]
    )

    out = _attach_targets(events, {"NZD": history})
    assert out.loc[0, "transition_4w"] == 1
    assert out.loc[0, "release_6w"] == 1
    assert out.loc[0, "transition_lead_days_8w"] > 0


def test_episode_baseline_uses_one_row_per_event():
    frame = pd.DataFrame(
        {
            "relation": ["CONFLICT", "COT_NEUTRAL"],
            "release_2w": [0, 1],
            "release_4w": [1, 1],
            "release_6w": [1, 1],
            "release_8w": [1, 1],
            "transition_6w": [1, 1],
            "release_lead_days_8w": [21, 7],
        }
    )
    baseline = _episode_baseline(frame)
    all_row = baseline[baseline["Gruppe"].eq("ALL")].iloc[0]
    assert int(all_row["Episoden"]) == 2
    assert all_row["Release ≤2W"] == 0.5


def test_page_contains_on_demand_ml_research():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.18.0 · RATES COT LEAD LAG ML" in text
    assert "Rates → COT Lead/Lag ML" in text
    assert "ML-Studie starten" in text
    assert "Walk-forward" in text
    assert "kein Trade-Signal" in text


def test_requirement_contains_scikit_learn():
    text = REQ.read_text(encoding="utf-8").lower()
    assert "scikit-learn" in text


def test_files_parse():
    for path in (ENGINE, PAGE):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
