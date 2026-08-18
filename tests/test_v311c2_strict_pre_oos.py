import numpy as np
import pandas as pd
import pytest

from src.positioning_robustness import (
    distinct_candidate_shortlist,
    overlap_redundancy_summary,
    scan_parameter_robustness,
    strict_monotonicity_assessment,
)


def test_strict_monotonicity_rejects_two_of_three_step_pattern():
    diagnostic = pd.DataFrame(
        {
            "bucket": ["Q1", "Q2", "Q3", "Q4"],
            "train_median": [-0.0169, 0.0261, -0.0183, 0.0054],
            "validation_median": [-0.0262, 0.0216, -0.0220, 0.0007],
        }
    )
    result = strict_monotonicity_assessment(diagnostic)
    assert result["train_positive_steps"] == pytest.approx(2 / 3)
    assert result["validation_positive_steps"] == pytest.approx(2 / 3)
    assert result["train_ordered"] is False
    assert result["validation_ordered"] is False
    assert result["verdict"] not in {
        "STRONG REPLICATED EFFECT",
        "MODERATE REPLICATED EFFECT",
    }


def test_strict_monotonicity_accepts_fully_ordered_replication():
    diagnostic = pd.DataFrame(
        {
            "bucket": ["Q1", "Q2", "Q3", "Q4"],
            "train_median": [-0.02, 0.00, 0.02, 0.05],
            "validation_median": [-0.01, 0.01, 0.03, 0.06],
        }
    )
    result = strict_monotonicity_assessment(diagnostic)
    assert result["train_ordered"] is True
    assert result["validation_ordered"] is True
    assert result["train_spearman"] == pytest.approx(1.0)
    assert result["validation_spearman"] == pytest.approx(1.0)
    assert result["train_q4_q1_spread"] == pytest.approx(0.07)
    assert result["validation_q4_q1_spread"] == pytest.approx(0.07)
    assert result["verdict"] == "STRONG REPLICATED EFFECT"


def test_strict_monotonicity_refuses_oos_columns():
    diagnostic = pd.DataFrame(
        {
            "bucket": ["Q1", "Q2", "Q3", "Q4"],
            "train_median": [0.0, 0.1, 0.2, 0.3],
            "validation_median": [0.0, 0.1, 0.2, 0.3],
            "oos_median": [1.0, 1.0, 1.0, 1.0],
        }
    )
    with pytest.raises(ValueError):
        strict_monotonicity_assessment(diagnostic)


def _events():
    dates = pd.date_range("2010-01-05", periods=40, freq="70D")
    rows = []
    for i, date in enumerate(dates):
        flow = float(i + 1)
        rows.append(
            {
                "release_report_date": date,
                "release_available": True,
                "window_weeks": 156,
                "threshold_upper": 80.0,
                "threshold_lower": 20.0,
                "directional_return_8w": 0.002 + flow / 10000.0,
                "pct_release_velocity_2w": flow,
                "raw_release_velocity_2w": flow * 100.0,
                "pct_release_acceleration": flow if i % 2 == 0 else -flow,
            }
        )
    return pd.DataFrame(rows)


def test_shortlist_deduplicates_nearly_identical_flow_hypotheses():
    events = _events()
    scan, _ = scan_parameter_robustness(
        events,
        horizon_weeks=8,
        flow_features=(
            "pct_release_velocity_2w",
            "raw_release_velocity_2w",
            "pct_release_acceleration",
        ),
        flow_quantiles=(0.50,),
        min_train=4,
        min_validation=2,
    )
    shortlist = distinct_candidate_shortlist(
        events,
        scan,
        max_total=4,
        overlap_threshold=0.80,
    )
    flow_features = list(
        shortlist.loc[shortlist["candidate_type"].eq("FLOW"), "feature"]
    )
    assert not (
        "pct_release_velocity_2w" in flow_features
        and "raw_release_velocity_2w" in flow_features
    )

    summary = overlap_redundancy_summary(
        events,
        scan,
        top_n=6,
        overlap_threshold=0.80,
    )
    assert summary["redundant_pairs"] >= 1
