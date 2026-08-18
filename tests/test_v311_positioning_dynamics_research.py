import numpy as np
import pandas as pd

from src.positioning_dynamics_research import (
    add_positioning_dynamics_features,
    compare_flow_measures,
    extract_percentile_episodes,
    quantile_effect_study,
    release_directional_value,
    research_question_coverage,
    summarize_window_threshold_grid,
)


def _sample_enriched(n=220):
    idx = np.arange(n, dtype=float)
    raw = 1000.0 + idx * 7.0 + np.sin(idx / 4.0) * 40.0
    oi = 100_000.0 + idx * 20.0
    return pd.DataFrame(
        {
            "report_date": pd.date_range("2020-01-07", periods=n, freq="7D"),
            "producer_net": raw,
            "producer_net_oi": raw / oi,
        }
    )


def test_dynamics_features_create_multi_window_and_flow_columns():
    out = add_positioning_dynamics_features(_sample_enriched(), "producer", windows=(104, 156, 208))
    for window in (104, 156, 208):
        assert f"producer_raw_pct_{window}w" in out.columns
        assert f"producer_net_oi_pct_{window}w" in out.columns
        assert f"producer_raw_pct_{window}w_delta_1w" in out.columns
        assert f"producer_raw_pct_{window}w_velocity_4w" in out.columns
        assert f"producer_raw_pct_{window}w_acceleration_1v4" in out.columns
    assert "producer_raw_velocity_1w" in out.columns
    assert "producer_net_oi_acceleration_1v4" in out.columns


def test_extract_percentile_episode_tracks_depth_duration_and_release():
    dates = pd.Series(pd.date_range("2026-01-06", periods=8, freq="7D"))
    pct = pd.Series([55.0, 82.0, 91.0, 88.0, 72.0, 45.0, 18.0, 31.0])
    episodes = extract_percentile_episodes(dates, pct, upper=80, lower=20)
    assert len(episodes) == 2
    upper = episodes.iloc[0]
    assert upper["zone"] == 1
    assert upper["duration_weeks"] == 3
    assert upper["extreme_percentile"] == 91.0
    assert upper["extreme_depth"] == 11.0
    assert upper["release_report_date"] == dates.iloc[4]
    lower = episodes.iloc[1]
    assert lower["zone"] == -1
    assert lower["duration_weeks"] == 1
    assert lower["extreme_depth"] == 2.0
    assert lower["release_report_date"] == dates.iloc[7]


def test_release_directional_value_makes_out_of_extreme_positive():
    assert release_directional_value(-12.0, 1) == 12.0
    assert release_directional_value(12.0, -1) == 12.0
    assert release_directional_value(5.0, 1) == -5.0


def test_window_threshold_summary_uses_independent_episode_rows():
    events = pd.DataFrame(
        {
            "window_weeks": [104, 104, 156, 156],
            "threshold_upper": [80.0, 80.0, 90.0, 90.0],
            "threshold_lower": [20.0, 20.0, 10.0, 10.0],
            "release_available": [True, True, True, False],
            "duration_weeks": [2, 4, 8, 10],
            "extreme_depth": [3.0, 9.0, 4.0, 8.0],
            "return_8w": [0.02, -0.01, 0.03, np.nan],
            "directional_return_8w": [0.02, -0.01, 0.03, np.nan],
        }
    )
    out = summarize_window_threshold_grid(events, horizon_weeks=8)
    assert len(out) == 2
    first = out[out["window_weeks"] == 104].iloc[0]
    assert first["episodes"] == 2
    assert first["releases"] == 2
    assert first["median_duration_weeks"] == 3.0
    assert first["n_8w"] == 2


def test_quantile_effect_study_can_test_depth_monotonicity():
    n = 40
    events = pd.DataFrame(
        {
            "extreme_depth": np.arange(1, n + 1, dtype=float),
            "directional_return_8w": np.arange(1, n + 1, dtype=float) / 1000.0,
        }
    )
    study = quantile_effect_study(events, "extreme_depth", horizon_weeks=8, quantiles=4)
    assert len(study) == 4
    assert study.iloc[-1]["directional_return_median"] > study.iloc[0]["directional_return_median"]


def test_compare_flow_measures_keeps_raw_oi_and_percentile_separate():
    n = 40
    x = np.arange(1, n + 1, dtype=float)
    events = pd.DataFrame(
        {
            "pct_release_velocity_2w": x,
            "raw_release_velocity_2w": x * 100.0,
            "net_oi_release_velocity_2w": x / 1000.0,
            "pct_release_acceleration": x / 2.0,
            "raw_release_acceleration": x * 10.0,
            "net_oi_release_acceleration": x / 2000.0,
            "directional_return_8w": x / 1000.0,
        }
    )
    out = compare_flow_measures(events, horizon_weeks=8, lag_weeks=2, quantiles=4)
    assert set(out["feature"]) == {
        "pct_release_velocity_2w",
        "raw_release_velocity_2w",
        "net_oi_release_velocity_2w",
        "pct_release_acceleration",
        "raw_release_acceleration",
        "net_oi_release_acceleration",
    }


def test_v311a_scope_is_explicit_about_remaining_questions():
    coverage = research_question_coverage()
    assert len(coverage) == 11
    assert (coverage["v311a"] == "JA").sum() >= 7
    assert "NEIN" in set(coverage["v311a"])
