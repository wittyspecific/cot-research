import numpy as np
import pandas as pd

from src.positioning_robustness import (
    candidate_overlap_table,
    flow_monotonicity_diagnostic,
    incremental_value_table,
    monotonicity_summary,
    scan_parameter_robustness,
)


def _overlap_events():
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
            }
        )
    return pd.DataFrame(rows)


def test_event_overlap_detects_equivalent_flow_filters():
    events = _overlap_events()
    scan, _ = scan_parameter_robustness(
        events,
        horizon_weeks=8,
        flow_features=(
            "pct_release_velocity_2w",
            "raw_release_velocity_2w",
        ),
        flow_quantiles=(0.50,),
        min_train=4,
        min_validation=2,
    )

    overlap = candidate_overlap_table(events, scan, top_n=4)
    assert not overlap.empty
    assert np.isclose(overlap.iloc[0]["jaccard"], 1.0)
    assert overlap.iloc[0]["interpretation"] == "NAHEZU GLEICHE EVENTS"


def test_incremental_value_compares_flow_to_exact_state_baseline():
    events = _overlap_events()
    scan, _ = scan_parameter_robustness(
        events,
        horizon_weeks=8,
        flow_features=("pct_release_velocity_2w",),
        flow_quantiles=(0.50,),
        min_train=4,
        min_validation=2,
    )

    table = incremental_value_table(scan)
    assert len(table) == 1
    row = table.iloc[0]
    assert row["parameter"] == "156W · 80/20"
    assert np.isfinite(row["validation_median_lift"])
    assert 0 < row["validation_sample_retention"] <= 1


def test_monotonicity_uses_train_bins_and_excludes_oos():
    dates = pd.date_range("2010-01-05", periods=40, freq="70D")
    rows = []
    for i, date in enumerate(dates):
        if i < 32:
            flow = float(i + 1)
            ret = flow / 1000.0
        else:
            flow = float(1000 + i)
            ret = -1.0

        rows.append(
            {
                "release_report_date": date,
                "release_available": True,
                "window_weeks": 156,
                "threshold_upper": 80.0,
                "threshold_lower": 20.0,
                "directional_return_8w": ret,
                "pct_release_velocity_2w": flow,
            }
        )

    events = pd.DataFrame(rows)
    scan, _ = scan_parameter_robustness(
        events,
        horizon_weeks=8,
        flow_features=("pct_release_velocity_2w",),
        flow_quantiles=(0.50,),
        min_train=4,
        min_validation=2,
    )
    candidate = scan[scan["candidate_type"] == "FLOW"].iloc[0]

    diagnostic = flow_monotonicity_diagnostic(events, candidate)
    summary = monotonicity_summary(diagnostic)

    assert not diagnostic.empty
    assert "oos_median" not in diagnostic.columns
    assert summary["train_positive_steps"] >= 2 / 3
    assert int(diagnostic["n_validation"].sum()) == 8
    assert int(diagnostic.iloc[-1]["n_validation"]) == 8
