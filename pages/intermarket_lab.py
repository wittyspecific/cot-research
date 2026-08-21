from __future__ import annotations

import pandas as pd
import streamlit as st

from src.intermarket import (
    INTERMARKET_RELATIONSHIPS,
    evaluate_relationships,
    relationship_matrix,
)
from src.style import apply_style, context_strip, page_header, section_line
from src.watchlist import scan_classic_markets

# V3.20.0 · ADVANCED DIRECT ACCESS GUARD
_v3200_trader = dict(st.session_state.get("auth_trader") or {})
if (
    not _v3200_trader
    or str(_v3200_trader.get("role", "TRADER")).upper() != "ADMIN"
):
    st.error("Kein Zugriff auf den Advanced-Bereich.")
    st.stop()



apply_style()

# V3.19.5 · INTERMARKET LAB


def _category_label(value: str) -> str:
    return {
        "CURRENCY_COMMODITY": "FX ↔ Commodity",
        "MACRO_COMMODITY": "USD ↔ Commodity",
        "COMMODITY_COMMODITY": "Commodity ↔ Commodity",
        "COMMODITY_RATES": "Commodity ↔ Rates",
        "RISK_SENTIMENT": "Risk ↔ Volatility",
    }.get(str(value), str(value))


page_header(
    "Advanced · Intermarket Lab",
    "Intermarket Lab",
    "Beziehungen, Gewichtungen und Datenqualität hinter der sichtbaren Intermarket-Analyse.",
    "V3.19.5 · INTERMARKET LAB",
)

st.caption(
    "Admin-/Research-Ebene. Hier liegt bewusst der Analyseweg hinter der Trader-Ansicht: "
    "kuratierte Beziehungen, Polarität, qualitative Gewichtung, Regimeabhängigkeit, "
    "Rationale und Datenqualität. Diese Seite verändert keine Trading-Entscheidung."
)

with st.spinner("Intermarket Research-Daten werden geladen …"):
    scan = scan_classic_markets()

all_markets = scan.get("all_markets", pd.DataFrame())
if isinstance(all_markets, list):
    all_markets = pd.DataFrame(all_markets)
if all_markets is None:
    all_markets = pd.DataFrame()

results = evaluate_relationships(all_markets)

available_count = (
    int(results["available"].fillna(False).sum())
    if not results.empty and "available" in results.columns
    else 0
)
regime_count = sum(
    1
    for item in INTERMARKET_RELATIONSHIPS
    if bool(item.regime_dependent)
)
errors = scan.get("errors")
error_count = (
    int(len(errors))
    if isinstance(errors, pd.DataFrame)
    else 0
)

context_strip(
    [
        ("Beziehungen", str(len(INTERMARKET_RELATIONSHIPS))),
        ("Daten verfügbar", f"{available_count}/{len(INTERMARKET_RELATIONSHIPS)}"),
        ("Regimeabhängig", str(regime_count)),
        ("Datenprobleme", str(error_count)),
    ]
)

section_line(
    "Beziehungsmatrix",
    "kuratierte COT↔COT-Beziehungen · Research-Definition",
)

matrix = relationship_matrix().copy()
matrix["Bereich"] = matrix["category"].map(_category_label)
matrix["Regimeabhängig"] = matrix["regime_dependent"].map(
    lambda value: "Ja" if bool(value) else "Nein"
)
matrix = matrix.rename(
    columns={
        "currency_symbol": "Markt A",
        "reference_market": "Markt B",
        "relationship": "Beziehung",
        "weight": "Gewicht",
        "rationale": "Warum",
    }
)

st.dataframe(
    matrix[
        [
            "Bereich",
            "Markt A",
            "Markt B",
            "Beziehung",
            "Gewicht",
            "Regimeabhängig",
            "Warum",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "POSITIV: gleiche COT-Richtung = SUPPORT. "
    "NEGATIV: entgegengesetzte COT-Richtung = SUPPORT. "
    "Ein neutraler COT-Zustand bleibt NEUTRAL. "
    "REGIME kennzeichnet bewusst weniger stabile Beziehungen."
)

section_line(
    "Aktuelle Rohbewertung",
    "vollständiger Research-Output vor der reduzierten Trader-Darstellung",
)

if results.empty:
    st.info("Aktuell keine Intermarket-Auswertung verfügbar.")
else:
    research_columns = [
        column
        for column in (
            "currency_symbol",
            "reference_market",
            "category",
            "relationship",
            "weight",
            "regime_dependent",
            "currency_macro_label",
            "reference_macro_label",
            "macro_alignment",
            "currency_micro_label",
            "reference_micro_label",
            "micro_alignment",
            "overall",
            "available",
            "error",
        )
        if column in results.columns
    ]

    raw = results[research_columns].copy().rename(
        columns={
            "currency_symbol": "Markt A",
            "reference_market": "Markt B",
            "category": "Kategorie",
            "relationship": "Beziehung",
            "weight": "Gewicht",
            "regime_dependent": "Regimeabhängig",
            "currency_macro_label": "Makro A",
            "reference_macro_label": "Makro B",
            "macro_alignment": "Makro Ergebnis",
            "currency_micro_label": "Mikro A",
            "reference_micro_label": "Mikro B",
            "micro_alignment": "Mikro Ergebnis",
            "overall": "Gesamt",
            "available": "Verfügbar",
            "error": "Fehler",
        }
    )

    st.dataframe(
        raw,
        use_container_width=True,
        hide_index=True,
    )

section_line(
    "Datenqualität",
    "technische Probleme bleiben ausschließlich im Admin-Lab sichtbar",
)

if isinstance(errors, pd.DataFrame) and not errors.empty:
    st.dataframe(
        errors,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.success("Keine Datenprobleme im aktuellen Scan.")

with st.expander("Methodik · Beziehungsauswertung", expanded=False):
    st.markdown(
        """
- Die Beziehungen sind **kuratierte fundamentale COT↔COT-Beziehungen**, kein all-vs-all Korrelationsscan.
- **POSITIV** bedeutet: gleiche COT-Richtung unterstützt die Beziehung.
- **NEGATIV** bedeutet: entgegengesetzte COT-Richtung unterstützt die Beziehung.
- Makro **156W** und Mikro **26W** werden getrennt bewertet.
- `SUPPORT`, `CONFLICT`, `MIXED` und `NEUTRAL` sind Confluence-Zustände.
- Qualitative Gewichte und `REGIME` sind Research-Kontext und kein Trading-Score.
- Die Trader-Seite zeigt bewusst nur die resultierende Analyse, nicht diese Herleitung.
        """.strip()
    )

st.caption(
    "Intermarket bleibt ein Research-/Confluence-Layer und verändert weder "
    "Watchlist-Signal, Entry, Risiko, Journal noch Execution."
)
