from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping
import math
import re

import numpy as np
import pandas as pd

from src.cftc_reports import load_report_history, load_report_universe, primary_report_for_asset_class, resolve_report_market
from src.markets import CLASSIC_MARKETS
from src.prices import load_prices
from src.report_analysis import enrich_report_positioning
from src.seasonality_edge_research import current_phase_day, nearest_turn_context, seasonal_template, stability_table
from src.cot_price_analog import analyze_historical_analogs
from src.fx_relative_cot_analog import FX_PAIRS, analyze_fx_relative_analogs
from src.macro.macro_model_library import evaluate as evaluate_macro
from src.macro_cot_regime import asset_specs, evaluate_cot_positioning, evaluate_macro_cot_regime, load_config as load_macro_cot_config

try:
    from src.cftc_market_resolver import resolve_universe_alias
except Exception:  # pragma: no cover
    resolve_universe_alias = None

try:
    from src.cot_x_seasonality import (
        build_group_flow_map,
        robust_horizon_summary,
        seasonal_edge_context,
        simple_cot_seasonality_turn_read,
        simple_turn_group_selection,
    )
except Exception:  # pragma: no cover
    build_group_flow_map = robust_horizon_summary = seasonal_edge_context = None
    simple_cot_seasonality_turn_read = simple_turn_group_selection = None


# Typed state layer: Data -> Interpretation -> Regime -> Bias -> Opportunity.
@dataclass
class CotPositioningState:
    available: bool; market: str; report_type: str; structural_group: str; structural_bias: str; micro_bias: str
    score: float | None; position_strength: float | None; persistence: float | None
    commercial_net_156w_percentile: float | None; cot_index_26w: float | None
    direction_1w: str; direction_2w: str; direction_4w: str
    long_delta_1w: float | None; short_delta_1w: float | None; long_delta_2w: float | None; short_delta_2w: float | None
    long_delta_4w: float | None; short_delta_4w: float | None; net_delta_1w: float | None; net_delta_2w: float | None; net_delta_4w: float | None
    momentum_context: str; nonreportable_context: str; report_date: str | None; availability_date: str | None
    freshness_days: int | None; freshness_state: str; confidence_state: str; reason: str = ""
    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass
class SeasonalTurnState:
    available: bool; market: str; turn_type: str; distance_days: int | None; robustness: str
    direction_20t: str; direction_40t: str; direction_60t: str; turn_read: str; cot_confirmation: str
    supporters: tuple[str, ...]; conflicts: tuple[str, ...]; reason: str = ""
    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass
class HistoricalAnalogState:
    available: bool; engine: str; outcome_bias: str; similarity: float | None; directional_hit_rate: float | None
    median_forward_return: float | None; sample_size: int; sample_quality: str; horizon_weeks: int
    conclusion: str; top_matches: tuple[dict[str, Any], ...]; reason: str = ""
    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass
class MarketContextState:
    available: bool; business_cycle_state: str; macro_momentum_state: str; volatility_regime_state: str
    risk_conditions_state: str; cross_asset_support_state: str; intermarket_state: str; macro_bias: str; cot_bias: str
    alignment: str; transition_pressure_score: float | None; risk_off_breadth: float | None; risk_on_breadth: float | None; reason: str = ""
    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass
class TradeOpportunityState:
    setup_type: str; trade_type: str; structural_bias: str; conviction: str; preferred_action: str; thesis: str
    supports: tuple[str, ...]; conflicts: tuple[str, ...]; confidence_state: str
    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass
class MacroRegimeState:
    available: bool; business_cycle_state: str; macro_momentum_state: str; cot_regime_state: str; macro_cot_state: str
    transition_pressure_score: float | None; transition_pressure_label: str; risk_off_breadth: float | None; risk_on_breadth: float | None
    risk_off_persistence: float | None; risk_on_persistence: float | None; liquidity_state: str; rates_positioning_state: str
    trading_regime: str; alignment: str; next_regime_direction: str
    transition_confirmation: tuple[dict[str, Any], ...]; opportunity_map: tuple[dict[str, Any], ...]; raw_result: dict[str, Any]; reason: str = ""
    def to_dict(self) -> dict[str, Any]: return asdict(self)


CURRENCY_ALIASES = {
    "EUR": ("EURO FX", "EURO"), "GBP": ("BRITISH POUND", "POUND"), "AUD": ("AUSTRALIAN DOLLAR", "AUSTRALIAN"),
    "NZD": ("NEW ZEALAND DOLLAR", "NEW ZEALAND"), "JPY": ("JAPANESE YEN", "YEN"), "CHF": ("SWISS FRANC", "SWISS"),
    "CAD": ("CANADIAN DOLLAR", "CANADIAN"),
}


def finite(value: Any) -> float | None:
    try: value = float(value)
    except (TypeError, ValueError): return None
    return value if np.isfinite(value) else None


def _slug(value: str) -> str: return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")

def market_names(asset_class: str) -> list[str]: return [str(x["name"]) for x in CLASSIC_MARKETS.get(asset_class, []) if x.get("name")]

def _classic_market(asset_class: str, name: str) -> dict[str, Any] | None:
    return next((dict(x) for x in CLASSIC_MARKETS.get(asset_class, []) if str(x.get("name")) == str(name)), None)


