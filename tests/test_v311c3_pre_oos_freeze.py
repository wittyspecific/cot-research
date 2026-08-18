import json

import pandas as pd

from src.positioning_robustness import (
    build_pre_oos_freeze_snapshot,
    freeze_snapshot_json,
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
                "flow_cutoff_train": None,
                "robustness_score": 85.0,
                "n_train": 28,
                "train_median": 0.012,
                "n_validation": 7,
                "validation_median": 0.0066,
                "neighbor_positive_share": 0.67,
                "shortlist_reason": "STRUCTURAL BASELINE",
                "max_overlap_with_selected_flow": None,
                "n_oos": 99,
                "oos_median": 9.99,
            },
            {
                "shortlist_rank": 2,
                "candidate_type": "FLOW",
                "window_weeks": 104,
                "threshold_upper": 75.0,
                "threshold_lower": 25.0,
                "feature": "pct_release_acceleration",
                "flow_quantile": 0.50,
                "flow_cutoff_train": 1.23,
                "robustness_score": 78.9,
                "n_train": 18,
                "train_median": 0.0148,
                "n_validation": 5,
                "validation_median": 0.0065,
                "neighbor_positive_share": 0.67,
                "shortlist_reason": "DISTINCT FLOW HYPOTHESIS",
                "max_overlap_with_selected_flow": 0.05,
                "n_oos": 77,
                "oos_median": -8.88,
            },
        ]
    )


def test_freeze_snapshot_excludes_oos_and_contains_hash():
    snap = build_pre_oos_freeze_snapshot(
        _shortlist(),
        market_name="Japanischer Yen",
        group_key="dealer",
        basis="net_oi",
        horizon_weeks=8,
    )
    text = freeze_snapshot_json(snap).decode("utf-8")

    assert snap["oos_used_for_selection"] is False
    assert len(snap["freeze_hash_sha256"]) == 64
    assert "oos_median" not in text
    assert "n_oos" not in text
    assert "Japanischer Yen" in text


def test_freeze_json_contains_exact_shortlist():
    snap = build_pre_oos_freeze_snapshot(
        _shortlist(),
        market_name="JPY",
        group_key="dealer",
        basis="raw",
        horizon_weeks=8,
    )
    parsed = json.loads(freeze_snapshot_json(snap))
    assert len(parsed["candidates"]) == 2
    assert parsed["candidates"][0]["window_weeks"] == 156
    assert parsed["candidates"][1]["feature"] == "pct_release_acceleration"
