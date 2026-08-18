import pandas as pd

from src.status_age import (
    macro_status_age_weeks,
    micro_status_age_weeks,
    transition_status_age_weeks,
)


def _cot(percentiles, indexes):
    return pd.DataFrame(
        {
            "report_date": pd.date_range(
                "2026-01-01",
                periods=len(percentiles),
                freq="7D",
            ),
            "commercial_net_percentile": percentiles,
            "commercial_index": indexes,
        }
    )


def test_micro_bullish_age_counts_consecutive_80_plus_weeks():
    cot = _cot([50] * 5, [55, 79, 82, 91, 88])
    assert micro_status_age_weeks(cot) == 3


def test_micro_bearish_age_counts_consecutive_20_minus_weeks():
    cot = _cot([50] * 4, [60, 18, 11, 20])
    assert micro_status_age_weeks(cot) == 3


def test_micro_neutral_age_is_also_measured():
    cot = _cot([50] * 4, [92, 67, 54, 48])
    assert micro_status_age_weeks(cot) == 3


def test_upper_transition_age_counts_current_early_release_run():
    cot = _cot([60, 82, 98, 96, 91], [50] * 5)
    assert transition_status_age_weeks(
        cot,
        extreme_direction=1,
    ) == 2


def test_lower_transition_age_counts_current_early_release_run():
    cot = _cot([40, 18, 7, 10, 14], [50] * 5)
    assert transition_status_age_weeks(
        cot,
        extreme_direction=-1,
    ) == 2


def test_macro_extreme_uses_episode_duration():
    cot = _cot([70, 82, 90, 95], [50] * 4)
    cycle = {
        "phase": "EXTREME",
        "transition": "HEDGE STABLE",
        "extreme_duration": 3,
        "extreme_direction": 1,
    }
    assert macro_status_age_weeks(cot, cycle) == 3


def test_macro_transition_uses_transition_run_not_full_extreme_duration():
    cot = _cot([60, 82, 98, 96, 91], [50] * 5)
    cycle = {
        "phase": "EXTREME",
        "transition": "EARLY RELEASE · STILL EXTREME",
        "extreme_duration": 4,
        "extreme_direction": 1,
    }
    assert macro_status_age_weeks(cot, cycle) == 2


def test_macro_release_week_is_week_one():
    cot = _cot([60, 82, 98, 79], [50] * 4)
    cycle = {
        "phase": "RELEASE",
        "weeks_since_release": 0,
    }
    assert macro_status_age_weeks(cot, cycle) == 1


def test_macro_release_age_advances():
    cot = _cot([60, 82, 98, 79, 70, 65], [50] * 6)
    cycle = {
        "phase": "RELEASE",
        "weeks_since_release": 2,
    }
    assert macro_status_age_weeks(cot, cycle) == 3