def find_market_by_aliases(asset_class: str, aliases: tuple[str, ...] | list[str]) -> dict[str, Any] | None:
    for alias in aliases:
        a = str(alias).upper()
        for row in CLASSIC_MARKETS.get(asset_class, []):
            n = str(row.get("name", "")).upper()
            if a in n or n in a: return dict(row)
    return None


def load_enriched_cot(asset_class: str, market_name: str) -> tuple[str, pd.DataFrame, dict[str, Any] | None, str]:
    market = _classic_market(asset_class, market_name)
    if market is None: return "", pd.DataFrame(), None, "Markt nicht im Katalog."
    report_type = primary_report_for_asset_class(asset_class)
    try:
        universe = load_report_universe(report_type)
        resolved = resolve_report_market(market, universe)
        if not resolved: return report_type, pd.DataFrame(), None, "CFTC-Markt nicht auflösbar."
        raw = load_report_history(report_type, resolved["cftc_contract_market_code"])
        if raw is None or raw.empty: return report_type, pd.DataFrame(), resolved, "Keine COT-Historie."
        enriched = enrich_report_positioning(raw, report_type=report_type, index_weeks=26, validation_weeks=156)
        return report_type, enriched, resolved, ""
    except Exception as exc:
        return report_type, pd.DataFrame(), None, f"{type(exc).__name__}: {exc}"


def _cot_index_26w(enriched: pd.DataFrame, group: str) -> float | None:
    req = {f"{group}_long", f"{group}_short", "open_interest_all"}
    if enriched.empty or not req.issubset(enriched.columns): return None
    oi = pd.to_numeric(enriched["open_interest_all"], errors="coerce").replace(0, np.nan)
    net = (pd.to_numeric(enriched[f"{group}_long"], errors="coerce") - pd.to_numeric(enriched[f"{group}_short"], errors="coerce")) / oi
    w = net.dropna().tail(26)
    if len(w) < 8: return None
    lo, hi, cur = finite(w.min()), finite(w.max()), finite(w.iloc[-1])
    if lo is None or hi is None or cur is None or math.isclose(lo, hi): return None
    return max(0.0, min(100.0, 100.0 * (cur - lo) / (hi - lo)))


def _micro_bias(cot: Mapping[str, Any]) -> str:
    d1, d2 = str(cot.get("direction_1w", "N/V")).upper(), str(cot.get("direction_2w", "N/V")).upper()
    if d1 == d2 and d1 in {"BULLISH", "BEARISH"}: return d1
    if d2 in {"BULLISH", "BEARISH"}: return f"{d2} · 1W GEMISCHT"
    return "NEUTRAL"


def _empty_cot(market: str, report_type: str, reason: str) -> CotPositioningState:
    return CotPositioningState(False, market, report_type, "N/V", "Insufficient Data", "No Current Signal", None, None, None, None, None,
        "N/V", "N/V", "N/V", None, None, None, None, None, None, None, None, None, "N/V", "N/V", None, None, None,
        "Insufficient Data", "Low Confidence", reason)


def cot_state_for_market(asset_class: str, market_name: str, *, config_path: str = "config/macro_cot_regime.toml") -> CotPositioningState:
    report_type, enriched, _, error = load_enriched_cot(asset_class, market_name)
    if enriched.empty: return _empty_cot(market_name, report_type, error)
    config = load_macro_cot_config(config_path)
    result = evaluate_cot_positioning(enriched, report_type, key=_slug(market_name), label=market_name, config=config)
    availability, freshness_days = result.get("availability_date"), None
    if availability:
        try: freshness_days = (pd.Timestamp.today().normalize() - pd.Timestamp(availability).normalize()).days
        except Exception: pass
    freshness = "Insufficient Data" if freshness_days is None else "AKTUELL" if freshness_days <= 6 else "1 RELEASE ALT" if freshness_days <= 13 else "VERALTET"
    persistence = finite(result.get("persistence"))
    confidence = "High Confidence" if result.get("available") and (persistence or 0) >= .65 else "Medium Confidence" if result.get("available") else "Low Confidence"
    group = str(result.get("structural_group", ""))
    return CotPositioningState(
        bool(result.get("available")), market_name, report_type, str(result.get("structural_group_label", group or "N/V")), str(result.get("state", "Insufficient Data")), _micro_bias(result),
        finite(result.get("score")), finite(result.get("position_strength")), persistence, finite(result.get("net_oi_percentile")), _cot_index_26w(enriched, group),
        str(result.get("direction_1w", "N/V")), str(result.get("direction_2w", "N/V")), str(result.get("direction_4w", "N/V")),
        finite(result.get("long_delta_1w")), finite(result.get("short_delta_1w")), finite(result.get("long_delta_2w")), finite(result.get("short_delta_2w")),
        finite(result.get("long_delta_4w")), finite(result.get("short_delta_4w")), finite(result.get("net_delta_1w")), finite(result.get("net_delta_2w")), finite(result.get("net_delta_4w")),
        str(result.get("momentum_context", "N/V")), str(result.get("nonreportable_context", "N/V")), result.get("report_date"), availability, freshness_days, freshness, confidence,
        str(result.get("reason", error) or error),
    )


def cot_scan_asset_class(asset_class: str) -> list[dict[str, Any]]:
    rows = [cot_state_for_market(asset_class, name).to_dict() for name in market_names(asset_class)]
    return sorted(rows, key=lambda x: (-float(x.get("position_strength") or 0), x.get("market", "")))


