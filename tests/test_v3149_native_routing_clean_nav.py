from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
WATCH = ROOT / "pages" / "watchlist.py"


def test_sidebar_no_long_asset_subpage_list():
    text = APP.read_text(encoding="utf-8")
    assert "from src.watchlist_asset_nav import WATCHLIST_ASSET_PAGES" not in text
    assert "for item in WATCHLIST_ASSET_PAGES" not in text
    assert 'st.Page("pages/watchlist.py", title="Watchlist"' in text


def test_native_market_route_sets_handoff_and_switches_page():
    text = WATCH.read_text(encoding="utf-8")
    assert "def _open_watchlist_market(" in text
    assert 'st.session_state["selected_market"] = handoff' in text
    assert 'st.session_state["_market_context_handoff"] = handoff' in text
    assert 'st.switch_page("pages/marktanalyse.py")' in text


def test_primary_renderer_uses_native_button():
    text = WATCH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    renderer = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_render_trader_table"
    )
    body = "\n".join(
        text.splitlines()[renderer.lineno - 1:renderer.end_lineno]
    )
    assert "st.button(" in body
    assert "_open_watchlist_market(row)" in body
    assert 'href="?open_market=' not in body


def test_old_query_param_navigation_is_gone():
    text = WATCH.read_text(encoding="utf-8")
    assert 'st.query_params.get("open_market"' not in text
    assert 'href="?open_market=' not in text


def test_watchlist_filters_are_structured():
    text = WATCH.read_text(encoding="utf-8")
    for label in (
        '"Assetklasse"',
        '"Richtung"',
        '"Makro-Phase"',
        '"Mikro-Trigger"',
        '"Alle Assetklassen"',
    ):
        assert label in text


def test_asset_filter_uses_real_asset_class_column():
    text = WATCH.read_text(encoding="utf-8")
    assert 'filtered["asset_class"]' in text
    assert ".eq(str(asset_filter))" in text


def test_old_asset_wrappers_can_remain_compatibility_only():
    nav = ROOT / "src" / "watchlist_asset_nav.py"
    if nav.exists():
        assert "WATCHLIST_ASSET_PAGES" in nav.read_text(encoding="utf-8")


def test_files_parse():
    ast.parse(APP.read_text(encoding="utf-8"))
    ast.parse(WATCH.read_text(encoding="utf-8"))
