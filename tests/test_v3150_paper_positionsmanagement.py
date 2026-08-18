from pathlib import Path
import ast

import pytest

from src.paper_position_management import close_price_for_side, is_fresh_quote, result_r_from_prices

ROOT = Path(__file__).resolve().parents[1]


def test_v3150_is_paper_only():
    page = (ROOT / "pages" / "positionsmanagement.py").read_text()
    assert "Nur SIMULATION" in page
    assert "keine MT5-Order" in page
    assert "Break Even gilt erst ab dem Klick-Zeitpunkt" in page


def test_read_only_bridge_stays_read_only():
    bridge = (ROOT / "mt5" / "MT5ReadOnlyBridge.mq5").read_text()
    assert "Contains no OrderSend, trade modification or close logic." in bridge
    assert "PositionClose(" not in bridge
    assert "PositionModify(" not in bridge


def test_no_trade_manager_ea_or_real_trade_action_module():
    assert not (ROOT / "mt5" / "MT5TradeManagerBridge.mq5").exists()
    assert not (ROOT / "src" / "mt5_trade_actions.py").exists()


def test_manual_close_uses_executable_side():
    quote = {"bid": 100.25, "ask": 100.75}
    assert close_price_for_side("LONG", quote) == pytest.approx(100.25)
    assert close_price_for_side("SHORT", quote) == pytest.approx(100.75)


def test_result_r_is_based_on_original_risk():
    assert result_r_from_prices(side="LONG", execution_price=100, original_stop=95, exit_price=102.5) == pytest.approx(0.5)
    assert result_r_from_prices(side="SHORT", execution_price=100, original_stop=105, exit_price=97.5) == pytest.approx(0.5)


def test_stale_quote_is_rejected():
    quote = {
        "bid": 100.0,
        "ask": 100.2,
        "tick_age_seconds": 1,
        "exported_at_utc": "2026-08-18T12:00:00Z",
    }
    assert is_fresh_quote(quote, now="2026-08-18T12:00:02Z", max_tick_age_seconds=5)
    assert not is_fresh_quote(quote, now="2026-08-18T12:00:30Z", max_tick_age_seconds=5)
    assert not is_fresh_quote(dict(quote, tick_age_seconds=30), now="2026-08-18T12:00:02Z", max_tick_age_seconds=5)


def test_live_watcher_processes_paper_management():
    live = (ROOT / "src" / "live_execution.py").read_text()
    assert "process_paper_management_quotes" in live
    assert '"managed_exits"' in live


def test_gateway_and_client_have_paper_routes():
    gateway = (ROOT / "gateway" / "journal_gateway.py").read_text()
    client = (ROOT / "src" / "journal_gateway_client.py").read_text()
    assert 'path == "/v1/paper-positions"' in gateway
    assert 'parts[3] in {"break-even", "manual-close"}' in gateway
    assert "def paper_positions(" in client
    assert "def paper_break_even(" in client
    assert "def paper_manual_close(" in client


def test_navigation_order():
    app = (ROOT / "app.py").read_text()
    assert app.index("pages/trade_planner.py") < app.index("pages/positionsmanagement.py") < app.index("pages/trading_journal.py")


def test_management_events_are_append_only():
    source = (ROOT / "src" / "paper_position_management.py").read_text()
    assert "trg_paper_management_events_no_update" in source
    assert "trg_paper_management_events_no_delete" in source
    assert "stop_effective_at_utc" in source
    assert "retroactive" in source


def test_modified_python_files_parse():
    for rel in [
        "app.py",
        "pages/positionsmanagement.py",
        "src/paper_position_management.py",
        "src/journal_gateway_client.py",
        "src/live_execution.py",
        "gateway/journal_gateway.py",
    ]:
        path = ROOT / rel
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
