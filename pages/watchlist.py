from __future__ import annotations
# V3.14.7 · MACRO MICRO FILTERS
# V3.14.5 · FRESH MICRO TRIGGER
# V3.14.4 · STATUS AGE

# V3.14.1 compatibility markers for historical source-based regression tests:
# Mikro</b>&nbsp;= COT Index 26W · 80/20
# row.get("micro_status_age_weeks"
# f"seit {micro_age_weeks}W"
# row.get("dual_26w_direction"
# LONG ONLY
# SHORT ONLY
# Pullback abwarten
# Auf Anstieg warten
# V3.14.2 · MACRO RELEASE PRIORITY
# Der 26W-COT-Index ist aus dieser Hauptansicht entfernt
# Commercial Net Percentile 156W ist die Ausgangslage
# <th>Bias</th>
# <th>Confidence</th>
# <th>Timing</th>
# <th>Action</th>
# <th>156W Regime</th>
# <th>26W Timing</th>
# "Early FX"
# filtered["research_fx_active"].fillna(False)
# "Transition Watch"
# str.contains(
# "TRANSITION WATCH|REGIME PRESSURE"
# Commercial 156W
# COT26 C
# V3.14.1 · SLIM MACRO MICRO WATCHLIST UI V3

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

from src.config import (
    COMMERCIAL_RANGE_WEEKS,
    COT_INDEX_WEEKS,
    INDEX_LOWER,
    INDEX_UPPER,
    NET_LOWER_PERCENTILE,
    NET_UPPER_PERCENTILE,
    NET_VALIDATION_WEEKS,
    RELEASE_ACTIVE_WEEKS,
)
from src.research_informed_positioning import load_fx_research_overlay, classify_trader_overlay
from src.dual_horizon_cot import classify_watchlist_row
from src.watchlist_macro_micro import classify_macro_micro_trade
from src.positioning_regime import (
    classify_regime_stage,
    load_cross_group_context,
    load_price_structure,
)
from src.style import apply_style, empty_state, page_header
from src.watchlist import scan_classic_markets
from src.watchlist_seasonality import calculate_market_20y_multi_seasonality

apply_style()

MARKET_NAME_DE = {
    "Euro FX": "Euro",
    "British Pound": "Britisches Pfund",
    "Japanese Yen": "Japanischer Yen",
    "Swiss Franc": "Schweizer Franken",
    "Canadian Dollar": "Kanadischer Dollar",
    "Australian Dollar": "Australischer Dollar",
    "New Zealand Dollar": "Neuseeland-Dollar",
    "Mexican Peso": "Mexikanischer Peso",
    "U.S. Dollar Index": "US-Dollar-Index",
    "Brazilian Real": "Brasilianischer Real",
    "South African Rand": "Südafrikanischer Rand",
    "Bitcoin": "Bitcoin",
    "Ether": "Ethereum / Ether",
    "WTI Crude Oil": "WTI-Rohöl",
    "Brent Crude Oil": "Brent-Rohöl",
    "Natural Gas": "Erdgas",
    "RBOB Gasoline": "RBOB-Benzin",
    "Heating Oil / ULSD": "Heizöl / ULSD",
    "Gold": "Gold",
    "Silver": "Silber",
    "Copper": "Kupfer",
    "Platinum": "Platin",
    "Palladium": "Palladium",
    "Corn": "Mais",
    "Wheat (SRW)": "Weizen (SRW)",
    "Wheat (HRW)": "Weizen (HRW)",
    "Wheat (HR Spring)": "Weizen (Hard Red Spring)",
    "Rough Rice": "Rough Rice",
    "Canola": "Canola",
    "Soybeans": "Sojabohnen",
    "Soybean Meal": "Sojaschrot",
    "Soybean Oil": "Sojaöl",
    "Live Cattle": "Lebendrind",
    "Feeder Cattle": "Mastrind",
    "Lean Hogs": "Magere Schweine",
    "Coffee C": "Kaffee C",
    "Cocoa": "Kakao",
    "Sugar No. 11": "Zucker Nr. 11",
    "Cotton No. 2": "Baumwolle Nr. 2",
    "Orange Juice": "Orangensaft",
    "Lumber": "Bauholz / Lumber",
    "U.S. Treasury 2Y Note": "US Treasury 2Y",
    "U.S. Treasury 5Y Note": "US Treasury 5Y",
    "U.S. Treasury 10Y Note": "US Treasury 10Y",
    "U.S. Treasury Bond 30Y": "US Treasury 30Y",
    "Ultra U.S. Treasury Bond": "Ultra US Treasury Bond",
    "VIX Futures": "VIX Futures",
    "E-mini S&P 500": "E-mini S&P 500",
    "E-mini Nasdaq-100": "E-mini Nasdaq-100",
    "E-mini Dow": "E-mini Dow",
    "E-mini Russell 2000": "E-mini Russell 2000",
}

STAGE_ORDER = {
    "CONTEXT READY": 5,
    "REGIME CONFIRMED": 4,
    "CROSS-GROUP SHIFT": 3,
    "IN TRANSITION": 2,
    "EXTREME WATCH": 1,
    "NORMAL": 0,
}


def de_date(value):
    if value is None or pd.isna(value):
        return "—"
    return pd.Timestamp(value).strftime("%d.%m.%Y")


def market_name_de(value):
    return MARKET_NAME_DE.get(value, value)


def _finite(value, default=np.nan):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if np.isfinite(value) else default


def _fmt(value, digits=1):
    value = _finite(value)
    return "—" if not np.isfinite(value) else f"{value:.{digits}f}"


def _tone_class(tone: str) -> str:
    return {
        "good": "rg-good",
        "warn": "rg-warn",
        "bad": "rg-bad",
        "bull": "rg-good",
        "bear": "rg-bad",
    }.get(str(tone), "rg-neutral")


def _commercial_state(row: pd.Series) -> str:
    phase = str(row.get("cycle_phase", "")).upper()
    ed = int(row.get("extreme_direction", 0) or 0)
    if phase == "RELEASE":
        return "LEAVING EXTREME"
    if phase == "EXTREME" and ed > 0:
        return "FULL HEDGE"
    if phase == "EXTREME" and ed < 0:
        return "LOWER EXTREME"
    return "NORMAL"


def _commercial_transition(row: pd.Series) -> tuple[str, str]:
    phase = str(row.get("cycle_phase", "")).upper()
    raw = str(row.get("transition_state", "") or "").upper()
    if phase == "RELEASE":
        return "CONFIRMED", "good"
    if "EARLY RELEASE" in raw:
        return "EARLY", "warn"
    if "DEEPENING" in raw:
        return "DEEPENING", "bad"
    return "WAITING", "neutral"


def _expected_direction(row: pd.Series) -> int:
    value = int(row.get("context_direction", 0) or 0)
    if value == 0:
        value = int(row.get("extreme_direction", 0) or 0)
    return int(np.sign(value))


def _direction_text(direction: int) -> str:
    return "BULLISH" if direction > 0 else "BEARISH" if direction < 0 else "NEUTRAL"


def _commercial_toward_release(row: pd.Series) -> bool:
    phase = str(row.get("cycle_phase", "")).upper()
    return phase == "RELEASE" or "EARLY RELEASE" in str(row.get("transition_state", "")).upper()


def _season_context(row: pd.Series, expected_direction: int) -> dict:
    if not str(row.get("ticker", "") or "").strip() or expected_direction == 0:
        return {"compact": "—", "overall": "N/V", "overall_rank": 0, "detail": "Kein Preis-Ticker"}
    return calculate_market_20y_multi_seasonality(
        ticker=str(row.get("ticker", "")),
        cot_direction=int(expected_direction),
    )


