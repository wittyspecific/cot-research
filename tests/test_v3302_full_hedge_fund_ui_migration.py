from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

APP = ROOT / "app.py"
UI = ROOT / "src" / "ui" / "hedgefund.py"
STYLE = ROOT / "src" / "style.py"
TRADER = ROOT / "src" / "trader_theme.py"

MARKER = "V3.30.2 · FULL HEDGE FUND UI MIGRATION"


def test_v3302_ui_module_is_full_global_theme():
    source = UI.read_text(encoding="utf-8")

    assert MARKER in source
    for token in (
        "--hf-bg",
        "--hf-surface",
        '[data-testid="stSidebar"]',
        '[data-baseweb="tab-list"]',
        '[data-testid="stSelectbox"]',
        '[data-testid="stDataFrame"]',
        ".sw-card",
        ".sw-chip",
        ".hf-card",
        ".hf-page-head",
    ):
        assert token in source


def test_v3302_research_components_delegate_to_final_ui():
    source = TRADER.read_text(encoding="utf-8")

    assert MARKER in source
    assert "from src.ui.hedgefund import render_page_header" in source
    assert "from src.ui.hedgefund import render_card" in source
    assert "from src.ui.hedgefund import render_summary" in source


def test_v3302_legacy_theme_uses_final_ui():
    source = STYLE.read_text(encoding="utf-8")

    assert MARKER in source
    assert "apply_hedgefund_theme" in source


def test_v3302_app_applies_post_render_theme():
    source = APP.read_text(encoding="utf-8")

    assert "V3.30.2 · POST RENDER THEME" in source
    assert "page.run()" in source
    assert "_v3302_apply_post_render_theme()" in source


def test_v3302_post_render_occurs_after_page_run():
    source = APP.read_text(encoding="utf-8")

    run = source.index("page.run()")
    call = source.index(
        "_v3302_apply_post_render_theme()",
        run,
    )

    assert run < call


def test_v3302_files_parse():
    for path in (
        APP,
        UI,
        STYLE,
        TRADER,
    ):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