def _dir_text(value: Any) -> str:
    try: value = int(value or 0)
    except Exception: value = 0
    return "BULLISH" if value > 0 else "BEARISH" if value < 0 else "NEUTRAL"


def _horizon(stability: pd.DataFrame, horizon: int) -> dict[str, Any]:
    if robust_horizon_summary is not None:
        try: return dict(robust_horizon_summary(stability, horizon) or {})
        except Exception: pass
    if stability.empty or "horizon_days" not in stability: return {"direction": 0, "quality": "N/V"}
    rows = stability[pd.to_numeric(stability["horizon_days"], errors="coerce") == horizon]
    dirs = pd.to_numeric(rows.get("direction"), errors="coerce").dropna()
    if dirs.empty: return {"direction": 0, "quality": "N/V"}
    direction = 1 if (dirs > 0).mean() >= .75 else -1 if (dirs < 0).mean() >= .75 else 0
    return {"direction": direction, "quality": "ROBUST" if direction and len(dirs) >= 3 else "MIXED"}


# ---------------------------------------------------------------------------
# V3.29.4 · STRUCTURAL TURN CONSISTENCY
# The integrated Seasonal Turn uses the SAME structural COT evaluator as the
# visible COT tab. TFF = Asset Manager structural layer; Disaggregated =
# Producer/Merchant structural layer. No change to the underlying engines.
# ---------------------------------------------------------------------------

def _direction_sign(value: Any) -> int:
    if isinstance(value, (int, float, np.integer, np.floating)):
        try:
            numeric = float(value)
        except Exception:
            numeric = 0.0
        if np.isfinite(numeric):
            return 1 if numeric > 0 else -1 if numeric < 0 else 0

    text = str(value or "").strip().upper()
    if "BULL" in text or text in {"LONG", "+1", "1"}:
        return 1
    if "BEAR" in text or "BÄR" in text or text in {"SHORT", "-1"}:
        return -1
    return 0


def _active_turn_target(turn_type: Any, distance_days: Any) -> int:
    try:
        distance = int(round(float(distance_days)))
    except (TypeError, ValueError):
        return 0

    if abs(distance) > 15:
        return 0

    kind = str(turn_type or "").strip().upper()
    if kind == "BOTTOM":
        return 1
    if kind == "TOP":
        return -1
    return 0


def _classify_structural_turn_flow(
    target_direction: int,
    direction_4w: Any,
    direction_2w: Any,
    direction_1w: Any,
) -> str:
    """Classify structural COT flow relative to a seasonal Top/Bottom."""
    target = int(target_direction or 0)
    if target == 0:
        return "KEIN AKTIVER TURN"

    d4 = _direction_sign(direction_4w)
    d2 = _direction_sign(direction_2w)
    d1 = _direction_sign(direction_1w)

    # Full persistence in the expected turn direction.
    if d4 == target and d2 == target and d1 == target:
        return "BESTÄTIGT"

    # Older 4W structure still points the other way, but 2W and 1W have
    # already reversed into the expected turn direction.
    if d4 == -target and d2 == target and d1 == target:
        return "DREHT IN TURN-RICHTUNG"

    # Recent persistent confirmation outweighs a neutral/mixed 4W print.
    if d2 == target and d1 == target:
        return "BESTÄTIGT"

    # Only the latest week is aligned; useful, but too early to call confirmed.
    if d1 == target and d2 != -target:
        return "FRÜHE BESTÄTIGUNG"

    # Persistent flow directly against the seasonal turn.
    if d4 == -target and d2 == -target and d1 == -target:
        return "WIDERSPRICHT"
    if d2 == -target and d1 == -target:
        return "WIDERSPRICHT"
    if d1 == -target:
        return "ZULETZT GEGEN TURN"

    return "GEMISCHT"


def _classify_turn_robustness(
    target_direction: int,
    h40: Mapping[str, Any] | None,
    h60: Mapping[str, Any] | None,
) -> str:
    """Describe robustness RELATIVE to the active seasonal turn direction."""
    target = int(target_direction or 0)
    if target == 0:
        return "KEIN AKTIVER TURN"

    h40 = dict(h40 or {})
    h60 = dict(h60 or {})

    d40 = _direction_sign(h40.get("direction"))
    d60 = _direction_sign(h60.get("direction"))
    q40 = str(h40.get("quality", "") or "").upper()
    q60 = str(h60.get("quality", "") or "").upper()

    robust_dirs = []
    if q40 == "ROBUST" and d40 != 0:
        robust_dirs.append(d40)
    if q60 == "ROBUST" and d60 != 0:
        robust_dirs.append(d60)

    if len(robust_dirs) == 2 and all(d == target for d in robust_dirs):
        return "ROBUST"
    if robust_dirs and all(d == target for d in robust_dirs):
        return "UNTERSTÜTZT"
    if robust_dirs and all(d == -target for d in robust_dirs):
        return "WIDERSPRICHT"
    return "GEMISCHT"


