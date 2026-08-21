from __future__ import annotations

import streamlit as st

from src.config import (
    COT_INDEX_WEEKS,
    INDEX_LOWER,
    INDEX_UPPER,
    NET_VALIDATION_WEEKS,
    NC_DIV_FLOW_WINDOW_W,
    NC_DIV_PATH_WINDOW_W,
    NC_DIV_STANDARDIZE_HIST_W,
    SEASONAL_HISTORY_WINDOWS,
    SEASONAL_PRIMARY_HORIZON_DAYS,
)
from src.micro_trigger import (
    MICRO_TRIGGER_FRESH_WEEKS,
    MICRO_TRIGGER_LOWER,
    MICRO_TRIGGER_UPPER,
)
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
    "Marktanalyse Lab",
    "Interne COT-Makro-/Mikro-Methodik und Parameter. ADMIN-only.",
    "V3.20.0 · TRADER IP SHIELD",
)
section_line("Makro", "struktureller COT-Kontext")
st.markdown(
    f"""
- COT Index Basisfenster: **{COT_INDEX_WEEKS}W**
- klassische Index-Grenzen: **{INDEX_UPPER}/{INDEX_LOWER}**
- Netto-Validierung: **{NET_VALIDATION_WEEKS}W**
- Zustandsfolge: EXTREME → TRANSITION → RELEASE → CONFIRMED.
"""
)
section_line("Mikro", "eventbasiertes Timing")
st.markdown(
    f"""
- Bullisher Entry-Trigger beim Eintritt in die obere Zone **≥ {MICRO_TRIGGER_UPPER:g}**.
- Bärischer Entry-Trigger beim Eintritt in die untere Zone **≤ {MICRO_TRIGGER_LOWER:g}**.
- Fresh-Fenster: **0–{MICRO_TRIGGER_FRESH_WEEKS} COT-Wochen**.
- Trigger = Ereignis, nicht bloß aktueller Indexwert.
"""
)
section_line("Cross-Group / Flow", "interner Kontext")
st.markdown(
    f"""
- Flow-Fenster: **{NC_DIV_FLOW_WINDOW_W}W**
- Pfad-Fenster: **{NC_DIV_PATH_WINDOW_W}W**
- robuste Historie: **{NC_DIV_STANDARDIZE_HIST_W}W**
- Cross-Group bestätigt/widerspricht; erzeugt nicht allein die Handelsrichtung.
"""
)
section_line("Seasonality", "Confluence only")
st.markdown(
    f"""
- primärer Horizont: **{SEASONAL_PRIMARY_HORIZON_DAYS} Handelstage**
- historische Fenster: **{list(SEASONAL_HISTORY_WINDOWS)}**
- Seasonality überschreibt keinen COT-Zustand.
"""
)
section_line("Produktionspriorität", "interne Referenz")
st.info(
    "Vor aktivem Makro-Release kann ein frischer Mikro-Trigger das Timing führen. "
    "Ab RELEASE/CONFIRMED hat Makro Priorität; gegengerichtetes Mikro = Timing/Korrektur."
)
