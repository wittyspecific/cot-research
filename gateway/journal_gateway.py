from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import secrets
import sys
try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urlparse

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.mt5_account import config_from_mapping as mt5_config_from_mapping, get_mt5_snapshot
from src.trade_journal import (
    append_trade_event,
    create_trade_plan,
    get_trade_events,
    get_trade_outcome,
    get_trade_snapshot,
    initialize_journal,
    journal_connection,
    journal_summary,
    list_trade_plans,
    resolve_db_path,
)
from src.trader_auth import (
    authenticate_trader,
    change_own_password,
    create_trader,
    get_trader,
    list_traders,
    reset_trader_password,
    set_trader_active,
)

VERSION = "3.7.0.1"
MAX_BODY_BYTES = 8 * 1024 * 1024


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (datetime, pd.Timestamp)):
        if pd.isna(value):
            return None
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, pd.DataFrame):
        return [_jsonable(row) for row in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return _jsonable(value.to_dict())
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def _sanitize_snapshot_for_remote(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a remote-safe copy of a historical snapshot.

    Research/execution context stays visible, while FTMO account, open-position
    and private risk data never leave the local Mac through the gateway.
    """
    out = json.loads(json.dumps(_jsonable(dict(payload))))
    out["account"] = {"available": False, "scope": "LOCAL_ONLY"}
    out["portfolio"] = {"open_positions": [], "open_position_count": None, "scope": "LOCAL_ONLY"}
    out["risk"] = {
        "available": False,
        "scope": "LOCAL_ONLY",
        "note": "FTMO-/Portfolio-Risk bleibt ausschließlich in der lokalen Master-Instanz.",
    }
    meta = dict(out.get("meta") or {})
    meta["remote_privacy_filter"] = "ACCOUNT_PORTFOLIO_RISK_REMOVED"
    out["meta"] = meta
    return out


def _read_secrets(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Secrets-Datei nicht gefunden: {path}")
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    return dict(data or {})


def _ensure_session_schema(db_path: Path) -> None:
    initialize_journal(db_path)
    with journal_connection(db_path) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS gateway_sessions(
                session_hash TEXT PRIMARY KEY,
                trader_id TEXT NOT NULL REFERENCES traders(trader_id),
                created_at_utc TEXT NOT NULL,
                expires_at_utc TEXT NOT NULL,
                last_seen_at_utc TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_gateway_sessions_trader ON gateway_sessions(trader_id, expires_at_utc)")


class GatewayState:
    def __init__(self, *, secrets_path: Path, shared_key: str | None = None, session_hours: float = 12.0):
        secrets_data = _read_secrets(secrets_path)
        self.secrets_path = secrets_path
        self.journal_cfg = dict(secrets_data.get("journal", {}) or {})
        self.mt5_cfg = dict(secrets_data.get("mt5", {}) or {})
        self.gateway_cfg = dict(secrets_data.get("gateway", {}) or {})
        self.db_path = resolve_db_path(self.journal_cfg)
        initialize_journal(self.db_path)
        _ensure_session_schema(self.db_path)
        configured_key = str(shared_key or self.gateway_cfg.get("shared_key", "") or "").strip()
        if len(configured_key) < 32:
            raise ValueError("[gateway] shared_key muss mindestens 32 Zeichen lang sein.")
        self.shared_key = configured_key
        try:
            configured_hours = float(self.gateway_cfg.get("session_hours", session_hours))
        except (TypeError, ValueError):
            configured_hours = session_hours
        self.session_hours = max(1.0, min(configured_hours, 72.0))

    def gateway_key_ok(self, candidate: str) -> bool:
        return hmac.compare_digest(str(candidate or ""), self.shared_key)

    def create_session(self, trader_id: str) -> str:
        token = secrets.token_urlsafe(48)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = _utc_now()
        expires = now + timedelta(hours=self.session_hours)
        with journal_connection(self.db_path) as con:
            con.execute(
                """
                INSERT INTO gateway_sessions(session_hash, trader_id, created_at_utc, expires_at_utc, last_seen_at_utc, revoked)
                VALUES(?,?,?,?,?,0)
                """,
                (digest, str(trader_id), _iso(now), _iso(expires), _iso(now)),
            )
            con.execute("DELETE FROM gateway_sessions WHERE revoked=1 OR expires_at_utc < ?", (_iso(now - timedelta(days=2)),))
        return token

    def revoke_session(self, token: str) -> None:
        digest = hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()
        with journal_connection(self.db_path) as con:
            con.execute("UPDATE gateway_sessions SET revoked=1 WHERE session_hash=?", (digest,))

    def authenticate_session(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = _utc_now()
        with journal_connection(self.db_path) as con:
            row = con.execute(
                "SELECT trader_id, expires_at_utc, revoked FROM gateway_sessions WHERE session_hash=?",
                (digest,),
            ).fetchone()
            if row is None or bool(row["revoked"]):
                return None
            try:
                expires = datetime.fromisoformat(str(row["expires_at_utc"]))
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
            if expires <= now:
                con.execute("UPDATE gateway_sessions SET revoked=1 WHERE session_hash=?", (digest,))
                return None
            con.execute("UPDATE gateway_sessions SET last_seen_at_utc=? WHERE session_hash=?", (_iso(now), digest))
            trader_id = str(row["trader_id"])
        trader = get_trader(trader_id, db_path=self.db_path)
        if not trader or not trader.get("active"):
            return None
        return trader

    def authorize_trade(self, trader: Mapping[str, Any], trade_id: str) -> bool:
        if str(trader.get("role", "")).upper() == "ADMIN":
            return True
        with journal_connection(self.db_path) as con:
            row = con.execute("SELECT trader_id FROM trade_plans WHERE trade_id=?", (str(trade_id),)).fetchone()
        return row is not None and str(row["trader_id"] or "") == str(trader.get("trader_id", ""))

    def resolved_trader_filter(self, trader: Mapping[str, Any], requested: str | None) -> str | None:
        if str(trader.get("role", "")).upper() == "ADMIN":
            return str(requested) if requested else None
        return str(trader.get("trader_id", ""))


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "COTJournalGateway/3.7.0.1"

    @property
    def state(self) -> GatewayState:
        return self.server.gateway_state  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(_jsonable(payload), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._send(status, {"error": message})

    def _read_json(self) -> dict[str, Any]:
        raw_len = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_len)
        except ValueError:
            raise ValueError("Ungültige Content-Length.")
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("Request-Body ist zu groß.")
        if length == 0:
            return {}
        body = self.rfile.read(length)
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request enthält kein gültiges JSON.") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON-Body muss ein Objekt sein.")
        return data

    def _gateway_key_required(self) -> bool:
        candidate = self.headers.get("X-COT-Gateway-Key", "")
        if not self.state.gateway_key_ok(candidate):
            self._error(403, "Gateway-Key ungültig.")
            return False
        return True

    def _bearer(self) -> str:
        auth = str(self.headers.get("Authorization", "") or "")
        return auth[7:].strip() if auth.lower().startswith("bearer ") else ""

    def _session_required(self) -> tuple[dict[str, Any] | None, str]:
        if not self._gateway_key_required():
            return None, ""
        token = self._bearer()
        trader = self.state.authenticate_session(token)
        if not trader:
            self._error(401, "Sitzung ungültig oder abgelaufen.")
            return None, token
        return trader, token

    def _admin_required(self) -> tuple[dict[str, Any] | None, str]:
        trader, token = self._session_required()
        if trader and str(trader.get("role", "")).upper() != "ADMIN":
            self._error(403, "ADMIN-Rechte erforderlich.")
            return None, token
        return trader, token

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        try:
            if path == "/v1/health":
                self._send(200, {"ok": True, "version": VERSION, "service": "COT Journal Gateway"})
                return
            if path == "/v1/auth/me":
                trader, _ = self._session_required()
                if trader:
                    self._send(200, trader)
                return
            if path == "/v1/mt5/planner-context":
                trader, _ = self._session_required()
                if not trader:
                    return
                cfg = mt5_config_from_mapping(self.state.mt5_cfg)
                snap = get_mt5_snapshot(cfg)
                # Strictly sanitize account/private portfolio fields before leaving the Mac.
                catalog = snap.get("symbol_catalog", pd.DataFrame())
                if not isinstance(catalog, pd.DataFrame):
                    catalog = pd.DataFrame()
                catalog = catalog.copy()
                # Do not redistribute the live FTMO quote stream through the public planner.
                for quote_col in ("bid", "ask", "last"):
                    if quote_col in catalog.columns:
                        catalog[quote_col] = np.nan
                payload = {
                    "source": snap.get("source"),
                    "captured_at": snap.get("captured_at"),
                    "market_time": None,
                    "symbol_catalog": catalog,
                    "account": {},
                    "positions": [],
                    "privacy_scope": "SYMBOL_METADATA_ONLY_NO_LIVE_QUOTES",
                }
                self._send(200, payload)
                return
            if path == "/v1/journal/summary":
                trader, _ = self._session_required()
                if not trader:
                    return
                requested = (query.get("trader_id") or [None])[0]
                trader_id = self.state.resolved_trader_filter(trader, requested)
                self._send(200, journal_summary(db_path=self.state.db_path, trader_id=trader_id))
                return
            if path == "/v1/trades":
                trader, _ = self._session_required()
                if not trader:
                    return
                requested = (query.get("trader_id") or [None])[0]
                trader_id = self.state.resolved_trader_filter(trader, requested)
                try:
                    limit = max(1, min(int((query.get("limit") or [500])[0]), 5000))
                except (TypeError, ValueError):
                    limit = 500
                plan_type = (query.get("plan_type") or [None])[0]
                raw_statuses = (query.get("lifecycle_statuses") or [""])[0]
                statuses = [x.strip().upper() for x in str(raw_statuses).split(",") if x.strip()] or None
                df = list_trade_plans(db_path=self.state.db_path, limit=limit, plan_type=plan_type, trader_id=trader_id, lifecycle_statuses=statuses)
                self._send(200, {"rows": df})
                return
            if path == "/v1/admin/traders":
                trader, _ = self._admin_required()
                if not trader:
                    return
                active_only = str((query.get("active_only") or ["0"])[0]).lower() in {"1", "true", "yes"}
                self._send(200, {"rows": list_traders(db_path=self.state.db_path, active_only=active_only)})
                return

            parts = [unquote(p) for p in path.split("/") if p]
            if len(parts) == 4 and parts[:2] == ["v1", "trades"] and parts[3] in {"snapshot", "outcome", "events"}:
                trade_id, leaf = parts[2], parts[3]
                trader, _ = self._session_required()
                if not trader:
                    return
                if not self.state.authorize_trade(trader, trade_id):
                    self._error(403, "Kein Zugriff auf diesen Trade.")
                    return
                if leaf == "snapshot":
                    raw_snapshot = get_trade_snapshot(trade_id, db_path=self.state.db_path)
                    self._send(200, _sanitize_snapshot_for_remote(raw_snapshot))
                elif leaf == "outcome":
                    self._send(200, get_trade_outcome(trade_id, db_path=self.state.db_path))
                else:
                    self._send(200, {"rows": get_trade_events(trade_id, db_path=self.state.db_path)})
                return

            self._error(404, "Endpoint nicht gefunden.")
        except KeyError as exc:
            self._error(404, str(exc))
        except Exception as exc:
            self._error(500, f"Gateway-Fehler: {exc}")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path == "/v1/auth/login":
                if not self._gateway_key_required():
                    return
                data = self._read_json()
                trader = authenticate_trader(str(data.get("username", "")), str(data.get("password", "")), db_path=self.state.db_path)
                if not trader:
                    self._error(401, "Login fehlgeschlagen oder Konto deaktiviert.")
                    return
                token = self.state.create_session(str(trader["trader_id"]))
                self._send(200, {"token": token, "trader": trader, "expires_in_hours": self.state.session_hours})
                return
            if path == "/v1/auth/logout":
                trader, token = self._session_required()
                if trader:
                    self.state.revoke_session(token)
                    self._send(200, {"ok": True})
                return
            if path == "/v1/trades":
                trader, _ = self._session_required()
                if not trader:
                    return
                data = self._read_json()
                plan = data.get("plan")
                snapshot_payload = data.get("snapshot_payload")
                if not isinstance(plan, dict) or not isinstance(snapshot_payload, dict):
                    self._error(400, "plan und snapshot_payload müssen JSON-Objekte sein.")
                    return
                snapshot_payload = _sanitize_snapshot_for_remote(snapshot_payload)
                meta = dict(snapshot_payload.get("meta") or {})
                meta["ingest_channel"] = "REMOTE_GATEWAY"
                snapshot_payload["meta"] = meta
                saved = create_trade_plan(
                    plan=plan,
                    snapshot_payload=snapshot_payload,
                    trader_id=str(trader["trader_id"]),
                    db_path=self.state.db_path,
                )
                # Never expose the local database path to the remote deployment.
                saved.pop("db_path", None)
                append_trade_event(
                    str(saved["trade_id"]),
                    "REMOTE_GATEWAY_INGEST",
                    {"gateway_version": VERSION},
                    source="GATEWAY",
                    db_path=self.state.db_path,
                )
                self._send(201, saved)
                return
            if path == "/v1/admin/traders":
                trader, _ = self._admin_required()
                if not trader:
                    return
                data = self._read_json()
                created = create_trader(
                    username=str(data.get("username", "")),
                    display_name=str(data.get("display_name", "")),
                    password=str(data.get("password", "")),
                    role=str(data.get("role", "TRADER")),
                    db_path=self.state.db_path,
                )
                self._send(201, created)
                return
            if path == "/v1/account/change-password":
                trader, _ = self._session_required()
                if not trader:
                    return
                data = self._read_json()
                changed = change_own_password(
                    str(trader["trader_id"]),
                    str(data.get("old_password", "")),
                    str(data.get("new_password", "")),
                    db_path=self.state.db_path,
                )
                if not changed:
                    self._error(400, "Aktuelles Passwort ist falsch.")
                    return
                self._send(200, {"changed": True})
                return

            parts = [unquote(p) for p in path.split("/") if p]
            if len(parts) == 4 and parts[:2] == ["v1", "trades"] and parts[3] == "events":
                trade_id = parts[2]
                trader, _ = self._session_required()
                if not trader:
                    return
                if not self.state.authorize_trade(trader, trade_id):
                    self._error(403, "Kein Zugriff auf diesen Trade.")
                    return
                data = self._read_json()
                event_type = str(data.get("event_type", "") or "").strip().upper()
                if not event_type:
                    self._error(400, "event_type fehlt.")
                    return
                payload = data.get("payload")
                if payload is not None and not isinstance(payload, dict):
                    self._error(400, "payload muss ein JSON-Objekt sein.")
                    return
                event_id = append_trade_event(trade_id, event_type, payload or {}, source="USER", db_path=self.state.db_path)
                self._send(201, {"event_id": event_id})
                return
            if len(parts) == 5 and parts[:3] == ["v1", "admin", "traders"] and parts[4] in {"active", "reset-password"}:
                target_id, action = parts[3], parts[4]
                trader, _ = self._admin_required()
                if not trader:
                    return
                data = self._read_json()
                if action == "active":
                    set_trader_active(target_id, bool(data.get("active", False)), db_path=self.state.db_path)
                    self._send(200, {"ok": True})
                else:
                    reset_trader_password(target_id, str(data.get("new_password", "")), db_path=self.state.db_path)
                    self._send(200, {"ok": True})
                return

            self._error(404, "Endpoint nicht gefunden.")
        except ValueError as exc:
            self._error(400, str(exc))
        except KeyError as exc:
            self._error(404, str(exc))
        except Exception as exc:
            self._error(500, f"Gateway-Fehler: {exc}")


def build_server(host: str, port: int, state: GatewayState) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, int(port)), GatewayHandler)
    server.gateway_state = state  # type: ignore[attr-defined]
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="COT Research local Journal Gateway")
    parser.add_argument("--host", default="127.0.0.1", help="Default 127.0.0.1; expose externally only through an HTTPS tunnel/reverse proxy.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--secrets", default=str(ROOT / ".streamlit" / "secrets.toml"))
    args = parser.parse_args()

    state = GatewayState(secrets_path=Path(args.secrets).expanduser().resolve())
    server = build_server(args.host, args.port, state)
    print(f"COT Journal Gateway V{VERSION} · http://{args.host}:{args.port}")
    print(f"DB: {state.db_path}")
    print("Hinweis: Für Internetzugriff nur über einen HTTPS-Tunnel/Reverse-Proxy veröffentlichen; nicht direkt Port 8765 freigeben.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
