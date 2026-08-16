from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping
import uuid

import numpy as np
import pandas as pd


JOURNAL_SCHEMA_VERSION = 6
SNAPSHOT_SCHEMA_VERSION = "1.0"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime | None = None) -> str:
    dt = value or _utc_now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _iso_local(value: datetime | None = None) -> str:
    dt = value or datetime.now().astimezone()
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.isoformat(timespec="microseconds")


def default_db_path() -> Path:
    """Stable user-level path so journal data survives downloaded app versions."""
    home = Path.home()
    if os.name == "nt":
        root = Path(os.getenv("APPDATA", home / "AppData/Roaming")) / "COT Research"
    elif sys_platform() == "darwin":
        root = home / "Library/Application Support/COT Research"
    else:
        root = home / ".local/share/cot-research"
    return root / "trading_journal.sqlite3"


def sys_platform() -> str:
    import sys
    return sys.platform


def resolve_db_path(mapping: Mapping[str, Any] | None = None) -> Path:
    raw = dict(mapping or {})
    configured = str(raw.get("db_path", "") or "").strip()
    return Path(configured).expanduser() if configured else default_db_path()


def _json_clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        ts = pd.Timestamp(value)
        return ts.isoformat()
    if isinstance(value, pd.Timedelta):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Series):
        return {str(k): _json_clean(v) for k, v in value.to_dict().items()}
    if isinstance(value, pd.DataFrame):
        return [_json_clean(row) for row in value.to_dict(orient="records")]
    if isinstance(value, Mapping):
        return {str(k): _json_clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_clean(v) for v in value]
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def canonical_json(payload: Mapping[str, Any]) -> str:
    cleaned = _json_clean(payload)
    return json.dumps(cleaned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def payload_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def flatten_snapshot(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Create a future-proof long feature table while retaining the full JSON snapshot.

    Nested mappings become dotted feature names. Lists are preserved as JSON text to
    avoid inventing positional semantics. Scalar missing values stay explicit NULLs.
    """
    rows: list[dict[str, Any]] = []

    def visit(path: list[str], value: Any) -> None:
        if isinstance(value, Mapping):
            if not value:
                add(path, None)
                return
            for key, child in value.items():
                visit(path + [str(key)], child)
            return
        if isinstance(value, (list, tuple, set, pd.DataFrame, pd.Series)):
            add(path, json.dumps(_json_clean(value), ensure_ascii=False, sort_keys=True))
            return
        add(path, value)

    def add(path: list[str], value: Any) -> None:
        if not path:
            return
        cleaned = _json_clean(value)
        group = path[0]
        feature_name = ".".join(path[1:]) if len(path) > 1 else path[0]
        numeric_value = None
        text_value = None
        bool_value = None
        value_type = "null"

        if isinstance(cleaned, bool):
            bool_value = int(cleaned)
            value_type = "bool"
        elif isinstance(cleaned, (int, float)) and not isinstance(cleaned, bool):
            numeric_value = float(cleaned)
            value_type = "numeric"
        elif cleaned is not None:
            text_value = str(cleaned)
            value_type = "text"

        rows.append({
            "feature_group": group,
            "feature_name": feature_name,
            "value_type": value_type,
            "numeric_value": numeric_value,
            "text_value": text_value,
            "bool_value": bool_value,
        })

    for key, value in payload.items():
        visit([str(key)], value)
    return rows


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traders (
    trader_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    password_iterations INTEGER NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('ADMIN','TRADER')),
    active INTEGER NOT NULL DEFAULT 1,
    created_at_utc TEXT NOT NULL,
    created_at_local TEXT NOT NULL,
    last_login_utc TEXT
);

CREATE TABLE IF NOT EXISTS trade_plans (
    trade_id TEXT PRIMARY KEY,
    trader_id TEXT,
    created_at_utc TEXT NOT NULL,
    created_at_local TEXT NOT NULL,
    timezone TEXT NOT NULL,
    plan_type TEXT NOT NULL CHECK(plan_type IN ('REAL','SIMULATION','SKIPPED')),
    order_type TEXT NOT NULL DEFAULT 'LIMIT' CHECK(order_type IN ('LIMIT','MARKET')),
    expiry_at_utc TEXT,
    skip_reason TEXT,
    asset_class TEXT,
    market_name TEXT,
    cot_symbol TEXT,
    cftc_code TEXT,
    cfd_symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('LONG','SHORT')),
    zone_type TEXT NOT NULL CHECK(zone_type IN ('DEMAND','SUPPLY','OTHER')),
    timeframe TEXT NOT NULL,
    zone_low REAL,
    zone_high REAL,
    entry REAL NOT NULL,
    stop REAL NOT NULL,
    target REAL,
    planned_rr REAL,
    requested_risk_pct REAL,
    zone_freshness TEXT,
    retest_count INTEGER,
    quality_grade TEXT,
    notes TEXT,
    snapshot_id TEXT NOT NULL UNIQUE,
    schema_version INTEGER NOT NULL,
    FOREIGN KEY(trader_id) REFERENCES traders(trader_id),
    FOREIGN KEY(snapshot_id) REFERENCES trade_snapshots(snapshot_id) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS trade_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    trade_id TEXT NOT NULL UNIQUE,
    captured_at_utc TEXT NOT NULL,
    captured_at_local TEXT NOT NULL,
    snapshot_schema_version TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    feature_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(trade_id) REFERENCES trade_plans(trade_id) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS snapshot_features (
    snapshot_id TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    feature_group TEXT NOT NULL,
    feature_name TEXT NOT NULL,
    value_type TEXT NOT NULL,
    numeric_value REAL,
    text_value TEXT,
    bool_value INTEGER,
    PRIMARY KEY(snapshot_id, feature_group, feature_name),
    FOREIGN KEY(snapshot_id) REFERENCES trade_snapshots(snapshot_id),
    FOREIGN KEY(trade_id) REFERENCES trade_plans(trade_id)
);

CREATE TABLE IF NOT EXISTS trade_events (
    event_id TEXT PRIMARY KEY,
    trade_id TEXT NOT NULL,
    occurred_at_utc TEXT NOT NULL,
    occurred_at_local TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'USER',
    payload_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(trade_id) REFERENCES trade_plans(trade_id)
);

CREATE TABLE IF NOT EXISTS trade_outcomes (
    trade_id TEXT PRIMARY KEY,
    last_evaluated_at_utc TEXT,
    lifecycle_status TEXT,
    exit_time_utc TEXT,
    last_bar_time_utc TEXT,
    ambiguity_reason TEXT,
    data_timeframe TEXT,
    plus_1r_time_utc TEXT,
    plus_2r_time_utc TEXT,
    plus_3r_time_utc TEXT,
    entry_triggered INTEGER,
    entry_time_utc TEXT,
    execution_price REAL,
    fill_timeframe TEXT,
    stop_time_utc TEXT,
    target_time_utc TEXT,
    first_exit TEXT,
    result_r REAL,
    mae_r REAL,
    mfe_r REAL,
    holding_minutes REAL,
    forward_1d REAL,
    forward_3d REAL,
    forward_5d REAL,
    forward_10d REAL,
    forward_20d REAL,
    forward_40d REAL,
    forward_60d REAL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(trade_id) REFERENCES trade_plans(trade_id)
);

CREATE TABLE IF NOT EXISTS mt5_history_bars (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    time_utc TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    tick_volume REAL,
    spread REAL,
    real_volume REAL,
    cached_at_utc TEXT NOT NULL,
    PRIMARY KEY(symbol, timeframe, time_utc)
);

CREATE TABLE IF NOT EXISTS mt5_history_coverage (
    coverage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    synced_at_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mt5_history_bars_lookup
ON mt5_history_bars(symbol, timeframe, time_utc);
CREATE INDEX IF NOT EXISTS idx_mt5_history_coverage_lookup
ON mt5_history_coverage(symbol, timeframe, start_utc, end_utc);

CREATE INDEX IF NOT EXISTS idx_trade_plans_created ON trade_plans(created_at_utc DESC);
CREATE INDEX IF NOT EXISTS idx_trade_plans_symbol ON trade_plans(cfd_symbol, created_at_utc DESC);
CREATE INDEX IF NOT EXISTS idx_trade_plans_type ON trade_plans(plan_type, created_at_utc DESC);
CREATE INDEX IF NOT EXISTS idx_features_name_numeric ON snapshot_features(feature_group, feature_name, numeric_value);
CREATE INDEX IF NOT EXISTS idx_events_trade_time ON trade_events(trade_id, occurred_at_utc);

CREATE TRIGGER IF NOT EXISTS no_update_trade_plans
BEFORE UPDATE ON trade_plans BEGIN SELECT RAISE(ABORT, 'trade_plans are immutable; append a trade_event instead'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_trade_plans
BEFORE DELETE ON trade_plans BEGIN SELECT RAISE(ABORT, 'trade_plans are immutable'); END;
CREATE TRIGGER IF NOT EXISTS no_update_trade_snapshots
BEFORE UPDATE ON trade_snapshots BEGIN SELECT RAISE(ABORT, 'trade_snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_trade_snapshots
BEFORE DELETE ON trade_snapshots BEGIN SELECT RAISE(ABORT, 'trade_snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS no_update_snapshot_features
BEFORE UPDATE ON snapshot_features BEGIN SELECT RAISE(ABORT, 'snapshot_features are immutable'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_snapshot_features
BEFORE DELETE ON snapshot_features BEGIN SELECT RAISE(ABORT, 'snapshot_features are immutable'); END;
CREATE TRIGGER IF NOT EXISTS no_update_trade_events
BEFORE UPDATE ON trade_events BEGIN SELECT RAISE(ABORT, 'trade_events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_trade_events
BEFORE DELETE ON trade_events BEGIN SELECT RAISE(ABORT, 'trade_events are append-only'); END;
"""


@contextmanager
def journal_connection(db_path: str | Path | None = None):
    path = Path(db_path) if db_path else default_db_path()
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = NORMAL")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _ensure_column(con: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def initialize_journal(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path else default_db_path()
    with journal_connection(path) as con:
        con.executescript(SCHEMA_SQL)
        # Forward-only additive migrations keep the user's persistent journal intact.
        _ensure_column(con, "trade_plans", "order_type", "TEXT NOT NULL DEFAULT 'LIMIT'")
        _ensure_column(con, "trade_plans", "expiry_at_utc", "TEXT")
        _ensure_column(con, "trade_plans", "trader_id", "TEXT")
        con.execute("CREATE INDEX IF NOT EXISTS idx_trade_plans_trader ON trade_plans(trader_id, created_at_utc DESC)")
        for name, ddl in [
            ("lifecycle_status", "TEXT"),
            ("exit_time_utc", "TEXT"),
            ("last_bar_time_utc", "TEXT"),
            ("ambiguity_reason", "TEXT"),
            ("data_timeframe", "TEXT"),
            ("plus_1r_time_utc", "TEXT"),
            ("plus_2r_time_utc", "TEXT"),
            ("plus_3r_time_utc", "TEXT"),
            ("execution_price", "REAL"),
            ("fill_timeframe", "TEXT"),
        ]:
            _ensure_column(con, "trade_outcomes", name, ddl)
        con.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
            (str(JOURNAL_SCHEMA_VERSION),),
        )
        con.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('snapshot_schema_version', ?)",
            (SNAPSHOT_SCHEMA_VERSION,),
        )
    return path


