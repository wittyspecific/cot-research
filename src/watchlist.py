
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from .analysis import (
    classify_positioning_bias,
    commercial_range_state,
    enrich_cot,
    hedger_cycle_state,
    net_validation,
    positioning_velocity_state,
)
from .cftc import load_cftc_universe, load_history, resolve_market
from .markets import CLASSIC_MARKETS
from .config import (
    COMMERCIAL_RANGE_WEEKS,
    COT_INDEX_WEEKS,
    INDEX_LOWER,
    INDEX_UPPER,
    NET_LOWER_PERCENTILE,
    NET_UPPER_PERCENTILE,
    NET_VALIDATION_WEEKS,
    RELEASE_ACTIVE_WEEKS,
)


COMMODITY_CLASSES = {
    "Energy",
    "Metals",
    "Grains",
    "Livestock",
    "Soft Commodities",
    "Forest Products",
}

FINANCIAL_CLASSES = {
    "Currencies",
    "Cryptocurrencies",
    "Rates",
    "Volatility",
    "Indices",
}

# Only group complexes where the economic overlap is obvious enough that
# counting every line as an independent idea would be misleading.
THEME_BY_SYMBOL = {
    # Agricultural complexes
    "ZS": "Sojakomplex",
    "ZM": "Sojakomplex",
    "ZL": "Sojakomplex",
    "ZC": "Getreide",
    "ZW": "Getreide",
    "KE": "Getreide",
    "MWE": "Getreide",
    "ZR": "Getreide",
    "RS": "Ölsaaten",

    # Energy
    "CL": "Rohölkomplex",
    "BZ": "Rohölkomplex",
    "RB": "Rohölkomplex",
    "HO": "Rohölkomplex",

    # Metals
    "GC": "Edelmetalle",
    "SI": "Edelmetalle",

    # Livestock
    "LE": "Rindfleisch",
    "GF": "Rindfleisch",

    # Financial factors
    "ES": "Aktienindizes",
    "NQ": "Aktienindizes",
    "YM": "Aktienindizes",
    "RTY": "Aktienindizes",

    "EUR": "USD-Währungsfaktor",
    "GBP": "USD-Währungsfaktor",
    "JPY": "USD-Währungsfaktor",
    "CHF": "USD-Währungsfaktor",
    "CAD": "USD-Währungsfaktor",
    "AUD": "USD-Währungsfaktor",
    "NZD": "USD-Währungsfaktor",
    "MXN": "USD-Währungsfaktor",
    "USD": "USD-Währungsfaktor",
    "BRL": "USD-Währungsfaktor",
    "ZAR": "USD-Währungsfaktor",

    "BTC": "Krypto",
    "ETH": "Krypto",
    "LBR": "Holz",
    "ZT": "US-Zinskurve",
    "ZF": "US-Zinskurve",
    "ZN": "US-Zinskurve",
    "ZB": "US-Zinskurve",
    "UB": "US-Zinskurve",
    "VIX": "Volatilität",
}


def _direction_label(direction: int) -> str:
    if direction > 0:
        return "BULLISH"
    if direction < 0:
        return "BEARISH"
    return "NEUTRAL"


def _segment(asset_class: str) -> str:
    if asset_class in COMMODITY_CLASSES:
        return "ROHSTOFFE"
    if asset_class in FINANCIAL_CLASSES:
        return "FINANZWERTE"
    return "SONSTIGE"


def _theme(market: dict) -> str:
    return THEME_BY_SYMBOL.get(market["symbol"], market["name"])


def _expected_range_state(direction: int) -> str | None:
    if direction > 0:
        return "AT / NEAR RANGE HIGH"
    if direction < 0:
        return "AT / NEAR RANGE LOW"
    return None


def _validation_failure_reasons(
    row: pd.Series,
    direction: int,
    validation_upper: float,
    validation_lower: float,
) -> list[str]:
    comm = float(row.get("commercial_net_percentile", np.nan))
    retail = float(row.get("retail_net_percentile", np.nan))
    reasons = []

    if direction > 0:
        if not np.isfinite(comm) or comm < validation_upper:
            reasons.append(
                f"Commercial-Netto {comm:.1f} < {validation_upper:.0f}"
                if np.isfinite(comm)
                else "Commercial-Netto n/v"
            )
        if not np.isfinite(retail) or retail > validation_lower:
            reasons.append(
                f"Retail-Netto {retail:.1f} > {validation_lower:.0f}"
                if np.isfinite(retail)
                else "Retail-Netto n/v"
            )
    elif direction < 0:
        if not np.isfinite(comm) or comm > validation_lower:
            reasons.append(
                f"Commercial-Netto {comm:.1f} > {validation_lower:.0f}"
                if np.isfinite(comm)
                else "Commercial-Netto n/v"
            )
        if not np.isfinite(retail) or retail < validation_upper:
            reasons.append(
                f"Retail-Netto {retail:.1f} < {validation_upper:.0f}"
                if np.isfinite(retail)
                else "Retail-Netto n/v"
            )
    else:
        reasons.append("keine aktive Zyklusrichtung")

    return reasons


