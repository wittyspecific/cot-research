from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
CORE = (
    "pages/opportunity_scanner.py",
    "pages/market_analysis_hub.py",
    "pages/currency_strength_hub.py",
    "pages/macro_regime.py",
)


def _groups():
    text = APP.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(APP))
    groups = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str) and isinstance(value, ast.List):
                groups[key.value] = value
    return text, groups


def _paths(text, node):
    out = []
    for item in node.elts:
        for child in ast.walk(item):
            if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value.startswith("pages/"):
                out.append(child.value); break
    return out


def test_research_navigation_has_exactly_four_core_pages():
    text, groups = _groups()
    assert tuple(_paths(text, groups["RESEARCH"])) == CORE


def test_market_analysis_has_five_trader_tabs():
    source = (ROOT / "pages/market_analysis_hub.py").read_text(encoding="utf-8")
    for token in ('"Overview"','"COT"','"Seasonal Turn"','"Historical Analog"','"Market Context"',"derive_trade_opportunity"):
        assert token in source


def test_opportunity_scanner_has_two_discovery_tabs():
    source = (
        ROOT
        / "pages"
        / "opportunity_scanner.py"
    ).read_text(
        encoding="utf-8"
    )

    # V3.29.3:
    # The original Watchlist is again the authoritative COT discovery layer,
    # while Seasonality remains the second discovery tab.
    assert '"Beobachtungsliste"' in source
    assert '"Seasonality Scanner"' in source

    # The existing Watchlist page itself is executed inside the scanner.
    assert "runpy.run_path(" in source
    assert 'run_name="__main__"' in source


def test_macro_regime_has_four_tabs():
    source = (ROOT / "pages/macro_regime.py").read_text(encoding="utf-8")
    for token in ('"Overview"','"Business Cycle"','"Macro × COT"','"Risk Conditions"'):
        assert token in source


def test_state_layer_is_typed_and_has_no_mock_fallback():
    source = (ROOT / "src/research_panel_v1.py").read_text(encoding="utf-8")
    for token in ("@dataclass","class CotPositioningState","class SeasonalTurnState","class HistoricalAnalogState","class MarketContextState","class TradeOpportunityState","class MacroRegimeState","Insufficient Data","Low Confidence","No Current Signal"):
        assert token in source
    assert "mock_data" not in source.lower()


def test_dark_theme_is_shared_and_global():
    theme = (ROOT / "src/trader_theme.py").read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    assert "apply_trader_dark_theme" in app
    for token in ("--qa-bg","--qa-green","--qa-red","--qa-amber"):
        assert token in theme


def test_old_research_models_are_preserved():
    manifest = ROOT / "docs" / "V32901_LEGACY_RESEARCH_MANIFEST.txt"

    assert manifest.exists()

    legacy = [
        line.strip()
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert legacy

    for rel in legacy:
        assert (ROOT / rel).exists(), rel


def test_new_files_parse():
    for rel in ("src/trader_theme.py","src/research_panel_v1.py","pages/opportunity_scanner.py","pages/market_analysis_hub.py","pages/currency_strength_hub.py","pages/macro_regime.py","app.py"):
        path = ROOT / rel
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
