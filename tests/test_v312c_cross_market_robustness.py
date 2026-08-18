import pandas as pd

from src.positioning_cross_market import (
    aggregate_cross_market_scans,
    cross_market_candidate_detail,
    cross_market_findings,
)


def _candidate(
    *,
    val,
    train=0.01,
    market_robustness=80.0,
    oos=0.0,
    feature="STATE",
    candidate_type="STATE",
):
    return {
        "candidate_type": candidate_type,
        "window_weeks": 156,
        "threshold_upper": 80.0,
        "threshold_lower": 20.0,
        "feature": feature,
        "flow_quantile": None if candidate_type == "STATE" else 0.50,
        "horizon_weeks": 8,
        "sample_ok": True,
        "n_train": 20,
        "train_median": train,
        "train_hit_rate": 0.60,
        "n_validation": 6,
        "validation_median": val,
        "validation_hit_rate": 0.60 if val > 0 else 0.40,
        "neighbor_positive_share": 0.75,
        "robustness_score": market_robustness,
        "rank_train_validation": 1,
        "status": "ROBUST CANDIDATE",
        "oos_median": oos,
        "oos_hit_rate": 1.0 if oos > 0 else 0.0,
    }


def test_cross_market_score_rewards_breadth_not_single_market_peak():
    scans = {
        "EUR": pd.DataFrame([_candidate(val=0.010)]),
        "JPY": pd.DataFrame([_candidate(val=0.012)]),
        "GBP": pd.DataFrame([_candidate(val=0.008)]),
        "CHF": pd.DataFrame([_candidate(val=0.006)]),
        "CAD": pd.DataFrame([_candidate(val=0.004)]),
        "AUD": pd.DataFrame([_candidate(val=0.005)]),
        "NZD": pd.DataFrame([_candidate(val=-0.001)]),
    }

    out = aggregate_cross_market_scans(scans, min_markets=4)
    assert len(out) == 1
    row = out.iloc[0]

    assert row["markets_eligible"] == 7
    assert row["positive_validation_markets"] == 6
    assert row["positive_validation_share"] > 0.80
    assert row["cross_market_status"] == "CROSS-MARKET ROBUST"


def test_oos_changes_cannot_change_cross_market_ranking():
    base = {
        "EUR": pd.DataFrame([_candidate(val=0.01, oos=-9.0)]),
        "JPY": pd.DataFrame([_candidate(val=0.01, oos=-9.0)]),
        "GBP": pd.DataFrame([_candidate(val=0.01, oos=-9.0)]),
        "CHF": pd.DataFrame([_candidate(val=0.01, oos=-9.0)]),
    }
    altered = {
        name: frame.assign(oos_median=999.0, oos_hit_rate=1.0)
        for name, frame in base.items()
    }

    first = aggregate_cross_market_scans(base, min_markets=4).iloc[0]
    second = aggregate_cross_market_scans(altered, min_markets=4).iloc[0]

    assert first["cross_market_score"] == second["cross_market_score"]
    assert (
        first["positive_validation_share"]
        == second["positive_validation_share"]
    )


def test_cross_market_detail_never_exposes_oos_columns():
    scans = {
        "EUR": pd.DataFrame([_candidate(val=0.01, oos=99.0)]),
        "JPY": pd.DataFrame([_candidate(val=-0.01, oos=-99.0)]),
    }
    aggregate = aggregate_cross_market_scans(scans, min_markets=1)
    detail = cross_market_candidate_detail(scans, aggregate.iloc[0])

    assert len(detail) == 2
    assert "oos_median" not in detail.columns
    assert "oos_hit_rate" not in detail.columns


def test_findings_separate_state_and_flow():
    scans = {}
    for name in ("EUR", "JPY", "GBP", "CHF", "CAD"):
        scans[name] = pd.DataFrame(
            [
                _candidate(val=0.01),
                {
                    **_candidate(
                        val=0.012,
                        feature="pct_release_acceleration",
                        candidate_type="FLOW",
                    ),
                    "rank_train_validation": 2,
                },
            ]
        )

    aggregate = aggregate_cross_market_scans(scans, min_markets=4)
    findings = cross_market_findings(aggregate)

    assert findings["top_state"] is not None
    assert findings["top_flow"] is not None
    assert findings["top_flow"]["feature"] == "pct_release_acceleration"
