from __future__ import annotations

import numpy as np
import streamlit as st

from src.style import apply_style, context_strip, page_header, section_line
from src.volatility_regime import build_volatility_regime

apply_style()
page_header("Research · Risk", "Volatility Regime", "Options-implied Stress- und Risk-Regime als unabhängiger Kontext.", "V3.22.0 · VOLATILITY REGIME")
st.caption("Externer Research-Layer. Kein COT-Signal und kein Entry-Filter.")

@st.cache_data(ttl=60 * 60, show_spinner=False)
def _load_snapshot():
    return build_volatility_regime()

with st.spinner("Volatility-Regime wird geladen …"):
    _snapshot = _load_snapshot()
_vix = _snapshot.get("vix", np.nan)
_vix_text = f"{float(_vix):.2f}" if np.isfinite(_vix) else "N/V"
context_strip([
    ("Regime", str(_snapshot.get("regime", "N/V"))),
    ("Stress", str(_snapshot.get("stress", "N/V"))),
    ("VIX", _vix_text),
    ("Curve", str(_snapshot.get("curve", "N/V"))),
])
section_line("Volatility Context", "Spot-Stress · mittlere Laufzeit · Momentum")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Volatility Regime", str(_snapshot.get("regime", "N/V")))
with c2:
    st.metric("Term Structure", str(_snapshot.get("curve", "N/V")))
with c3:
    st.metric("Momentum", str(_snapshot.get("momentum", "N/V")))
_as_of = _snapshot.get("as_of")
if _as_of is not None:
    st.caption(f"Datenstand: {_as_of:%d.%m.%Y} · CBOE-Reihen über FRED.")
else:
    st.info("Volatility-Daten sind aktuell nicht verfügbar.")
st.caption("Die Seite zeigt nur den resultierenden Stress-Kontext. Interne Klassifikationsschwellen bleiben verborgen.")
