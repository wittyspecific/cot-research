from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
MARKET = ROOT / "pages" / "marktanalyse.py"


def _text():
    return MARKET.read_text(encoding="utf-8")


def test_current_context_uses_watchlist_decision_core():
    text = _text()
    assert "latest_micro_trigger(" in text
    assert "classify_macro_micro_trade(" in text
    assert "Aktueller Trade-Kontext · V3.14.5 Logik" in text


def test_current_context_cards():
    text = _text()
    for label in (
        "Makro · 156W",
        "Mikro · 26W 90/10",
        "Bias",
        "Seasonality",
        "Plan",
    ):
        assert label in text


def test_visible_micro_chart_is_90_10_event_based():
    text = _text()
    assert "Mikro-Timing · 26W COT-Index" in text
    assert "_micro_prev < 90.0" in text
    assert "_micro_values >= 90.0" in text
    assert "_micro_prev > 10.0" in text
    assert "_micro_values <= 10.0" in text
    assert "Bullish Trigger · Eintritt ≥90" in text
    assert "Bearish Trigger · Eintritt ≤10" in text


def test_micro_age_and_freshness_visible():
    text = _text()
    assert "LETZTER MIKRO-TRIGGER" in text
    assert 'f"vor {_micro_trigger_age}W"' in text
    assert "0–2 COT-Wochen" in text


def test_research_layers_remain():
    text = _text()
    assert "Netto & Flow" in text
    assert "Hedger-Zyklus" in text
    assert "Spekulativer Flow" in text
    assert "Saisonalität" in text


def test_seasonality_is_confluence_only():
    text = _text()
    assert "Seasonality ist Confluence only" in text
    assert "calculate_market_20y_multi_seasonality(" in text


def test_history_has_current_and_legacy_micro_logic():
    text = _text()
    assert "Aktuelle Mikro-Logik · historische 90/10-Trigger" in text
    assert "Legacy · ursprüngliche 80/20-Index-Auswertung" in text
    assert "Diese 80/20-Auswertung steuert den heutigen Mikro-Bias" in text


def test_old_visible_fx_overlay_removed():
    assert "RESEARCH-INFORMED FX OVERLAY" not in _text()


def test_market_analysis_parses():
    ast.parse(_text())
