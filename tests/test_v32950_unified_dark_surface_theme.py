from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "src" / "style.py"
TRADER = ROOT / "src" / "trader_theme.py"

MARKER = "V3.29.5 · UNIFIED DARK SURFACE THEME"


def test_v32950_both_theme_layers_have_unified_overlay():
    for path in (STYLE, TRADER):
        source = path.read_text(encoding="utf-8")
        assert MARKER in source


def test_v32950_background_is_single_dark_surface():
    for path in (STYLE, TRADER):
        source = path.read_text(encoding="utf-8")
        assert "--qa-bg: #0B0F14" in source
        assert "--qa-surface: #0B0F14" in source


def test_v32950_white_inline_surfaces_are_overridden():
    source = STYLE.read_text(encoding="utf-8")

    assert '[style*="background: white"]' in source
    assert '[style*="background: #fff"]' in source
    assert "background: var(--qa-surface) !important" in source


def test_v32950_body_text_is_light_and_section_headings_blue():
    for path in (STYLE, TRADER):
        source = path.read_text(encoding="utf-8")
        assert "--qa-text: #F3F6FB" in source
        assert "--qa-blue: #62A6C9" in source

    style = STYLE.read_text(encoding="utf-8")
    assert '[data-testid="stAppViewContainer"] h2' in style
    assert "color: var(--qa-blue) !important" in style


def test_v32950_inputs_stay_dark_but_distinguishable():
    for path in (STYLE, TRADER):
        source = path.read_text(encoding="utf-8")
        assert "--qa-control: #111923" in source
        assert '[data-testid="stSelectbox"]' in source
        assert '[data-testid="stTextInput"]' in source


def test_v32950_watchlist_white_cards_are_neutralized():
    source = STYLE.read_text(encoding="utf-8")

    assert ".sw-card," in source
    assert ".sw-legend," in source
    assert ".sw-table" in source
    assert ".sw-row," in source


def test_v32950_modules_parse():
    for path in (STYLE, TRADER):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
