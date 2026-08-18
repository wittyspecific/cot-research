from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "pages" / "watchlist.py"


def _text():
    return WATCH.read_text(encoding="utf-8")


def _renderer_body():
    text = _text()
    tree = ast.parse(text)
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_render_trader_table"
    )
    return "\n".join(
        text.splitlines()[fn.lineno - 1:fn.end_lineno]
    )


def test_renderer_contains_seasonality_helper():
    body = _renderer_body()
    assert "def _seasonality_for_bias(" in body


def test_helper_uses_current_bias_direction():
    body = _renderer_body()
    assert "cot_direction=int(bias_direction)" in body


def test_helper_uses_existing_seasonality_engine():
    body = _renderer_body()
    assert "calculate_market_20y_multi_seasonality(" in body


def test_helper_keeps_supported_and_countertrend_states():
    body = _renderer_body()
    assert '"UNTERSTÜTZT"' in body
    assert '"GEGENLÄUFIG"' in body


def test_renderer_still_calls_helper():
    body = _renderer_body()
    assert "season_mark, _, season_help = _seasonality_for_bias(" in body


def test_native_market_routing_still_present():
    text = _text()
    assert 'st.switch_page("pages/marktanalyse.py")' in text
    assert 'href="?open_market=' not in text


def test_watchlist_parses():
    ast.parse(_text())
