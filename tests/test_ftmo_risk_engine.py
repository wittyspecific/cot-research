from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from src.ftmo_risk import (
    FTMORiskConfig,
    canonical_instrument,
    classify_cluster,
    cluster_risk_table,
    ftmo_rule_state,
    fx_factor_risk_table,
    instrument_risk_table,
    portfolio_risk_status,
    pretrade_approval,
    size_trade,
    stop_risk,
)


def _cfg():
    return FTMORiskConfig(initial_capital=100_000.0)


def _eurusd_position(**overrides):
    row = {
        "ticket": 1,
        "symbol": "EURUSD",
        "side": "LONG",
        "volume": 0.50,
        "price_open": 1.10000,
        "sl": 1.09000,
        "tp": 1.12000,
        "price_current": 1.10500,
        "profit": 250.0,
        "swap": -2.0,
        "tick_size": 0.00001,
        "tick_value": 0.50,  # 1 lot would be $1/tick; 0.5 lot -> multiplied below
        "tick_value_loss": 1.0,
        "contract_size": 100000,
        "currency_base": "EUR",
        "currency_profit": "USD",
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
    }
    row.update(overrides)
    return row


def test_stop_risk_uses_current_to_sl_and_entry_to_sl_separately():
    row = _eurusd_position()
    # Current 1.105 -> SL 1.090 = 1500 ticks * $1 * 0.5 = $750.
    assert math.isclose(stop_risk(row, from_current=True), 750.0, rel_tol=1e-9)
    # Entry 1.100 -> SL 1.090 = 1000 ticks * $1 * 0.5 = $500.
    assert math.isclose(stop_risk(row, from_current=False), 500.0, rel_tol=1e-9)


def test_ftmo_two_step_rule_state_uses_midnight_balance_and_static_floor():
    account = {
        "balance": 102000.0,
        "equity": 101500.0,
        "day_start_balance": 102000.0,
        "daily_realized_pnl": 0.0,
    }
    state = ftmo_rule_state(account, pd.DataFrame([_eurusd_position()]), _cfg())
    assert state["daily_limit"] == 97000.0
    assert state["daily_buffer"] == 4500.0
    assert state["maximum_loss_limit"] == 90000.0
    assert state["total_buffer"] == 11500.0
    assert state["exact_daily_limit"] is True


def test_missing_daily_start_is_not_silently_guessed():
    state = ftmo_rule_state(
        {"balance": 100000.0, "equity": 100000.0},
        pd.DataFrame(),
        _cfg(),
    )
    assert math.isnan(state["daily_limit"])
    assert state["exact_daily_limit"] is False


def test_lot_sizing_rounds_down_to_mt5_volume_step():
    spec = {
        "tick_size": 0.00001,
        "tick_value_loss": 1.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
    }
    result = size_trade(spec, side="LONG", entry=1.10000, stop=1.09230, risk_budget=500.0)
    assert result["ok"] is True
    # Risk per 1 lot = 770 ticks = $770; raw = .64935, rounded down .64.
    assert result["lots"] == 0.64
    assert result["actual_risk"] <= 500.0


def test_lot_sizing_rejects_wrong_stop_side():
    spec = {
        "tick_size": 0.01,
        "tick_value_loss": 1.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
    }
    result = size_trade(spec, side="LONG", entry=100.0, stop=101.0, risk_budget=500.0)
    assert result["ok"] is False


def test_cluster_and_fx_factor_identify_shared_usd_exposure():
    positions = pd.DataFrame([
        _eurusd_position(symbol="EURUSD", side="LONG", currency_base="EUR", currency_profit="USD"),
        _eurusd_position(ticket=2, symbol="GBPUSD", side="LONG", currency_base="GBP", currency_profit="USD"),
    ])
    clusters = cluster_risk_table(positions, _cfg())
    assert clusters.iloc[0]["cluster"] == "FX"
    fx = fx_factor_risk_table(positions, _cfg())
    usd = fx[fx["currency"] == "USD"].iloc[0]
    assert usd["direction"] == "SHORT"
    assert usd["positions"] == 2


def test_symbol_cluster_classification():
    assert classify_cluster("XAUUSD", "XAU", "USD") == "Metals"
    assert classify_cluster("XCUUSD", "XCU", "USD") == "Metals"
    assert classify_cluster("USOIL.cash", "", "USD") == "Energy"
    assert classify_cluster("US100.cash", "", "USD") == "Indices"
    assert classify_cluster("EURUSD", "EUR", "USD") == "FX"
    # Regression: AUDJPY must never match a broad DJ/index token.
    assert classify_cluster("AUDJPY", "", "") == "FX"


