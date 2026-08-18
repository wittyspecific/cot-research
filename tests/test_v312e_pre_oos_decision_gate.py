import numpy as np
import pandas as pd

from src.positioning_cross_market import (
    candidate_flow_overlap,
    evaluate_pre_oos_decision_gate,
    fixed_parameter_region_matrix,
)


def _candidate(**updates):
    row = {
        "candidate_type": "FLOW",
        "window_weeks": 156,
        "threshold_upper": 75.0,
        "threshold_lower": 25.0,
        "feature": "raw_release_velocity_1w",
        "flow_quantile": 0.50,
        "horizon_weeks": 8,
        "markets_eligible": 5,
        "positive_validation_markets": 4,
        "positive_validation_share": 0.80,
        "train_validation_positive_share": 0.80,
        "median_n_validation": 6.0,
        "cross_market_rank": 1,
    }
    row.update(updates)
    return row


def test_current_like_candidate_is_hold_when_region_is_point_unstable():
    result = evaluate_pre_oos_decision_gate(
        _candidate(),
        selected_markets_total=7,
        loaded_markets_total=6,
        lomo_summary={
            "stable": True,
            "worst_score": 76.4,
            "max_abs_delta": 10.8,
            "positive_share_min": 0.75,
        },
        neighborhood_summary={
            "stable_region": False,
            "positive_neighbor_share": 0.25,
            "median_neighbor_score": 57.4,
        },
        max_median_jaccard=0.69,
    )

    assert result["verdict"] == "HOLD"
    region = result["criteria"][
        result["criteria"]["criterion"] == "Parameter Region"
    ].iloc[0]
    assert region["status"] == "FAIL"


def test_incomplete_core_fx_selection_cannot_pass():
    result = evaluate_pre_oos_decision_gate(
        _candidate(),
        selected_markets_total=6,
        loaded_markets_total=6,
        lomo_summary={
            "stable": True,
            "worst_score": 80.0,
            "max_abs_delta": 5.0,
            "positive_share_min": 0.75,
        },
        neighborhood_summary={
            "stable_region": True,
            "positive_neighbor_share": 0.75,
            "median_neighbor_score": 75.0,
        },
        max_median_jaccard=0.50,
    )

    assert result["verdict"] == "HOLD"
    assert not result["universe_complete"]


def test_full_stable_candidate_can_pass():
    result = evaluate_pre_oos_decision_gate(
        _candidate(),
        selected_markets_total=7,
        loaded_markets_total=7,
        lomo_summary={
            "stable": True,
            "worst_score": 78.0,
            "max_abs_delta": 7.0,
            "positive_share_min": 0.75,
        },
        neighborhood_summary={
            "stable_region": True,
            "positive_neighbor_share": 0.75,
            "median_neighbor_score": 70.0,
        },
        max_median_jaccard=0.50,
    )

    assert result["verdict"] == "PASS"
    assert result["fail_count"] == 0
    assert result["watch_count"] == 0


def test_fixed_region_matrix_uses_only_declared_3x3_grid():
    rows = []
    for window in (104, 156, 208):
        for threshold in (70.0, 75.0, 80.0):
            rows.append(
                {
                    **_candidate(
                        window_weeks=window,
                        threshold_upper=threshold,
                        threshold_lower=100.0-threshold,
                    ),
                    "cross_market_score": 70.0,
                    "cross_market_status": "PROMISING ACROSS MARKETS",
                    "median_validation_return": 0.01,
                }
            )

    cross = pd.DataFrame(rows)
    matrix = fixed_parameter_region_matrix(
        cross,
        _candidate(),
    )

    assert len(matrix) == 9
    assert set(matrix["window_weeks"]) == {104, 156, 208}
    assert set(matrix["threshold_upper"]) == {70.0, 75.0, 80.0}
    assert matrix["available"].all()


def test_candidate_flow_overlap_returns_selected_candidates_max_pair():
    redundancy = pd.DataFrame(
        [
            {
                "rank_a": 1,
                "rank_b": 2,
                "median_jaccard": 0.69,
            },
            {
                "rank_a": 1,
                "rank_b": 3,
                "median_jaccard": 0.27,
            },
            {
                "rank_a": 2,
                "rank_b": 3,
                "median_jaccard": 0.30,
            },
        ]
    )

    result = candidate_flow_overlap(redundancy, 1)
    assert np.isclose(result["max_median_jaccard"], 0.69)
    assert result["counterpart_rank"] == 2
