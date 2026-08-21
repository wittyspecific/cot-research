from __future__ import annotations
# V3.22.6.1 · SEASONALITY EDGE LAB UI HOTFIX

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.cftc_reports import (
    DATASETS,
    load_report_history,
    load_report_universe,
    primary_report_for_asset_class,
    resolve_report_market,
)
from src.markets import CLASSIC_MARKETS
from src.prices import load_prices
from src.report_analysis import enrich_report_positioning
from src.seasonality_edge_research import (
    current_phase_day,
    nearest_turn_context,
    offset_forward_surface,
    phase_shift_consensus,
    phase_shift_match,
    positioning_flow_context,
    seasonal_dynamics,
    seasonal_template,
    seasonal_turns,
    stability_table,
    transition_hypothesis,
)
from src.style import (
    apply_style,
    context_strip,
    definition,
    metric_card,
    page_header,
    plotly_config,
    section_line,
)


apply_style()

ASSET_CLASS_DE = {
    "Currencies": "Währungen",
    "Cryptocurrencies": "Kryptowährungen",
    "Forest Products": "Forstprodukte",
    "Rates": "US-Zinsen",
    "Volatility": "Volatilität",
    "Energy": "Energie",
    "Metals": "Metalle",
    "Grains": "Getreide",
    "Livestock": "Vieh",
    "Soft Commodities": "Softs",
    "Indices": "Aktienindizes",
}


def _pct(value, digits=1):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    if not np.isfinite(value):
        return "—"
    return f"{value:+.{digits}%}"


def _num(value, digits=2):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    if not np.isfinite(value):
        return "—"
    return f"{value:+.{digits}f}"


def _pp(value, digits=1):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "—"
    if not np.isfinite(value):
        return "—"
    return f"{value:+.{digits}f} Pp."


page_header(
    "Research · Seasonality",
    "Seasonality Edge Lab",
    "Saisonale Wendefenster, Phasenverschiebung und COT-Flow als überprüfbare Research-Hypothesen.",
    "V3.22.6 · SEASONALITY EDGE LAB",
)

st.caption(
    "Research-Seite, kein Entry-Signal und kein neuer Ranking-Score. "
    "Die produktive Watchlist-/COT-/Seasonality-Logik bleibt unverändert."
)

_context = st.session_state.pop("_market_context_handoff", None)
_selected = st.session_state.get("selected_market")

if _context:
    st.session_state["season_edge_asset_class"] = _context["asset_class"]
    st.session_state["season_edge_market"] = _context["market_name"]
elif _selected and "season_edge_asset_class" not in st.session_state:
    st.session_state["season_edge_asset_class"] = _selected["asset_class"]
    st.session_state["season_edge_market"] = _selected["market_name"]

# V3.22.6.1 · PAGE-LOCAL CONTROLS + AUTO PRICE TICKER
st.markdown("### Research-Konfiguration")

with st.container(border=True):
    c_asset, c_market = st.columns(2, gap="small")

    with c_asset:
        asset_class = st.selectbox(
            "Assetklasse",
            list(CLASSIC_MARKETS.keys()),
            format_func=lambda x: ASSET_CLASS_DE.get(x, x),
            key="season_edge_asset_class",
        )

    markets = CLASSIC_MARKETS[asset_class]
    names = [m["name"] for m in markets]

    if st.session_state.get("season_edge_market") not in names:
        st.session_state["season_edge_market"] = names[0]

    with c_market:
        market_name = st.selectbox(
            "Markt",
            names,
            key="season_edge_market",
        )

    market = next(m for m in markets if m["name"] == market_name)

    st.session_state["selected_market"] = {
        "asset_class": asset_class,
        "market_name": market_name,
    }

    # Canonical market mapping determines the price proxy automatically.
    price_ticker = market["ticker"]

    c_hist, c_horizon = st.columns(2, gap="small")

    with c_hist:
        history_years = st.selectbox(
            "Primäres Historienfenster",
            [10, 15, 20, 30],
            index=2,
            format_func=lambda x: f"{x} Jahre",
            help=(
                "20 Jahre bleiben der Default. Die Robustheitssektion prüft "
                "zusätzlich mehrere Fenster getrennt."
            ),
        )

    with c_horizon:
        horizon = st.selectbox(
            "Turn-Window Forward-Horizont",
            [5, 10, 20, 40, 60],
            index=3,
            format_func=lambda x: f"{x} Handelstage",
        )

    st.caption(
        f"Preis-Proxy automatisch erkannt: **{price_ticker}** · "
        "Keine Optimierung eines Gesamtscores; Fenster und Horizonte "
        "werden separat sichtbar gehalten."
    )

