from __future__ import annotations

from typing import Any, Mapping

from .ftmo_risk import canonical_instrument, fx_pair_from_symbol
from .fx_relative_core import CURRENCY_ORDER
from .markets import CLASSIC_MARKETS


CFD_COT_SYMBOL_MAP = {
    "XAUUSD": "GC", "GOLD": "GC",
    "XAGUSD": "SI", "SILVER": "SI",
    "XCUUSD": "HG", "COPPER": "HG",
    "NATGAS": "NG", "NGAS": "NG",
    "USOIL": "CL", "WTI": "CL",
    "UKOIL": "BZ", "BRENT": "BZ",
    "US500": "ES", "SPX500": "ES",
    "US100": "NQ", "NAS100": "NQ", "USTEC": "NQ",
    "US30": "YM", "DJ30": "YM",
    "US2000": "RTY", "RUSSELL2000": "RTY",
    "BTCUSD": "BTC", "BITCOIN": "BTC",
    "ETHUSD": "ETH", "ETHEREUM": "ETH",
}


def all_markets() -> list[dict[str, Any]]:
    rows = []
    for asset_class, markets in CLASSIC_MARKETS.items():
        for market in markets:
            rows.append({"asset_class": asset_class, **market})
    return rows


def market_by_symbol(symbol: str) -> tuple[str, dict[str, Any]] | None:
    wanted = str(symbol or "").upper().strip()
    for asset_class, markets in CLASSIC_MARKETS.items():
        for market in markets:
            if str(market.get("symbol", "")).upper() == wanted:
                return asset_class, market
    return None


def infer_cot_context(cfd_symbol: str, spec: Mapping[str, Any] | None = None) -> dict[str, Any]:
    spec = dict(spec or {})
    fx_pair = fx_pair_from_symbol(
        cfd_symbol,
        spec.get("currency_base", ""),
        spec.get("currency_profit", ""),
    )
    if fx_pair and fx_pair[0] in CURRENCY_ORDER and fx_pair[1] in CURRENCY_ORDER:
        return {"mode": "FX_PAIR", "base": fx_pair[0], "quote": fx_pair[1]}

    instrument = canonical_instrument(cfd_symbol)
    cot_symbol = CFD_COT_SYMBOL_MAP.get(instrument) or CFD_COT_SYMBOL_MAP.get(str(cfd_symbol).upper())
    if cot_symbol:
        found = market_by_symbol(cot_symbol)
        if found:
            asset_class, market = found
            return {"mode": "MARKET", "asset_class": asset_class, "market": market}
    return {"mode": "NONE"}
