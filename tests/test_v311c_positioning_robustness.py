import numpy as np
import pandas as pd

from src.positioning_robustness import (
    add_research_time_split,
    scan_parameter_robustness,
    scanner_findings,
)


def _events_for_two_candidates():
    dates = pd.date_range("2010-01-05", periods=30, freq="91D")
    rows = []
    for i, date in enumerate(dates):
        if i < 18:
            a_ret = 0.030
            b_ret = 0.010
        elif i < 24:
            a_ret = 0.020
            b_ret = -0.005
        else:
            # Candidate A deliberately collapses OOS while candidate B becomes
            # fantastic. Ranking must still prefer A because OOS is locked out.
            a_ret = -0.200
            b_ret = 0.500

        rows.append(
            {
                "release_report_date": date,
                "release_available": True,
                "window_weeks": 156,
                "threshold_upper": 90.0,
                "threshold_lower": 10.0,
                "directional_return_8w": a_ret,
            }
        )
        rows.append(
            {
                "release_report_date": date,
                "release_available": True,
                "window_weeks": 104,
                "threshold_upper": 80.0,
                "threshold_lower": 20.0,
                "directional_return_8w": b_ret,
            }
        )
    return pd.DataFrame(rows)


def test_shared_time_split_keeps_same_date_in_same_segment():
    events = _events_for_two_candidates()
    split, meta = add_research_time_split(events)

    assert meta["enough_history"] is True
    per_date = split.groupby("release_report_date")["research_split"].nunique()
    assert int(per_date.max()) == 1
    assert set(split["research_split"].dropna()) == {"TRAIN", "VALIDATION", "OOS"}


def test_scanner_does_not_use_oos_to_rank_candidates():
    events = _events_for_two_candidates()
    scan, meta = scan_parameter_robustness(
        events,
        horizon_weeks=8,
        flow_features=(),
        min_train=8,
        min_validation=4,
    )

    assert meta["oos_used_in_score"] is False

    states = scan[scan["candidate_type"] == "STATE"].copy()
    top = states.sort_values("rank_train_validation").iloc[0]

    assert int(top["window_weeks"]) == 156
    assert float(top["threshold_upper"]) == 90.0
    assert top["validation_median"] > 0
    assert top["oos_median"] < 0


def test_flow_cutoff_is_estimated_from_train_only():
    dates = pd.date_range("2010-01-05", periods=30, freq="91D")
    values = []
    rows = []

    # First 60% has small velocity values. Later periods contain huge values.
    # A leaking full-sample quantile would therefore be far above the Train cutoff.
    for i, date in enumerate(dates):
        flow = float(i + 1) if i < 18 else float(1000 + i)
        values.append(flow)
        rows.append(
            {
                "release_report_date": date,
                "release_available": True,
                "window_weeks": 156,
                "threshold_upper": 80.0,
                "threshold_lower": 20.0,
                "directional_return_8w": 0.01,
                "pct_release_velocity_2w": flow,
            }
        )

    events = pd.DataFrame(rows)
    split, _ = add_research_time_split(events)
    train_values = split.loc[
        split["research_split"] == "TRAIN",
        "pct_release_velocity_2w",
    ]
    expected = float(train_values.quantile(0.75))
    leaking = float(events["pct_release_velocity_2w"].quantile(0.75))

    scan, _ = scan_parameter_robustness(
        events,
        horizon_weeks=8,
        flow_features=("pct_release_velocity_2w",),
        flow_quantiles=(0.75,),
        min_train=4,
        min_validation=2,
    )

    flow = scan[scan["candidate_type"] == "FLOW"].iloc[0]
    assert np.isclose(flow["flow_cutoff_train"], expected)
    assert not np.isclose(flow["flow_cutoff_train"], leaking)


def test_scanner_reports_parameter_neighborhood_and_findings():
    dates = pd.date_range("2010-01-05", periods=30, freq="91D")
    rows = []
    for window in (104, 156, 208):
        for threshold in (80.0, 90.0):
            for date in dates:
                rows.append(
                    {
                        "release_report_date": date,
                        "release_available": True,
                        "window_weeks": window,
                        "threshold_upper": threshold,
                        "threshold_lower": 100.0 - threshold,
                        "directional_return_8w": 0.02,
                    }
                )

    scan, _ = scan_parameter_robustness(
        pd.DataFrame(rows),
        horizon_weeks=8,
        flow_features=(),
        min_train=8,
        min_validation=4,
    )

    assert scan["neighbor_count"].max() > 0
    assert np.isclose(
        scan.loc[scan["neighbor_count"] > 0, "neighbor_positive_share"].min(),
        1.0,
    )

    findings = scanner_findings(scan)
    assert findings["top_state"] is not None
    assert findings["eligible_count"] > 0
