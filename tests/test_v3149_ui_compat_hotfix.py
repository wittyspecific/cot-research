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


def test_v3144_status_age_compat_class_remains():
    assert "sl-age" in _text()


def test_v3145_micro_age_source_contract_remains():
    body = _renderer_body()
    assert "micro_age = int(" in body
    assert 'f"vor {micro_age}W"' in body


def test_new_v3149_classes_remain_too():
    body = _renderer_body()
    assert "wl9-age" in body
    assert "wl9-age-fresh" in body


def test_native_routing_is_untouched():
    text = _text()
    assert 'st.switch_page("pages/marktanalyse.py")' in text
    assert 'href="?open_market=' not in text


def test_watchlist_parses():
    ast.parse(_text())
