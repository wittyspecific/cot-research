
from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "src" / "research_panel_v1.py"
STYLE = ROOT / "src" / "style.py"
WATCH = ROOT / "pages" / "watchlist.py"


def _source(path):
    return path.read_text(encoding="utf-8")


def _function_source(name):
    source = _source(PANEL)
    tree = ast.parse(source, filename=str(PANEL))
    node = next(
        n for n in tree.body
        if isinstance(n, ast.FunctionDef)
        and n.name == name
    )
    lines = source.splitlines(keepends=True)
    return "".join(lines[node.lineno - 1:node.end_lineno])


def _classification_namespace():
    source = (
        _function_source("_direction_sign")
        + "\n"
        + _function_source("_classify_structural_turn_flow")
    )
    ns = {}
    exec(
        "from typing import Any\n"
        "import numpy as np\n"
        + source,
        ns,
    )
    return ns


def test_bottom_persistent_bearish_flow_opposes():
    classify = _classification_namespace()[
        "_classify_structural_turn_flow"
    ]
    assert classify(1, "BEARISH", "BEARISH", "BEARISH") == "WIDERSPRICHT"


def test_bottom_persistent_bullish_flow_confirms():
    classify = _classification_namespace()[
        "_classify_structural_turn_flow"
    ]
    assert classify(1, "BULLISH", "BULLISH", "BULLISH") == "BESTÄTIGT"


def test_top_persistent_bearish_flow_confirms():
    classify = _classification_namespace()[
        "_classify_structural_turn_flow"
    ]
    assert classify(-1, "BEARISH", "BEARISH", "BEARISH") == "BESTÄTIGT"


def test_top_persistent_bullish_flow_opposes():
    classify = _classification_namespace()[
        "_classify_structural_turn_flow"
    ]
    assert classify(-1, "BULLISH", "BULLISH", "BULLISH") == "WIDERSPRICHT"


def test_recent_reversal_into_bottom_is_distinguished():
    classify = _classification_namespace()[
        "_classify_structural_turn_flow"
    ]
    assert (
        classify(1, "BEARISH", "BULLISH", "BULLISH")
        == "DREHT IN TURN-RICHTUNG"
    )


def test_integrated_seasonal_state_uses_structural_evaluator():
    segment = _function_source("seasonal_state_for_prices")
    assert "_structural_turn_read(" in segment
    assert "_classify_turn_robustness(" in segment
    assert "_integrated_turn_read_label(" in segment
    assert "verdict.upper()" not in segment


def test_structural_turn_read_uses_same_cot_engine():
    segment = _function_source("_structural_turn_read")
    assert "evaluate_cot_positioning(" in segment
    assert "direction_4w" in segment
    assert "direction_2w" in segment
    assert "direction_1w" in segment


def test_watchlist_dark_override_is_installed():
    text = _source(STYLE)
    assert "V3.29.4 · LEGACY WATCHLIST DARK OVERRIDE" in text
    assert ".sw-card," in text
    assert ".sw-legend," in text
    assert ".sw-table" in text
    assert "background: #0F151C !important" in text
    assert "color: #EDF2F7 !important" in text
    assert '[data-testid="stMultiSelect"]' in text
    assert '[data-testid="stBaseButton-secondary"]' in text


def test_watchlist_page_itself_was_not_rewritten_by_v3294():
    assert "V3.29.4" not in _source(WATCH)


def test_changed_files_parse():
    for path in (PANEL, STYLE, WATCH):
        ast.parse(
            _source(path),
            filename=str(path),
        )
