from pathlib import Path

import pandas as pd

from src.ftmo_risk import FTMORiskConfig, risk_cockpit_summary


ROOT = Path(__file__).resolve().parents[1]


def _position(symbol, side, risk_price, sl, tick=0.01, tick_value=1.0, volume=1.0):
    return {
        "symbol": symbol,
        "side": side,
        "volume": volume,
        "price_open": risk_price,
        "price_current": risk_price,
        "sl": sl,
        "tick_size": tick,
        "tick_value": tick_value,
        "tick_value_loss": tick_value,
        "currency_base": "",
        "currency_profit": "",
        "ticket": 1,
    }


def test_navigation_contains_risk_cockpit_before_detail_page():
    text = (ROOT / "app.py").read_text()
    assert 'pages/risk_cockpit.py' in text
    assert 'title="Risk Cockpit"' in text
    assert text.index('pages/risk_cockpit.py') < text.index('pages/portfolio_risk.py')


def test_cockpit_page_is_intentionally_compact():
    text = (ROOT / "pages" / "risk_cockpit.py").read_text()
    assert 'Darf aktuell neues Risiko ins Portfolio?' in text
    assert 'Die 3 größten Risikotreiber' in text
    assert 'Risk Capacity nach Bereich' in text
    assert 'Alle Risk-Details & Pre-Trade-Rechner öffnen' in text
    assert 'st.dataframe(' not in text


def test_risk_cockpit_summary_reports_remaining_capacity_and_drivers():
    cfg = FTMORiskConfig()
    # $1,000 risk: 100 price points / 0.01 * $1 * 0.1 lots = $1,000
    positions = pd.DataFrame([
        _position("XAUUSD", "LONG", 2000.0, 1900.0, volume=0.1),
        _position("XAGUSD", "LONG", 30.0, 20.0, volume=0.1),
    ])
    account = {
        "balance": 100_000.0,
        "equity": 100_000.0,
        "day_start_balance": 100_000.0,
        "daily_realized_pnl": 0.0,
    }
    out = risk_cockpit_summary(account, positions, cfg)
    assert out["portfolio_limit"] == 2_000.0
    assert out["portfolio_risk"] > 0
    assert out["portfolio_remaining"] < out["portfolio_limit"]
    assert not out["drivers"].empty
    assert "Metals" in set(out["cluster_capacity"]["cluster"])
