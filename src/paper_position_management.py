from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import json
import math
import sqlite3
import uuid

import pandas as pd

from .price_units import plan_to_mt5_units
from .trade_journal import initialize_journal, journal_connection


MANAGEMENT_VERSION = "3.15.0"
DEFAULT_MAX_TICK_AGE_SECONDS = 5.0


class PaperPositionManagementError(RuntimeError):
    pass


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _utc(value: Any | None = None) -> pd.Timestamp:
    ts = pd.Timestamp(value if value is not None else datetime.now(timezone.utc))
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)


def _schema(db_path: str | Path | None = None) -> Path:
    path = initialize_journal(db_path)
    with journal_connection(path) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_position_management(
                trade_id TEXT PRIMARY KEY,
                break_even_active INTEGER NOT NULL DEFAULT 0,
                current_stop_mt5 REAL,
                stop_effective_at_utc TEXT,
                exit_price_mt5 REAL,
                exit_time_utc TEXT,
                exit_reason TEXT,
                updated_at_utc TEXT NOT NULL,
                updated_by_trader_id TEXT NOT NULL,
                FOREIGN KEY(trade_id) REFERENCES trade_plans(trade_id)
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_position_management_events(
                event_id TEXT PRIMARY KEY,
                trade_id TEXT NOT NULL,
                occurred_at_utc TEXT NOT NULL,
                actor_trader_id TEXT NOT NULL,
                action TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                old_stop_mt5 REAL,
                new_stop_mt5 REAL,
                execution_price_mt5 REAL,
                exit_price_mt5 REAL,
                bid_mt5 REAL,
                ask_mt5 REAL,
                quote_exported_at_utc TEXT,
                tick_age_seconds REAL,
                result_r REAL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(trade_id) REFERENCES trade_plans(trade_id)
            )
            """
        )
        con.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_paper_management_events_trade_time
            ON paper_position_management_events(trade_id, occurred_at_utc DESC)
            """
        )
        con.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_paper_management_events_no_update
            BEFORE UPDATE ON paper_position_management_events
            BEGIN
                SELECT RAISE(ABORT, 'paper_position_management_events is append-only');
            END
            """
        )
        con.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_paper_management_events_no_delete
            BEFORE DELETE ON paper_position_management_events
            BEGIN
                SELECT RAISE(ABORT, 'paper_position_management_events is append-only');
            END
            """
        )
    return path


def _trade_row(
    con: sqlite3.Connection,
    trade_id: str,
    *,
    actor_trader_id: str | None,
    authorize: bool,
) -> dict[str, Any]:
    row = con.execute(
        """
        SELECT
            p.trade_id, p.trader_id, p.plan_type, p.cfd_symbol, p.side,
            p.entry, p.stop, p.target, p.created_at_utc,
            o.lifecycle_status, o.entry_triggered, o.entry_time_utc,
            o.execution_price, o.fill_timeframe, o.holding_minutes,
            o.payload_json
        FROM trade_plans p
        LEFT JOIN trade_outcomes o ON o.trade_id=p.trade_id
        WHERE p.trade_id=?
        """,
        (str(trade_id),),
    ).fetchone()
    if row is None:
        raise PaperPositionManagementError("Trade nicht gefunden.")
    trade = dict(row)
    if str(trade.get("plan_type") or "").upper() != "SIMULATION":
        raise PaperPositionManagementError("Positionsmanagement ist nur für SIMULATION-Trades erlaubt.")
    if str(trade.get("lifecycle_status") or "PLANNED").upper() != "ACTIVE":
        raise PaperPositionManagementError("Der Trade ist nicht ACTIVE.")
    if int(trade.get("entry_triggered") or 0) != 1:
        raise PaperPositionManagementError("Der Trade besitzt noch keinen bestätigten Fill.")

    if authorize:
        actor_id = str(actor_trader_id or "").strip()
        actor = con.execute(
            "SELECT trader_id, role FROM traders WHERE trader_id=?",
            (actor_id,),
        ).fetchone()
        if actor is None:
            raise PermissionError("Trader-Sitzung ist ungültig.")
        if str(actor["role"] or "TRADER").upper() != "ADMIN" and str(trade["trader_id"]) != actor_id:
            raise PermissionError("Kein Zugriff auf diesen Trade.")
    return trade


def _plan_mt5(trade: Mapping[str, Any]) -> dict[str, Any]:
    return plan_to_mt5_units(dict(trade))


