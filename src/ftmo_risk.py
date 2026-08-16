from __future__ import annotations

from dataclasses import dataclass
from math import floor
import re
from typing import Any, Mapping

import numpy as np
import pandas as pd


CURRENCIES = {
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "MXN", "NOK",
    "SEK", "DKK", "SGD", "HKD", "CNH", "CNY", "ZAR", "TRY", "PLN", "CZK",
    "HUF", "BRL",
}


@dataclass(frozen=True)
class FTMORiskConfig:
    """Risk policy for a 2-Step FTMO Swing account.

    The 5% Maximum Daily Loss and 10% Maximum Loss values are FTMO 2-Step
    objectives. Every other limit below is an internal, user-adjustable safety
    policy and must not be presented as an FTMO rule.
    """

    initial_capital: float = 100_000.0
    max_daily_loss_pct: float = 0.05
    max_loss_pct: float = 0.10

    # V3.5.2 conservative institutional defaults (internal policy only).
    target_trade_risk_pct: float = 0.0025
    max_single_trade_risk_pct: float = 0.0050
    max_instrument_risk_pct: float = 0.0050
    max_open_risk_pct: float = 0.0200
    max_cluster_risk_pct: float = 0.0075
    max_fx_factor_risk_pct: float = 0.0075
    daily_safety_reserve_pct: float = 0.0200
    total_safety_reserve_pct: float = 0.0400
    weekend_stress_multiplier: float = 2.00


def risk_config_from_mapping(mapping: Mapping[str, Any] | None) -> FTMORiskConfig:
    raw = dict(mapping or {})

    def f(name: str, default: float, low: float, high: float) -> float:
        try:
            value = float(raw.get(name, default))
        except (TypeError, ValueError):
            value = default
        return min(max(value, low), high)

    return FTMORiskConfig(
        initial_capital=f("initial_capital", 100_000.0, 1_000.0, 10_000_000.0),
        # FTMO 2-Step rule values remain fixed by design.
        max_daily_loss_pct=0.05,
        max_loss_pct=0.10,
        target_trade_risk_pct=f("target_trade_risk_pct", 0.0025, 0.0001, 0.05),
        max_single_trade_risk_pct=f("max_single_trade_risk_pct", 0.0050, 0.0001, 0.05),
        max_instrument_risk_pct=f("max_instrument_risk_pct", 0.0050, 0.0001, 0.10),
        max_open_risk_pct=f("max_open_risk_pct", 0.0200, 0.001, 0.20),
        max_cluster_risk_pct=f("max_cluster_risk_pct", 0.0075, 0.001, 0.20),
        max_fx_factor_risk_pct=f("max_fx_factor_risk_pct", 0.0075, 0.001, 0.20),
        daily_safety_reserve_pct=f("daily_safety_reserve_pct", 0.0200, 0.0, 0.05),
        total_safety_reserve_pct=f("total_safety_reserve_pct", 0.0400, 0.0, 0.10),
        weekend_stress_multiplier=f("weekend_stress_multiplier", 2.00, 1.0, 5.0),
    )


