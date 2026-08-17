from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.fx_relative import (
    add_20y_multi_pair_seasonality,
    add_currency_20y_multi_seasonality,
    build_all_fx_pairs,
    load_currency_cot_profiles,
)
from src.fx_relative_core import CURRENCY_NAMES_DE, CURRENCY_ORDER
from src.style import (
    apply_style,
    context_strip,
    definition,
    empty_state,
    page_header,
    section_line,
)


apply_style()


def de_date(value):
    if value is None or pd.isna(value):
        return "—"
    return pd.Timestamp(value).strftime("%d.%m.%Y")


def currency_bias_display(row: pd.Series) -> str:
    confirmations = int(row["confirmations"])
    direction = int(row["direction"])
    if confirmations == 0 or direction == 0:
        return "— NEUTRAL"
    return (
        f"▲ BULLISH {confirmations}/4"
        if direction > 0
        else f"▼ BÄRISCH {confirmations}/4"
    )


def value_text(value, ok: bool) -> str:
    if value is None or not np.isfinite(float(value)):
        return "—"
    return f"{'✓' if ok else '–'} {float(value):.1f}"


def render_currency_table(profiles: pd.DataFrame):
    if profiles.empty:
        empty_state(
            "Keine Währungs-COT-Daten verfügbar.",
            "Die Forex-Matrix benötigt aktuelle COT-Daten der Einzelwährungen.",
        )
        return

    rows = []
    for _, row in profiles.iterrows():
        rows.append(
            {
                "Währung": (
                    f"{CURRENCY_NAMES_DE.get(row['symbol'], row['symbol'])} "
                    f"· {row['symbol']}"
                ),
                "State": str(row.get("state_label", "—")),
                "Signal": currency_bias_display(row),
                "COT Index": f"{float(row['commercial_index']):.1f}" if pd.notna(row.get("commercial_index")) else "—",
                "Commercial": value_text(
                    row["commercial_net_percentile"],
                    bool(row["commercial_ok"]),
                ),
                "Non-Commercial": value_text(
                    row["noncommercial_net_percentile"],
                    bool(row["noncommercial_ok"]),
                ),
                "Retail": value_text(
                    row["retail_net_percentile"],
                    bool(row["retail_ok"]),
                ),
                "Saison 20/40/60T": str(
                    row.get("currency_seasonality_compact", "20· · 40· · 60·")
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
        column_config={
            "Saison 20/40/60T": st.column_config.TextColumn(
                "Saison 20/40/60T",
                width="medium",
                help=(
                    "20 abgeschlossene Jahre, gleiche Methodik wie in der Watchlist. "
                    "▲ = saisonal bullish, ▼ = saisonal bearish, — = gemischt, · = N/V. "
                    "Bei bullish COT unterstützt ▲; bei bearish COT unterstützt ▼. "
                    "Die Saison verändert den COT-Score nicht."
                ),
            ),
        },
    )


def render_pairs(df: pd.DataFrame):
    if df.empty:
        empty_state(
            "Keine Forex-Paare in dieser Auswahl.",
            "Passe den Filter an oder prüfe die Datenverfügbarkeit.",
        )
        return

    table = df[
        [
            "pair",
            "pair_display",
            "trade_bias",
            "seasonality_compact",
            "seasonality_detail",
            "base_state",
            "quote_state",
        ]
    ].rename(
        columns={
            "pair": "Paar",
            "pair_display": "COT-Paarbias",
            "trade_bias": "Richtung",
            "seasonality_compact": "Saison 20/40/60T",
            "seasonality_detail": "20J-Historie",
            "base_state": "Basis",
            "quote_state": "Gegenwährung",
        }
    )

    st.dataframe(
        table,
        width="stretch",
        height=760,
        hide_index=True,
        column_config={
            "Paar": st.column_config.TextColumn("Forex-Paar", width="small"),
            "COT-Paarbias": st.column_config.TextColumn(
                "COT-Paarbias",
                width="medium",
            ),
            "Richtung": st.column_config.TextColumn(
                "Long / Short",
                width="small",
            ),
            "Saison 20/40/60T": st.column_config.TextColumn(
                "Saison 20/40/60T",
                width="medium",
                help=(
                    "Historisches Verhalten dieses Paares über die letzten "
                    "20 abgeschlossenen Jahre für die nächsten 20, 40 und 60 Handelstage."
                ),
            ),
            "20J-Historie": st.column_config.TextColumn(
                "20J-Historie",
                width="large",
            ),
            "Basis": st.column_config.TextColumn("Basiswährung", width="medium"),
            "Gegenwährung": st.column_config.TextColumn(
                "Gegenwährung",
                width="medium",
            ),
        },
    )


page_header(
    "Research · Forex",
    "Relative Währungsstärke",
    "Hedge-Release-Signale der Einzelwährungen werden zu Paaren kombiniert.",
    "V3.9.0 · RELEASE-BASED FX",
)

st.caption(
    "Forex-Universum: EUR · GBP · AUD · NZD · USD · CAD · CHF · MXN · JPY. "
    "BRL und ZAR sind auf dieser Seite bewusst ausgeschlossen."
)

st.caption(
    "COT erzeugt den Paarbias. Die Saisonalität prüft separat, wie sich genau "
    "dieses Währungspaar am heutigen Jahreszeitpunkt in den folgenden "
    "20, 40 und 60 Handelstagen über die letzten 20 abgeschlossenen Jahre verhalten hat."
)

with st.spinner("Währungs-COT-Daten werden geladen …"):
    profiles, errors = load_currency_cot_profiles()

with st.spinner("20J / 20-40-60T Währungs-Saisonalität wird berechnet …"):
    profiles = add_currency_20y_multi_seasonality(profiles)

pairs = build_all_fx_pairs(profiles)

with st.spinner("20J / 20-40-60T Forex-Saisonalität wird berechnet …"):
    pairs = add_20y_multi_pair_seasonality(pairs)

latest_report = (
    profiles["report_date"].max()
    if not profiles.empty
    else pd.NaT
)

supported = (
    int(pairs["seasonality_supports"].sum())
    if not pairs.empty
    else 0
)

context_strip(
    [
        ("COT-Report", de_date(latest_report)),
        ("Währungen", f"{len(profiles)}/{len(CURRENCY_ORDER)}"),
        ("Forex-Paare", str(len(pairs))),
        ("20J-Saison unterstützt", str(supported)),
    ]
)

definition(
    "State ≠ Signal: Ein COT-Extrem erzeugt noch keine Währungsrichtung. Erst ein aktives Hedge-Release wird als +/− COT-Stärke gezählt. Commercial-, Non-Commercial- und Retail-Netto können dieses Release bis 4/4 bestätigen. Paarbias = Signalstärke Basis minus Gegenwährung; Saison bleibt separat."
)

section_line(
    "Währungsübersicht",
    "Hedge-State · Release-Signal · Netto-Bestätigung · Saison",
)
st.caption(
    "Saison: ▲ bullish · ▼ bearish · — gemischt · · N/V. "
    "Die Pfeile zeigen die saisonale Richtung der einzelnen Währung; "
    "sie sind Kontext und kein zusätzlicher COT-Punkt."
)
render_currency_table(profiles)

section_line(
    "Forex-Paare",
    f"{len(pairs)} Crosses · stärkster COT-Gegensatz zuerst",
)

st.caption(
    "Nur aktive Releases tragen Richtung. FULL HEDGE ohne Release bleibt neutral und erzeugt keinen Paarbias."
)

only_supported = st.toggle(
    "Nur Paare mit überwiegend/stabil saisonaler Unterstützung anzeigen",
    value=False,
)

shown = pairs.copy()
if only_supported and not shown.empty:
    shown = shown[shown["seasonality_supports"]].reset_index(drop=True)

if shown.empty:
    render_pairs(shown)
else:
    long_count = int((shown["pair_direction"] > 0).sum())
    short_count = int((shown["pair_direction"] < 0).sum())
    neutral_count = int((shown["pair_direction"] == 0).sum())

    tabs = st.tabs(
        [
            f"Alle · {len(shown)}",
            f"Long-Bias · {long_count}",
            f"Short-Bias · {short_count}",
            f"Neutral · {neutral_count}",
        ]
    )

    with tabs[0]:
        render_pairs(shown)
    with tabs[1]:
        render_pairs(
            shown[shown["pair_direction"] > 0].reset_index(drop=True)
        )
    with tabs[2]:
        render_pairs(
            shown[shown["pair_direction"] < 0].reset_index(drop=True)
        )
    with tabs[3]:
        render_pairs(
            shown[shown["pair_direction"] == 0].reset_index(drop=True)
        )


with st.expander("Wie entsteht der COT-Paarbias?", expanded=False):
    st.markdown(
        """
- Bullish 4/4 = `+4`
- Bullish 3/4 = `+3`
- Bullish 2/4 = `+2`
- Bullish 1/4 = `+1`
- Neutral = `0`
- Bearish entsprechend `-1` bis `-4`

Die vier Bedingungen sind:
`Hedge-Release + Commercial-Netto + Non-Commercial-Netto + Retail-Netto`.

Ein COT-Extrem allein bleibt **State / Waiting for Release** und zählt nicht als bullishes oder bärisches Signal.

Bei einem bullishen Reversal-Bias muss das NC-Netto historisch **tief** liegen;
bei einem bearishen Bias historisch **hoch**.

`Paarbias = Stärke Basis − Stärke Gegenwährung`

- Abstand 6–8 → **STARK**
- Abstand 3–5 → **BULLISH / BÄRISCH**
- Abstand 1–2 → **LEICHT**
- Abstand 0 → **NEUTRAL**

Commercials und Legacy Non-Commercials sind teilweise mechanisch gekoppelt.
4/4 bedeutet daher ein sehr geschlossenes **Positionierungsbild**, nicht vier
statistisch unabhängige Signale.
"""
    )

with st.expander("Wie funktioniert die 20J / 20-40-60T-Saisonalität?", expanded=False):
    st.markdown(
        """
Für jedes Paar wird eine historische **Base/Quote-Preisreihe** gebildet.
Am aktuellen Trading-Day des Jahres wird in jedem der letzten
**20 abgeschlossenen Jahre** derselbe Trading-Day als Startpunkt genommen.

Dann werden die Renditen der folgenden **20, 40 und 60 Handelstage** gemessen.

Die Richtung entspricht der bestehenden Seasonality-Methodik des Bots:

- **bullish:** Median > 0 und positive Quote über der marktinternen Basisrate
- **bearish:** Median < 0 und positive Quote unter der marktinternen Basisrate
- sonst **gemischt**

Mindestens 8 historische Jahresbeobachtungen sind erforderlich. In der
Tabelle siehst du zusätzlich `positive Jahre / Stichprobe`, Medianrendite
und Basisrate.

Die Saison verändert den COT-Bias **nicht**:
sie steht nur als `UNTERSTÜTZT`, `GEGENLÄUFIG`, `GEMISCHT` oder `N/V` daneben.
"""
    )

with st.expander("USD und Paarpreise", expanded=False):
    st.caption(
        "Der USD-COT-Bias stammt aus dem U.S. Dollar Index. "
        "Für die Pair-Seasonality werden dagegen Spot-FX-Preisrelationen "
        "verwendet. Crosses werden aus den historischen USD-Werten der beiden "
        "Währungen synthetisiert, was exakt der Base/Quote-Relation entspricht."
    )

if not errors.empty:
    with st.expander(
        f"Datenprobleme · {len(errors)} Währungen",
        expanded=False,
    ):
        st.dataframe(
            errors.rename(
                columns={
                    "symbol": "Symbol",
                    "market_name": "Markt",
                    "error": "Fehler",
                }
            ),
            width="stretch",
            hide_index=True,
        )
