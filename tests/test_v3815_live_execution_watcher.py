from __future__ import annotations

from pathlib import Path
import time

import pandas as pd

from src.live_execution import resolve_live_entry, watched_symbols
from src.mt5_account import MT5Config, bridge_snapshot, read_bridge_quotes, write_bridge_quote_watch
from src.trade_journal import activate_simulation_trade_live, create_trade_plan, get_trade_events, list_trade_plans
from src.outcome_tracker import evaluate_trade_path


def _plan(**updates):
    plan = {
        "trade_id": "t1",
        "created_at_utc": "2026-08-17T10:00:00Z",
        "plan_type": "SIMULATION",
        "order_type": "MARKET",
        "cfd_symbol": "XAUUSD",
        "side": "LONG",
        "entry": 100.0,
        "stop": 95.0,
        "target": 110.0,
        "expiry_at_utc": None,
    }
    plan.update(updates)
    return plan


def _quote(**updates):
    q = {
        "symbol": "XAUUSD",
        "bid": 100.1,
        "ask": 100.2,
        "last": 0.0,
        "exported_at_utc": pd.Timestamp("2026-08-17T10:00:02Z"),
        "tick_age_seconds": 1.0,
        "trade_mode": 4,
        "can_open": 1,
    }
    q.update(updates)
    return q


def test_market_live_long_uses_ask_and_short_uses_bid():
    long_fill = resolve_live_entry(_plan(side="LONG"), _quote(), now="2026-08-17T10:00:03Z")
    short_fill = resolve_live_entry(_plan(side="SHORT", stop=105.0, target=90.0), _quote(), now="2026-08-17T10:00:03Z")
    assert long_fill["execution_price"] == 100.2
    assert short_fill["execution_price"] == 100.1
    assert long_fill["fill_timeframe"] == "LIVE_TICK"
    assert short_fill["lifecycle_status"] == "ACTIVE"


def test_limit_live_trigger_uses_correct_bid_ask_side():
    buy = resolve_live_entry(
        _plan(order_type="LIMIT", side="LONG", entry=100.3),
        _quote(ask=100.2, bid=100.1),
        now="2026-08-17T10:00:03Z",
    )
    sell = resolve_live_entry(
        _plan(order_type="LIMIT", side="SHORT", entry=100.0, stop=105.0, target=90.0),
        _quote(ask=100.2, bid=100.1),
        now="2026-08-17T10:00:03Z",
    )
    not_buy = resolve_live_entry(
        _plan(order_type="LIMIT", side="LONG", entry=100.0),
        _quote(ask=100.2, bid=99.9),
        now="2026-08-17T10:00:03Z",
    )
    assert buy["execution_price"] == 100.2
    assert buy["live_trigger"] == "BUY_LIMIT_ASK_TOUCH"
    assert sell["execution_price"] == 100.1
    assert sell["live_trigger"] == "SELL_LIMIT_BID_TOUCH"
    assert not_buy is None  # Bid below the limit is irrelevant for a BUY LIMIT; Ask must touch.


def test_recent_pre_plan_export_can_fill_but_stale_export_or_tick_cannot():
    recent = resolve_live_entry(
        _plan(), _quote(exported_at_utc=pd.Timestamp("2026-08-17T09:59:59Z"), tick_age_seconds=1), now="2026-08-17T10:00:03Z"
    )
    assert recent is not None
    assert pd.Timestamp(recent["entry_time_utc"]) == pd.Timestamp("2026-08-17T10:00:00Z")
    assert resolve_live_entry(
        _plan(), _quote(exported_at_utc=pd.Timestamp("2026-08-17T10:00:02Z"), tick_age_seconds=1), now="2026-08-17T10:01:00Z", max_tick_age_seconds=15
    ) is None
    assert resolve_live_entry(
        _plan(), _quote(exported_at_utc=pd.Timestamp("2026-08-17T10:00:02Z"), tick_age_seconds=60), now="2026-08-17T10:00:03Z"
    ) is None




