from pathlib import Path

import pandas as pd

from src.mt5_symbols import openable_symbol_catalog, symbol_label_map


def test_openable_catalog_keeps_hidden_broker_symbols_not_in_market_watch():
    raw = pd.DataFrame([
        {
            "symbol": "XAUUSD",
            "description": "Gold vs US Dollar",
            "selected": 1,
            "visible": 1,
            "can_open": 1,
            "currency_base": "XAU",
            "currency_profit": "USD",
            "volume_min": 0.01,
            "tick_size": 0.01,
        },
        {
            "symbol": "USOIL.cash",
            "description": "WTI Crude Oil Cash",
            "selected": 0,
            "visible": 0,
            "can_open": 1,
            "currency_base": "",
            "currency_profit": "USD",
            "volume_min": 0.01,
            "tick_size": 0.001,
        },
    ])

    out = openable_symbol_catalog(raw)
    assert set(out["symbol"]) == {"XAUUSD", "USOIL.cash"}
    assert out.loc[out["symbol"] == "USOIL.cash", "cluster"].iloc[0] == "Energy"

    labels = symbol_label_map(raw)
    assert "WTI Crude Oil Cash" in labels["USOIL.cash"]
    assert "Market Watch" not in labels["USOIL.cash"]


def test_disabled_symbol_is_not_offered_for_new_trade_plans():
    raw = pd.DataFrame([
        {"symbol": "EURUSD", "can_open": 1, "selected": 1},
        {"symbol": "OLD.CFD", "can_open": 0, "selected": 0},
    ])
    out = openable_symbol_catalog(raw)
    assert out["symbol"].tolist() == ["EURUSD"]


def test_bridge_source_exports_full_broker_universe_and_throttles_catalog_refresh():
    root = Path(__file__).resolve().parents[1]
    source = (root / "mt5" / "MT5ReadOnlyBridge.mq5").read_text(encoding="utf-8")
    assert "SymbolsTotal(false)" in source
    assert "SymbolName(i, false)" in source
    assert "SymbolsTotal(true)" not in source
    assert "SYMBOL_TRADE_MODE" in source
    assert '"can_open"' in source
    assert "SymbolCatalogRefreshSeconds" in source
