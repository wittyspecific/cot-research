from src.dual_horizon_cot import (
    commercial_156w_pressure,
    cot_26w_timing,
    combine_dual_horizon,
)


def test_156w_extreme_level_and_slope_are_separate():
    out = commercial_156w_pressure(84, 3, 7, 12)
    assert out["direction"] == 1
    assert out["label"] == "STRONG BULLISH · BUILDING"
    assert out["slope_direction"] == 1


def test_near_80_rising_becomes_bullish_building_watch():
    out = commercial_156w_pressure(76, 2, 5, 9)
    assert out["direction"] == 1
    assert out["label"] == "BULLISH BUILDING"
    assert out["interesting"]


def test_retail_bullish_and_commercial_bearish_is_short_term_bearish():
    out = cot_26w_timing(8, 94)
    assert out["direction"] == -1
    assert out["label"] == "BEARISH EXTREME"


def test_short_bearish_plus_long_bullish_is_transition_watch_not_long():
    long_term = commercial_156w_pressure(84, 2, 6, 10)
    short_term = cot_26w_timing(5, 95)
    out = combine_dual_horizon(long_term, short_term)
    assert out["interpretation"] == (
        "BEARISH CONTINUATION · BULLISH TRANSITION WATCH"
    )
    assert "LONG NOCH NICHT FREI" in out["action"]


def test_confirmed_hard_regime_wins_over_opposite_26w_timing():
    long_term = commercial_156w_pressure(88, 2, 4, 8)
    short_term = cot_26w_timing(5, 95)
    out = combine_dual_horizon(
        long_term,
        short_term,
        hard_regime_direction=1,
        hard_regime_stage=5,
    )
    assert out["interpretation"] == "BULLISH REGIME · SHORT-TERM CORRECTION"
    assert out["action"] == "KORREKTUR / PULLBACK ABWARTEN"


def test_no_new_midrange_signal_from_small_slope_only():
    out = commercial_156w_pressure(52, 0.2, 0.3, 0.5)
    assert out["direction"] == 0
    assert not out["interesting"]