price_start = pd.Timestamp.today().normalize() - pd.DateOffset(years=35)
prices = load_prices(price_ticker, start=price_start)

if prices.empty:
    st.error(
        "Keine Preisreihe verfügbar. Yahoo-Ticker bzw. Datenverbindung prüfen."
    )
    st.stop()

template = seasonal_template(
    prices,
    years=int(history_years),
)
phase_day = current_phase_day(prices)
turn = nearest_turn_context(template, phase_day)
dynamics = seasonal_dynamics(template, phase_day)
matches = phase_shift_match(
    prices,
    years=int(history_years),
)
consensus = phase_shift_consensus(matches)

# COT context is intentionally report-specific and isolated from production.
positioning = {"available": False}
cot_error = None
report_type = None

try:
    report_type = primary_report_for_asset_class(asset_class)
    universe = load_report_universe(report_type)
    resolved = resolve_report_market(market, universe)
    if resolved:
        raw = load_report_history(
            report_type,
            resolved["cftc_contract_market_code"],
        )
        if raw is not None and not raw.empty:
            enriched = enrich_report_positioning(
                raw,
                report_type=report_type,
                index_weeks=26,
                validation_weeks=156,
            )
            positioning = positioning_flow_context(
                enriched,
                report_type,
            )
except Exception as exc:
    cot_error = f"{type(exc).__name__}: {exc}"

hypothesis = transition_hypothesis(
    turn,
    dynamics,
    positioning,
)

context_strip(
    [
        ("Markt", market_name),
        ("Preis-Proxy", price_ticker),
        ("Historie", f"{history_years} abgeschlossene Jahre"),
        (
            "Letzter Preis",
            (
                str(pd.Timestamp(prices.index.max()).date())
                if not prices.empty
                else "—"
            ),
        ),
    ]
)

section_line(
    "1 · Current Seasonal State",
    "Phase → Turn Window → Dynamics → Phase Shift",
)

a, b, c, d, e = st.columns(5)

with a:
    metric_card(
        "SAISON-PHASE",
        f"Tag {phase_day}" if phase_day is not None else "—",
        "normalisierte 252-Handelstage-Phase",
    )

with b:
    turn_type = str(turn.get("turn_type", "N/V"))
    metric_card(
        "NÄCHSTER TURN",
        turn_type,
        str(turn.get("window_state", "N/V")),
    )

with c:
    distance = turn.get("distance_days")
    distance_text = "—"
    if distance is not None:
        distance_text = (
            "HEUTE"
            if int(distance) == 0
            else f"{int(distance):+d}T"
        )
    metric_card(
        "TURN DISTANCE",
        distance_text,
        "negativ = Turn bereits passiert",
    )

with d:
    metric_card(
        "10T SAISON-SLOPE",
        _num(dynamics.get("slope_10d"), 3),
        str(dynamics.get("direction", "N/V")),
    )

with e:
    shift = consensus.get("consensus_shift_days")
    metric_card(
        "PHASE SHIFT",
        "—" if shift is None else f"{int(shift):+d}T",
        (
            f"{consensus.get('agreement')} · "
            f"{consensus.get('usable_windows', 0)} Fenster"
        ),
    )

definition(
    "Ein saisonales Top oder Bottom wird nicht als exakter Handelstag behandelt. "
    "Gesucht wird ein Wendefenster. Ein belastbarer Effekt sollte kleine "
    "Verschiebungen des Einstiegs überstehen."
)

if not template.empty:
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=template["phase_day"],
            y=template["q75_pct"],
            mode="lines",
            name="75%-Quantil",
            line=dict(width=0),
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=template["phase_day"],
            y=template["q25_pct"],
            mode="lines",
            name="25–75% Band",
            fill="tonexty",
            line=dict(width=0),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=template["phase_day"],
            y=template["median_pct"],
            mode="lines",
            name=f"Median · {history_years}J",
        )
    )

    if phase_day is not None:
        fig.add_vline(
            x=int(phase_day),
            line_dash="dash",
            annotation_text="aktuelle Phase",
        )

    turns = seasonal_turns(template)
    if not turns.empty:
        tops = turns[turns["turn_type"].eq("TOP")]
        bottoms = turns[turns["turn_type"].eq("BOTTOM")]

        if not tops.empty:
            fig.add_trace(
                go.Scatter(
                    x=tops["phase_day"],
                    y=tops["seasonal_level_pct"],
                    mode="markers",
                    name="Seasonal Tops",
                )
            )

        if not bottoms.empty:
            fig.add_trace(
                go.Scatter(
                    x=bottoms["phase_day"],
                    y=bottoms["seasonal_level_pct"],
                    mode="markers",
                    name="Seasonal Bottoms",
                )
            )

    fig.update_layout(
        height=430,
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis_title="Normalisierter Handelstag im Jahr",
        yaxis_title="Kumulativer saisonaler Log-Return (%)",
        legend=dict(orientation="h"),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config=plotly_config(),
    )

