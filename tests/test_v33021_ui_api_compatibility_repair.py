from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

UI = ROOT / "src" / "ui" / "hedgefund.py"
INIT = ROOT / "src" / "ui" / "__init__.py"

MARKER = "V3.30.2.1 · UI API COMPATIBILITY REPAIR"


def test_v33021_compatibility_marker_is_present():
    source = UI.read_text(
        encoding="utf-8"
    )

    assert MARKER in source


def test_v33021_v3300_component_api_is_restored():
    source = UI.read_text(
        encoding="utf-8"
    )

    for name in (
        "render_page_header",
        "render_section_header",
        "render_metric_grid",
        "render_status_chip",
        "render_callout",
        "render_divider",
    ):
        assert f"def {name}(" in source


def test_v33021_metric_grid_delegates_to_current_card():
    source = UI.read_text(
        encoding="utf-8"
    )

    assert "render_card(" in source
    assert "render_metric_grid(" in source


def test_v33021_package_exports_restored_api():
    source = INIT.read_text(
        encoding="utf-8"
    )

    for name in (
        "render_section_header",
        "render_metric_grid",
        "render_status_chip",
        "render_callout",
        "render_divider",
    ):
        assert name in source


def test_v33021_files_parse():
    for path in (
        UI,
        INIT,
    ):
        ast.parse(
            path.read_text(
                encoding="utf-8"
            ),
            filename=str(path),
        )