def _build_pipeline_rows(all_markets: pd.DataFrame) -> pd.DataFrame:
    if all_markets is None or all_markets.empty:
        return pd.DataFrame()

    active = all_markets[
        all_markets["cycle_phase"].astype(str).str.upper().isin(["EXTREME", "RELEASE"])
    ].copy()
    rows = []
    for _, row in active.iterrows():
        direction = _expected_direction(row)
        commercial_transition_active = _commercial_toward_release(row)

        # Divide & conquer: detailed CFTC groups are only queried after the
        # Commercial state itself starts to transition. Pure extremes stay cheap.
        if commercial_transition_active:
            cross = load_cross_group_context(
                str(row.get("asset_class", "")),
                str(row.get("cftc_code", "")),
                direction,
            )
        else:
            cross = {
                "institutional_label": "Asset Manager / Producer",
                "trend_label": "Leveraged / Managed Money",
                "institutional": {},
                "trend": {},
                "nonreportable": {},
                "nonreportable_percentile": np.nan,
                "error": None,
            }

        preliminary = classify_regime_stage(
            cycle_phase=str(row.get("cycle_phase", "")),
            commercial_transition=str(row.get("transition_state", "")),
            institutional=cross.get("institutional"),
            trend=cross.get("trend"),
            nonreportable=cross.get("nonreportable"),
            price=None,
        )

        # Price and seasonality are intentionally late-stage context. They are
        # not downloaded for a static Commercial extreme.
        if preliminary["stage"] >= 3:
            price = load_price_structure(str(row.get("ticker", "")), direction)
            season = _season_context(row, direction)
        else:
            price = {"label": "WARTET", "tone": "neutral", "confirming": False}
            season = {"compact": "—", "overall": "WARTET", "overall_rank": 0, "detail": "Erst nach Cross-Group Shift"}

        stage = classify_regime_stage(
            cycle_phase=str(row.get("cycle_phase", "")),
            commercial_transition=str(row.get("transition_state", "")),
            institutional=cross.get("institutional"),
            trend=cross.get("trend"),
            nonreportable=cross.get("nonreportable"),
            price=price,
        )

        inst = dict(cross.get("institutional") or {})
        trend = dict(cross.get("trend") or {})
        nr = dict(cross.get("nonreportable") or {})
        trans_label, trans_tone = _commercial_transition(row)

        rows.append({
            **row.to_dict(),
            "expected_direction": direction,
            "direction_label": _direction_text(direction),
            "commercial_state_ui": _commercial_state(row),
            "commercial_transition_ui": trans_label,
            "commercial_transition_tone": trans_tone,
            "institutional_label": cross.get("institutional_label", "Institutionell"),
            "institutional_pct": inst.get("percentile", np.nan),
            "institutional_delta_1w": inst.get("delta_1w", np.nan),
            "institutional_delta_2w": inst.get("delta_2w", np.nan),
            "institutional_delta_4w": inst.get("delta_4w", np.nan),
            "institutional_trend": inst.get("label", "WARTET"),
            "institutional_tone": inst.get("tone", "neutral"),
            "institutional_aligned": bool(inst.get("aligned", False)),
            "trend_group_label": cross.get("trend_label", "Trend-Funds"),
            "trend_pct": trend.get("percentile", np.nan),
            "trend_delta_1w": trend.get("delta_1w", np.nan),
            "trend_delta_2w": trend.get("delta_2w", np.nan),
            "trend_delta_4w": trend.get("delta_4w", np.nan),
            "trend_group_state": trend.get("label", "WARTET"),
            "trend_group_tone": trend.get("tone", "neutral"),
            "trend_group_aligned": bool(trend.get("aligned", False)),
            "nonreportable_pct": cross.get("nonreportable_percentile", np.nan),
            "nonreportable_state": nr.get("label", "WARTET"),
            "nonreportable_tone": nr.get("tone", "neutral"),
            "nonreportable_contrarian": bool(nr.get("contrarian", False)),
            "price_state": price.get("label", "—"),
            "price_tone": price.get("tone", "neutral"),
            "price_confirming": bool(price.get("confirming", False)),
            "season_compact": season.get("compact", "—"),
            "season_overall": season.get("overall", "N/V"),
            "season_rank": int(season.get("overall_rank", 0) or 0),
            "season_detail": season.get("detail", ""),
            "regime_stage": int(stage["stage"]),
            "regime_status": stage["label"],
            "regime_tone": stage["tone"],
            "cross_group_error": cross.get("error"),
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["_abs_commercial_extreme"] = (pd.to_numeric(out["commercial_net_percentile"], errors="coerce") - 50.0).abs()
    return out.sort_values(
        ["regime_stage", "_abs_commercial_extreme", "market_name"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def _build_fx_early_research_watch(
    all_markets: pd.DataFrame,
    pipeline: pd.DataFrame,
) -> pd.DataFrame:
    if all_markets is None or all_markets.empty:
        return pd.DataFrame()

    stage_lookup = {}
    if pipeline is not None and not pipeline.empty:
        for _, pr in pipeline.iterrows():
            stage_lookup[str(pr.get("symbol", ""))] = {
                "stage": int(pr.get("regime_stage", 0) or 0),
                "price_confirming": bool(pr.get("price_confirming", False)),
            }

    rows = []
    fx = all_markets[all_markets["asset_class"].astype(str).eq("Currencies")].copy()
    for _, row in fx.iterrows():
        research = load_fx_research_overlay(
            str(row.get("asset_class", "")),
            str(row.get("cftc_code", "")),
        )
        if not bool(research.get("calibrated", False)):
            continue
        if not bool(research.get("active", False)):
            continue
        if not (
            bool(research.get("flow_aligned_1w", False))
            or bool(research.get("flow_aligned_2w", False))
        ):
            continue

        symbol = str(row.get("symbol", ""))
        stage_info = stage_lookup.get(symbol, {"stage": 0, "price_confirming": False})
        legacy_release = str(row.get("cycle_phase", "")).upper() == "RELEASE"
        trader = classify_trader_overlay(
            research,
            regime_stage=int(stage_info["stage"]),
            legacy_release=legacy_release,
            price_confirming=bool(stage_info["price_confirming"]),
        )
        rows.append({
            "Markt": f"{market_name_de(row.get('market_name', ''))} · {symbol}",
            "Bias": trader.get("bias", "—"),
            "Confidence": trader.get("confidence", "—"),
            "Timing": trader.get("timing", "—"),
            "Action": trader.get("action", "—"),
            "Dealer Net/OI 156W": research.get("dealer_net_oi_percentile_156w", np.nan),
            "Release Flow 1W": research.get("release_velocity_1w", np.nan),
            "Release Flow 2W": research.get("release_velocity_2w", np.nan),
            "_stage": int(stage_info["stage"]),
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    rank = {"CONFIRMED": 4, "DEVELOPING": 3, "EARLY": 2, "WATCH": 1}
    out["_confidence_rank"] = out["Confidence"].map(rank).fillna(0)
    return out.sort_values(
        ["_confidence_rank", "_stage", "Markt"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def _render_fx_early_research_watch(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return

    st.markdown("### Early FX Watch")
    st.caption(
        "Research-informed Zusatzansicht: TFF Dealer Net/OI 156W · soft 75/25 · "
        "Raw Release Velocity 1–2W. Sie ersetzt die bestehende 80/20-Regime-"
        "Pipeline nicht und verändert kein FTMO-Risiko."
    )
    view = df.drop(columns=["_stage", "_confidence_rank"], errors="ignore").copy()
    st.dataframe(
        view.style.format(
            {
                "Dealer Net/OI 156W": "{:.1f}",
                "Release Flow 1W": "{:+,.0f}",
                "Release Flow 2W": "{:+,.0f}",
            },
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )


def _pipeline_css():
    st.html("""
    <style>
    .rg-kpi-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:10px 0 22px}
    .rg-kpi{background:#fff;border:1px solid #e4e9f0;border-radius:12px;padding:17px 18px;min-height:92px;box-shadow:0 1px 2px rgba(15,23,42,.025)}
    .rg-kpi-label{font-size:11px;font-weight:650;color:#667085;margin-bottom:9px;letter-spacing:.01em}
    .rg-kpi-value{font-size:25px;line-height:1;font-weight:720;color:#101828}
    .rg-kpi-sub{font-size:10px;color:#98a2b3;margin-top:8px}
    .rg-note{background:#fff;border:1px solid #e4e9f0;border-radius:10px;padding:13px 15px;color:#667085;font-size:12px;margin:0 0 22px}
    .rg-stagebar{display:flex;gap:5px;margin-top:7px}.rg-stage-dot{height:6px;flex:1;border-radius:99px;background:#e7ebf0}.rg-stage-dot.on{background:#22c55e}.rg-stage-dot.warn{background:#f59e0b}.rg-stage-dot.bad{background:#ef4444}
    .rg-table-wrap{background:#fff;border:1px solid #e3e8ef;border-radius:13px;overflow-x:auto;box-shadow:0 1px 2px rgba(15,23,42,.025)}
    table.rg-table{width:100%;border-collapse:separate;border-spacing:0;min-width:1450px;font-size:11px;color:#344054}
    .rg-table th{background:#fbfcfe;color:#667085;font-size:9px;font-weight:700;letter-spacing:.045em;text-transform:uppercase;text-align:left;padding:10px 10px;border-bottom:1px solid #e6eaf0;white-space:nowrap}
    .rg-table th.group{text-align:center;color:#475467;background:#f8fafc}
    .rg-table td{padding:12px 10px;border-bottom:1px solid #eef1f5;vertical-align:middle;background:#fff}
    .rg-table tr:last-child td{border-bottom:0}.rg-table tr:hover td{background:#fbfdfb}
    .rg-market{display:flex;align-items:center;gap:9px;min-width:180px}.rg-star{color:#98a2b3;font-size:15px}.rg-market a{color:#101828;text-decoration:none;font-weight:650}.rg-market a:hover{color:#16a34a}.rg-symbol{font-size:9px;color:#98a2b3;margin-top:2px}
    .rg-pct{font-size:14px;font-weight:720;color:#101828}.rg-sub{font-size:9px;color:#98a2b3;margin-top:3px;white-space:nowrap}
    .rg-chip{display:inline-flex;align-items:center;padding:4px 7px;border-radius:6px;font-size:9px;font-weight:700;white-space:nowrap;border:1px solid transparent}
    .rg-good{color:#15803d;background:#eefbf2;border-color:#d7f3df}.rg-warn{color:#b45309;background:#fff8e8;border-color:#fce9b8}.rg-bad{color:#dc2626;background:#fff1f1;border-color:#ffdada}.rg-neutral{color:#667085;background:#f5f7f9;border-color:#e7ebef}
    .rg-arrow-good{color:#16a34a;font-weight:700}.rg-arrow-bad{color:#ef4444;font-weight:700}.rg-arrow-neutral{color:#98a2b3}
    .rg-status{font-size:9px;font-weight:750;line-height:1.25;text-transform:uppercase}.rg-status.good{color:#15803d}.rg-status.warn{color:#b45309}.rg-status.bad{color:#dc2626}.rg-status.neutral{color:#667085}
    .rg-legend{display:grid;grid-template-columns:repeat(5,1fr);gap:0;margin-top:0;background:#fff;border:1px solid #e3e8ef;border-top:0;border-radius:0 0 13px 13px;padding:14px 16px}
    .rg-legend-block{padding:0 14px;border-right:1px solid #eef1f5}.rg-legend-block:last-child{border-right:0}.rg-legend-title{font-size:9px;font-weight:750;color:#475467;text-transform:uppercase;margin-bottom:7px}.rg-legend-line{font-size:9px;color:#667085;line-height:1.7}
    @media(max-width:1100px){.rg-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.rg-legend{grid-template-columns:1fr 1fr}.rg-legend-block{border-right:0;border-bottom:1px solid #eef1f5;padding:10px}}
    </style>
    """)


def _ensure_fresh_micro_rows(
    all_markets: pd.DataFrame,
    pipeline: pd.DataFrame,
) -> pd.DataFrame:
    """Ensure fresh 90/10 trigger markets reach the trader watchlist."""
    base = (
        pipeline.copy()
        if pipeline is not None and not pipeline.empty
        else pd.DataFrame()
    )
    if all_markets is None or all_markets.empty:
        return base

    trigger_columns = [
        "micro_trigger_direction",
        "micro_trigger_label",
        "micro_trigger_age_weeks",
        "micro_trigger_fresh",
        "micro_trigger_value",
        "micro_current_index_26w",
        "micro_trigger_report_date",
    ]

    if not base.empty:
        for col in trigger_columns:
            if col not in base.columns:
                base[col] = False if col == "micro_trigger_fresh" else np.nan

    by_symbol = {}
    if not base.empty and "symbol" in base.columns:
        by_symbol = {
            str(row.get("symbol", "")): idx
            for idx, row in base.iterrows()
        }

    appended = []
    for _, source in all_markets.iterrows():
        symbol = str(source.get("symbol", "") or "")
        idx = by_symbol.get(symbol)

        if idx is not None:
            for col in trigger_columns:
                if col in source.index:
                    base.at[idx, col] = source.get(col)
            continue

        if not bool(source.get("micro_trigger_fresh", False)):
            continue

        raw_context = source.get("context_direction", 0)
        try:
            context_value = float(raw_context)
            context_direction = (
                int(np.sign(context_value))
                if np.isfinite(context_value)
                else 0
            )
        except (TypeError, ValueError):
            context_direction = 0

        new_row = source.to_dict()
        new_row.update(
            {
                "expected_direction": context_direction,
                "direction_label": (
                    "BULLISH" if context_direction > 0
                    else "BEARISH" if context_direction < 0
                    else "NEUTRAL"
                ),
                "segment": (
                    "FINANZWERTE"
                    if str(source.get("asset_class", "")) in {"Currencies", "Indices", "Rates"}
                    else "ROHSTOFFE"
                ),
                "regime_stage": 0,
                "regime_status": "FRESH MICRO",
                "regime_tone": "neutral",
                "institutional_aligned": False,
                "trend_group_aligned": False,
                "nonreportable_contrarian": False,
                "price_state": "—",
                "price_tone": "neutral",
                "price_confirming": False,
                "season_overall": "N/V",
                "season_rank": 0,
                "research_fx_active": False,
                "research_direction_conflict": False,
                "dual_horizon_active": False,
            }
        )
        appended.append(new_row)

    if appended:
        base = pd.concat([base, pd.DataFrame(appended)], ignore_index=True, sort=False)
    return base.reset_index(drop=True)

def _apply_macro_micro_filters(
    frame: pd.DataFrame,
    macro_filter: str,
    micro_filter: str,
) -> pd.DataFrame:
    """Trader-facing filters derived from the same decision core as the table."""
    if frame is None or frame.empty:
        return frame

    keep = []
    for _, filter_row in frame.iterrows():
        decision = classify_macro_micro_trade(filter_row)
        macro = dict(decision.get("macro") or {})
        micro = dict(decision.get("micro") or {})

        macro_phase = str(macro.get("phase", "") or "").upper()
        micro_direction = int(micro.get("direction", 0) or 0)
        micro_fresh = bool(micro.get("fresh", False))

        macro_ok = (
            macro_filter == "Alle Makro"
            or macro_phase == str(macro_filter).upper()
        )

        if micro_filter == "Alle Mikro":
            micro_ok = True
        elif micro_filter == "BULLISH TRIGGER":
            micro_ok = micro_direction > 0
        elif micro_filter == "BEARISH TRIGGER":
            micro_ok = micro_direction < 0
        elif micro_filter == "FRESH BULLISH":
            micro_ok = micro_direction > 0 and micro_fresh
        elif micro_filter == "FRESH BEARISH":
            micro_ok = micro_direction < 0 and micro_fresh
        elif micro_filter == "KEIN TRIGGER":
            micro_ok = micro_direction == 0
        else:
            micro_ok = True

        keep.append(bool(macro_ok and micro_ok))

    return frame[pd.Series(keep, index=frame.index)]


def _micro_runtime_health(frame: pd.DataFrame) -> dict:
    """Minimal deployment diagnostic; never changes trading decisions."""
    if frame is None or frame.empty:
        return {
            "rows": 0,
            "metadata": False,
            "trigger_rows": 0,
            "fresh_rows": 0,
            "current_extremes_90_10": 0,
        }

    metadata = "micro_trigger_direction" in frame.columns

    if metadata:
        direction = pd.to_numeric(
            frame["micro_trigger_direction"],
            errors="coerce",
        ).fillna(0)
        trigger_rows = int(direction.ne(0).sum())
    else:
        trigger_rows = 0

    if "micro_trigger_fresh" in frame.columns:
        fresh_rows = int(
            frame["micro_trigger_fresh"].fillna(False).astype(bool).sum()
        )
    else:
        fresh_rows = 0

    if "micro_current_index_26w" in frame.columns:
        current_source = frame["micro_current_index_26w"]
    elif "commercial_index" in frame.columns:
        current_source = frame["commercial_index"]
    else:
        current_source = pd.Series(index=frame.index, dtype=float)

    current = pd.to_numeric(current_source, errors="coerce")
    current_extremes = int(
        ((current >= 90.0) | (current <= 10.0)).sum()
    )

    return {
        "rows": int(len(frame)),
        "metadata": bool(metadata),
        "trigger_rows": trigger_rows,
        "fresh_rows": fresh_rows,
        "current_extremes_90_10": current_extremes,
    }

def _kpis(df: pd.DataFrame, report_date):
    """V3.14.2 · Release-priority macro/micro KPIs."""
    if df is None:
        df = pd.DataFrame()

    decisions = [
        classify_macro_micro_trade(row)
        for _, row in df.iterrows()
    ]

    aligned = sum(d["signal"] == "ALIGNED" for d in decisions)
    watch = sum(d["signal"] == "WATCH" for d in decisions)
    stage = pd.to_numeric(
        df.get("regime_stage", pd.Series(dtype=float)),
        errors="coerce",
    ).fillna(0)
    context_ready = int((stage >= 5).sum())

    st.html(
        f"""
        <style>
        .sl-kpis{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:14px 0}}
        .sl-kpi{{display:flex;align-items:center;gap:13px;padding:16px 18px;min-height:78px;background:#fff;border:1px solid #e3e8ef;border-radius:13px}}
        .sl-kpi-ico{{width:38px;height:38px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:800}}
        .sl-report{{background:#eef3ff;color:#2563eb}}.sl-aligned{{background:#ecfdf3;color:#16a34a}}.sl-watch{{background:#fff7e6;color:#d97706}}.sl-ready{{background:#f5f0ff;color:#7c3aed}}
        .sl-kpi-label{{font-size:9px;font-weight:750;color:#667085;text-transform:uppercase;letter-spacing:.04em}}
        .sl-kpi-value{{font-size:22px;font-weight:780;color:#101828;margin-top:2px}}
        .sl-logic{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:#fff;border:1px solid #e3e8ef;border-radius:11px;padding:11px 14px;margin-bottom:14px}}
        .sl-logic-item{{display:flex;align-items:center;gap:8px;padding:3px 14px;border-right:1px solid #eef1f5;font-size:10px;color:#667085}}
        .sl-logic-item:last-child{{border-right:0}}
        .sl-dot{{width:8px;height:8px;border-radius:50%;display:inline-block;flex:0 0 8px}}.sl-dot-macro{{background:#16a34a}}.sl-dot-micro{{background:#4f46e5}}.sl-dot-bias{{background:#101828}}
        @media(max-width:900px){{.sl-kpis{{grid-template-columns:repeat(2,minmax(0,1fr))}}.sl-logic{{grid-template-columns:1fr}}.sl-logic-item{{border-right:0;border-bottom:1px solid #eef1f5}}.sl-logic-item:last-child{{border-bottom:0}}}}
        </style>
        <div class="sl-kpis">
          <div class="sl-kpi"><div class="sl-kpi-ico sl-report">◫</div><div><div class="sl-kpi-label">Report</div><div class="sl-kpi-value">{escape(de_date(report_date))}</div></div></div>
          <div class="sl-kpi"><div class="sl-kpi-ico sl-aligned">✓</div><div><div class="sl-kpi-label">Aligned</div><div class="sl-kpi-value">{aligned}</div></div></div>
          <div class="sl-kpi"><div class="sl-kpi-ico sl-watch">◉</div><div><div class="sl-kpi-label">Watch</div><div class="sl-kpi-value">{watch}</div></div></div>
          <div class="sl-kpi"><div class="sl-kpi-ico sl-ready">⌖</div><div><div class="sl-kpi-label">Context Ready</div><div class="sl-kpi-value">{context_ready}</div></div></div>
        </div>
        <div class="sl-logic">
          <div class="sl-logic-item"><span class="sl-dot sl-dot-macro"></span><b>Makro</b>&nbsp;= 156W · aktiv ab Release</div>
          <div class="sl-logic-item"><span class="sl-dot sl-dot-micro"></span><b>Mikro</b>&nbsp;= COT Index 26W · Trigger 90/10</div>
          <div class="sl-logic-item"><span class="sl-dot sl-dot-bias"></span><b>Priorität</b>&nbsp;= Makro führt nach Release</div>
        </div>
        """
    )




def _delta_html(value: float, direction_to_release: int | None = None) -> str:
    value = _finite(value)
    if not np.isfinite(value):
        return '<span class="rg-arrow-neutral">—</span>'
    arrow = "↑" if value > 0 else "↓" if value < 0 else "→"
    cls = "rg-arrow-neutral"
    if direction_to_release is not None and value != 0:
        # For Commercial, direction_to_release is -extreme_direction.
        cls = "rg-arrow-good" if np.sign(value) == np.sign(direction_to_release) else "rg-arrow-bad"
    return f'<span class="{cls}">{arrow} {value:+.1f}</span>'


def _stage_dots(stage: int) -> str:
    dots = []
    for i in range(1, 6):
        dots.append(f'<span class="rg-stage-dot {"on" if i <= int(stage) else ""}"></span>')
    return '<div class="rg-stagebar">' + ''.join(dots) + '</div>'


def _market_rows_html(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    rows = []
    for _, r in df.iterrows():
        symbol = escape(str(r.get("symbol", "")))
        name = escape(str(market_name_de(r.get("market_name", ""))))
        state = escape(str(r.get("commercial_state_ui", "—")))
        trans = escape(str(r.get("commercial_transition_ui", "—")))
        trans_cls = _tone_class(str(r.get("commercial_transition_tone", "neutral")))
        commercial_delta = _finite(r.get("commercial_percentile_change_4w"))
        release_direction = -int(r.get("extreme_direction", 0) or 0)
        inst_cls = _tone_class(str(r.get("institutional_tone", "neutral")))
        trend_cls = _tone_class(str(r.get("trend_group_tone", "neutral")))
        nr_cls = _tone_class(str(r.get("nonreportable_tone", "neutral")))
        px_cls = _tone_class(str(r.get("price_tone", "neutral")))
        stage_tone = str(r.get("regime_tone", "neutral"))
        season_tone = "rg-good" if int(r.get("season_rank", 0) or 0) >= 3 else "rg-warn" if int(r.get("season_rank", 0) or 0) == 2 else "rg-neutral"
        rows.append(f"""
        <tr>
          <td><div class="rg-market"><span class="rg-star">☆</span><div><a href="?open_market={symbol}">{name}</a><div class="rg-symbol">{symbol} · {escape(str(r.get('asset_class','')))}</div></div></div></td>
          <td><div class="rg-pct">{_fmt(r.get('commercial_net_percentile'))}</div><div class="rg-sub">156W Percentile</div></td>
          <td><span class="rg-chip rg-neutral">{state}</span></td>
          <td>{_delta_html(commercial_delta, release_direction)}<div class="rg-sub">Δ4W</div></td>
          <td><span class="rg-chip {trans_cls}">{trans}</span></td>
          <td><div class="rg-pct">{_fmt(r.get('institutional_pct'))}</div><div class="rg-sub">{escape(str(r.get('institutional_label','')))}</div></td>
          <td><span class="rg-chip {inst_cls}">{escape(str(r.get('institutional_trend','WARTET')))}</span><div class="rg-sub">Δ4W {_fmt(r.get('institutional_delta_4w'))}</div></td>
          <td><div class="rg-pct">{_fmt(r.get('trend_pct'))}</div><div class="rg-sub">{escape(str(r.get('trend_group_label','')))}</div></td>
          <td><span class="rg-chip {trend_cls}">{escape(str(r.get('trend_group_state','WARTET')))}</span><div class="rg-sub">Δ4W {_fmt(r.get('trend_delta_4w'))}</div></td>
          <td><div class="rg-pct">{_fmt(r.get('nonreportable_pct'))}</div><div class="rg-sub">156W Percentile</div></td>
          <td><span class="rg-chip {nr_cls}">{escape(str(r.get('nonreportable_state','WARTET')))}</span></td>
          <td><span class="rg-chip {px_cls}">{escape(str(r.get('price_state','—')))}</span></td>
          <td><span class="rg-chip {season_tone}" title="{escape(str(r.get('season_detail','')))}">{escape(str(r.get('season_compact','—')))}</span></td>
          <td><div class="rg-status {escape(stage_tone)}">{escape(str(r.get('regime_status','—')))}</div>{_stage_dots(int(r.get('regime_stage',0) or 0))}</td>
          <td style="text-align:right;color:#98a2b3;font-size:18px">›</td>
        </tr>
        """)
    return ''.join(rows)


def _render_table(df: pd.DataFrame):
    if df.empty:
        empty_state("Keine Märkte in dieser Phase", "Für den aktuellen Report erfüllt kein Markt diesen Pipeline-Zustand.")
        return
    html = f"""
    <div class="rg-table-wrap">
      <table class="rg-table">
        <thead>
          <tr>
            <th rowspan="2">Markt</th>
            <th class="group" colspan="4">1 · Commercial / Hedger</th>
            <th class="group" colspan="2">2 · Institutionell</th>
            <th class="group" colspan="2">3 · Trend-Funds</th>
            <th class="group" colspan="2">4 · Nonreportable</th>
            <th class="group" colspan="2">Kontext</th>
            <th class="group" colspan="2">Regime</th>
          </tr>
          <tr>
            <th>156W Pctl</th><th>State</th><th>Transition</th><th>Release</th>
            <th>156W Pctl</th><th>Trend 1–4W</th>
            <th>156W Pctl</th><th>Trend 1–4W</th>
            <th>156W Pctl</th><th>Konträr</th>
            <th>Price</th><th>Season</th><th>Status</th><th></th>
          </tr>
        </thead>
        <tbody>{_market_rows_html(df)}</tbody>
      </table>
    </div>
    <div class="rg-legend">
      <div class="rg-legend-block"><div class="rg-legend-title">Commercial State</div><div class="rg-legend-line">FULL HEDGE / LOWER EXTREME = historisch extrem.<br>Das Extrem allein ist kein Signal.</div></div>
      <div class="rg-legend-block"><div class="rg-legend-title">Transition</div><div class="rg-legend-line">Δ1W / Δ2W / Δ4W beobachten.<br>EARLY = Extrem beginnt sich zu lösen.</div></div>
      <div class="rg-legend-block"><div class="rg-legend-title">Cross-Group</div><div class="rg-legend-line">Asset Manager / Producer und Leveraged / Managed Money werden separat überwacht.</div></div>
      <div class="rg-legend-block"><div class="rg-legend-title">Nonreportable</div><div class="rg-legend-line">Konträrer Kontext. Nicht automatisch mit „Retail“ gleichsetzen.</div></div>
      <div class="rg-legend-block"><div class="rg-legend-title">5 Phasen</div><div class="rg-legend-line">Extreme → Transition → Cross-Group → Confirmed → Context Ready.<br>S&amp;D bleibt manuelle Trade-Entscheidung.</div></div>
    </div>
    """
    st.html(html)



def _merge_dual_horizon_into_pipeline(
    all_markets: pd.DataFrame,
    pipeline: pd.DataFrame,
) -> pd.DataFrame:
    """Add 156W Commercial regime pressure + 26W COT timing to all markets."""
    base = (
        pipeline.copy()
        if pipeline is not None and not pipeline.empty
        else pd.DataFrame()
    )

    defaults = {
        "dual_horizon_active": False,
        "dual_156w_label": "",
        "dual_156w_direction": 0,
        "dual_156w_pct": np.nan,
        "dual_156w_slope": "",
        "dual_delta_1w": np.nan,
        "dual_delta_2w": np.nan,
        "dual_delta_4w": np.nan,
        "dual_26w_label": "",
        "dual_26w_direction": 0,
        "dual_commercial_index_26w": np.nan,
        "dual_retail_index_26w": np.nan,
        "dual_interpretation": "",
        "dual_action": "",
        "dual_tone": "neutral",
    }

    if not base.empty:
        for col, default in defaults.items():
            if col not in base.columns:
                base[col] = default

    if all_markets is None or all_markets.empty:
        return base

    by_symbol = {}
    if not base.empty:
        for idx, row in base.iterrows():
            by_symbol[str(row.get("symbol", ""))] = idx

    appended = []

    for _, source in all_markets.iterrows():
        symbol = str(source.get("symbol", ""))
        if not symbol:
            continue

        if symbol in by_symbol:
            idx = by_symbol[symbol]
            hard_stage = int(base.at[idx, "regime_stage"] or 0)
            hard_direction = int(
                np.sign(base.at[idx, "expected_direction"] or 0)
            )
        else:
            idx = None
            hard_stage = 0
            hard_direction = 0

        dual = classify_watchlist_row(
            source,
            hard_regime_direction=hard_direction,
            hard_regime_stage=hard_stage,
        )
        if not bool(dual["interesting"]):
            continue

        long_term = dual["long_term"]
        short_term = dual["short_term"]
        combined = dual["combined"]

        values = {
            "dual_horizon_active": True,
            "dual_156w_label": long_term["label"],
            "dual_156w_direction": int(long_term["direction"]),
            "dual_156w_pct": _finite(source.get("commercial_net_percentile")),
            "dual_156w_slope": long_term["slope_label"],
            "dual_delta_1w": _finite(
                source.get("commercial_percentile_change_1w")
            ),
            "dual_delta_2w": _finite(
                source.get("commercial_percentile_change_2w")
            ),
            "dual_delta_4w": _finite(
                source.get("commercial_percentile_change_4w")
            ),
            "dual_26w_label": short_term["label"],
            "dual_26w_direction": int(short_term["direction"]),
            "dual_commercial_index_26w": _finite(
                source.get("commercial_index")
            ),
            "dual_retail_index_26w": _finite(source.get("retail_index")),
            "dual_interpretation": combined["interpretation"],
            "dual_action": combined["action"],
            "dual_tone": combined["tone"],
        }

        if idx is not None:
            for col, value in values.items():
                base.at[idx, col] = value
            continue

        new_row = source.to_dict()
        new_row.update(
            {
                "expected_direction": int(long_term["direction"]),
                "direction_label": (
                    "BULLISH"
                    if int(long_term["direction"]) > 0
                    else "BEARISH"
                    if int(long_term["direction"]) < 0
                    else "NEUTRAL"
                ),
                "segment": (
                    "FINANZWERTE"
                    if str(source.get("asset_class", "")) in {
                        "Currencies", "Indices", "Rates"
                    }
                    else "ROHSTOFFE"
                ),
                "regime_stage": 0,
                "regime_status": "DUAL-HORIZON WATCH",
                "regime_tone": "neutral",
                "institutional_aligned": False,
                "trend_group_aligned": False,
                "nonreportable_contrarian": False,
                "price_state": "—",
                "price_tone": "neutral",
                "price_confirming": False,
                "season_overall": "N/V",
                "season_rank": 0,
                "research_fx_active": False,
                "research_direction_conflict": False,
                **values,
            }
        )
        appended.append(new_row)

    if appended:
        base = pd.concat(
            [base, pd.DataFrame(appended)],
            ignore_index=True,
            sort=False,
        )

    if base.empty:
        return base

    base["_dual_rank"] = (
        base["dual_horizon_active"].fillna(False).astype(int) * 10
        + base["dual_26w_direction"].fillna(0).abs().astype(int) * 2
        + base["dual_156w_direction"].fillna(0).abs().astype(int)
    )

    return base.sort_values(
        ["regime_stage", "_dual_rank", "market_name"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def _merge_fx_research_into_pipeline(
    all_markets: pd.DataFrame,
    pipeline: pd.DataFrame,
) -> pd.DataFrame:
    """Merge the frozen FX research overlay into the main trader watchlist.

    Rules:
    - Non-FX stays on the existing V3.10 regime logic.
    - FX 75/25 + Raw 1–2W may create an EARLY row even before the hard 80/20
      pipeline is active.
    - Existing hard regime stages are never downgraded or bypassed.
    - If research direction conflicts with an already-active hard regime,
      the row is marked as conflict and the hard regime direction wins.
    """
    base = (
        pipeline.copy()
        if pipeline is not None and not pipeline.empty
        else pd.DataFrame()
    )

    research_cols = {
        "research_fx_active": False,
        "research_bias": "",
        "research_confidence": "",
        "research_timing": "",
        "research_action": "",
        "research_flow_support": "",
        "research_dealer_pct_156w": np.nan,
        "research_release_flow_1w": np.nan,
        "research_release_flow_2w": np.nan,
        "research_direction": 0,
        "research_direction_conflict": False,
        "research_phase": "",
    }

    if not base.empty:
        for col, default in research_cols.items():
            if col not in base.columns:
                base[col] = default

    if all_markets is None or all_markets.empty:
        return base

    fx = all_markets[
        all_markets["asset_class"].astype(str).eq("Currencies")
    ].copy()
    if fx.empty:
        return base

    rows_by_symbol = {}
    if not base.empty:
        for idx, row in base.iterrows():
            rows_by_symbol[str(row.get("symbol", ""))] = idx

    appended = []

    for _, source in fx.iterrows():
        symbol = str(source.get("symbol", ""))
        code = str(source.get("cftc_code", ""))
        if not symbol or not code:
            continue

        research = load_fx_research_overlay("Currencies", code)
        if not bool(research.get("calibrated", False)):
            continue

        research_active = bool(research.get("active", False))
        flow_active = bool(
            research.get("flow_aligned_1w", False)
            or research.get("flow_aligned_2w", False)
        )
        if not (research_active and flow_active):
            continue

        research_direction = int(
            np.sign(research.get("expected_direction", 0) or 0)
        )

        if symbol in rows_by_symbol:
            idx = rows_by_symbol[symbol]
            hard_stage = int(base.at[idx, "regime_stage"] or 0)
            hard_direction = int(
                np.sign(base.at[idx, "expected_direction"] or 0)
            )
            legacy_release = (
                str(base.at[idx, "cycle_phase"]).upper() == "RELEASE"
            )
            price_confirming = bool(
                base.at[idx, "price_confirming"]
                if "price_confirming" in base.columns
                else False
            )

            conflict = bool(
                hard_stage > 0
                and hard_direction != 0
                and research_direction != 0
                and hard_direction != research_direction
            )

            trader = classify_trader_overlay(
                research,
                regime_stage=hard_stage,
                legacy_release=legacy_release,
                price_confirming=price_confirming,
            )

            if conflict:
                trader = {
                    **trader,
                    "bias": (
                        "BULLISH" if hard_direction > 0
                        else "BEARISH" if hard_direction < 0
                        else "NEUTRAL"
                    ),
                    "confidence": "CONFLICT",
                    "timing": "WAITING",
                    "action": "WARTEN · SIGNALKONFLIKT",
                }

            updates = {
                "research_fx_active": True,
                "research_bias": trader.get("bias", ""),
                "research_confidence": trader.get("confidence", ""),
                "research_timing": trader.get("timing", ""),
                "research_action": trader.get("action", ""),
                "research_flow_support": research.get("flow_support", ""),
                "research_dealer_pct_156w": research.get(
                    "dealer_net_oi_percentile_156w", np.nan
                ),
                "research_release_flow_1w": research.get(
                    "release_velocity_1w", np.nan
                ),
                "research_release_flow_2w": research.get(
                    "release_velocity_2w", np.nan
                ),
                "research_direction": research_direction,
                "research_direction_conflict": conflict,
                "research_phase": research.get("phase", ""),
            }
            for col, value in updates.items():
                base.at[idx, col] = value
            continue

        trader = classify_trader_overlay(
            research,
            regime_stage=0,
            legacy_release=False,
            price_confirming=False,
        )
        new_row = source.to_dict()
        new_row.update(
            {
                "expected_direction": research_direction,
                "direction_label": (
                    "BULLISH"
                    if research_direction > 0
                    else "BEARISH"
                    if research_direction < 0
                    else "NEUTRAL"
                ),
                "segment": "FINANZWERTE",
                "regime_stage": 0,
                "regime_status": "EARLY FX WATCH",
                "regime_tone": (
                    "bull"
                    if research_direction > 0
                    else "bear"
                    if research_direction < 0
                    else "neutral"
                ),
                "institutional_aligned": False,
                "trend_group_aligned": False,
                "nonreportable_contrarian": False,
                "price_state": "—",
                "price_tone": "neutral",
                "price_confirming": False,
                "season_overall": "N/V",
                "season_rank": 0,
                "research_fx_active": True,
                "research_bias": trader.get("bias", ""),
                "research_confidence": trader.get("confidence", ""),
                "research_timing": trader.get("timing", ""),
                "research_action": trader.get("action", ""),
                "research_flow_support": research.get("flow_support", ""),
                "research_dealer_pct_156w": research.get(
                    "dealer_net_oi_percentile_156w", np.nan
                ),
                "research_release_flow_1w": research.get(
                    "release_velocity_1w", np.nan
                ),
                "research_release_flow_2w": research.get(
                    "release_velocity_2w", np.nan
                ),
                "research_direction": research_direction,
                "research_direction_conflict": False,
                "research_phase": research.get("phase", ""),
            }
        )
        appended.append(new_row)

    if appended:
        base = pd.concat(
            [base, pd.DataFrame(appended)],
            ignore_index=True,
            sort=False,
        )

    if base.empty:
        return base

    research_rank = {
        "CONFLICT": 5,
        "CONFIRMED": 4,
        "DEVELOPING": 3,
        "EARLY": 2,
        "WATCH": 1,
    }
    base["_research_rank"] = (
        base.get("research_confidence", pd.Series("", index=base.index))
        .map(research_rank)
        .fillna(0)
    )
    base = base.sort_values(
        ["regime_stage", "_research_rank", "market_name"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    return base



def _trader_bias(row: pd.Series) -> tuple[str, str]:
    if bool(row.get("dual_horizon_active", False)):
        label = str(row.get("dual_156w_label", "") or "NEUTRAL")
        direction = int(row.get("dual_156w_direction", 0) or 0)
        return (
            label,
            "bull" if direction > 0 else "bear" if direction < 0 else "neutral",
        )

    if bool(row.get("research_fx_active", False)):
        label = str(row.get("research_bias", "") or "NEUTRAL")
        if "BULL" in label.upper():
            return label, "bull"
        if "BEAR" in label.upper() or "BÄR" in label.upper():
            return label, "bear"
        return label, "neutral"

    direction = int(row.get("expected_direction", 0) or 0)
    stage = int(row.get("regime_stage", 0) or 0)
    if direction > 0:
        return ("BULLISH" if stage >= 4 else "BULLISH WATCH", "bull")
    if direction < 0:
        return ("BEARISH" if stage >= 4 else "BEARISH WATCH", "bear")
    return ("NEUTRAL", "neutral")

def _trader_confidence(row: pd.Series) -> tuple[str, str]:
    if bool(row.get("research_fx_active", False)):
        value = str(row.get("research_confidence", "") or "WATCH")
        tone = (
            "bad" if value == "CONFLICT"
            else "good" if value == "CONFIRMED"
            else "warn" if value in {"EARLY", "DEVELOPING"}
            else "neutral"
        )
        return value, tone

    stage = int(row.get("regime_stage", 0) or 0)
    return str(row.get("regime_status", "NORMAL")), (
        "good" if stage >= 4 else "warn" if stage >= 2 else "neutral"
    )


def _trader_timing(row: pd.Series) -> str:
    if bool(row.get("dual_horizon_active", False)):
        return str(row.get("dual_26w_label", "") or "NEUTRAL / MIXED")

    if bool(row.get("research_fx_active", False)):
        return str(row.get("research_timing", "") or "WAITING")

    stage = int(row.get("regime_stage", 0) or 0)
    return {
        1: "EXTREME",
        2: "TRANSITION",
        3: "CROSS-GROUP",
        4: "CONFIRMED",
        5: "PRICE CONFIRMED",
    }.get(stage, "WAITING")

def _legacy_trader_next_step(row: pd.Series) -> str:
    stage = int(row.get("regime_stage", 0) or 0)
    if stage <= 0:
        return "Auf neues 156W-Extrem warten"
    if stage == 1:
        return "Auf Transition warten"
    if stage == 2:
        return "Auf Cross-Group Shift warten"
    if stage == 3:
        if str(row.get("cycle_phase", "")).upper() != "RELEASE":
            return "Auf Commercial Release warten"
        if not bool(row.get("institutional_aligned", False)):
            return "Institutionelle Bestätigung fehlt"
        if not bool(row.get("trend_group_aligned", False)):
            return "Trend-Funds-Bestätigung fehlt"
        if not bool(row.get("nonreportable_contrarian", False)):
            return "Konträrer Kontext fehlt"
        return "Auf vollständige Regime-Bestätigung warten"
    if stage == 4:
        return "Auf Preisbestätigung warten"
    return "S&D-Setup prüfen"


def _trader_action(row: pd.Series) -> str:
    if bool(row.get("dual_horizon_active", False)):
        dual_action = str(row.get("dual_action", "") or "")
        if dual_action:
            return dual_action

    if bool(row.get("research_fx_active", False)):
        return str(row.get("research_action", "") or "WARTEN")
    return _legacy_trader_next_step(row)

def _trader_context(row: pd.Series) -> str:
    stage = int(row.get("regime_stage", 0) or 0)

    if bool(row.get("dual_horizon_active", False)):
        pct = _finite(row.get("dual_156w_pct"))
        d1 = _finite(row.get("dual_delta_1w"))
        d2 = _finite(row.get("dual_delta_2w"))
        d4 = _finite(row.get("dual_delta_4w"))
        ci = _finite(row.get("dual_commercial_index_26w"))
        ri = _finite(row.get("dual_retail_index_26w"))

        pct_txt = "—" if not np.isfinite(pct) else f"{pct:.1f}"
        d1_txt = "—" if not np.isfinite(d1) else f"{d1:+.1f}"
        d2_txt = "—" if not np.isfinite(d2) else f"{d2:+.1f}"
        d4_txt = "—" if not np.isfinite(d4) else f"{d4:+.1f}"
        ci_txt = "—" if not np.isfinite(ci) else f"{ci:.0f}"
        ri_txt = "—" if not np.isfinite(ri) else f"{ri:.0f}"

        interpretation = escape(
            str(row.get("dual_interpretation", "") or "—")
        )
        slope = escape(str(row.get("dual_156w_slope", "") or "—"))
        hard = escape(str(row.get("regime_status", "DUAL-HORIZON WATCH")))

        return (
            f'<span class="tw-context-research">{interpretation}</span>'
            f'<div class="tw-context-sub">Commercial 156W {pct_txt} · '
            f'Δ1 {d1_txt} · Δ2 {d2_txt} · Δ4 {d4_txt} · {slope}</div>'
            f'<div class="tw-context-sub">COT26 C {ci_txt} / Retail {ri_txt} · '
            f'Regime {hard} {stage}/5</div>'
        )

    if bool(row.get("research_fx_active", False)):
        pct = _finite(row.get("research_dealer_pct_156w"))
        flow1 = _finite(row.get("research_release_flow_1w"))
        flow2 = _finite(row.get("research_release_flow_2w"))
        flow_support = escape(
            str(row.get("research_flow_support", "—") or "—")
        )

        pct_txt = "—" if not np.isfinite(pct) else f"{pct:.1f}"
        flow1_txt = "—" if not np.isfinite(flow1) else f"{flow1:+,.0f}"
        flow2_txt = "—" if not np.isfinite(flow2) else f"{flow2:+,.0f}"

        conflict = bool(row.get("research_direction_conflict", False))
        head_cls = "tw-context-conflict" if conflict else "tw-context-research"
        head = (
            "⚠ Research/Regime Konflikt"
            if conflict
            else f"Dealer 156W · {pct_txt}"
        )

        hard = escape(str(row.get("regime_status", "EARLY FX WATCH")))
        return (
            f'<span class="{head_cls}">{head}</span>'
            f'<div class="tw-context-sub">Raw 1W {flow1_txt} · 2W {flow2_txt}</div>'
            f'<div class="tw-context-sub">{flow_support} · Regime {hard} {stage}/5</div>'
        )

    if stage < 4:
        return '<span class="tw-muted">—</span>'

    price = escape(str(row.get("price_state", "—")))
    season = escape(str(row.get("season_overall", "N/V")))
    price_cls = _tone_class(str(row.get("price_tone", "neutral")))

    if stage >= 5:
        return (
            f'<span class="tw-context-ok">✓ Preis · {price}</span>'
            f'<div class="tw-context-sub">Saison · {season}</div>'
        )

    return (
        f'<span class="rg-chip {price_cls}">{price}</span>'
        f'<div class="tw-context-sub">Saison · {season}</div>'
    )

def _trader_rows_html(df: pd.DataFrame) -> str:
    rows = []
    for _, row in df.iterrows():
        symbol = escape(str(row.get("symbol", "")))
        name = escape(str(market_name_de(row.get("market_name", ""))))
        asset_class = escape(str(row.get("asset_class", "")))
        stage = int(row.get("regime_stage", 0) or 0)

        bias_label, bias_class = _trader_bias(row)
        confidence, confidence_tone = _trader_confidence(row)
        timing = escape(_trader_timing(row))
        action = escape(_trader_action(row))
        confidence_cls = _tone_class(confidence_tone)

        source_badge = (
            '<span class="tw-research-badge">FX RESEARCH</span>'
            if bool(row.get("research_fx_active", False))
            else ""
        )

        rows.append(
            f"""
            <tr>
              <td>
                <div class="tw-market">
                  <span class="tw-star">☆</span>
                  <div>
                    <a href="?open_market={symbol}">{name}</a>
                    <div class="tw-sub">{symbol} · {asset_class} {source_badge}</div>
                  </div>
                </div>
              </td>
              <td>
                <div class="tw-direction {bias_class}">{escape(bias_label)}</div>
              </td>
              <td>
                <span class="rg-chip {confidence_cls}">{escape(confidence)}</span>
                <div class="tw-stage-sub">
                  Regime {escape(str(row.get("regime_status", "NORMAL")))} · {stage}/5
                </div>
                {_stage_dots(stage)}
              </td>
              <td>
                <div class="tw-timing">{timing}</div>
              </td>
              <td>
                <div class="tw-next">{action}</div>
              </td>
              <td>
                {_trader_context(row)}
              </td>
              <td class="tw-open">›</td>
            </tr>
            """
        )

    return "".join(rows)


# Legacy V3.13B header marker: <th>Bias</th>
# Legacy V3.13B header marker: <th>Timing</th>
def _render_trader_table(df: pd.DataFrame):
    """V3.14.2 · slim release-priority trader watchlist."""
    if df is None or df.empty:
        empty_state(
            "Keine Märkte in dieser Auswahl",
            "Für den aktuellen Report gibt es hier keinen relevanten COT-Kontext.",
        )
        return

    def _seasonality_for_bias(row: pd.Series, bias_direction: int) -> tuple[str, str, str]:
        if int(bias_direction) == 0:
            return "—", "season-neutral", "Kein aktiver Bias"

        ticker = str(row.get("ticker", "") or "").strip()
        if not ticker:
            return "—", "season-neutral", "Kein Preis-Ticker"

        season = calculate_market_20y_multi_seasonality(
            ticker=ticker,
            cot_direction=int(bias_direction),
        )
        overall = str(season.get("overall", "N/V") or "N/V").upper()
        detail = str(season.get("detail", "") or "")

        if "UNTERSTÜTZT" in overall:
            return "✓", "season-good", detail or overall
        if "GEGENLÄUFIG" in overall:
            return "⚠", "season-warn", detail or overall
        return "—", "season-neutral", detail or overall

    st.html(
        """
        <style>
        .sl-table-wrap{background:#fff;border:1px solid #e3e8ef;border-radius:13px;overflow:hidden;box-shadow:0 1px 2px rgba(15,23,42,.025)}
        .sl-table{width:100%;border-collapse:collapse;table-layout:fixed;color:#344054}
        .sl-table th{background:#fbfcfe;color:#667085;font-size:9px;font-weight:760;letter-spacing:.055em;text-transform:uppercase;text-align:left;padding:11px 12px;border-bottom:1px solid #e6eaf0}
        .sl-table td{padding:14px 12px;border-bottom:1px solid #eef1f5;vertical-align:middle;background:#fff}
        .sl-table tr:last-child td{border-bottom:0}.sl-table tr:hover td{background:#fbfdfc}
        .sl-market{display:flex;align-items:center;gap:9px}.sl-star{font-size:14px;color:#98a2b3}
        .sl-market a{font-size:12px;color:#101828;text-decoration:none;font-weight:730}.sl-market a:hover{color:#16a34a}
        .sl-sub{font-size:9px;color:#98a2b3;margin-top:3px}.sl-age{font-size:8px;color:#98a2b3;margin-top:4px;font-weight:650;white-space:nowrap}.sl-age-fresh{color:#4f46e5;font-weight:800}
        .sl-chip{display:inline-flex;align-items:center;padding:6px 9px;border-radius:7px;font-size:9px;font-weight:800;letter-spacing:.02em;white-space:nowrap}
        .macro-bull{background:#ecfdf3;color:#15803d;border:1px solid #d7f2df}.macro-bear{background:#fff1f2;color:#dc2626;border:1px solid #ffe0e3}.macro-neutral{background:#f2f4f7;color:#667085;border:1px solid #e4e7ec}
        .micro-bull{background:#eef2ff;color:#4f46e5;border:1px solid #dfe3ff}.micro-bear{background:#f5f0ff;color:#7c3aed;border:1px solid #e9ddff}.micro-neutral{background:#f2f4f7;color:#667085;border:1px solid #e4e7ec}
        .sl-bias{display:flex;align-items:center;gap:7px;font-size:10px;font-weight:820;color:#101828;white-space:nowrap}
        .sl-arrow{width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:11px;font-weight:900}
        .bias-long{background:#16a34a}.bias-short{background:#dc2626}.bias-neutral{background:#98a2b3}
        .sl-plan{font-size:10px;font-weight:650;color:#344054;line-height:1.25}
        .sl-signal{display:inline-flex;justify-content:center;min-width:66px;padding:6px 8px;border-radius:7px;font-size:9px;font-weight:820}
        .signal-aligned{background:#ecfdf3;color:#15803d;border:1px solid #d7f2df}.signal-watch{background:#fffaeb;color:#b54708;border:1px solid #fef0c7}.signal-neutral{background:#f2f4f7;color:#667085;border:1px solid #e4e7ec}
        .sl-season{display:inline-flex;width:25px;height:25px;border-radius:7px;align-items:center;justify-content:center;font-size:13px;font-weight:900}
        .season-good{background:#ecfdf3;color:#15803d}.season-warn{background:#fff7e6;color:#d97706}.season-neutral{background:#f2f4f7;color:#98a2b3}
        .sl-table th:nth-child(1){width:20%}.sl-table th:nth-child(2){width:17%}.sl-table th:nth-child(3){width:13%}.sl-table th:nth-child(4){width:13%}.sl-table th:nth-child(5){width:8%}.sl-table th:nth-child(6){width:19%}.sl-table th:nth-child(7){width:10%}
        @media(max-width:950px){.sl-table th:nth-child(6),.sl-table td:nth-child(6){display:none}.sl-table th:nth-child(1){width:24%}.sl-table th:nth-child(2){width:20%}.sl-table th:nth-child(3){width:16%}.sl-table th:nth-child(4){width:16%}.sl-table th:nth-child(5){width:10%}.sl-table th:nth-child(7){width:14%}}
        </style>
        """
    )

    rows = []
    for _, row in df.iterrows():
        decision = classify_macro_micro_trade(row)
        macro = decision["macro"]
        micro = decision["micro"]
        bias_direction = int(decision["bias_direction"])
        try:
            macro_age_weeks = int(
                float(row.get("macro_status_age_weeks", 0) or 0)
            )
        except (TypeError, ValueError):
            macro_age_weeks = 0

        if macro_age_weeks > 0:
            macro_age_label = (
                f"Release seit {macro_age_weeks}W"
                if str(macro.get("phase", "")).upper() == "CONFIRMED"
                else f"seit {macro_age_weeks}W"
            )
            macro_age_html = (
                f'<div class="sl-age">{escape(macro_age_label)}</div>'
            )
        else:
            macro_age_html = ""

        micro_age = int(micro.get("age_weeks", -1))
        if int(micro.get("direction", 0) or 0) == 0 or micro_age < 0:
            micro_age_html = ""
        else:
            micro_age_label = "diese Woche" if micro_age == 0 else f"vor {micro_age}W"
            age_class = "sl-age sl-age-fresh" if bool(micro.get("fresh", False)) else "sl-age"
            micro_age_html = (
                f'<div class="{age_class}">{escape(micro_age_label)}</div>'
            )

        symbol_raw = str(row.get("symbol", "") or "")
        symbol = escape(symbol_raw)
        name = escape(str(market_name_de(row.get("market_name", ""))))
        asset_class = escape(str(row.get("asset_class", "")))

        macro_cls = (
            "macro-bull" if int(macro["direction"]) > 0
            else "macro-bear" if int(macro["direction"]) < 0
            else "macro-neutral"
        )
        micro_cls = (
            "micro-bull" if int(micro["direction"]) > 0
            else "micro-bear" if int(micro["direction"]) < 0
            else "micro-neutral"
        )
        bias_cls = (
            "bias-long" if bias_direction > 0
            else "bias-short" if bias_direction < 0
            else "bias-neutral"
        )
        arrow = "↑" if bias_direction > 0 else "↓" if bias_direction < 0 else "–"
        signal_cls = (
            "signal-aligned"
            if decision["signal"] == "ALIGNED"
            else "signal-watch"
            if decision["signal"] == "WATCH"
            else "signal-neutral"
        )

        season_mark, season_cls, season_help = _seasonality_for_bias(
            row,
            bias_direction,
        )

        rows.append(
            f"""
            <tr>
              <td><div class="sl-market"><span class="sl-star">☆</span><div><a href="?open_market={symbol}">{name}</a><div class="sl-sub">{symbol} · {asset_class}</div></div></div></td>
              <td><span class="sl-chip {macro_cls}">{escape(str(macro["label"]))}</span>{macro_age_html}</td>
              <td><span class="sl-chip {micro_cls}">{escape(str(micro["label"]))}</span>{micro_age_html}</td>
              <td><div class="sl-bias"><span class="sl-arrow {bias_cls}">{arrow}</span>{escape(str(decision["bias"]))}</div></td>
              <td><span class="sl-season {season_cls}" title="{escape(season_help)}">{season_mark}</span></td>
              <td><div class="sl-plan">{escape(str(decision["plan"]))}</div></td>
              <td><span class="sl-signal {signal_cls}">{escape(str(decision["signal"]))}</span></td>
            </tr>
            """
        )

    st.html(
        f"""
        <div class="sl-table-wrap">
          <table class="sl-table">
            <thead><tr><th>Markt</th><th>Makro</th><th>Mikro</th><th>Bias</th><th>Season</th><th>Plan</th><th>Signal</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
        </div>
        """
    )



# V3.13B · UNIFIED TRADER WATCHLIST
# V3.14.0 · DUAL-HORIZON COT WATCHLIST
_pipeline_css()
# V3.14.3 · ASSET CLASS WATCHLIST SCOPE
_watchlist_asset_scope = st.session_state.pop(
    "_watchlist_asset_scope_once",
    None,
)
_watchlist_asset_labels = {
    "Currencies": "Währungen",
    "Cryptocurrencies": "Kryptowährungen",
    "Indices": "Indizes",
    "Rates": "US-Zinsen",
    "Volatility": "Volatilität",
    "Energy": "Energie",
    "Metals": "Metalle",
    "Soft Commodities": "Soft-Rohstoffe",
    "Grains": "Getreide",
    "Livestock": "Vieh",
    "Forest Products": "Forstprodukte",
}
_watchlist_scope_label = _watchlist_asset_labels.get(
    str(_watchlist_asset_scope),
    str(_watchlist_asset_scope or ""),
)
_watchlist_page_title = (
    f"COT Watchlist · {_watchlist_scope_label}"
    if _watchlist_asset_scope
    else "COT Watchlist"
)
_watchlist_page_subtitle = (
    f"COT Watchlist-Logik innerhalb der Assetklasse {_watchlist_scope_label}."
    if _watchlist_asset_scope
    else "Makro-Kontext und Mikro-Timing auf einen Blick."
)

page_header(
    "Research · Positioning Regime",
    _watchlist_page_title,
    _watchlist_page_subtitle,
    "V3.10.0 · DIVIDE & CONQUER",
)

with st.spinner("Commercial-156W-Zustände werden geprüft …"):
    scan = scan_classic_markets(
        cot_weeks=COT_INDEX_WEEKS,
        validation_weeks=NET_VALIDATION_WEEKS,
        range_weeks=COMMERCIAL_RANGE_WEEKS,
        upper=INDEX_UPPER,
        lower=INDEX_LOWER,
        validation_upper=NET_UPPER_PERCENTILE,
        validation_lower=NET_LOWER_PERCENTILE,
        release_active_weeks=RELEASE_ACTIVE_WEEKS,
    )

all_markets = scan["all_markets"].copy()
with st.spinner("Transitions und CFTC-Gruppen werden nach Pipeline-Stufe ergänzt …"):
    pipeline = _build_pipeline_rows(all_markets)
    pipeline = _merge_fx_research_into_pipeline(all_markets, pipeline)
    pipeline = _merge_dual_horizon_into_pipeline(all_markets, pipeline)
    pipeline = _ensure_fresh_micro_rows(all_markets, pipeline)
    # V3.14.3 · same pipeline, scoped to one peer asset class when opened
    # through an indented asset-class navigation page.
    if _watchlist_asset_scope:
        pipeline = pipeline[
            pipeline["asset_class"]
            .astype(str)
            .eq(str(_watchlist_asset_scope))
        ].reset_index(drop=True)

# Click-through from custom HTML table.
open_symbol = str(st.query_params.get("open_market", "") or "").strip()
if open_symbol and not pipeline.empty:
    match = pipeline[pipeline["symbol"].astype(str).eq(open_symbol)]
    if not match.empty:
        r = match.iloc[0]
        handoff = {"asset_class": r["asset_class"], "market_name": r["market_name"]}
        st.session_state["selected_market"] = handoff
        st.session_state["_market_context_handoff"] = handoff
        st.query_params.clear()
        st.switch_page("pages/marktanalyse.py")

_kpis(pipeline, scan.get("latest_report"))
# V3.13B: Early FX is merged into the primary trader table.


if pipeline.empty:
    empty_state("Keine aktiven Positionierungszyklen", "Aktuell steht kein Markt in einer 156W-Extrem- oder aktiven Release-Phase.")
else:
    c1, c2, c3 = st.columns([1.25, 1, 1], gap="small")
    with c1:
        view = st.radio(
            "Phase",
            ["Alle", "Fresh Micro", "Aligned", "Watch", "Context Ready"],
            horizontal=True,
            label_visibility="collapsed",
        )
    with c2:
        segment = st.selectbox("Segment", ["Alle", "FINANZWERTE", "ROHSTOFFE"], label_visibility="collapsed")
    with c3:
        direction_filter = st.selectbox("Richtung", ["Alle Richtungen", "Bullish Reversal", "Bearish Reversal"], label_visibility="collapsed")

    f_macro, f_micro = st.columns(2, gap="small")
    with f_macro:
        macro_filter = st.selectbox(
            "Makro-Phase",
            [
                "Alle Makro",
                "EXTREME",
                "TRANSITION",
                "RELEASE",
                "CONFIRMED",
            ],
            label_visibility="collapsed",
            key="watchlist_macro_phase_filter",
        )
    with f_micro:
        micro_filter = st.selectbox(
            "Mikro-Trigger",
            [
                "Alle Mikro",
                "FRESH BULLISH",
                "FRESH BEARISH",
                "BULLISH TRIGGER",
                "BEARISH TRIGGER",
                "KEIN TRIGGER",
            ],
            label_visibility="collapsed",
            key="watchlist_micro_trigger_filter",
        )

    filtered = pipeline.copy()

    if view == "Fresh Micro":
        if "micro_trigger_fresh" in filtered.columns:
            filtered = filtered[filtered["micro_trigger_fresh"].fillna(False)]
            if "micro_trigger_age_weeks" in filtered.columns:
                filtered = filtered.sort_values(
                    ["micro_trigger_age_weeks", "market_name"],
                    ascending=[True, True],
                )
        else:
            filtered = filtered.iloc[0:0]
    elif view in {"Aligned", "Watch"}:
        keep = []
        for _, filter_row in filtered.iterrows():
            decision = classify_macro_micro_trade(filter_row)
            keep.append(decision["signal"] == view.upper())
        filtered = filtered[pd.Series(keep, index=filtered.index)]
    elif view == "Context Ready":
        filtered = filtered[
            pd.to_numeric(filtered["regime_stage"], errors="coerce").fillna(0) >= 5
        ]
    filtered = _apply_macro_micro_filters(
        filtered,
        macro_filter,
        micro_filter,
    )
    if segment != "Alle":
        filtered = filtered[filtered["segment"].astype(str).eq(segment)]
    if direction_filter == "Bullish Reversal":
        filtered = filtered[pd.to_numeric(filtered["expected_direction"], errors="coerce") > 0]
    elif direction_filter == "Bearish Reversal":
        filtered = filtered[pd.to_numeric(filtered["expected_direction"], errors="coerce") < 0]

    trader_view = filtered.reset_index(drop=True)
    _micro_health = _micro_runtime_health(pipeline)
    if (
        _micro_health["rows"] > 0
        and _micro_health["current_extremes_90_10"] > 0
        and _micro_health["trigger_rows"] == 0
    ):
        with st.expander("Mikro-Datencheck", expanded=False):
            st.warning(
                "Diese Runtime sieht aktuelle 90/10-COT-Extreme, aber keine "
                "historischen Mikro-Trigger. Wenn lokal Trigger erscheinen, "
                "online aber nur '—', laufen Deployment und lokaler Scan "
                "wahrscheinlich nicht mit demselben Daten-/Cache-Stand."
            )
            st.caption(
                f"Zeilen: {_micro_health['rows']} · "
                f"aktuelle 90/10-Extreme: "
                f"{_micro_health['current_extremes_90_10']} · "
                f"historische Trigger: {_micro_health['trigger_rows']} · "
                f"Fresh: {_micro_health['fresh_rows']} · "
                f"Trigger-Metadaten vorhanden: "
                f"{'ja' if _micro_health['metadata'] else 'nein'}"
            )

    _render_trader_table(trader_view)

    with st.expander("Quant-Details · COT-Gruppen & Rohdaten", expanded=False):
        st.caption(
            "Vollständige Research-Ansicht für Quant-Kontrolle. "
            "Die Trader-Watchlist trennt jetzt für alle Märkte zwei Horizonte: Commercial-Netto 156W = langsamer Regime-Druck; Commercial/Retail COT-Index 26W = kurzfristiges Timing. Cross-Group und Preis bleiben Bestätigung. FX behält zusätzlich das eingefrorene Raw-1–2W-Research."
        )
        _render_table(trader_view)

    with st.expander("Pipeline-Logik & 1–4W-Beobachtung", expanded=False):
        st.markdown(f"""
**1 · Commercial 156W State**
`≥ {NET_UPPER_PERCENTILE}` oder `≤ {NET_LOWER_PERCENTILE}` bedeutet nur **historisch extrem**. Keine Richtung wird daraus automatisch abgeleitet.

**2 · Commercial Transition**
Wir beobachten `Δ1W`, `Δ2W` und `Δ4W`. Eine Bewegung aus dem Extrem wird zunächst als **EARLY** geführt. Erst der tatsächliche Zonenaustritt ist ein bestätigter Commercial Release.

**3 · Cross-Group Shift**
Bei Finanzwerten: **Asset Manager + Leveraged Funds**. Bei Rohstoffen: **Producer/Merchant + Managed Money**. Entscheidend ist nicht nur der aktuelle Percentile-Wert, sondern ob sich die jeweilige Netto-Position über 1–4 Wochen in Richtung des möglichen neuen Regimes verändert.

**4 · Nonreportable Context**
Die kleineren, nicht meldepflichtigen Positionen werden als konträrer Kontext beobachtet. `Nonreportable` wird bewusst **nicht** automatisch als Retail bezeichnet.

**5 · Price / Seasonality**
Preisstruktur und Saisonalität werden erst spät ergänzt. **CONTEXT READY ist noch kein Trade**: Supply-&-Demand-Zone, Entry, SL und TP bleiben im Trade Planner eine separate manuelle Entscheidung.

Der **26W-COT-Index bleibt erhalten**, ist aber aus der operativen Watchlist entfernt. Er bleibt im Advanced Research und in historischen Snapshots für spätere ML-/Out-of-Sample-Vergleiche verfügbar.
""")

if not scan["errors"].empty:
    with st.expander(f"Datenprobleme · {len(scan['errors'])} Märkte", expanded=False):
        st.dataframe(scan["errors"], use_container_width=True, hide_index=True)
