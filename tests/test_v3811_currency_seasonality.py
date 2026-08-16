import ast
from pathlib import Path

from src.fx_relative_core import summarize_currency_horizons


def test_currency_horizon_arrows_show_direction_not_new_score():
    result = summarize_currency_horizons({
        20: {"seasonal_direction": 1, "support": "UNTERSTÜTZT", "detail": "a"},
        40: {"seasonal_direction": -1, "support": "GEGENLÄUFIG", "detail": "b"},
        60: {"seasonal_direction": 0, "support": "GEMISCHT", "detail": "c"},
    })
    assert result["compact"] == "20▲ · 40▼ · 60—"
    assert result["valid_horizons"] == 3
    assert result["supported_horizons"] == 1


def test_currency_horizon_missing_history_uses_dot():
    result = summarize_currency_horizons({
        20: {"seasonal_direction": 1, "support": "UNTERSTÜTZT"},
        40: {"seasonal_direction": 0, "support": "N/V"},
        60: {"seasonal_direction": -1, "support": "UNTERSTÜTZT"},
    })
    assert result["compact"] == "20▲ · 40· · 60▼"
    assert result["valid_horizons"] == 2
    assert result["supported_horizons"] == 2


def test_forex_matrix_contains_single_compact_currency_seasonality_column():
    source = Path("pages/forex_matrix.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert '"Saison 20/40/60T"' in source
    assert "add_currency_20y_multi_seasonality(profiles)" in source
    assert "Die Pfeile zeigen die saisonale Richtung" in source


def test_currency_seasonality_batch_loader_uses_watchlist_price_proxies():
    source = Path("src/fx_relative.py").read_text(encoding="utf-8")
    ast.parse(source)
    assert 'CLASSIC_MARKETS["Currencies"]' in source
    assert 'group_by="ticker"' in source
    assert "classify_asset_seasonality" in source
    assert "FX_SEASONALITY_FORWARD_DAYS" in source
