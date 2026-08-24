from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

UI = ROOT / "src" / "ui" / "research_terminal.py"

MARKER = "V3.30.4.1 · RT HERO COMPATIBILITY REPAIR"


def test_v33041_marker_is_present():
    source = UI.read_text(encoding="utf-8")
    assert MARKER in source


def test_v33041_old_and_new_hero_contracts_are_both_supported():
    source = UI.read_text(encoding="utf-8")

    assert ".rt-hero" in source
    assert ".rt-thesis-hero" in source
    assert 'class="rt-hero rt-thesis-hero"' in source


def test_v33041_current_thesis_layout_remains_present():
    source = UI.read_text(encoding="utf-8")

    assert ".rt-thesis-market" in source
    assert ".rt-thesis-cell" in source
    assert ".rt-thesis-summary" in source


def test_v33041_ui_module_parses():
    ast.parse(
        UI.read_text(encoding="utf-8"),
        filename=str(UI),
    )
