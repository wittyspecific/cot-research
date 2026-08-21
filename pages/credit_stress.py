from __future__ import annotations

import numpy as np
import streamlit as st

from src.credit_stress import build_credit_stress
from src.style import apply_style, context_strip, page_header, section_line

apply_style()
page_header("Research · Credit", "Credit Stress", "US-Credit-Spreads als unabhängiger Risiko-Unterbau für Cross-Asset-Kontext.", "V3.22.0 · CREDIT STRESS")
st.caption("Externer Research-Layer. Credit bestätigt oder widerspricht dem Risk-Kontext, erzeugt aber kein eigenes Trade-Signal.")

@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def _load_snapshot():
    return build_credit_stress()

with st.spinner("Credit-Stress wird geladen …"):
    _snapshot = _load_snapshot()
_hy = _snapshot.get("hy_oas", np.nan)
_ig = _snapshot.get("ig_oas", np.nan)
_hy_text = f"{float(_hy):.2f}%" if np.isfinite(_hy) else "N/V"
_ig_text = f"{float(_ig):.2f}%" if np.isfinite(_ig) else "N/V"
context_strip([
    ("Credit Regime", str(_snapshot.get("regime", "N/V"))),
    ("Spread Direction", str(_snapshot.get("direction", "N/V"))),
    ("HY OAS", _hy_text),
    ("IG OAS", _ig_text),
])
section_line("Credit Context", "High Yield · Investment Grade · Spread-Dynamik")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Credit Regime", str(_snapshot.get("regime", "N/V")))
with c2:
    st.metric("HY OAS", _hy_text)
with c3:
    st.metric("IG OAS", _ig_text)
_as_of = _snapshot.get("as_of")
if _as_of is not None:
    st.caption(f"Datenstand: {_as_of:%d.%m.%Y} · ICE BofA OAS über FRED.")
else:
    st.info("Credit-Daten sind aktuell nicht verfügbar.")
if _snapshot.get("regime") == "STRESS":
    st.warning("Credit signalisiert erhöhten Stress bzw. breitere Risikoaufschläge.")
elif _snapshot.get("regime") == "CALM":
    st.success("Credit zeigt aktuell keinen erhöhten Stress.")
else:
    st.info("Credit ist aktuell gemischt und liefert keine klare Bestätigung.")
st.caption("Die Seite zeigt nur den resultierenden Credit-Kontext. Interne Klassifikationsschwellen bleiben verborgen.")
