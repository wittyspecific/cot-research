from __future__ import annotations

import pandas as pd
import streamlit as st

from src.fx_relative_cot_analog import FX_PAIRS
from src.markets import CLASSIC_MARKETS
from src.research_panel_v1 import (
    CotPositioningState, MacroRegimeState, SeasonalTurnState,
    cot_state_for_market, derive_trade_opportunity, fx_relative_cot_summary,
    historical_analog_for_fx, historical_analog_for_market,
    macro_regime_snapshot, market_context_for_classic, market_context_for_fx,
    market_names, seasonal_state_for_fx, seasonal_state_for_market,
)
from src.trader_theme import apply_trader_dark_theme, render_card, render_page_header, render_summary

apply_trader_dark_theme()
render_page_header("RESEARCH · TRADE THESIS", "Marktanalyse", "Ein Markt, eine Research-These. COT, saisonaler Turn, historische Analogs und Market Context werden an einem Ort gebündelt.")
st.caption("V3.29.0 · Hauptansicht bewusst schlank · Rohdiagnostik bleibt eingeklappt")

@st.cache_data(ttl=3600, show_spinner=False)
def _cot(a: str, m: str): return cot_state_for_market(a, m).to_dict()
@st.cache_data(ttl=21600, show_spinner=False)
def _season(a: str, m: str): return seasonal_state_for_market(a, m).to_dict()
@st.cache_data(ttl=21600, show_spinner=False)
def _season_fx(p: str): return seasonal_state_for_fx(p).to_dict()
@st.cache_data(ttl=21600, show_spinner=False)
def _macro(): return macro_regime_snapshot().to_dict()

handoff = st.session_state.pop("research_market_handoff", None)
if handoff:
    if handoff.get("kind") == "fx":
        st.session_state["v3290_market_kind"] = "FX-Paar"; st.session_state["v3290_fx_pair"] = handoff.get("pair")
    else:
        st.session_state["v3290_market_kind"] = "Markt"; st.session_state["v3290_asset_class"] = handoff.get("asset_class"); st.session_state["v3290_market_name"] = handoff.get("market_name")

with st.container(border=True):
    c1, c2, c3 = st.columns([.8, 1, 1.45])
    with c1: kind = st.selectbox("Analyse-Typ", ["Markt", "FX-Paar"], key="v3290_market_kind")
    if kind == "Markt":
        classes = list(CLASSIC_MARKETS.keys())
        with c2: asset_class = st.selectbox("Assetklasse", classes, key="v3290_asset_class")
        names = market_names(asset_class)
        if st.session_state.get("v3290_market_name") not in names: st.session_state["v3290_market_name"] = names[0] if names else None
        with c3: market_name = st.selectbox("Markt", names, key="v3290_market_name")
        selection = market_name
    else:
        with c2: st.markdown("**Relative FX-Analyse**"); st.caption("Base-COT minus Quote-COT")
        pairs = list(FX_PAIRS.keys())
        if st.session_state.get("v3290_fx_pair") not in pairs: st.session_state["v3290_fx_pair"] = pairs[0] if pairs else None
        with c3: pair = st.selectbox("FX-Paar", pairs, key="v3290_fx_pair")
        selection = pair

tabs = st.tabs(["Overview", "COT", "Seasonal Turn", "Historical Analog", "Market Context"])
macro_payload = _macro(); macro_state = MacroRegimeState(**{k: v for k, v in macro_payload.items() if k in MacroRegimeState.__dataclass_fields__})

if kind == "Markt":
    cot = CotPositioningState(**_cot(asset_class, market_name)); seasonal = SeasonalTurnState(**_season(asset_class, market_name)); context = market_context_for_classic(asset_class, market_name, macro_state=macro_state); relative = None
else:
    relative = fx_relative_cot_summary(pair); diff = relative.get("differential")
    cot = CotPositioningState(bool(relative.get("available")), pair, "relative tff", "Base minus Quote", str(relative.get("bias", "Insufficient Data")), "RELATIVE COT", diff, abs(float(diff)) if diff is not None else None, None, None, None,
        "N/V", "N/V", "N/V", None, None, None, None, None, None, None, None, None, "Relative FX Positioning", "N/V", None, None, None, "RELATIVE", "Medium Confidence" if relative.get("available") else "Low Confidence", "")
    seasonal = SeasonalTurnState(**_season_fx(pair)); context = market_context_for_fx(pair, macro_state=macro_state)

opportunity = derive_trade_opportunity(cot, seasonal, context)

