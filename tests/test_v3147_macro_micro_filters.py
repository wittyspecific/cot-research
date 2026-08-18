from pathlib import Path
import ast

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"


def _load_filter_functions():
    namespace = {}
    text = WATCH.read_text(encoding="utf-8")
    tree = ast.parse(text)

    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {
            "_apply_macro_micro_filters",
            "_micro_runtime_health",
        }
    ]
    module = ast.Module(body=nodes, type_ignores=[])
    namespace["pd"] = pd

    def classifier(row):
        return {
            "macro": {"phase": row["macro_phase"]},
            "micro": {
                "direction": row["micro_direction"],
                "fresh": row["micro_fresh"],
            },
        }

    namespace["classify_macro_micro_trade"] = classifier
    exec(compile(module, str(WATCH), "exec"), namespace)
    return namespace


def _frame():
    return pd.DataFrame(
        [
            {
                "symbol": "A",
                "macro_phase": "TRANSITION",
                "micro_direction": 1,
                "micro_fresh": True,
            },
            {
                "symbol": "B",
                "macro_phase": "RELEASE",
                "micro_direction": -1,
                "micro_fresh": False,
            },
            {
                "symbol": "C",
                "macro_phase": "EXTREME",
                "micro_direction": 0,
                "micro_fresh": False,
            },
        ]
    )


def test_macro_phase_filter():
    funcs = _load_filter_functions()
    out = funcs["_apply_macro_micro_filters"](
        _frame(),
        "TRANSITION",
        "Alle Mikro",
    )
    assert out["symbol"].tolist() == ["A"]


def test_micro_direction_filter():
    funcs = _load_filter_functions()
    out = funcs["_apply_macro_micro_filters"](
        _frame(),
        "Alle Makro",
        "BEARISH TRIGGER",
    )
    assert out["symbol"].tolist() == ["B"]


def test_fresh_micro_filter_is_strict():
    funcs = _load_filter_functions()
    out = funcs["_apply_macro_micro_filters"](
        _frame(),
        "Alle Makro",
        "FRESH BULLISH",
    )
    assert out["symbol"].tolist() == ["A"]


def test_no_trigger_filter():
    funcs = _load_filter_functions()
    out = funcs["_apply_macro_micro_filters"](
        _frame(),
        "Alle Makro",
        "KEIN TRIGGER",
    )
    assert out["symbol"].tolist() == ["C"]


def test_ui_contains_macro_and_micro_dropdowns():
    text = WATCH.read_text(encoding="utf-8")
    assert '"Makro-Phase"' in text
    assert '"Mikro-Trigger"' in text
    assert '"EXTREME"' in text
    assert '"TRANSITION"' in text
    assert '"RELEASE"' in text
    assert '"CONFIRMED"' in text
    assert '"FRESH BULLISH"' in text
    assert '"FRESH BEARISH"' in text


def test_filters_use_same_decision_core():
    text = WATCH.read_text(encoding="utf-8")
    assert "decision = classify_macro_micro_trade(filter_row)" in text
    assert "_apply_macro_micro_filters(" in text


def test_runtime_diagnostic_exists():
    text = WATCH.read_text(encoding="utf-8")
    assert "def _micro_runtime_health(" in text
    assert '"Mikro-Datencheck"' in text
    assert "current_extremes_90_10" in text


def test_watchlist_parses():
    ast.parse(WATCH.read_text(encoding="utf-8"))
