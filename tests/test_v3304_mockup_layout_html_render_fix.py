from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

UI = ROOT / "src" / "ui" / "research_terminal.py"
MARKET = ROOT / "pages" / "market_analysis_hub.py"


def test_v3304_html_renderer_uses_st_html_or_safe_fallback():
    source = UI.read_text(
        encoding="utf-8"
    )

    assert "V3.30.4 · MOCKUP LAYOUT + HTML RENDER FIX" in source
    assert "def _html(" in source
    assert 'hasattr(st, "html")' in source
    assert "dedent(" in source


def test_v3304_raw_html_helpers_route_through_html_renderer():
    source = UI.read_text(
        encoding="utf-8"
    )

    for name in (
        "header",
        "section",
        "stat_grid",
        "thesis_hero",
        "evidence_panels",
        "insights",
        "regime_path",
    ):
        assert f"def {name}(" in source

    assert "_html(" in source


def test_v3304_market_hero_matches_mockup_information_architecture():
    source = MARKET.read_text(
        encoding="utf-8"
    )

    assert "thesis_hero(" in source
    assert "structural_bias=opportunity.structural_bias" in source
    assert "setup_state=opportunity.setup_type" in source
    assert "conviction=opportunity.conviction" in source
    assert "setup_type=opportunity.trade_type" in source
    assert "action=opportunity.preferred_action" in source


def test_v3304_historical_analog_is_two_column_research_layout():
    source = MARKET.read_text(
        encoding="utf-8"
    )

    assert 'left, right = st.columns(' in source
    assert '"Historische Analogs"' in source
    assert '"Marktkontext"' in source
    assert "insights(" in source


def test_v3304_historical_analog_contract_stays_simplified():
    source = MARKET.read_text(
        encoding="utf-8"
    )

    assert '"Bullish %"' in source
    assert '"Bearish %"' in source
    assert '"Directional Hit Rate"' not in source
    assert "bullish_rate" in source
    assert "bearish_rate" in source
    assert "if analog.top_matches:" not in source


def test_v3304_does_not_fake_full_analog_paths():
    source = MARKET.read_text(
        encoding="utf-8"
    )

    assert "anonymized forward-return distribution" in source
    assert "We do not pretend this is a full path" in source


def test_v3304_files_parse():
    for path in (
        UI,
        MARKET,
    ):
        ast.parse(
            path.read_text(
                encoding="utf-8"
            ),
            filename=str(path),
        )
