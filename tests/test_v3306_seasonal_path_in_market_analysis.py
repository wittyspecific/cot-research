from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

MARKET = ROOT / "pages" / "market_analysis_hub.py"
CHART = ROOT / "src" / "ui" / "seasonality_path_chart.py"


def _source(path):
    return path.read_text(encoding="utf-8")


def test_v3306_shared_chart_uses_existing_seasonality_engine():
    source = _source(CHART)

    assert "V3.30.6 · SHARED SEASONAL PATH CHART" in source
    assert "seasonal_template(" in source
    assert "current_phase_day(" in source
    assert "seasonal_turns(" in source


def test_v3306_chart_contains_lab_visual_contract():
    source = _source(CHART)

    for token in (
        '"25–75% Band"',
        '"Seasonal Tops"',
        '"Seasonal Bottoms"',
        '"aktuelle Phase"',
        '"Normalisierter Handelstag im Jahr"',
        '"Kumulativer saisonaler Log-Return (%)"',
    ):
        assert token in source


def test_v3306_market_analysis_loads_price_ticker_for_chart():
    source = _source(MARKET)

    assert "from src.prices import load_prices" in source
    assert "render_seasonal_path_chart" in source
    assert 'FX_PAIRS[pair].get("ticker")' in source
    assert "_season_market_spec.get" in source
    assert '"ticker"' in source


def test_v3306_chart_is_inside_seasonal_turn_before_forward_table():
    source = _source(MARKET)

    start = source.index("with tabs[2]:")
    end = source.index("with tabs[3]:", start)
    segment = source[start:end]

    chart_pos = segment.index("render_seasonal_path_chart(")
    table_pos = segment.index("st.dataframe(")

    assert chart_pos < table_pos
    assert '"Saisonaler Verlauf"' in segment


def test_v3306_20_40_60_summary_remains():
    source = _source(MARKET)

    start = source.index("with tabs[2]:")
    end = source.index("with tabs[3]:", start)
    segment = source[start:end]

    assert '"20T"' in segment
    assert '"40T"' in segment
    assert '"60T"' in segment
    assert "seasonal.direction_20t" in segment
    assert "seasonal.direction_40t" in segment
    assert "seasonal.direction_60t" in segment


def test_v3306_modified_files_parse():
    for path in (MARKET, CHART):
        ast.parse(
            _source(path),
            filename=str(path),
        )