def _structural_turn_read(
    enriched: pd.DataFrame | None,
    report_type: str,
    market_name: str,
    turn_type: Any,
    distance_days: Any,
    *,
    config_path: str = "config/macro_cot_regime.toml",
) -> dict[str, Any]:
    target = _active_turn_target(turn_type, distance_days)
    base = {
        "available": False,
        "target_direction": target,
        "state": "KEIN AKTIVER TURN" if target == 0 else "Insufficient Data",
        "structural_group": "",
        "structural_group_label": "N/V",
        "direction_4w": "N/V",
        "direction_2w": "N/V",
        "direction_1w": "N/V",
        "reason": "",
    }

    if target == 0:
        return base
    if enriched is None or enriched.empty or not report_type:
        return {**base, "reason": "Keine strukturellen COT-Daten verfügbar."}

    try:
        config = load_macro_cot_config(config_path)
        result = evaluate_cot_positioning(
            enriched,
            report_type,
            key=_slug(market_name),
            label=market_name,
            config=config,
        )
    except Exception as exc:
        return {
            **base,
            "reason": f"{type(exc).__name__}: {exc}",
        }

    if not result.get("available"):
        return {
            **base,
            "structural_group": str(result.get("structural_group", "") or ""),
            "structural_group_label": str(
                result.get("structural_group_label", "N/V") or "N/V"
            ),
            "reason": str(result.get("reason", "") or ""),
        }

    d4 = result.get("direction_4w", "N/V")
    d2 = result.get("direction_2w", "N/V")
    d1 = result.get("direction_1w", "N/V")
    state = _classify_structural_turn_flow(target, d4, d2, d1)

    return {
        "available": True,
        "target_direction": target,
        "state": state,
        "structural_group": str(result.get("structural_group", "") or ""),
        "structural_group_label": str(
            result.get("structural_group_label", "N/V") or "N/V"
        ),
        "direction_4w": str(d4),
        "direction_2w": str(d2),
        "direction_1w": str(d1),
        "reason": str(result.get("reason", "") or ""),
    }


def _integrated_turn_read_label(
    turn_type: Any,
    target_direction: int,
    robustness: str,
    cot_confirmation: str,
) -> str:
    target = int(target_direction or 0)
    kind = str(turn_type or "TURN").upper()

    if target == 0:
        return "KEIN AKTIVER SAISONALER TURN"

    direction_word = "BULLISH" if target > 0 else "BEARISH"
    turn_word = "BOTTOM" if target > 0 else "TOP"
    robust = str(robustness or "").upper()
    cot = str(cot_confirmation or "").upper()

    if robust == "WIDERSPRICHT":
        return f"{direction_word} {turn_word} · SAISON-ROBUSTHEIT WIDERSPRICHT"

    if cot == "WIDERSPRICHT":
        return f"{direction_word} {turn_word} · COT WIDERSPRICHT"

    if cot == "ZULETZT GEGEN TURN":
        return f"{direction_word} {turn_word} · COT ZULETZT GEGEN TURN"

    if cot == "DREHT IN TURN-RICHTUNG":
        return f"EARLY {direction_word} {turn_word} TRANSITION"

    if cot == "FRÜHE BESTÄTIGUNG":
        return f"{direction_word} {turn_word} · FRÜHE COT-BESTÄTIGUNG"

    if cot == "BESTÄTIGT":
        if robust == "ROBUST":
            return f"{direction_word} {turn_word} EVIDENCE · STRONG"
        if robust == "UNTERSTÜTZT":
            return f"{direction_word} {turn_word} EVIDENCE · MODERATE"
        return f"{direction_word} {turn_word} · COT BESTÄTIGT / SAISON GEMISCHT"

    if cot == "INSUFFICIENT DATA":
        return f"{direction_word} {turn_word} · COT-DATEN NICHT AUSREICHEND"

    return f"{direction_word} {turn_word} · COT NOCH NICHT BESTÄTIGT"

def seasonal_state_for_prices(
    prices: pd.DataFrame,
    *,
    market_name: str,
    enriched: pd.DataFrame | None = None,
    report_type: str = "",
) -> SeasonalTurnState:
    if prices is None or prices.empty:
        return SeasonalTurnState(
            False,
            market_name,
            "Insufficient Data",
            None,
            "Insufficient Data",
            "N/V",
            "N/V",
            "N/V",
            "No Current Signal",
            "Insufficient Data",
            (),
            (),
            "Keine Preisreihe.",
        )

    try:
        template = seasonal_template(prices, years=20)
        phase = current_phase_day(prices)
        turn = nearest_turn_context(template, phase)
        stability = stability_table(prices)
    except Exception as exc:
        return SeasonalTurnState(
            False,
            market_name,
            "Insufficient Data",
            None,
            "Insufficient Data",
            "N/V",
            "N/V",
            "N/V",
            "No Current Signal",
            "Insufficient Data",
            (),
            (),
            f"{type(exc).__name__}: {exc}",
        )

    h20 = _horizon(stability, 20)
    h40 = _horizon(stability, 40)
    h60 = _horizon(stability, 60)

    turn_type = str(
        (turn or {}).get("turn_type", "N/V") or "N/V"
    ).upper()

    try:
        distance = int(
            round(
                float(
                    (turn or {}).get("distance_days")
                )
            )
        )
    except Exception:
        distance = None

    target = _active_turn_target(
        turn_type,
        distance,
    )

    robustness = _classify_turn_robustness(
        target,
        h40,
        h60,
    )

    structural = _structural_turn_read(
        enriched,
        report_type,
        market_name,
        turn_type,
        distance,
    )

    cot_confirm = str(
        structural.get(
            "state",
            "Insufficient Data",
        )
        or "Insufficient Data"
    )

    turn_read = _integrated_turn_read_label(
        turn_type,
        target,
        robustness,
        cot_confirm,
    )

    supporters = []
    conflicts = []

    if robustness in {
        "ROBUST",
        "UNTERSTÜTZT",
    }:
        supporters.append(
            "Saisonale 40T/60T-Robustheit"
        )
    elif robustness == "WIDERSPRICHT":
        conflicts.append(
            "Saisonale 40T/60T-Robustheit"
        )

    structural_label = str(
        structural.get(
            "structural_group_label",
            "Struktureller COT-Flow",
        )
        or "Struktureller COT-Flow"
    )

    if cot_confirm in {
        "BESTÄTIGT",
        "DREHT IN TURN-RICHTUNG",
        "FRÜHE BESTÄTIGUNG",
    }:
        supporters.append(
            f"Struktureller COT-Flow ({structural_label})"
        )
    elif cot_confirm in {
        "WIDERSPRICHT",
        "ZULETZT GEGEN TURN",
    }:
        conflicts.append(
            f"Struktureller COT-Flow ({structural_label})"
        )

    return SeasonalTurnState(
        True,
        market_name,
        turn_type,
        distance,
        robustness,
        _dir_text(h20.get("direction")),
        _dir_text(h40.get("direction")),
        _dir_text(h60.get("direction")),
        turn_read,
        cot_confirm,
        tuple(supporters),
        tuple(conflicts),
        str(structural.get("reason", "") or ""),
    )


