from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

TRADER = ROOT / "src" / "trader_theme.py"
STYLE = ROOT / "src" / "style.py"

MARKER = "V3.30.1 · VISIBLE HEDGE FUND COMPONENT MIGRATION"


def test_v3301_visible_layer_installed_in_both_theme_modules():
    for path in (
        TRADER,
        STYLE,
    ):
        source = path.read_text(
            encoding="utf-8"
        )
        assert MARKER in source


def test_v3301_trader_components_are_actually_redefined():
    source = TRADER.read_text(
        encoding="utf-8"
    )

    assert 'class="hf330-page-head"' in source
    assert 'class="hf330-card"' in source
    assert 'class="hf330-summary"' in source
    assert "def _v3301_tone_color(" in source


def test_v3301_card_has_institutional_surface_and_accent():
    source = TRADER.read_text(
        encoding="utf-8"
    )

    assert "linear-gradient(" in source
    assert "--hf330-accent" in source
    assert "#22303D" in source
    assert "#62A6C9" in source


def test_v3301_sidebar_has_active_research_accent():
    for path in (
        TRADER,
        STYLE,
    ):
        source = path.read_text(
            encoding="utf-8"
        )
        assert '[aria-current="page"]' in source
        assert "inset 3px 0 0 #62A6C9" in source


def test_v3301_theme_files_parse():
    for path in (
        TRADER,
        STYLE,
    ):
        ast.parse(
            path.read_text(
                encoding="utf-8"
            ),
            filename=str(path),
        )
