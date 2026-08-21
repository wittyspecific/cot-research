from __future__ import annotations

import pandas as pd
import streamlit as st

from src.market_risk_regime import build_market_risk_regime
from src.style import apply_style, context_strip, page_header, section_line
from src.watchlist import scan_classic_markets

apply_style()

page_header(
    "Research · Cross-Asset",
    "Market Regime",
    "Globaler Risk-On/Risk-Off-Kontext aus bestehenden COT-Märkten.",
    "V3.22.0 · MARKET REGIME",
)
st.caption("Research-/Kontextschicht. Das Regime verändert weder COT-Richtung, Watchlist-Signal, Entry, Risiko noch Execution.")

with st.spinner("Cross-Asset-COT-Regime wird aufgebaut …"):
    _scan = scan_classic_markets()
_all_markets = _scan.get("all_markets", pd.DataFrame())
if isinstance(_all_markets, list):
    _all_markets = pd.DataFrame(_all_markets)
if _all_markets is None:
    _all_markets = pd.DataFrame()
_snapshot = build_market_risk_regime(_all_markets)

context_strip([
    ("Macro Regime", str(_snapshot["regime"])),
    ("Breadth", str(_snapshot["breadth"])),
    ("Micro Pulse", str(_snapshot["micro_pulse"])),
    ("Rotation", str(_snapshot["pressure"])),
])
section_line("Risk Buckets", "gleichgewichtete Assetgruppen · Ergebnisansicht")
_buckets = _snapshot["buckets"].copy()
if _buckets.empty:
    st.info("Noch keine ausreichenden COT-Daten für die Risk-Buckets.")
else:
    _display = _buckets[["bucket", "macro", "micro", "commercial_flow", "coverage", "members"]].rename(columns={
        "bucket": "Bucket", "macro": "Makro", "micro": "Mikro", "commercial_flow": "Commercial Flow", "coverage": "Verfügbar", "members": "Märkte"
    })
    st.dataframe(_display, use_container_width=True, hide_index=True)

if _snapshot["pressure"] == "TRANSITION PRESSURE":
    st.warning("Das strukturelle Regime steht unter erhöhtem Gegenwind: Commercial Flow und Micro Pulse drehen gegen das Makro.")
elif _snapshot["pressure"] == "ROTATION WARNING":
    st.warning("Commercial Flow zeigt eine mögliche Rotation gegen das bestehende Makro-Regime.")
elif _snapshot["pressure"] == "STABLE":
    st.success("Commercial Flow unterstützt aktuell das bestehende Makro-Regime.")
else:
    st.info("Der Cross-Asset-Kontext ist aktuell gemischt.")
st.caption("Trader sehen hier bewusst nur Regime und Bucket-Ergebnis. Die exakte interne Zuordnung und Schwellenlogik wird nicht offengelegt.")
