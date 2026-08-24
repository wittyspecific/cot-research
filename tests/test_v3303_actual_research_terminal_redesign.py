from pathlib import Path
import ast
import hashlib


ROOT = Path(__file__).resolve().parents[1]

OPPORTUNITY = ROOT / "pages" / "opportunity_scanner.py"
MARKET = ROOT / "pages" / "market_analysis_hub.py"
MACRO = ROOT / "pages" / "macro_regime.py"
CURRENCY = ROOT / "pages" / "currency_strength_hub.py"
WATCH = ROOT / "pages" / "watchlist.py"
UI = ROOT / "src" / "ui" / "research_terminal.py"


def test_v3303_actual_pages_are_rewritten():
    for path in (
        OPPORTUNITY,
        MARKET,
        MACRO,
        CURRENCY,
    ):
        source = path.read_text(encoding="utf-8")
        assert "V3.30.3 · ACTUAL RESEARCH TERMINAL REDESIGN" in source


def test_v3303_terminal_has_visible_layout_components():
    source = UI.read_text(encoding="utf-8")

    for token in (
        ".rt-hero",
        ".rt-stat",
        ".rt-regime-path",
        "def thesis_hero(",
        "def stat_grid(",
        "def evidence_panels(",
        "def regime_path(",
    ):
        assert token in source


def test_v3303_original_watchlist_is_still_embedded():
    source = OPPORTUNITY.read_text(encoding="utf-8")

    assert '"Beobachtungsliste"' in source
    assert '"Seasonality Scanner"' in source
    assert "runpy.run_path(" in source
    assert 'run_name="__main__"' in source
    assert "_run_legacy_watchlist_with_routing()" in source


def test_v3303_legacy_routing_contract_is_preserved():
    source = OPPORTUNITY.read_text(encoding="utf-8")

    assert "V3.29.4.1 · LEGACY WATCHLIST ROUTING BRIDGE" in source
    assert '"pages/marktanalyse.py"' in source
    assert '"pages/market_analysis_hub.py"' in source
    assert '"research_market_handoff"' in source


def test_v3303_watchlist_flat_dark_compatibility_contract_is_preserved():
    source = OPPORTUNITY.read_text(encoding="utf-8")

    assert "V3.29.5.1 · WATCHLIST FLAT DARK POST OVERRIDE" in source
    assert ".sw-chip," in source
    assert ".sw-signal," in source
    assert ".sw-plan," in source
    assert "background: transparent !important" in source
    assert "border: 0 !important" in source
    assert ".sw-card," in source
    assert ".sw-legend," in source
    assert "background: var(--qa-bg) !important" in source
    assert ".sw-bias," in source
    assert "color: var(--qa-text) !important" in source
    assert "opacity: 1 !important" in source
    assert ".sw-signal.signal-aligned" in source
    assert ".sw-signal.signal-watch" in source
    assert ".sw-signal.signal-neutral" in source
    assert ".sw-signal.signal-ready" in source


def test_v3303_historical_analog_contract_is_preserved():
    source = MARKET.read_text(encoding="utf-8")

    assert '"Bullish %"' in source
    assert '"Bearish %"' in source
    assert '"Directional Hit Rate"' not in source
    assert "bullish_rate" in source
    assert "bearish_rate" in source
    assert "if analog.top_matches:" not in source


def test_v3303_market_has_mockup_style_trade_thesis():
    source = MARKET.read_text(encoding="utf-8")

    assert "thesis_hero(" in source
    assert "evidence_panels(" in source
    assert '"Overview"' in source
    assert '"COT"' in source
    assert '"Seasonal Turn"' in source
    assert '"Historical Analog"' in source
    assert '"Market Context"' in source


def test_v3303_macro_has_regime_path():
    source = MACRO.read_text(encoding="utf-8")

    assert "regime_path(" in source
    assert '"Business Cycle"' in source
    assert '"Macro × COT"' in source
    assert '"Risk Conditions"' in source


def test_v3303_files_parse():
    for path in (
        OPPORTUNITY,
        MARKET,
        MACRO,
        CURRENCY,
        UI,
    ):
        ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
