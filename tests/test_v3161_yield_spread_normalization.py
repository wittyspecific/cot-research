from pathlib import Path
import ast

import pandas as pd

from src.yield_spreads import (
    YieldSeriesResult,
    historical_move_stats,
    percentile_strength,
    pair_spread_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "yield_spreads.py"
ENGINE = ROOT / "src" / "yield_spreads.py"


def _spread(values):
    return pd.Series(
        values,
        index=pd.date_range("2020-01-01", periods=len(values), freq="B"),
        dtype=float,
    )


def _result(currency, values):
    return YieldSeriesResult(
        currency=currency,
        label=currency,
        source="test",
        source_url="",
        series=_spread(values).rename(currency),
    )


def test_percentile_strength_thresholds():
    assert percentile_strength(None) == "N/V"
    assert percentile_strength(10) == "NORMAL"
    assert percentile_strength(59.9) == "NORMAL"
    assert percentile_strength(60) == "MILD"
    assert percentile_strength(75) == "STRONG"
    assert percentile_strength(90) == "EXTREME"


def test_historical_stats_require_minimum_history():
    spread = _spread([1.0 + i * 0.001 for i in range(200)])
    stats = historical_move_stats(
        spread,
        periods=20,
        min_history=252,
    )
    assert stats["percentile"] is None
    assert stats["strength"] == "N/V"


def test_historical_percentile_uses_absolute_magnitude():
    values = []
    level = 0.0
    for i in range(1400):
        # Mostly tiny daily drift, then a very large final repricing.
        level += 0.001 if i < 1399 else 0.50
        values.append(level)

    stats = historical_move_stats(
        _spread(values),
        periods=20,
        lookback_years=5,
        min_history=252,
    )
    assert stats["percentile"] is not None
    assert stats["percentile"] >= 90
    assert stats["strength"] == "EXTREME"


def test_current_move_is_excluded_from_reference_sample():
    values = [i * 0.001 for i in range(1400)]
    values[-1] += 1.0
    stats = historical_move_stats(
        _spread(values),
        periods=5,
        lookback_years=5,
        min_history=252,
    )
    assert stats["history_count"] <= 1394
    assert stats["percentile"] >= 90


def test_pair_snapshot_contains_normalized_fields():
    eur = [2.0 + i * 0.001 for i in range(1400)]
    usd = [4.0 for _ in range(1400)]
    universe = {
        "EUR": _result("EUR", eur),
        "USD": _result("USD", usd),
    }
    row = pair_spread_snapshot("EURUSD", universe)
    for key in (
        "percentile_5d",
        "strength_5d",
        "percentile_20d",
        "strength_20d",
        "percentile_60d",
        "strength_60d",
        "rates_consistency",
        "normalization_obs_20d",
    ):
        assert key in row


def test_rates_consistency_reports_common_direction():
    eur = [2.0 + i * 0.002 for i in range(1400)]
    usd = [4.0 for _ in range(1400)]
    universe = {
        "EUR": _result("EUR", eur),
        "USD": _result("USD", usd),
    }
    row = pair_spread_snapshot("EURUSD", universe)
    assert row["rates_consistency"] == "3/3 EUR"


def test_page_explains_normalization():
    text = PAGE.read_text(encoding="utf-8")
    assert "V3.16.1 · HISTORICALLY NORMALIZED 2Y YIELD SPREADS" in text
    assert "letzten fünf Kalenderjahre" in text
    assert "20D" in text
    assert "EXTREME" in text


def test_engine_and_page_parse():
    for path in (ENGINE, PAGE):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
