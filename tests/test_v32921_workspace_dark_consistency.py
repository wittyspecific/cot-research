from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "src" / "style.py"

MARKER = "V3.29.2.1 · WORKSPACE DARK CONSISTENCY"


def test_workspace_dark_overlay_is_installed():
    source = STYLE.read_text(encoding="utf-8")

    assert MARKER in source
    assert "_v32921_workspace_dark_overlay" in source


def test_branding_and_headings_are_forced_light():
    source = STYLE.read_text(encoding="utf-8")

    assert '[class*="brand"]' in source
    assert "#F3F6FB" in source
    assert '[data-testid="stAppViewContainer"] h1' in source


def test_sidebar_user_and_logout_are_dark():
    source = STYLE.read_text(encoding="utf-8")

    assert '[data-testid="stSidebar"] [data-testid="stButton"] button' in source
    assert ".user-card" in source
    assert ".admin-card" in source


def test_dashboard_cards_and_quick_access_are_dark():
    source = STYLE.read_text(encoding="utf-8")

    assert ".metric-card" in source
    assert '[data-testid="stMetric"]' in source
    assert '[data-testid="stMainBlockContainer"] [data-testid="stPageLink"] a' in source


def test_login_labels_and_inputs_are_readable():
    source = STYLE.read_text(encoding="utf-8")

    assert '[data-testid="stTextInput"] label' in source
    assert 'background: #111923 !important' in source
    assert '-webkit-text-fill-color: var(--qa-text) !important' in source
    assert 'input::placeholder' in source


def test_style_module_parses():
    ast.parse(
        STYLE.read_text(encoding="utf-8"),
        filename=str(STYLE),
    )
