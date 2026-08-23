from pathlib import Path
import ast
import re
import tomllib


ROOT = Path(__file__).resolve().parents[1]

SERVICE = ROOT / "src" / "research_panel_v1.py"
THEME = ROOT / "src" / "trader_theme.py"
CONFIG = ROOT / ".streamlit" / "config.toml"

MARKER = "V3.29.0.3.1 · NATIVE DARK WIDGET OVERLAY"

LEGACY_PAGE_LINKS = (
    "pages/watchlist.py",
    "pages/intermarket.py",
    "pages/market_analysis.py",
    "pages/forex_matrix.py",
    "pages/macro_model_library.py",
    "pages/macro_cot_regime.py",
    "pages/cot_price_analog.py",
    "pages/fx_relative_cot_analog.py",
    "pages/volatility_regime.py",
    "pages/cot_x_seasonality.py",
)


def test_macro_adapter_uses_real_v3272_keys():
    source = SERVICE.read_text(encoding="utf-8")

    assert 'combined.get("transition_state"' in source
    assert 'combined.get("alignment_state"' in source


def test_native_streamlit_theme_is_dark():
    config = tomllib.loads(
        CONFIG.read_text(encoding="utf-8")
    )

    theme = config["theme"]

    assert theme["base"] == "dark"
    assert theme["backgroundColor"].lower() == "#0b0f14"
    assert theme["secondaryBackgroundColor"].lower() == "#131b24"
    assert theme["textColor"].lower() == "#edf2f7"


def test_dark_widget_overlay_is_installed():
    source = THEME.read_text(encoding="utf-8")

    assert MARKER in source
    assert "_v329031_dark_widget_overlay" in source

    ast.parse(
        source,
        filename=str(THEME),
    )


def test_integrated_pages_are_not_targeted_by_direct_page_links():
    stale = []

    for path in (ROOT / "pages").glob("*.py"):
        source = path.read_text(encoding="utf-8")

        for legacy in LEGACY_PAGE_LINKS:
            if re.search(
                r'st\.page_link\(\s*["\']'
                + re.escape(legacy)
                + r'["\']',
                source,
            ):
                stale.append(
                    f"{path.name}: {legacy}"
                )

    assert not stale, stale
