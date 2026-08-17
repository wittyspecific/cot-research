from __future__ import annotations

import json
import re
from html import escape


# TradingView is a visual analysis surface only. The outcome engine continues
# to use the broker's MT5 CFD history as the source of truth.
_CURRENCY_CODES = {
    "AUD", "CAD", "CHF", "CNH", "CNY", "CZK", "DKK", "EUR", "GBP", "HKD",
    "HUF", "ILS", "INR", "JPY", "MXN", "NOK", "NZD", "PLN", "RON", "SEK",
    "SGD", "THB", "TRY", "USD", "ZAR",
}

_COMMON_SYMBOLS = {
    "XAUUSD": "OANDA:XAUUSD",
    "XAGUSD": "OANDA:XAGUSD",
    "USOIL": "TVC:USOIL",
    "WTI": "TVC:USOIL",
    "WTIUSD": "TVC:USOIL",
    "UKOIL": "TVC:UKOIL",
    "BRENT": "TVC:UKOIL",
    "BRENTUSD": "TVC:UKOIL",
    "NATGAS": "TVC:NATGAS",
    "NGAS": "TVC:NATGAS",
    "DXY": "TVC:DXY",
    "US500": "TVC:SPX",
    "SPX500": "TVC:SPX",
    "SP500": "TVC:SPX",
    "US30": "TVC:DJI",
    "DJ30": "TVC:DJI",
    "USTEC": "NASDAQ:NDX",
    "NAS100": "NASDAQ:NDX",
    "US100": "NASDAQ:NDX",
    "GER40": "XETR:DAX",
    "DE40": "XETR:DAX",
    "DAX40": "XETR:DAX",
    "UK100": "TVC:UKX",
    "FTSE100": "TVC:UKX",
    "JP225": "TVC:NI225",
    "JPN225": "TVC:NI225",
    "AUS200": "ASX:XJO",
    "HK50": "TVC:HSI",
    "COTTON": "ICEUS:CT1!",
    "COCOA": "ICEUS:CC1!",
    "COFFEE": "ICEUS:KC1!",
    "SUGAR": "ICEUS:SB1!",
}

_TIMEFRAME_INTERVALS = {
    "1H": "60",
    "H1": "60",
    "4H": "240",
    "H4": "240",
    "DAILY": "D",
    "1D": "D",
    "D1": "D",
    "WEEKLY": "W",
    "1W": "W",
    "W1": "W",
}


def _base_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip().upper()
    if not raw:
        return ""
    # Common broker suffixes arrive as EURUSD.c / US500.cash / XAUUSD.pro.
    # Keep the first alpha-numeric token for visual symbol resolution.
    return re.split(r"[._\-]", raw, maxsplit=1)[0]


def tradingview_symbol(cfd_symbol: str) -> str:
    """Best-effort visual mapping from broker CFD ticker to TradingView ticker."""
    base = _base_symbol(cfd_symbol)
    if not base:
        return "FX_IDC:EURUSD"

    mapped = _COMMON_SYMBOLS.get(base)
    if mapped:
        return mapped

    if len(base) == 6 and base[:3] in _CURRENCY_CODES and base[3:] in _CURRENCY_CODES:
        return f"FX_IDC:{base}"

    # For unknown broker CFDs, pass the cleaned ticker through. The Advanced
    # Chart widget keeps symbol search enabled so the trader can correct it.
    return base


def tradingview_interval(timeframe: str | None) -> str:
    key = str(timeframe or "").strip().upper()
    return _TIMEFRAME_INTERVALS.get(key, "240")


def tradingview_embed_html(cfd_symbol: str, timeframe: str | None = None) -> str:
    tv_symbol = tradingview_symbol(cfd_symbol)
    config = {
        "autosize": True,
        "symbol": tv_symbol,
        "interval": tradingview_interval(timeframe),
        "timezone": "Etc/UTC",
        "theme": "light",
        "style": "1",
        "locale": "en",
        "backgroundColor": "#FFFFFF",
        "gridColor": "rgba(148, 163, 184, 0.18)",
        "withdateranges": True,
        "hide_side_toolbar": False,
        "hide_top_toolbar": False,
        "hide_legend": False,
        "hide_volume": False,
        "allow_symbol_change": True,
        "save_image": False,
        "calendar": False,
        "support_host": "https://www.tradingview.com",
    }
    cfg = json.dumps(config, ensure_ascii=True, separators=(",", ":"))
    label = escape(tv_symbol)
    return f"""<!doctype html>
<html>
<head>
<meta charset=\"utf-8\">
<style>
html, body {{ margin: 0; padding: 0; background: #FFFFFF; height: 100%; overflow: hidden; }}
.tradingview-widget-container {{ height: 100%; width: 100%; }}
.tradingview-widget-container__widget {{ height: calc(100% - 24px); width: 100%; }}
.tradingview-widget-copyright {{ height: 24px; box-sizing: border-box; padding: 5px 8px 0; font: 11px/1.2 Arial, sans-serif; color: #6B7280; }}
.tradingview-widget-copyright a {{ color: #16A34A; text-decoration: none; }}
</style>
</head>
<body>
<div class=\"tradingview-widget-container\">
  <div class=\"tradingview-widget-container__widget\"></div>
  <div class=\"tradingview-widget-copyright\">
    <a href=\"https://www.tradingview.com/\" rel=\"noopener nofollow\" target=\"_blank\">{label} chart</a> by TradingView
  </div>
  <script type=\"text/javascript\" src=\"https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js\" async>{cfg}</script>
</div>
</body>
</html>"""


def render_tradingview_chart(cfd_symbol: str, timeframe: str | None = None, *, height: int = 570) -> str:
    """Render the official Advanced Chart widget and return the resolved TV symbol."""
    import streamlit.components.v1 as components

    tv_symbol = tradingview_symbol(cfd_symbol)
    components.html(
        tradingview_embed_html(cfd_symbol, timeframe),
        height=max(420, int(height)),
        scrolling=False,
    )
    return tv_symbol