def test_pretrade_approval_blocks_when_an_open_trade_has_no_stop():
    cfg = _cfg()
    positions = pd.DataFrame([_eurusd_position(sl=0.0)])
    account = {
        "balance": 100000.0,
        "equity": 100000.0,
        "day_start_balance": 100000.0,
        "daily_realized_pnl": 0.0,
    }
    spec = {
        "currency_base": "XAU", "currency_profit": "USD",
        "tick_size": 0.01, "tick_value_loss": 1.0,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01,
    }
    result = pretrade_approval(
        account=account, positions=positions, cfg=cfg, spec=spec,
        symbol="XAUUSD", side="LONG", entry=2500.0, stop=2475.0,
        requested_risk_pct=0.005,
    )
    assert result["status"] == "BLOCKED"
    assert any("keinen Stop Loss" in reason for reason in result["reasons"])


def test_pretrade_approval_respects_cluster_limit_and_can_reduce():
    # Preserve a wider 1.5% cluster cap for this reduction-specific test.
    cfg = FTMORiskConfig(initial_capital=100_000.0, max_cluster_risk_pct=0.015)
    # Existing XAU stop risk = $1,250, leaving $250 under 1.5% cluster cap.
    existing = _eurusd_position(
        symbol="XAUUSD", side="LONG", volume=0.50, price_open=2500.0,
        price_current=2500.0, sl=2475.0, tick_size=0.01, tick_value_loss=1.0,
        currency_base="XAU", currency_profit="USD",
    )
    positions = pd.DataFrame([existing])
    account = {
        "balance": 100000.0, "equity": 100000.0,
        "day_start_balance": 100000.0, "daily_realized_pnl": 0.0,
    }
    spec = {
        "currency_base": "XAG", "currency_profit": "USD",
        "tick_size": 0.01, "tick_value_loss": 1.0,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01,
    }
    result = pretrade_approval(
        account=account, positions=positions, cfg=cfg, spec=spec,
        symbol="XAGUSD", side="LONG", entry=30.0, stop=29.0,
        requested_risk_pct=0.005,
    )
    assert result["status"] == "REDUCED"
    assert result["approved_budget"] <= 250.0 + 1e-9
    assert result["actual_risk"] <= result["approved_budget"] + 1e-9


def test_bridge_source_has_no_trade_execution_and_exports_v351_risk_fields():
    root = Path(__file__).resolve().parents[1]
    mq5 = (root / "mt5" / "MT5ReadOnlyBridge.mq5").read_text(encoding="utf-8")
    assert "day_start_balance" in mq5
    assert "daily_realized_pnl" in mq5
    assert "cot_mt5_symbols.csv" in mq5
    assert "SYMBOL_TRADE_TICK_VALUE_LOSS" in mq5
    forbidden = ["OrderSend(", "trade.Buy(", "trade.Sell(", "PositionClose(", "PositionModify("]
    assert not any(token in mq5 for token in forbidden)


def test_portfolio_page_exposes_ftmo_risk_engine_not_order_execution():
    root = Path(__file__).resolve().parents[1]
    page = (root / "pages" / "portfolio_risk.py").read_text(encoding="utf-8")
    assert "FTMO Portfolio & Risk Engine" in page
    assert "DAILY LOSS LIMIT" in page
    assert "OPEN STOP RISK" in page
    assert "Pre-Trade Risk Approval" in page
    assert "RISK APPROVED" in page
    assert "order_send" not in page


def test_same_underlying_tickets_are_aggregated_into_one_instrument_limit():
    cfg = _cfg()
    positions = pd.DataFrame([
        _eurusd_position(ticket=1, symbol="NATGAS.cash", side="LONG", volume=1.0, price_current=3.0, price_open=3.0, sl=2.8, tick_size=0.01, tick_value_loss=10.0, currency_base="", currency_profit="USD"),
        _eurusd_position(ticket=2, symbol="NATGAS.cash", side="LONG", volume=1.0, price_current=3.0, price_open=3.0, sl=2.8, tick_size=0.01, tick_value_loss=10.0, currency_base="", currency_profit="USD"),
    ])
    table = instrument_risk_table(positions, cfg)
    assert len(table) == 1
    assert table.iloc[0]["instrument"] == "NATGAS"
    assert table.iloc[0]["positions"] == 2
    assert math.isclose(table.iloc[0]["stop_risk"], 400.0, rel_tol=1e-9)
    assert canonical_instrument("NATGAS.cash") == "NATGAS"


