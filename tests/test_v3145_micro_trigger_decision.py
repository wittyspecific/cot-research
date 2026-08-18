from src.watchlist_macro_micro import classify_macro_micro_trade


def _row(phase="EXTREME", macro_direction=1, trigger_direction=0, trigger_age=-1, fresh=False):
    return {
        "context_direction": macro_direction,
        "cycle_phase": phase,
        "transition_state": "HEDGE STABLE",
        "regime_stage": 2 if phase == "RELEASE" else 1,
        "micro_trigger_direction": trigger_direction,
        "micro_trigger_age_weeks": trigger_age,
        "micro_trigger_fresh": fresh,
        "micro_trigger_value": 95 if trigger_direction > 0 else 5,
        "micro_current_index_26w": 76,
    }


def test_fresh_micro_leads_before_macro_release():
    out = classify_macro_micro_trade(_row(trigger_direction=-1, trigger_age=1, fresh=True))
    assert out["bias"] == "SHORT"
    assert out["bias_direction"] == -1


def test_old_trigger_does_not_drive_new_trade_before_release():
    out = classify_macro_micro_trade(_row(trigger_direction=1, trigger_age=8, fresh=False))
    assert out["bias"] == "WAIT"
    assert out["bias_direction"] == 0


def test_macro_release_overrides_opposite_fresh_micro():
    out = classify_macro_micro_trade(
        _row(phase="RELEASE", trigger_direction=-1, trigger_age=1, fresh=True)
    )
    assert out["bias"] == "LONG BIAS"
    assert out["plan"] == "Korrektur abwarten"


def test_macro_release_aligned_fresh_micro_is_long():
    out = classify_macro_micro_trade(
        _row(phase="RELEASE", trigger_direction=1, trigger_age=0, fresh=True)
    )
    assert out["bias"] == "LONG"
    assert out["signal"] == "ALIGNED"
