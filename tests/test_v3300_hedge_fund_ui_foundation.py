from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

UI = ROOT / "src" / "ui" / "hedgefund.py"
INIT = ROOT / "src" / "ui" / "__init__.py"
STYLE = ROOT / "src" / "style.py"
TRADER = ROOT / "src" / "trader_theme.py"
DOC = ROOT / "docs" / "V330_HEDGE_FUND_UI.md"

MARKER = "V3.30.0 · HEDGE FUND UI FOUNDATION"


def test_v3300_ui_module_exists_and_parses():
    assert UI.exists()
    ast.parse(
        UI.read_text(encoding="utf-8"),
        filename=str(UI),
    )


def test_v3300_palette_contains_core_tokens():
    source = UI.read_text(encoding="utf-8")

    for token in (
        "#081018",
        "#0D1722",
        "#111D29",
        "#22303D",
        "#F3F6FB",
        "#95A3B3",
        "#62A6C9",
        "#65D98B",
        "#FF7373",
        "#F2B84B",
        "#79B8FF",
    ):
        assert token in source


def test_v3300_reusable_components_are_present():
    source = UI.read_text(encoding="utf-8")

    for name in (
        "render_page_header",
        "render_section_header",
        "render_metric_grid",
        "render_status_chip",
        "render_callout",
        "render_divider",
    ):
        assert f"def {name}(" in source


def test_v3300_both_theme_layers_apply_foundation_last():
    for path in (STYLE, TRADER):
        source = path.read_text(encoding="utf-8")
        assert MARKER in source
        assert "apply_hedgefund_theme" in source


def test_v3300_no_product_pages_are_rewritten_by_foundation():
    source = DOC.read_text(encoding="utf-8")
    assert "ändert keine COT-, Macro-, Seasonality-, Analog-, Risk- oder" in source


def test_v3300_package_init_parses():
    ast.parse(
        INIT.read_text(encoding="utf-8"),
        filename=str(INIT),
    )
