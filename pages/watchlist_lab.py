from __future__ import annotations

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
    "Watchlist Lab",
    "Interne Watchlist-Methodik und Produktionsparameter. ADMIN-only.",
    "V3.20.0 · TRADER IP SHIELD",
)
section_line("Produktionsparameter", "nur interne Referenz")
st.dataframe(
    {
        "Parameter": [
            "COT Index Fenster", "Index obere Grenze", "Index untere Grenze",
            "Netto Validierung", "Netto obere Grenze", "Netto untere Grenze",
            "Commercial Range", "Release aktiv",
        ],
        "Wert": [
            f"{COT_INDEX_WEEKS}W", INDEX_UPPER, INDEX_LOWER,
            f"{NET_VALIDATION_WEEKS}W", NET_UPPER_PERCENTILE, NET_LOWER_PERCENTILE,
            f"{COMMERCIAL_RANGE_WEEKS}W", f"{RELEASE_ACTIVE_WEEKS}W",
        ],
    },
    use_container_width=True,
    hide_index=True,
)
section_line("Pipeline", "interne Entscheidungsstruktur")
st.markdown(
    """
1. COT-Daten report-spezifisch auflösen.
2. Makro-/Zykluszustand und Validierung berechnen.
3. Releases bzw. Watch-Zustände bestimmen.
4. Mikro-Timing und Seasonality separat halten.
5. Trader-Seite zeigt nur das resultierende Analyseergebnis.
"""
)
st.warning("Methodik-Änderungen hier ändern nicht automatisch die Produktionslogik.")