with tabs[0]:
    st.markdown(f"### {selection}")
    c1, c2, c3, c4 = st.columns(4)
    with c1: render_card("Struktureller Bias", opportunity.structural_bias, cot.structural_group)
    with c2: render_card("Setup State", opportunity.setup_type, opportunity.trade_type)
    with c3: render_card("Conviction", opportunity.conviction, opportunity.confidence_state)
    with c4: render_card("Handlung", opportunity.preferred_action, "Entry bleibt technischer Layer")
    render_summary(opportunity.thesis)
    left, right = st.columns(2)
    with left:
        st.markdown("#### Unterstützt")
        if opportunity.supports:
            for item in opportunity.supports: st.markdown(f"✓ {item}")
        else: st.caption("Noch keine starke Bestätigung.")
    with right:
        st.markdown("#### Konflikte")
        if opportunity.conflicts:
            for item in opportunity.conflicts: st.markdown(f"⚠ {item}")
        else: st.caption("Kein zentraler Konflikt erkannt.")
    with st.expander("Why this regime?", expanded=False): st.write({"COT": cot.structural_bias, "Seasonality": seasonal.turn_read, "Market Context": context.alignment, "Setup Type": opportunity.setup_type})

with tabs[1]:
    st.markdown("### COT")
    if kind == "Markt":
        c1, c2, c3, c4 = st.columns(4)
        with c1: render_card("156W Struktur", "—" if cot.commercial_net_156w_percentile is None else f"{cot.commercial_net_156w_percentile:.0f}", cot.structural_group, tone="info")
        with c2: render_card("26W COT-Index", "—" if cot.cot_index_26w is None else f"{cot.cot_index_26w:.0f}", "kurzfristiges Extrem-/Fortsetzungssignal", tone="info")
        with c3: render_card("Persistenz", "—" if cot.persistence is None else f"{cot.persistence:.0%}", "1W / 2W / 4W", tone="info")
        with c4: render_card("Mikro-COT", cot.micro_bias, cot.momentum_context)
        flow = pd.DataFrame([
            {"Fenster": "4W", "Richtung": cot.direction_4w, "Long Δ": cot.long_delta_4w, "Short Δ": cot.short_delta_4w, "Net Δ": cot.net_delta_4w},
            {"Fenster": "2W", "Richtung": cot.direction_2w, "Long Δ": cot.long_delta_2w, "Short Δ": cot.short_delta_2w, "Net Δ": cot.net_delta_2w},
            {"Fenster": "1W", "Richtung": cot.direction_1w, "Long Δ": cot.long_delta_1w, "Short Δ": cot.short_delta_1w, "Net Δ": cot.net_delta_1w},
        ])
        st.dataframe(flow.style.format({"Long Δ": "{:+.4f}", "Short Δ": "{:+.4f}", "Net Δ": "{:+.4f}"}, na_rep="—"), use_container_width=True, hide_index=True)
        st.caption(f"Release: {cot.freshness_state} · Report {cot.report_date or '—'}")
    else:
        base, quote = dict(relative.get("base", {})), dict(relative.get("quote", {})); c1, c2, c3 = st.columns(3)
        with c1: render_card(f"{FX_PAIRS[pair]['base']} COT", base.get("structural_bias", "Insufficient Data"), "Score —" if base.get("score") is None else f"Score {base['score']:+.0f}")
        with c2: render_card(f"{FX_PAIRS[pair]['quote']} COT", quote.get("structural_bias", "Insufficient Data"), "Score —" if quote.get("score") is None else f"Score {quote['score']:+.0f}")
        with c3: render_card("Relative Differenz", "—" if relative.get("differential") is None else f"{relative['differential']:+.0f}", relative.get("bias", "No Current Signal"), tone="info")
    with st.expander("COT Evidence", expanded=False): st.json(cot.to_dict())

with tabs[2]:
    st.markdown("### Seasonal Turn")
    c1, c2, c3, c4 = st.columns(4)
    with c1: render_card("Turn", seasonal.turn_type, "Distanz —" if seasonal.distance_days is None else "HEUTE" if seasonal.distance_days == 0 else f"Distanz {seasonal.distance_days:+d}T")
    with c2: render_card("Robustheit", seasonal.robustness, "20/40/60T")
    with c3: render_card("COT am Turn", seasonal.cot_confirmation, "1W/2W/4W Flow am Wendefenster")
    with c4: render_card("Turn Read", seasonal.turn_read, "Seasonality ist Timing-Kontext")
    st.dataframe(pd.DataFrame([{"Forward":"20T","Richtung":seasonal.direction_20t},{"Forward":"40T","Richtung":seasonal.direction_40t},{"Forward":"60T","Richtung":seasonal.direction_60t}]), use_container_width=True, hide_index=True)
    with st.expander("Transition Triggers", expanded=False): st.write({"Unterstützer": list(seasonal.supporters), "Konflikte": list(seasonal.conflicts), "Turn": seasonal.turn_type, "Distanz": seasonal.distance_days})

