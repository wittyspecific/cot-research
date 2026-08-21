from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "seasonality_edge_lab.py"


def _text():
    return PAGE.read_text(encoding="utf-8")


def test_controls_are_on_page_not_sidebar():
    text = _text()

    assert 'with st.sidebar:' not in text
    assert 'st.container(border=True)' in text
    assert '"Assetklasse"' in text
    assert '"Markt"' in text
    assert '"Primäres Historienfenster"' in text
    assert '"Turn-Window Forward-Horizont"' in text


def test_ticker_is_resolved_automatically():
    text = _text()

    assert 'price_ticker = market["ticker"]' in text
    assert 'st.text_input(' not in text
    assert '"Preis-Proxy automatisch erkannt:' in text


def test_existing_research_sections_survive():
    text = _text()

    for token in (
        "Current Seasonal State",
        "Turn Window Surface",
        "Phase Shift",
        "Multi-Window Robustness",
        "COT × Seasonal Turn",
    ):
        assert token in text


def test_page_parses():
    ast.parse(
        _text(),
        filename=str(PAGE),
    )
