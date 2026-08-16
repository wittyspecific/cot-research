from __future__ import annotations

from collections import namedtuple
from pathlib import Path
import time

import pandas as pd

from src.mt5_account import (
    POSITION_COLUMNS,
    MT5Config,
    bridge_snapshot,
    config_from_mapping,
    direct_snapshot,
)


Account = namedtuple(
    "Account",
    "login server name company currency balance equity profit margin margin_free margin_level leverage trade_allowed trade_expert trade_mode",
)
Position = namedtuple(
    "Position",
    "ticket symbol type volume price_open sl tp price_current profit swap time comment",
)
Symbol = namedtuple(
    "Symbol",
    "trade_contract_size trade_tick_size trade_tick_value trade_tick_value_profit trade_tick_value_loss point digits volume_min volume_max volume_step currency_base currency_profit currency_margin swap_long swap_short margin_initial margin_maintenance trade_calc_mode",
)


class FakeMT5:
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1

    def __init__(self):
        self.shutdown_called = False
        self.initialize_kwargs = None

    def initialize(self, *args, **kwargs):
        self.initialize_kwargs = (args, kwargs)
        return True

    def shutdown(self):
        self.shutdown_called = True

    def last_error(self):
        return (1, "ok")

    def version(self):
        return (5, 5000, "01 Jan 2026")

    def account_info(self):
        return Account(
            123456789,
            "FTMO-Server4",
            "Read Only",
            "FTMO",
            "USD",
            100000.0,
            100250.0,
            250.0,
            1000.0,
            99250.0,
            10025.0,
            30,
            False,
            False,
            0,
        )

    def positions_get(self):
        return (
            Position(
                10,
                "XAUUSD",
                0,
                0.20,
                2500.0,
                2475.0,
                2550.0,
                2510.0,
                200.0,
                -4.0,
                1700000000,
                "test",
            ),
        )

    def symbol_info(self, symbol):
        assert symbol == "XAUUSD"
        return Symbol(
            100.0,
            0.01,
            1.0,
            1.0,
            1.0,
            0.01,
            2,
            0.01,
            100.0,
            0.01,
            "XAU",
            "USD",
            "USD",
            -10.0,
            3.0,
            0.0,
            0.0,
            0,
        )


def test_direct_snapshot_is_read_only_and_maps_account_positions():
    fake = FakeMT5()
    config = MT5Config(
        mode="python",
        login=123456789,
        password="investor-only",
        server="FTMO-Server4",
    )

    snap = direct_snapshot(config, mt5_module=fake)

    assert snap["source"] == "MT5 PYTHON · READ ONLY"
    assert snap["account"]["balance"] == 100000.0
    assert snap["account"]["trade_allowed"] is False
    assert snap["positions"].iloc[0]["side"] == "LONG"
    assert snap["positions"].iloc[0]["volume"] == 0.20
    assert snap["symbol_specs"].iloc[0]["contract_size"] == 100.0
    assert fake.shutdown_called is True
    assert fake.initialize_kwargs[1]["server"] == "FTMO-Server4"


def test_config_keeps_credentials_local_mapping_only():
    cfg = config_from_mapping(
        {
            "mode": "auto",
            "login": "123456789",
            "password": "secret",
            "server": "FTMO-Server4",
        }
    )
    assert cfg.login == 123456789
    assert cfg.has_credentials is True
    assert cfg.mode == "auto"


