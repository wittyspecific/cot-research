import pandas as pd

from src.positioning_robustness import frozen_candidates_from_scan


def _scan():
    return pd.DataFrame(
        [
            {
                "candidate_type": "STATE",
                "window_weeks": 156,
                "threshold_upper": 70.0,
                "threshold_lower": 30.0,
                "feature": "STATE",
                "flow_quantile": None,
                "rank_train_validation": 1,
                "robustness_score": 85.0,
                "oos_median": 0.01,
            },
            {
                "candidate_type": "FLOW",
                "window_weeks": 104,
                "threshold_upper": 95.0,
                "threshold_lower": 5.0,
                "feature": "pct_release_velocity_4w",
                "flow_quantile": 0.50,
                "rank_train_validation": 2,
                "robustness_score": 79.5,
                "oos_median": -0.02,
            },
            {
                "candidate_type": "FLOW",
                "window_weeks": 104,
                "threshold_upper": 95.0,
                "threshold_lower": 5.0,
                "feature": "raw_release_velocity_2w",
                "flow_quantile": 0.50,
                "rank_train_validation": 3,
                "robustness_score": 79.5,
                "oos_median": 9.99,
            },
            {
                "candidate_type": "FLOW",
                "window_weeks": 104,
                "threshold_upper": 75.0,
                "threshold_lower": 25.0,
                "feature": "pct_release_acceleration",
                "flow_quantile": 0.50,
                "rank_train_validation": 4,
                "robustness_score": 78.9,
                "oos_median": 0.03,
            },
        ]
    )


def _snapshot():
    return {
        "candidates": [
            {
                "candidate_type": "STATE",
                "window_weeks": 156,
                "threshold_upper": 70.0,
                "threshold_lower": 30.0,
                "feature": "STATE",
                "flow_quantile": None,
            },
            {
                "candidate_type": "FLOW",
                "window_weeks": 104,
                "threshold_upper": 95.0,
                "threshold_lower": 5.0,
                "feature": "pct_release_velocity_4w",
                "flow_quantile": 0.50,
            },
            {
                "candidate_type": "FLOW",
                "window_weeks": 104,
                "threshold_upper": 75.0,
                "threshold_lower": 25.0,
                "feature": "pct_release_acceleration",
                "flow_quantile": 0.50,
            },
        ]
    }


def test_frozen_only_reveal_excludes_rejected_raw_velocity():
    frozen = frozen_candidates_from_scan(_scan(), _snapshot())
    assert len(frozen) == 3
    assert "raw_release_velocity_2w" not in set(frozen["feature"])
    assert list(frozen["frozen_order"]) == [1, 2, 3]


def test_unfrozen_oos_winner_cannot_enter_reveal():
    frozen = frozen_candidates_from_scan(_scan(), _snapshot())
    assert 9.99 not in set(frozen["oos_median"])
