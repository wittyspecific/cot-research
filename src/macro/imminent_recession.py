
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .config import MacroConfig


def _latest(frame: pd.DataFrame, column: str):
    if frame is None or frame.empty or column not in frame.columns:
        return None
    clean = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(clean.iloc[-1]) if not clean.empty else None


def _score(weekly_scores: pd.DataFrame, name: str):
    return _latest(weekly_scores, name)


def _raw(weekly_raw: pd.DataFrame, name: str):
    return _latest(weekly_raw, name)


def _curve_resteepening(
    weekly_raw: pd.DataFrame,
    config: MacroConfig,
) -> tuple[bool, dict[str, Any]]:
    required = (
        "10Y-2Y Yield Spread",
        "10Y-3M Yield Spread",
    )
    if any(name not in weekly_raw.columns for name in required):
        return False, {"available": False}

    s102 = pd.to_numeric(
        weekly_raw["10Y-2Y Yield Spread"],
        errors="coerce",
    )
    s103 = pd.to_numeric(
        weekly_raw["10Y-3M Yield Spread"],
        errors="coerce",
    )

    curve = pd.concat(
        [s102.rename("s102"), s103.rename("s103")],
        axis=1,
    ).min(axis=1).dropna()

    if curve.empty:
        return False, {"available": False}

    prior = curve.tail(104)
    trough = float(prior.min())
    current = float(curve.iloc[-1])
    recovery_bp = (current - trough) * 100.0
    threshold_bp = float(
        config.section("imminent").get(
            "restepening_bp",
            50.0,
        )
    )

    active = bool(
        trough < 0.0
        and recovery_bp >= threshold_bp
    )

    return active, {
        "available": True,
        "current_spread": current,
        "prior_trough": trough,
        "restepening_bp": recovery_bp,
        "threshold_bp": threshold_bp,
    }


def evaluate_imminent_recession(
    *,
    cycle_phase: str,
    weekly_scores: pd.DataFrame,
    weekly_raw: pd.DataFrame,
    cycle_history: pd.DataFrame,
    config: MacroConfig,
) -> dict[str, Any]:
    cfg = config.section("imminent")

    gated = cycle_phase == "SLOWDOWN"

    short_rate = _score(
        weekly_scores,
        "US2Y Change 13W",
    )
    claims4 = _score(
        weekly_scores,
        "Initial Claims 4W",
    )
    claims13 = _score(
        weekly_scores,
        "Initial Claims 13W",
    )
    unemp6 = _score(
        weekly_scores,
        "Unemployment 6M Change",
    )
    cont13 = _score(
        weekly_scores,
        "Continuing Claims 13W",
    )
    payroll = _score(
        weekly_scores,
        "Payroll 3M Average Change",
    )
    hy = _score(
        weekly_scores,
        "High Yield OAS 13W",
    )
    nfci = _score(
        weekly_scores,
        "NFCI 13W Change",
    )

    curve_active, curve_meta = _curve_resteepening(
        weekly_raw,
        config,
    )

    short_active = (
        short_rate is not None
        and short_rate <= float(cfg.get("short_rate_score", -35.0))
    )

    claims_candidates = [
        x
        for x in (claims4, claims13)
        if x is not None
    ]
    claims_active = bool(
        claims_candidates
        and min(claims_candidates)
        <= float(cfg.get("claims_score", -20.0))
    )

    labor_candidates = [
        x
        for x in (unemp6, cont13, payroll)
        if x is not None
    ]
    labor_active = bool(
        labor_candidates
        and min(labor_candidates)
        <= float(cfg.get("labor_score", -20.0))
    )

    credit_candidates = [
        x
        for x in (hy, nfci)
        if x is not None
    ]
    credit_active = bool(
        credit_candidates
        and min(credit_candidates)
        <= float(cfg.get("credit_score", -20.0))
    )

    coincident_active = False
    coincident_meta = {"available": False}

    if cycle_history is not None and not cycle_history.empty:
        row = cycle_history.iloc[-1]
        cd = row.get("coincident_distance")
        cs = row.get("coincident_slope_13w")
        try:
            cd = float(cd)
            cs = float(cs)
            if np.isfinite(cd) and np.isfinite(cs):
                coincident_active = bool(
                    cs < 0
                    and cd
                    <= float(
                        cfg.get(
                            "coincident_distance_watch",
                            10.0,
                        )
                    )
                )
                coincident_meta = {
                    "available": True,
                    "distance": cd,
                    "slope_13w": cs,
                }
        except (TypeError, ValueError):
            pass

    criteria = [
        {
            "key": "short_rates_fall",
            "label": "Short-Term-Yields fallen",
            "active": bool(short_active) if gated else False,
            "observed": bool(short_active),
            "meta": {"US2Y_13W_score": short_rate},
        },
        {
            "key": "yield_curve_resteepens",
            "label": "Yield Curve re-steepens",
            "active": bool(curve_active) if gated else False,
            "observed": bool(curve_active),
            "meta": curve_meta,
        },
        {
            "key": "claims_accelerate",
            "label": "Claims deteriorate",
            "active": bool(claims_active) if gated else False,
            "observed": bool(claims_active),
            "meta": {
                "claims_4w_score": claims4,
                "claims_13w_score": claims13,
            },
        },
        {
            "key": "labor_weakens",
            "label": "Labor weakens",
            "active": bool(labor_active) if gated else False,
            "observed": bool(labor_active),
            "meta": {
                "unemployment_6m_score": unemp6,
                "continuing_claims_13w_score": cont13,
                "payroll_3m_score": payroll,
            },
        },
        {
            "key": "credit_deteriorates",
            "label": "Credit deteriorates",
            "active": bool(credit_active) if gated else False,
            "observed": bool(credit_active),
            "meta": {
                "hy_oas_13w_score": hy,
                "nfci_13w_score": nfci,
            },
        },
        {
            "key": "coincident_rollover",
            "label": "Coincident indicators roll over",
            "active": bool(coincident_active) if gated else False,
            "observed": bool(coincident_active),
            "meta": coincident_meta,
        },
    ]

    observed_count = sum(bool(item["observed"]) for item in criteria)
    active_count = sum(bool(item["active"]) for item in criteria)

    if not gated:
        state = "INACTIVE_OUTSIDE_SLOWDOWN"
        score = 0.0
    else:
        score = active_count / len(criteria) * 100.0
        if active_count >= 5:
            state = "IMMINENT"
        elif active_count >= 4:
            state = "BROAD"
        elif active_count >= 2:
            state = "BUILDING"
        else:
            state = "EARLY"

    return {
        "phase_gate_active": gated,
        "state": state,
        "score": float(score),
        "active_count": int(active_count),
        "observed_count": int(observed_count),
        "total": len(criteria),
        "criteria": criteria,
        "interpretation": (
            "Phase-conditional accelerator. Criteria are counted only during SLOWDOWN; "
            "outside SLOWDOWN they remain observable diagnostics but cannot declare imminent recession."
        ),
    }
