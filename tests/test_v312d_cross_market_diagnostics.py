import numpy as np
import pandas as pd

from src.positioning_cross_market import (
    aggregate_cross_market_scans,
    cross_market_coverage_diagnostic,
    cross_market_flow_redundancy,
    cross_market_leave_one_out,
    cross_market_neighborhood_summary,
    cross_market_parameter_neighborhood,
    leave_one_out_summary,
)


def _scan_row(
    *,
    window=156,
    threshold=75.0,
    feature="raw_release_velocity_1w",
    q=0.50,
    val=0.01,
    train=0.01,
    cutoff=5.0,
    score=80.0,
):
    return {
        "candidate_type": "FLOW",
        "window_weeks": window,
        "threshold_upper": threshold,
        "threshold_lower": 100.0 - threshold,
        "feature": feature,
        "flow_quantile": q,
        "horizon_weeks": 8,
        "sample_ok": True,
        "n_train": 12,
        "train_median": train,
        "train_hit_rate": 0.60,
        "n_validation": 6,
        "validation_median": val,
        "validation_hit_rate": 0.60 if val > 0 else 0.40,
        "neighbor_positive_share": 0.75,
        "robustness_score": score,
        "rank_train_validation": 1,
        "status": "ROBUST CANDIDATE",
        "flow_cutoff_train": cutoff,
        "oos_median": 999.0,
    }


def _events():
    dates = pd.date_range("2010-01-05", periods=30, freq="70D")
    rows = []
    for i, date in enumerate(dates):
        rows.append(
            {
                "release_report_date": date,
                "release_available": True,
                "window_weeks": 156,
                "threshold_upper": 75.0,
                "threshold_lower": 25.0,
                "raw_release_velocity_1w": float(i),
                "raw_release_velocity_2w": float(i),
            }
        )
    return pd.DataFrame(rows)


def test_coverage_reports_positive_eligible_and_total_separately():
    scans = {
        "EUR": pd.DataFrame([_scan_row(val=0.01)]),
        "JPY": pd.DataFrame([_scan_row(val=0.01)]),
        "GBP": pd.DataFrame([_scan_row(val=-0.01)]),
        "CHF": pd.DataFrame([_scan_row(val=0.01)]),
        "CAD": pd.DataFrame([_scan_row(val=0.01)]),
    }
    cross = aggregate_cross_market_scans(scans, min_markets=3)
    diagnosed = cross_market_coverage_diagnostic(cross)
    row = diagnosed.iloc[0]

    assert row["positive_validation_markets"] == 4
    assert row["markets_eligible"] == 5
    assert row["markets_total"] == 5
    assert row["coverage_text"] == "4 positiv / 5 eligible / 5 total"


def test_leave_one_out_is_stable_and_ignores_oos():
    scans = {
        name: pd.DataFrame([_scan_row(val=0.01)])
        for name in ("EUR", "JPY", "GBP", "CHF", "CAD")
    }
    cross = aggregate_cross_market_scans(scans, min_markets=3)
    candidate = cross.iloc[0]

    first = cross_market_leave_one_out(scans, candidate, min_markets=3)
    changed = {
        name: frame.assign(oos_median=-999999.0)
        for name, frame in scans.items()
    }
    second = cross_market_leave_one_out(changed, candidate, min_markets=3)

    assert np.allclose(
        first["cross_market_score"],
        second["cross_market_score"],
        equal_nan=True,
    )
    assert leave_one_out_summary(first)["stable"]


def test_flow_redundancy_detects_identical_event_membership():
    scans = {}
    events = {}
    for name in ("EUR", "JPY", "GBP", "CHF"):
        scans[name] = pd.DataFrame(
            [
                _scan_row(
                    feature="raw_release_velocity_1w",
                    cutoff=10.0,
                ),
                _scan_row(
                    feature="raw_release_velocity_2w",
                    cutoff=10.0,
                ),
            ]
        )
        events[name] = _events()

    cross = aggregate_cross_market_scans(scans, min_markets=3)
    redundancy = cross_market_flow_redundancy(
        events,
        scans,
        cross,
        top_n=4,
    )

    assert not redundancy.empty
    assert np.isclose(redundancy.iloc[0]["median_jaccard"], 1.0)
    assert bool(redundancy.iloc[0]["redundant"])


def test_cross_market_parameter_neighborhood_detects_region():
    scans = {}
    for name in ("EUR", "JPY", "GBP", "CHF", "CAD"):
        scans[name] = pd.DataFrame(
            [
                _scan_row(window=104, threshold=75.0),
                _scan_row(window=156, threshold=70.0),
                _scan_row(window=156, threshold=75.0),
                _scan_row(window=156, threshold=80.0),
                _scan_row(window=208, threshold=75.0),
            ]
        )

    cross = aggregate_cross_market_scans(scans, min_markets=3)
    center = cross[
        (cross["window_weeks"] == 156)
        & (cross["threshold_upper"] == 75.0)
    ].iloc[0]

    neighborhood = cross_market_parameter_neighborhood(cross, center)
    summary = cross_market_neighborhood_summary(neighborhood)

    assert len(neighborhood) == 5
    assert summary["neighbor_count"] == 4
    assert summary["positive_neighbor_share"] == 1.0
    assert summary["stable_region"]