def seasonal_state_for_market(asset_class: str, market_name: str) -> SeasonalTurnState:
    market = _classic_market(asset_class, market_name)
    if not market: return SeasonalTurnState(False, market_name, "Insufficient Data", None, "Insufficient Data", "N/V", "N/V", "N/V", "No Current Signal", "Insufficient Data", (), (), "Markt nicht gefunden.")
    prices = load_prices(market["ticker"], start=pd.Timestamp.today().normalize() - pd.DateOffset(years=35))
    report_type, enriched, _, _ = load_enriched_cot(asset_class, market_name)
    return seasonal_state_for_prices(prices, market_name=market_name, enriched=enriched, report_type=report_type)


def seasonality_scan_asset_class(asset_class: str) -> list[dict[str, Any]]:
    rows = [seasonal_state_for_market(asset_class, name).to_dict() for name in market_names(asset_class)]
    return sorted(rows, key=lambda x: (abs(int(x.get("distance_days") if x.get("distance_days") is not None else 9999)), 0 if x.get("robustness") == "ROBUST" else 1))


def _analog_state(result: Mapping[str, Any], engine: str, horizon: int) -> HistoricalAnalogState:
    if not result.get("available"): return HistoricalAnalogState(False, engine, "No Current Signal", None, None, None, 0, "Insufficient Data", horizon, "Keine ausreichend ähnlichen historischen Setups.", (), str(result.get("reason", "")))
    agg, matches = dict(result.get("aggregate", {}) or {}), pd.DataFrame(result.get("matches"))
    hit, med = finite(agg.get(f"positive_rate_{horizon}w", agg.get("positive_rate"))), finite(agg.get(f"median_return_{horizon}w", agg.get("median_return")))
    bias, quality = str(agg.get("outcome_bias", "MIXED")), str(agg.get("sample_quality", "N/V"))
    conclusion = f"Historische Analogs: {bias} · Richtungsquote {hit:.0%} · {quality}." if hit is not None else "Historische Analogs liefern kein eindeutiges Richtungsbild."
    top = []
    for _, row in matches.head(5).iterrows():
        d = row.get("availability_date", row.get("report_date")); top.append({"Datum": str(pd.Timestamp(d).date()) if d is not None else "—", "Ähnlichkeit": finite(row.get("similarity")), f"{horizon}W": finite(row.get(f"return_{horizon}w"))})
    return HistoricalAnalogState(True, engine, bias, finite(agg.get("median_similarity")), hit, med, int(agg.get("matches", len(matches)) or 0), quality, horizon, conclusion, tuple(top), "")


