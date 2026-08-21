from __future__ import annotations
# V3.19.4 · YIELD SPREADS MOVED TO ADVANCED
# Legacy location label only: Research · Rates
# V3.16.3 · OFFICIAL 2Y ADAPTERS COMPLETE
# V3.16.1 · HISTORICALLY NORMALIZED 2Y YIELD SPREADS
# V3.16.2 · REPAIRED OFFICIAL 2Y DATA ADAPTERS

import pandas as pd
import streamlit as st

from src.style import apply_style, context_strip, page_header, section_line
from src.yield_spreads import (
    DEFAULT_PAIRS,
    data_age_days,
    fetch_yield_universe,
    freshness_status,
    pair_table,
)

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
    "Advanced · Rates",
    "Yield Spreads",
    "Relative 2Y-Zinsdifferenzen als fundamentaler FX-Kontext.",
    "V3.16.4 · RBA 403 TRANSPORT FIX",
)

st.caption(
    "Fundamental-/Confluence-Layer. 5D / 20D / 60D Spread-Moves werden gegen "
    "ihre eigene historische Verteilung normalisiert. 20D = Swing-Hauptsicht, "
    "60D = Rates-Regime, 5D = frisches Repricing. Noch kein harter Trade-Filter."
)


@st.cache_data(ttl=3600, show_spinner=False)
def _load_yields():
    return fetch_yield_universe()


with st.spinner("Offizielle 2Y-Renditedaten werden geladen …"):
    universe = _load_yields()

currency_rows = []
for currency in ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "MXN"):
    result = universe[currency]
    latest = (
        float(result.series.iloc[-1])
        if result.series is not None and not result.series.empty
        else None
    )
    currency_rows.append(
        {
            "Währung": currency,
            "2Y Yield %": latest,
            "Stand": (
                result.as_of.strftime("%Y-%m-%d")
                if result.as_of is not None
                else "—"
            ),
            "Freshness": freshness_status(result),
            "Alter Tage": data_age_days(result),
            "Quelle": result.source,
            "Status": result.status,
            "Hinweis": result.note,
        }
    )

currency_frame = pd.DataFrame(currency_rows)

fresh_count = int(currency_frame["Freshness"].eq("FRESH").sum())
usable_count = int(currency_frame["2Y Yield %"].notna().sum())
stale_count = int(currency_frame["Freshness"].eq("STALE").sum())

context_strip(
    [
        ("Währungen", str(len(currency_frame))),
        ("2Y verfügbar", f"{usable_count}/{len(currency_frame)}"),
        ("Fresh", str(fresh_count)),
        ("Stale", str(stale_count)),
    ]
)

st.caption(
    "V3.16.2 Adapter-Schutz: strukturierte Official-Source-Parser + "
    "Plausibilitätsprüfung für Datum und Yield. Fehlerhafte Feeds werden "
    "als ERROR/N/V gezeigt und nicht in Spreads eingerechnet."
)

st.caption(
    "V3.16.3: CAD nutzt den offiziellen Bank-of-Canada V39051-Lookup; "
    "AUD liest RBA F2 robust über FCMYGBAG2D; NZD nutzt den offiziellen "
    "RBNZ-B2-Daily-Close-Download mit kompatiblen Request-Headern."
)

st.caption(
    "V3.16.4: AUD bleibt die offizielle RBA-F2-Serie FCMYGBAG2D. "
    "Bei RBA HTTP 403 wird lediglich der Transport auf browser-kompatibles "
    "libcurl umgestellt; Datenquelle und Serie ändern sich nicht."
)

section_line(
    "Rates Universe",
    "offizielle Quellen · keine veralteten Werte werden als live erzwungen",
)

display_currency = currency_frame.copy()
display_currency["2Y Yield %"] = display_currency["2Y Yield %"].map(
    lambda x: "—" if pd.isna(x) else f"{x:.3f}%"
)
display_currency["Alter Tage"] = display_currency["Alter Tage"].map(
    lambda x: "—" if pd.isna(x) else int(x)
)

