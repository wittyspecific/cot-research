from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote

import pandas as pd
import requests


class JournalGatewayError(RuntimeError):
    pass


@dataclass(frozen=True)
class JournalGatewayConfig:
    base_url: str
    shared_key: str
    timeout_seconds: float = 15.0
    verify_tls: bool = True


def config_from_mapping(mapping: Mapping[str, Any] | None) -> JournalGatewayConfig:
    raw = dict(mapping or {})
    base_url = str(raw.get("base_url", "") or "").strip().rstrip("/")
    shared_key = str(raw.get("shared_key", "") or "").strip()
    if not base_url:
        raise ValueError("[gateway] base_url fehlt für REMOTE_GATEWAY.")
    if not base_url.lower().startswith("https://") and not base_url.lower().startswith("http://127.0.0.1") and not base_url.lower().startswith("http://localhost"):
        raise ValueError("Gateway muss per HTTPS erreichbar sein; HTTP ist nur für localhost erlaubt.")
    if len(shared_key) < 32:
        raise ValueError("[gateway] shared_key fehlt oder ist zu kurz (mindestens 32 Zeichen).")
    try:
        timeout = float(raw.get("timeout_seconds", 15.0))
    except (TypeError, ValueError):
        timeout = 15.0
    verify_tls = bool(raw.get("verify_tls", True))
    return JournalGatewayConfig(base_url=base_url, shared_key=shared_key, timeout_seconds=max(2.0, min(timeout, 60.0)), verify_tls=verify_tls)


class JournalGatewayClient:
    def __init__(self, config: JournalGatewayConfig, session_token: str | None = None):
        self.config = config
        self.session_token = str(session_token or "")

    def with_token(self, token: str | None) -> "JournalGatewayClient":
        return JournalGatewayClient(self.config, token)

    def _headers(self, *, auth: bool = True) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-COT-Gateway-Key": self.config.shared_key,
        }
        if auth:
            if not self.session_token:
                raise JournalGatewayError("Keine Gateway-Sitzung aktiv.")
            headers["Authorization"] = f"Bearer {self.session_token}"
        return headers

    def _request(self, method: str, path: str, *, auth: bool = True, params: Mapping[str, Any] | None = None, json_body: Any = None) -> Any:
        url = f"{self.config.base_url}{path}"
        try:
            response = requests.request(
                method,
                url,
                headers=self._headers(auth=auth),
                params=dict(params or {}),
                json=json_body,
                timeout=self.config.timeout_seconds,
                verify=self.config.verify_tls,
            )
        except requests.RequestException as exc:
            raise JournalGatewayError(f"Lokales Journal-Gateway nicht erreichbar: {exc}") from exc
        try:
            payload = response.json()
        except ValueError:
            payload = {"error": response.text[:500]}
        if response.status_code >= 400:
            message = payload.get("error") if isinstance(payload, dict) else str(payload)
            raise JournalGatewayError(str(message or f"Gateway HTTP {response.status_code}"))
        return payload

    def health(self) -> dict[str, Any]:
        payload = self._request("GET", "/v1/health", auth=False)
        return dict(payload or {})

    def login(self, username: str, password: str) -> dict[str, Any]:
        payload = self._request("POST", "/v1/auth/login", auth=False, json_body={"username": username, "password": password})
        return dict(payload or {})

    def logout(self) -> None:
        self._request("POST", "/v1/auth/logout", json_body={})

    def me(self) -> dict[str, Any]:
        return dict(self._request("GET", "/v1/auth/me") or {})

    def planner_context(self) -> dict[str, Any]:
        payload = dict(self._request("GET", "/v1/mt5/planner-context") or {})
        catalog = payload.get("symbol_catalog", [])
        payload["symbol_catalog"] = pd.DataFrame(catalog if isinstance(catalog, list) else [])
        payload["positions"] = pd.DataFrame()
        payload["account"] = {}
        return payload

    def create_trade_plan(self, plan: Mapping[str, Any], snapshot_payload: Mapping[str, Any]) -> dict[str, Any]:
        return dict(self._request("POST", "/v1/trades", json_body={"plan": dict(plan), "snapshot_payload": dict(snapshot_payload)}) or {})

    def list_trade_plans(self, *, limit: int = 500, plan_type: str | None = None, trader_id: str | None = None, lifecycle_statuses: list[str] | None = None) -> pd.DataFrame:
        params: dict[str, Any] = {"limit": int(limit)}
        if plan_type:
            params["plan_type"] = plan_type
        if trader_id:
            params["trader_id"] = trader_id
        if lifecycle_statuses:
            params["lifecycle_statuses"] = ",".join(lifecycle_statuses)
        payload = self._request("GET", "/v1/trades", params=params)
        return pd.DataFrame((payload or {}).get("rows", []))

    def journal_summary(self, *, trader_id: str | None = None) -> dict[str, Any]:
        params = {"trader_id": trader_id} if trader_id else {}
        return dict(self._request("GET", "/v1/journal/summary", params=params) or {})

    def get_trade_snapshot(self, trade_id: str) -> dict[str, Any]:
        return dict(self._request("GET", f"/v1/trades/{quote(str(trade_id), safe='')}/snapshot") or {})

    def get_trade_outcome(self, trade_id: str) -> dict[str, Any]:
        return dict(self._request("GET", f"/v1/trades/{quote(str(trade_id), safe='')}/outcome") or {})

    def get_trade_events(self, trade_id: str) -> pd.DataFrame:
        payload = self._request("GET", f"/v1/trades/{quote(str(trade_id), safe='')}/events")
        return pd.DataFrame((payload or {}).get("rows", []))

    def append_trade_event(self, trade_id: str, event_type: str, payload: Mapping[str, Any] | None = None) -> str:
        out = self._request("POST", f"/v1/trades/{quote(str(trade_id), safe='')}/events", json_body={"event_type": event_type, "payload": dict(payload or {})})
        return str((out or {}).get("event_id", ""))

    def list_traders(self, *, active_only: bool = False) -> pd.DataFrame:
        payload = self._request("GET", "/v1/admin/traders", params={"active_only": int(bool(active_only))})
        return pd.DataFrame((payload or {}).get("rows", []))

    def create_trader(self, *, username: str, display_name: str, password: str, role: str = "TRADER") -> dict[str, Any]:
        return dict(self._request("POST", "/v1/admin/traders", json_body={"username": username, "display_name": display_name, "password": password, "role": role}) or {})

    def set_trader_active(self, trader_id: str, active: bool) -> None:
        self._request("POST", f"/v1/admin/traders/{quote(str(trader_id), safe='')}/active", json_body={"active": bool(active)})

    def reset_trader_password(self, trader_id: str, new_password: str) -> None:
        self._request("POST", f"/v1/admin/traders/{quote(str(trader_id), safe='')}/reset-password", json_body={"new_password": new_password})

    def change_own_password(self, old_password: str, new_password: str) -> bool:
        payload = self._request("POST", "/v1/account/change-password", json_body={"old_password": old_password, "new_password": new_password})
        return bool((payload or {}).get("changed", False))