def historical_analog_for_market(asset_class: str, market_name: str, *, top_n: int = 8, horizon_weeks: int = 8) -> HistoricalAnalogState:
    market = _classic_market(asset_class, market_name); report_type, enriched, _, error = load_enriched_cot(asset_class, market_name)
    if not market or enriched.empty: return HistoricalAnalogState(False, "COT × Preis-Analog", "Insufficient Data", None, None, None, 0, "Insufficient Data", horizon_weeks, "Keine Analyse verfügbar.", (), error)
    prices = load_prices(market["ticker"], start=pd.Timestamp.today().normalize() - pd.DateOffset(years=35))
    try: result = analyze_historical_analogs(prices, enriched, report_type, top_n=top_n, min_spacing_weeks=13, exclude_recent_weeks=26, excursion_horizon_weeks=horizon_weeks)
    except Exception as exc: result = {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    return _analog_state(result, "COT × Preis-Analog", horizon_weeks)


def find_currency_market(currency: str) -> dict[str, Any] | None: return find_market_by_aliases("Currencies", CURRENCY_ALIASES.get(currency.upper(), (currency.upper(),)))


def currency_cot_state(currency: str) -> CotPositioningState:
    currency = currency.upper()
    if currency == "USD":
        state = _empty_cot("USD", "relative basis", "USD ist nur relative Null-Basis, kein synthetischer COT-Report.")
        state.available = True; state.structural_group = "Relative Basis"; state.structural_bias = state.micro_bias = "NEUTRAL"; state.score = 0.0; state.position_strength = 0.0; state.freshness_state = "RELATIVE BASIS"; state.confidence_state = "Derived"
        return state
    market = find_currency_market(currency)
    if not market: return _empty_cot(currency, "tff", "Kein Currency-Future gefunden.")
    state = cot_state_for_market("Currencies", str(market["name"])); state.market = currency; return state


def currency_strength_snapshot() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    currencies = sorted({str(v.get("base")) for v in FX_PAIRS.values()} | {str(v.get("quote")) for v in FX_PAIRS.values()})
    states = {c: currency_cot_state(c) for c in currencies}
    ranking = sorted([{"Währung": c, "Relative COT-Stärke": finite(s.score), "Struktureller Bias": s.structural_bias, "Mikro-Bias": s.micro_bias, "Persistenz": s.persistence, "Datenstatus": s.freshness_state} for c, s in states.items()], key=lambda x: -float(x.get("Relative COT-Stärke") or 0))
    pairs = []
    for pair, spec in FX_PAIRS.items():
        b, q = str(spec.get("base")), str(spec.get("quote")); bs, qs = finite(states[b].score), finite(states[q].score); diff = bs - qs if bs is not None and qs is not None else None
        if diff is None: bias, alignment = "No Current Signal", "Insufficient Data"
        elif diff >= 25: bias, alignment = f"{b} stärker als {q}", "FAVOR"
        elif diff <= -25: bias, alignment = f"{q} stärker als {b}", "FAVOR"
        elif abs(diff) >= 12: bias, alignment = (f"{b} leicht stärker" if diff > 0 else f"{q} leicht stärker"), "WATCH"
        else: bias, alignment = "Kein klarer relativer Vorteil", "NEUTRAL"
        pairs.append({"Pair": pair, "Base": b, "Quote": q, "Stärke-Differenz": diff, "Pair Bias": bias, "Alignment": alignment})
    return ranking, sorted(pairs, key=lambda x: -abs(float(x.get("Stärke-Differenz") or 0)))


def _currency_enriched(currency: str) -> pd.DataFrame:
    if currency.upper() == "USD": return pd.DataFrame()
    market = find_currency_market(currency)
    if not market: return pd.DataFrame()
    return load_enriched_cot("Currencies", str(market["name"]))[1]


def historical_analog_for_fx(pair: str, *, top_n: int = 8, horizon_weeks: int = 8) -> HistoricalAnalogState:
    spec = FX_PAIRS.get(pair.upper())
    if not spec: return HistoricalAnalogState(False, "FX-COT-Analog", "Insufficient Data", None, None, None, 0, "Insufficient Data", horizon_weeks, "Keine Analyse verfügbar.", (), "FX-Paar nicht unterstützt.")
    prices = load_prices(spec["ticker"], start=pd.Timestamp.today().normalize() - pd.DateOffset(years=35)); base, quote = str(spec["base"]), str(spec["quote"])
    bc, qc = _currency_enriched(base), _currency_enriched(quote)
    if prices is None or prices.empty or (base != "USD" and bc.empty) or (quote != "USD" and qc.empty): return HistoricalAnalogState(False, "FX-COT-Analog", "Insufficient Data", None, None, None, 0, "Insufficient Data", horizon_weeks, "Keine Analyse verfügbar.", (), "Preis- oder COT-Historie fehlt.")
    try: result = analyze_fx_relative_analogs(prices, pair=pair.upper(), base_cot=bc, quote_cot=qc, top_n=top_n, min_spacing_weeks=13, exclude_recent_weeks=26, outcome_horizon_weeks=horizon_weeks)
    except Exception as exc: result = {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    return _analog_state(result, "FX-COT-Analog", horizon_weeks)


def seasonal_state_for_fx(pair: str) -> SeasonalTurnState:
    spec = FX_PAIRS.get(pair.upper())
    if not spec: return SeasonalTurnState(False, pair, "Insufficient Data", None, "Insufficient Data", "N/V", "N/V", "N/V", "No Current Signal", "Insufficient Data", (), (), "FX-Paar nicht unterstützt.")
    prices = load_prices(spec["ticker"], start=pd.Timestamp.today().normalize() - pd.DateOffset(years=35))
    return seasonal_state_for_prices(prices, market_name=pair.upper())


def fx_relative_cot_summary(pair: str) -> dict[str, Any]:
    spec = FX_PAIRS.get(pair.upper())
    if not spec: return {"available": False, "pair": pair, "bias": "Insufficient Data", "base": {}, "quote": {}, "differential": None}
    base, quote = currency_cot_state(str(spec["base"])), currency_cot_state(str(spec["quote"])); bs, qs = finite(base.score), finite(quote.score); diff = bs - qs if bs is not None and qs is not None else None
    bias = "Insufficient Data" if diff is None else f"BULLISH {pair}" if diff >= 18 else f"BEARISH {pair}" if diff <= -18 else "NEUTRAL"
    return {"available": diff is not None, "pair": pair.upper(), "bias": bias, "base": base.to_dict(), "quote": quote.to_dict(), "differential": diff}


def _load_cot_by_spec(spec: Any, config: dict[str, Any]) -> dict[str, Any]:
    asset_class, aliases = str(getattr(spec, "asset_class", "")), tuple(getattr(spec, "aliases", ()) or ()); market = find_market_by_aliases(asset_class, aliases); report_type = primary_report_for_asset_class(asset_class)
    try: universe = load_report_universe(report_type)
    except Exception: universe = None
    resolved = None
    if market is not None and universe is not None:
        try: resolved = resolve_report_market(market, universe)
        except Exception: pass
    if not resolved and resolve_universe_alias is not None and universe is not None:
        try: resolved = resolve_universe_alias(universe, aliases)
        except Exception: pass
    enriched = pd.DataFrame()
    if resolved:
        try:
            raw = load_report_history(report_type, resolved["cftc_contract_market_code"])
            if raw is not None and not raw.empty: enriched = enrich_report_positioning(raw, report_type=report_type, index_weeks=26, validation_weeks=156)
        except Exception: pass
    return evaluate_cot_positioning(enriched, report_type, key=str(getattr(spec, "key", _slug(str(getattr(spec, "label", "asset"))))), label=str(getattr(spec, "label", "N/V")), config=config)


def macro_regime_snapshot(*, force_refresh: bool = False) -> MacroRegimeState:
    try:
        macro_result = evaluate_macro(config_path="config/macro_model_library.toml", force_refresh=force_refresh); config = load_macro_cot_config("config/macro_cot_regime.toml")
        cot_states = {spec.key: _load_cot_by_spec(spec, config) for spec in asset_specs(config)}
        result = evaluate_macro_cot_regime(macro_result=macro_result, cot_states=cot_states, config=config)
    except Exception as exc:
        return MacroRegimeState(False, "Insufficient Data", "Insufficient Data", "Insufficient Data", "Insufficient Data", None, "Insufficient Data", None, None, None, None, "Insufficient Data", "Insufficient Data", "No Current Signal", "Insufficient Data", "Insufficient Data", (), (), {}, f"{type(exc).__name__}: {exc}")
    macro, cross, combined, rates = (dict(result.get(k, {}) or {}) for k in ("macro", "cross_asset", "combined", "rates_positioning"))
    pressure = finite(combined.get("transition_pressure", combined.get("transition_pressure_score")))
    pressure_label = str(combined.get("transition_pressure_label", "HOCH" if pressure is not None and pressure >= 65 else "ERHÖHT" if pressure is not None and pressure >= 40 else "NIEDRIG" if pressure is not None else "Insufficient Data"))
    return MacroRegimeState(True, str(macro.get("business_cycle_state", "Insufficient Data")), str(macro.get("macro_momentum_state", "Insufficient Data")), str(cross.get("regime", cross.get("state", cross.get("label", "Insufficient Data")))), str(combined.get("transition_state", combined.get("state", combined.get("regime_state", "Insufficient Data")))), pressure, pressure_label,
        finite(cross.get("risk_off_breadth")), finite(cross.get("risk_on_breadth")), finite(cross.get("risk_off_persistence")), finite(cross.get("risk_on_persistence")), str(macro.get("liquidity_state", "Insufficient Data")), str(rates.get("state", "Insufficient Data")), str(combined.get("trading_regime", combined.get("bias", "No Current Signal"))), str(combined.get("alignment_state", combined.get("alignment", "Insufficient Data"))), str(combined.get("target_transition_direction", "Insufficient Data")),
        tuple(dict(x) for x in result.get("transition_confirmation", [])), tuple(dict(x) for x in result.get("opportunity_map", [])), {"macro_result": macro_result, "macro_cot": result}, "")


def volatility_regime(prices: pd.DataFrame) -> str:
    if prices is None or prices.empty: return "Insufficient Data"
    col = next((x for x in ("close", "Close", "adj_close", "Adj Close") if x in prices), None)
    if col is None: return "Insufficient Data"
    close = pd.to_numeric(prices[col], errors="coerce").dropna(); hist = (close.pct_change().rolling(20).std() * np.sqrt(252)).dropna().tail(756)
    if len(hist) < 40: return "Low Confidence"
    pct = float((hist <= hist.iloc[-1]).mean())
    return "HOCH" if pct >= .85 else "ERHÖHT" if pct >= .65 else "NIEDRIG" if pct <= .20 else "NORMAL"


def _opportunity_row(state: MacroRegimeState, market_name: str) -> dict[str, Any] | None:
    target = market_name.upper()
    for row in state.opportunity_map:
        label = str(row.get("market", row.get("label", ""))).upper()
        if label and (label in target or target in label): return dict(row)
    return None


def _context(state: MacroRegimeState, prices: pd.DataFrame, row: dict[str, Any] | None) -> MarketContextState:
    ro, rn = finite(state.risk_off_breadth), finite(state.risk_on_breadth); risk = "DEFENSIV" if ro is not None and ro >= .55 else "RISK-ON" if rn is not None and rn >= .55 else "GEMISCHT"
    if row:
        align = str(row.get("alignment", "N/V")); inter = "CONFLICT" if "CONFLICT" in align.upper() else "SUPPORT" if "ALIGN" in align.upper() or row.get("preference") == "FAVOR" else "NEUTRAL"
        support, macro_bias, cot_bias = str(row.get("preference", align)), str(row.get("macro_bias", "N/V")), str(row.get("cot_bias", "N/V"))
    else: align, inter, support, macro_bias, cot_bias = "No Current Signal", risk, "MIXED" if risk == "GEMISCHT" else risk, "No Current Signal", "No Current Signal"
    return MarketContextState(state.available, state.business_cycle_state, state.macro_momentum_state, volatility_regime(prices), risk, support, inter, macro_bias, cot_bias, align, state.transition_pressure_score, ro, rn, state.reason)


def market_context_for_classic(asset_class: str, market_name: str, *, macro_state: MacroRegimeState | None = None) -> MarketContextState:
    state = macro_state or macro_regime_snapshot(); market = _classic_market(asset_class, market_name)
    try: prices = load_prices(market["ticker"], start=pd.Timestamp.today().normalize() - pd.DateOffset(years=4)) if market else pd.DataFrame()
    except Exception: prices = pd.DataFrame()
    return _context(state, prices, _opportunity_row(state, market_name))


def market_context_for_fx(pair: str, *, macro_state: MacroRegimeState | None = None) -> MarketContextState:
    state = macro_state or macro_regime_snapshot(); spec = FX_PAIRS.get(pair.upper())
    try: prices = load_prices(spec["ticker"], start=pd.Timestamp.today().normalize() - pd.DateOffset(years=4)) if spec else pd.DataFrame()
    except Exception: prices = pd.DataFrame()
    return _context(state, prices, None)


def _direction(text: str) -> int:
    t = str(text).upper(); return 1 if "BULLISH" in t else -1 if "BEARISH" in t else 0


def derive_trade_opportunity(cot: CotPositioningState, seasonal: SeasonalTurnState, context: MarketContextState) -> TradeOpportunityState:
    if not cot.available: return TradeOpportunityState("NO EDGE", "NO EDGE", "No Current Signal", "NIEDRIG", "WARTEN", "COT-Struktur ist nicht ausreichend belastbar.", (), (), "Low Confidence")
    cd, d1, d2, d4 = _direction(cot.structural_bias), _direction(cot.direction_1w), _direction(cot.direction_2w), _direction(cot.direction_4w)
    transition = d2 if d2 and d1 == d2 and d4 == -d2 else 0
    sd = 1 if seasonal.turn_type == "BOTTOM" and seasonal.robustness in {"ROBUST", "UNTERSTÜTZT"} else -1 if seasonal.turn_type == "TOP" and seasonal.robustness in {"ROBUST", "UNTERSTÜTZT"} else _direction(seasonal.direction_40t) if seasonal.direction_40t == seasonal.direction_60t else 0
    supports, conflicts = [], []
    if (cot.persistence or 0) >= .65: supports.append("2W/4W COT-Persistenz")
    target = transition or cd
    if sd and sd == target: supports.append("Saisonales Wendefenster")
    elif sd and target and sd != target: conflicts.append("Seasonality")
    if "CONFLICT" in context.alignment.upper(): conflicts.append("Makro / Cross-Asset")
    elif "ALIGN" in context.alignment.upper() or "FAVOR" in context.cross_asset_support_state.upper(): supports.append("Makro / Cross-Asset")
    if transition:
        bias = "BULLISH" if transition > 0 else "BEARISH"; setup = "PEAK REVERSAL" if seasonal.turn_type == "TOP" and transition < 0 else "TROUGH REVERSAL" if seasonal.turn_type == "BOTTOM" and transition > 0 else "EARLY TRANSITION"; trade = "TRANSITION TRADE"; action = "BEOBACHTEN" if conflicts else "AUF TECHNISCHE BESTÄTIGUNG WARTEN"; thesis = f"2W/1W-COT drehen {bias.lower()}, während 4W noch das alte Regime trägt."
    elif cd and conflicts:
        bias = "BULLISH" if cd > 0 else "BEARISH"; setup = "MACRO-COT DIVERGENCE"; trade = "TRANSITION TRADE"; action = "BEOBACHTEN"; thesis = "COT ist gerichtet, Makro/Seasonality bestätigt den Bias noch nicht vollständig."
    elif cd and sd == cd and not conflicts:
        bias = "BULLISH" if cd > 0 else "BEARISH"; setup = "CONFIRMED TREND"; trade = "ALIGNMENT TRADE"; action = "FAVOR"; thesis = "Strukturelles COT und robuste saisonale Richtung zeigen gemeinsam."
    elif cd:
        bias = "BULLISH" if cd > 0 else "BEARISH"; setup = "NO EDGE"; trade = "NO EDGE"; action = "WATCH"; thesis = "COT ist gerichtet, aber weitere Bestätigung fehlt."
    else:
        bias, setup, trade, action, thesis = "NEUTRAL", "NO EDGE", "NO EDGE", "WARTEN", "Keine klare strukturelle Richtung."
    high = (cot.persistence or 0) >= .70 and len(supports) >= 2 and not conflicts; medium = (cot.position_strength or 0) >= 40
    return TradeOpportunityState(setup, trade, bias, "HOCH" if high else "MITTEL" if medium else "NIEDRIG", action, thesis, tuple(supports), tuple(conflicts), "High Confidence" if high else "Medium Confidence" if medium else "Low Confidence")