st.caption(
    "Die zentrale Kurve ist der Median abgeschlossener Jahre. Das 25–75%-Band "
    "zeigt, ob die scheinbare Saisonstruktur zwischen den Jahren stark streut."
)

section_line(
    "2 · Turn Window Surface",
    "Ist die Wirkung robust um den Wendepunkt oder nur ein einzelner Kalendertag?",
)

surface = offset_forward_surface(
    prices,
    years=int(history_years),
)

if surface.empty:
    st.info("Keine ausreichende Historie für die Turn-Window-Auswertung.")
else:
    selected = surface[
        surface["horizon_days"].eq(int(horizon))
    ].copy()

    s1, s2 = st.columns([0.58, 0.42])

    with s1:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=selected["offset_days"],
                y=selected["median_edge"],
                mode="lines+markers",
                name="Median Edge vs. Markt-Basisphase",
            )
        )
        fig.add_hline(y=0, line_dash="dot")
        fig.add_vline(x=0, line_dash="dash")
        fig.update_layout(
            height=360,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_title="Entry-Offset zur aktuellen Saisonphase (Handelstage)",
            yaxis_title="Median-Return minus Markt-Basismedian",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            config=plotly_config(),
        )

    with s2:
        show = selected[
            [
                "offset_days",
                "sample_size",
                "positive_rate",
                "base_positive_rate",
                "hit_rate_edge_pp",
                "median_return",
                "median_edge",
            ]
        ].rename(
            columns={
                "offset_days": "Offset",
                "sample_size": "N",
                "positive_rate": "Positiv",
                "base_positive_rate": "Basis",
                "hit_rate_edge_pp": "Δ Trefferquote",
                "median_return": "Median",
                "median_edge": "Median Edge",
            }
        )

        st.dataframe(
            show.style.format(
                {
                    "Positiv": "{:.0%}",
                    "Basis": "{:.0%}",
                    "Δ Trefferquote": "{:+.1f} Pp.",
                    "Median": "{:+.2%}",
                    "Median Edge": "{:+.2%}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

st.caption(
    "Edge-förmig wäre hier keine einzelne starke Offset-Zelle, sondern ein "
    "zusammenhängendes Fenster mit ähnlicher Richtung und ähnlichem Effekt."
)

section_line(
    "3 · Phase Shift",
    "Läuft der aktuelle Markt seinem typischen Jahresrhythmus voraus oder hinterher?",
)

if matches.empty:
    st.info("Noch keine belastbare Phasenverschiebung berechenbar.")
else:
    phase_display = matches.rename(
        columns={
            "lookback_days": "Lookback",
            "phase_shift_days": "Beste Verschiebung",
            "correlation": "Korrelation",
            "shape_rmse": "Shape RMSE",
        }
    )
    st.dataframe(
        phase_display.style.format(
            {
                "Korrelation": "{:+.3f}",
                "Shape RMSE": "{:.3f}",
            },
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Nur Fenster mit Korrelation ≥ 0,30 fließen in den angezeigten "
        "Konsens ein. Ein positiver Shift bedeutet: der aktuelle Verlauf "
        "ähnelt einer späteren saisonalen Phase."
    )

section_line(
    "4 · Multi-Window Robustness",
    "10J / 15J / 20J / 30J getrennt statt ein einziges optimiertes Fenster",
)

stability = stability_table(prices)

if stability.empty:
    st.info("Keine ausreichenden Daten für die Robustheitsmatrix.")
else:
    table = stability[
        [
            "history_years",
            "horizon_days",
            "sample_size",
            "direction",
            "positive_rate",
            "base_positive_rate",
            "hit_rate_edge_pp",
            "median_return",
            "median_edge",
        ]
    ].rename(
        columns={
            "history_years": "Historie",
            "horizon_days": "Forward",
            "sample_size": "N",
            "direction": "Richtung",
            "positive_rate": "Positiv",
            "base_positive_rate": "Basis",
            "hit_rate_edge_pp": "Δ Trefferquote",
            "median_return": "Median",
            "median_edge": "Median Edge",
        }
    )

    st.dataframe(
        table.style.format(
            {
                "Historie": "{:.0f}J",
                "Forward": "{:.0f}T",
                "Positiv": "{:.0%}",
                "Basis": "{:.0%}",
                "Δ Trefferquote": "{:+.1f} Pp.",
                "Median": "{:+.2%}",
                "Median Edge": "{:+.2%}",
            },
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )

st.caption(
    "Die Historienfenster sind verschachtelt und daher nicht unabhängig. "
    "Gesucht wird Stabilität der Richtung, nicht eine künstliche Anzahl "
    "statistisch unabhängiger Bestätigungen."
)

section_line(
    "5 · COT × Seasonal Turn",
    "aktiver Positionsaufbau vs. bloße Positionsauflösung",
)

if cot_error:
    st.warning(f"COT-Kontext konnte nicht geladen werden: {cot_error}")

if not positioning.get("available"):
    st.info("Für diesen Markt ist aktuell kein ausreichender COT-Flow-Kontext verfügbar.")
else:
    p1, p2, p3, p4 = st.columns(4)

    with p1:
        metric_card(
            "PRIMÄRGRUPPE",
            positioning.get("primary_label", "—"),
            (
                DATASETS.get(report_type, {}).get("label", "Report")
                if report_type
                else "Report"
            ),
        )

    with p2:
        metric_card(
            "NET/OI %ILE",
            _num(positioning.get("net_oi_percentile"), 1),
            "156W Kontext",
        )

    with p3:
        metric_card(
            "NET/OI Δ4W",
            _pct(positioning.get("net_oi_delta_4w"), 2),
            "Positionsgröße relativ zum OI",
        )

    with p4:
        metric_card(
            "RESEARCH HYPOTHESE",
            hypothesis.get("label", "—"),
            hypothesis.get("detail", "—"),
        )

    flow_rows = []
    for weeks in (1, 2, 4):
        flow_rows.append(
            {
                "Fenster": f"{weeks}W",
                "Net Δ": positioning.get(f"net_delta_{weeks}w"),
                "Net/OI Δ": positioning.get(f"net_oi_delta_{weeks}w"),
                "Long Δ": positioning.get(f"long_delta_{weeks}w"),
                "Short Δ": positioning.get(f"short_delta_{weeks}w"),
            }
        )

    flow = pd.DataFrame(flow_rows)
    st.dataframe(
        flow.style.format(
            {
                "Net Δ": "{:+,.0f}",
                "Net/OI Δ": "{:+.3%}",
                "Long Δ": "{:+,.0f}",
                "Short Δ": "{:+,.0f}",
            },
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )

    if not positioning.get("directional_interpretation"):
        st.caption(
            "TFF Dealer/Intermediary wird bewusst nicht automatisch als "
            "physischer Hedger interpretiert. Deshalb bleibt die Anzeige "
            "bei Finanzfutures zunächst Kontext statt directional Signal."
        )
    else:
        st.caption(
            "Bei Producer/Merchant wird unterschieden: Nettoverbesserung durch "
            "aktiven Long-Aufbau ist eine andere Hypothese als dieselbe "
            "Nettoverbesserung durch Short-Abbau."
        )

with st.expander(
    "Methodik · Was wäre echte Edge und was noch nicht?",
    expanded=False,
):
    st.markdown(
        """
        **Als interessanter Research-Kandidat gilt:**

        - ein saisonaler Turn, der als breites Fenster und nicht als einzelner Tag erscheint;
        - eine ähnliche Richtung über mehrere Historienfenster;
        - ein positiver/negativer Effekt relativ zur marktinternen Basisphase;
        - eine nachvollziehbare Phasenverschiebung über mehrere Lookbacks;
        - bei Rohstoffen ein COT-Flow, dessen aktive Long-/Short-Komponente zur
          Turn-Hypothese passt.

        **Noch nicht bewiesen ist damit:**

        - echte Out-of-Sample-Edge;
        - Unabhängigkeit der Historienfenster;
        - Stabilität über verschiedene Marktregime;
        - Nutzbarkeit nach Transaktionskosten oder als Entry-Trigger.

        Der nächste methodische Schritt wäre ein eingefrorener Walk-Forward-Test,
        in dem Turn-Definition, Offset-Fenster und COT-Flow-Klassifikation nur
        mit zu diesem Zeitpunkt verfügbaren Daten berechnet werden.
        """
    )
