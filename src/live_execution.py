from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
import threading
from typing import Any, Mapping

import pandas as pd

from .mt5_account import MT5Config, read_bridge_quotes, write_bridge_quote_watch
from .price_units import plan_to_mt5_units
from .trade_journal import activate_simulation_trade_live, list_trade_plans


WATCHER_VERSION = "3.8.1.5.1"


def _utc(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def watched_symbols(plans: pd.DataFrame) -> list[str]:
    if plans.empty or "cfd_symbol" not in plans.columns:
        return []
    return sorted({str(v).strip() for v in plans["cfd_symbol"].dropna().tolist() if str(v).strip()})


def resolve_live_entry(plan: Mapping[str, Any], quote: Mapping[str, Any], *, now: Any | None = None, max_tick_age_seconds: float = 5.0) -> dict[str, Any] | None:
    """Resolve a live simulated entry from a fresh MT5 tick.

    MARKET: LONG fills on Ask, SHORT on Bid at the first fresh tick after plan creation.
    LIMIT: BUY/LONG triggers when Ask <= entry; SELL/SHORT when Bid >= entry.
    """
    created = _utc(plan["created_at_utc"])
    now_ts = _utc(now or datetime.now(timezone.utc))
    exported_raw = quote.get("exported_at_utc")
    tick_age = _finite(quote.get("tick_age_seconds"))
    if exported_raw is None or pd.isna(exported_raw) or tick_age is None:
        return None
    exported_at = _utc(exported_raw)
    export_age = (now_ts - exported_at).total_seconds()
    if export_age < -2 or export_age > float(max_tick_age_seconds):
        return None
    if tick_age < 0 or tick_age > float(max_tick_age_seconds):
        return None

    normalized = plan_to_mt5_units(plan)
    side = str(normalized.get("side", "") or "").upper()
    order_type = str(normalized.get("order_type", "LIMIT") or "LIMIT").upper()
    bid = _finite(quote.get("bid"))
    ask = _finite(quote.get("ask"))
    entry = _finite(normalized.get("entry"))
    stop = _finite(normalized.get("stop"))
    target = _finite(normalized.get("target"))
    if side not in {"LONG", "SHORT"} or stop is None:
        return None
    if order_type == "LIMIT" and entry is None:
        return None

    can_open = _finite(quote.get("can_open"))
    trade_mode = _finite(quote.get("trade_mode"))
    if can_open is None or int(can_open) != 1:
        return None
    if trade_mode is not None:
        mode = int(trade_mode)
        if mode in {0, 3}:  # disabled / close-only
            return None
        if side == "LONG" and mode == 2:  # short-only
            return None
        if side == "SHORT" and mode == 1:  # long-only
            return None

    execution: float | None = None
    trigger = ""
    if order_type == "MARKET":
        execution = ask if side == "LONG" else bid
        trigger = "MARKET_NEXT_QUOTE"
    elif order_type == "LIMIT":
        if side == "LONG" and ask is not None and ask > 0 and ask <= entry:
            execution = ask
            trigger = "BUY_LIMIT_ASK_TOUCH"
        elif side == "SHORT" and bid is not None and bid > 0 and bid >= entry:
            execution = bid
            trigger = "SELL_LIMIT_BID_TOUCH"
    if execution is None or execution <= 0:
        return None

    # Never manufacture a nonsensical active state after a gap beyond SL/TP.
    if side == "LONG" and execution <= stop:
        return None
    if side == "SHORT" and execution >= stop:
        return None
    if target is not None:
        if side == "LONG" and execution >= target:
            return None
        if side == "SHORT" and execution <= target:
            return None

    return {
        "tracker_version": WATCHER_VERSION,
        "lifecycle_status": "ACTIVE",
        "entry_triggered": 1,
        "entry_time_utc": max(created, exported_at).isoformat(),
        "execution_price": float(execution),
        "fill_timeframe": "LIVE_TICK",
        "data_timeframe": "LIVE_TICK",
        "mae_r": 0.0,
        "mfe_r": 0.0,
        "holding_minutes": max(0.0, (now_ts - max(created, exported_at)).total_seconds() / 60.0),
        "ambiguity_reason": None,
        "live_trigger": trigger,
        "live_bid": bid,
        "live_ask": ask,
        "quote_exported_at_utc": exported_at.isoformat(),
        "tick_age_seconds": float(tick_age),
    }


def live_execution_cycle(
    config: MT5Config,
    *,
    db_path: str | Path,
    now: Any | None = None,
    max_tick_age_seconds: float = 5.0,
    limit: int = 10_000,
) -> dict[str, Any]:
    """Run one local watcher iteration. No order-send/trade mutation is possible."""
    plans = list_trade_plans(
        db_path=db_path,
        limit=limit,
        plan_type="SIMULATION",
        lifecycle_statuses=("PLANNED", "ACTIVE"),
    )
    symbols = watched_symbols(plans)
    write_bridge_quote_watch(config, symbols)
    quotes = read_bridge_quotes(config, max_age_seconds=max(3, int(max_tick_age_seconds)))
    quote_map: dict[str, dict[str, Any]] = {}
    if not quotes.empty:
        for _, row in quotes.iterrows():
            quote_map[str(row.get("symbol", "")).upper()] = row.to_dict()

    if plans.empty:
        return {"watched_symbols": 0, "planned": 0, "activated": 0, "quote_rows": len(quotes)}

    status = plans.get("lifecycle_status", pd.Series(index=plans.index, dtype=object)).fillna("PLANNED").astype(str).str.upper()
    pending = plans[status.eq("PLANNED")]
    activated = 0
    for _, row in pending.iterrows():
        plan = row.to_dict()
        trade_id = str(plan.get("trade_id", ""))
        quote = quote_map.get(str(plan.get("cfd_symbol", "")).upper())
        if not trade_id or quote is None:
            continue
        fill = resolve_live_entry(plan, quote, now=now, max_tick_age_seconds=max_tick_age_seconds)
        if fill is None:
            continue

        if activate_simulation_trade_live(trade_id, fill, db_path=db_path):
            activated += 1

    return {
        "watched_symbols": len(symbols),
        "planned": int(len(pending)),
        "activated": activated,
        "quote_rows": int(len(quotes)),
    }


@dataclass
class LiveExecutionWatcher:
    config: MT5Config
    db_path: str | Path
    interval_seconds: float = 2.0
    max_tick_age_seconds: float = 5.0

    def __post_init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_cycle: dict[str, Any] = {}
        self.last_error: str | None = None
        self.last_run_utc: str | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="cot-live-execution-watcher", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.last_cycle = live_execution_cycle(
                    self.config,
                    db_path=self.db_path,
                    max_tick_age_seconds=self.max_tick_age_seconds,
                )
                self.last_error = None
            except Exception as exc:  # keep gateway alive; expose error through health/status
                self.last_error = str(exc)
            self.last_run_utc = datetime.now(timezone.utc).isoformat()
            self._stop.wait(max(0.5, float(self.interval_seconds)))

    def status(self) -> dict[str, Any]:
        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "last_run_utc": self.last_run_utc,
            "last_error": self.last_error,
            "last_cycle": dict(self.last_cycle),
            "interval_seconds": float(self.interval_seconds),
        }
