from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "pages" / "market_analysis_hub.py"
THEME = ROOT / "src" / "trader_theme.py"
DASHBOARD = ROOT / "pages" / "dashboard.py"


def test_historical_analog_uses_bullish_and_bearish_rates():
    source = MARKET.read_text(encoding="utf-8")

    assert '"Bullish %"' in source
    assert '"Bearish %"' in source
    assert '"Directional Hit Rate"' not in source
    assert "bullish_rate" in source
    assert "bearish_rate" in source


def test_historical_match_rows_are_not_rendered():
    source = MARKET.read_text(encoding="utf-8")

    assert "if analog.top_matches:" not in source
    assert "matches.style.format" not in source


def test_selectbox_dark_override_is_present():
    source = THEME.read_text(encoding="utf-8")

    assert "V3.29.1 · SELECTBOX DARK OVERRIDE" in source
    assert '[data-testid="stSelectbox"]' in source
    assert '[role="combobox"]' in source
    assert "-webkit-text-fill-color" in source


def test_dashboard_wording_is_consolidated():
    if DASHBOARD.exists():
        source = DASHBOARD.read_text(encoding="utf-8")
        assert 'label="Intermarket öffnen"' not in source


def test_modified_ui_files_parse():
    for path in (
        MARKET,
        THEME,
        DASHBOARD,
    ):
        if path.exists():
            ast.parse(
                path.read_text(encoding="utf-8"),
                filename=str(path),
            )