def _planned_rr(side: str, entry: float, stop: float, target: float | None) -> float | None:
    if target is None or not np.isfinite(target):
        return None
    risk = abs(float(entry) - float(stop))
    if risk <= 0:
        return None
    reward = (float(target) - float(entry)) if side == "LONG" else (float(entry) - float(target))
    return float(reward / risk)


def validate_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    p = dict(plan)
    plan_type = str(p.get("plan_type", "SIMULATION") or "SIMULATION").upper()
    order_type = str(p.get("order_type", "LIMIT") or "LIMIT").upper()
    side = str(p.get("side", "") or "").upper()
    zone_type = str(p.get("zone_type", "OTHER") or "OTHER").upper()
    if plan_type not in {"REAL", "SIMULATION", "SKIPPED"}:
        raise ValueError("plan_type muss REAL, SIMULATION oder SKIPPED sein.")
    if order_type not in {"LIMIT", "MARKET"}:
        raise ValueError("order_type muss LIMIT oder MARKET sein.")
    if side not in {"LONG", "SHORT"}:
        raise ValueError("side muss LONG oder SHORT sein.")
    if zone_type not in {"DEMAND", "SUPPLY", "OTHER"}:
        raise ValueError("zone_type muss DEMAND, SUPPLY oder OTHER sein.")
    cfd_symbol = str(p.get("cfd_symbol", "") or "").strip()
    if not cfd_symbol:
        raise ValueError("CFD-Symbol fehlt.")
    entry = float(p.get("entry"))
    stop = float(p.get("stop"))
    if not np.isfinite(entry) or not np.isfinite(stop) or entry == stop:
        raise ValueError("Entry und Stop müssen gültig und verschieden sein.")
    if side == "LONG" and stop >= entry:
        raise ValueError("Bei LONG muss der Stop unter dem Entry liegen.")
    if side == "SHORT" and stop <= entry:
        raise ValueError("Bei SHORT muss der Stop über dem Entry liegen.")
    target_raw = p.get("target")
    target = None if target_raw in (None, "") else float(target_raw)
    if target is not None and not np.isfinite(target):
        target = None
    if target is not None and side == "LONG" and target <= entry:
        raise ValueError("Bei LONG muss ein verwendetes Target über dem Entry liegen.")
    if target is not None and side == "SHORT" and target >= entry:
        raise ValueError("Bei SHORT muss ein verwendetes Target unter dem Entry liegen.")
    zone_low_raw = p.get("zone_low")
    zone_high_raw = p.get("zone_high")
    zone_low = None if zone_low_raw in (None, "") else float(zone_low_raw)
    zone_high = None if zone_high_raw in (None, "") else float(zone_high_raw)
    if zone_low is not None and zone_high is not None and zone_low > zone_high:
        zone_low, zone_high = zone_high, zone_low
    requested_risk_pct = float(p.get("requested_risk_pct", 0.0) or 0.0)
    if requested_risk_pct < 0:
        raise ValueError("requested_risk_pct darf nicht negativ sein.")

    p.update({
        "plan_type": plan_type,
        "order_type": order_type,
        "expiry_at_utc": str(p.get("expiry_at_utc", "") or "") or None,
        "side": side,
        "zone_type": zone_type,
        "cfd_symbol": cfd_symbol,
        "entry": entry,
        "stop": stop,
        "target": target,
        "zone_low": zone_low,
        "zone_high": zone_high,
        "requested_risk_pct": requested_risk_pct,
        "planned_rr": _planned_rr(side, entry, stop, target),
    })
    if plan_type == "SKIPPED" and not str(p.get("skip_reason", "") or "").strip():
        p["skip_reason"] = "NICHT ANGEGEBEN"
    return p