with tabs[3]:
    st.markdown("### Historical Analog"); st.caption("Research-Kontext, keine kalibrierte Wahrscheinlichkeit.")
    c1, c2 = st.columns(2)
    with c1: horizon = st.selectbox("Forward-Horizont", [4,8,12], index=1, format_func=lambda x:f"{x}W", key="v3290_analog_horizon")
    with c2: top_n = st.selectbox("Historische Matches", [5,8,10,12], index=1, key="v3290_analog_matches")
    if st.button("Analogs berechnen", key="v3290_run_analog"):
        with st.spinner("Historische Setups werden gesucht …"):
            analog = historical_analog_for_market(asset_class, market_name, top_n=top_n, horizon_weeks=horizon) if kind == "Markt" else historical_analog_for_fx(pair, top_n=top_n, horizon_weeks=horizon)
        if not analog.available: st.info(analog.reason or "No Current Signal")
        else:
            matches = pd.DataFrame(
                analog.top_matches
            )

            forward_col = (
                f"{analog.horizon_weeks}W"
            )

            if (
                not matches.empty
                and forward_col in matches.columns
            ):
                forward_returns = pd.to_numeric(
                    matches[
                        forward_col
                    ],
                    errors="coerce",
                ).dropna()
            else:
                forward_returns = pd.Series(
                    dtype=float
                )

            bullish_rate = (
                float(
                    (
                        forward_returns
                        > 0
                    ).mean()
                )
                if not forward_returns.empty
                else None
            )

            bearish_rate = (
                float(
                    (
                        forward_returns
                        < 0
                    ).mean()
                )
                if not forward_returns.empty
                else None
            )

            st.caption(
                f"Engine: {analog.engine} · "
                f"N={analog.sample_size} · "
                f"{analog.sample_quality}"
            )

            c1, c2, c3, c4 = st.columns(
                4
            )

            with c1:
                render_card(
                    "Analog Bias",
                    analog.outcome_bias,
                    f"{analog.horizon_weeks}W Forward",
                )

            with c2:
                render_card(
                    "Bullish %",
                    (
                        "—"
                        if bullish_rate is None
                        else f"{bullish_rate:.0%}"
                    ),
                    "Forward Return > 0",
                    tone="positive",
                )

            with c3:
                render_card(
                    "Bearish %",
                    (
                        "—"
                        if bearish_rate is None
                        else f"{bearish_rate:.0%}"
                    ),
                    "Forward Return < 0",
                    tone="negative",
                )

            with c4:
                render_card(
                    "Median Forward",
                    (
                        "—"
                        if analog.median_forward_return
                        is None
                        else f"{analog.median_forward_return:+.2%}"
                    ),
                    f"{analog.horizon_weeks}W",
                    tone="info",
                )

            render_summary(
                (
                    f"Historische Analogs: {analog.outcome_bias} · "
                    f"Bullish "
                    f"{'—' if bullish_rate is None else f'{bullish_rate:.0%}'} · "
                    f"Bearish "
                    f"{'—' if bearish_rate is None else f'{bearish_rate:.0%}'} · "
                    f"{analog.sample_quality}."
                )
            )
    else: st.caption("Wird erst auf Anforderung gerechnet, damit die Hauptansicht schnell bleibt.")

with tabs[4]:
    st.markdown("### Market Context")
    c1,c2,c3,c4=st.columns(4)
    with c1: render_card("Makro-Regime", context.business_cycle_state, context.macro_momentum_state)
    with c2: render_card("Volatilität", context.volatility_regime_state, "aktuelles Preisregime")
    with c3: render_card("Cross-Asset", context.cross_asset_support_state, context.intermarket_state)
    with c4: render_card("Transition Pressure", "—" if context.transition_pressure_score is None else f"{context.transition_pressure_score:.0f}/100", "Druck auf das nächste Regime", tone="warning")
    st.dataframe(pd.DataFrame([{"Layer":"Business Cycle","State":context.business_cycle_state},{"Layer":"Macro Momentum","State":context.macro_momentum_state},{"Layer":"Intermarket","State":context.intermarket_state},{"Layer":"Volatility","State":context.volatility_regime_state},{"Layer":"Cross-Asset","State":context.cross_asset_support_state}]), use_container_width=True, hide_index=True)
    with st.expander("Macro Evidence", expanded=False): st.write({"Risk-Off Breadth": context.risk_off_breadth, "Risk-On Breadth": context.risk_on_breadth, "Macro Bias": context.macro_bias})
    with st.expander("Cross-Asset Evidence", expanded=False): st.write({"Alignment": context.alignment, "COT Bias": context.cot_bias, "Intermarket": context.intermarket_state})
    with st.expander("Raw Diagnostics", expanded=False): st.json({"COT": cot.to_dict(), "Seasonality": seasonal.to_dict(), "Context": context.to_dict()})
