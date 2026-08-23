from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.rates_positioning import evaluate_rates_positioning

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


STATE_SEQUENCE = (
    "R1 — CONFIRMED RISK-ON",
    "R2 — EARLY DIVERGENCE",
    "R3 — LATE EXPANSION WARNING",
    "R4 — PEAK WATCH",
    "R5 — CONFIRMED CONTRACTION",
    "R6 — EARLY TROUGH DIVERGENCE",
    "R7 — TROUGH WATCH",
    "R8 — EARLY EXPANSION",
)


@dataclass(frozen=True)
class AssetSpec:
    key: str
    label: str
    asset_class: str
    aliases: tuple[str, ...]
    risk_off_when: str
    weight: float
    opportunity_group: str


@dataclass
class MacroState:
    business_cycle_state: str
    source_cycle_phase: str
    source_transition_state: str
    macro_momentum_state: str
    macro_momentum_score: float | None
    leading_distance: float | None
    leading_slope_13w: float | None
    coincident_distance: float | None
    coincident_slope_13w: float | None
    leading_risk_off_breadth: float | None
    leading_risk_on_breadth: float | None
    financial_market_score: float | None
    liquidity_state: str
    confidence: float
    as_of: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def _clip(value: float, low: float, high: float) -> float:
    return float(np.clip(float(value), low, high))


def _norm(value: float | None, scale: float) -> float | None:
    if value is None:
        return None
    return float(np.tanh(float(value) / max(abs(float(scale)), 1e-9)))


def _weighted(values: dict[str, float | None], weights: dict[str, float]) -> tuple[float | None, float]:
    numer = denom = 0.0
    total = sum(max(0.0, float(w)) for w in weights.values())
    for key, weight in weights.items():
        value = values.get(key)
        if value is None:
            continue
        weight = max(0.0, float(weight))
        numer += float(value) * weight
        denom += weight
    if denom <= 0:
        return None, 0.0
    return numer / denom, (denom / total if total else 0.0)


def load_config(path: str | Path = "config/macro_cot_regime.toml") -> dict[str, Any]:
    if tomllib is None:
        raise RuntimeError("Python 3.11+ / tomllib required")
    with Path(path).open("rb") as fh:
        data = tomllib.load(fh)
    for section, name in (("transition_pressure", "weights"), ("cot", "flow_weights"), ("rates", "contract_weights")):
        weights = data[section][name]
        if not np.isclose(sum(float(v) for v in weights.values()), 1.0, atol=1e-8):
            raise ValueError(f"{section}.{name} must sum to 1.0")
    return data


def asset_specs(config: dict[str, Any]) -> list[AssetSpec]:
    return [
        AssetSpec(
            key=str(key),
            label=str(raw.get("label", key)),
            asset_class=str(raw.get("asset_class", "")),
            aliases=tuple(str(x) for x in raw.get("aliases", [])),
            risk_off_when=str(raw.get("risk_off_when", "ASSET_SPECIFIC")).upper(),
            weight=float(raw.get("weight", 0.0)),
            opportunity_group=str(raw.get("opportunity_group", "OTHER")),
        )
        for key, raw in config.get("assets", {}).items()
    ]


def _rolling_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce").astype(float)
    def rank(values):
        values = np.asarray(values, dtype=float)
        values = values[np.isfinite(values)]
        if len(values) < min_periods:
            return np.nan
        return float(100.0 * np.mean(values <= values[-1]))
    return x.rolling(window, min_periods=min_periods).apply(rank, raw=True)


def _directional_flow(long_delta: float | None, short_delta: float | None, unwind_factor: float) -> float | None:
    if long_delta is None or short_delta is None:
        return None
    active_long = max(long_delta, 0.0)
    long_unwind = max(-long_delta, 0.0)
    active_short = max(short_delta, 0.0)
    short_unwind = max(-short_delta, 0.0)
    return float(active_long + unwind_factor * short_unwind - active_short - unwind_factor * long_unwind)


def _dir(score: float | None, threshold: float) -> str:
    if score is None:
        return "N/V"
    if score > threshold:
        return "BULLISH"
    if score < -threshold:
        return "BEARISH"
    return "NEUTRAL"


def _cot_state(score: float | None, directional: float, very: float) -> str:
    if score is None:
        return "INSUFFICIENT DATA"
    if score >= very:
        return "VERY BULLISH"
    if score >= directional:
        return "BULLISH"
    if score <= -very:
        return "VERY BEARISH"
    if score <= -directional:
        return "BEARISH"
    return "NEUTRAL"


def _context_group(frame: pd.DataFrame, group: str, cfg: dict[str, Any]) -> str:
    cols = (f"{group}_long", f"{group}_short", "open_interest_all")
    if any(c not in frame.columns for c in cols):
        return "N/V"
    oi = pd.to_numeric(frame["open_interest_all"], errors="coerce").replace(0, np.nan)
    net = (pd.to_numeric(frame[cols[0]], errors="coerce") - pd.to_numeric(frame[cols[1]], errors="coerce")) / oi
    pct = _rolling_percentile(net, int(cfg["percentile_window_weeks"]), int(cfg["percentile_min_weeks"]))
    p = _finite(pct.iloc[-1]) if len(pct) else None
    d4 = _finite(net.diff(4).iloc[-1]) if len(net) > 4 else None
    level = "high" if p is not None and p >= 70 else "low" if p is not None and p <= 30 else "mid"
    flow = _dir((_norm(d4, float(cfg["flow_scale_net_oi"])) or 0.0) * 100.0 if d4 is not None else None, 8.0)
    return f"{level} percentile · 4W {flow.lower()}"