def create_trade_plan(
    *,
    plan: Mapping[str, Any],
    snapshot_payload: Mapping[str, Any],
    trader_id: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    path = initialize_journal(db_path)
    p = validate_plan(plan)
    if trader_id:
        with journal_connection(path) as con:
            if not con.execute("SELECT 1 FROM traders WHERE trader_id=? AND active=1", (str(trader_id),)).fetchone():
                raise ValueError("Trader-ID ist unbekannt oder deaktiviert.")
    now_utc = _utc_now()
    local_now = datetime.now().astimezone()
    trade_id = str(uuid.uuid4())
    snapshot_id = str(uuid.uuid4())

    payload = dict(snapshot_payload)
    payload.setdefault("meta", {})
    payload["meta"] = dict(payload["meta"] or {})
    payload["meta"].update({
        "trade_id": trade_id,
        "trader_id": str(trader_id or "") or None,
        "snapshot_id": snapshot_id,
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "captured_at_utc": _iso_utc(now_utc),
        "captured_at_local": _iso_local(local_now),
        "trader_id": str(trader_id or "") or None,
    })
    payload["plan"] = _json_clean(p)
    payload_text = canonical_json(payload)
    digest = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    features = flatten_snapshot(payload)

    timezone_name = str(local_now.tzinfo or "local")
    with journal_connection(path) as con:
        # Deferred circular FKs allow the immutable plan and snapshot to be inserted atomically.
        con.execute(
            """
            INSERT INTO trade_plans(
                trade_id, trader_id, created_at_utc, created_at_local, timezone, plan_type, order_type, expiry_at_utc,
                skip_reason, asset_class, market_name, cot_symbol, cftc_code,
                cfd_symbol, side, zone_type, timeframe, zone_low, zone_high,
                entry, stop, target, planned_rr, requested_risk_pct, zone_freshness,
                retest_count, quality_grade, notes, snapshot_id, schema_version
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                trade_id, str(trader_id or "") or None, _iso_utc(now_utc), _iso_local(local_now), timezone_name,
                p["plan_type"], p["order_type"], p.get("expiry_at_utc"), str(p.get("skip_reason", "") or ""),
                str(p.get("asset_class", "") or ""), str(p.get("market_name", "") or ""),
                str(p.get("cot_symbol", "") or ""), str(p.get("cftc_code", "") or ""),
                p["cfd_symbol"], p["side"], p["zone_type"], str(p.get("timeframe", "") or ""),
                p.get("zone_low"), p.get("zone_high"), p["entry"], p["stop"], p.get("target"),
                p.get("planned_rr"), p.get("requested_risk_pct", 0.0),
                str(p.get("zone_freshness", "") or ""),
                int(p.get("retest_count", 0) or 0), str(p.get("quality_grade", "") or ""),
                str(p.get("notes", "") or ""), snapshot_id, JOURNAL_SCHEMA_VERSION,
            ),
        )
        con.execute(
            """
            INSERT INTO trade_snapshots(
                snapshot_id, trade_id, captured_at_utc, captured_at_local,
                snapshot_schema_version, payload_json, payload_sha256, feature_count
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                snapshot_id, trade_id, _iso_utc(now_utc), _iso_local(local_now),
                SNAPSHOT_SCHEMA_VERSION, payload_text, digest, len(features),
            ),
        )
        con.executemany(
            """
            INSERT INTO snapshot_features(
                snapshot_id, trade_id, feature_group, feature_name, value_type,
                numeric_value, text_value, bool_value
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            [
                (
                    snapshot_id, trade_id, row["feature_group"], row["feature_name"],
                    row["value_type"], row["numeric_value"], row["text_value"], row["bool_value"],
                )
                for row in features
            ],
        )
        con.execute(
            """
            INSERT INTO trade_events(event_id, trade_id, occurred_at_utc, occurred_at_local, event_type, source, payload_json)
            VALUES(?,?,?,?,?,?,?)
            """,
            (str(uuid.uuid4()), trade_id, _iso_utc(now_utc), _iso_local(local_now), "PLAN_CREATED", "SYSTEM", "{}"),
        )

    prop_allocation = None
    prop_allocation_error = None
    if p.get("plan_type") == "SIMULATION" and trader_id:
        try:
            from .prop_desk import create_prop_allocation
            prop_allocation = create_prop_allocation(
                trade_id=trade_id, trader_id=str(trader_id), plan=p, snapshot_payload=payload, db_path=path
            )
        except Exception as exc:
            # The immutable research plan must remain saved even when virtual sizing
            # is temporarily unavailable. The dashboard surfaces this explicitly.
            prop_allocation_error = str(exc)
            append_trade_event(
                trade_id, "PROP_ALLOCATION_ERROR", {"error": prop_allocation_error}, source="SYSTEM", db_path=path
            )

    return {
        "trade_id": trade_id,
        "snapshot_id": snapshot_id,
        "payload_sha256": digest,
        "feature_count": len(features),
        "db_path": str(path),
        "plan": p,
        "prop_allocation": prop_allocation,
        "prop_allocation_error": prop_allocation_error,
    }


def append_trade_event(
    trade_id: str,
    event_type: str,
    payload: Mapping[str, Any] | None = None,
    *,
    source: str = "USER",
    db_path: str | Path | None = None,
) -> str:
    path = initialize_journal(db_path)
    event_id = str(uuid.uuid4())
    now_utc = _utc_now()
    local_now = datetime.now().astimezone()
    with journal_connection(path) as con:
        exists = con.execute("SELECT 1 FROM trade_plans WHERE trade_id=?", (trade_id,)).fetchone()
        if not exists:
            raise KeyError(f"Unbekannte trade_id: {trade_id}")
        con.execute(
            """
            INSERT INTO trade_events(event_id, trade_id, occurred_at_utc, occurred_at_local, event_type, source, payload_json)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                event_id, trade_id, _iso_utc(now_utc), _iso_local(local_now),
                str(event_type).strip().upper(), str(source).strip().upper(),
                canonical_json(dict(payload or {})),
            ),
        )
    return event_id