def _management_row(con: sqlite3.Connection, trade_id: str) -> dict[str, Any] | None:
    row = con.execute(
        "SELECT * FROM paper_position_management WHERE trade_id=?",
        (str(trade_id),),
    ).fetchone()
    return dict(row) if row is not None else None


def _append_event(
    con: sqlite3.Connection,
    *,
    trade: Mapping[str, Any],
    actor_trader_id: str,
    action: str,
    occurred_at_utc: str,
    old_stop_mt5: float | None = None,
    new_stop_mt5: float | None = None,
    exit_price_mt5: float | None = None,
    quote: Mapping[str, Any] | None = None,
    result_r: float | None = None,
    extra: Mapping[str, Any] | None = None,
) -> str:
    quote = dict(quote or {})
    payload = dict(extra or {})
    payload.update({
        "management_version": MANAGEMENT_VERSION,
        "effective_at_utc": occurred_at_utc,
        "retroactive": False,
    })
    event_id = str(uuid.uuid4())
    con.execute(
        """
        INSERT INTO paper_position_management_events(
            event_id, trade_id, occurred_at_utc, actor_trader_id, action,
            symbol, side, old_stop_mt5, new_stop_mt5, execution_price_mt5,
            exit_price_mt5, bid_mt5, ask_mt5, quote_exported_at_utc,
            tick_age_seconds, result_r, payload_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            event_id,
            str(trade["trade_id"]),
            occurred_at_utc,
            str(actor_trader_id),
            str(action).upper(),
            str(trade["cfd_symbol"]),
            str(trade["side"]).upper(),
            old_stop_mt5,
            new_stop_mt5,
            _finite(trade.get("execution_price")),
            exit_price_mt5,
            _finite(quote.get("bid")),
            _finite(quote.get("ask")),
            None if quote.get("exported_at_utc") in (None, "") else str(quote.get("exported_at_utc")),
            _finite(quote.get("tick_age_seconds")),
            result_r,
            _json(payload),
        ),
    )
    trade_payload = {
        **payload,
        "old_stop_mt5": old_stop_mt5,
        "new_stop_mt5": new_stop_mt5,
        "exit_price_mt5": exit_price_mt5,
        "bid_mt5": _finite(quote.get("bid")),
        "ask_mt5": _finite(quote.get("ask")),
        "result_r": result_r,
        "actor_trader_id": str(actor_trader_id),
    }
    con.execute(
        """
        INSERT INTO trade_events(
            event_id, trade_id, occurred_at_utc, occurred_at_local,
            event_type, source, payload_json
        ) VALUES(?,?,?,?,?,?,?)
        """,
        (
            str(uuid.uuid4()),
            str(trade["trade_id"]),
            occurred_at_utc,
            datetime.now().astimezone().isoformat(),
            f"PAPER_{str(action).upper()}",
            "SYSTEM" if str(actor_trader_id) == "SYSTEM" else "USER",
            _json(trade_payload),
        ),
    )
    return event_id


def records_json_safe(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient="records"):
        clean: dict[str, Any] = {}
        for key, value in raw.items():
            if value is None:
                clean[key] = None
                continue
            try:
                if pd.isna(value):
                    clean[key] = None
                    continue
            except (TypeError, ValueError):
                pass
            if isinstance(value, pd.Timestamp):
                clean[key] = value.isoformat()
            elif hasattr(value, "item"):
                try:
                    clean[key] = value.item()
                except Exception:
                    clean[key] = str(value)
            else:
                clean[key] = value
        rows.append(clean)
    return rows


def list_active_paper_positions(
    *,
    trader_id: str | None = None,
    db_path: str | Path | None = None,
) -> pd.DataFrame:
    path = _schema(db_path)
    sql = """
        SELECT
            p.trade_id, p.trader_id, p.created_at_utc, p.cfd_symbol,
            p.side, p.order_type, p.entry, p.stop, p.target,
            o.entry_time_utc, o.execution_price, o.fill_timeframe,
            COALESCE(m.break_even_active, 0) AS break_even_active,
            m.current_stop_mt5, m.stop_effective_at_utc
        FROM trade_plans p
        JOIN trade_outcomes o ON o.trade_id=p.trade_id
        LEFT JOIN paper_position_management m ON m.trade_id=p.trade_id
        WHERE p.plan_type='SIMULATION'
          AND o.lifecycle_status='ACTIVE'
          AND COALESCE(o.entry_triggered, 0)=1
    """
    params: tuple[Any, ...] = ()
    if trader_id is not None:
        sql += " AND p.trader_id=?"
        params = (str(trader_id),)
    sql += " ORDER BY o.entry_time_utc DESC, p.created_at_utc DESC"
    with journal_connection(path) as con:
        return pd.read_sql_query(sql, con, params=params)


def list_paper_management_events(
    *,
    trader_id: str | None = None,
    limit: int = 100,
    db_path: str | Path | None = None,
) -> pd.DataFrame:
    path = _schema(db_path)
    sql = """
        SELECT e.*
        FROM paper_position_management_events e
        JOIN trade_plans p ON p.trade_id=e.trade_id
    """
    params: list[Any] = []
    if trader_id is not None:
        sql += " WHERE p.trader_id=?"
        params.append(str(trader_id))
    sql += " ORDER BY e.occurred_at_utc DESC LIMIT ?"
    params.append(max(1, int(limit)))
    with journal_connection(path) as con:
        return pd.read_sql_query(sql, con, params=tuple(params))


def set_break_even(
    trade_id: str,
    *,
    actor_trader_id: str,
    db_path: str | Path | None = None,
    effective_at_utc: Any | None = None,
) -> dict[str, Any]:
    path = _schema(db_path)
    effective = _utc(effective_at_utc).isoformat()
    with journal_connection(path) as con:
        con.execute("BEGIN IMMEDIATE")
        trade = _trade_row(
            con,
            trade_id,
            actor_trader_id=actor_trader_id,
            authorize=True,
        )
        execution = _finite(trade.get("execution_price"))
        if execution is None or execution <= 0:
            raise PaperPositionManagementError("Execution-Fill fehlt.")
        current = _management_row(con, trade_id)
        if current and int(current.get("break_even_active") or 0) == 1:
            old = _finite(current.get("current_stop_mt5"))
            if old is not None and math.isclose(old, execution, rel_tol=0.0, abs_tol=1e-12):
                return {
                    "trade_id": str(trade_id),
                    "action": "BREAK_EVEN",
                    "already_active": True,
                    "new_stop_mt5": execution,
                    "effective_at_utc": current.get("stop_effective_at_utc"),
                }
        original_stop = _finite(_plan_mt5(trade).get("stop"))
        old_stop = _finite(current.get("current_stop_mt5")) if current else original_stop
        con.execute(
            """
            INSERT INTO paper_position_management(
                trade_id, break_even_active, current_stop_mt5,
                stop_effective_at_utc, exit_price_mt5, exit_time_utc,
                exit_reason, updated_at_utc, updated_by_trader_id
            ) VALUES(?,?,?,?,NULL,NULL,NULL,?,?)
            ON CONFLICT(trade_id) DO UPDATE SET
                break_even_active=1,
                current_stop_mt5=excluded.current_stop_mt5,
                stop_effective_at_utc=excluded.stop_effective_at_utc,
                updated_at_utc=excluded.updated_at_utc,
                updated_by_trader_id=excluded.updated_by_trader_id
            """,
            (str(trade_id), 1, execution, effective, effective, str(actor_trader_id)),
        )
        event_id = _append_event(
            con,
            trade=trade,
            actor_trader_id=str(actor_trader_id),
            action="BREAK_EVEN",
            occurred_at_utc=effective,
            old_stop_mt5=old_stop,
            new_stop_mt5=execution,
            extra={
                "rule": "stop_to_execution_fill",
                "original_stop_mt5": original_stop,
            },
        )
    return {
        "trade_id": str(trade_id),
        "event_id": event_id,
        "action": "BREAK_EVEN",
        "already_active": False,
        "old_stop_mt5": old_stop,
        "new_stop_mt5": execution,
        "effective_at_utc": effective,
    }


def quote_for_symbol(quotes: pd.DataFrame, symbol: str) -> dict[str, Any] | None:
    if quotes is None or quotes.empty or "symbol" not in quotes.columns:
        return None
    wanted = str(symbol).strip().upper()
    rows = quotes.loc[quotes["symbol"].astype(str).str.strip().str.upper().eq(wanted)]
    return None if rows.empty else dict(rows.iloc[-1])


def is_fresh_quote(
    quote: Mapping[str, Any] | None,
    *,
    now: Any | None = None,
    max_tick_age_seconds: float = DEFAULT_MAX_TICK_AGE_SECONDS,
) -> bool:
    if not quote:
        return False
    max_age = max(0.5, float(max_tick_age_seconds))
    tick_age = _finite(quote.get("tick_age_seconds"))
    exported = quote.get("exported_at_utc")
    if tick_age is None or tick_age < 0 or tick_age > max_age or exported in (None, ""):
        return False
    export_age = float((_utc(now) - _utc(exported)).total_seconds())
    return -2.0 <= export_age <= max_age


def close_price_for_side(side: str, quote: Mapping[str, Any]) -> float:
    direction = str(side or "").upper()
    price = _finite(quote.get("bid" if direction == "LONG" else "ask" if direction == "SHORT" else ""))
    if direction not in {"LONG", "SHORT"}:
        raise PaperPositionManagementError(f"Ungültige Richtung: {side}")
    if price is None or price <= 0:
        raise PaperPositionManagementError("Ausführbarer Bid/Ask fehlt.")
    return price


def result_r_from_prices(
    *,
    side: str,
    execution_price: float,
    original_stop: float,
    exit_price: float,
) -> float:
    risk = abs(float(execution_price) - float(original_stop))
    if not math.isfinite(risk) or risk <= 0:
        raise PaperPositionManagementError("Initiales Risiko ist ungültig.")
    if str(side).upper() == "LONG":
        return (float(exit_price) - float(execution_price)) / risk
    if str(side).upper() == "SHORT":
        return (float(execution_price) - float(exit_price)) / risk
    raise PaperPositionManagementError(f"Ungültige Richtung: {side}")


def _close_from_quote(
    trade_id: str,
    *,
    actor_trader_id: str,
    quote: Mapping[str, Any],
    db_path: str | Path | None,
    max_tick_age_seconds: float,
    reason: str,
    authorize: bool,
    occurred_at_utc: Any | None = None,
) -> dict[str, Any]:
    now_ts = _utc(occurred_at_utc)
    if not is_fresh_quote(quote, now=now_ts, max_tick_age_seconds=max_tick_age_seconds):
        raise PaperPositionManagementError(
            f"Quote ist nicht frisch genug (max. {float(max_tick_age_seconds):g}s)."
        )
    path = _schema(db_path)
    closed_at = now_ts.isoformat()
    with journal_connection(path) as con:
        con.execute("BEGIN IMMEDIATE")
        trade = _trade_row(
            con,
            trade_id,
            actor_trader_id=actor_trader_id,
            authorize=authorize,
        )
        side = str(trade["side"]).upper()
        exit_price = close_price_for_side(side, quote)
        execution = _finite(trade.get("execution_price"))
        original_stop = _finite(_plan_mt5(trade).get("stop"))
        if execution is None or original_stop is None:
            raise PaperPositionManagementError("Execution oder ursprünglicher Stop fehlt.")
        result_r = result_r_from_prices(
            side=side,
            execution_price=execution,
            original_stop=original_stop,
            exit_price=exit_price,
        )
        management = _management_row(con, trade_id)
        current_stop = _finite(management.get("current_stop_mt5")) if management else original_stop
        entry_time = _utc(trade.get("entry_time_utc"))
        holding_minutes = max(0.0, float((now_ts - entry_time).total_seconds() / 60.0))

        try:
            payload = json.loads(trade.get("payload_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload["paper_position_management"] = {
            "version": MANAGEMENT_VERSION,
            "exit_reason": str(reason).upper(),
            "exit_price_mt5": exit_price,
            "exit_time_utc": closed_at,
            "original_stop_mt5": original_stop,
            "managed_stop_mt5": current_stop,
            "result_r": result_r,
            "actor_trader_id": str(actor_trader_id),
            "bid_mt5": _finite(quote.get("bid")),
            "ask_mt5": _finite(quote.get("ask")),
            "quote_exported_at_utc": str(quote.get("exported_at_utc") or ""),
        }
        first_exit = "MANUAL_CLOSE" if str(reason).upper() == "MANUAL_CLOSE" else "STOP"
        con.execute(
            """
            UPDATE trade_outcomes
            SET last_evaluated_at_utc=?,
                lifecycle_status='CLOSED',
                data_timeframe='LIVE_TICK_MANAGEMENT',
                exit_time_utc=?,
                last_bar_time_utc=?,
                first_exit=?,
                result_r=?,
                holding_minutes=?,
                payload_json=?
            WHERE trade_id=?
            """,
            (
                closed_at, closed_at, closed_at, first_exit,
                result_r, holding_minutes, _json(payload), str(trade_id),
            ),
        )
        con.execute(
            """
            INSERT INTO paper_position_management(
                trade_id, break_even_active, current_stop_mt5,
                stop_effective_at_utc, exit_price_mt5, exit_time_utc,
                exit_reason, updated_at_utc, updated_by_trader_id
            ) VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(trade_id) DO UPDATE SET
                exit_price_mt5=excluded.exit_price_mt5,
                exit_time_utc=excluded.exit_time_utc,
                exit_reason=excluded.exit_reason,
                updated_at_utc=excluded.updated_at_utc,
                updated_by_trader_id=excluded.updated_by_trader_id
            """,
            (
                str(trade_id), int(management.get("break_even_active") or 0) if management else 0,
                current_stop, management.get("stop_effective_at_utc") if management else None,
                exit_price, closed_at, str(reason).upper(), closed_at, str(actor_trader_id),
            ),
        )
        event_id = _append_event(
            con,
            trade=trade,
            actor_trader_id=str(actor_trader_id),
            action=str(reason).upper(),
            occurred_at_utc=closed_at,
            old_stop_mt5=current_stop,
            new_stop_mt5=current_stop,
            exit_price_mt5=exit_price,
            quote=quote,
            result_r=result_r,
            extra={
                "exit_side": "BID" if side == "LONG" else "ASK",
                "original_stop_mt5": original_stop,
                "managed_stop_mt5": current_stop,
            },
        )
    return {
        "trade_id": str(trade_id),
        "event_id": event_id,
        "action": str(reason).upper(),
        "exit_price_mt5": exit_price,
        "exit_time_utc": closed_at,
        "result_r": result_r,
        "lifecycle_status": "CLOSED",
    }


def manual_close_from_quotes(
    trade_id: str,
    *,
    actor_trader_id: str,
    quotes: pd.DataFrame,
    db_path: str | Path | None = None,
    max_tick_age_seconds: float = DEFAULT_MAX_TICK_AGE_SECONDS,
    occurred_at_utc: Any | None = None,
) -> dict[str, Any]:
    path = _schema(db_path)
    with journal_connection(path) as con:
        trade = _trade_row(
            con,
            trade_id,
            actor_trader_id=actor_trader_id,
            authorize=True,
        )
        quote = quote_for_symbol(quotes, str(trade["cfd_symbol"]))
    if quote is None:
        raise PaperPositionManagementError(
            f"Kein aktueller Bridge-Quote für {trade['cfd_symbol']} vorhanden."
        )
    return _close_from_quote(
        trade_id,
        actor_trader_id=actor_trader_id,
        quote=quote,
        db_path=path,
        max_tick_age_seconds=max_tick_age_seconds,
        reason="MANUAL_CLOSE",
        authorize=True,
        occurred_at_utc=occurred_at_utc,
    )


def process_paper_management_quotes(
    quotes: pd.DataFrame,
    *,
    db_path: str | Path | None = None,
    max_tick_age_seconds: float = DEFAULT_MAX_TICK_AGE_SECONDS,
    now: Any | None = None,
) -> dict[str, Any]:
    """Process only user-activated paper BE stops from the current quote onward.

    The management row is created at the button timestamp. Therefore a price move
    that happened before stop_effective_at_utc can never trigger this live BE stop.
    """
    path = _schema(db_path)
    positions = list_active_paper_positions(db_path=path)
    if positions.empty:
        return {"checked": 0, "closed": 0, "errors": []}
    managed = positions.loc[
        pd.to_numeric(positions["break_even_active"], errors="coerce").fillna(0).astype(int).eq(1)
    ]
    closed = 0
    errors: list[str] = []
    for row in managed.to_dict(orient="records"):
        quote = quote_for_symbol(quotes, str(row.get("cfd_symbol")))
        if not is_fresh_quote(quote, now=now, max_tick_age_seconds=max_tick_age_seconds):
            continue
        stop = _finite(row.get("current_stop_mt5"))
        if stop is None:
            continue
        side = str(row.get("side") or "").upper()
        try:
            price = close_price_for_side(side, quote or {})
        except PaperPositionManagementError:
            continue
        hit = (side == "LONG" and price <= stop) or (side == "SHORT" and price >= stop)
        if not hit:
            continue
        try:
            _close_from_quote(
                str(row["trade_id"]),
                actor_trader_id="SYSTEM",
                quote=quote or {},
                db_path=path,
                max_tick_age_seconds=max_tick_age_seconds,
                reason="BREAK_EVEN_STOP",
                authorize=False,
                occurred_at_utc=now,
            )
            closed += 1
        except Exception as exc:
            errors.append(f"{row.get('trade_id')}: {exc}")
    return {"checked": int(len(managed)), "closed": int(closed), "errors": errors}
