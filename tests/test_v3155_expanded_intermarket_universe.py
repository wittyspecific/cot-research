from pathlib import Path
import ast

import pandas as pd

from src.intermarket import (
    CORE_RELATIONSHIPS,
    INTERMARKET_RELATIONSHIPS,
    _find_market_row,
    relationship_matrix,
)


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "src" / "intermarket.py"
PAGE = ROOT / "pages" / "intermarket.py"


def test_original_core_relationships_remain_stable():
    assert len(CORE_RELATIONSHIPS) == 3
    pairs = {
        (r.currency_symbol, r.reference_symbol, r.polarity)
        for r in CORE_RELATIONSHIPS
    }
    assert ("CAD", "CL", 1) in pairs
    assert ("AUD", "HG", 1) in pairs
    assert ("JPY", "CL", -1) in pairs


def test_expanded_universe_contains_ten_relationships():
    assert len(INTERMARKET_RELATIONSHIPS) == 10


def test_expanded_universe_contains_requested_pairs():
    pairs = {
        (r.currency_symbol, r.reference_symbol, r.polarity)
        for r in INTERMARKET_RELATIONSHIPS
    }
    expected = {
        ("CAD", "CL", 1),
        ("AUD", "HG", 1),
        ("JPY", "CL", -1),
        ("CHF", "GC", 1),
        ("DX", "GC", -1),
        ("DX", "HG", -1),
        ("GC", "SI", 1),
        ("GC", "ZN", 1),
        ("ES", "VX", -1),
        ("NQ", "VX", -1),
    }
    assert pairs == expected


def test_regime_dependent_relationships_are_marked():
    regime_pairs = {
        (r.currency_symbol, r.reference_symbol)
        for r in INTERMARKET_RELATIONSHIPS
        if r.regime_dependent
    }
    assert ("CHF", "GC") in regime_pairs
    assert ("DX", "HG") in regime_pairs
    assert ("GC", "ZN") in regime_pairs


def test_market_lookup_accepts_german_aliases():
    frame = pd.DataFrame(
        [
            {"market_name": "Kanadischer Dollar", "ticker": "6C"},
            {"market_name": "US-Dollar-Index", "ticker": "DX"},
            {"market_name": "Kupfer", "ticker": "HG"},
        ]
    )
    assert _find_market_row(
        frame,
        "Canadian Dollar",
        aliases=("Kanadischer Dollar",),
        symbol="CAD",
    ) is not None
    assert _find_market_row(
        frame,
        "US Dollar Index",
        aliases=("US-Dollar-Index",),
        symbol="DX",
    ) is not None
    assert _find_market_row(
        frame,
        "Copper",
        aliases=("Kupfer",),
        symbol="HG",
    ) is not None


def test_symbol_fallback_resolves_market():
    frame = pd.DataFrame(
        [{"market_name": "Some Broker Label", "ticker": "ZN"}]
    )
    row = _find_market_row(
        frame,
        "US Treasury 10Y",
        aliases=(),
        symbol="ZN",
    )
    assert row is not None
    assert row["ticker"] == "ZN"


def test_relationship_matrix_defaults_to_expanded_universe():
    matrix = relationship_matrix()
    assert len(matrix) == 10
    assert set(
        [
            "category",
            "regime_dependent",
            "relationship",
            "weight",
        ]
    ).issubset(matrix.columns)


def test_page_uses_expanded_relationships():
    text = PAGE.read_text(encoding="utf-8")
    assert "INTERMARKET_RELATIONSHIPS" in text
    assert "evaluate_relationships" in text
    assert "V3.15.5 · EXPANDED COT INTERMARKET UNIVERSE" in text


def test_page_has_category_filters():
    text = PAGE.read_text(encoding="utf-8")
    for label in (
        "FX ↔ Commodity",
        "USD ↔ Commodity",
        "Commodity ↔ Commodity",
        "Commodity ↔ Rates",
        "Risk ↔ Volatility",
    ):
        assert label in text


def test_intermarket_remains_research_only():
    text = PAGE.read_text(encoding="utf-8")
    assert "weder Watchlist-Signal noch Trade-Entscheidung" in text
    assert "trade_journal" not in text
    assert "manual_close" not in text
    assert "set_break_even" not in text


def test_python_files_parse():
    for path in (ENGINE, PAGE):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
