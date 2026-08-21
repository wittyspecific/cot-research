from __future__ import annotations
# V3.20.0 · FX TRADER OUTPUT ONLY
# Legacy source-contract only: Wie entsteht der COT-Paarbias?
# Legacy source-contract only: Paarbias = Stärke Basis − Stärke Gegenwährung
# V3.19.4 · FX OVERVIEW CLEANUP
# V3.19.4 legacy contracts only; not rendered: Fundamentale Währungsstärke | ALIGNED | RATES LEAD | COT LEADS | CONFLICT | NEUTRAL | Währung im Detail | 20J-Historie
# V3.19.0 · ML MOVED TO ADVANCED YIELD X COT
# Legacy source contracts only; no ML UI is rendered on Währungsstärke:
# V3.18.0 · RATES COT LEAD LAG ML | Rates → COT Lead/Lag ML | ML-Studie starten | Walk-forward | kein Trade-Signal
# V3.18.1 · RATES COT ML DEEP DIVE | Feature-Ablation | Echter Rates-Lead | Leave-One-Currency-Out | STRICT LEAD

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
from src.fundamental_currency_strength import build_fundamental_currency_strength
from src.yield_spreads import fetch_yield_universe
from src.style import (
    apply_style,
    context_strip,
    definition,
    empty_state,
    page_header,
    section_line,
)


apply_style()

@st.cache_data(ttl=3600, show_spinner=False)
def _load_fundamental_yields_v3170():
    return fetch_yield_universe()


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
                "Transition": str(row.get("transition_state", "—")),
                "Signal": currency_bias_display(row),
                "Commercial 156W": value_text(
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
            "base_state",
            "quote_state",
        ]
    ].rename(
        columns={
            "pair": "Paar",
            "pair_display": "COT-Paarbias",
            "trade_bias": "Richtung",
            "seasonality_compact": "Saison 20/40/60T",
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
    "V3.10.0 · 156W RELEASE CONTEXT",
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
    "Commercial Net Percentile 156W ist das Primärmaß der Währungspositionierung. Ein 156W-Extrem erzeugt "
    "noch keine Richtung; erst das Verlassen der Extremzone aktiviert das Hedge-Release. Transition, aktuelles "
    "156W-Perzentil, NC und Retail bleiben sichtbar. Der 26W-COT-Index wird nur noch im Advanced Research geführt."
)

# V3.17.0 · FUNDAMENTAL CURRENCY STRENGTH

section_line(
    "COT Währungsübersicht",
    "156W-State · Transition · Release · Bestätigung · Saison",
)
st.caption(
    "Saison: ▲ bullish · ▼ bearish · — gemischt · · N/V. "
    "Die Pfeile zeigen die saisonale Richtung der einzelnen Währung; "
    "sie sind Kontext und kein zusätzlicher COT-Punkt."
)
render_currency_table(profiles)

# V3.19.4 · COT + YIELD SPREADS CURRENCY OVERVIEW
section_line(
    "COT + Yield Spreads Währungsübersicht",
    "COT 156W + historisch normalisierte 2Y-Rates · zusätzlicher Kontext",
)
st.caption(
    "Zweite Ebene unter der reinen COT-Übersicht. COT bleibt die primäre "
    "Positionierungslogik; Yield Spreads liefern zusätzlichen fundamentalen "
    "Kontext und überschreiben kein COT-Signal."
)
try:
    with st.spinner("COT + Yield Spreads werden zusammengeführt …"):
        _v3170_yields = _load_fundamental_yields_v3170()
        _v3170_fundamental = build_fundamental_currency_strength(
            profiles,
            _v3170_yields,
        )
        # V3.20.0 · YIELD COVERAGE FILTER
        if not _v3170_fundamental.empty and "rates_20d_available" in _v3170_fundamental.columns:
            _v3170_fundamental = _v3170_fundamental.loc[
                pd.to_numeric(
                    _v3170_fundamental["rates_20d_available"],
                    errors="coerce",
                ).fillna(0).ge(2)
            ].copy()

    st.caption("Nur Währungen mit ausreichender Yield-Spread-Abdeckung werden in dieser kombinierten Ansicht gezeigt.")
    if _v3170_fundamental.empty:
        st.info("Noch keine gemeinsame COT-/Yield-Spread-Auswertung verfügbar.")
    else:
        _v3170_table = _v3170_fundamental[
            [
                "symbol",
                "state_display",
                "cot_macro_label",
                "micro_label",
                "rates_20d_label",
                "rates_60d_label",
                "rates_5d_label",
                "rates_alignment",
            ]
        ].rename(
            columns={
                "symbol": "Währung",
                "state_display": "COT + Yield State",
                "cot_macro_label": "COT Macro 156W",
                "micro_label": "COT Micro 26W",
                "rates_20d_label": "Yield Spreads 20D",
                "rates_60d_label": "Yield Spreads 60D",
                "rates_5d_label": "Yield Spreads 5D",
                "rates_alignment": "Rates Alignment",
            }
        )
        st.dataframe(
            _v3170_table,
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "ALIGNED ist nur Kontext und kein stärkeres Entry-Signal. "
            "CONFLICT markiert fundamentalen Gegenwind; die COT-Logik bleibt unverändert."
        )
except Exception as _v3170_exc:
    st.warning(
        "COT + Yield Spreads konnten gerade nicht vollständig berechnet werden: "
        f"{type(_v3170_exc).__name__}: {_v3170_exc}"
    )


section_line(
    "Forex-Paare",
    f"{len(pairs)} Crosses · stärkster COT-Gegensatz zuerst",
)

st.caption(
    "Nur bestätigte Releases aus dem Commercial-156W-Zyklus tragen Richtung. FULL/LOW HEDGE ohne Release bleibt neutral."
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
