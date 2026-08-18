from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.journal_execution_metrics import effective_rr, execution_rr, rr_source
from src.journal_strategy_view import find_strategy_logic_blocks

ROOT = Path(__file__).resolve().parents[1]


def test_market_execution_rr_long_uses_real_fill():
    row = {
        "order_type": "MARKET",
        "cfd_symbol": "EURUSD",
        "side": "LONG",
        "execution_price": 100.0,
        "stop": 95.0,
        "target": 110.0,
        "planned_rr": None,
    }
    assert execution_rr(row) == pytest.approx(2.0)
    assert effective_rr(row) == pytest.approx(2.0)
    assert rr_source(row) == "EXECUTION"


def test_market_execution_rr_short_uses_real_fill():
    row = {
        "order_type": "MARKET",
        "cfd_symbol": "EURUSD",
        "side": "SHORT",
        "execution_price": 100.0,
        "stop": 105.0,
        "target": 90.0,
    }
    assert execution_rr(row) == pytest.approx(2.0)


def test_market_without_fill_has_no_fake_rr():
    row = {
        "order_type": "MARKET",
        "cfd_symbol": "EURUSD",
        "side": "LONG",
        "execution_price": None,
        "stop": 95.0,
        "target": 110.0,
    }
    assert effective_rr(row) is None
    assert rr_source(row) == "PENDING_FILL"


def test_limit_keeps_planned_rr():
    assert effective_rr({"order_type": "LIMIT", "planned_rr": 2.35}) == pytest.approx(2.35)


def test_recursive_strategy_view_finds_blocks():
    snapshot = {
        "research": {
            "base": {"strategy_logic": {"logic_version": "V3.14.5"}},
            "quote": {"strategy_logic": {"logic_version": "V3.14.5"}},
        }
    }
    blocks = find_strategy_logic_blocks(snapshot)
    assert len(blocks) == 2


def test_snapshot_freezes_current_strategy_contract():
    src = (ROOT / "src" / "trade_snapshot.py").read_text(encoding="utf-8")
    assert 'SNAPSHOT_BUILDER_VERSION = "V3.14.6"' in src
    assert '"logic_version": "V3.14.5"' in src
    assert '"snapshot_contract_version": "V3.14.6"' in src
    assert '"window_weeks": 156' in src
    assert '"trigger_upper": float(MICRO_TRIGGER_UPPER)' in src
    assert '"fresh_weeks": int(MICRO_TRIGGER_FRESH_WEEKS)' in src
    assert '"feature_timing": "PLAN_TIME"' in src
    assert "classify_macro_micro_trade(decision_row)" in src


def test_journal_uses_effective_rr_and_shows_strategy_snapshot():
    src = (ROOT / "pages" / "trading_journal.py").read_text(encoding="utf-8")
    assert "view.apply(effective_rr, axis=1)" in src
    assert '"EXECUTION R:R"' in src
    assert "find_strategy_logic_blocks(snapshot)" in src
    assert "Strategie-Snapshot · beim Trade eingefroren" in src
    assert "wird nicht rückwirkend mit heutiger Logik beschriftet" in src


def test_patched_files_parse():
    for rel in (
        "src/journal_execution_metrics.py",
        "src/journal_strategy_view.py",
        "src/trade_snapshot.py",
        "pages/trading_journal.py",
    ):
        ast.parse((ROOT / rel).read_text(encoding="utf-8"))
