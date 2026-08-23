from __future__ import annotations

import pandas as pd
import streamlit as st

from src.research_panel_v1 import MacroRegimeState, macro_regime_snapshot
from src.trader_theme import apply_trader_dark_theme, render_card, render_page_header, render_summary

apply_trader_dark_theme()
render_page_header("RESEARCH · STRATEGIC REGIME", "Makro-Regime", "Wo steht die Wirtschaft aktuell, und preist die Positionierung bereits das nächste Regime ein? Business Cycle und Macro × COT werden gebündelt.")
st.caption("V3.29.0 · Macro ist strategischer Kontext, kein Entry-Layer")

@st.cache_data(ttl=21600, show_spinner=False)
def _load_macro(force_refresh: bool = False): return macro_regime_snapshot(force_refresh=force_refresh).to_dict()

_, right = st.columns([5,1])
with right: refresh = st.button("Makro aktualisieren", use_container_width=True)
if refresh: st.cache_data.clear()
with st.spinner("Makro- und Cross-Asset-Regime wird geladen …"):
    payload = _load_macro(refresh)
state = MacroRegimeState(**{k:v for k,v in payload.items() if k in MacroRegimeState.__dataclass_fields__})
if not state.available: st.warning(state.reason or "Insufficient Data")

tabs = st.tabs(["Overview", "Business Cycle", "Macro × COT", "Risk Conditions"])

with tabs[0]:
    c1,c2,c3,c4=st.columns(4)
    with c1: render_card("Business Cycle", state.business_cycle_state, state.macro_momentum_state)
    with c2: render_card("COT Regime", state.cot_regime_state, state.alignment)
    with c3: render_card("Macro × COT State", state.macro_cot_state, state.trading_regime)
    with c4: render_card("Next-Regime Pressure", "—" if state.transition_pressure_score is None else f"{state.transition_pressure_score:.0f}/100", state.transition_pressure_label, tone="warning")
    render_summary(f"Aktuelles Regime: {state.business_cycle_state}. Makro-Dynamik: {state.macro_momentum_state}. Positionierung: {state.cot_regime_state}. Nächste beobachtete Transition: {state.next_regime_direction}.")
    st.markdown("#### Was bestätigt das nächste Regime?")
    confirm = pd.DataFrame(state.transition_confirmation)
    if confirm.empty: st.caption("Insufficient Data")
    else:
        cols=[x for x in ("trigger","status","why") if x in confirm.columns]
        st.dataframe(confirm[cols].rename(columns={"trigger":"Trigger","status":"Status","why":"Warum"}).head(7), use_container_width=True, hide_index=True)
    with st.expander("Why this regime?", expanded=False): st.write({"Business Cycle":state.business_cycle_state,"Macro Momentum":state.macro_momentum_state,"Macro × COT":state.macro_cot_state,"Alignment":state.alignment})

with tabs[1]:
    raw = dict(state.raw_result.get("macro_result", {}) or {}); leading, coincident, lagging = (dict(raw.get(k,{}) or {}) for k in ("leading","coincident","lagging"))
    st.markdown("### Business Cycle"); c1,c2,c3,c4=st.columns(4)
    with c1: render_card("Zyklus", state.business_cycle_state, "strategischer Regime-State")
    with c2: render_card("Momentum", state.macro_momentum_state, "Velocity + zweite Ableitung")
    with c3: render_card("Leading", "—" if leading.get("distance") is None else f"{float(leading['distance']):+.2f}", "Distance vs. Equilibrium", tone="info")
    with c4: render_card("Coincident", "—" if coincident.get("distance") is None else f"{float(coincident['distance']):+.2f}", "aktuelle Wirtschaftsaktivität", tone="info")
    table=pd.DataFrame([{"Tier":"Leading","Distance":leading.get("distance"),"13W Slope":leading.get("slope_13w")},{"Tier":"Coincident","Distance":coincident.get("distance"),"13W Slope":coincident.get("slope_13w")},{"Tier":"Lagging","Distance":lagging.get("distance"),"13W Slope":lagging.get("slope_13w")}])
    st.dataframe(table.style.format({"Distance":"{:+.2f}","13W Slope":"{:+.2f}"},na_rep="—"),use_container_width=True,hide_index=True)
    with st.expander("Macro Evidence", expanded=False): st.json({"leading":leading,"coincident":coincident,"lagging":lagging})

with tabs[2]:
    st.markdown("### Macro × COT"); c1,c2,c3,c4=st.columns(4)
    with c1: render_card("Macro × COT", state.macro_cot_state, state.alignment)
    with c2: render_card("Trading Regime", state.trading_regime, "strategischer Bias")
    with c3: render_card("Risk-Off Breadth", "—" if state.risk_off_breadth is None else f"{state.risk_off_breadth:.0%}", "Persistenz —" if state.risk_off_persistence is None else f"Persistenz {state.risk_off_persistence:.0%}", tone="info")
    with c4: render_card("Risk-On Breadth", "—" if state.risk_on_breadth is None else f"{state.risk_on_breadth:.0%}", "Persistenz —" if state.risk_on_persistence is None else f"Persistenz {state.risk_on_persistence:.0%}", tone="info")
    opp=pd.DataFrame(state.opportunity_map)
    if not opp.empty:
        cols=[x for x in ("market","macro_bias","cot_bias","alignment","setup_type","preference") if x in opp.columns]
        st.dataframe(opp[cols].rename(columns={"market":"Markt","macro_bias":"Makro","cot_bias":"COT","alignment":"Alignment","setup_type":"Setup","preference":"Präferenz"}).head(12),use_container_width=True,hide_index=True)
    with st.expander("COT Evidence", expanded=False):
        mc=dict(state.raw_result.get("macro_cot",{}) or {}); st.json({"rates_positioning":mc.get("rates_positioning",{}),"cross_asset":mc.get("cross_asset",{})})

with tabs[3]:
    st.markdown("### Risk Conditions"); c1,c2,c3,c4=st.columns(4)
    with c1: render_card("Liquidität", state.liquidity_state, "Modifier, nicht Zyklus-Richtung")
    with c2: render_card("Treasury Duration", state.rates_positioning_state, "2Y / 5Y / 10Y / 30Y")
    with c3: render_card("Transition Pressure", "—" if state.transition_pressure_score is None else f"{state.transition_pressure_score:.0f}/100", "Next-Regime Pressure", tone="warning")
    with c4: render_card("Next Watch", state.next_regime_direction, "keine Rezessionswahrscheinlichkeit", tone="warning")
    mc=dict(state.raw_result.get("macro_cot",{}) or {})
    with st.expander("Cross-Asset Evidence", expanded=False): st.json(mc.get("alignment_matrix",[]))
    with st.expander("Transition Triggers", expanded=False): st.json(list(state.transition_confirmation))
    with st.expander("Raw Diagnostics", expanded=False): st.json(state.raw_result)
