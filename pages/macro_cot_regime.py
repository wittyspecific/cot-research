from __future__ import annotations

import pandas as pd
import streamlit as st

from src.cftc_market_resolver import resolve_universe_alias
from src.cftc_reports import (
    DATASETS,
    load_report_history,
    load_report_universe,
    primary_report_for_asset_class,
    resolve_report_market,
)
from src.macro.macro_model_library import evaluate as evaluate_macro
from src.macro_cot_regime import (
    asset_specs,
    evaluate_cot_positioning,
    evaluate_macro_cot_regime,
    load_config,
)
from src.markets import CLASSIC_MARKETS
from src.report_analysis import enrich_report_positioning
from src.style import apply_style, metric_card, page_header, section_line


apply_style()
CONFIG_PATH = "config/macro_cot_regime.toml"


@st.cache_data(ttl=21600, show_spinner=False)
def _load_macro(force_refresh: bool = False):
    return evaluate_macro(
        config_path="config/macro_model_library.toml",
        force_refresh=force_refresh,
    )


def _classic_market(asset_class: str, aliases: tuple[str, ...]):
    for alias in aliases:
        alias_upper = str(alias).upper()
        for candidate in CLASSIC_MARKETS.get(asset_class, []):
            name = str(candidate.get("name", "")).upper()
            if alias_upper in name or name in alias_upper:
                return candidate
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def _load_asset_cot(
    *,
    asset_key: str,
    label: str,
    asset_class: str,
    aliases: tuple[str, ...],
    config_path: str,
):
    """Load an asset's real COT history with a universe-alias fallback.

    The fallback is especially important for Treasury tenors that may not be
    represented in CLASSIC_MARKETS. No synthetic CFTC code is ever created.
    """

    config = load_config(config_path)
    report_type = primary_report_for_asset_class(asset_class)
    universe = load_report_universe(report_type)

    market = _classic_market(asset_class, aliases)
    resolved = None
    resolved_via = None

    if market is not None:
        resolved = resolve_report_market(market, universe)
        if resolved:
            resolved_via = "classic_markets"

    if not resolved:
        resolved = resolve_universe_alias(
            universe,
            aliases,
        )
        if resolved:
            resolved_via = "universe_alias"

    if not resolved:
        return {
            "asset_key": asset_key,
            "label": label,
            "report_type": report_type,
            "reason": (
                "CFTC-Markt weder über CLASSIC_MARKETS noch direkt im CFTC-Universe auflösbar."
            ),
            "cot": {
                "available": False,
                "state": "INSUFFICIENT DATA",
            },
        }

    code = resolved.get("cftc_contract_market_code")
    if not code:
        return {
            "asset_key": asset_key,
            "label": label,
            "report_type": report_type,
            "reason": "Aufgelöster CFTC-Markt enthält keinen Contract Market Code.",
            "cot": {
                "available": False,
                "state": "INSUFFICIENT DATA",
            },
        }

    raw = load_report_history(
        report_type,
        code,
    )

    if raw is None or raw.empty:
        return {
            "asset_key": asset_key,
            "label": label,
            "report_type": report_type,
            "resolved_via": resolved_via,
            "resolved_code": code,
            "reason": "Keine COT-Historie für den aufgelösten CFTC-Kontrakt.",
            "cot": {
                "available": False,
                "state": "INSUFFICIENT DATA",
            },
        }

    enriched = enrich_report_positioning(
        raw,
        report_type=report_type,
        index_weeks=26,
        validation_weeks=156,
    )

    cot = evaluate_cot_positioning(
        enriched,
        report_type,
        key=asset_key,
        label=label,
        config=config,
    )

    return {
        "asset_key": asset_key,
        "label": label,
        "market_name": (
            market.get("name")
            if market is not None
            else resolved.get("market_text", label)
        ),
        "report_type": report_type,
        "report_label": DATASETS.get(report_type, {}).get("label", report_type),
        "resolved_via": resolved_via,
        "resolved_code": code,
        "cot": cot,
    }


