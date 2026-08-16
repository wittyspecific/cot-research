from __future__ import annotations

import math
import re
from typing import Any, Mapping


# Planner/chart units can differ from the broker's MT5 quote units. Keep this
# mapping deliberately small and explicit: silent heuristics around money are
# riskier than an auditable instrument rule.
_PRICE_FACTORS_TO_MT5: dict[str, float] = {
    "XCUUSD": 100.0,
}


def _canonical(symbol: Any) -> str:
    raw = str(symbol or "").strip().upper()
    # Broker suffixes such as .c/.cash must not break a known base rule.
    return re.sub(r"[^A-Z0-9]", "", raw)


def price_factor_to_mt5(symbol: Any) -> float:
    key = _canonical(symbol)
    for base, factor in _PRICE_FACTORS_TO_MT5.items():
        if key == base or key.startswith(base):
            return float(factor)
    return 1.0


def has_price_unit_adjustment(symbol: Any) -> bool:
    return not math.isclose(price_factor_to_mt5(symbol), 1.0, rel_tol=0.0, abs_tol=1e-12)


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def plan_price_to_mt5(symbol: Any, value: Any) -> float | None:
    number = _finite(value)
    if number is None:
        return None
    return float(number * price_factor_to_mt5(symbol))


def mt5_price_to_plan(symbol: Any, value: Any) -> float | None:
    number = _finite(value)
    if number is None:
        return None
    factor = price_factor_to_mt5(symbol)
    return float(number / factor)


def planner_digits(symbol: Any, mt5_digits: int) -> int:
    factor = price_factor_to_mt5(symbol)
    extra = 0
    if factor >= 10 and math.isclose(factor, 10 ** round(math.log10(factor)), rel_tol=1e-12):
        extra = int(round(math.log10(factor)))
    return min(max(int(mt5_digits) + extra, 0), 8)


def price_unit_note(symbol: Any) -> str | None:
    factor = price_factor_to_mt5(symbol)
    if math.isclose(factor, 1.0, rel_tol=0.0, abs_tol=1e-12):
        return None
    return (
        f"MT5-Preisfaktor ×{factor:g} aktiv: Zone/SL/TP werden in deiner Chart-Einheit gespeichert "
        "und für Execution, History und Prop Desk automatisch in MT5-Einheiten umgerechnet."
    )


def auto_market_reference_entry(plan: Mapping[str, Any]) -> float | None:
    """DB-compatible reference only; never a MARKET execution price."""
    explicit = _finite(plan.get("entry"))
    if explicit is not None:
        return explicit
    low = _finite(plan.get("zone_low"))
    high = _finite(plan.get("zone_high"))
    if low is not None and high is not None:
        return float((low + high) / 2.0)
    return None


def plan_to_mt5_units(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy whose price levels are in broker/MT5 quote units.

    The marker prevents double-scaling after a live/history execution price has
    already replaced the synthetic/planned entry.
    """
    out = dict(plan)
    if str(out.get("_price_units") or "").upper() == "MT5":
        return out
    symbol = out.get("cfd_symbol")
    factor = price_factor_to_mt5(symbol)
    for key in ("entry", "stop", "target", "zone_low", "zone_high"):
        value = _finite(out.get(key))
        if value is not None:
            out[key] = float(value * factor)
    out["_price_units"] = "MT5"
    out["_price_unit_factor"] = float(factor)
    return out
