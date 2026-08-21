from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


def _finite(value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return np.nan
    return x if np.isfinite(x) else np.nan


def _sign(value: Any) -> int:
    x = _finite(value)
    if not np.isfinite(x) or x == 0:
        return 0
    return 1 if x > 0 else -1


def direction_label(direction: int) -> str:
    value = int(direction or 0)
    if value > 0:
        return "BULLISH"
    if value < 0:
        return "BEARISH"
    return "NEUTRAL"


def robust_horizon_summary(stability: pd.DataFrame, horizon_days: int) -> dict:
    base = {
        "horizon_days": int(horizon_days),
        "available_windows": 0,
        "bullish_windows": 0,
        "bearish_windows": 0,
        "mixed_windows": 0,
        "direction": 0,
        "quality": "N/V",
        "label": "N/V",
        "median_edge": np.nan,
        "median_hit_edge_pp": np.nan,
    }
    if stability is None or stability.empty:
        return base

    work = stability[
        pd.to_numeric(stability["horizon_days"], errors="coerce").eq(int(horizon_days))
    ].copy()
    if work.empty:
        return base

    dirs = work["direction"].astype(str).str.upper()
    bull = int(dirs.eq("BULLISH").sum())
    bear = int(dirs.eq("BEARISH").sum())
    mixed = int(dirs.eq("MIXED").sum())

    median_edge = float(pd.to_numeric(work["median_edge"], errors="coerce").median())
    median_hit = float(pd.to_numeric(work["hit_rate_edge_pp"], errors="coerce").median())

    direction = 0
    quality = "MIXED"
    label = "MIXED"
    if bull >= 3 and bear == 0:
        direction, quality, label = 1, "ROBUST", "ROBUST BULLISH"
    elif bear >= 3 and bull == 0:
        direction, quality, label = -1, "ROBUST", "ROBUST BEARISH"
    elif bull >= 2 and bear == 0:
        direction, quality, label = 1, "LEAN", "BULLISH LEAN"
    elif bear >= 2 and bull == 0:
        direction, quality, label = -1, "LEAN", "BEARISH LEAN"

    return {
        **base,
        "available_windows": int(len(work)),
        "bullish_windows": bull,
        "bearish_windows": bear,
        "mixed_windows": mixed,
        "direction": direction,
        "quality": quality,
        "label": label,
        "median_edge": median_edge,
        "median_hit_edge_pp": median_hit,
    }


def seasonal_edge_context(stability: pd.DataFrame, turn: Mapping[str, Any] | None) -> dict:
    turn = dict(turn or {})
    h40 = robust_horizon_summary(stability, 40)
    h60 = robust_horizon_summary(stability, 60)
    d40, d60 = int(h40["direction"]), int(h60["direction"])
    q40, q60 = str(h40["quality"]), str(h60["quality"])

    edge_direction = 0
    edge_quality = "MIXED"
    edge_label = "40/60 MIXED"

    if d40 != 0 and d40 == d60:
        edge_direction = d40
        if q40 == "ROBUST" and q60 == "ROBUST":
            edge_quality = "ROBUST"
            edge_label = f"{direction_label(d40)} · 40/60 ROBUST"
        else:
            edge_quality = "PARTIAL"
            edge_label = f"{direction_label(d40)} · 40/60 LEAN"
    elif d40 != 0 and d60 == 0 and q40 == "ROBUST":
        edge_direction, edge_quality = d40, "PARTIAL"
        edge_label = f"{direction_label(d40)} · 40T ROBUST"
    elif d60 != 0 and d40 == 0 and q60 == "ROBUST":
        edge_direction, edge_quality = d60, "PARTIAL"
        edge_label = f"{direction_label(d60)} · 60T ROBUST"
    elif d40 != 0 and d60 != 0 and d40 == -d60:
        edge_label = "40/60 CONFLICT"

    turn_type = str(turn.get("turn_type", "N/V") or "N/V").upper()
    try:
        distance = int(turn.get("distance_days"))
    except (TypeError, ValueError):
        distance = None

    turn_direction = 0
    if distance is not None and abs(distance) <= 15:
        if turn_type == "BOTTOM":
            turn_direction = 1
        elif turn_type == "TOP":
            turn_direction = -1

    if turn_direction and edge_direction:
        relation = "TURN + EDGE ALIGNED" if turn_direction == edge_direction else "TURN / EDGE CONFLICT"
    elif turn_direction:
        relation = "TURN ACTIVE · EDGE MIXED"
    elif edge_direction:
        relation = "EDGE PRESENT · NO NEAR TURN"
    else:
        relation = "NO CLEAR SEASONAL CONFLUENCE"

    return {
        "h40": h40,
        "h60": h60,
        "edge_direction": edge_direction,
        "edge_quality": edge_quality,
        "edge_label": edge_label,
        "turn_direction": turn_direction,
        "turn_edge_relation": relation,
        "turn_type": turn_type,
        "turn_distance_days": distance,
    }


def positioning_flow_from_history(enriched: pd.DataFrame, report_type: str) -> dict:
    base = {
        "available": False,
        "report_type": str(report_type),
        "directional_interpretation": False,
        "primary_key": "",
        "primary_label": "N/V",
        "flow_direction_4w": 0,
        "flow_label_4w": "N/V",
        "recent_flow": "N/V",
        "identity_ok": True,
    }
    if enriched is None or enriched.empty:
        return base

    primary = "producer" if str(report_type) == "disaggregated" else "dealer"
    label = "Producer / Merchant" if primary == "producer" else "Dealer / Intermediary"
    required = {"report_date", f"{primary}_long", f"{primary}_short", "open_interest_all"}
    if not required.issubset(set(enriched.columns)):
        return {**base, "primary_key": primary, "primary_label": label}

    x = enriched.copy()
    x["report_date"] = pd.to_datetime(x["report_date"], errors="coerce")
    x = x.dropna(subset=["report_date"]).sort_values("report_date").reset_index(drop=True)
    if len(x) < 5:
        return {**base, "primary_key": primary, "primary_label": label}

    longs = pd.to_numeric(x[f"{primary}_long"], errors="coerce")
    shorts = pd.to_numeric(x[f"{primary}_short"], errors="coerce")
    oi = pd.to_numeric(x["open_interest_all"], errors="coerce").replace(0, np.nan)
    net = longs - shorts
    net_oi = net / oi
    last = len(x) - 1

    out = {
        **base,
        "available": True,
        "primary_key": primary,
        "primary_label": label,
        "directional_interpretation": primary == "producer",
        "report_date": x.iloc[-1]["report_date"],
        "current_net": float(net.iloc[-1]),
        "current_net_oi": float(net_oi.iloc[-1]),
    }

    identity_ok = True
    for weeks in (1, 2, 4):
        prior = last - weeks
        long_delta = float(longs.iloc[last] - longs.iloc[prior])
        short_delta = float(shorts.iloc[last] - shorts.iloc[prior])
        net_delta = float(long_delta - short_delta)
        net_oi_delta = float(net_oi.iloc[last] - net_oi.iloc[prior])
        out[f"long_delta_{weeks}w"] = long_delta
        out[f"short_delta_{weeks}w"] = short_delta
        out[f"net_delta_{weeks}w"] = net_delta
        out[f"net_oi_delta_{weeks}w"] = net_oi_delta
        identity_ok = identity_ok and bool(np.isclose(net_delta, long_delta - short_delta, rtol=0.0, atol=1e-9))

    out["identity_ok"] = identity_ok
    net4 = float(out["net_delta_4w"])
    long4 = float(out["long_delta_4w"])
    short4 = float(out["short_delta_4w"])
    flow_direction = _sign(net4)

    if flow_direction > 0:
        if long4 > 0 and short4 <= 0:
            flow_label = "ACTIVE LONG + SHORT COVERING"
        elif long4 > 0 and short4 > 0:
            flow_label = "ACTIVE LONG BUILD"
        elif short4 < 0:
            flow_label = "SHORT COVERING"
        else:
            flow_label = "NET BULLISH FLOW"
    elif flow_direction < 0:
        if short4 > 0 and long4 <= 0:
            flow_label = "ACTIVE SHORT + LONG LIQUIDATION"
        elif short4 > 0 and long4 > 0:
            flow_label = "ACTIVE SHORT BUILD"
        elif long4 < 0:
            flow_label = "LONG LIQUIDATION"
        else:
            flow_label = "NET BEARISH FLOW"
    else:
        flow_label = "FLAT 4W FLOW"

    out["flow_direction_4w"] = flow_direction
    out["flow_label_4w"] = flow_label
    s1, s2 = _sign(out["net_delta_1w"]), _sign(out["net_delta_2w"])
    if flow_direction == 0:
        recent = "NO 4W DIRECTION"
    elif s1 == flow_direction and s2 == flow_direction:
        recent = "CONFIRMING"
    elif s1 == -flow_direction and s2 == -flow_direction:
        recent = "REVERSING"
    elif s1 == -flow_direction or s2 == -flow_direction:
        recent = "WEAKENING"
    else:
        recent = "MIXED"
    out["recent_flow"] = recent
    return out


def phase_shift_modifier(consensus: Mapping[str, Any] | None) -> dict:
    consensus = dict(consensus or {})
    agreement = str(consensus.get("agreement", "N/V") or "N/V").upper()
    try:
        shift = int(consensus.get("consensus_shift_days"))
    except (TypeError, ValueError):
        shift = None
    usable = bool(agreement == "CONSISTENT" and shift is not None)
    if not usable:
        label = "IGNORED · NO CONSISTENT SHIFT"
    elif shift <= -5:
        label = f"LAG {abs(shift)}T"
    elif shift >= 5:
        label = f"LEAD {shift}T"
    else:
        label = "IN PHASE"
    return {"usable": usable, "shift_days": shift, "agreement": agreement, "label": label}


def classify_cot_x_seasonality(
    macro: Mapping[str, Any] | None,
    seasonal: Mapping[str, Any] | None,
    flow: Mapping[str, Any] | None,
    phase_shift: Mapping[str, Any] | None = None,
) -> dict:
    macro = dict(macro or {})
    seasonal = dict(seasonal or {})
    flow = dict(flow or {})
    phase_shift = dict(phase_shift or {})

    macro_dir = int(macro.get("direction", 0) or 0)
    macro_phase = str(macro.get("phase", "NEUTRAL") or "NEUTRAL").upper()
    macro_active = bool(macro.get("active", False))
    edge_dir = int(seasonal.get("edge_direction", 0) or 0)
    turn_dir = int(seasonal.get("turn_direction", 0) or 0)
    flow_dir = int(flow.get("flow_direction_4w", 0) or 0) if bool(flow.get("directional_interpretation", False)) else 0
    recent = str(flow.get("recent_flow", "N/V") or "N/V").upper()

    direction = 0
    status = "MIXED · WAIT"
    reason = "Noch keine eindeutige gemeinsame COT-/Seasonality-Struktur."

    if macro_active and macro_dir != 0:
        direction = macro_dir
        if edge_dir == -macro_dir:
            status = "MACRO / SEASONAL CONFLICT"
            reason = "Aktives Makro-Regime und robuste saisonale Forward-Edge zeigen in entgegengesetzte Richtungen."
        elif edge_dir == macro_dir and flow_dir == macro_dir and turn_dir != -macro_dir:
            status = f"{direction_label(macro_dir)} STRUCTURAL ALIGNMENT"
            reason = "Aktives Makro-Regime, saisonale Forward-Edge und 4W-Producer-Flow zeigen gemeinsam."
        elif edge_dir == macro_dir:
            status = f"{direction_label(macro_dir)} MACRO + SEASONAL"
            reason = "Makro-Regime und saisonale Forward-Edge sind aligned; der 4W-Flow bestätigt noch nicht vollständig."
        else:
            status = f"{direction_label(macro_dir)} MACRO · SEASON MIXED"
            reason = "Makro-Regime ist aktiv, die saisonale Research-Ebene liefert jedoch keine robuste Bestätigung."
    elif macro_dir != 0 and macro_phase in {"EXTREME", "TRANSITION"}:
        direction = macro_dir
        if edge_dir == -macro_dir:
            status = "SEASONAL CONFLICT · WAIT"
            reason = "Der erwartete Makro-Übergang läuft gegen die robuste 40/60T-Saisonstruktur."
        elif turn_dir == macro_dir and edge_dir == macro_dir and flow_dir == macro_dir:
            status = f"EARLY {direction_label(macro_dir)} TRANSITION WATCH"
            reason = "Turn-Fenster, robuste saisonale Forward-Edge und aktiver 4W-Producer-Flow unterstützen denselben noch nicht freigegebenen Makro-Übergang."
        elif edge_dir == macro_dir and flow_dir == macro_dir:
            status = f"{direction_label(macro_dir)} STRUCTURAL BUILDUP"
            reason = "Saisonale Forward-Edge und 4W-Positionierungsflow unterstützen den erwarteten Makro-Übergang; das Turn-Fenster bestätigt noch nicht vollständig."
        elif turn_dir == macro_dir and flow_dir == macro_dir:
            status = f"{direction_label(macro_dir)} TURN + FLOW WATCH"
            reason = "Saisonales Wendefenster und 4W-Producer-Flow zeigen gemeinsam; die 40/60T-Robustheit ist noch gemischt."
        else:
            status = f"{direction_label(macro_dir)} MACRO WATCH · MIXED"
            reason = "Makro befindet sich vor dem Release; Seasonality und Positionierungsflow liefern noch kein gemeinsames Bild."
    elif edge_dir != 0 and flow_dir == edge_dir and turn_dir == edge_dir:
        direction = edge_dir
        status = f"{direction_label(edge_dir)} SEASON + FLOW RESEARCH"
        reason = "Seasonality und Producer-Flow sind aligned, aber es fehlt ein entsprechender Makro-COT-Zustand."

    if recent in {"WEAKENING", "REVERSING"}:
        status = f"{status} · FLOW {recent}"
        reason += " Der jüngste 1W/2W-Nettoflow schwächt die 4W-Struktur ab."

    if bool(phase_shift.get("usable", False)):
        reason += f" Phase Shift bleibt Timing-Modifikator: {phase_shift.get('label', '')}."

    return {
        "status": status,
        "direction": direction,
        "reason": reason,
        "macro_phase": macro_phase,
        "macro_active": macro_active,
        "macro_direction": macro_dir,
        "edge_direction": edge_dir,
        "turn_direction": turn_dir,
        "flow_direction": flow_dir,
        "recent_flow": recent,
    }
# ---------------------------------------------------------------------------
# V3.22.8 · MULTI-GROUP FLOW PATH
# Research-only extension. No production score and no Watchlist coupling.
# ---------------------------------------------------------------------------

GROUP_ROLES = {
    "tff": [
        {
            "key": "dealer",
            "label": "Dealer / Intermediary",
            "role": "INTERMEDIARY CONTEXT",
            "directional": False,
            "turn_role": "context",
        },
        {
            "key": "asset_manager",
            "label": "Asset Manager",
            "role": "INSTITUTIONAL FLOW",
            "directional": True,
            "turn_role": "institutional",
        },
        {
            "key": "leveraged_funds",
            "label": "Leveraged Funds",
            "role": "SPECULATIVE FLOW",
            "directional": True,
            "turn_role": "speculative",
        },
        {
            "key": "nonreportable",
            "label": "Nonreportable",
            "role": "RESIDUAL / CONTRARIAN CONTEXT",
            "directional": False,
            "turn_role": "residual",
        },
    ],
    "disaggregated": [
        {
            "key": "producer",
            "label": "Producer / Merchant",
            "role": "HEDGER / COMMERCIAL FLOW",
            "directional": True,
            "turn_role": "commercial",
        },
        {
            "key": "managed_money",
            "label": "Managed Money",
            "role": "SPECULATIVE FLOW",
            "directional": True,
            "turn_role": "speculative",
        },
        {
            "key": "swap",
            "label": "Swap Dealer",
            "role": "SWAP / INTERMEDIARY CONTEXT",
            "directional": False,
            "turn_role": "context",
        },
        {
            "key": "nonreportable",
            "label": "Nonreportable",
            "role": "RESIDUAL / CONTRARIAN CONTEXT",
            "directional": False,
            "turn_role": "residual",
        },
    ],
}


def _flow_segment(
    longs: pd.Series,
    shorts: pd.Series,
    net_oi: pd.Series,
    start_idx: int,
    end_idx: int,
    label: str,
) -> dict:
    long_delta = float(longs.iloc[end_idx] - longs.iloc[start_idx])
    short_delta = float(shorts.iloc[end_idx] - shorts.iloc[start_idx])
    net_delta = float(long_delta - short_delta)
    net_oi_delta = float(net_oi.iloc[end_idx] - net_oi.iloc[start_idx])

    if net_delta > 0:
        direction = 1
        if long_delta > 0 and short_delta < 0:
            mechanics = "LONG BUILD + SHORT COVERING"
            strength = "STRONG BULLISH"
        elif long_delta > 0 and short_delta >= 0:
            mechanics = "TWO-SIDED BUILD · LONGS DOMINATE"
            strength = "BULLISH"
        elif long_delta <= 0 and short_delta < 0:
            mechanics = "TWO-SIDED REDUCTION · SHORTS FALL FASTER"
            strength = "BULLISH DELEVERAGING"
        else:
            mechanics = "NET BULLISH"
            strength = "BULLISH"
    elif net_delta < 0:
        direction = -1
        if long_delta < 0 and short_delta > 0:
            mechanics = "LONG LIQUIDATION + SHORT BUILD"
            strength = "STRONG BEARISH"
        elif long_delta <= 0 and short_delta > 0:
            mechanics = "SHORT BUILD"
            strength = "BEARISH"
        elif long_delta < 0 and short_delta <= 0:
            mechanics = "TWO-SIDED REDUCTION · LONGS FALL FASTER"
            strength = "BEARISH DELEVERAGING"
        elif long_delta > 0 and short_delta > 0:
            mechanics = "TWO-SIDED BUILD · SHORTS DOMINATE"
            strength = "SLIGHT BEARISH"
        else:
            mechanics = "NET BEARISH"
            strength = "BEARISH"
    else:
        direction = 0
        if long_delta > 0 and short_delta > 0:
            mechanics = "BALANCED TWO-SIDED BUILD"
        elif long_delta < 0 and short_delta < 0:
            mechanics = "BALANCED TWO-SIDED REDUCTION"
        else:
            mechanics = "FLAT NET FLOW"
        strength = "NEUTRAL"

    return {
        "segment": label,
        "long_delta": long_delta,
        "short_delta": short_delta,
        "net_delta": net_delta,
        "net_oi_delta": net_oi_delta,
        "direction": int(direction),
        "mechanics": mechanics,
        "strength": strength,
    }


def _flow_sequence_label(segments: list[dict]) -> str:
    if not segments:
        return "N/V"

    dirs = [int(row.get("direction", 0) or 0) for row in segments]
    mechanics = [str(row.get("mechanics", "")) for row in segments]

    early = dirs[0]
    middle = dirs[1] if len(dirs) > 1 else 0
    recent = dirs[-1]

    if early > 0 and middle < 0:
        if recent < 0:
            return "BULLISH → BEARISH REVERSAL → BEARISH"
        if recent == 0:
            return "BULLISH → BEARISH REVERSAL → STALLING"
        if "SHORTS DOMINATE" in mechanics[-1]:
            return "BULLISH → BEARISH REVERSAL → TWO-SIDED BEARISH"
        return "BULLISH → BEARISH REVERSAL → REBOUND"

    if early < 0 and middle > 0:
        if recent > 0:
            return "BEARISH → BULLISH REVERSAL → BULLISH"
        if recent == 0:
            return "BEARISH → BULLISH REVERSAL → STALLING"
        return "BEARISH → BULLISH REVERSAL → PULLBACK"

    if early > 0 and middle > 0 and recent > 0:
        return "PERSISTENT BULLISH BUILDUP"

    if early < 0 and middle < 0 and recent < 0:
        return "PERSISTENT BEARISH BUILDUP"

    if recent > 0:
        return "RECENT BULLISH SHIFT"

    if recent < 0:
        return "RECENT BEARISH SHIFT"

    return "MIXED / TWO-SIDED"


def build_group_flow_map(
    enriched: pd.DataFrame,
    report_type: str,
) -> dict:
    """Build non-overlapping chronological flow paths for all relevant groups."""
    report_type = str(report_type)
    specs = list(GROUP_ROLES.get(report_type, []))

    result = {
        "available": False,
        "report_type": report_type,
        "groups": {},
        "group_order": [spec["key"] for spec in specs],
    }

    if enriched is None or enriched.empty or len(enriched) < 5:
        return result

    x = enriched.copy()

    if "report_date" not in x.columns or "open_interest_all" not in x.columns:
        return result

    x["report_date"] = pd.to_datetime(
        x["report_date"],
        errors="coerce",
    )
    x = (
        x.dropna(subset=["report_date"])
        .sort_values("report_date")
        .reset_index(drop=True)
    )

    if len(x) < 5:
        return result

    oi = pd.to_numeric(
        x["open_interest_all"],
        errors="coerce",
    ).replace(0, np.nan)

    last = len(x) - 1
    index_pairs = [
        (last - 4, last - 2, "W-4 → W-2"),
        (last - 2, last - 1, "W-2 → W-1"),
        (last - 1, last, "W-1 → NOW"),
    ]

    groups = {}

    for spec in specs:
        key = spec["key"]
        long_col = f"{key}_long"
        short_col = f"{key}_short"

        if long_col not in x.columns or short_col not in x.columns:
            continue

        longs = pd.to_numeric(
            x[long_col],
            errors="coerce",
        )
        shorts = pd.to_numeric(
            x[short_col],
            errors="coerce",
        )

        if longs.iloc[-5:].isna().any() or shorts.iloc[-5:].isna().any():
            continue

        net = longs - shorts
        net_oi = net / oi

        segments = [
            _flow_segment(
                longs,
                shorts,
                net_oi,
                start,
                end,
                label,
            )
            for start, end, label in index_pairs
        ]

        percentile = _finite(
            x.iloc[-1].get(
                f"{key}_net_oi_percentile",
                np.nan,
            )
        )

        groups[key] = {
            **spec,
            "available": True,
            "report_date": x.iloc[-1]["report_date"],
            "current_long": float(longs.iloc[-1]),
            "current_short": float(shorts.iloc[-1]),
            "current_net": float(net.iloc[-1]),
            "current_net_oi": float(net_oi.iloc[-1]),
            "net_oi_percentile": percentile,
            "segments": segments,
            "sequence_label": _flow_sequence_label(segments),
            "recent_direction": int(
                segments[-1].get("direction", 0) or 0
            ),
            "middle_direction": int(
                segments[-2].get("direction", 0) or 0
            ),
            "early_direction": int(
                segments[0].get("direction", 0) or 0
            ),
        }

    result["groups"] = groups
    result["available"] = bool(groups)
    return result


def group_flow_path_table(
    flow_map: Mapping[str, Any] | None,
) -> pd.DataFrame:
    flow_map = dict(flow_map or {})
    groups = dict(flow_map.get("groups") or {})
    order = list(flow_map.get("group_order") or groups.keys())

    rows = []
    for key in order:
        group = groups.get(key)
        if not group:
            continue

        for segment in group.get("segments", []):
            rows.append(
                {
                    "Gruppe": group.get("label", key),
                    "Rolle": group.get("role", ""),
                    "Segment": segment.get("segment", ""),
                    "Long Δ": segment.get("long_delta", np.nan),
                    "Short Δ": segment.get("short_delta", np.nan),
                    "Net Δ": segment.get("net_delta", np.nan),
                    "Net/OI Δ": segment.get("net_oi_delta", np.nan),
                    "Mechanik": segment.get("mechanics", ""),
                    "Flow": segment.get("strength", ""),
                }
            )

    return pd.DataFrame(rows)


def _group_supports_turn(
    group: Mapping[str, Any] | None,
    target_direction: int,
) -> dict:
    group = dict(group or {})
    target_direction = int(target_direction or 0)

    if not group or target_direction == 0:
        return {
            "supports": False,
            "opposes": False,
            "state": "N/V",
            "detail": "Kein aktives Turn-Ziel.",
        }

    early = int(group.get("early_direction", 0) or 0)
    middle = int(group.get("middle_direction", 0) or 0)
    recent = int(group.get("recent_direction", 0) or 0)

    supports = False
    opposes = False

    # A reversal into the seasonal turn direction is the strongest path:
    # prior flow on the opposite side, then middle/recent turns toward target.
    if early == -target_direction and middle == target_direction:
        supports = True
        state = "REVERSAL INTO TURN"
    elif middle == target_direction and recent == target_direction:
        supports = True
        state = "PERSISTENT TURN FLOW"
    elif recent == target_direction:
        supports = True
        state = "RECENT TURN FLOW"
    elif middle == -target_direction and recent == -target_direction:
        opposes = True
        state = "PERSISTENT OPPOSING FLOW"
    elif recent == -target_direction:
        opposes = True
        state = "RECENT OPPOSING FLOW"
    else:
        state = "MIXED / TWO-SIDED"

    return {
        "supports": bool(supports),
        "opposes": bool(opposes),
        "state": state,
        "detail": str(group.get("sequence_label", "N/V")),
    }


def positioning_turn_evidence(
    flow_map: Mapping[str, Any] | None,
    turn_direction: int,
    *,
    residual_upper: float = 80.0,
    residual_lower: float = 20.0,
) -> dict:
    """Role-based turn evidence without adding group positions together.

    TFF:
      Asset Manager = institutional flow
      Leveraged Funds = speculative flow
      Dealer = intermediary context only
      Nonreportable = residual contrarian context only at extremes

    Disaggregated:
      Producer/Merchant = commercial flow
      Managed Money = speculative flow
      Swap = intermediary context only
      Nonreportable = residual contrarian context only at extremes
    """
    flow_map = dict(flow_map or {})
    groups = dict(flow_map.get("groups") or {})
    report_type = str(flow_map.get("report_type", ""))
    target = int(turn_direction or 0)

    turn_name = (
        "BOTTOMING"
        if target > 0
        else "TOPPING"
        if target < 0
        else "NO TURN"
    )

    base = {
        "available": bool(groups) and target != 0,
        "turn_direction": target,
        "turn_name": turn_name,
        "quality": "N/V",
        "label": f"{turn_name} EVIDENCE · N/V",
        "supporting_roles": [],
        "opposing_roles": [],
        "neutral_roles": [],
        "role_checks": [],
        "residual_context": "N/V",
        "evidence_direction": 0,
    }

    if not groups or target == 0:
        return base

    if report_type == "tff":
        directional_keys = [
            ("asset_manager", "Asset Manager"),
            ("leveraged_funds", "Leveraged Funds"),
        ]
    else:
        directional_keys = [
            ("producer", "Producer / Merchant"),
            ("managed_money", "Managed Money"),
        ]

    support = []
    oppose = []
    neutral = []
    checks = []

    for key, label in directional_keys:
        group = groups.get(key)
        if not group:
            continue

        check = _group_supports_turn(
            group,
            target,
        )
        checks.append(
            {
                "group": label,
                "role": group.get("role", ""),
                **check,
            }
        )

        if check["supports"]:
            support.append(label)
        elif check["opposes"]:
            oppose.append(label)
        else:
            neutral.append(label)

    residual = groups.get("nonreportable")
    residual_context = "N/V"

    if residual:
        pct = _finite(
            residual.get(
                "net_oi_percentile",
                np.nan,
            )
        )

        if np.isfinite(pct):
            # At a seasonal TOP, unusually high residual net-long positioning
            # is contrarian support. At a BOTTOM, unusually low positioning is.
            if target < 0 and pct >= float(residual_upper):
                residual_context = (
                    f"CONTRARIAN TOP SUPPORT · {pct:.1f}. %ile"
                )
                support.append("Nonreportable Extreme")
            elif target > 0 and pct <= float(residual_lower):
                residual_context = (
                    f"CONTRARIAN BOTTOM SUPPORT · {pct:.1f}. %ile"
                )
                support.append("Nonreportable Extreme")
            elif target < 0 and pct <= float(residual_lower):
                residual_context = (
                    f"OPPOSES TOP · {pct:.1f}. %ile"
                )
                oppose.append("Nonreportable Extreme")
            elif target > 0 and pct >= float(residual_upper):
                residual_context = (
                    f"OPPOSES BOTTOM · {pct:.1f}. %ile"
                )
                oppose.append("Nonreportable Extreme")
            else:
                residual_context = (
                    f"NEUTRAL RESIDUAL · {pct:.1f}. %ile"
                )

    # Transparent rule hierarchy, not a weighted score.
    directional_support = sum(
        1
        for name in support
        if name != "Nonreportable Extreme"
    )
    directional_oppose = sum(
        1
        for name in oppose
        if name != "Nonreportable Extreme"
    )
    residual_support = "Nonreportable Extreme" in support

    if directional_support >= 2 and directional_oppose == 0:
        quality = "STRONG"
        evidence_direction = target
    elif directional_support >= 1 and directional_oppose == 0:
        quality = (
            "MODERATE+"
            if residual_support
            else "MODERATE"
        )
        evidence_direction = target
    elif directional_oppose >= 2 and directional_support == 0:
        quality = "OPPOSED"
        evidence_direction = -target
    elif directional_support and directional_oppose:
        quality = "MIXED"
        evidence_direction = 0
    elif residual_support:
        quality = "WEAK"
        evidence_direction = target
    else:
        quality = "WEAK / MIXED"
        evidence_direction = 0

    return {
        **base,
        "quality": quality,
        "label": f"{turn_name} EVIDENCE · {quality}",
        "supporting_roles": support,
        "opposing_roles": oppose,
        "neutral_roles": neutral,
        "role_checks": checks,
        "residual_context": residual_context,
        "evidence_direction": int(evidence_direction),
    }


def positioning_transition_summary(
    flow_map: Mapping[str, Any] | None,
    evidence: Mapping[str, Any] | None,
) -> str:
    flow_map = dict(flow_map or {})
    evidence = dict(evidence or {})
    groups = dict(flow_map.get("groups") or {})

    parts = []

    for key in (
        "asset_manager",
        "leveraged_funds",
        "producer",
        "managed_money",
    ):
        group = groups.get(key)
        if not group:
            continue
        parts.append(
            f"{group.get('label')}: {group.get('sequence_label', 'N/V')}"
        )

    residual = str(
        evidence.get(
            "residual_context",
            "N/V",
        )
    )
    if residual != "N/V":
        parts.append(f"Nonreportable: {residual}")

    return " · ".join(parts) if parts else "Kein Multi-Group-Flow verfügbar."
# ---------------------------------------------------------------------------
# V3.22.9 · SIMPLE TURN VIEW
# Three-group research read:
# Commercial side + Momentum Funds + Nonreportables versus Seasonal Turn.
# ---------------------------------------------------------------------------

def _window_mechanics_from_deltas(
    long_delta: float,
    short_delta: float,
) -> dict:
    long_delta = float(long_delta)
    short_delta = float(short_delta)
    net_delta = float(long_delta - short_delta)

    if net_delta > 0:
        direction = 1
        if long_delta > 0 and short_delta < 0:
            label = "STRONG BULLISH"
            mechanics = "Long-Aufbau + Short-Covering"
        elif long_delta > 0 and short_delta > 0:
            label = "BULLISH" if long_delta > short_delta else "MIXED"
            mechanics = "Beide Seiten bauen auf"
        elif long_delta <= 0 and short_delta < 0:
            label = "BULLISH DELEVERAGING"
            mechanics = "Shorts fallen stärker"
        else:
            label = "BULLISH"
            mechanics = "Netto bullish"
    elif net_delta < 0:
        direction = -1
        if long_delta < 0 and short_delta > 0:
            label = "STRONG BEARISH"
            mechanics = "Long-Liquidation + Short-Aufbau"
        elif long_delta > 0 and short_delta > 0:
            label = "SLIGHT BEARISH"
            mechanics = "Beide Seiten bauen auf · Shorts stärker"
        elif long_delta < 0 and short_delta <= 0:
            label = "BEARISH DELEVERAGING"
            mechanics = "Longs fallen stärker"
        elif short_delta > 0:
            label = "BEARISH"
            mechanics = "Short-Aufbau"
        else:
            label = "BEARISH"
            mechanics = "Netto bearish"
    else:
        direction = 0
        if long_delta > 0 and short_delta > 0:
            label = "TWO-SIDED"
            mechanics = "Beide Seiten bauen gleich stark auf"
        elif long_delta < 0 and short_delta < 0:
            label = "DELEVERAGING"
            mechanics = "Beide Seiten reduzieren"
        else:
            label = "NEUTRAL"
            mechanics = "Netto unverändert"

    return {
        "direction": int(direction),
        "label": label,
        "mechanics": mechanics,
        "long_delta": long_delta,
        "short_delta": short_delta,
        "net_delta": net_delta,
    }


def group_4w_2w_1w_summary(
    group: Mapping[str, Any] | None,
) -> dict:
    """Convert non-overlapping V3.22.8 segments into intuitive 4W/2W/1W views."""
    group = dict(group or {})
    segments = list(group.get("segments") or [])

    base = {
        "available": False,
        "group_label": str(group.get("label", "N/V")),
        "role": str(group.get("role", "")),
        "percentile": _finite(group.get("net_oi_percentile", np.nan)),
        "w4": {},
        "w2": {},
        "w1": {},
        "evolution": "N/V",
    }

    if len(segments) != 3:
        return base

    def aggregate(items):
        long_delta = float(
            sum(float(row.get("long_delta", 0.0) or 0.0) for row in items)
        )
        short_delta = float(
            sum(float(row.get("short_delta", 0.0) or 0.0) for row in items)
        )
        result = _window_mechanics_from_deltas(
            long_delta,
            short_delta,
        )
        result["net_oi_delta"] = float(
            sum(float(row.get("net_oi_delta", 0.0) or 0.0) for row in items)
        )
        return result

    w4 = aggregate(segments)
    w2 = aggregate(segments[-2:])
    w1 = aggregate(segments[-1:])

    d4 = int(w4["direction"])
    d2 = int(w2["direction"])
    d1 = int(w1["direction"])

    if d4 > 0 and d2 < 0:
        if d1 < 0:
            evolution = "BULLISH → BEARISH REVERSAL"
        elif d1 == 0:
            evolution = "BULLISH → BEARISH → STALLING"
        else:
            evolution = "BULLISH → BEARISH → REBOUND"
    elif d4 < 0 and d2 > 0:
        if d1 > 0:
            evolution = "BEARISH → BULLISH REVERSAL"
        elif d1 == 0:
            evolution = "BEARISH → BULLISH → STALLING"
        else:
            evolution = "BEARISH → BULLISH → PULLBACK"
    elif d4 > 0 and d2 > 0 and d1 > 0:
        evolution = "PERSISTENT BULLISH"
    elif d4 < 0 and d2 < 0 and d1 < 0:
        evolution = "PERSISTENT BEARISH"
    elif d2 < 0 and d1 < 0:
        evolution = "RECENT BEARISH"
    elif d2 > 0 and d1 > 0:
        evolution = "RECENT BULLISH"
    else:
        evolution = "MIXED / TRANSITION"

    return {
        **base,
        "available": True,
        "w4": w4,
        "w2": w2,
        "w1": w1,
        "evolution": evolution,
    }


def simple_turn_group_selection(
    flow_map: Mapping[str, Any] | None,
) -> dict:
    flow_map = dict(flow_map or {})
    report_type = str(flow_map.get("report_type", ""))
    groups = dict(flow_map.get("groups") or {})

    if report_type == "tff":
        commercial_key = "dealer"
        momentum_key = "leveraged_funds"
        asset_manager_key = "asset_manager"
        commercial_note = (
            "Dealer / Intermediary · TFF-Kontext, nicht identisch mit "
            "Producer/Merchant bei Rohstoffen"
        )
        momentum_note = "Leveraged Funds · spekulativer Momentum-/Trend-Flow"
    else:
        commercial_key = "producer"
        momentum_key = "managed_money"
        asset_manager_key = None
        commercial_note = "Producer / Merchant · Commercial/Hedger-Flow"
        momentum_note = "Managed Money · spekulativer Momentum-/Trend-Flow"

    return {
        "report_type": report_type,
        "commercial": group_4w_2w_1w_summary(
            groups.get(commercial_key)
        ),
        "commercial_key": commercial_key,
        "commercial_note": commercial_note,
        "momentum": group_4w_2w_1w_summary(
            groups.get(momentum_key)
        ),
        "momentum_key": momentum_key,
        "momentum_note": momentum_note,
        "nonreportable": group_4w_2w_1w_summary(
            groups.get("nonreportable")
        ),
        "asset_manager": (
            group_4w_2w_1w_summary(groups.get(asset_manager_key))
            if asset_manager_key
            else {"available": False}
        ),
    }


def seasonal_turn_robustness(
    seasonal: Mapping[str, Any] | None,
) -> dict:
    seasonal = dict(seasonal or {})
    turn_direction = int(
        seasonal.get("turn_direction", 0) or 0
    )
    turn_type = str(
        seasonal.get("turn_type", "N/V") or "N/V"
    ).upper()
    distance = seasonal.get("turn_distance_days")

    h40 = dict(seasonal.get("h40") or {})
    h60 = dict(seasonal.get("h60") or {})

    d40 = int(h40.get("direction", 0) or 0)
    d60 = int(h60.get("direction", 0) or 0)
    q40 = str(h40.get("quality", "N/V") or "N/V").upper()
    q60 = str(h60.get("quality", "N/V") or "N/V").upper()

    if turn_direction == 0:
        quality = "NO ACTIVE TURN"
    elif (
        d40 == turn_direction
        and d60 == turn_direction
        and q40 == "ROBUST"
        and q60 == "ROBUST"
    ):
        quality = "ROBUST"
    elif (
        (
            d40 == turn_direction and q40 == "ROBUST"
        )
        or (
            d60 == turn_direction and q60 == "ROBUST"
        )
    ) and d40 != -turn_direction and d60 != -turn_direction:
        quality = "SUPPORTED"
    elif d40 == -turn_direction and d60 == -turn_direction:
        quality = "CONFLICT"
    else:
        quality = "MIXED"

    return {
        "turn_direction": turn_direction,
        "turn_type": turn_type,
        "distance_days": distance,
        "quality": quality,
        "h40": h40,
        "h60": h60,
    }


def _direct_group_turn_read(
    summary: Mapping[str, Any] | None,
    target_direction: int,
) -> dict:
    summary = dict(summary or {})
    target = int(target_direction or 0)

    if not summary.get("available") or target == 0:
        return {
            "state": "N/V",
            "supports": False,
            "opposes": False,
            "reason": "Keine auswertbare Gruppe.",
        }

    w4 = int(
        dict(summary.get("w4") or {}).get("direction", 0) or 0
    )
    w2 = int(
        dict(summary.get("w2") or {}).get("direction", 0) or 0
    )
    w1 = int(
        dict(summary.get("w1") or {}).get("direction", 0) or 0
    )

    # Recent 2W/1W matter more for a turn than the older 4W structure.
    if w2 == target and w1 == target:
        state = "SUPPORTS TURN"
        supports = True
        opposes = False
    elif w4 == -target and w2 == target:
        state = "REVERSAL INTO TURN"
        supports = True
        opposes = False
    elif w1 == target and w2 != -target:
        state = "EARLY SUPPORT"
        supports = True
        opposes = False
    elif w2 == -target and w1 == -target:
        state = "OPPOSES TURN"
        supports = False
        opposes = True
    elif w1 == -target:
        state = "RECENTLY OPPOSES"
        supports = False
        opposes = True
    else:
        state = "MIXED / TRANSITION"
        supports = False
        opposes = False

    return {
        "state": state,
        "supports": supports,
        "opposes": opposes,
        "reason": str(summary.get("evolution", "N/V")),
    }


def _nonreportable_turn_read(
    summary: Mapping[str, Any] | None,
    target_direction: int,
    *,
    upper: float = 80.0,
    lower: float = 20.0,
) -> dict:
    """Contrarian read: nonreportables support a turn when positioned into the old move."""
    summary = dict(summary or {})
    target = int(target_direction or 0)

    if not summary.get("available") or target == 0:
        return {
            "state": "N/V",
            "supports": False,
            "opposes": False,
            "reason": "Kein Nonreportable-Kontext.",
        }

    w2 = int(
        dict(summary.get("w2") or {}).get("direction", 0) or 0
    )
    w1 = int(
        dict(summary.get("w1") or {}).get("direction", 0) or 0
    )
    pct = _finite(summary.get("percentile", np.nan))

    # At a TOP (target=-1), bullish nonreportable chasing is contrarian support.
    # At a BOTTOM (target=+1), bearish nonreportable chasing is contrarian support.
    contrarian_direction = -target

    flow_support = (
        w1 == contrarian_direction
        or w2 == contrarian_direction
    )

    extreme_support = False
    extreme_oppose = False

    if np.isfinite(pct):
        if target < 0:
            extreme_support = pct >= float(upper)
            extreme_oppose = pct <= float(lower)
        else:
            extreme_support = pct <= float(lower)
            extreme_oppose = pct >= float(upper)

    if extreme_support and flow_support:
        state = "STRONG CONTRARIAN SUPPORT"
        supports = True
        opposes = False
    elif extreme_support or flow_support:
        state = "CONTRARIAN SUPPORT"
        supports = True
        opposes = False
    elif extreme_oppose:
        state = "CONTRARIANLY OPPOSES"
        supports = False
        opposes = True
    else:
        state = "NEUTRAL / MIXED"
        supports = False
        opposes = False

    pct_text = (
        f"{pct:.1f}. %ile"
        if np.isfinite(pct)
        else "Percentile N/V"
    )

    return {
        "state": state,
        "supports": supports,
        "opposes": opposes,
        "reason": (
            f"{summary.get('evolution', 'N/V')} · {pct_text}"
        ),
    }


def simple_cot_seasonality_turn_read(
    seasonal: Mapping[str, Any] | None,
    selected_groups: Mapping[str, Any] | None,
) -> dict:
    """Final simple research verdict. Rule hierarchy, no numeric composite score."""
    seasonal_read = seasonal_turn_robustness(seasonal)
    selected = dict(selected_groups or {})
    target = int(
        seasonal_read.get("turn_direction", 0) or 0
    )

    commercial = _direct_group_turn_read(
        selected.get("commercial"),
        target,
    )
    momentum = _direct_group_turn_read(
        selected.get("momentum"),
        target,
    )
    residual = _nonreportable_turn_read(
        selected.get("nonreportable"),
        target,
    )

    turn_type = str(
        seasonal_read.get("turn_type", "N/V")
    )
    turn_word = (
        "TOP"
        if target < 0
        else "BOTTOM"
        if target > 0
        else "TURN"
    )
    direction_word = (
        "BEARISH"
        if target < 0
        else "BULLISH"
        if target > 0
        else "NEUTRAL"
    )

    supporters = []
    opponents = []

    for name, read in (
        ("Commercial-Seite", commercial),
        ("Momentum-Funds", momentum),
        ("Nonreportables", residual),
    ):
        if read["supports"]:
            supporters.append(name)
        if read["opposes"]:
            opponents.append(name)

    season_quality = str(
        seasonal_read.get("quality", "MIXED")
    )

    # Hierarchy:
    # Robust seasonality + both directional groups = strongest.
    # Nonreportables are supporting context, never sufficient alone.
    if target == 0:
        quality = "NO ACTIVE TURN"
        verdict = "KEIN AKTIVES TOP/BOTTOM"
    elif season_quality == "CONFLICT":
        quality = "CONFLICT"
        verdict = f"{turn_word} NICHT BESTÄTIGT"
    elif (
        season_quality == "ROBUST"
        and commercial["supports"]
        and momentum["supports"]
        and not opponents
    ):
        quality = "STRONG"
        verdict = f"{direction_word} {turn_word} EVIDENCE · STRONG"
    elif (
        season_quality in {"ROBUST", "SUPPORTED"}
        and momentum["supports"]
        and (
            commercial["supports"]
            or residual["supports"]
        )
        and not (
            commercial["opposes"]
            or momentum["opposes"]
        )
    ):
        quality = "MODERATE+"
        verdict = f"{direction_word} {turn_word} EVIDENCE · MODERATE+"
    elif (
        season_quality in {"ROBUST", "SUPPORTED", "MIXED"}
        and (
            commercial["supports"]
            or momentum["supports"]
        )
        and not (
            commercial["opposes"]
            and momentum["opposes"]
        )
    ):
        quality = "MODERATE"
        verdict = f"{direction_word} {turn_word} EVIDENCE · MODERATE"
    elif commercial["opposes"] and momentum["opposes"]:
        quality = "WEAK / OPPOSED"
        verdict = f"{turn_word} POSITIONING WIDERSPRICHT"
    else:
        quality = "MIXED"
        verdict = f"{turn_word} EVIDENCE · MIXED"

    return {
        "verdict": verdict,
        "quality": quality,
        "direction": target,
        "turn_type": turn_type,
        "seasonality": seasonal_read,
        "commercial": commercial,
        "momentum": momentum,
        "nonreportable": residual,
        "supporters": supporters,
        "opponents": opponents,
    }
