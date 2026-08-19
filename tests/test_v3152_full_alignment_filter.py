from pathlib import Path
import ast

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"


def _load_helper(classifier, seasonality):
    text = WATCH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_full_alignment_state"
    )
    namespace = {
        "pd": pd,
        "classify_macro_micro_trade": classifier,
        "calculate_market_20y_multi_seasonality": seasonality,
    }
    module = ast.Module(body=[fn], type_ignores=[])
    exec(compile(module, str(WATCH), "exec"), namespace)
    return namespace["_full_alignment_state"]


def test_full_alignment_bullish():
    helper = _load_helper(
        lambda row: {
            "macro": {"direction": 1},
            "micro": {"direction": 1},
        },
        lambda **kwargs: {"overall": "UNTERSTÜTZT"},
    )
    out = helper(pd.Series({"ticker": "TEST"}))
    assert out["aligned"] is True
    assert out["direction"] == 1


def test_full_alignment_bearish():
    helper = _load_helper(
        lambda row: {
            "macro": {"direction": -1},
            "micro": {"direction": -1},
        },
        lambda **kwargs: {"overall": "UNTERSTÜTZT"},
    )
    out = helper(pd.Series({"ticker": "TEST"}))
    assert out["aligned"] is True
    assert out["direction"] == -1


def test_macro_micro_conflict_is_not_full_alignment():
    calls = []

    def seasonality(**kwargs):
        calls.append(kwargs)
        return {"overall": "UNTERSTÜTZT"}

    helper = _load_helper(
        lambda row: {
            "macro": {"direction": 1},
            "micro": {"direction": -1},
        },
        seasonality,
    )
    out = helper(pd.Series({"ticker": "TEST"}))
    assert out["aligned"] is False
    assert calls == []


def test_neutral_macro_or_micro_is_not_full_alignment():
    helper = _load_helper(
        lambda row: {
            "macro": {"direction": 0},
            "micro": {"direction": 0},
        },
        lambda **kwargs: {"overall": "UNTERSTÜTZT"},
    )
    assert helper(pd.Series({"ticker": "TEST"}))["aligned"] is False


def test_countertrend_seasonality_is_not_full_alignment():
    helper = _load_helper(
        lambda row: {
            "macro": {"direction": 1},
            "micro": {"direction": 1},
        },
        lambda **kwargs: {"overall": "GEGENLÄUFIG"},
    )
    assert helper(pd.Series({"ticker": "TEST"}))["aligned"] is False


def test_missing_seasonality_is_not_full_alignment():
    helper = _load_helper(
        lambda row: {
            "macro": {"direction": 1},
            "micro": {"direction": 1},
        },
        lambda **kwargs: {"overall": "N/V"},
    )
    assert helper(pd.Series({"ticker": "TEST"}))["aligned"] is False


def test_filter_is_visible_and_wired():
    text = WATCH.read_text(encoding="utf-8")
    assert '"Alles aligned"' in text
    assert 'elif view == "Alles aligned":' in text
    assert "_full_alignment_state(filter_row)" in text


def test_seasonality_is_evaluated_against_common_direction():
    text = WATCH.read_text(encoding="utf-8")
    assert "cot_direction=macro_direction" in text
    assert '"UNTERSTÜTZT" in overall' in text


def test_watchlist_parses():
    ast.parse(WATCH.read_text(encoding="utf-8"))