def evaluate_cot_positioning(
    enriched_cot: pd.DataFrame,
    report_type: str,
    *,
    key: str,
    label: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    cfg = config["cot"]
    structural = "producer" if report_type == "disaggregated" else "asset_manager"
    structural_label = "Producer / Merchant" if structural == "producer" else "Asset Manager"
    momentum = "managed_money" if report_type == "disaggregated" else "leveraged_funds"
    empty = {
        "key": key, "label": label, "available": False, "report_type": report_type,
        "structural_group": structural, "structural_group_label": structural_label,
        "state": "INSUFFICIENT DATA", "score": None, "position_strength": None,
        "persistence": None, "direction_1w": "N/V", "direction_2w": "N/V", "direction_4w": "N/V",
        "net_oi": None, "net_oi_percentile": None,
        "long_delta_1w": None, "short_delta_1w": None, "long_delta_2w": None, "short_delta_2w": None,
        "long_delta_4w": None, "short_delta_4w": None, "net_delta_1w": None, "net_delta_2w": None, "net_delta_4w": None,
        "active_build_share": None, "momentum_context": "N/V", "nonreportable_context": "N/V",
        "report_date": None, "availability_date": None, "reason": "Keine ausreichende COT-Historie.",
    }
    if enriched_cot is None or enriched_cot.empty or "report_date" not in enriched_cot.columns:
        return empty
    frame = enriched_cot.copy()
    frame["report_date"] = pd.to_datetime(frame["report_date"], errors="coerce")
    frame = frame.dropna(subset=["report_date"]).sort_values("report_date").reset_index(drop=True)
    long_col, short_col = f"{structural}_long", f"{structural}_short"
    if any(c not in frame.columns for c in (long_col, short_col, "open_interest_all")):
        empty["reason"] = "Erforderliche COT-Gruppenspalten fehlen."
        return empty
    if len(frame) < int(cfg["min_history_weeks"]):
        empty["reason"] = f"Nur {len(frame)} Wochen COT-Historie."
        return empty
    oi = pd.to_numeric(frame["open_interest_all"], errors="coerce").replace(0, np.nan)
    long_oi = pd.to_numeric(frame[long_col], errors="coerce") / oi
    short_oi = pd.to_numeric(frame[short_col], errors="coerce") / oi
    net_oi = long_oi - short_oi
    pct = _rolling_percentile(net_oi, int(cfg["percentile_window_weeks"]), int(cfg["percentile_min_weeks"]))
    percentile = _finite(pct.iloc[-1]) if len(pct) else None
    level_score = (percentile - 50.0) * 2.0 if percentile is not None else None
    details: dict[str, dict[str, Any]] = {}
    for name, periods in (("1w", 1), ("2w", 2), ("4w", 4)):
        ld = _finite(long_oi.diff(periods).iloc[-1]) if len(frame) > periods else None
        sd = _finite(short_oi.diff(periods).iloc[-1]) if len(frame) > periods else None
        nd = _finite(net_oi.diff(periods).iloc[-1]) if len(frame) > periods else None
        flow = _directional_flow(ld, sd, float(cfg["unwind_factor"]))
        score = (_norm(flow, float(cfg["flow_scale_net_oi"])) * 100.0) if flow is not None else None
        details[name] = {"long_delta": ld, "short_delta": sd, "net_delta": nd, "flow_score": score, "direction": _dir(score, float(cfg["direction_neutral_threshold"]))}
    flow_weights = {str(k): float(v) for k, v in cfg["flow_weights"].items()}
    weighted_flow, flow_coverage = _weighted({k: _finite(v["flow_score"]) for k, v in details.items()}, flow_weights)
    threshold = float(cfg["direction_neutral_threshold"])
    sign = 1 if weighted_flow is not None and weighted_flow > threshold else -1 if weighted_flow is not None and weighted_flow < -threshold else 0
    denom = agree = 0.0
    if sign:
        for k, w in flow_weights.items():
            direction = details[k]["direction"]
            if direction == "N/V":
                continue
            denom += w
            if (sign > 0 and direction == "BULLISH") or (sign < 0 and direction == "BEARISH"):
                agree += w
    persistence = agree / denom if denom else 0.0
    effective_flow = weighted_flow * (0.50 + 0.50 * persistence) if weighted_flow is not None else None
    score, coverage = _weighted(
        {"level": level_score, "flow": effective_flow},
        {"level": float(cfg["level_weight"]), "flow": float(cfg["flow_weight"])},
    )
    score = _clip(score, -100, 100) if score is not None else None
    state = _cot_state(score, float(cfg["state_directional_threshold"]), float(cfg["state_very_threshold"]))
    build_parts = []
    for k, w in flow_weights.items():
        ld, sd = details[k]["long_delta"], details[k]["short_delta"]
        if ld is None or sd is None or sign == 0:
            continue
        if sign > 0:
            active, unwind = max(ld, 0), max(-sd, 0) * float(cfg["unwind_factor"])
        else:
            active, unwind = max(sd, 0), max(-ld, 0) * float(cfg["unwind_factor"])
        if active + unwind > 0:
            build_parts.append((w, active / (active + unwind)))
    active_build = sum(w * v for w, v in build_parts) / sum(w for w, _ in build_parts) if build_parts else None
    strength = 0.70 * abs(score) + 0.30 * persistence * 100.0 if score is not None else None
    rd = pd.Timestamp(frame.iloc[-1]["report_date"])
    return {
        **empty,
        "available": bool(coverage >= 0.75 and flow_coverage >= 0.75),
        "state": state, "score": score, "position_strength": strength, "persistence": persistence,
        "direction_1w": details["1w"]["direction"], "direction_2w": details["2w"]["direction"], "direction_4w": details["4w"]["direction"],
        "net_oi": _finite(net_oi.iloc[-1]), "net_oi_percentile": percentile,
        "long_delta_1w": details["1w"]["long_delta"], "short_delta_1w": details["1w"]["short_delta"],
        "long_delta_2w": details["2w"]["long_delta"], "short_delta_2w": details["2w"]["short_delta"],
        "long_delta_4w": details["4w"]["long_delta"], "short_delta_4w": details["4w"]["short_delta"],
        "net_delta_1w": details["1w"]["net_delta"], "net_delta_2w": details["2w"]["net_delta"], "net_delta_4w": details["4w"]["net_delta"],
        "active_build_share": active_build,
        "momentum_context": _context_group(frame, momentum, cfg),
        "nonreportable_context": _context_group(frame, "nonreportable", cfg),
        "report_date": rd.date().isoformat(), "availability_date": (rd + pd.Timedelta(days=3)).date().isoformat(), "reason": "",
    }


def evaluate_macro_state(macro_result: dict[str, Any], *, config: dict[str, Any]) -> dict[str, Any]:
    cfg = config["macro"]
    leading = dict(macro_result.get("leading", {}) or {})
    coincident = dict(macro_result.get("coincident", {}) or {})
    ls, cs = _finite(leading.get("slope_13w")), _finite(coincident.get("slope_13w"))
    velocity, _ = _weighted({"l": _norm(ls, cfg["slope_scale"]), "c": _norm(cs, cfg["slope_scale"])}, {"l": .65, "c": .35})
    history = pd.DataFrame(macro_result.get("cycle_history", []))
    acceleration = None
    if len(history) >= 5 and {"leading_slope_13w", "coincident_slope_13w"}.issubset(history.columns):
        l0, l4 = _finite(history.iloc[-1]["leading_slope_13w"]), _finite(history.iloc[-5]["leading_slope_13w"])
        c0, c4 = _finite(history.iloc[-1]["coincident_slope_13w"]), _finite(history.iloc[-5]["coincident_slope_13w"])
        vals = {}
        if l0 is not None and l4 is not None:
            vals["l"] = _norm(l0 - l4, cfg["acceleration_scale"])
        if c0 is not None and c4 is not None:
            vals["c"] = _norm(c0 - c4, cfg["acceleration_scale"])
        acceleration, _ = _weighted(vals, {"l": .70, "c": .30})
    momentum, m_cov = _weighted({"velocity": velocity, "acceleration": acceleration}, {"velocity": .65, "acceleration": .35})
    momentum_score = momentum * 100.0 if momentum is not None else None
    if momentum_score is None:
        momentum_state = "INSUFFICIENT DATA"
    elif momentum_score >= float(cfg["momentum_improving_threshold"]):
        momentum_state = "IMPROVING"
    elif momentum_score <= float(cfg["momentum_deteriorating_threshold"]):
        momentum_state = "DETERIORATING"
    elif velocity is not None and velocity > 0 and acceleration is not None and acceleration < -.10:
        momentum_state = "DECELERATING"
    elif velocity is not None and velocity < 0 and acceleration is not None and acceleration > .20:
        momentum_state = "IMPROVING"
    else:
        momentum_state = "STABLE"
    phase = str(macro_result.get("cycle_phase", "UNCERTAIN")).upper()
    transition = str(macro_result.get("transition_state", phase)).upper()
    if phase == "EXPANSION":
        business = "PEAK" if transition == "PEAK_WATCH" else "LATE EXPANSION" if momentum_state in {"DECELERATING", "DETERIORATING"} else "EXPANSION"
    elif phase == "SLOWDOWN":
        business = "PEAK" if transition == "LATE_SLOWDOWN" else "LATE EXPANSION"
    elif phase == "CONTRACTION":
        business = "TROUGH" if transition == "RECOVERY_WATCH" or (ls is not None and ls > 0 and momentum_state == "IMPROVING") else "CONTRACTION"
    elif phase == "RECOVERY":
        business = "EARLY EXPANSION"
    else:
        business = "INSUFFICIENT DATA"
    leading_breadth = (((macro_result.get("model_breadth") or {}).get("tiers") or {}).get("leading") or {})
    liquidity = dict(macro_result.get("liquidity_modifier", {}) or {})
    confidence = float(_finite(macro_result.get("confidence")) or 0.0) * (.75 + .25 * m_cov)
    return MacroState(
        business_cycle_state=business, source_cycle_phase=phase, source_transition_state=transition,
        macro_momentum_state=momentum_state, macro_momentum_score=momentum_score,
        leading_distance=_finite(leading.get("distance")), leading_slope_13w=ls,
        coincident_distance=_finite(coincident.get("distance")), coincident_slope_13w=cs,
        leading_risk_off_breadth=_finite(leading_breadth.get("risk_off_breadth")), leading_risk_on_breadth=_finite(leading_breadth.get("risk_on_breadth")),
        financial_market_score=_finite(((liquidity.get("channels") or {}).get("market"))), liquidity_state=str(liquidity.get("state", "N/V")),
        confidence=_clip(confidence, 0, 1), as_of=str(macro_result.get("as_of")) if macro_result.get("as_of") is not None else None,
    ).to_dict()


def evaluate_cross_asset_positioning(
    cot_states: dict[str, dict[str, Any]],
    specs: list[AssetSpec],
    *,
    config: dict[str, Any],
    rates_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate cross-asset positioning without mixing directional persistence.

    `risk_off_persistence` and `risk_on_persistence` are calculated only from
    components that actually confirm that direction. `persistence_score` is
    kept as a legacy all-available diagnostic and is not used as directional
    confirmation.
    """

    threshold = float(config["cot"]["state_directional_threshold"])
    expected = [
        spec
        for spec in specs
        if spec.weight > 0
        and spec.risk_off_when in {"BULLISH", "BEARISH"}
    ]
    expected_weight = sum(spec.weight for spec in expected)

    rates_cfg = config.get("rates", {})
    rates_weight = float(rates_cfg.get("basket_weight", 0.0))
    if rates_weight > 0 and rates_state is not None:
        expected_weight += rates_weight

    risk_off_weight = 0.0
    risk_on_weight = 0.0
    available_weight = 0.0
    overall_persistence_numer = 0.0

    risk_off_persistence_numer = 0.0
    risk_off_persistence_denom = 0.0
    risk_on_persistence_numer = 0.0
    risk_on_persistence_denom = 0.0

    risk_off_count = 0
    risk_on_count = 0
    available_count = 0

    for spec in expected:
        state = cot_states.get(spec.key, {})
        if not state.get("available"):
            continue

        score = _finite(state.get("score"))
        if score is None:
            continue

        persistence = float(_finite(state.get("persistence")) or 0.0)
        available_weight += spec.weight
        available_count += 1
        overall_persistence_numer += spec.weight * persistence

        risk_off = (
            score >= threshold
            if spec.risk_off_when == "BULLISH"
            else score <= -threshold
        )
        risk_on = (
            score <= -threshold
            if spec.risk_off_when == "BULLISH"
            else score >= threshold
        )

        if risk_off:
            risk_off_weight += spec.weight
            risk_off_count += 1
            risk_off_persistence_numer += spec.weight * persistence
            risk_off_persistence_denom += spec.weight

        if risk_on:
            risk_on_weight += spec.weight
            risk_on_count += 1
            risk_on_persistence_numer += spec.weight * persistence
            risk_on_persistence_denom += spec.weight

    rates_included = False
    if (
        rates_weight > 0
        and rates_state
        and rates_state.get("available")
    ):
        rates_score = _finite(rates_state.get("score"))
        if rates_score is not None:
            rates_included = True
            persistence = float(_finite(rates_state.get("persistence")) or 0.0)
            available_weight += rates_weight
            available_count += 1
            overall_persistence_numer += rates_weight * persistence

            if rates_score >= threshold:
                risk_off_weight += rates_weight
                risk_off_count += 1
                risk_off_persistence_numer += rates_weight * persistence
                risk_off_persistence_denom += rates_weight
            elif rates_score <= -threshold:
                risk_on_weight += rates_weight
                risk_on_count += 1
                risk_on_persistence_numer += rates_weight * persistence
                risk_on_persistence_denom += rates_weight

    expected_assets = len(expected) + (
        1
        if rates_weight > 0 and rates_state is not None
        else 0
    )

    if available_weight <= 0:
        return {
            "state": "INSUFFICIENT DATA",
            "risk_off_breadth": None,
            "risk_on_breadth": None,
            "risk_off_confirmations": 0,
            "risk_on_confirmations": 0,
            "directional_assets": 0,
            "available_assets": 0,
            "expected_assets": expected_assets,
            "weighted_coverage": 0.0,
            "cot_risk_score": None,
            "persistence_score": None,
            "risk_off_persistence": None,
            "risk_on_persistence": None,
            "rates_included": False,
        }

    risk_off_breadth = risk_off_weight / available_weight
    risk_on_breadth = risk_on_weight / available_weight
    coverage = (
        available_weight / expected_weight
        if expected_weight > 0
        else 0.0
    )

    sm = config["state_machine"]
    if coverage < float(sm["minimum_cross_asset_coverage"]):
        state_name = "INSUFFICIENT DATA"
    elif risk_off_breadth >= float(sm["strong_breadth"]):
        state_name = "DEFENSIVE / RISK-OFF"
    elif risk_on_breadth >= float(sm["strong_breadth"]):
        state_name = "RISK-ON"
    elif risk_off_breadth >= float(sm["lean_breadth"]):
        state_name = "DEFENSIVE LEAN"
    elif risk_on_breadth >= float(sm["lean_breadth"]):
        state_name = "RISK-ON LEAN"
    else:
        state_name = "MIXED"

    return {
        "state": state_name,
        "risk_off_breadth": risk_off_breadth,
        "risk_on_breadth": risk_on_breadth,
        "risk_off_confirmations": risk_off_count,
        "risk_on_confirmations": risk_on_count,
        "directional_assets": available_count,
        "available_assets": sum(
            bool(value.get("available"))
            for value in cot_states.values()
        ) + (1 if rates_included else 0),
        "expected_assets": expected_assets,
        "weighted_coverage": _clip(coverage, 0, 1),
        "cot_risk_score": risk_on_breadth - risk_off_breadth,
        "persistence_score": overall_persistence_numer / available_weight,
        "risk_off_persistence": (
            risk_off_persistence_numer / risk_off_persistence_denom
            if risk_off_persistence_denom > 0
            else None
        ),
        "risk_on_persistence": (
            risk_on_persistence_numer / risk_on_persistence_denom
            if risk_on_persistence_denom > 0
            else None
        ),
        "rates_included": rates_included,
    }


def _macro_risk_sign(phase: str) -> float:
    return {"EXPANSION": 1.0, "LATE EXPANSION": .60, "PEAK": .15, "CONTRACTION": -1.0, "TROUGH": -.35, "EARLY EXPANSION": .75}.get(phase, 0.0)


def _target(phase: str) -> str:
    if phase in {"EXPANSION", "LATE EXPANSION", "PEAK"}:
        return "RISK_OFF"
    if phase in {"CONTRACTION", "TROUGH", "EARLY EXPANSION"}:
        return "RISK_ON"
    return "UNKNOWN"


def _pressure_components(
    macro: dict[str, Any],
    cross: dict[str, Any],
    cot_states: dict[str, dict[str, Any]],
    specs: list[AssetSpec],
    config: dict[str, Any],
    rates_state: dict[str, Any] | None = None,
) -> tuple[dict[str, float | None], str]:
    target = _target(str(macro.get("business_cycle_state", "")))
    if target == "UNKNOWN":
        return {k: None for k in config["transition_pressure"]["weights"]}, target

    breadth = _finite(cross.get("risk_off_breadth" if target == "RISK_OFF" else "risk_on_breadth"))
    threshold = float(config["cot"]["state_directional_threshold"])
    pers_n = pers_d = 0.0

    for spec in specs:
        if spec.weight <= 0 or spec.risk_off_when not in {"BULLISH", "BEARISH"}:
            continue
        state = cot_states.get(spec.key, {})
        if not state.get("available"):
            continue
        score, persistence = _finite(state.get("score")), _finite(state.get("persistence"))
        if score is None or persistence is None:
            continue
        ro = score >= threshold if spec.risk_off_when == "BULLISH" else score <= -threshold
        ri = score <= -threshold if spec.risk_off_when == "BULLISH" else score >= threshold
        confirms = ro if target == "RISK_OFF" else ri
        pers_d += spec.weight
        if confirms:
            pers_n += spec.weight * persistence * min(1.0, abs(score) / 70.0)

    rates_weight = float(config.get("rates", {}).get("basket_weight", 0.0))
    if rates_weight > 0 and rates_state and rates_state.get("available"):
        score = _finite(rates_state.get("score"))
        persistence = _finite(rates_state.get("persistence"))
        if score is not None and persistence is not None:
            confirms = score >= threshold if target == "RISK_OFF" else score <= -threshold
            pers_d += rates_weight
            if confirms:
                pers_n += rates_weight * persistence * min(1.0, abs(score) / 70.0)

    momentum = str(macro.get("macro_momentum_state", "N/V"))
    mm = (
        {"IMPROVING": 0, "STABLE": 20, "DECELERATING": 65, "DETERIORATING": 100}.get(momentum)
        if target == "RISK_OFF"
        else {"IMPROVING": 100, "STABLE": 25, "DECELERATING": 10, "DETERIORATING": 0}.get(momentum)
    )
    leading = _finite(macro.get("leading_risk_off_breadth" if target == "RISK_OFF" else "leading_risk_on_breadth"))
    market = _finite(macro.get("financial_market_score"))
    financial = None if market is None else _clip(-market if target == "RISK_OFF" else market, 0, 100)

    return {
        "cot_persistence": (pers_n / pers_d * 100.0) if pers_d else None,
        "cross_asset_breadth": breadth * 100.0 if breadth is not None else None,
        "macro_momentum": float(mm) if mm is not None else None,
        "leading_breadth": leading * 100.0 if leading is not None else None,
        "financial_market_confirmation": financial,
    }, target


def _pressure_label(value: float | None) -> str:
    if value is None: return "INSUFFICIENT DATA"
    if value < 20: return "CURRENT REGIME STABLE"
    if value < 40: return "MILD DIVERGENCE"
    if value < 60: return "TRANSITION WATCH"
    if value < 80: return "ELEVATED TRANSITION PRESSURE"
    return "REGIME SHIFT LIKELY / PARTIALLY PRICED"


def _alignment(macro: dict[str, Any], cross: dict[str, Any]) -> tuple[str, str, str]:
    ms = _macro_risk_sign(str(macro.get("business_cycle_state", "")))
    cs = _finite(cross.get("cot_risk_score"))
    if cs is None or abs(ms) < .10:
        return "MIXED", "MIXED", "NO CLEAR DIRECTION"
    product, mag = ms * cs, min(abs(ms), abs(cs))
    if product > 0:
        return ("STRONG ALIGNMENT" if mag >= .55 else "MODERATE ALIGNMENT", "LOW", "RISK-ON CONFIRMED" if ms > 0 else "RISK-OFF CONFIRMED")
    return ("STRONG DIVERGENCE" if mag >= .55 else "MODERATE DIVERGENCE", "STRONG" if mag >= .55 else "MODERATE", "RISK-ON → RISK-OFF" if ms > 0 else "RISK-OFF → RISK-ON")


def classify_regime_transition(macro: dict[str, Any], cross: dict[str, Any], *, transition_pressure: float | None, config: dict[str, Any]) -> tuple[str, str]:
    sm = config["state_machine"]
    if macro.get("business_cycle_state") == "INSUFFICIENT DATA" or float(cross.get("weighted_coverage", 0.0)) < float(sm["minimum_cross_asset_coverage"]) or transition_pressure is None:
        return "INSUFFICIENT DATA", "R0"
    phase, momentum = str(macro.get("business_cycle_state")), str(macro.get("macro_momentum_state"))
    ro, ri = float(cross.get("risk_off_breadth") or 0), float(cross.get("risk_on_breadth") or 0)
    lro, lri = float(macro.get("leading_risk_off_breadth") or 0), float(macro.get("leading_risk_on_breadth") or 0)
    strong, lean = float(sm["strong_breadth"]), float(sm["lean_breadth"])
    elevated, watch = float(sm["elevated_pressure"]), float(sm["watch_pressure"])
    if phase == "EARLY EXPANSION": return ("R8 — EARLY EXPANSION", "R8") if ri >= lean else ("R6 — EARLY TROUGH DIVERGENCE", "R6")
    if phase in {"CONTRACTION", "TROUGH"}:
        if ri >= strong and momentum == "IMPROVING" and transition_pressure >= elevated and lri >= lean: return "R7 — TROUGH WATCH", "R7"
        if ri >= lean: return "R6 — EARLY TROUGH DIVERGENCE", "R6"
        return "R5 — CONFIRMED CONTRACTION", "R5"
    if phase == "PEAK":
        if ro >= strong and transition_pressure >= elevated and lro >= lean: return "R4 — PEAK WATCH", "R4"
        if ro >= lean: return "R3 — LATE EXPANSION WARNING", "R3"
        return "R2 — EARLY DIVERGENCE", "R2"
    if phase in {"EXPANSION", "LATE EXPANSION"}:
        if ro >= strong and momentum in {"DECELERATING", "DETERIORATING"} and transition_pressure >= elevated and lro >= lean:
            return ("R4 — PEAK WATCH", "R4") if phase == "LATE EXPANSION" else ("R3 — LATE EXPANSION WARNING", "R3")
        if ro >= lean and momentum in {"DECELERATING", "DETERIORATING"} and transition_pressure >= watch: return "R3 — LATE EXPANSION WARNING", "R3"
        if ro >= lean: return "R2 — EARLY DIVERGENCE", "R2"
        return "R1 — CONFIRMED RISK-ON", "R1"
    return "INSUFFICIENT DATA", "R0"


def evaluate_combined_regime(
    macro: dict[str, Any],
    cot_states: dict[str, dict[str, Any]],
    specs: list[AssetSpec],
    *,
    config: dict[str, Any],
    rates_state: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cross = evaluate_cross_asset_positioning(cot_states, specs, config=config, rates_state=rates_state)
    components, target = _pressure_components(macro, cross, cot_states, specs, config, rates_state=rates_state)
    weights = {str(k): float(v) for k, v in config["transition_pressure"]["weights"].items()}
    pressure, component_coverage = _weighted(components, weights)
    pressure = _clip(pressure, 0, 100) if pressure is not None else None
    state, code = classify_regime_transition(macro, cross, transition_pressure=pressure, config=config)
    alignment, divergence, direction = _alignment(macro, cross)
    confidence = _clip(float(macro.get("confidence", 0)) * .45 + float(cross.get("weighted_coverage", 0)) * .35 + component_coverage * .20, 0, 1)
    trading = {"R1": "RISK-ON", "R2": "NEUTRAL → CAUTIOUS", "R3": "NEUTRAL → DEFENSIVE", "R4": "DEFENSIVE", "R5": "RISK-OFF", "R6": "RISK-OFF → SELECTIVE", "R7": "SELECTIVE → OFFENSIVE", "R8": "RISK-ON"}.get(code, "LOW CONFIDENCE")

    rates_text = ""
    if rates_state and rates_state.get("available"):
        rates_text = f" Treasury Duration: {rates_state.get('state')}."

    if "INSUFFICIENT" in state:
        summary = "Makro- oder Cross-Asset-COT-Abdeckung ist unzureichend. Es wird bewusst kein belastbarer Transition-Bias abgeleitet."
    elif code in {"R2", "R3", "R4"}:
        summary = f"Makro bleibt {macro.get('business_cycle_state')}, während die Positionierung {cross.get('state')} zeigt.{rates_text} {direction}; 2W/4W-Persistenz und Leading-/Market-Bestätigung entscheiden über den Regimewechsel."
    elif code in {"R6", "R7"}:
        summary = f"Die Realwirtschaft bleibt {macro.get('business_cycle_state')}, aber COT zeigt {cross.get('state')}.{rates_text} Positionierung könnte eine Bodenbildung vorwegnehmen; technisches Timing bleibt erforderlich."
    else:
        summary = f"Business Cycle {macro.get('business_cycle_state')} und COT {cross.get('state')} ergeben {state}.{rates_text}"

    return {
        "transition_state": state,
        "transition_code": code,
        "transition_pressure": pressure,
        "transition_pressure_label": _pressure_label(pressure),
        "transition_pressure_confidence": confidence,
        "alignment_state": alignment,
        "divergence_state": divergence,
        "direction": direction,
        "trading_regime": trading,
        "summary": summary,
        "pressure_components": components,
        "target_transition_direction": target,
    }, cross


def _asset_macro_bias(spec: AssetSpec, macro: dict[str, Any]) -> tuple[str, float]:
    risk = _macro_risk_sign(str(macro.get("business_cycle_state", "")))
    if spec.risk_off_when == "ASSET_SPECIFIC": return "NEUTRAL", 0.0
    score = -risk if spec.risk_off_when == "BULLISH" else risk
    label = "BULLISH" if score >= .60 else "BULLISH / FRAGILE" if score >= .20 else "BEARISH" if score <= -.60 else "BEARISH / FRAGILE" if score <= -.20 else "NEUTRAL"
    return label, score


def build_opportunity_map(
    macro: dict[str, Any],
    combined: dict[str, Any],
    cross: dict[str, Any],
    cot_states: dict[str, dict[str, Any]],
    specs: list[AssetSpec],
    *,
    config: dict[str, Any],
    rates_state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    code = str(combined.get("transition_code", "R0"))
    pressure = float(combined.get("transition_pressure") or 0)
    target = str(combined.get("target_transition_direction", "UNKNOWN"))

    for spec in specs:
        if spec.opportunity_group == "RATES_CURVE":
            continue

        cot = cot_states.get(spec.key, {})
        macro_bias, macro_score = _asset_macro_bias(spec, macro)
        if not cot.get("available"):
            rows.append({"market": spec.label, "macro_bias": macro_bias, "cot_bias": "INSUFFICIENT DATA", "alignment": "LOW CONFIDENCE", "setup_type": "NO EDGE", "preference": "NEUTRAL", "bias_note": "COT-Daten fehlen.", "asymmetric_transition": False, "position_strength": None, "persistence": None})
            continue

        cot_score = float(_finite(cot.get("score")) or 0) / 100.0
        persistence = float(_finite(cot.get("persistence")) or 0)
        strength = _finite(cot.get("position_strength"))

        if abs(macro_score) < .20 or abs(cot_score) < .18:
            alignment = "NEUTRAL"
        elif macro_score * cot_score > 0:
            alignment = "STRONG ALIGNMENT" if min(abs(macro_score), abs(cot_score)) >= .55 else "ALIGNED"
        else:
            alignment = "STRONG CONFLICT" if min(abs(macro_score), abs(cot_score)) >= .55 else "CONFLICT"

        if alignment in {"STRONG ALIGNMENT", "ALIGNED"}:
            setup, pref = "CONFIRMED TREND", "FAVOR" if persistence >= .65 and (strength or 0) >= 50 else "WATCH"
        elif alignment in {"STRONG CONFLICT", "CONFLICT"}:
            if code == "R4" and pressure >= 60:
                setup, pref = "PEAK REVERSAL", "WATCH"
            elif code == "R7" and pressure >= 60:
                setup, pref = "TROUGH REVERSAL", "WATCH"
            elif code in {"R2", "R3", "R6"}:
                setup, pref = "MACRO-COT DIVERGENCE", "WATCH" if persistence >= .65 else "CONFLICT"
            else:
                setup, pref = "CONFLICT", "AVOID" if pressure < 40 else "CONFLICT"
        elif pressure >= 40 and persistence >= .65 and abs(cot_score) >= .40:
            setup, pref = "EARLY TRANSITION", "WATCH"
        else:
            setup, pref = "NO EDGE", "NEUTRAL"

        note = "Bullish Bias" if cot_score > .18 else "Bearish Bias" if cot_score < -.18 else "Wait"
        confirms = False
        if spec.risk_off_when in {"BULLISH", "BEARISH"}:
            ro = cot_score > .18 if spec.risk_off_when == "BULLISH" else cot_score < -.18
            ri = cot_score < -.18 if spec.risk_off_when == "BULLISH" else cot_score > .18
            confirms = ro if target == "RISK_OFF" else ri if target == "RISK_ON" else False
        breadth = _finite(cross.get("risk_off_breadth" if target == "RISK_OFF" else "risk_on_breadth"))
        asym = bool(confirms and persistence >= .65 and abs(cot_score) >= .55 and pressure >= 60 and breadth is not None and breadth >= .60 and setup in {"MACRO-COT DIVERGENCE", "EARLY TRANSITION", "PEAK REVERSAL", "TROUGH REVERSAL"})
        rows.append({"market": spec.label, "macro_bias": macro_bias, "cot_bias": str(cot.get("state", "NEUTRAL")), "alignment": alignment, "setup_type": setup, "preference": pref, "bias_note": note + (" · asymmetric transition watch" if asym else ""), "asymmetric_transition": asym, "position_strength": strength, "persistence": persistence})

    if rates_state is not None:
        synthetic = AssetSpec(
            key="rates_duration",
            label="Treasury Duration",
            asset_class="Rates",
            aliases=(),
            risk_off_when="BULLISH",
            weight=float(config.get("rates", {}).get("basket_weight", 0.0)),
            opportunity_group="RATES",
        )
        macro_bias, macro_score = _asset_macro_bias(synthetic, macro)
        if not rates_state.get("available"):
            rows.append({"market": "Treasury Duration", "macro_bias": macro_bias, "cot_bias": "INSUFFICIENT DATA", "alignment": "LOW CONFIDENCE", "setup_type": "NO EDGE", "preference": "NEUTRAL", "bias_note": "Treasury-Curve-COT unvollständig.", "asymmetric_transition": False, "position_strength": None, "persistence": None})
        else:
            cot_score = float(_finite(rates_state.get("score")) or 0) / 100.0
            persistence = float(_finite(rates_state.get("persistence")) or 0)
            strength = abs(cot_score) * 100.0
            if abs(macro_score) < .20 or abs(cot_score) < .18:
                alignment = "NEUTRAL"
            elif macro_score * cot_score > 0:
                alignment = "STRONG ALIGNMENT" if min(abs(macro_score), abs(cot_score)) >= .55 else "ALIGNED"
            else:
                alignment = "STRONG CONFLICT" if min(abs(macro_score), abs(cot_score)) >= .55 else "CONFLICT"

            if alignment in {"STRONG ALIGNMENT", "ALIGNED"}:
                setup, pref = "CONFIRMED TREND", "FAVOR" if persistence >= .65 and strength >= 50 else "WATCH"
            elif code in {"R2", "R3", "R4", "R6", "R7"} and persistence >= .65:
                setup, pref = "MACRO-COT DIVERGENCE", "WATCH"
            elif alignment in {"STRONG CONFLICT", "CONFLICT"}:
                setup, pref = "CONFLICT", "CONFLICT"
            else:
                setup, pref = "NO EDGE", "NEUTRAL"

            note = "Bullish Duration" if cot_score > .18 else "Bearish Duration" if cot_score < -.18 else "Mixed Duration"
            rows.append({"market": "Treasury Duration", "macro_bias": macro_bias, "cot_bias": str(rates_state.get("state", "MIXED DURATION")), "alignment": alignment, "setup_type": setup, "preference": pref, "bias_note": note, "asymmetric_transition": False, "position_strength": strength, "persistence": persistence})

    order = {"FAVOR": 0, "WATCH": 1, "CONFLICT": 2, "AVOID": 3, "NEUTRAL": 4}
    return sorted(rows, key=lambda r: (order.get(r["preference"], 9), -float(r.get("position_strength") or 0), r["market"]))


def build_alignment_matrix(
    macro: dict[str, Any],
    cot_states: dict[str, dict[str, Any]],
    specs: list[AssetSpec],
    rates_state: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    phase = str(macro.get("business_cycle_state", "N/V"))
    ms = _macro_risk_sign(phase)
    rows = [{"layer": "Business Cycle", "state": phase, "contribution": "POSITIVE" if ms > .2 else "NEGATIVE" if ms < -.2 else "NEUTRAL"}]
    mom = str(macro.get("macro_momentum_state", "N/V"))
    rows.append({"layer": "Leading / Macro Momentum", "state": mom, "contribution": "POSITIVE" if mom == "IMPROVING" else "NEGATIVE" if mom in {"DECELERATING", "DETERIORATING"} else "NEUTRAL"})
    liq = str(macro.get("liquidity_state", "N/V"))
    rows.append({"layer": "Financial Conditions", "state": liq, "contribution": "POSITIVE" if liq == "SUPPORTIVE" else "NEGATIVE" if liq == "RESTRICTIVE" else "NEUTRAL"})

    spec_map = {s.key: s for s in specs}
    for key in ("sp500", "dow", "nasdaq", "jpy", "chf", "gold"):
        spec, cot = spec_map.get(key), cot_states.get(key, {})
        if spec is None:
            continue
        if not cot.get("available"):
            contribution, state = "INSUFFICIENT DATA", "INSUFFICIENT DATA"
        else:
            score, state = float(_finite(cot.get("score")) or 0), str(cot.get("state", "N/V"))
            if spec.risk_off_when == "BULLISH":
                contribution = "DEFENSIVE" if score > 18 else "RISK-ON" if score < -18 else "NEUTRAL"
            elif spec.risk_off_when == "BEARISH":
                contribution = "DEFENSIVE" if score < -18 else "RISK-ON" if score > 18 else "NEUTRAL"
            else:
                contribution = "ASSET SPECIFIC"
        rows.append({"layer": f"{spec.label} COT", "state": state, "contribution": contribution})

    if rates_state is not None:
        if not rates_state.get("available"):
            contribution, state = "INSUFFICIENT DATA", "INSUFFICIENT DATA"
        else:
            score = float(_finite(rates_state.get("score")) or 0)
            state = str(rates_state.get("state", "MIXED DURATION"))
            contribution = "DEFENSIVE" if score > 18 else "RISK-ON" if score < -18 else "NEUTRAL"
        rows.append({"layer": "Treasury Duration COT", "state": state, "contribution": contribution})

    return rows


def build_transition_confirmation(
    macro: dict[str, Any],
    combined: dict[str, Any],
    cross: dict[str, Any],
    *,
    config: dict[str, Any],
    rates_state: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    target = str(combined.get("target_transition_direction", "UNKNOWN"))
    if target == "UNKNOWN":
        return [
            {
                "trigger": "Transition Direction",
                "status": "INSUFFICIENT DATA",
                "why": "Makro-Regime nicht eindeutig genug.",
            }
        ]

    if target == "RISK_OFF":
        persistence = _finite(cross.get("risk_off_persistence"))
        breadth = _finite(cross.get("risk_off_breadth"))
        leading = _finite(macro.get("leading_risk_off_breadth"))
        momentum = str(macro.get("macro_momentum_state", "N/V"))
        market = _finite(macro.get("financial_market_score"))
        momentum_ok = momentum in {"DECELERATING", "DETERIORATING"}
        market_ok = market is not None and market < -15
        labels = (
            "2W/4W Risk-Off-COT bleibt persistent",
            "Leading breadth verschlechtert sich",
            "Financial/market conditions bestätigen Risk-Off",
        )
        rates_ok = bool(
            rates_state
            and rates_state.get("risk_off_confirmed")
            and (_finite(rates_state.get("persistence")) or 0) >= 0.65
        )
        rates_target = "Bullish Duration / defensive"
    else:
        persistence = _finite(cross.get("risk_on_persistence"))
        breadth = _finite(cross.get("risk_on_breadth"))
        leading = _finite(macro.get("leading_risk_on_breadth"))
        momentum = str(macro.get("macro_momentum_state", "N/V"))
        market = _finite(macro.get("financial_market_score"))
        momentum_ok = momentum == "IMPROVING"
        market_ok = market is not None and market > 15
        labels = (
            "2W/4W Risk-On-COT bleibt persistent",
            "Leading breadth stabilisiert / dreht Risk-On",
            "Financial/market conditions bestätigen Risk-On",
        )
        rates_ok = bool(
            rates_state
            and rates_state.get("risk_on_confirmed")
            and (_finite(rates_state.get("persistence")) or 0) >= 0.65
        )
        rates_target = "Bearish Duration / risk-on repricing"

    strong = float(config["state_machine"]["strong_breadth"])
    rows = [
        {
            "trigger": labels[0],
            "status": (
                "CONFIRMED"
                if persistence is not None and persistence >= 0.65
                else "WATCH"
            ),
            "why": (
                f"Direction-specific persistence {persistence:.0%}"
                if persistence is not None
                else "Direction-specific persistence N/V"
            ),
        },
        {
            "trigger": "Cross-Asset Breadth",
            "status": (
                "CONFIRMED"
                if breadth is not None and breadth >= strong
                else "WATCH"
            ),
            "why": (
                f"{breadth:.0%} bestätigen die Transition-Richtung"
                if breadth is not None
                else "Breadth N/V"
            ),
        },
    ]

    if rates_state is not None:
        rates_2w = _finite(
            rates_state.get(
                "bullish_2w_breadth"
                if target == "RISK_OFF"
                else "bearish_2w_breadth"
            )
        )
        rates_4w = _finite(
            rates_state.get(
                "bullish_4w_breadth"
                if target == "RISK_OFF"
                else "bearish_4w_breadth"
            )
        )
        evidence = (
            f"{rates_state.get('state', 'N/V')} · 2W {rates_2w:.0%} · 4W {rates_4w:.0%}"
            if rates_2w is not None and rates_4w is not None
            else str(rates_state.get("state", "N/V"))
        )
        rows.append(
            {
                "trigger": "Treasury Duration COT",
                "status": (
                    "CONFIRMED"
                    if rates_ok
                    else "WATCH"
                    if rates_state.get("available")
                    else "INSUFFICIENT DATA"
                ),
                "why": f"{rates_target}: {evidence}",
            }
        )

    rows.extend(
        [
            {
                "trigger": "Macro Momentum / zweite Ableitung",
                "status": "CONFIRMED" if momentum_ok else "WATCH",
                "why": momentum,
            },
            {
                "trigger": labels[1],
                "status": (
                    "CONFIRMED"
                    if leading is not None and leading >= 0.50
                    else "WATCH"
                ),
                "why": (
                    f"Leading breadth {leading:.0%}"
                    if leading is not None
                    else "Leading breadth N/V"
                ),
            },
            {
                "trigger": labels[2],
                "status": (
                    "CONFIRMED"
                    if market_ok
                    else "WATCH"
                    if market is not None
                    else "INSUFFICIENT DATA"
                ),
                "why": (
                    f"Market-liquidity score {market:+.0f}"
                    if market is not None
                    else "keine verfügbare Market-Confirmation"
                ),
            },
            {
                "trigger": "Technical Setup",
                "status": "NEEDED",
                "why": "Der Macro × COT Layer erzeugt bewusst keinen Entry.",
            },
        ]
    )
    return rows


def evaluate_macro_cot_regime(*, macro_result: dict[str, Any], cot_states: dict[str, dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    specs = asset_specs(config)
    macro = evaluate_macro_state(macro_result, config=config)
    rates_state = evaluate_rates_positioning(cot_states, config=config)
    combined, cross = evaluate_combined_regime(macro, cot_states, specs, config=config, rates_state=rates_state)
    return {
        "macro": macro,
        "cot_assets": cot_states,
        "rates_positioning": rates_state,
        "cross_asset": cross,
        "combined": combined,
        "alignment_matrix": build_alignment_matrix(macro, cot_states, specs, rates_state=rates_state),
        "opportunity_map": build_opportunity_map(macro, combined, cross, cot_states, specs, config=config, rates_state=rates_state),
        "transition_confirmation": build_transition_confirmation(macro, combined, cross, config=config, rates_state=rates_state),
        "transition_path": list(STATE_SEQUENCE),
        "methodology": {
            "entry_signal": False,
            "mock_fallback": False,
            "cot_structural_groups": {"tff": "Asset Manager", "disaggregated": "Producer / Merchant"},
            "dealer_note": "Dealer/Intermediary is not treated as physical Commercial/Producer.",
            "rates_note": "2Y/5Y/10Y/30Y Treasury COT is aggregated once as a duration basket to avoid double counting.",
            "seasonality_role": "Separate turning-window layer; not an independent V1 Macro × COT signal.",
        },
    }
