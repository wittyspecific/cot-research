from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
WATCH = ROOT / "pages" / "watchlist.py"
NAV = ROOT / "src" / "watchlist_asset_nav.py"


def test_v3143_navigation_metadata_exists():
    text = NAV.read_text(encoding="utf-8")
    assert "WATCHLIST_ASSET_PAGES" in text
    for label in (
        "Währungen",
        "Indizes",
        "US-Zinsen",
        "Energie",
        "Metalle",
        "Soft-Rohstoffe",
        "Getreide",
        "Vieh",
        "Forstprodukte",
    ):
        assert label in text


def test_v3143_app_places_asset_pages_after_watchlist():
    text = APP.read_text(encoding="utf-8")
    assert "from src.watchlist_asset_nav import WATCHLIST_ASSET_PAGES" in text
    assert 'st.Page("pages/watchlist.py", title="Watchlist"' in text
    assert 'title=f"↳ {item[\'label\']}"' in text
    assert "for item in WATCHLIST_ASSET_PAGES" in text


def test_v3143_wrappers_reuse_main_watchlist():
    wrappers = list((ROOT / "pages").glob("watchlist_*.py"))
    scoped = [
        p for p in wrappers
        if "ASSET CLASS WATCHLIST WRAPPER" in p.read_text(encoding="utf-8")
    ]
    assert scoped
    for path in scoped:
        text = path.read_text(encoding="utf-8")
        assert '_watchlist_asset_scope_once' in text
        assert 'with_name("watchlist.py")' in text
        assert "runpy.run_path" in text


def test_v3143_watchlist_consumes_scope_and_filters_pipeline():
    text = WATCH.read_text(encoding="utf-8")
    assert '_watchlist_asset_scope_once' in text
    assert 'pipeline["asset_class"]' in text
    assert ".eq(str(_watchlist_asset_scope))" in text
    assert 'f"COT Watchlist · {_watchlist_scope_label}"' in text


def test_v3143_watchlist_still_parses():
    ast.parse(WATCH.read_text(encoding="utf-8"))