def _range_failure_reason(
    range_state: dict,
    direction: int,
) -> str:
    expected = _expected_range_state(direction)
    state = str(range_state.get("state", "NO RANGE DATA"))
    distance = range_state.get("distance_pct", np.nan)

    if expected is None:
        return "keine aktive Zyklusrichtung"

    side = "Hoch" if direction > 0 else "Tief"
    if np.isfinite(distance):
        return f"{state} · {distance:.1f}% vom nächsten Range-{side}"
    return state


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def scan_classic_markets(
    cot_weeks: int = COT_INDEX_WEEKS,
    validation_weeks: int = NET_VALIDATION_WEEKS,
    range_weeks: int = COMMERCIAL_RANGE_WEEKS,
    upper: float = INDEX_UPPER,
    lower: float = INDEX_LOWER,
    validation_upper: float = NET_UPPER_PERCENTILE,
    validation_lower: float = NET_LOWER_PERCENTILE,
    release_active_weeks: int = RELEASE_ACTIVE_WEEKS,
) -> dict:
    """
    Scan the complete classic COT universe using CFTC data only.

    The primary candidate list is intentionally condition-based rather than
    ranked. A market qualifies only when all three gates are true:

    1) Hedger cycle phase is EXTREME or RELEASE
    2) Commercial + Retail net percentiles confirm the cycle direction
    3) Commercial net is at/near the directionally correct range extreme

    No prices are loaded here. NC divergence and seasonality remain detail-view
    calculations.
    """
    universe = load_cftc_universe()
    total = sum(len(markets) for markets in CLASSIC_MARKETS.values())

    all_rows = []
    change_rows = []
    errors = []

    for asset_class, markets in CLASSIC_MARKETS.items():
        for market in markets:
            try:
                resolved = resolve_market(market, universe)
                if not resolved:
                    raise ValueError("Keine eindeutige CFTC-Serie aufgelöst")

                code = str(resolved["cftc_contract_market_code"])
                raw = load_history(code)
                if raw.empty:
                    raise ValueError("Keine COT-Historie")

                cot = enrich_cot(
                    raw,
                    weeks=int(cot_weeks),
                    validation_weeks=int(validation_weeks),
                    range_weeks=int(range_weeks),
                )

                valid = cot.dropna(subset=[
                    "commercial_index",
                    "retail_index",
                    "commercial_net_percentile",
                    "noncommercial_net_percentile",
                    "retail_net_percentile",
                    "commercial_change_4w_percentile",
                ])

                if valid.empty:
                    raise ValueError(
                        "Nicht genügend Historie für die aktuellen Scan-Parameter"
                    )

                latest = valid.iloc[-1]

                cycle = hedger_cycle_state(
                    cot,
                    upper=upper,
                    lower=lower,
                    release_active_weeks=int(release_active_weeks),
                )
                cycle_direction = int(cycle.get("direction", 0) or 0)

                positioning = classify_positioning_bias(
                    latest,
                    upper=upper,
                    lower=lower,
                    validation_upper=validation_upper,
                    validation_lower=validation_lower,
                )

                # During a RELEASE the current COT index is already outside the
                # extreme zone. Validation must therefore follow the direction of
                # the preceding Hedger cycle, not the current index state.
                validation_direction = (
                    cycle_direction
                    if cycle["phase"] in {"EXTREME", "RELEASE"}
                    else int(positioning["direction"])
                )
                validation = net_validation(
                    latest,
                    _direction_label(validation_direction),
                    upper=validation_upper,
                    lower=validation_lower,
                )

                range_state = commercial_range_state(latest)
                velocity = positioning_velocity_state(
                    latest,
                    direction=validation_direction,
                )

                active_cycle = cycle["phase"] in {"EXTREME", "RELEASE"}
                validation_ok = (
                    active_cycle
                    and validation_direction != 0
                    and validation["status"] == "CONFIRMED"
                )
                expected_range = _expected_range_state(validation_direction)
                range_ok = (
                    active_cycle
                    and expected_range is not None
                    and range_state["state"] == expected_range
                )
                qualifies = bool(active_cycle and validation_ok and range_ok)

                failed = []
                if not active_cycle:
                    failed.append("kein aktiver EXTREME-/RELEASE-Zyklus")
                if active_cycle and not validation_ok:
                    failed.extend(
                        _validation_failure_reasons(
                            latest,
                            validation_direction,
                            validation_upper,
                            validation_lower,
                        )
                    )
                if active_cycle and not range_ok:
                    failed.append(
                        "Range: " + _range_failure_reason(
                            range_state,
                            validation_direction,
                        )
                    )

                velocity_pct = float(latest["commercial_change_4w_percentile"])
                change_4w = float(latest["commercial_change_4w"])
                acceleration = float(latest["commercial_acceleration_4w"])

                base = {
                    "segment": _segment(asset_class),
                    "theme": _theme(market),
                    "asset_class": asset_class,
                    "market_name": market["name"],
                    "symbol": market["symbol"],
                    "ticker": market["ticker"],
                    "cftc_code": code,
                    "commodity_name": resolved.get("commodity_name", ""),
                    "official_series": resolved.get("market_and_exchange_names", ""),
                    "report_date": latest["report_date"],

                    "cycle_state": cycle["state"],
                    "cycle_phase": cycle["phase"],
                    "cycle_direction": validation_direction,
                    "extreme_duration": int(cycle.get("extreme_duration", 0) or 0),
                    "weeks_since_release": cycle.get("weeks_since_release", np.nan),
                    "extreme_index": cycle.get("extreme_index", np.nan),
                    "extreme_net": cycle.get("extreme_net", np.nan),

                    "commercial_index": float(latest["commercial_index"]),
                    "retail_index": float(latest["retail_index"]),
                    "commercial_net": float(latest["commercial_net"]),
                    "commercial_net_percentile": float(
                        latest["commercial_net_percentile"]
                    ),
                    "noncommercial_net_percentile": float(
                        latest["noncommercial_net_percentile"]
                    ),
                    "retail_net_percentile": float(
                        latest["retail_net_percentile"]
                    ),
                    "validation_status": validation["status"],

                    "range_state": range_state["state"],
                    "range_distance_pct": float(
                        range_state.get("distance_pct", np.nan)
                    ),
                    "range_expected": expected_range or "—",

                    "commercial_change_4w": change_4w,
                    "commercial_change_4w_percentile": velocity_pct,
                    "commercial_acceleration_4w": acceleration,
                    "velocity_state": velocity["state"],

                    "active_cycle": bool(active_cycle),
                    "validation_ok": bool(validation_ok),
                    "range_ok": bool(range_ok),
                    "qualifies": qualifies,
                    "failed_conditions": " · ".join(failed) if failed else "—",
                }
                all_rows.append(base)

                # Secondary "what changed?" layer retained from V2.7.
                change_category = None
                if (
                    cycle["phase"] == "EXTREME"
                    and int(cycle.get("extreme_duration", 0) or 0) == 1
                ):
                    change_category = "NEU BETRETEN"
                elif cycle["phase"] == "RELEASE":
                    change_category = "RELEASE"
                elif cycle["phase"] not in {"EXTREME", "RELEASE"} and (
                    velocity_pct >= 90.0 or velocity_pct <= 10.0
                ):
                    change_category = "AUFFÄLLIGE GESCHWINDIGKEIT"

                if change_category is not None:
                    changed = dict(base)
                    changed["change_category"] = change_category
                    change_rows.append(changed)

            except Exception as exc:
                errors.append({
                    "asset_class": asset_class,
                    "market_name": market["name"],
                    "symbol": market["symbol"],
                    "error": str(exc),
                })

    all_df = pd.DataFrame(all_rows)
    changes_df = pd.DataFrame(change_rows)
    errors_df = pd.DataFrame(errors)

    if not all_df.empty:
        all_df = all_df.sort_values(
            ["segment", "theme", "market_name", "symbol"]
        ).reset_index(drop=True)

    qualified = (
        all_df[all_df["qualifies"]].copy()
        if not all_df.empty
        else pd.DataFrame()
    )

    # "Near miss" is purely logical: active cycle + exactly one of the two
    # remaining gates succeeds. No distance score and no ranking.
    near_miss = pd.DataFrame()
    rejected_active = pd.DataFrame()

    if not all_df.empty:
        active = all_df[all_df["active_cycle"]].copy()
        if not active.empty:
            gate_count = (
                active["validation_ok"].astype(int)
                + active["range_ok"].astype(int)
            )
            near_miss = active[
                (~active["qualifies"]) & (gate_count == 1)
            ].copy()
            rejected_active = active[
                (~active["qualifies"]) & (gate_count == 0)
            ].copy()

    if not changes_df.empty:
        changes_df = changes_df.sort_values(
            ["change_category", "segment", "theme", "market_name", "symbol"]
        ).reset_index(drop=True)

    latest_report = (
        all_df["report_date"].max()
        if not all_df.empty
        else pd.NaT
    )

    return {
        "qualified": qualified.reset_index(drop=True),
        "near_miss": near_miss.reset_index(drop=True),
        "rejected_active": rejected_active.reset_index(drop=True),
        "changes": changes_df,
        "all_markets": all_df,
        "errors": errors_df,
        "loaded_count": int(len(all_df)),
        "total_count": int(total),
        "latest_report": latest_report,
    }
