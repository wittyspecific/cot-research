from __future__ import annotations

from typing import Any

import pandas as pd


def _params(trader_id: str | None = None) -> dict[str, Any]:
    return {"trader_id": trader_id} if trader_id else {}


def prop_account(client: Any, *, trader_id: str | None = None) -> dict[str, Any]:
    method = getattr(client, "prop_account", None)
    if callable(method):
        return dict(method(trader_id=trader_id) or {})
    return dict(client._request("GET", "/v1/prop-account", params=_params(trader_id)) or {})


def prop_desk(client: Any, *, trader_id: str | None = None) -> dict[str, Any]:
    method = getattr(client, "prop_desk", None)
    if callable(method):
        return dict(method(trader_id=trader_id) or {})
    return dict(client._request("GET", "/v1/prop-desk", params=_params(trader_id)) or {})


def prop_desk_ranking(client: Any) -> pd.DataFrame:
    method = getattr(client, "prop_desk_ranking", None)
    if callable(method):
        return method()
    payload = client._request("GET", "/v1/prop-desk/ranking")
    return pd.DataFrame((payload or {}).get("rows", []))


def update_prop_account(
    client: Any,
    trader_id: str,
    *,
    starting_capital: float,
    default_risk_pct: float,
    max_risk_pct: float,
    enabled: bool = True,
) -> dict[str, Any]:
    method = getattr(client, "update_prop_account", None)
    if callable(method):
        return dict(
            method(
                trader_id,
                starting_capital=starting_capital,
                default_risk_pct=default_risk_pct,
                max_risk_pct=max_risk_pct,
                enabled=enabled,
            )
            or {}
        )
    from urllib.parse import quote

    return dict(
        client._request(
            "POST",
            f"/v1/admin/traders/{quote(str(trader_id), safe='')}/prop-account",
            json_body={
                "starting_capital": float(starting_capital),
                "default_risk_pct": float(default_risk_pct),
                "max_risk_pct": float(max_risk_pct),
                "enabled": bool(enabled),
            },
        )
        or {}
    )