def test_live_entry_requires_openable_direction_and_fresh_tick():
    assert resolve_live_entry(_plan(side="LONG"), _quote(can_open=0), now="2026-08-17T10:00:03Z") is None
    assert resolve_live_entry(_plan(side="LONG"), _quote(trade_mode=2), now="2026-08-17T10:00:03Z") is None
    assert resolve_live_entry(
        _plan(side="SHORT", stop=105.0, target=90.0), _quote(trade_mode=1), now="2026-08-17T10:00:03Z"
    ) is None

def test_watched_symbols_deduplicates_only_supplied_open_plan_rows():
    plans = pd.DataFrame({"cfd_symbol": ["XAUUSD", "USDMXN", "XAUUSD", None]})
    assert watched_symbols(plans) == ["USDMXN", "XAUUSD"]


def test_bridge_fast_quote_file_overlays_slow_symbol_catalog(tmp_path: Path):
    now = int(time.time())
    pd.DataFrame([{
        "timestamp_unix": now, "server_time_unix": now, "login": 1, "server": "FTMO-Server4",
        "name": "Test", "company": "FTMO", "currency": "USD", "balance": 100000,
        "equity": 100000, "profit": 0, "margin": 0, "margin_free": 100000, "margin_level": 0,
        "leverage": 30, "trade_allowed": 0, "trade_expert": 0, "day_start_balance": 100000,
        "daily_realized_pnl": 0,
    }]).to_csv(tmp_path / "cot_mt5_account.csv", sep=";", index=False)
    pd.DataFrame(columns=["ticket", "symbol"]).to_csv(tmp_path / "cot_mt5_positions.csv", sep=";", index=False)
    pd.DataFrame([{
        "symbol": "XAUUSD", "description": "Gold", "path": "Metals", "selected": 1, "visible": 1,
        "trade_mode": 4, "can_open": 1, "bid": 4300.0, "ask": 4300.5, "last": 0.0,
        "contract_size": 100, "tick_size": 0.01, "tick_value": 1.0,
    }]).to_csv(tmp_path / "cot_mt5_symbols.csv", sep=";", index=False)
    pd.DataFrame([{
        "symbol": "XAUUSD", "bid": 4374.29, "ask": 4374.81, "last": 0.0,
        "quote_time_server_unix": now, "exported_at_utc_unix": now, "tick_age_seconds": 1, "trade_mode": 4, "can_open": 1,
    }]).to_csv(tmp_path / "cot_mt5_quotes.csv", sep=";", index=False)

    cfg = MT5Config(mode="bridge", bridge_common_path=str(tmp_path), bridge_max_age_seconds=30)
    snap = bridge_snapshot(cfg)
    row = snap["symbol_catalog"].set_index("symbol").loc["XAUUSD"]
    assert row["bid"] == 4374.29
    assert row["ask"] == 4374.81

    watch_path = write_bridge_quote_watch(cfg, ["XAUUSD", "USDMXN", "XAUUSD"])
    assert watch_path.read_text().splitlines() == ["symbol", "USDMXN", "XAUUSD"]
    quotes = read_bridge_quotes(cfg)
    assert len(quotes) == 1
    assert quotes.iloc[0]["symbol"] == "XAUUSD"


def test_history_replay_preserves_already_resolved_live_limit_fill():
    plan = _plan(
        order_type="LIMIT",
        created_at_utc="2026-08-17T10:00:02Z",  # effective live fill time
        entry=100.2,
        stop=95.0,
        target=110.0,
        _resolved_entry_fill=True,
        _entry_fill_source="LIVE_TICK",
    )
    # No completed H1 after the fill yet: must remain ACTIVE, not revert to PLANNED.
    out = evaluate_trade_path(plan, pd.DataFrame(), timeframe="H1", now="2026-08-17T10:30:00Z")
    assert out["lifecycle_status"] == "ACTIVE"
    assert out["entry_triggered"] == 1
    assert out["execution_price"] == 100.2
    assert out["fill_timeframe"] == "LIVE_TICK"


def test_bridge_source_exports_only_watched_quotes_every_timer_tick():
    source = Path("mt5/MT5ReadOnlyBridge.mq5").read_text(encoding="utf-8")
    assert '#property version   "3.815"' in source
    assert 'QUOTE_WATCH_FILE = "cot_mt5_quote_watch.csv"' in source
    assert 'QUOTES_FILE      = "cot_mt5_quotes.csv"' in source
    assert '"tick_age_seconds"' in source
    assert "void WriteWatchedQuotes()" in source
    assert "SymbolInfoTick(symbol, tick)" in source
    assert "WriteWatchedQuotes();" in source


