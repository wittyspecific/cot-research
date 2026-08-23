from pathlib import Path
import ast

import pandas as pd
import pytest

from src.yield_spreads import (
    YieldSeriesResult,
    freshness_status,
    pair_spread_snapshot,
    parse_pair,
    spread_series,
)


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
PAGE = ROOT / "pages" / "yield_spreads.py"
ENGINE = ROOT / "src" / "yield_spreads.py"


def _result(currency, values):
    index = pd.date_range("2026-01-01", periods=len(values), freq="B")
    return YieldSeriesResult(
        currency=currency,
        label=currency,
        source="test",
        source_url="",
        series=pd.Series(values, index=index, dtype=float, name=currency),
    )


def test_parse_pair():
    assert parse_pair("EURUSD") == ("EUR", "USD")
    assert parse_pair("EUR/USD") == ("EUR", "USD")


def test_spread_orientation_is_base_minus_quote():
    base = pd.Series([3.0, 3.2], index=pd.date_range("2026-01-01", periods=2))
    quote = pd.Series([4.0, 3.9], index=pd.date_range("2026-01-01", periods=2))
    spread = spread_series(base, quote)
    assert spread.iloc[-1] == pytest.approx(-0.7)


def test_rising_base_minus_quote_spread_supports_base_direction_label():
    eur = [2.0 + i * 0.01 for i in range(70)]
    usd = [4.0 for _ in range(70)]
    universe = {"EUR": _result("EUR", eur), "USD": _result("USD", usd)}
    row = pair_spread_snapshot("EURUSD", universe)
    assert row["available"] is True
    assert row["delta_20d_bp"] > 0
    assert row["direction_20d"] == "EUR +"


def test_falling_base_minus_quote_spread_supports_quote_direction_label():
    eur = [2.0 for _ in range(70)]
    usd = [4.0 + i * 0.01 for i in range(70)]
    universe = {"EUR": _result("EUR", eur), "USD": _result("USD", usd)}
    row = pair_spread_snapshot("EURUSD", universe)
    assert row["delta_20d_bp"] < 0
    assert row["direction_20d"] == "USD +"


def test_missing_currency_is_not_forced():
    universe = {
        "USD": _result("USD", [4.0] * 70),
        "CHF": YieldSeriesResult(
            "CHF",
            "Swiss 2Y",
            "SNB",
            "",
            pd.Series(dtype=float),
            status="N/V",
        ),
    }
    row = pair_spread_snapshot("USDCHF", universe)
    assert row["available"] is False
    assert row["direction_20d"] == "N/V"


def test_freshness_gate():
    result = YieldSeriesResult(
        "USD",
        "US 2Y",
        "test",
        "",
        pd.Series(
            [4.0],
            index=[pd.Timestamp("2026-08-18")],
        ),
    )
    assert freshness_status(result, now="2026-08-20") == "FRESH"
    assert freshness_status(result, now="2026-08-27") == "LAGGED"
    assert freshness_status(result, now="2026-09-05") == "STALE"


def test_navigation_places_yield_spreads_after_currency_strength():
    text = APP.read_text(encoding="utf-8")
    tree = ast.parse(text)

    pages_assign = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and (
                (
                    isinstance(node, ast.Assign)
                    and any(
                        isinstance(target, ast.Name)
                        and target.id == "pages"
                        for target in node.targets
                    )
                )
                or (
                    isinstance(node, ast.AnnAssign)
                    and isinstance(node.target, ast.Name)
                    and node.target.id == "pages"
                )
            )
        ),
        None,
    )

    assert pages_assign is not None

    sections = {}

    for key, value in zip(
        pages_assign.value.keys,
        pages_assign.value.values,
    ):
        if (
            isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and isinstance(value, ast.List)
        ):
            sections[key.value] = [
                ast.get_source_segment(text, element) or ""
                for element in value.elts
            ]

    research = sections["RESEARCH"]
    advanced = sections["ADVANCED"]

    # V3.29.x Research is intentionally reduced to four core pages.
    assert any(
        "pages/currency_strength_hub.py" in item
        for item in research
    )
    assert not any(
        "pages/yield_spreads.py" in item
        for item in research
    )

    # Yield Spreads remains preserved as diagnostic/Advanced functionality.
    assert any(
        (
            "pages/yield_spreads.py" in item
            or "advanced_legacy_yield_spreads.py" in item
        )
        for item in advanced
    )


def test_page_is_research_only():
    text = PAGE.read_text(encoding="utf-8")
    assert "kein harter Trade-Filter" in text
    assert "manual_close" not in text
    assert "order_send" not in text.lower()


def test_python_files_parse():
    for path in (ENGINE, PAGE):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
