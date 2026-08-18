from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "pages" / "marktanalyse.py"


def _text():
    return MARKET.read_text(encoding="utf-8")


def test_commercial_remains_primary_micro_trigger_series():
    text = _text()
    assert 'name="Commercial COT-Index · 26W"' in text
    assert "_micro_prev < 90.0" in text
    assert "_micro_values >= 90.0" in text
    assert "_micro_prev > 10.0" in text
    assert "_micro_values <= 10.0" in text


def test_noncommercial_26w_comparison_trace_is_restored():
    assert 'name="Non-Commercial COT-Index"' in _text()


def test_retail_26w_comparison_trace_is_restored():
    assert 'name="Retail COT-Index"' in _text()


def test_comparison_series_do_not_create_micro_trigger():
    text = _text()
    assert (
        "Non-Commercial und Retail werden im Chart ausschließlich als "
        in text
    )
    assert "erzeugen keinen Mikro-Trigger" in text


def test_market_analysis_parses():
    ast.parse(_text())