st.dataframe(
    display_currency[
        [
            "Währung",
            "2Y Yield %",
            "Stand",
            "Freshness",
            "Quelle",
            "Status",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

with st.expander("Datenquellen / Hinweise", expanded=False):
    st.dataframe(
        display_currency[
            [
                "Währung",
                "Quelle",
                "Stand",
                "Alter Tage",
                "Freshness",
                "Hinweis",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

section_line(
    "FX Yield Spreads",
    "historisch normalisiert · 5 Jahre Referenz, mindestens 252 frühere Beobachtungen",
)

view = st.radio(
    "Ansicht",
    options=["Alle", "USD Majors", "JPY Crosses", "Crosses"],
    horizontal=True,
    label_visibility="collapsed",
)

pairs = list(DEFAULT_PAIRS)
if view == "USD Majors":
    pairs = [
        "EURUSD",
        "GBPUSD",
        "AUDUSD",
        "NZDUSD",
        "USDJPY",
        "USDCHF",
        "USDCAD",
        "USDMXN",
    ]
elif view == "JPY Crosses":
    pairs = [
        "USDJPY",
        "EURJPY",
        "GBPJPY",
        "AUDJPY",
        "CADJPY",
        "NZDJPY",
    ]
elif view == "Crosses":
    pairs = [
        pair
        for pair in DEFAULT_PAIRS
        if "USD" not in pair
    ]

spreads = pair_table(universe, pairs=pairs)

if spreads.empty:
    st.info("Keine Yield-Spread-Daten verfügbar.")
else:
    table = spreads.copy()
    table = table.rename(
        columns={
            "pair": "Paar",
            "spread_bp": "2Y Spread bp",
            "delta_5d_bp": "Δ 5D bp",
            "percentile_5d": "5D Pctl",
            "strength_5d": "5D Stärke",
            "delta_20d_bp": "Δ 20D bp",
            "percentile_20d": "20D Pctl",
            "strength_20d": "20D Stärke",
            "delta_60d_bp": "Δ 60D bp",
            "percentile_60d": "60D Pctl",
            "strength_60d": "60D Stärke",
            "direction_20d": "20D Rates Bias",
            "rates_consistency": "Rates Alignment",
            "normalization_obs_20d": "Hist. Obs.",
            "as_of": "Stand",
        }
    )

    for column in ("2Y Spread bp", "Δ 5D bp", "Δ 20D bp", "Δ 60D bp"):
        if column in table.columns:
            table[column] = table[column].map(
                lambda x: "—" if pd.isna(x) else f"{x:+.1f}"
            )

    for column in ("5D Pctl", "20D Pctl", "60D Pctl"):
        if column in table.columns:
            table[column] = table[column].map(
                lambda x: "—" if pd.isna(x) else f"{x:.0f}%"
            )

    table["Stand"] = table["Stand"].map(
        lambda x: "—"
        if pd.isna(x)
        else pd.Timestamp(x).strftime("%Y-%m-%d")
    )

    primary_columns = [
        "Paar",
        "2Y Spread bp",
        "Δ 20D bp",
        "20D Pctl",
        "20D Stärke",
        "20D Rates Bias",
        "Δ 60D bp",
        "60D Pctl",
        "60D Stärke",
        "Rates Alignment",
        "Stand",
    ]
    primary_columns = [c for c in primary_columns if c in table.columns]

    st.dataframe(
        table[primary_columns],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("5D Repricing + Normalisierungsdetails", expanded=False):
        detail_columns = [
            "Paar",
            "Δ 5D bp",
            "5D Pctl",
            "5D Stärke",
            "Δ 20D bp",
            "20D Pctl",
            "20D Stärke",
            "Δ 60D bp",
            "60D Pctl",
            "60D Stärke",
            "Hist. Obs.",
            "Stand",
        ]
        detail_columns = [c for c in detail_columns if c in table.columns]
        st.dataframe(
            table[detail_columns],
            use_container_width=True,
            hide_index=True,
        )

st.caption(
    "Pctl misst die historische Ungewöhnlichkeit des Betrags der jeweiligen "
    "Spread-Bewegung. 90% bedeutet: Der aktuelle Move ist stärker als ungefähr "
    "90% der vergleichbaren Moves im Referenzfenster. Die Richtung kommt separat "
    "vom Vorzeichen des Spread-Moves."
)

section_line(
    "Interpretation",
    "Magnitude und Richtung werden bewusst getrennt",
)

st.markdown(
    """
**Horizonte**
- `5D` = frisches Rates-Repricing / Frühindikator
- `20D` = **Hauptsicht für Swing Trading**
- `60D` = übergeordnetes Rates-Regime

**Historische Stärke**
- `< 60%` → `NORMAL`
- `60–<75%` → `MILD`
- `75–<90%` → `STRONG`
- `≥ 90%` → `EXTREME`

Beispiel: `EURUSD · Δ20D +28 bp · 86% · STRONG · EUR +` bedeutet:
Der EUR−USD-Spread hat sich über 20 Beobachtungen um 28 bp zugunsten EUR bewegt,
und dieser Betrag ist größer als ungefähr 86% der vergleichbaren historischen
20D-Moves.

Die Normalisierung nutzt standardmäßig die **letzten fünf Kalenderjahre** der
gemeinsam verfügbaren 2Y-Spread-Historie. Der aktuelle Move wird nicht in seine
eigene Referenzverteilung aufgenommen. Wenn weniger als 252 frühere Beobachtungen
vorliegen, bleibt das Perzentil `N/V`.

Der absolute 2Y-Spread bleibt Carry-/Level-Kontext. Für die Richtungsanalyse ist
die Veränderung des Spreads wichtiger.
"""
)

section_line(
    "Methodik",
    "kein Composite Score · keine fixe bp-Schwelle für alle Währungen",
)

st.markdown(
    """
Die Stärke wird **für jedes FX-Paar und jeden Horizont separat** berechnet.
Dadurch wird nicht unterstellt, dass beispielsweise `+25 bp` bei EURUSD und
AUDJPY dieselbe Bedeutung haben.

`Rates Alignment` fasst nur zusammen, ob 5D/20D/60D in dieselbe relative
Währungsrichtung zeigen. Es verändert keine Trade-Entscheidung.

`CHF` und `MXN` bleiben weiterhin `N/V`, solange kein ausreichend stabiler
offizieller 2Y-Adapter aktiv ist.
"""
)
