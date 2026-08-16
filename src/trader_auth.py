from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import re
import secrets
from pathlib import Path
from typing import Any
import uuid

import pandas as pd

from .trade_journal import canonical_json, initialize_journal, journal_connection

PBKDF2_ITERATIONS = 310_000
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._@+-]{3,64}$")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _local_now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def normalize_username(username: str) -> str:
    value = str(username or "").strip().casefold()
    if not _USERNAME_RE.fullmatch(value):
        raise ValueError("Benutzername: 3–64 Zeichen; erlaubt sind Buchstaben, Zahlen sowie . _ @ + -")
    return value


def validate_password(password: str) -> str:
    value = str(password or "")
    if len(value) < 8:
        raise ValueError("Passwort muss mindestens 8 Zeichen lang sein.")
    return value


def _hash_password(password: str, *, salt_hex: str | None = None, iterations: int = PBKDF2_ITERATIONS) -> tuple[str, str, int]:
    value = validate_password(password)
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(24)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, int(iterations))
    return digest.hex(), salt.hex(), int(iterations)


def _public_trader(row: Any) -> dict[str, Any]:
    data = dict(row)
    for key in ("password_hash", "password_salt", "password_iterations"):
        data.pop(key, None)
    data["active"] = bool(data.get("active", 0))
    return data


def trader_count(*, db_path: str | Path | None = None, active_only: bool = False) -> int:
    path = initialize_journal(db_path)
    sql = "SELECT COUNT(*) FROM traders"
    if active_only:
        sql += " WHERE active=1"
    with journal_connection(path) as con:
        return int(con.execute(sql).fetchone()[0])


