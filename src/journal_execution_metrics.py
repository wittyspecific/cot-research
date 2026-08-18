from __future__ import annotations

import math
from typing import Any, Mapping

from .price_units import mt5_price_to_plan


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def execution_rr(row: Mapping[str, Any]) -> float | None:
    """Initial R:R for a filled MARKET trade using the real execution price."""
    if str(row.get("order_type") or "").upper() != "MARKET":
        return None

    execution_mt5 = _finite(row.get("execution_price"))
    stop = _finite(row.get("stop"))
    target = _finite(row.get("target"))
    if execution_mt5 is None or stop is None or target is None:
        return None

    execution_plan = mt5_price_to_plan(row.get("cfd_symbol"), execution_mt5)
    execution = _finite(execution_plan)
    if execution is None:
        return None

    risk = abs(execution - stop)
    if risk <= 0:
        return None

    side = str(row.get("side") or "").upper()
    if side == "LONG":
        reward = target - execution
    elif side == "SHORT":
        reward = execution - target
    else:
        return None

    if reward <= 0:
        return None
    return float(reward / risk)


def effective_rr(row: Mapping[str, Any]) -> float | None:
    """LIMIT uses planned R:R; MARKET uses actual fill R:R."""
    if str(row.get("order_type") or "").upper() == "MARKET":
        return execution_rr(row)
    return _finite(row.get("planned_rr"))


def rr_source(row: Mapping[str, Any]) -> str:
    if str(row.get("order_type") or "").upper() == "MARKET":
        return "EXECUTION" if execution_rr(row) is not None else "PENDING_FILL"
    return "PLANNED"
