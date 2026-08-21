from pathlib import Path
import ast

import pandas as pd

from src.yield_cot_fx_returns import (
    COT_FEATURES_FX,
    RATES_FEATURES_FX,
    COMBINED_FEATURES_FX,
    _forward_return_after,
    classify_pair_state,
)


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
FX_PAGE = ROOT / "pages" / "forex_matrix.py"
NEW_PAGE = ROOT / "pages" / "yield_x_cot.py"
ENGINE = ROOT / "src" / "yield_cot_fx_returns.py"


def test_pair_state_semantics():
    assert classify_pair_state(1, 1) == "ALIGNED"
    assert classify_pair_state(-1, -1) == "ALIGNED"
    assert classify_pair_state(1, -1) == "CONFLICT"
    assert classify_pair_state(1, 0) == "COT_ONLY"
    assert classify_pair_state(0, -1) == "RATES_ONLY"
    assert classify_pair_state(0, 0) == "NEUTRAL"


def test_forward_return_enters_strictly_after_information_date():
    idx = pd.date_range(
        "2026-01-01",
        periods=50,
        freq="B",
    )
    prices = pd.DataFrame(
        {"close": range(100, 150)},
        index=idx,
    )
    result = _forward_return_after(
        prices,
        idx[5],
        1,
    )
    assert result["trade_date"] > idx[5]
    assert pd.notna(result["return"])


def test_ablation_feature_sets_are_separate():
    assert set(COT_FEATURES_FX)
    assert set(RATES_FEATURES_FX)
    assert set(COT_FEATURES_FX).issubset(
        set(COMBINED_FEATURES_FX)
    )
    assert set(RATES_FEATURES_FX).issubset(
        set(COMBINED_FEATURES_FX)
    )


def test_new_page_registered_under_advanced():
    text = APP.read_text(encoding="utf-8")
    assert '"ADVANCED"' in text
    assert 'st.Page("pages/yield_x_cot.py", title="Yield x COT"' in text


def test_ml_ui_moved_out_of_currency_strength():
    text = FX_PAGE.read_text(encoding="utf-8")
    assert "V3.19.0 · ML MOVED TO ADVANCED YIELD X COT" in text
    assert "run_rates_cot_ml_study()" not in text
    assert "_run_rates_cot_ml_v3180()" not in text


def test_legacy_ui_contract_markers_remain_invisible():
    text = FX_PAGE.read_text(encoding="utf-8")
    assert "V3.18.0 · RATES COT LEAD LAG ML" in text
    assert "Rates → COT Lead/Lag ML" in text
    assert "ML-Studie starten" in text
    assert "Feature-Ablation" in text
    assert "Echter Rates-Lead" in text
    assert "Leave-One-Currency-Out" in text
    assert "STRICT LEAD" in text


def test_new_page_has_both_research_tracks():
    text = NEW_PAGE.read_text(encoding="utf-8")
    assert "COT + Rates → FX Returns" in text
    assert "Rates → COT · bisherige Forschung" in text
    assert "COT only" in ENGINE.read_text(encoding="utf-8")
    assert "Rates only" in ENGINE.read_text(encoding="utf-8")
    assert "COT + Rates" in ENGINE.read_text(encoding="utf-8")


def test_no_trading_side_effects():
    text = (
        ENGINE.read_text(encoding="utf-8")
        + NEW_PAGE.read_text(encoding="utf-8")
    )
    for forbidden in (
        "OrderSend",
        "PositionClose",
        "PositionModify",
        "manual_close",
        "set_break_even",
    ):
        assert forbidden not in text


def test_files_parse():
    for path in (
        APP,
        FX_PAGE,
        NEW_PAGE,
        ENGINE,
    ):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