def _finite(value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return np.nan
    return x if np.isfinite(x) else np.nan


def _tick_value(row: Mapping[str, Any]) -> float:
    loss = _finite(row.get("tick_value_loss"))
    if np.isfinite(loss) and loss > 0:
        return loss
    generic = _finite(row.get("tick_value"))
    return generic if np.isfinite(generic) and generic > 0 else np.nan


def _symbol_core(symbol: str) -> str:
    """Return a stable uppercase core for broker-suffixed CFD symbols."""
    raw = str(symbol or "").upper().strip()
    raw = re.split(r"[._#\-]", raw, maxsplit=1)[0]
    return re.sub(r"[^A-Z0-9]", "", raw)


def canonical_instrument(symbol: str) -> str:
    """Aggregate tickets that represent the same broker instrument/underlying."""
    core = _symbol_core(symbol)
    aliases = {
        "NGAS": "NATGAS",
        "NATURALGAS": "NATGAS",
        "WTI": "USOIL",
        "BRENT": "UKOIL",
        "BRN": "UKOIL",
        "USTEC": "US100",
        "NAS100": "US100",
        "SPX500": "US500",
        "DJ30": "US30",
        "DJI30": "US30",
        "COPPER": "XCUUSD",
    }
    return aliases.get(core, core)


def fx_pair_from_symbol(symbol: str, currency_base: str = "", currency_profit: str = "") -> tuple[str, str] | None:
    base = str(currency_base or "").upper().strip()
    quote = str(currency_profit or "").upper().strip()
    if base in CURRENCIES and quote in CURRENCIES and base != quote:
        return base, quote

    core = _symbol_core(symbol)
    if len(core) >= 6:
        b, q = core[:3], core[3:6]
        if b in CURRENCIES and q in CURRENCIES and b != q:
            return b, q
    return None


def classify_cluster(symbol: str, currency_base: str = "", currency_profit: str = "") -> str:
    core = _symbol_core(symbol)

    # FX must be detected before broad textual index aliases. This prevents
    # symbols such as AUDJPY from accidentally matching a "DJ" index token.
    if fx_pair_from_symbol(symbol, currency_base, currency_profit):
        return "FX"

    if any(token in core for token in ("XAU", "XAG", "XPT", "XPD", "XCU", "COPPER")):
        return "Metals"
    if any(token in core for token in ("USOIL", "UKOIL", "WTI", "BRENT", "BRN", "NGAS", "NATGAS", "GASOIL")):
        return "Energy"
    if any(token in core for token in (
        "US500", "SPX", "US100", "NAS100", "USTEC", "US30", "DJ30", "DJI30",
        "GER40", "DE40", "UK100", "FRA40", "EU50", "STOXX", "JP225", "JPN225",
        "AUS200", "HK50", "VIX",
    )):
        return "Indices"
    if any(token in core for token in ("BTC", "ETH", "LTC", "XRP", "SOL", "ADA", "DOT", "DOGE")):
        return "Crypto"
    return "Other"


def stop_risk(row: Mapping[str, Any], *, from_current: bool = True) -> float:
    """Return additional account-currency loss to SL using MT5 tick economics."""
    side = str(row.get("side", "")).upper()
    sl = _finite(row.get("sl"))
    ref = _finite(row.get("price_current" if from_current else "price_open"))
    volume = _finite(row.get("volume"))
    tick_size = _finite(row.get("tick_size"))
    tick_value = _tick_value(row)

    if not all(np.isfinite(v) for v in (sl, ref, volume, tick_size, tick_value)):
        return np.nan
    if sl <= 0 or ref <= 0 or volume <= 0 or tick_size <= 0 or tick_value <= 0:
        return np.nan

    if side == "LONG":
        distance = ref - sl
    elif side == "SHORT":
        distance = sl - ref
    else:
        return np.nan

    distance = max(distance, 0.0)
    return float((distance / tick_size) * tick_value * volume)


def enrich_position_risk(positions: pd.DataFrame, cfg: FTMORiskConfig) -> pd.DataFrame:
    out = positions.copy()
    if out.empty:
        dtypes = {
            "has_sl": "bool",
            "stop_risk_current": "float64",
            "stop_risk_entry": "float64",
            "risk_pct_initial": "float64",
            "cluster": "object",
            "instrument": "object",
        }
        for col, dtype in dtypes.items():
            out[col] = pd.Series(dtype=dtype)
        return out

    out["has_sl"] = pd.to_numeric(out.get("sl"), errors="coerce").fillna(0) > 0
    out["stop_risk_current"] = out.apply(lambda r: stop_risk(r, from_current=True), axis=1)
    out["stop_risk_entry"] = out.apply(lambda r: stop_risk(r, from_current=False), axis=1)
    out["risk_pct_initial"] = out["stop_risk_current"] / float(cfg.initial_capital)
    out["instrument"] = out["symbol"].map(canonical_instrument)
    out["cluster"] = out.apply(
        lambda r: classify_cluster(
            r.get("symbol", ""), r.get("currency_base", ""), r.get("currency_profit", "")
        ),
        axis=1,
    )
    return out


def ftmo_rule_state(account: Mapping[str, Any], positions: pd.DataFrame, cfg: FTMORiskConfig) -> dict[str, Any]:
    equity = _finite(account.get("equity"))
    balance = _finite(account.get("balance"))
    day_start_balance = _finite(account.get("day_start_balance"))
    daily_realized = _finite(account.get("daily_realized_pnl"))

    daily_loss_amount = cfg.initial_capital * cfg.max_daily_loss_pct
    maximum_loss_amount = cfg.initial_capital * cfg.max_loss_pct
    daily_limit = day_start_balance - daily_loss_amount if np.isfinite(day_start_balance) else np.nan
    maximum_loss_limit = cfg.initial_capital - maximum_loss_amount

    enriched = enrich_position_risk(positions, cfg)
    known_open_risk = float(pd.to_numeric(enriched.get("stop_risk_current"), errors="coerce").fillna(0).sum())
    missing_sl_count = int((~enriched.get("has_sl", pd.Series(dtype=bool)).fillna(False)).sum()) if not enriched.empty else 0

    daily_buffer = equity - daily_limit if np.isfinite(equity) and np.isfinite(daily_limit) else np.nan
    total_buffer = equity - maximum_loss_limit if np.isfinite(equity) else np.nan
    all_stops_equity = equity - known_open_risk if np.isfinite(equity) else np.nan
    weekend_stress_loss = known_open_risk * cfg.weekend_stress_multiplier
    weekend_stress_equity = equity - weekend_stress_loss if np.isfinite(equity) else np.nan

    return {
        "balance": balance,
        "equity": equity,
        "day_start_balance": day_start_balance,
        "daily_realized_pnl": daily_realized,
        "daily_loss_amount": daily_loss_amount,
        "daily_limit": daily_limit,
        "daily_buffer": daily_buffer,
        "maximum_loss_amount": maximum_loss_amount,
        "maximum_loss_limit": maximum_loss_limit,
        "total_buffer": total_buffer,
        "known_open_stop_risk": known_open_risk,
        "known_open_stop_risk_pct": known_open_risk / cfg.initial_capital,
        "missing_sl_count": missing_sl_count,
        "all_stops_equity": all_stops_equity,
        "weekend_stress_loss": weekend_stress_loss,
        "weekend_stress_equity": weekend_stress_equity,
        "exact_daily_limit": bool(np.isfinite(day_start_balance)),
        "positions": enriched,
    }


def instrument_risk_table(positions: pd.DataFrame, cfg: FTMORiskConfig) -> pd.DataFrame:
    enriched = enrich_position_risk(positions, cfg)
    cols = ["instrument", "symbols", "positions", "stop_risk", "risk_pct", "limit", "remaining"]
    if enriched.empty:
        return pd.DataFrame(columns=cols)
    work = enriched.copy()
    work["stop_risk_current"] = pd.to_numeric(work["stop_risk_current"], errors="coerce").fillna(0.0)
    grouped = work.groupby("instrument", dropna=False).agg(
        symbols=("symbol", lambda x: ", ".join(sorted(set(map(str, x))))),
        positions=("symbol", "count"),
        stop_risk=("stop_risk_current", "sum"),
    ).reset_index()
    grouped["risk_pct"] = grouped["stop_risk"] / cfg.initial_capital
    grouped["limit"] = cfg.initial_capital * cfg.max_instrument_risk_pct
    grouped["remaining"] = grouped["limit"] - grouped["stop_risk"]
    return grouped[cols].sort_values(["stop_risk", "instrument"], ascending=[False, True]).reset_index(drop=True)


def cluster_risk_table(positions: pd.DataFrame, cfg: FTMORiskConfig) -> pd.DataFrame:
    enriched = enrich_position_risk(positions, cfg)
    cols = ["cluster", "positions", "instruments", "stop_risk", "risk_pct", "limit", "remaining"]
    if enriched.empty:
        return pd.DataFrame(columns=cols)
    work = enriched.copy()
    work["stop_risk_current"] = pd.to_numeric(work["stop_risk_current"], errors="coerce").fillna(0.0)
    grouped = work.groupby("cluster", dropna=False).agg(
        positions=("symbol", "count"),
        instruments=("instrument", "nunique"),
        stop_risk=("stop_risk_current", "sum"),
    ).reset_index()
    grouped["risk_pct"] = grouped["stop_risk"] / cfg.initial_capital
    grouped["limit"] = cfg.initial_capital * cfg.max_cluster_risk_pct
    grouped["remaining"] = grouped["limit"] - grouped["stop_risk"]
    return grouped[cols].sort_values(["stop_risk", "cluster"], ascending=[False, True]).reset_index(drop=True)


def _fx_factor_rows(positions: pd.DataFrame, cfg: FTMORiskConfig) -> pd.DataFrame:
    enriched = enrich_position_risk(positions, cfg)
    rows: list[dict[str, Any]] = []
    for _, row in enriched.iterrows():
        pair = fx_pair_from_symbol(row.get("symbol", ""), row.get("currency_base", ""), row.get("currency_profit", ""))
        if row.get("cluster") != "FX" or pair is None:
            continue
        risk = _finite(row.get("stop_risk_current"))
        if not np.isfinite(risk):
            continue
        base, quote = pair
        side = str(row.get("side", "") or "").upper()
        if side not in {"LONG", "SHORT"}:
            continue
        base_sign = 1 if side == "LONG" else -1
        quote_sign = -base_sign
        common = {"symbol": row.get("symbol"), "ticket": row.get("ticket")}
        rows.append({"currency": base, "signed_risk": base_sign * risk, "gross_risk": risk, **common})
        rows.append({"currency": quote, "signed_risk": quote_sign * risk, "gross_risk": risk, **common})
    return pd.DataFrame(rows)


def fx_factor_risk_table(positions: pd.DataFrame, cfg: FTMORiskConfig) -> pd.DataFrame:
    cols = [
        "currency", "direction", "net_factor_risk", "gross_factor_risk", "net_risk_pct",
        "gross_risk_pct", "positions", "symbols", "limit", "remaining",
    ]
    df = _fx_factor_rows(positions, cfg)
    if df.empty:
        return pd.DataFrame(columns=cols)
    out = df.groupby("currency").agg(
        net_factor_risk=("signed_risk", "sum"),
        gross_factor_risk=("gross_risk", "sum"),
        positions=("ticket", "count"),
        symbols=("symbol", lambda x: ", ".join(sorted(set(map(str, x))))),
    ).reset_index()
    out["direction"] = np.where(
        out["net_factor_risk"] > 1e-12,
        "LONG",
        np.where(out["net_factor_risk"] < -1e-12, "SHORT", "NEUTRAL"),
    )
    out["net_risk_pct"] = out["net_factor_risk"].abs() / cfg.initial_capital
    out["gross_risk_pct"] = out["gross_factor_risk"] / cfg.initial_capital
    out["limit"] = cfg.initial_capital * cfg.max_fx_factor_risk_pct
    out["remaining"] = out["limit"] - out["net_factor_risk"].abs()
    return out[cols].sort_values(["net_risk_pct", "currency"], ascending=[False, True]).reset_index(drop=True)


def _round_volume_down(raw_volume: float, step: float, minimum: float, maximum: float) -> float:
    if not all(np.isfinite(v) for v in (raw_volume, step, minimum, maximum)):
        return 0.0
    if raw_volume <= 0 or step <= 0 or maximum <= 0:
        return 0.0
    minimum = max(minimum, step)
    if raw_volume + 1e-12 < minimum:
        return 0.0
    units = floor((min(raw_volume, maximum) + 1e-12) / step)
    volume = units * step
    if volume + 1e-12 < minimum:
        return 0.0
    return float(min(volume, maximum))


def size_trade(
    spec: Mapping[str, Any], *, side: str, entry: float, stop: float, risk_budget: float
) -> dict[str, Any]:
    side = str(side or "").upper()
    entry = _finite(entry)
    stop = _finite(stop)
    risk_budget = _finite(risk_budget)
    tick_size = _finite(spec.get("tick_size"))
    tick_value = _tick_value(spec)
    volume_min = _finite(spec.get("volume_min"))
    volume_max = _finite(spec.get("volume_max"))
    volume_step = _finite(spec.get("volume_step"))

    if side not in {"LONG", "SHORT"}:
        return {"ok": False, "reason": "Richtung muss LONG oder SHORT sein."}
    if not all(np.isfinite(v) for v in (entry, stop, risk_budget, tick_size, tick_value, volume_min, volume_max, volume_step)):
        return {"ok": False, "reason": "Unvollständige MT5-Symbolspezifikation oder ungültige Eingabe."}
    if entry <= 0 or stop <= 0 or risk_budget <= 0 or tick_size <= 0 or tick_value <= 0:
        return {"ok": False, "reason": "Entry, Stop, Tick-Werte und Risikobudget müssen positiv sein."}
    if side == "LONG" and stop >= entry:
        return {"ok": False, "reason": "Bei LONG muss der Stop unter dem Entry liegen."}
    if side == "SHORT" and stop <= entry:
        return {"ok": False, "reason": "Bei SHORT muss der Stop über dem Entry liegen."}

    distance = abs(entry - stop)
    risk_per_lot = (distance / tick_size) * tick_value
    raw_lots = risk_budget / risk_per_lot if risk_per_lot > 0 else 0.0
    lots = _round_volume_down(raw_lots, volume_step, volume_min, volume_max)
    actual_risk = lots * risk_per_lot
    if lots <= 0:
        min_risk = volume_min * risk_per_lot
        return {
            "ok": False,
            "reason": "Kleinste handelbare Lotgröße überschreitet das freigegebene Risikobudget.",
            "raw_lots": raw_lots,
            "minimum_lots": volume_min,
            "minimum_risk": min_risk,
            "risk_per_lot": risk_per_lot,
        }
    return {
        "ok": True,
        "lots": lots,
        "raw_lots": raw_lots,
        "actual_risk": actual_risk,
        "risk_per_lot": risk_per_lot,
        "distance": distance,
    }


def _existing_fx_net(positions: pd.DataFrame, cfg: FTMORiskConfig) -> dict[str, float]:
    df = _fx_factor_rows(positions, cfg)
    if df.empty:
        return {}
    return df.groupby("currency")["signed_risk"].sum().astype(float).to_dict()


def _proposed_fx_signs(symbol: str, spec: Mapping[str, Any], side: str) -> dict[str, int]:
    pair = fx_pair_from_symbol(symbol, spec.get("currency_base", ""), spec.get("currency_profit", ""))
    side = str(side or "").upper()
    if pair is None or side not in {"LONG", "SHORT"}:
        return {}
    base, quote = pair
    base_sign = 1 if side == "LONG" else -1
    return {base: base_sign, quote: -base_sign}


def portfolio_risk_status(account: Mapping[str, Any], positions: pd.DataFrame, cfg: FTMORiskConfig) -> dict[str, Any]:
    """Return GREEN/YELLOW/RED based on internal policy and FTMO buffers."""
    state = ftmo_rule_state(account, positions, cfg)
    instruments = instrument_risk_table(positions, cfg)
    clusters = cluster_risk_table(positions, cfg)
    fx = fx_factor_risk_table(positions, cfg)

    red: list[str] = []
    yellow: list[str] = []

    if state["missing_sl_count"] > 0:
        red.append(f"{state['missing_sl_count']} offene Position(en) ohne Stop Loss.")
    if state["known_open_stop_risk_pct"] > cfg.max_open_risk_pct + 1e-12:
        red.append("Portfolio Open Stop Risk liegt über dem internen Limit.")

    if not instruments.empty:
        for _, row in instruments[instruments["remaining"] < -1e-9].iterrows():
            red.append(f"Instrument {row['instrument']} liegt über dem Instrument-Limit.")
    if not clusters.empty:
        for _, row in clusters[clusters["remaining"] < -1e-9].iterrows():
            red.append(f"Cluster {row['cluster']} liegt über dem Cluster-Limit.")
    if not fx.empty:
        for _, row in fx[fx["remaining"] < -1e-9].iterrows():
            red.append(f"FX-Faktor {row['currency']} liegt über dem Richtungs-Limit.")

    daily_internal_floor = (
        state["daily_limit"] + cfg.initial_capital * cfg.daily_safety_reserve_pct
        if np.isfinite(state["daily_limit"]) else np.nan
    )
    total_internal_floor = state["maximum_loss_limit"] + cfg.initial_capital * cfg.total_safety_reserve_pct

    if np.isfinite(state["all_stops_equity"]) and np.isfinite(daily_internal_floor) and state["all_stops_equity"] < daily_internal_floor:
        red.append("All-Stops-Equity unterschreitet den internen Daily-Sicherheitsfloor.")
    if np.isfinite(state["weekend_stress_equity"]) and state["weekend_stress_equity"] < total_internal_floor:
        red.append("Weekend-Stress unterschreitet den internen Max-Loss-Sicherheitsfloor.")

    # Yellow = at least 75% utilization of any internal concentration cap.
    def near_limit(risk: float, limit: float) -> bool:
        return limit > 0 and risk >= 0.75 * limit - 1e-12

    if not red:
        if near_limit(state["known_open_stop_risk"], cfg.initial_capital * cfg.max_open_risk_pct):
            yellow.append("Portfolio Open Stop Risk nutzt mindestens 75 % des Limits.")
        if not instruments.empty and (instruments["stop_risk"] >= 0.75 * instruments["limit"]).any():
            yellow.append("Mindestens ein Instrument nutzt mindestens 75 % seines Limits.")
        if not clusters.empty and (clusters["stop_risk"] >= 0.75 * clusters["limit"]).any():
            yellow.append("Mindestens ein Cluster nutzt mindestens 75 % seines Limits.")
        if not fx.empty and (fx["net_factor_risk"].abs() >= 0.75 * fx["limit"]).any():
            yellow.append("Mindestens ein FX-Faktor nutzt mindestens 75 % seines Limits.")

    status = "RED" if red else ("YELLOW" if yellow else "GREEN")
    reasons = red if red else yellow
    return {
        "status": status,
        "reasons": reasons,
        "state": state,
        "instrument_table": instruments,
        "cluster_table": clusters,
        "fx_factor_table": fx,
        "daily_internal_floor": daily_internal_floor,
        "total_internal_floor": total_internal_floor,
    }



def risk_cockpit_summary(
    account: Mapping[str, Any], positions: pd.DataFrame, cfg: FTMORiskConfig
) -> dict[str, Any]:
    """Compact decision-oriented portfolio view for the Risk Cockpit.

    This deliberately reuses the same calculations as the detailed risk page so
    the cockpit cannot drift from the underlying FTMO/risk-engine methodology.
    """
    status = portfolio_risk_status(account, positions, cfg)
    state = status["state"]
    instruments = status["instrument_table"].copy()
    clusters = status["cluster_table"].copy()
    fx = status["fx_factor_table"].copy()

    portfolio_limit = float(cfg.initial_capital * cfg.max_open_risk_pct)
    portfolio_risk = float(state["known_open_stop_risk"])
    portfolio_remaining = portfolio_limit - portfolio_risk

    daily_buffer = _finite(state.get("daily_buffer"))
    total_buffer = _finite(state.get("total_buffer"))
    ftmo_current_ok = bool(
        np.isfinite(daily_buffer)
        and np.isfinite(total_buffer)
        and daily_buffer > 0
        and total_buffer > 0
    )

    all_stops_daily_safety = (
        _finite(state.get("all_stops_equity")) - _finite(status.get("daily_internal_floor"))
        if np.isfinite(_finite(state.get("all_stops_equity")))
        and np.isfinite(_finite(status.get("daily_internal_floor")))
        else np.nan
    )
    weekend_total_safety = (
        _finite(state.get("weekend_stress_equity")) - _finite(status.get("total_internal_floor"))
        if np.isfinite(_finite(state.get("weekend_stress_equity")))
        and np.isfinite(_finite(status.get("total_internal_floor")))
        else np.nan
    )

    driver_rows: list[dict[str, Any]] = []
    if not instruments.empty:
        for _, row in instruments.iterrows():
            limit = _finite(row.get("limit"))
            risk_value = _finite(row.get("stop_risk"))
            utilization = risk_value / limit if np.isfinite(limit) and limit > 0 else np.nan
            driver_rows.append(
                {
                    "label": str(row.get("instrument") or "—"),
                    "kind": "Instrument",
                    "risk": risk_value,
                    "limit": limit,
                    "remaining": _finite(row.get("remaining")),
                    "utilization": utilization,
                }
            )
    if not clusters.empty:
        for _, row in clusters.iterrows():
            limit = _finite(row.get("limit"))
            risk_value = _finite(row.get("stop_risk"))
            utilization = risk_value / limit if np.isfinite(limit) and limit > 0 else np.nan
            driver_rows.append(
                {
                    "label": str(row.get("cluster") or "—"),
                    "kind": "Cluster",
                    "risk": risk_value,
                    "limit": limit,
                    "remaining": _finite(row.get("remaining")),
                    "utilization": utilization,
                }
            )
    if not fx.empty:
        for _, row in fx.iterrows():
            limit = _finite(row.get("limit"))
            risk_value = abs(_finite(row.get("net_factor_risk")))
            utilization = risk_value / limit if np.isfinite(limit) and limit > 0 else np.nan
            direction = str(row.get("direction") or "")
            driver_rows.append(
                {
                    "label": f"{row.get('currency', '—')} {direction}".strip(),
                    "kind": "FX-Faktor",
                    "risk": risk_value,
                    "limit": limit,
                    "remaining": _finite(row.get("remaining")),
                    "utilization": utilization,
                }
            )

    drivers = pd.DataFrame(driver_rows)
    if not drivers.empty:
        drivers = drivers.sort_values(
            ["utilization", "risk", "label"], ascending=[False, False, True], na_position="last"
        ).reset_index(drop=True)

    cluster_capacity = clusters.copy()
    if not cluster_capacity.empty:
        cluster_capacity["available"] = pd.to_numeric(
            cluster_capacity["remaining"], errors="coerce"
        ).clip(lower=0.0)
        cluster_capacity["utilization"] = (
            pd.to_numeric(cluster_capacity["stop_risk"], errors="coerce")
            / pd.to_numeric(cluster_capacity["limit"], errors="coerce").replace(0, np.nan)
        )

    return {
        "status": status["status"],
        "reasons": list(status["reasons"]),
        "state": state,
        "ftmo_current_ok": ftmo_current_ok,
        "portfolio_limit": portfolio_limit,
        "portfolio_risk": portfolio_risk,
        "portfolio_remaining": portfolio_remaining,
        "all_stops_daily_safety": all_stops_daily_safety,
        "weekend_total_safety": weekend_total_safety,
        "drivers": drivers,
        "cluster_capacity": cluster_capacity,
    }

def pretrade_approval(
    *,
    account: Mapping[str, Any],
    positions: pd.DataFrame,
    cfg: FTMORiskConfig,
    spec: Mapping[str, Any],
    symbol: str,
    side: str,
    entry: float,
    stop: float,
    requested_risk_pct: float,
) -> dict[str, Any]:
    state = ftmo_rule_state(account, positions, cfg)
    requested = max(0.0, float(requested_risk_pct)) * cfg.initial_capital
    cluster = classify_cluster(symbol, spec.get("currency_base", ""), spec.get("currency_profit", ""))
    instrument = canonical_instrument(symbol)

    cluster_table = cluster_risk_table(positions, cfg)
    cluster_existing = 0.0
    if not cluster_table.empty:
        match = cluster_table[cluster_table["cluster"] == cluster]
        if not match.empty:
            cluster_existing = float(match.iloc[0]["stop_risk"])

    instrument_table = instrument_risk_table(positions, cfg)
    instrument_existing = 0.0
    if not instrument_table.empty:
        match = instrument_table[instrument_table["instrument"] == instrument]
        if not match.empty:
            instrument_existing = float(match.iloc[0]["stop_risk"])

    reasons: list[str] = []
    if not state["exact_daily_limit"]:
        reasons.append("Exakter FTMO Daily-Loss-Limit fehlt: MT5-Bridge aktualisieren.")
    if state["missing_sl_count"] > 0:
        reasons.append("Mindestens eine offene Position besitzt keinen Stop Loss; Gesamt-Stop-Risk ist nicht begrenzt.")

    max_single = cfg.initial_capital * cfg.max_single_trade_risk_pct
    max_instrument = cfg.initial_capital * cfg.max_instrument_risk_pct
    open_remaining = cfg.initial_capital * cfg.max_open_risk_pct - state["known_open_stop_risk"]
    cluster_remaining = cfg.initial_capital * cfg.max_cluster_risk_pct - cluster_existing
    instrument_remaining = max_instrument - instrument_existing
    daily_remaining = (
        state["daily_buffer"]
        - cfg.initial_capital * cfg.daily_safety_reserve_pct
        - state["known_open_stop_risk"]
        if np.isfinite(state["daily_buffer"])
        else np.nan
    )
    total_remaining = (
        state["total_buffer"]
        - cfg.initial_capital * cfg.total_safety_reserve_pct
        - state["known_open_stop_risk"]
        if np.isfinite(state["total_buffer"])
        else np.nan
    )

    caps: dict[str, float] = {
        "requested": requested,
        "single_trade": max_single,
        "instrument": max(0.0, instrument_remaining),
        "open_risk": max(0.0, open_remaining),
        "cluster": max(0.0, cluster_remaining),
        "daily_ftmo_buffer": max(0.0, daily_remaining) if np.isfinite(daily_remaining) else 0.0,
        "total_ftmo_buffer": max(0.0, total_remaining) if np.isfinite(total_remaining) else 0.0,
    }

    # Directional FX factor caps. Opposite-direction trades can release rather
    # than consume factor risk, therefore the cap is based on signed net risk.
    existing_fx = _existing_fx_net(positions, cfg)
    proposed_signs = _proposed_fx_signs(symbol, spec, side)
    fx_limit = cfg.initial_capital * cfg.max_fx_factor_risk_pct
    factor_details: dict[str, dict[str, float | int]] = {}
    for currency, sign in proposed_signs.items():
        existing_net = float(existing_fx.get(currency, 0.0))
        remaining = max(0.0, fx_limit - sign * existing_net)
        caps[f"fx_factor_{currency}"] = remaining
        factor_details[currency] = {
            "existing_net": existing_net,
            "sign": int(sign),
            "limit": fx_limit,
            "remaining_for_direction": remaining,
        }

    hard_zero_messages = [
        (open_remaining <= 0, "Portfolio Open-Risk-Limit ist bereits ausgeschöpft."),
        (instrument_remaining <= 0, f"Instrument-Limit für {instrument} ist bereits ausgeschöpft."),
        (cluster_remaining <= 0, f"Cluster-Limit für {cluster} ist bereits ausgeschöpft."),
    ]
    for condition, message in hard_zero_messages:
        if condition:
            reasons.append(message)
    for currency, detail in factor_details.items():
        if float(detail["remaining_for_direction"]) <= 0:
            reasons.append(f"FX-Faktor-Limit für {currency} ist in dieser Richtung ausgeschöpft.")

    if reasons:
        approved_budget = 0.0
    else:
        approved_budget = min(caps.values())

    sizing = size_trade(spec, side=side, entry=entry, stop=stop, risk_budget=approved_budget) if approved_budget > 0 else {
        "ok": False,
        "reason": reasons[0] if reasons else "Kein Risikobudget innerhalb der aktuellen Limits verfügbar.",
    }

    if approved_budget <= 0 or not sizing.get("ok"):
        status = "BLOCKED"
    elif approved_budget + 1e-9 < requested:
        status = "REDUCED"
    else:
        status = "APPROVED"

    actual_risk = float(sizing.get("actual_risk", 0.0) or 0.0)
    projected_open_risk = state["known_open_stop_risk"] + actual_risk
    projected_cluster_risk = cluster_existing + actual_risk
    projected_instrument_risk = instrument_existing + actual_risk
    projected_all_stops_equity = state["equity"] - projected_open_risk if np.isfinite(state["equity"]) else np.nan
    projected_fx = {
        currency: float(detail["existing_net"]) + int(detail["sign"]) * actual_risk
        for currency, detail in factor_details.items()
    }

    limiting_cap = min(caps, key=caps.get) if caps else "—"
    if status == "REDUCED":
        reasons.append(f"Risiko wurde durch Limit '{limiting_cap}' reduziert.")
    if status == "BLOCKED" and not reasons:
        reasons.append(str(sizing.get("reason", "Kein freigegebenes Risikobudget.")))

    return {
        "status": status,
        "symbol": symbol,
        "instrument": instrument,
        "cluster": cluster,
        "requested_risk": requested,
        "approved_budget": approved_budget,
        "actual_risk": actual_risk,
        "lots": float(sizing.get("lots", 0.0) or 0.0),
        "raw_lots": _finite(sizing.get("raw_lots")),
        "risk_per_lot": _finite(sizing.get("risk_per_lot")),
        "existing_instrument_risk": instrument_existing,
        "projected_instrument_risk": projected_instrument_risk,
        "projected_open_risk": projected_open_risk,
        "projected_cluster_risk": projected_cluster_risk,
        "projected_fx_factor_risk": projected_fx,
        "projected_all_stops_equity": projected_all_stops_equity,
        "reasons": reasons,
        "caps": caps,
        "limiting_cap": limiting_cap,
        "factor_details": factor_details,
        "sizing": sizing,
    }
