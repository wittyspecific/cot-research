from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .ftmo_risk import size_trade
from .trade_journal import canonical_json, get_trade_snapshot, initialize_journal, journal_connection

DEFAULT_STARTING_CAPITAL = 200_000.0
DEFAULT_RISK_PCT = 0.005
DEFAULT_MAX_RISK_PCT = 0.01


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _finite(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def _prop_schema(db_path: str | Path | None = None) -> Path:
    path = initialize_journal(db_path)
    with journal_connection(path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS prop_accounts (
                trader_id TEXT PRIMARY KEY REFERENCES traders(trader_id),
                starting_capital REAL NOT NULL DEFAULT 200000,
                currency TEXT NOT NULL DEFAULT 'USD',
                default_risk_pct REAL NOT NULL DEFAULT 0.005,
                max_risk_pct REAL NOT NULL DEFAULT 0.01,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS prop_trade_allocations (
                trade_id TEXT PRIMARY KEY REFERENCES trade_plans(trade_id),
                trader_id TEXT NOT NULL REFERENCES traders(trader_id),
                balance_at_plan REAL NOT NULL,
                requested_risk_pct REAL NOT NULL,
                risk_budget REAL NOT NULL,
                lots REAL,
                raw_lots REAL,
                actual_risk REAL,
                risk_per_lot REAL,
                tick_size REAL,
                tick_value REAL,
                volume_min REAL,
                volume_max REAL,
                volume_step REAL,
                sizing_status TEXT NOT NULL,
                sizing_reason TEXT,
                created_at_utc TEXT NOT NULL,
                sizing_payload_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_prop_allocations_trader
            ON prop_trade_allocations(trader_id, created_at_utc);

            CREATE TRIGGER IF NOT EXISTS no_update_prop_trade_allocations
            BEFORE UPDATE ON prop_trade_allocations
            BEGIN SELECT RAISE(ABORT, 'prop_trade_allocations are immutable'); END;

            CREATE TRIGGER IF NOT EXISTS no_delete_prop_trade_allocations
            BEFORE DELETE ON prop_trade_allocations
            BEGIN SELECT RAISE(ABORT, 'prop_trade_allocations are immutable'); END;
            """
        )
    return path


def ensure_prop_account(
    trader_id: str,
    *,
    db_path: str | Path | None = None,
    starting_capital: float = DEFAULT_STARTING_CAPITAL,
    currency: str = "USD",
    default_risk_pct: float = DEFAULT_RISK_PCT,
    max_risk_pct: float = DEFAULT_MAX_RISK_PCT,
) -> dict[str, Any]:
    path = _prop_schema(db_path)
    trader_id = str(trader_id or "").strip()
    if not trader_id:
        raise ValueError("Trader-ID fehlt.")
    starting_capital = float(starting_capital)
    default_risk_pct = float(default_risk_pct)
    max_risk_pct = float(max_risk_pct)
    if not np.isfinite(starting_capital) or starting_capital <= 0:
        raise ValueError("Virtuelles Startkapital muss positiv sein.")
    if not (0 < default_risk_pct <= max_risk_pct <= 0.05):
        raise ValueError("Prop-Risk muss 0 < Default Risk <= Max Risk <= 5% erfüllen.")
    now = _utc_now_iso()
    with journal_connection(path) as con:
        if not con.execute("SELECT 1 FROM traders WHERE trader_id=?", (trader_id,)).fetchone():
            raise KeyError("Unbekannter Trader.")
        con.execute(
            """
            INSERT OR IGNORE INTO prop_accounts(
                trader_id, starting_capital, currency, default_risk_pct, max_risk_pct,
                enabled, created_at_utc, updated_at_utc
            ) VALUES(?,?,?,?,?,1,?,?)
            """,
            (trader_id, starting_capital, str(currency or "USD").upper(), default_risk_pct, max_risk_pct, now, now),
        )
        row = con.execute("SELECT * FROM prop_accounts WHERE trader_id=?", (trader_id,)).fetchone()
    return dict(row)


def get_prop_account(trader_id: str, *, db_path: str | Path | None = None) -> dict[str, Any]:
    return ensure_prop_account(str(trader_id), db_path=db_path)


def update_prop_account(
    trader_id: str,
    *,
    starting_capital: float | None = None,
    default_risk_pct: float | None = None,
    max_risk_pct: float | None = None,
    enabled: bool | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    path = _prop_schema(db_path)
    current = ensure_prop_account(trader_id, db_path=path)
    new_start = float(current["starting_capital"] if starting_capital is None else starting_capital)
    new_default = float(current["default_risk_pct"] if default_risk_pct is None else default_risk_pct)
    new_max = float(current["max_risk_pct"] if max_risk_pct is None else max_risk_pct)
    new_enabled = bool(current["enabled"] if enabled is None else enabled)
    if not np.isfinite(new_start) or new_start <= 0:
        raise ValueError("Virtuelles Startkapital muss positiv sein.")
    if not (0 < new_default <= new_max <= 0.05):
        raise ValueError("Prop-Risk muss 0 < Default Risk <= Max Risk <= 5% erfüllen.")
    with journal_connection(path) as con:
        allocation_count = int(con.execute(
            "SELECT COUNT(*) FROM prop_trade_allocations WHERE trader_id=?",
            (str(trader_id),),
        ).fetchone()[0])
        if allocation_count and not math.isclose(new_start, float(current["starting_capital"]), rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("Startkapital kann nach dem ersten Prop-Trade nicht mehr geändert werden. Alte Positionsgrößen bleiben absichtlich unveränderlich.")
        con.execute(
            """
            UPDATE prop_accounts
            SET starting_capital=?, default_risk_pct=?, max_risk_pct=?, enabled=?, updated_at_utc=?
            WHERE trader_id=?
            """,
            (new_start, new_default, new_max, int(new_enabled), _utc_now_iso(), str(trader_id)),
        )
        row = con.execute("SELECT * FROM prop_accounts WHERE trader_id=?", (str(trader_id),)).fetchone()
    return dict(row)


def _closed_rows(trader_id: str, *, db_path: str | Path) -> pd.DataFrame:
    query = """
        SELECT p.trade_id, p.cfd_symbol, p.side, p.entry, p.stop, p.target,
               p.created_at_utc, a.balance_at_plan, a.requested_risk_pct,
               a.risk_budget, a.lots, a.actual_risk, a.risk_per_lot, a.tick_size, a.tick_value, a.sizing_status,
               o.lifecycle_status, o.exit_time_utc, o.result_r, o.first_exit,
               o.entry_time_utc, o.execution_price, o.fill_timeframe
        FROM prop_trade_allocations a
        JOIN trade_plans p ON p.trade_id=a.trade_id
        LEFT JOIN trade_outcomes o ON o.trade_id=p.trade_id
        WHERE a.trader_id=? AND p.plan_type='SIMULATION'
        ORDER BY COALESCE(o.exit_time_utc, p.created_at_utc), p.created_at_utc, p.trade_id
    """
    with journal_connection(db_path) as con:
        return pd.read_sql_query(query, con, params=[str(trader_id)])


def realized_balance(
    trader_id: str, *, db_path: str | Path | None = None, as_of_utc: str | None = None
) -> float:
    path = _prop_schema(db_path)
    account = ensure_prop_account(trader_id, db_path=path)
    df = _closed_rows(trader_id, db_path=path)
    if df.empty:
        return float(account["starting_capital"])
    result = pd.to_numeric(df.get("result_r"), errors="coerce")
    effective_risk = df.apply(_effective_risk_usd, axis=1)
    closed = df.get("lifecycle_status", pd.Series(index=df.index, dtype=object)).fillna("").astype(str).str.upper().eq("CLOSED")
    if as_of_utc:
        exits = pd.to_datetime(df.get("exit_time_utc"), errors="coerce", utc=True)
        cutoff = pd.to_datetime(as_of_utc, errors="coerce", utc=True)
        if pd.notna(cutoff):
            closed = closed & exits.notna() & exits.le(cutoff)
    pnl = (result * effective_risk).where(closed, 0.0).fillna(0.0)
    return float(account["starting_capital"] + pnl.sum())


def _snapshot_spec(snapshot_payload: Mapping[str, Any]) -> dict[str, Any]:
    mt5_symbol = snapshot_payload.get("mt5_symbol") if isinstance(snapshot_payload, Mapping) else None
    if not isinstance(mt5_symbol, Mapping):
        return {}
    spec = mt5_symbol.get("spec")
    return dict(spec) if isinstance(spec, Mapping) else {}


def create_prop_allocation(
    *,
    trade_id: str,
    trader_id: str | None,
    plan: Mapping[str, Any],
    snapshot_payload: Mapping[str, Any],
    db_path: str | Path | None = None,
    balance_as_of_utc: str | None = None,
) -> dict[str, Any] | None:
    """Freeze virtual account sizing for SIMULATION trades only.

    Balance/risk/lots are immutable once the plan is stored. This prevents a later
    account balance from retroactively changing historical position size.
    """
    if str(plan.get("plan_type", "")).upper() != "SIMULATION" or not trader_id:
        return None
    path = _prop_schema(db_path)
    account = ensure_prop_account(str(trader_id), db_path=path)
    if not bool(account.get("enabled", 1)):
        return None
    requested = float(plan.get("requested_risk_pct", account["default_risk_pct"]) or account["default_risk_pct"])
    max_risk = float(account["max_risk_pct"])
    balance = realized_balance(str(trader_id), db_path=path, as_of_utc=balance_as_of_utc)
    risk_budget = balance * max(requested, 0.0)
    spec = _snapshot_spec(snapshot_payload)
    if requested <= 0 or requested > max_risk + 1e-12:
        sizing = {"ok": False, "reason": f"Prop-Desk Risiko muss zwischen 0 und {max_risk*100:.2f}% liegen."}
        status = "BLOCKED"
    else:
        sizing = size_trade(
            spec,
            side=str(plan.get("side", "")),
            entry=float(plan.get("entry")),
            stop=float(plan.get("stop")),
            risk_budget=float(risk_budget),
        )
        status = "SIZED" if bool(sizing.get("ok")) else "UNSIZED"
    reason = "" if status == "SIZED" else str(sizing.get("reason", "Positionsgröße nicht berechenbar."))
    tick_value = _finite(spec.get("tick_value_loss"))
    if not np.isfinite(tick_value) or tick_value <= 0:
        tick_value = _finite(spec.get("tick_value"))
    row = {
        "trade_id": str(trade_id),
        "trader_id": str(trader_id),
        "balance_at_plan": float(balance),
        "requested_risk_pct": requested,
        "risk_budget": float(risk_budget),
        "lots": _finite(sizing.get("lots"), np.nan),
        "raw_lots": _finite(sizing.get("raw_lots"), np.nan),
        "actual_risk": _finite(sizing.get("actual_risk"), np.nan),
        "risk_per_lot": _finite(sizing.get("risk_per_lot"), np.nan),
        "tick_size": _finite(spec.get("tick_size"), np.nan),
        "tick_value": tick_value,
        "volume_min": _finite(spec.get("volume_min"), np.nan),
        "volume_max": _finite(spec.get("volume_max"), np.nan),
        "volume_step": _finite(spec.get("volume_step"), np.nan),
        "sizing_status": status,
        "sizing_reason": reason,
        "created_at_utc": _utc_now_iso(),
        "sizing_payload_json": canonical_json(sizing),
    }
    with journal_connection(path) as con:
        existing = con.execute("SELECT * FROM prop_trade_allocations WHERE trade_id=?", (str(trade_id),)).fetchone()
        if existing is not None:
            return dict(existing)
        con.execute(
            """
            INSERT INTO prop_trade_allocations(
                trade_id, trader_id, balance_at_plan, requested_risk_pct, risk_budget,
                lots, raw_lots, actual_risk, risk_per_lot, tick_size, tick_value,
                volume_min, volume_max, volume_step, sizing_status, sizing_reason,
                created_at_utc, sizing_payload_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row["trade_id"], row["trader_id"], row["balance_at_plan"], row["requested_risk_pct"], row["risk_budget"],
                row["lots"], row["raw_lots"], row["actual_risk"], row["risk_per_lot"], row["tick_size"], row["tick_value"],
                row["volume_min"], row["volume_max"], row["volume_step"], row["sizing_status"], row["sizing_reason"],
                row["created_at_utc"], row["sizing_payload_json"],
            ),
        )
    return row


def backfill_prop_allocations(trader_id: str, *, db_path: str | Path | None = None) -> int:
    """Create missing immutable allocations for pre-V3.8 SIMULATION plans.

    Plans are processed chronologically. Realized balance is evaluated as-of each
    plan timestamp so later exits cannot inflate historical position sizing.
    """
    path = _prop_schema(db_path)
    ensure_prop_account(trader_id, db_path=path)
    with journal_connection(path) as con:
        rows = con.execute(
            """
            SELECT p.trade_id, p.created_at_utc
            FROM trade_plans p
            LEFT JOIN prop_trade_allocations a ON a.trade_id=p.trade_id
            LEFT JOIN trade_outcomes o ON o.trade_id=p.trade_id
            WHERE p.trader_id=? AND p.plan_type='SIMULATION' AND a.trade_id IS NULL
              AND COALESCE(o.lifecycle_status, 'PLANNED') <> 'VOID'
            ORDER BY p.created_at_utc, p.trade_id
            """,
            (str(trader_id),),
        ).fetchall()
    created = 0
    for row in rows:
        trade_id = str(row["trade_id"])
        with journal_connection(path) as con:
            plan_row = con.execute("SELECT * FROM trade_plans WHERE trade_id=?", (trade_id,)).fetchone()
        if plan_row is None:
            continue
        try:
            snapshot = get_trade_snapshot(trade_id, db_path=path)
            allocation = create_prop_allocation(
                trade_id=trade_id,
                trader_id=str(trader_id),
                plan=dict(plan_row),
                snapshot_payload=snapshot,
                db_path=path,
                balance_as_of_utc=str(row["created_at_utc"]),
            )
            if allocation:
                created += 1
        except Exception:
            # A legacy plan with incomplete historical symbol specs remains visible
            # in the journal but is not guessed into the virtual account.
            continue
    return created


def get_prop_allocation(trade_id: str, *, db_path: str | Path | None = None) -> dict[str, Any]:
    path = _prop_schema(db_path)
    with journal_connection(path) as con:
        row = con.execute("SELECT * FROM prop_trade_allocations WHERE trade_id=?", (str(trade_id),)).fetchone()
    return dict(row) if row is not None else {}


def _catalog_map(mt5_snapshot: Mapping[str, Any] | None) -> tuple[dict[str, dict[str, Any]], str | None]:
    if not mt5_snapshot:
        return {}, None
    catalog = mt5_snapshot.get("symbol_catalog")
    if not isinstance(catalog, pd.DataFrame) or catalog.empty or "symbol" not in catalog.columns:
        return {}, str(mt5_snapshot.get("captured_at") or "") or None
    rows = {}
    for _, row in catalog.iterrows():
        rows[str(row.get("symbol", "")).upper()] = row.to_dict()
    captured = mt5_snapshot.get("captured_at")
    return rows, str(captured) if captured is not None else None


def _liquidation_mark(spec: Mapping[str, Any], side: str) -> float:
    side = str(side or "").upper()
    bid = _finite(spec.get("bid"))
    ask = _finite(spec.get("ask"))
    last = _finite(spec.get("last"))
    if side == "LONG" and np.isfinite(bid) and bid > 0:
        return bid
    if side == "SHORT" and np.isfinite(ask) and ask > 0:
        return ask
    if np.isfinite(last) and last > 0:
        return last
    if np.isfinite(bid) and np.isfinite(ask) and bid > 0 and ask > 0:
        return (bid + ask) / 2.0
    if np.isfinite(bid) and bid > 0:
        return bid
    if np.isfinite(ask) and ask > 0:
        return ask
    return np.nan


def _effective_entry(row: Mapping[str, Any]) -> float:
    execution = _finite(row.get("execution_price"))
    if np.isfinite(execution):
        return execution
    return _finite(row.get("entry"))


def _effective_risk_usd(row: Mapping[str, Any]) -> float:
    """Actual stop risk using the resolved MARKET fill when available."""
    entry = _effective_entry(row)
    stop = _finite(row.get("stop"))
    lots = _finite(row.get("lots"))
    tick_size = _finite(row.get("tick_size"))
    tick_value = _finite(row.get("tick_value"))
    if all(np.isfinite(v) for v in (entry, stop, lots, tick_size, tick_value)) and lots > 0 and tick_size > 0 and tick_value > 0:
        return float((abs(entry - stop) / tick_size) * tick_value * lots)
    return _finite(row.get("actual_risk"), 0.0)


def _floating_pnl(row: Mapping[str, Any], mark: float) -> float:
    if not np.isfinite(mark):
        return np.nan
    lots = _finite(row.get("lots"))
    tick_size = _finite(row.get("tick_size"))
    tick_value = _finite(row.get("tick_value"))
    entry = _effective_entry(row)
    if not all(np.isfinite(v) for v in (lots, tick_size, tick_value, entry)) or lots <= 0 or tick_size <= 0 or tick_value <= 0:
        return np.nan
    signed_move = (mark - entry) if str(row.get("side", "")).upper() == "LONG" else (entry - mark)
    return float((signed_move / tick_size) * tick_value * lots)


def prop_desk_state(
    trader_id: str,
    *,
    db_path: str | Path | None = None,
    mt5_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    path = _prop_schema(db_path)
    account = ensure_prop_account(trader_id, db_path=path)
    backfill_prop_allocations(trader_id, db_path=path)
    df = _closed_rows(trader_id, db_path=path)
    if df.empty:
        return {
            "account": account,
            "summary": {
                "starting_capital": float(account["starting_capital"]), "balance": float(account["starting_capital"]),
                "equity": float(account["starting_capital"]), "realized_pnl": 0.0, "floating_pnl": 0.0,
                "return_pct": 0.0, "current_drawdown_pct": 0.0, "max_drawdown_pct": 0.0,
                "open_positions": 0, "closed_trades": 0, "win_rate": np.nan, "profit_factor": np.nan,
                "expectancy_r": np.nan, "open_risk": 0.0, "open_risk_pct": 0.0,
            },
            "open_positions": [], "closed_trades": [],
            "equity_curve": [{"time_utc": account["created_at_utc"], "balance": float(account["starting_capital"]), "equity": float(account["starting_capital"])}],
            "mark_time": None, "price_source": "NO_ACTIVE_POSITIONS",
        }

    status = df.get("lifecycle_status", pd.Series(index=df.index, dtype=object)).fillna("PLANNED").astype(str).str.upper()
    result_r = pd.to_numeric(df.get("result_r"), errors="coerce")
    effective_risk = df.apply(_effective_risk_usd, axis=1)
    realized_each = (result_r * effective_risk).where(status.eq("CLOSED"), 0.0).fillna(0.0)
    realized_pnl = float(realized_each.sum())
    balance = float(account["starting_capital"] + realized_pnl)

    catalog, mark_time = _catalog_map(mt5_snapshot)
    open_rows: list[dict[str, Any]] = []
    floating_values: list[float] = []
    active_df = df[status.eq("ACTIVE")].copy()
    for _, row in active_df.iterrows():
        data = row.to_dict()
        spec = catalog.get(str(data.get("cfd_symbol", "")).upper(), {})
        mark = _liquidation_mark(spec, str(data.get("side", "")))
        pnl = _floating_pnl(data, mark)
        if np.isfinite(pnl):
            floating_values.append(float(pnl))
        risk = _effective_risk_usd(data)
        current_r = float(pnl / risk) if np.isfinite(pnl) and risk > 0 else np.nan
        open_rows.append({
            "trade_id": data.get("trade_id"), "symbol": data.get("cfd_symbol"), "side": data.get("side"),
            "entry": _effective_entry(data), "planned_entry": _finite(data.get("entry")), "stop": _finite(data.get("stop")), "target": _finite(data.get("target")),
            "lots": _finite(data.get("lots")), "risk_usd": risk, "risk_pct_at_plan": _finite(data.get("requested_risk_pct")),
            "mark": mark, "floating_pnl": pnl, "current_r": current_r,
            "entry_time_utc": data.get("entry_time_utc"), "mark_time_utc": mark_time,
        })
    floating_pnl = float(sum(floating_values)) if floating_values else 0.0
    equity = float(balance + floating_pnl)

    closed_df = df[status.eq("CLOSED")].copy()
    closed_rows: list[dict[str, Any]] = []
    for idx, row in closed_df.iterrows():
        pnl = float(realized_each.loc[idx])
        closed_rows.append({
            "trade_id": row.get("trade_id"), "symbol": row.get("cfd_symbol"), "side": row.get("side"),
            "exit_time_utc": row.get("exit_time_utc"), "result_r": _finite(row.get("result_r")),
            "realized_pnl": pnl, "lots": _finite(row.get("lots")), "risk_usd": _effective_risk_usd(row),
            "entry": _effective_entry(row), "planned_entry": _finite(row.get("entry")), "fill_timeframe": row.get("fill_timeframe"),
            "first_exit": row.get("first_exit"),
        })
    closed_rows.sort(key=lambda x: str(x.get("exit_time_utc") or ""), reverse=True)

    start = float(account["starting_capital"])
    running = start
    curve: list[dict[str, Any]] = [{"time_utc": account["created_at_utc"], "balance": start, "equity": start}]
    ordered = sorted(closed_rows, key=lambda x: str(x.get("exit_time_utc") or ""))
    for item in ordered:
        running += float(item["realized_pnl"])
        curve.append({"time_utc": item.get("exit_time_utc"), "balance": running, "equity": running})
    curve.append({"time_utc": mark_time or _utc_now_iso(), "balance": balance, "equity": equity})
    curve_values = np.array([float(x["equity"]) for x in curve], dtype=float)
    peaks = np.maximum.accumulate(curve_values)
    dd = np.where(peaks > 0, (curve_values - peaks) / peaks, 0.0)
    max_dd = float(abs(np.nanmin(dd))) if len(dd) else 0.0
    current_dd = float(abs(dd[-1])) if len(dd) else 0.0

    closed_results = pd.to_numeric(closed_df.get("result_r"), errors="coerce")
    wins = int((closed_results > 0).sum())
    closed_count = int(closed_results.notna().sum())
    win_rate = float(wins / closed_count) if closed_count else np.nan
    pos = sum(max(float(x["realized_pnl"]), 0.0) for x in closed_rows)
    neg = abs(sum(min(float(x["realized_pnl"]), 0.0) for x in closed_rows))
    profit_factor = float(pos / neg) if neg > 0 else (float("inf") if pos > 0 else np.nan)
    open_risk = float(sum(max(_finite(x.get("risk_usd"), 0.0), 0.0) for x in open_rows))

    return {
        "account": account,
        "summary": {
            "starting_capital": start, "balance": balance, "equity": equity,
            "realized_pnl": realized_pnl, "floating_pnl": floating_pnl,
            "return_pct": float((equity / start) - 1.0) if start else np.nan,
            "current_drawdown_pct": current_dd, "max_drawdown_pct": max_dd,
            "open_positions": len(open_rows), "closed_trades": closed_count,
            "win_rate": win_rate, "profit_factor": profit_factor,
            "expectancy_r": float(closed_results.mean()) if closed_count else np.nan,
            "open_risk": open_risk, "open_risk_pct": float(open_risk / balance) if balance > 0 else np.nan,
        },
        "open_positions": open_rows,
        "closed_trades": closed_rows[:500],
        "equity_curve": curve,
        "mark_time": mark_time,
        "price_source": "LOCAL_MT5_BRIDGE_QUOTES" if catalog else "NO_CURRENT_MARKS",
    }


def prop_desk_ranking(*, db_path: str | Path | None = None, mt5_snapshot: Mapping[str, Any] | None = None) -> pd.DataFrame:
    path = _prop_schema(db_path)
    with journal_connection(path) as con:
        traders = pd.read_sql_query(
            "SELECT trader_id, username, display_name, role, active FROM traders WHERE active=1 ORDER BY display_name COLLATE NOCASE",
            con,
        )
    rows: list[dict[str, Any]] = []
    for _, trader in traders.iterrows():
        state = prop_desk_state(str(trader["trader_id"]), db_path=path, mt5_snapshot=mt5_snapshot)
        summary = state["summary"]
        rows.append({
            "trader_id": trader["trader_id"], "display_name": trader["display_name"], "username": trader["username"],
            "equity": summary["equity"], "balance": summary["balance"], "return_pct": summary["return_pct"],
            "max_drawdown_pct": summary["max_drawdown_pct"], "open_risk_pct": summary["open_risk_pct"],
            "floating_pnl": summary["floating_pnl"], "realized_pnl": summary["realized_pnl"],
            "open_positions": summary["open_positions"], "closed_trades": summary["closed_trades"],
            "win_rate": summary["win_rate"], "profit_factor": summary["profit_factor"], "expectancy_r": summary["expectancy_r"],
        })
    return pd.DataFrame(rows)
