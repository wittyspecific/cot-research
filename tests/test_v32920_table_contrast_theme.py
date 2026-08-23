from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "src" / "trader_theme.py"


def test_v32920_table_contrast_overlay_is_present():
    source = THEME.read_text(encoding="utf-8")

    assert "V3.29.2 · TABLE CONTRAST THEME" in source
    assert "#1A2029" in source
    assert "#0F151C" in source
    assert "#29333E" in source
    assert "#EDF2F7" in source
    assert "#929EAD" in source


def test_v32920_glide_dataframe_variables_are_present():
    source = THEME.read_text(encoding="utf-8")

    for token in (
        "--gdg-bg-cell",
        "--gdg-bg-header",
        "--gdg-text-dark",
        "--gdg-text-light",
        "--gdg-border-color",
        "--gdg-accent-color",
    ):
        assert token in source


def test_v32920_native_table_styles_are_present():
    source = THEME.read_text(encoding="utf-8")

    assert '[data-testid="stTable"] thead th' in source
    assert '[data-testid="stTable"] tbody td' in source
    assert "tbody tr:hover" in source


def test_v32920_theme_parses():
    ast.parse(
        THEME.read_text(encoding="utf-8"),
        filename=str(THEME),
    )
