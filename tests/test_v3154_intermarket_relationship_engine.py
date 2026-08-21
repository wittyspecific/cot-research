from pathlib import Path
import ast

import pandas as pd

from src.intermarket import (
    CORE_RELATIONSHIPS,
    overall_alignment,
    relationship_alignment,
    relationship_matrix,
)


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "intermarket.py"
ENGINE = ROOT / "src" / "intermarket.py"


def test_core_relationships_are_intentionally_small_v1():
    pairs = {
        (r.currency_symbol, r.reference_market, r.polarity)
        for r in CORE_RELATIONSHIPS
    }
    assert ("CAD", "WTI Crude Oil", 1) in pairs
    assert ("AUD", "Copper", 1) in pairs
    assert ("JPY", "WTI Crude Oil", -1) in pairs
    assert len(CORE_RELATIONSHIPS) == 3


def test_positive_relationship_supports_same_direction():
    assert relationship_alignment(1, 1, 1) == "SUPPORT"
    assert relationship_alignment(-1, -1, 1) == "SUPPORT"


def test_positive_relationship_conflicts_on_opposite_direction():
    assert relationship_alignment(1, -1, 1) == "CONFLICT"
    assert relationship_alignment(-1, 1, 1) == "CONFLICT"


def test_negative_relationship_supports_opposite_direction():
    assert relationship_alignment(1, -1, -1) == "SUPPORT"
    assert relationship_alignment(-1, 1, -1) == "SUPPORT"


def test_any_neutral_leg_is_neutral():
    assert relationship_alignment(0, 1, 1) == "NEUTRAL"
    assert relationship_alignment(1, 0, 1) == "NEUTRAL"
    assert relationship_alignment(0, 0, -1) == "NEUTRAL"


def test_overall_alignment_is_transparent():
    assert overall_alignment("SUPPORT", "SUPPORT") == "STRONG SUPPORT"
    assert overall_alignment("SUPPORT", "NEUTRAL") == "SUPPORT"
    assert overall_alignment("SUPPORT", "CONFLICT") == "MIXED"
    assert overall_alignment("CONFLICT", "NEUTRAL") == "CONFLICT"
    assert overall_alignment("NEUTRAL", "NEUTRAL") == "NEUTRAL"


def test_matrix_exposes_relationship_and_weight():
    matrix = relationship_matrix()
    assert set(["currency_symbol", "reference_market", "relationship", "weight"]).issubset(
        matrix.columns
    )
    assert set(matrix["relationship"]) == {"POSITIV", "NEGATIV"}


def test_engine_reuses_current_macro_micro_core():
    text = ENGINE.read_text(encoding="utf-8")
    assert "classify_macro_micro_trade" in text
    assert 'currency_decision.get("macro")' in text
    assert 'currency_decision.get("micro")' in text


def test_page_is_research_only_and_does_not_touch_trading():
    text = PAGE.read_text(encoding="utf-8")
    assert "Research-/Confluence-Layer" in text
    assert "weder Watchlist-Signal" in text
    assert "Trade-Entscheidung" in text
    assert "trade_journal" not in text
    assert "gateway" not in text.lower()


def test_page_shows_macro_micro_and_overall():
    text = PAGE.read_text(encoding="utf-8")
    assert "Makro" in text
    assert "Mikro" in text
    assert "GESAMT" in text
    assert "STRONG SUPPORT" not in text or "overall" in text


def test_python_files_parse():
    for path in (PAGE, ENGINE):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