def create_trader(
    *,
    username: str,
    display_name: str,
    password: str,
    role: str = "TRADER",
    active: bool = True,
    claim_legacy_trades: bool = False,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    path = initialize_journal(db_path)
    user = normalize_username(username)
    name = str(display_name or "").strip()
    if not name:
        raise ValueError("Anzeigename darf nicht leer sein.")
    role_value = str(role or "TRADER").upper()
    if role_value not in {"ADMIN", "TRADER"}:
        raise ValueError("Rolle muss ADMIN oder TRADER sein.")
    pw_hash, salt, iterations = _hash_password(password)
    trader_id = str(uuid.uuid4())
    now_utc = _utc_now_iso()
    now_local = _local_now_iso()
    with journal_connection(path) as con:
        if con.execute("SELECT 1 FROM traders WHERE username=? COLLATE NOCASE", (user,)).fetchone():
            raise ValueError("Dieser Benutzername existiert bereits.")
        con.execute(
            """
            INSERT INTO traders(
                trader_id, username, display_name, password_hash, password_salt,
                password_iterations, role, active, created_at_utc, created_at_local
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (trader_id, user, name, pw_hash, salt, iterations, role_value, int(bool(active)), now_utc, now_local),
        )
    if claim_legacy_trades:
        claim_unassigned_plans(trader_id, db_path=path)
    return get_trader(trader_id, db_path=path)


def authenticate_trader(username: str, password: str, *, db_path: str | Path | None = None) -> dict[str, Any] | None:
    path = initialize_journal(db_path)
    try:
        user = normalize_username(username)
    except ValueError:
        return None
    with journal_connection(path) as con:
        row = con.execute("SELECT * FROM traders WHERE username=? COLLATE NOCASE", (user,)).fetchone()
        if row is None or not bool(row["active"]):
            return None
        try:
            digest, _, _ = _hash_password(
                str(password or ""),
                salt_hex=str(row["password_salt"]),
                iterations=int(row["password_iterations"]),
            )
        except ValueError:
            return None
        if not hmac.compare_digest(digest, str(row["password_hash"])):
            return None
        con.execute("UPDATE traders SET last_login_utc=? WHERE trader_id=?", (_utc_now_iso(), row["trader_id"]))
        refreshed = con.execute("SELECT * FROM traders WHERE trader_id=?", (row["trader_id"],)).fetchone()
        return _public_trader(refreshed)


def get_trader(trader_id: str, *, db_path: str | Path | None = None) -> dict[str, Any] | None:
    path = initialize_journal(db_path)
    with journal_connection(path) as con:
        row = con.execute("SELECT * FROM traders WHERE trader_id=?", (str(trader_id),)).fetchone()
    return _public_trader(row) if row is not None else None


def list_traders(*, db_path: str | Path | None = None, active_only: bool = False) -> pd.DataFrame:
    path = initialize_journal(db_path)
    where = "WHERE active=1" if active_only else ""
    with journal_connection(path) as con:
        return pd.read_sql_query(
            f"""
            SELECT trader_id, username, display_name, role, active, created_at_utc, created_at_local, last_login_utc
            FROM traders {where}
            ORDER BY CASE role WHEN 'ADMIN' THEN 0 ELSE 1 END, display_name COLLATE NOCASE, username COLLATE NOCASE
            """,
            con,
        )


def set_trader_active(trader_id: str, active: bool, *, db_path: str | Path | None = None) -> None:
    path = initialize_journal(db_path)
    with journal_connection(path) as con:
        row = con.execute("SELECT role, active FROM traders WHERE trader_id=?", (str(trader_id),)).fetchone()
        if row is None:
            raise KeyError("Unbekannter Trader.")
        if not active and str(row["role"]) == "ADMIN" and bool(row["active"]):
            active_admins = int(con.execute("SELECT COUNT(*) FROM traders WHERE role='ADMIN' AND active=1").fetchone()[0])
            if active_admins <= 1:
                raise ValueError("Der letzte aktive ADMIN kann nicht deaktiviert werden.")
        con.execute("UPDATE traders SET active=? WHERE trader_id=?", (int(bool(active)), str(trader_id)))


def reset_trader_password(trader_id: str, new_password: str, *, db_path: str | Path | None = None) -> None:
    path = initialize_journal(db_path)
    pw_hash, salt, iterations = _hash_password(new_password)
    with journal_connection(path) as con:
        if not con.execute("SELECT 1 FROM traders WHERE trader_id=?", (str(trader_id),)).fetchone():
            raise KeyError("Unbekannter Trader.")
        con.execute(
            "UPDATE traders SET password_hash=?, password_salt=?, password_iterations=? WHERE trader_id=?",
            (pw_hash, salt, iterations, str(trader_id)),
        )


def change_own_password(trader_id: str, old_password: str, new_password: str, *, db_path: str | Path | None = None) -> bool:
    trader = get_trader(trader_id, db_path=db_path)
    if not trader:
        return False
    verified = authenticate_trader(str(trader["username"]), old_password, db_path=db_path)
    if not verified:
        return False
    reset_trader_password(trader_id, new_password, db_path=db_path)
    return True


def unassigned_plan_count(*, db_path: str | Path | None = None) -> int:
    path = initialize_journal(db_path)
    with journal_connection(path) as con:
        return int(con.execute("SELECT COUNT(*) FROM trade_plans WHERE trader_id IS NULL OR trader_id='' ").fetchone()[0])


def claim_unassigned_plans(trader_id: str, *, db_path: str | Path | None = None) -> int:
    """One-time ownership migration for plans created before multi-trader support.

    The immutable plan trigger is suspended only for the ownership column migration;
    trade economics and snapshots are not modified. An audit event is appended per plan.
    """
    path = initialize_journal(db_path)
    trader = get_trader(trader_id, db_path=path)
    if not trader:
        raise KeyError("Unbekannter Trader.")
    now_utc = _utc_now_iso()
    now_local = _local_now_iso()
    with journal_connection(path) as con:
        rows = con.execute("SELECT trade_id FROM trade_plans WHERE trader_id IS NULL OR trader_id='' ORDER BY created_at_utc").fetchall()
        if not rows:
            return 0
        con.execute("DROP TRIGGER IF EXISTS no_update_trade_plans")
        con.execute("UPDATE trade_plans SET trader_id=? WHERE trader_id IS NULL OR trader_id=''", (str(trader_id),))
        con.execute(
            """
            CREATE TRIGGER IF NOT EXISTS no_update_trade_plans
            BEFORE UPDATE ON trade_plans BEGIN SELECT RAISE(ABORT, 'trade_plans are immutable; append a trade_event instead'); END
            """
        )
        events = [
            (
                str(uuid.uuid4()), str(row["trade_id"]), now_utc, now_local,
                "LEGACY_TRADER_CLAIM", "SYSTEM",
                canonical_json({"trader_id": str(trader_id), "username": trader["username"]}),
            )
            for row in rows
        ]
        con.executemany(
            """
            INSERT INTO trade_events(event_id, trade_id, occurred_at_utc, occurred_at_local, event_type, source, payload_json)
            VALUES(?,?,?,?,?,?,?)
            """,
            events,
        )
        con.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('legacy_trades_claimed_by', ?)",
            (str(trader_id),),
        )
        return len(rows)