def test_bridge_snapshot_reads_live_csv_format(tmp_path: Path):
    now = int(time.time())
    account = pd.DataFrame(
        [
            {
                "timestamp_unix": now,
                "login": 123456789,
                "server": "FTMO-Server4",
                "name": "Read Only",
                "company": "FTMO",
                "currency": "USD",
                "balance": 100000,
                "equity": 99500,
                "profit": -500,
                "margin": 1200,
                "margin_free": 98300,
                "margin_level": 8291.67,
                "leverage": 30,
                "trade_allowed": 0,
                "trade_expert": 0,
            }
        ]
    )
    account.to_csv(tmp_path / "cot_mt5_account.csv", sep=";", index=False)

    position = pd.DataFrame(
        [
            {
                "ticket": 1,
                "symbol": "EURUSD",
                "side": "SHORT",
                "volume": 0.5,
                "price_open": 1.1,
                "sl": 1.11,
                "tp": 1.08,
                "price_current": 1.095,
                "profit": 250,
                "swap": -2,
                "time": now - 3600,
                "comment": "",
                "contract_size": 100000,
                "tick_size": 0.00001,
                "tick_value": 1,
                "point": 0.00001,
                "digits": 5,
                "volume_min": 0.01,
                "volume_max": 100,
                "volume_step": 0.01,
                "currency_base": "EUR",
                "currency_profit": "USD",
                "currency_margin": "EUR",
                "swap_long": -5,
                "swap_short": 2,
            }
        ]
    )
    position.to_csv(tmp_path / "cot_mt5_positions.csv", sep=";", index=False)

    snap = bridge_snapshot(
        MT5Config(
            mode="bridge",
            login=123456789,
            server="FTMO-Server4",
            bridge_common_path=str(tmp_path),
            bridge_max_age_seconds=30,
        )
    )

    assert snap["source"] == "MT5 LOCAL BRIDGE · READ ONLY"
    assert snap["account"]["equity"] == 99500
    assert snap["account"]["trade_allowed"] is False
    assert snap["positions"].iloc[0]["symbol"] == "EURUSD"
    assert snap["symbol_specs"].iloc[0]["contract_size"] == 100000


def test_bridge_freshness_uses_file_mtime_when_market_time_is_stale(tmp_path):
    # Weekend/market-closed regression: MT5 TimeCurrent() may still contain the
    # last Friday server timestamp while the EA itself keeps exporting fresh files.
    stale_market_time = int(pd.Timestamp.now(tz="UTC").timestamp()) - 24 * 3600
    account = pd.DataFrame([
        {
            "timestamp_unix": stale_market_time,
            "login": 123456789,
            "server": "FTMO-Server4",
            "name": "Test",
            "company": "FTMO",
            "currency": "USD",
            "balance": 100000,
            "equity": 100000,
            "profit": 0,
            "margin": 0,
            "margin_free": 100000,
            "margin_level": 0,
            "leverage": 30,
            "trade_allowed": 0,
            "trade_expert": 0,
        }
    ])
    account.to_csv(tmp_path / "cot_mt5_account.csv", sep=";", index=False)
    pd.DataFrame(columns=POSITION_COLUMNS).to_csv(
        tmp_path / "cot_mt5_positions.csv", sep=";", index=False
    )

    snap = bridge_snapshot(MT5Config(
        mode="bridge",
        login=123456789,
        server="FTMO-Server4",
        bridge_common_path=str(tmp_path),
        bridge_max_age_seconds=30,
    ))

    assert snap["source"] == "MT5 LOCAL BRIDGE · READ ONLY"
    assert snap["account"]["balance"] == 100000
    assert pd.Timestamp(snap["market_time"]) < pd.Timestamp(snap["captured_at"])


def test_project_contains_no_mt5_trade_execution_calls():
    root = Path(__file__).resolve().parents[1]
    py = (root / "src" / "mt5_account.py").read_text(encoding="utf-8")
    mq5 = (root / "mt5" / "MT5ReadOnlyBridge.mq5").read_text(encoding="utf-8")

    forbidden_python = [".order_send(", ".order_check("]
    forbidden_mql = ["OrderSend(", "trade.Buy(", "trade.Sell(", "PositionClose("]
    assert not any(token in py for token in forbidden_python)
    assert not any(token in mq5 for token in forbidden_mql)


def test_navigation_and_secret_hygiene():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    example = (root / ".streamlit" / "secrets.toml.example").read_text(encoding="utf-8")

    assert "pages/portfolio_risk.py" in app
    assert ".streamlit/secrets.toml" in gitignore
    assert 'platform_system == "Windows"' in requirements
    assert "INVESTOR_PASSWORD" in example
    assert "REAL_ACCOUNT_NUMBER" not in example
