from __future__ import annotations

import pandas as pd
import streamlit as st

from src.research_panel_v1 import currency_strength_snapshot
from src.trader_theme import apply_trader_dark_theme, render_card, render_page_header

apply_trader_dark_theme()
render_page_header("RESEARCH · RELATIVE FX", "Währungsstärke", "Welche Währung ist strukturell stärker, welche schwächer? Relative COT-Struktur dient der Pair-Auswahl.")
st.caption("V3.29.0 · USD = transparente relative Null-Basis · kein erfundener COT-Report")

@st.cache_data(ttl=3600, show_spinner=False)
def _snapshot(): return currency_strength_snapshot()

with st.spinner("Relative Currency-COT-Struktur wird geladen …"):
    ranking_rows, pair_rows = _snapshot()
rank_tab, pair_tab = st.tabs(["Currency Ranking", "Pair Opportunities"])

with rank_tab:
    if not ranking_rows: st.info("Insufficient Data")
    else:
        ranking = pd.DataFrame(ranking_rows); strongest, weakest = ranking.iloc[0], ranking.iloc[-1]
        c1, c2, c3 = st.columns(3)
        with c1: render_card("Stärkste Währung", strongest["Währung"], strongest["Struktureller Bias"], tone="positive")
        with c2: render_card("Schwächste Währung", weakest["Währung"], weakest["Struktureller Bias"], tone="negative")
        with c3:
            spread = float(strongest["Relative COT-Stärke"] or 0) - float(weakest["Relative COT-Stärke"] or 0)
            render_card("Relative Spreizung", f"{spread:.0f}", "größere Spreizung = klarere relative Struktur", tone="info")
        st.dataframe(ranking.style.format({"Relative COT-Stärke": "{:+.0f}", "Persistenz": "{:.0%}"}, na_rep="—"), use_container_width=True, hide_index=True)

with pair_tab:
    if not pair_rows: st.info("No Current Signal")
    else:
        pairs = pd.DataFrame(pair_rows)
        st.dataframe(pairs.style.format({"Stärke-Differenz": "{:+.0f}"}, na_rep="—"), use_container_width=True, hide_index=True)
        favorable = pairs[pairs["Alignment"].isin(["FAVOR", "WATCH"])]
        choices = favorable["Pair"].tolist() if not favorable.empty else pairs["Pair"].tolist()
        c1, c2 = st.columns([2, 1])
        with c1: selected = st.selectbox("Pair für Marktanalyse", choices, key="v3290_currency_pair_open")
        with c2:
            st.write(""); st.write("")
            if st.button("In Marktanalyse öffnen", key="v3290_currency_open_button", use_container_width=True):
                st.session_state["research_market_handoff"] = {"kind": "fx", "pair": selected}
                st.switch_page("pages/market_analysis_hub.py")

with st.expander("Methodik & Einschränkungen", expanded=False):
    st.markdown("Nicht-USD-Währungen werden über ihren TFF-Future relativ zum USD gelesen. Pair Opportunity = **Base minus Quote**. USD ist Null-Basis, kein synthetischer Report. Fehlende Daten werden nicht ersetzt.")
