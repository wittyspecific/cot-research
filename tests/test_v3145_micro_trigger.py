import pandas as pd

from src.micro_trigger import latest_micro_trigger


def _cot(values):
    return pd.DataFrame({
        "report_date": pd.date_range("2026-01-01", periods=len(values), freq="7D"),
        "commercial_index": values,
    })


def test_bullish_trigger_is_entry_into_90_zone():
    out = latest_micro_trigger(_cot([72, 84, 93]))
    assert out["direction"] == 1
    assert out["age_weeks"] == 0
    assert out["fresh"]


def test_trigger_is_remembered_after_zone_exit():
    out = latest_micro_trigger(_cot([72, 95, 76]))
    assert out["direction"] == 1
    assert out["age_weeks"] == 1
    assert out["fresh"]


def test_old_extreme_is_not_fresh_trade_trigger():
    out = latest_micro_trigger(_cot([70, 92] + [95] * 12))
    assert out["direction"] == 1
    assert out["age_weeks"] == 12
    assert not out["fresh"]


def test_bearish_trigger_is_entry_into_10_zone():
    out = latest_micro_trigger(_cot([34, 18, 8]))
    assert out["direction"] == -1
    assert out["age_weeks"] == 0
    assert out["fresh"]


def test_reentry_creates_new_trigger():
    out = latest_micro_trigger(_cot([88, 94, 70, 93]))
    assert out["direction"] == 1
    assert out["age_weeks"] == 0
    assert out["trigger_value"] == 93