def test_pretrade_blocks_new_ticket_when_same_instrument_limit_is_exhausted():
    cfg = _cfg()
    existing = _eurusd_position(
        symbol="NATGAS.cash", side="LONG", volume=1.0, price_open=3.0, price_current=3.0,
        sl=2.5, tick_size=0.01, tick_value_loss=10.0, currency_base="", currency_profit="USD",
    )
    # Existing risk = $500, exactly the default 0.50% instrument limit.
    account = {"balance": 100000.0, "equity": 100000.0, "day_start_balance": 100000.0, "daily_realized_pnl": 0.0}
    spec = {
        "currency_base": "", "currency_profit": "USD", "tick_size": 0.01, "tick_value_loss": 10.0,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01,
    }
    result = pretrade_approval(
        account=account, positions=pd.DataFrame([existing]), cfg=cfg, spec=spec,
        symbol="NATGAS.cash", side="LONG", entry=3.0, stop=2.8, requested_risk_pct=0.0025,
    )
    assert result["status"] == "BLOCKED"
    assert any("Instrument-Limit" in reason for reason in result["reasons"])


def test_fx_factor_uses_directional_net_risk_and_counts_tickets():
    cfg = _cfg()
    positions = pd.DataFrame([
        _eurusd_position(ticket=1, symbol="AUDCAD", side="SHORT", sl=1.12000, currency_base="AUD", currency_profit="CAD"),
        _eurusd_position(ticket=2, symbol="AUDJPY", side="SHORT", sl=1.12000, currency_base="AUD", currency_profit="JPY"),
    ])
    fx = fx_factor_risk_table(positions, cfg)
    aud = fx[fx["currency"] == "AUD"].iloc[0]
    assert aud["direction"] == "SHORT"
    assert aud["positions"] == 2
    assert math.isclose(aud["net_factor_risk"], -1500.0, rel_tol=1e-9)
    assert math.isclose(aud["net_risk_pct"], 0.015, rel_tol=1e-9)


def test_fx_factor_opposite_trade_can_release_directional_factor_risk():
    cfg = FTMORiskConfig(
        initial_capital=100_000.0,
        max_open_risk_pct=0.10, max_cluster_risk_pct=0.10, max_instrument_risk_pct=0.10,
        max_fx_factor_risk_pct=0.0075, daily_safety_reserve_pct=0.0, total_safety_reserve_pct=0.0,
    )
    existing = _eurusd_position(symbol="EURUSD", side="LONG", volume=0.5, currency_base="EUR", currency_profit="USD")
    account = {"balance": 100000.0, "equity": 100000.0, "day_start_balance": 100000.0, "daily_realized_pnl": 0.0}
    spec = {
        "currency_base": "EUR", "currency_profit": "USD", "tick_size": 0.00001, "tick_value_loss": 1.0,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01,
    }
    # SHORT EURUSD offsets the existing EUR-long / USD-short factor rather than adding to it.
    result = pretrade_approval(
        account=account, positions=pd.DataFrame([existing]), cfg=cfg, spec=spec,
        symbol="EURUSD", side="SHORT", entry=1.1050, stop=1.1100, requested_risk_pct=0.0025,
    )
    assert result["status"] in {"APPROVED", "REDUCED"}
    assert result["caps"]["fx_factor_EUR"] > cfg.initial_capital * cfg.max_fx_factor_risk_pct


def test_portfolio_status_turns_red_when_internal_limits_are_breached():
    cfg = _cfg()
    position = _eurusd_position(volume=2.0)  # $3,000 current stop risk > 2% portfolio cap.
    account = {"balance": 100000.0, "equity": 100000.0, "day_start_balance": 100000.0, "daily_realized_pnl": 0.0}
    status = portfolio_risk_status(account, pd.DataFrame([position]), cfg)
    assert status["status"] == "RED"
    assert any("Open Stop Risk" in reason for reason in status["reasons"])


def test_v352_page_exposes_instrument_and_risk_desk_status():
    root = Path(__file__).resolve().parents[1]
    page = (root / "pages" / "portfolio_risk.py").read_text(encoding="utf-8")
    assert "V3.5.2" in page
    assert "Portfolio Risk Status" in page
    assert "Instrument Risk" in page
    assert "Max. FX-Faktor Risk" in page