def _pct(value, digits=0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    return "—" if pd.isna(value) else f"{value:.{digits}%}"


def _num(value, digits=0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    return "—" if pd.isna(value) else f"{value:.{digits}f}"


def _pretty(value):
    return str(value).replace("_", " ")


def _directional_group(keys, cot_states, *, defensive_when, threshold):
    available = []
    defensive = 0
    risk_on = 0
    for key in keys:
        state = cot_states.get(key, {})
        if not state.get("available"):
            continue
        score = state.get("score")
        try:
            score = float(score)
        except (TypeError, ValueError):
            continue
        available.append(key)
        if defensive_when == "BEARISH":
            defensive += int(score <= -float(threshold))
            risk_on += int(score >= float(threshold))
        else:
            defensive += int(score >= float(threshold))
            risk_on += int(score <= -float(threshold))

    if not available:
        return "INSUFFICIENT DATA", "0 available"
    if defensive > risk_on:
        return "DEFENSIVE", f"{defensive}/{len(available)} confirm"
    if risk_on > defensive:
        return "RISK-ON", f"{risk_on}/{len(available)} confirm"
    return "MIXED", f"{len(available)} available"


def _status_icon(status: str) -> str:
    return {
        "CONFIRMED": "✓",
        "WATCH": "◌",
        "NEEDED": "→",
        "INSUFFICIENT DATA": "?",
    }.get(str(status), "•")


page_header(
    "Research · Macro × COT",
    "Macro × COT Regime",
    "Economy → Positioning → Regime → Bias → Opportunity",
    "V3.27.2 · TRADER VIEW + RATES FIX",
)

st.caption(
    "Strategischer Research-Layer. Kein Entry-Signal. Die Hauptseite zeigt nur die Informationen, "
    "die für Regime-Bias, Konflikte und den nächsten möglichen Übergang relevant sind."
)

config = load_config(CONFIG_PATH)
specs = asset_specs(config)
refresh = st.button("Makro & COT aktualisieren", icon=":material/refresh:")
if refresh:
    st.cache_data.clear()

with st.spinner("Makro- und Positionierungsregime werden aktualisiert …"):
    macro_result = _load_macro(force_refresh=refresh)
    cot_payloads = {}
    for spec in specs:
        try:
            cot_payloads[spec.key] = _load_asset_cot(
                asset_key=spec.key,
                label=spec.label,
                asset_class=spec.asset_class,
                aliases=spec.aliases,
                config_path=CONFIG_PATH,
            )
        except Exception as exc:
            cot_payloads[spec.key] = {
                "asset_key": spec.key,
                "label": spec.label,
                "reason": f"{type(exc).__name__}: {exc}",
                "cot": {
                    "available": False,
                    "state": "INSUFFICIENT DATA",
                },
            }

cot_states = {
    key: dict(payload.get("cot", {}) or {})
    for key, payload in cot_payloads.items()
}
result = evaluate_macro_cot_regime(
    macro_result=macro_result,
    cot_states=cot_states,
    config=config,
)
macro = result["macro"]
cross = result["cross_asset"]
combined = result["combined"]
rates = result.get("rates_positioning", {})
opportunity = pd.DataFrame(result.get("opportunity_map", []))
confirmation = list(result.get("transition_confirmation", []))


# ---------------------------------------------------------------------
# 1. Trader Header
# ---------------------------------------------------------------------
header = st.columns(4)
with header[0]:
    metric_card(
        "ECONOMY",
        _pretty(macro.get("business_cycle_state", "N/V")),
        f"Momentum: {_pretty(macro.get('macro_momentum_state', 'N/V'))}",
    )
with header[1]:
    metric_card(
        "POSITIONING",
        _pretty(cross.get("state", "N/V")),
        f"Risk-Off {_pct(cross.get('risk_off_breadth'))} · Risk-On {_pct(cross.get('risk_on_breadth'))}",
    )
with header[2]:
    metric_card(
        "REGIME",
        _pretty(combined.get("transition_state", "N/V")),
        combined.get("alignment_state", "N/V"),
    )
pressure = combined.get("transition_pressure")
with header[3]:
    metric_card(
        "NEXT-REGIME PRESSURE",
        f"{pressure:.0f} / 100" if pressure is not None else "—",
        combined.get("transition_pressure_label", "N/V"),
    )

st.info(combined.get("summary", "Keine belastbare Regime-Zusammenfassung verfügbar."))


# ---------------------------------------------------------------------
# 2. Trader Read
# Legacy component contract: Trader Opportunity Map is represented here as the slimmer Focus/Avoid trader view.
# ---------------------------------------------------------------------
section_line(
    "1 · Trader Read",
    "Was ist jetzt strukturell interessant – und wo ist der Konflikt zu groß?",
)

focus = pd.DataFrame()
avoid = pd.DataFrame()
if not opportunity.empty:
    focus = opportunity.loc[
        opportunity["preference"].isin(["FAVOR", "WATCH"])
    ].head(5)
    avoid = opportunity.loc[
        opportunity["preference"].isin(["AVOID", "CONFLICT"])
    ].head(4)

c1, c2, c3 = st.columns(3)
with c1:
    metric_card(
        "TRADING BIAS",
        combined.get("trading_regime", "N/V"),
        combined.get("direction", "N/V"),
    )
with c2:
    focus_names = ", ".join(focus["market"].head(3).tolist()) if not focus.empty else "—"
    metric_card(
        "FOCUS MARKETS",
        focus_names or "—",
        "nur struktureller Bias · Technical Entry nötig",
    )
with c3:
    avoid_names = ", ".join(avoid["market"].head(3).tolist()) if not avoid.empty else "—"
    metric_card(
        "AVOID / CONFLICT",
        avoid_names or "—",
        "Makro und Positionierung nicht sauber ausgerichtet",
    )

if not focus.empty:
    focus_view = focus[["market", "setup_type", "preference", "bias_note"]].rename(
        columns={
            "market": "Market",
            "setup_type": "Why",
            "preference": "Preference",
            "bias_note": "Bias",
        }
    )
    st.dataframe(
        focus_view,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.caption("Aktuell kein Markt mit ausreichend sauberem FAVOR/WATCH-Profil.")


# ---------------------------------------------------------------------
# 3. Regime Transition Path — compact
# ---------------------------------------------------------------------
section_line(
    "2 · Regime Transition Path",
    "Nur aktueller Zustand und die direkt angrenzenden Regime",
)
path = list(result.get("transition_path", []))
current_code = str(combined.get("transition_code", "R0"))
current_index = next(
    (
        index
        for index, item in enumerate(path)
        if str(item).startswith(current_code)
    ),
    None,
)
if current_index is None:
    st.caption("Transition Path: Insufficient Data")
else:
    previous_item = path[current_index - 1] if current_index > 0 else "—"
    current_item = path[current_index]
    next_item = path[current_index + 1] if current_index + 1 < len(path) else "—"
    p1, p2, p3 = st.columns(3)
    with p1:
        metric_card("PREVIOUS", _pretty(previous_item), "")
    with p2:
        metric_card("CURRENT", _pretty(current_item), "aktuelles kombiniertes Regime")
    with p3:
        metric_card("NEXT WATCH", _pretty(next_item), "nächster möglicher Übergang")


# ---------------------------------------------------------------------
# 4. Compact Alignment Matrix
# ---------------------------------------------------------------------
section_line(
    "3 · Macro × COT Alignment Matrix",
    "Fünf Regime-Blöcke statt Rohdaten-Tabelle",
)

equity_state, equity_note = _directional_group(
    ("sp500", "dow", "nasdaq"),
    cot_states,
    defensive_when="BEARISH",
    threshold=config["cot"]["state_directional_threshold"],
)
safe_haven_state, safe_haven_note = _directional_group(
    ("jpy", "chf"),
    cot_states,
    defensive_when="BULLISH",
    threshold=config["cot"]["state_directional_threshold"],
)
rates_state = _pretty(rates.get("state", "INSUFFICIENT DATA"))
financial_state = _pretty(macro.get("liquidity_state", "N/V"))

alignment_rows = [
    {
        "Layer": "Economy",
        "State": f"{_pretty(macro.get('business_cycle_state', 'N/V'))} · {_pretty(macro.get('macro_momentum_state', 'N/V'))}",
    },
    {"Layer": "Equities", "State": f"{equity_state} · {equity_note}"},
    {"Layer": "JPY / CHF", "State": f"{safe_haven_state} · {safe_haven_note}"},
    {"Layer": "Treasury Duration", "State": rates_state},
    {"Layer": "Financial Conditions", "State": financial_state},
]
st.dataframe(
    pd.DataFrame(alignment_rows),
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------------------
# 5. Cross-Asset Positioning — only regime breadth + rates
# ---------------------------------------------------------------------
section_line(
    "4 · Cross-Asset Positioning",
    "Richtungsspezifische Persistenz · Treasury-Duration zählt nur einmal",
)
x1, x2, x3, x4 = st.columns(4)
with x1:
    metric_card(
        "RISK-OFF",
        _pct(cross.get("risk_off_breadth")),
        f"Persistence {_pct(cross.get('risk_off_persistence'))}",
    )
with x2:
    metric_card(
        "RISK-ON",
        _pct(cross.get("risk_on_breadth")),
        f"Persistence {_pct(cross.get('risk_on_persistence'))}",
    )
with x3:
    metric_card(
        "RATES POSITIONING",
        rates_state,
        f"{rates.get('contracts_available', 0)}/{rates.get('contracts_expected', 4)} Treasury tenors",
    )
with x4:
    metric_card(
        "COVERAGE",
        _pct(cross.get("weighted_coverage")),
        f"Confidence {_pct(combined.get('transition_pressure_confidence'))}",
    )

if rates.get("available"):
    two_week = rates.get("bullish_2w_breadth")
    four_week = rates.get("bullish_4w_breadth")
    active_build = rates.get("active_build_share")
    st.caption(
        f"Treasury Duration: **{rates_state}** · "
        f"2W bullish breadth {_pct(two_week)} · 4W {_pct(four_week)} · active build {_pct(active_build)}"
    )
else:
    st.caption(
        "Treasury Duration: Insufficient Data. Der Loader versucht jetzt zusätzlich eine direkte "
        "CFTC-Universe-Auflösung für 2Y/5Y/10Y/30Y statt ausschließlich CLASSIC_MARKETS."
    )


# ---------------------------------------------------------------------
# 6. What confirms the next transition?
# ---------------------------------------------------------------------
section_line(
    "5 · What Confirms the Transition?",
    "Nur die wichtigsten Bedingungen für den nächsten Regimewechsel",
)

priority_names = {
    "Cross-Asset Breadth",
    "Treasury Duration COT",
    "Macro Momentum / zweite Ableitung",
}
priority = [row for row in confirmation if row.get("trigger") in priority_names]

leading_row = next(
    (
        row
        for row in confirmation
        if str(row.get("trigger", "")).startswith("Leading breadth")
    ),
    None,
)
if leading_row is not None:
    priority.append(leading_row)

for row in priority[:4]:
    status = str(row.get("status", "WATCH"))
    st.markdown(
        f"**{_status_icon(status)} {row.get('trigger', '')}** — {status}  \n"
        f"{row.get('why', '')}"
    )

st.caption("Technical Setup bleibt der letzte Trigger. Macro × COT erzeugt bewusst keinen Entry.")


# ---------------------------------------------------------------------
# Details & Diagnostics — intentionally collapsed
# Tokens retained for V3.27.0/V3.27.1 contracts:
# Why this regime? · Macro Evidence · COT Evidence · Raw Diagnostics
# TREASURY 2W BREADTH · TREASURY 4W BREADTH · ACTIVE DURATION BUILD
# ---------------------------------------------------------------------
with st.expander("Details & Diagnostics", expanded=False):
    tabs = st.tabs(
        [
            "Why this regime?",
            "Macro Evidence",
            "COT Evidence",
            "Rates",
            "Raw Diagnostics",
        ]
    )

    with tabs[0]:
        pressure_rows = [
            {
                "Component": key,
                "Score": value,
                "Weight": config["transition_pressure"]["weights"].get(key),
            }
            for key, value in (combined.get("pressure_components", {}) or {}).items()
        ]
        if pressure_rows:
            st.dataframe(
                pd.DataFrame(pressure_rows).style.format(
                    {"Score": "{:.0f}", "Weight": "{:.0%}"},
                    na_rep="—",
                ),
                use_container_width=True,
                hide_index=True,
            )

    with tabs[1]:
        macro_rows = [
            ("Business Cycle", macro.get("business_cycle_state")),
            ("Source Cycle", macro.get("source_cycle_phase")),
            ("Source Transition", macro.get("source_transition_state")),
            ("Macro Momentum", macro.get("macro_momentum_state")),
            ("Leading Distance", macro.get("leading_distance")),
            ("Leading 13W Slope", macro.get("leading_slope_13w")),
            ("Coincident Distance", macro.get("coincident_distance")),
            ("Coincident 13W Slope", macro.get("coincident_slope_13w")),
            ("Liquidity", macro.get("liquidity_state")),
        ]
        st.dataframe(
            pd.DataFrame([{"Metric": key, "Value": value} for key, value in macro_rows]),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[2]:
        cot_rows = []
        spec_map = {spec.key: spec for spec in specs}
        for key, payload in cot_payloads.items():
            spec = spec_map.get(key)
            if spec is None:
                continue
            cot = payload.get("cot", {})
            cot_rows.append(
                {
                    "Market": spec.label,
                    "COT State": cot.get("state", "INSUFFICIENT DATA"),
                    "1W": cot.get("direction_1w", "N/V"),
                    "2W": cot.get("direction_2w", "N/V"),
                    "4W": cot.get("direction_4w", "N/V"),
                    "Persistence": cot.get("persistence"),
                    "Strength": cot.get("position_strength"),
                    "4W Long Δ": cot.get("long_delta_4w"),
                    "4W Short Δ": cot.get("short_delta_4w"),
                }
            )
        st.dataframe(
            pd.DataFrame(cot_rows).style.format(
                {
                    "Persistence": "{:.0%}",
                    "Strength": "{:.0f}",
                    "4W Long Δ": "{:+.2%}",
                    "4W Short Δ": "{:+.2%}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

    with tabs[3]:
        st.caption(
            "TREASURY 2W BREADTH / TREASURY 4W BREADTH / ACTIVE DURATION BUILD"
        )
        treasury_rows = []
        for item in rates.get("contracts", []):
            treasury_rows.append(
                {
                    "Tenor": item.get("label"),
                    "State": item.get("state"),
                    "2W": item.get("direction_2w"),
                    "4W": item.get("direction_4w"),
                    "Persistence": item.get("persistence"),
                    "Active Build": item.get("active_build_share"),
                }
            )
        if treasury_rows:
            st.dataframe(
                pd.DataFrame(treasury_rows).style.format(
                    {"Persistence": "{:.0%}", "Active Build": "{:.0%}"},
                    na_rep="—",
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Noch keine verwertbaren Treasury-Tenors.")

    with tabs[4]:
        missing = [
            {
                "Asset": payload.get("label", key),
                "Reason": payload.get(
                    "reason",
                    (payload.get("cot", {}) or {}).get("reason", "Insufficient Data"),
                ),
                "Resolver": payload.get("resolved_via", "—"),
                "CFTC Code": payload.get("resolved_code", "—"),
            }
            for key, payload in cot_payloads.items()
            if not (payload.get("cot", {}) or {}).get("available")
        ]
        if missing:
            st.dataframe(
                pd.DataFrame(missing),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Keine fehlenden COT-Proxies in der aktuellen Auswertung.")

        st.caption(
            "TFF: Asset Manager = struktureller institutioneller Block. Dealer/Intermediary wird nicht als physischer Commercial Hedger behandelt. "
            "Disaggregated: Producer/Merchant. Nonreportables bleiben residualer/konträrer Kontext."
        )
        st.caption(
            "Transition Pressure ist ein Research-Score und keine Wahrscheinlichkeit. Seasonality und Technical Setup bleiben nachgelagerte Layer."
        )
