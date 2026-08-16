from pathlib import Path

from src.tradingview_widget import (
    tradingview_embed_html,
    tradingview_interval,
    tradingview_symbol,
)


ROOT = Path(__file__).resolve().parents[1]


def test_fx_symbol_maps_to_fx_idc_and_strips_broker_suffix():
    assert tradingview_symbol("AUDUSD") == "FX_IDC:AUDUSD"
    assert tradingview_symbol("EURJPY.c") == "FX_IDC:EURJPY"


def test_common_cfd_symbol_mapping():
    assert tradingview_symbol("XAUUSD") == "OANDA:XAUUSD"
    assert tradingview_symbol("USOIL.cash") == "TVC:USOIL"
    assert tradingview_symbol("USTEC.c") == "NASDAQ:NDX"


def test_unknown_symbol_is_still_searchable_in_widget():
    assert tradingview_symbol("SOMETHING.c") == "SOMETHING"


def test_timeframe_to_widget_interval():
    assert tradingview_interval("1H") == "60"
    assert tradingview_interval("4H") == "240"
    assert tradingview_interval("Daily") == "D"
    assert tradingview_interval("Weekly") == "W"
    assert tradingview_interval("Andere") == "240"


def test_embed_uses_official_advanced_chart_script_and_dark_theme():
    html = tradingview_embed_html("AUDUSD", "4H")
    assert "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" in html
    assert '"symbol":"FX_IDC:AUDUSD"' in html
    assert '"interval":"240"' in html
    assert '"theme":"dark"' in html
    assert '"allow_symbol_change":true' in html
    assert "by TradingView" in html


def test_planner_and_journal_render_tradingview_preview():
    planner = (ROOT / "pages" / "trade_planner.py").read_text()
    journal = (ROOT / "pages" / "trading_journal.py").read_text()
    assert "render_tradingview_chart(symbol" in planner
    assert "TradingView Preview" in planner
    assert "render_tradingview_chart(str(row[\"cfd_symbol\"])" in journal
    assert "MT5-CFD-Historie" in journal