def test_cycle_processes_only_planned_simulations_and_uses_atomic_activation(monkeypatch, tmp_path):
    import src.live_execution as live

    plans = pd.DataFrame([
        {**_plan(trade_id="p1"), "lifecycle_status": "PLANNED"},
        {**_plan(trade_id="a1"), "lifecycle_status": "ACTIVE"},
    ])
    monkeypatch.setattr(live, "list_trade_plans", lambda **kwargs: plans)
    watched = {}
    monkeypatch.setattr(live, "write_bridge_quote_watch", lambda cfg, symbols: watched.setdefault("symbols", list(symbols)))
    monkeypatch.setattr(live, "read_bridge_quotes", lambda *a, **k: pd.DataFrame([_quote()]))
    activated = []
    monkeypatch.setattr(live, "activate_simulation_trade_live", lambda trade_id, fill, **kwargs: activated.append((trade_id, fill)) or True)

    result = live.live_execution_cycle(
        MT5Config(mode="bridge", bridge_common_path=str(tmp_path)),
        db_path=tmp_path / "journal.sqlite3",
        now="2026-08-17T10:00:03Z",
    )
    assert watched["symbols"] == ["XAUUSD"]
    assert [trade_id for trade_id, _ in activated] == ["p1"]
    assert result["activated"] == 1



def _journal_plan(plan_type="SIMULATION"):
    return {
        "plan_type": plan_type,
        "order_type": "MARKET",
        "asset_class": "Metals",
        "market_name": "Gold",
        "cot_symbol": "GC",
        "cftc_code": "088691",
        "cfd_symbol": "XAUUSD",
        "side": "LONG",
        "zone_type": "DEMAND",
        "timeframe": "H1",
        "zone_low": 99.0,
        "zone_high": 101.0,
        "entry": 100.0,
        "stop": 95.0,
        "target": 110.0,
        "requested_risk_pct": 0.005,
        "zone_freshness": "FRESH",
        "retest_count": 0,
        "quality_grade": "A",
        "notes": "live watcher test",
    }


def test_atomic_live_activation_updates_only_planned_simulation_once(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    sim = create_trade_plan(plan=_journal_plan(), snapshot_payload={"test": True}, db_path=db)
    fill = {
        "tracker_version": "3.8.1.5",
        "lifecycle_status": "ACTIVE",
        "entry_triggered": 1,
        "entry_time_utc": "2026-08-17T10:00:02+00:00",
        "execution_price": 100.2,
        "fill_timeframe": "LIVE_TICK",
        "data_timeframe": "LIVE_TICK",
        "mae_r": 0.0,
        "mfe_r": 0.0,
        "holding_minutes": 0.0,
        "live_trigger": "MARKET_NEXT_QUOTE",
        "live_bid": 100.1,
        "live_ask": 100.2,
        "quote_exported_at_utc": "2026-08-17T10:00:02+00:00",
        "tick_age_seconds": 1.0,
    }
    assert activate_simulation_trade_live(sim["trade_id"], fill, db_path=db) is True
    assert activate_simulation_trade_live(sim["trade_id"], fill, db_path=db) is False
    row = list_trade_plans(db_path=db).iloc[0]
    assert row["lifecycle_status"] == "ACTIVE"
    assert row["execution_price"] == 100.2
    events = get_trade_events(sim["trade_id"], db_path=db)
    assert list(events["event_type"]).count("ENTRY_TRIGGERED_LIVE") == 1


def test_live_activation_never_changes_real_trade(tmp_path: Path):
    db = tmp_path / "journal.sqlite3"
    real = create_trade_plan(plan=_journal_plan("REAL"), snapshot_payload={"test": True}, db_path=db)
    fill = {
        "entry_time_utc": "2026-08-17T10:00:02+00:00",
        "execution_price": 100.2,
        "fill_timeframe": "LIVE_TICK",
    }
    assert activate_simulation_trade_live(real["trade_id"], fill, db_path=db) is False
    row = list_trade_plans(db_path=db).iloc[0]
    assert pd.isna(row["lifecycle_status"])
