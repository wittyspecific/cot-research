import pandas as pd

from src.positioning_robustness import (
    candidate_freeze_id,
    candidate_review_label,
    reviewed_shortlist,
)


def _shortlist():
    return pd.DataFrame(
        [
            {
                "shortlist_rank": 1,
                "candidate_type": "STATE",
                "window_weeks": 156,
                "threshold_upper": 70.0,
                "threshold_lower": 30.0,
                "feature": "STATE",
                "flow_quantile": None,
                "robustness_score": 85.0,
            },
            {
                "shortlist_rank": 2,
                "candidate_type": "FLOW",
                "window_weeks": 104,
                "threshold_upper": 95.0,
                "threshold_lower": 5.0,
                "feature": "pct_release_velocity_4w",
                "flow_quantile": 0.50,
                "robustness_score": 79.5,
            },
            {
                "shortlist_rank": 3,
                "candidate_type": "FLOW",
                "window_weeks": 104,
                "threshold_upper": 95.0,
                "threshold_lower": 5.0,
                "feature": "raw_release_velocity_2w",
                "flow_quantile": 0.50,
                "robustness_score": 79.5,
            },
            {
                "shortlist_rank": 4,
                "candidate_type": "FLOW",
                "window_weeks": 104,
                "threshold_upper": 75.0,
                "threshold_lower": 25.0,
                "feature": "pct_release_acceleration",
                "flow_quantile": 0.50,
                "robustness_score": 78.9,
            },
        ]
    )


def test_reviewed_shortlist_can_exclude_raw_velocity():
    frame = _shortlist()
    keep = [
        candidate_freeze_id(frame.iloc[0]),
        candidate_freeze_id(frame.iloc[1]),
        candidate_freeze_id(frame.iloc[3]),
    ]
    reviewed = reviewed_shortlist(frame, keep)

    assert len(reviewed) == 3
    assert "raw_release_velocity_2w" not in set(reviewed["feature"])
    assert list(reviewed["shortlist_rank"]) == [1, 2, 4]


def test_candidate_id_is_stable_and_label_is_human_readable():
    row = _shortlist().iloc[3]
    assert candidate_freeze_id(row) == candidate_freeze_id(row.copy())
    label = candidate_review_label(row)
    assert "104W" in label
    assert "75/25" in label
    assert "Percentile Acceleration" in label
    assert "78.9" in label
