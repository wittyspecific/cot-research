from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"


def _text():
    return WATCH.read_text(encoding="utf-8")


def _renderer():
    text = _text()
    tree = ast.parse(text)
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_render_trader_table"
    )
    return "\n".join(text.splitlines()[fn.lineno - 1:fn.end_lineno])


def test_micro_display_is_simple_bullish_bearish():
    body = _renderer()
    assert '"Bullish"' in body
    assert '"Bearish"' in body
    assert "micro_display_label" in body


def test_micro_display_uses_direction_not_trigger_text():
    body = _renderer()
    assert 'micro.get("direction", 0)' in body
    assert "escape(micro_display_label)" in body


def test_bullish_micro_is_green():
    body = _renderer()
    assert (
        ".micro-bull{background:#ecfdf3;color:#15803d;"
        "border:1px solid #d7f2df}"
    ) in body


def test_bearish_micro_is_red():
    body = _renderer()
    assert (
        ".micro-bear{background:#fff1f2;color:#dc2626;"
        "border:1px solid #ffe0e3}"
    ) in body


def test_internal_trigger_logic_and_filters_remain():
    text = _text()
    assert '"BULLISH TRIGGER"' in text
    assert '"BEARISH TRIGGER"' in text
    assert '"FRESH BULLISH"' in text
    assert '"FRESH BEARISH"' in text


def test_watchlist_parses():
    ast.parse(_text())
