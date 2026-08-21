from __future__ import annotations

import streamlit as st

from src.style import apply_style, page_header, section_line

# V3.20.0 · ADVANCED DIRECT ACCESS GUARD
_v3200_trader = dict(st.session_state.get("auth_trader") or {})
if (
    not _v3200_trader
    or str(_v3200_trader.get("role", "TRADER")).upper() != "ADMIN"
):
    st.error("Kein Zugriff auf den Advanced-Bereich.")
    st.stop()

apply_style()
page_header(
    "Advanced · Methodik",
    "FX Lab",
    "Interne Herleitung von Währungs- und Paarbewertungen. ADMIN-only.",
    "V3.20.0 · TRADER IP SHIELD",
)
section_line("COT Paarbias", "interne Score-Herleitung")
st.markdown(
    """
- Bullish 4/4 = +4, 3/4 = +3, 2/4 = +2, 1/4 = +1.
- Neutral = 0; bearish entsprechend −1 bis −4.
- Paarbias = Stärke Basis − Stärke Gegenwährung.
- Abstand 6–8 = stark, 3–5 = directional, 1–2 = leicht, 0 = neutral.

Die Bedingungen sind Positionierungsmerkmale und nicht vier statistisch unabhängige Signale.
"""
)
section_line("COT + Yield Spreads", "zusätzlicher fundamentaler Kontext")
st.markdown(
    "Yield Spreads ergänzen COT und überschreiben es nicht. Die Trader-Tabelle zeigt "
    "nur Währungen mit ausreichender Yield-Abdeckung."
)
section_line("Seasonality", "Confluence only")
st.markdown("Seasonality unterstützt oder widerspricht; die genaue Methodik bleibt intern.")