def void_trade_plan(
    trade_id: str,
    *,
    reason: str,
    actor_trader_id: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Safely void an erroneous plan without deleting immutable research data.

    Only a PLANNED, never-triggered trade may be voided. The owner may void their
    own plan; ADMINs may void any plan. The plan/snapshot remain immutable, while
    the derived lifecycle becomes VOID and an append-only PLAN_VOIDED event records
    who did it and why.
    """
    path = initialize_journal(db_path)
    clean_reason = str(reason or "").strip()
    if len(clean_reason) < 3:
        raise ValueError("Bitte einen kurzen Grund für den Fehleintrag angeben.")
    actor_id = str(actor_trader_id or "").strip()
    if not actor_id:
        raise PermissionError("Trader-Sitzung fehlt.")

    now_utc = _utc_now()
    now_local = datetime.now().astimezone()
    event_id = str(uuid.uuid4())
    with journal_connection(path) as con:
        row = con.execute(
            """
            SELECT p.trade_id, p.trader_id, p.cfd_symbol, p.side, p.plan_type,
                   COALESCE(o.lifecycle_status, 'PLANNED') AS lifecycle_status,
                   COALESCE(o.entry_triggered, 0) AS entry_triggered,
                   t.role AS actor_role
            FROM trade_plans p
            LEFT JOIN trade_outcomes o ON o.trade_id=p.trade_id
            LEFT JOIN traders t ON t.trader_id=?
            WHERE p.trade_id=?
            """,
            (actor_id, str(trade_id)),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unbekannte trade_id: {trade_id}")
        is_admin = str(row["actor_role"] or "").upper() == "ADMIN"
        is_owner = str(row["trader_id"] or "") == actor_id
        if not (is_owner or is_admin):
            raise PermissionError("Du darfst nur eigene PLANNED-Trades verwerfen.")
        status = str(row["lifecycle_status"] or "PLANNED").upper()
        triggered = bool(row["entry_triggered"] or 0)
        if status == "VOID":
            raise ValueError("Dieser Trade wurde bereits als Fehleintrag verworfen.")
        if status != "PLANNED" or triggered:
            raise ValueError("Nur PLANNED-Trades ohne ausgelösten Entry dürfen verworfen werden.")

        payload = {
            "reason": clean_reason,
            "actor_trader_id": actor_id,
            "previous_status": status,
            "symbol": row["cfd_symbol"],
            "side": row["side"],
            "plan_type": row["plan_type"],
            "excluded_from_outcome_sync": True,
            "excluded_from_prop_desk": True,
            "excluded_from_ml": True,
        }
        con.execute(
            """
            INSERT INTO trade_outcomes(trade_id, last_evaluated_at_utc, lifecycle_status, entry_triggered, payload_json)
            VALUES(?,?,?,?,?)
            ON CONFLICT(trade_id) DO UPDATE SET
                last_evaluated_at_utc=excluded.last_evaluated_at_utc,
                lifecycle_status='VOID',
                entry_triggered=0,
                ambiguity_reason=NULL,
                payload_json=excluded.payload_json
            """,
            (str(trade_id), _iso_utc(now_utc), "VOID", 0, canonical_json(payload)),
        )
        con.execute(
            """
            INSERT INTO trade_events(event_id, trade_id, occurred_at_utc, occurred_at_local, event_type, source, payload_json)
            VALUES(?,?,?,?,?,?,?)
            """,
            (event_id, str(trade_id), _iso_utc(now_utc), _iso_local(now_local), "PLAN_VOIDED", "USER", canonical_json(payload)),
        )
    return {"trade_id": str(trade_id), "lifecycle_status": "VOID", "event_id": event_id, "reason": clean_reason}


def upsert_trade_outcome(
    trade_id: str,
    outcome: Mapping[str, Any],
    *,
    db_path: str | Path | None = None,
) -> None:
    """Derived market outcomes are intentionally mutable as new bars arrive."""
    path = initialize_journal(db_path)
    o = dict(outcome or {})
    fields = [
        "lifecycle_status", "exit_time_utc", "last_bar_time_utc", "ambiguity_reason", "data_timeframe",
        "plus_1r_time_utc", "plus_2r_time_utc", "plus_3r_time_utc",
        "entry_triggered", "entry_time_utc", "execution_price", "fill_timeframe", "stop_time_utc", "target_time_utc", "first_exit",
        "result_r", "mae_r", "mfe_r", "holding_minutes", "forward_1d", "forward_3d",
        "forward_5d", "forward_10d", "forward_20d", "forward_40d", "forward_60d",
    ]
    values = [o.get(k) for k in fields]
    with journal_connection(path) as con:
        exists = con.execute("SELECT 1 FROM trade_plans WHERE trade_id=?", (trade_id,)).fetchone()
        if not exists:
            raise KeyError(f"Unbekannte trade_id: {trade_id}")
        con.execute(
            f"""
            INSERT INTO trade_outcomes(trade_id, last_evaluated_at_utc, {','.join(fields)}, payload_json)
            VALUES(?, ?, {','.join(['?'] * len(fields))}, ?)
            ON CONFLICT(trade_id) DO UPDATE SET
                last_evaluated_at_utc=excluded.last_evaluated_at_utc,
                {', '.join([f'{f}=excluded.{f}' for f in fields])},
                payload_json=excluded.payload_json
            """,
            [trade_id, _iso_utc(), *values, canonical_json(o)],
        )


def list_trade_plans(
    *,
    db_path: str | Path | None = None,
    limit: int = 500,
    plan_type: str | None = None,
    trader_id: str | None = None,
    lifecycle_statuses: Iterable[str] | None = None,
) -> pd.DataFrame:
    path = initialize_journal(db_path)
    clauses: list[str] = []
    params: list[Any] = []
    if plan_type:
        clauses.append("p.plan_type=?")
        params.append(str(plan_type).upper())
    if trader_id:
        clauses.append("p.trader_id=?")
        params.append(str(trader_id))
    if lifecycle_statuses:
        statuses = [str(value).upper() for value in lifecycle_statuses]
        if statuses:
            clauses.append(f"COALESCE(o.lifecycle_status, 'PLANNED') IN ({','.join(['?'] * len(statuses))})")
            params.extend(statuses)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(int(limit))
    query = f"""
        SELECT p.*, t.username AS trader_username, t.display_name AS trader_display_name, t.role AS trader_role,
               o.lifecycle_status, o.entry_triggered, o.entry_time_utc, o.execution_price, o.fill_timeframe, o.exit_time_utc,
               o.first_exit, o.result_r, o.mae_r, o.mfe_r, o.last_evaluated_at_utc
        FROM trade_plans p
        LEFT JOIN traders t ON t.trader_id=p.trader_id
        LEFT JOIN trade_outcomes o ON o.trade_id=p.trade_id
        {where}
        ORDER BY p.created_at_utc DESC
        LIMIT ?
    """
    with journal_connection(path) as con:
        return pd.read_sql_query(query, con, params=params)


def get_trade_snapshot(trade_id: str, *, db_path: str | Path | None = None) -> dict[str, Any]:
    path = initialize_journal(db_path)
    with journal_connection(path) as con:
        row = con.execute(
            "SELECT payload_json, payload_sha256 FROM trade_snapshots WHERE trade_id=?",
            (trade_id,),
        ).fetchone()
    if row is None:
        raise KeyError(f"Kein Snapshot für trade_id {trade_id}")
    payload = json.loads(row["payload_json"])
    if hashlib.sha256(row["payload_json"].encode("utf-8")).hexdigest() != row["payload_sha256"]:
        raise RuntimeError("Snapshot-Hash stimmt nicht; Datenintegrität verletzt.")
    return payload


def get_trade_outcome(trade_id: str, *, db_path: str | Path | None = None) -> dict[str, Any]:
    path = initialize_journal(db_path)
    with journal_connection(path) as con:
        row = con.execute("SELECT * FROM trade_outcomes WHERE trade_id=?", (trade_id,)).fetchone()
    if row is None:
        return {}
    out = dict(row)
    try:
        payload = json.loads(out.get("payload_json") or "{}")
    except Exception:
        payload = {}
    out["payload"] = payload
    return out


def get_trade_events(trade_id: str, *, db_path: str | Path | None = None) -> pd.DataFrame:
    path = initialize_journal(db_path)
    with journal_connection(path) as con:
        return pd.read_sql_query(
            "SELECT * FROM trade_events WHERE trade_id=? ORDER BY occurred_at_utc, event_id",
            con,
            params=[trade_id],
        )


def journal_summary(*, db_path: str | Path | None = None, trader_id: str | None = None) -> dict[str, Any]:
    plans = list_trade_plans(db_path=db_path, limit=100_000, trader_id=trader_id)
    if plans.empty:
        return {
            "plans": 0, "real": 0, "simulation": 0, "skipped": 0, "voided": 0,
            "evaluated": 0, "expectancy_r": np.nan, "planned": 0, "active": 0,
            "closed": 0, "expired": 0, "ambiguous": 0,
        }
    statuses = plans.get("lifecycle_status", pd.Series(index=plans.index, dtype=object)).fillna("PLANNED").astype(str).str.upper()
    valid_mask = ~statuses.eq("VOID")
    valid = plans.loc[valid_mask].copy()
    valid_statuses = statuses.loc[valid_mask]
    evaluated = pd.to_numeric(valid.get("result_r"), errors="coerce")
    return {
        "plans": int(len(valid)),
        "real": int((valid["plan_type"] == "REAL").sum()),
        "simulation": int((valid["plan_type"] == "SIMULATION").sum()),
        "skipped": int((valid["plan_type"] == "SKIPPED").sum()),
        "voided": int(statuses.eq("VOID").sum()),
        "evaluated": int(evaluated.notna().sum()),
        "expectancy_r": float(evaluated.mean()) if evaluated.notna().any() else np.nan,
        "planned": int((valid_statuses == "PLANNED").sum()),
        "active": int((valid_statuses == "ACTIVE").sum()),
        "closed": int((valid_statuses == "CLOSED").sum()),
        "expired": int((valid_statuses == "EXPIRED").sum()),
        "ambiguous": int((valid_statuses == "AMBIGUOUS").sum()),
    }


def build_feature_matrix(
    *,
    db_path: str | Path | None = None,
    include_text: bool = False,
    include_outcomes: bool = True,
    trader_id: str | None = None,
    include_voided: bool = False,
) -> pd.DataFrame:
    """Build one ML/research row per trade without mutating stored snapshots.

    Snapshot features are prefixed with ``feature__``. Future outcomes are kept
    in explicit ``label__`` columns so they cannot be mistaken for plan-time
    predictors.
    """
    path = initialize_journal(db_path)
    with journal_connection(path) as con:
        plan_sql = """
            SELECT p.trade_id, p.trader_id, t.username AS trader_username, t.display_name AS trader_display_name,
                   p.created_at_utc, p.plan_type, p.order_type, p.expiry_at_utc, p.asset_class, p.market_name,
                   p.cot_symbol, p.cfd_symbol, p.side, p.zone_type, p.timeframe, p.zone_low,
                   p.zone_high, p.entry, p.stop, p.target, p.planned_rr, p.requested_risk_pct,
                   p.zone_freshness, p.retest_count, p.quality_grade, p.skip_reason
            FROM trade_plans p
            LEFT JOIN traders t ON t.trader_id=p.trader_id
            LEFT JOIN trade_outcomes vo ON vo.trade_id=p.trade_id
        """
        plan_params: list[Any] = []
        clauses: list[str] = []
        if trader_id:
            clauses.append("p.trader_id=?")
            plan_params.append(str(trader_id))
        if not include_voided:
            clauses.append("COALESCE(vo.lifecycle_status, 'PLANNED') <> 'VOID'")
        if clauses:
            plan_sql += " WHERE " + " AND ".join(clauses)
        plan_sql += " ORDER BY p.created_at_utc"
        plans = pd.read_sql_query(plan_sql, con, params=plan_params)
        features = pd.read_sql_query(
            """
            SELECT trade_id, feature_group, feature_name, value_type,
                   numeric_value, text_value, bool_value
            FROM snapshot_features
            """,
            con,
        )
        outcomes = pd.read_sql_query("SELECT * FROM trade_outcomes", con) if include_outcomes else pd.DataFrame()

    if plans.empty:
        return plans
    if not features.empty:
        features["column"] = "feature__" + features["feature_group"].astype(str) + "__" + features["feature_name"].astype(str).str.replace(".", "__", regex=False)
        features["value"] = features["numeric_value"]
        bool_mask = features["value_type"] == "bool"
        features.loc[bool_mask, "value"] = features.loc[bool_mask, "bool_value"].astype(float)
        if include_text:
            text_mask = features["value_type"] == "text"
            features.loc[text_mask, "value"] = features.loc[text_mask, "text_value"]
        else:
            features = features[features["value_type"].isin(["numeric", "bool"])]
        wide = features.pivot(index="trade_id", columns="column", values="value").reset_index()
        wide.columns.name = None
        plans = plans.merge(wide, on="trade_id", how="left")

    if include_outcomes and not outcomes.empty:
        label_cols = {
            col: f"label__{col}"
            for col in outcomes.columns
            if col not in {"trade_id", "payload_json", "last_evaluated_at_utc"}
        }
        labels = outcomes[["trade_id", *label_cols.keys()]].rename(columns=label_cols)
        plans = plans.merge(labels, on="trade_id", how="left")
    return plans
