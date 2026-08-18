from src.watchlist_macro_micro import (
    macro_156w_state,
    micro_26w_state,
    classify_macro_micro_trade,
)


def test_extreme_is_not_active_macro_bias():
    row = {
        "cycle_phase": "EXTREME",
        "expected_direction": 1,
        "regime_stage": 1,
        "commercial_index": 10,
    }
    macro = macro_156w_state(row)
    assert macro["phase"] == "EXTREME"
    assert not macro["active"]

    decision = classify_macro_micro_trade(row)
    assert decision["bias"] == "SHORT"
    assert decision["signal"] == "WATCH"


def test_bullish_release_has_priority_over_bearish_micro():
    row = {
        "cycle_phase": "RELEASE",
        "expected_direction": 1,
        "regime_stage": 2,
        "commercial_index": 10,
    }
    decision = classify_macro_micro_trade(row)
    assert decision["macro"]["active"]
    assert decision["bias"] == "LONG BIAS"
    assert decision["plan"] == "Korrektur abwarten"


def test_bearish_release_has_priority_over_bullish_micro():
    row = {
        "cycle_phase": "RELEASE",
        "expected_direction": -1,
        "regime_stage": 2,
        "commercial_index": 90,
    }
    decision = classify_macro_micro_trade(row)
    assert decision["bias"] == "SHORT BIAS"
    assert decision["plan"] == "Anstieg abwarten"


def test_active_macro_and_micro_alignment_is_directional_trade():
    bullish = {
        "cycle_phase": "RELEASE",
        "expected_direction": 1,
        "regime_stage": 2,
        "commercial_index": 90,
    }
    bearish = {
        "cycle_phase": "RELEASE",
        "expected_direction": -1,
        "regime_stage": 2,
        "commercial_index": 10,
    }
    assert classify_macro_micro_trade(bullish)["bias"] == "LONG"
    assert classify_macro_micro_trade(bullish)["signal"] == "ALIGNED"
    assert classify_macro_micro_trade(bearish)["bias"] == "SHORT"
    assert classify_macro_micro_trade(bearish)["signal"] == "ALIGNED"


def test_micro_current_fallback_uses_strict_90_10_logic():
    assert micro_26w_state({"commercial_index": 90})["trade_direction"] == 1
    assert micro_26w_state({"commercial_index": 10})["trade_direction"] == -1
    assert micro_26w_state({"commercial_index": 80})["trade_direction"] == 0
