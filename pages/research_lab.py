
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.cftc import load_cftc_universe, load_history, resolve_market
from src.cftc_reports import (
    DATASETS,
    load_report_history,
    load_report_universe,
    primary_report_for_asset_class,
    resolve_report_market,
)
from src.config import (
    INDEX_LOWER,
    INDEX_UPPER,
    NET_VALIDATION_WEEKS,
    NC_DIV_FLOW_WINDOW_W,
    NC_DIV_PATH_WINDOW_W,
    NC_DIV_PRICE_WINDOW_W,
    NC_DIV_STANDARDIZE_HIST_W,
    NC_DIV_USE_OI_NORM,
    NC_DIV_Z_THRESHOLD,
    NC_CONFIRMING_WEEKS,
    NC_DIVERGENCE_WEEKS,
    NC_MIN_ACTIVE_BUILD_SHARE,
    NC_MIN_ACTIVE_LEG_GROSS_PCT,
    NC_MIN_NET_CHANGE_GROSS_PCT,
    NC_MIN_PRICE_MOVE_PCT,
)
from src.markets import CLASSIC_MARKETS
from src.prices import load_prices, price_alignment_audit
from src.report_analysis import REPORT_GROUPS, enrich_report_positioning
from src.analysis import (
    attach_cot_prices,
    enrich_cot,
    historical_nc_divergences_legacy,
)
from src.nc_divergence import (
    build_divergence_history,
    compare_legacy_and_new_events,
    historical_divergence_events,
    redundancy_metrics,
    yearly_signal_counts,
)
from src.research_lab import (
    circular_shift_null_model,
    index_window_comparison,
    release_decay_study,
)
from src.positioning_dynamics_research import (
    build_positioning_episode_dataset,
    compare_flow_measures,
    quantile_effect_study,
    research_question_coverage,
    summarize_window_threshold_grid,
)
from src.style import (
    apply_style,
    context_strip,
    definition,
    page_header,
    section_line,
    metric_card,
    plotly_config,
    tradingview_chart,
    tradingview_plotly_chart,
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

MARKET_NAME_DE = {
    "Euro FX": "Euro",
    "British Pound": "Britisches Pfund",
    "Japanese Yen": "Japanischer Yen",
    "Swiss Franc": "Schweizer Franken",
    "Canadian Dollar": "Kanadischer Dollar",
    "Australian Dollar": "Australischer Dollar",
    "New Zealand Dollar": "Neuseeland-Dollar",
    "Mexican Peso": "Mexikanischer Peso",
    "U.S. Dollar Index": "US-Dollar-Index",
    "Brazilian Real": "Brasilianischer Real",
    "South African Rand": "Südafrikanischer Rand",
    "Bitcoin": "Bitcoin",
    "Ether": "Ethereum / Ether",
    "WTI Crude Oil": "WTI-Rohöl",
    "Brent Crude Oil": "Brent-Rohöl",
    "Natural Gas": "Erdgas",
    "RBOB Gasoline": "RBOB-Benzin",
    "Heating Oil / ULSD": "Heizöl / ULSD",
    "Gold": "Gold",
    "Silver": "Silber",
    "Copper": "Kupfer",
    "Platinum": "Platin",
    "Palladium": "Palladium",
    "Corn": "Mais",
    "Wheat (SRW)": "Weizen (SRW)",
    "Wheat (HRW)": "Weizen (HRW)",
    "Wheat (HR Spring)": "Weizen (Hard Red Spring)",
    "Rough Rice": "Rough Rice",
    "Canola": "Canola",
    "Soybeans": "Sojabohnen",
    "Soybean Meal": "Sojaschrot",
    "Soybean Oil": "Sojaöl",
    "Live Cattle": "Lebendrind",
    "Feeder Cattle": "Mastrind",
    "Lean Hogs": "Magere Schweine",
    "Coffee C": "Kaffee C",
    "Cocoa": "Kakao",
    "Sugar No. 11": "Zucker Nr. 11",
    "Cotton No. 2": "Baumwolle Nr. 2",
    "Orange Juice": "Orangensaft",
    "Lumber": "Bauholz / Lumber",
    "U.S. Treasury 2Y Note": "US Treasury 2Y",
    "U.S. Treasury 5Y Note": "US Treasury 5Y",
    "U.S. Treasury 10Y Note": "US Treasury 10Y",
    "U.S. Treasury Bond 30Y": "US Treasury 30Y",
    "Ultra U.S. Treasury Bond": "Ultra US Treasury Bond",
    "VIX Futures": "VIX Futures",
    "E-mini S&P 500": "E-mini S&P 500",
    "E-mini Nasdaq-100": "E-mini Nasdaq-100",
    "E-mini Dow": "E-mini Dow",
    "E-mini Russell 2000": "E-mini Russell 2000",
}

UNIVERSE_MARKET_COUNT = sum(len(markets) for markets in CLASSIC_MARKETS.values())


def pct(value, digits=1):
    if value is None or not np.isfinite(value):
        return "—"
    return f"{value:.{digits}%}"


def number(value, digits=1):
    if value is None or not np.isfinite(value):
        return "—"
    return f"{value:.{digits}f}"


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def _positioning_dynamics_events(
    enriched_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    group_key_value: str,
    state_basis_value: str,
    polarity_value: int,
) -> pd.DataFrame:
    return build_positioning_episode_dataset(
        enriched_df,
        group_key_value,
        prices=prices_df,
        state_basis=state_basis_value,
        windows=(104, 156, 208),
        thresholds=(70, 75, 80, 85, 90, 95),
        horizons=(1, 2, 4, 8, 12),
        polarity=int(polarity_value),
    )


page_header(
    "Advanced · Research Lab",
    "COT Research Lab",
    "Methoden vergleichen, Robustheit prüfen und Signale validieren.",
    "V3.9.0 · ADVANCED RESEARCH",
)

back_col, detail_col, data_col = st.columns([0.28, 0.36, 0.36])
with back_col:
    st.page_link(
        "pages/watchlist.py",
        label="← Watchlist",
        icon=":material/arrow_back:",
    )
with detail_col:
    if st.button(
        "Marktanalyse · gleicher Markt",
        key="research_to_market",
        use_container_width=True,
    ):
        context = st.session_state.get("selected_market")
        if context:
            st.session_state["_market_context_handoff"] = context
        st.switch_page("pages/marktanalyse.py")
with data_col:
    if st.button(
        "Datenmodell · gleicher Markt",
        key="research_to_data",
        use_container_width=True,
    ):
        context = st.session_state.get("selected_market")
        if context:
            st.session_state["_market_context_handoff"] = context
        st.switch_page("pages/datenmodell.py")

st.caption(
    "Research-Seite, nicht Produktionssignal. Zusätzlich werden die neue robuste "
    "Spec-Flow-Divergenz, Legacy-Vergleich und mechanische Redundanz geprüft."
)

_context = st.session_state.pop("_market_context_handoff", None)
_selected = st.session_state.get("selected_market")

if _context:
    st.session_state["research_asset_class"] = _context["asset_class"]
    st.session_state["research_market"] = _context["market_name"]
elif _selected and "research_asset_class" not in st.session_state:
    st.session_state["research_asset_class"] = _selected["asset_class"]
    st.session_state["research_market"] = _selected["market_name"]



with st.sidebar:
    st.markdown("## Research-Markt")

    asset_class = st.selectbox(
        "Assetklasse",
        list(CLASSIC_MARKETS.keys()),
        format_func=lambda x: ASSET_CLASS_DE.get(x, x),
        key="research_asset_class",
    )

    names = [m["name"] for m in CLASSIC_MARKETS[asset_class]]
    if st.session_state.get("research_market") not in names:
        st.session_state["research_market"] = names[0]

    market_name = st.selectbox(
        "Kontrakt",
        names,
        format_func=lambda x: MARKET_NAME_DE.get(x, x),
        key="research_market",
    )

    market = next(
        m for m in CLASSIC_MARKETS[asset_class]
        if m["name"] == market_name
    )

    st.session_state["selected_market"] = {
        "asset_class": asset_class,
        "market_name": market_name,
    }

    report_type = primary_report_for_asset_class(asset_class)
    group_defs = REPORT_GROUPS[report_type]
    group_labels = {key: label for key, label, _ in group_defs}

    default_group = "producer" if report_type == "disaggregated" else "dealer"
    group_keys = [key for key, _, _ in group_defs]

    group_key = st.selectbox(
        "Tradergruppe",
        group_keys,
        index=group_keys.index(default_group),
        format_func=lambda x: group_labels[x],
    )

    basis = st.radio(
        "Positionsbasis",
        ["net_oi", "raw"],
        index=0,
        format_func=lambda x: (
            "Net / Open Interest"
            if x == "net_oi"
            else "Raw Net"
        ),
        help=(
            "Net/OI ist die voreingestellte Research-Basis. "
            "Raw Net bleibt zum Vergleich verfügbar."
        ),
    )

    price_ticker = st.text_input(
        "Preis-Ticker",
        value=market["ticker"],
    )

    st.markdown("---")
    st.caption(
        f"Extremgrenzen fest: {INDEX_UPPER}/{INDEX_LOWER} · "
        "Forward-Horizonte: 4W / 8W"
    )


# Directional interpretation is deliberately narrow.
if report_type == "disaggregated" and group_key == "producer":
    polarity = 1
    directional_label = (
        "Producer/Merchant: oberes Extrem = bullish, "
        "unteres Extrem = bearish."
    )
else:
    polarity = 0
    directional_label = (
        "Für diese Tradergruppe wird keine automatische "
        "bullish/bearish-Richtung angenommen."
    )


try:
    universe = load_report_universe(report_type)
    resolved = resolve_report_market(market, universe)
except Exception as exc:
    st.error("Die report-spezifische CFTC-Datenbasis konnte nicht geladen werden.")
    with st.expander("Technische Details"):
        st.code(str(exc))
    st.stop()

if not resolved:
    st.error("Keine eindeutige CFTC-Serie für den Research-Markt gefunden.")
    st.stop()

try:
    raw = load_report_history(
        report_type,
        resolved["cftc_contract_market_code"],
    )
except Exception as exc:
    st.error("Die CFTC-Historie konnte nicht geladen werden.")
    with st.expander("Technische Details"):
        st.code(str(exc))
    st.stop()

if raw.empty:
    st.warning("Keine ausreichende CFTC-Historie vorhanden.")
    st.stop()

enriched = enrich_report_positioning(
    raw,
    report_type=report_type,
    index_weeks=26,
    validation_weeks=NET_VALIDATION_WEEKS,
)

prices = load_prices(
    price_ticker,
    start=raw["report_date"].min(),
)

if prices.empty:
    st.error(
        "Für den Research-Test konnte keine Preisreihe geladen werden. "
        "26W/52W-Struktur kann ohne Preise nicht mit Forward-Returns geprüft werden."
    )
    st.stop()


context_strip(
    [
        ("Markt", MARKET_NAME_DE.get(market_name, market_name)),
        ("Report", DATASETS[report_type]["label"]),
        ("Tradergruppe", group_labels[group_key]),
        ("Positionsbasis", "Net/OI" if basis == "net_oi" else "Raw Net"),
    ]
)

st.info(directional_label)

if str(price_ticker).upper().endswith("=F"):
    st.warning(
        "Die Preisreihe ist ein Yahoo-Continuous-Future. Rolls können "
        "Forward-Renditen beeinflussen. Für die endgültige Kalibrierung "
        "wäre eine rollbereinigte Futures-Reihe vorzuziehen."
    )


comparison = index_window_comparison(
    enriched,
    group_key=group_key,
    basis=basis,
    prices=prices,
    windows=(26, 52),
    horizons=(4, 8),
    upper=INDEX_UPPER,
    lower=INDEX_LOWER,
    polarity=polarity,
)

decay = release_decay_study(
    enriched,
    group_key=group_key,
    basis=basis,
    prices=prices,
    index_windows=(26, 52),
    delays=(0, 1, 2, 3, 4),
    horizons=(4, 8),
    upper=INDEX_UPPER,
    lower=INDEX_LOWER,
    polarity=polarity,
)


# V3.11B: The existing V3.10 release direction is tested as a hypothesis for
# the primary positioning group. For TFF this does NOT relabel Dealer as a
# physical hedger; it merely allows the historical price hypothesis to be
# measured instead of assumed.
dynamics_primary = (
    (report_type == "disaggregated" and group_key == "producer")
    or (report_type == "tff" and group_key == "dealer")
)
dynamics_polarity = 1 if dynamics_primary else 0

with st.spinner("Positioning-Dynamics-Episoden werden aufgebaut …"):
    dynamics_events = _positioning_dynamics_events(
        enriched,
        prices,
        group_key,
        basis,
        dynamics_polarity,
    )


tab5, tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Positioning Dynamics",
        "26W vs. 52W",
        "Release Decay",
        "Nullmodell",
        "Spec-Flow & Divergenz",
    ]
)


with tab5:
    section_line(
        "Positioning Dynamics",
        "V3.11B · State → Flow → Outcome · Research only",
    )
    definition(
        "Dieser Bereich verändert keine Produktionsregel. Er untersucht, ob "
        "Lookback, Extremtiefe, Episodendauer, Release-Velocity, Acceleration "
        "und OI-Normalisierung historisch zusätzliche Information über spätere "
        "Preisbewegungen enthalten."
    )

    if report_type == "tff" and group_key == "dealer":
        st.warning(
            "TFF Dealer/Intermediary werden ausdrücklich nicht als physische Hedger "
            "bezeichnet. Für diesen Research-Test wird lediglich die bestehende "
            "V3.10-Hypothese geprüft: Austritt aus oberem Extrem → bullish, "
            "Austritt aus unterem Extrem → bearish. Das Ergebnis darf diese "
            "Hypothese bestätigen oder widerlegen."
        )
    elif dynamics_polarity == 0:
        st.info(
            "Für die gewählte Tradergruppe ist keine Richtungs-Hypothese aktiviert. "
            "State-/Episodenstatistiken bleiben nutzbar; richtungsbereinigte "
            "Forward-Returns werden bewusst nicht interpretiert."
        )

    ctrl1, ctrl2, ctrl3 = st.columns(3)
    with ctrl1:
        dyn_horizon = st.radio(
            "Forward-Horizont",
            [4, 8, 12],
            index=1,
            horizontal=True,
            format_func=lambda x: f"{x}W",
            key="v311_dyn_horizon",
        )
    with ctrl2:
        dyn_window = st.selectbox(
            "Fokus-Lookback",
            [104, 156, 208],
            index=1,
            format_func=lambda x: f"{x} Wochen",
            key="v311_dyn_window",
        )
    with ctrl3:
        dyn_threshold = st.selectbox(
            "Fokus-Extrem",
            [70, 75, 80, 85, 90, 95],
            index=2,
            format_func=lambda x: f"{x}/{100-x}",
            key="v311_dyn_threshold",
        )

    focus = dynamics_events[
        (pd.to_numeric(dynamics_events.get("window_weeks"), errors="coerce") == int(dyn_window))
        & (
            pd.to_numeric(
                dynamics_events.get("threshold_upper"),
                errors="coerce",
            )
            == float(dyn_threshold)
        )
    ].copy() if not dynamics_events.empty else pd.DataFrame()

    releases = (
        focus[focus["release_available"].fillna(False)].copy()
        if not focus.empty and "release_available" in focus.columns
        else pd.DataFrame()
    )

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card(
            "EPISODEN",
            str(len(focus)),
            f"{dyn_window}W · {dyn_threshold}/{100-dyn_threshold}",
        )
    with k2:
        metric_card(
            "RELEASES",
            str(len(releases)),
            "erste Woche außerhalb derselben Extremzone",
        )
    with k3:
        metric_card(
            "MEDIAN DAUER",
            (
                "—"
                if focus.empty
                else f"{pd.to_numeric(focus['duration_weeks'], errors='coerce').median():.1f}W"
            ),
            "zusammenhängende Extrem-Episode",
        )
    with k4:
        metric_card(
            "MEDIAN EXTREMTIEFE",
            (
                "—"
                if focus.empty
                else f"{pd.to_numeric(focus['extreme_depth'], errors='coerce').median():.1f} Pkt."
            ),
            "Abstand jenseits der gewählten Schwelle",
        )

    dyn_state, dyn_depth, dyn_flow, dyn_scope = st.tabs(
        [
            "Window & Threshold",
            "Depth & Duration",
            "Velocity & Acceleration",
            "Research Scope",
        ]
    )

    with dyn_state:
        st.markdown("### 104W vs. 156W vs. 208W · Threshold Grid")
        st.caption(
            "Jede Zeile verwendet unabhängige Extrem-Episoden für genau dieses "
            "Fenster und diese Schwelle. Strengere Schwellen reduzieren die Fallzahl. "
            "Ein einzelner bester In-Sample-Wert wird bewusst nicht automatisch gekürt."
        )

        grid = summarize_window_threshold_grid(
            dynamics_events,
            horizon_weeks=int(dyn_horizon),
        )

        if grid.empty:
            st.info("Keine ausreichenden Episoden für das Window/Threshold-Grid.")
        else:
            grid_display = grid.copy()
            grid_display = grid_display.rename(
                columns={
                    "window_weeks": "Lookback",
                    "threshold_upper": "Upper",
                    "threshold_lower": "Lower",
                    "episodes": "Episoden",
                    "releases": "Releases",
                    "median_duration_weeks": "Median Dauer",
                    "median_extreme_depth": "Median Tiefe",
                    f"n_{int(dyn_horizon)}w": "n Forward",
                    f"median_directional_return_{int(dyn_horizon)}w": "Dir. Median",
                    f"hit_rate_{int(dyn_horizon)}w": "Dir. Hit Rate",
                    f"median_raw_return_{int(dyn_horizon)}w": "Raw Median",
                }
            )

            st.dataframe(
                grid_display.style.format(
                    {
                        "Upper": "{:.0f}",
                        "Lower": "{:.0f}",
                        "Median Dauer": "{:.1f}W",
                        "Median Tiefe": "{:.1f}",
                        "Dir. Median": "{:+.2%}",
                        "Dir. Hit Rate": "{:.1%}",
                        "Raw Median": "{:+.2%}",
                    },
                    na_rep="—",
                ),
                use_container_width=True,
                hide_index=True,
            )

            if dynamics_polarity:
                st.caption(
                    "Dir. Median und Dir. Hit Rate sind nach der getesteten "
                    "Release-Richtung vorzeichenbereinigt. Entscheidend sind "
                    "Stabilität über Fenster/Schwellen und ausreichende Episodenzahl, "
                    "nicht der höchste Einzelwert."
                )

    with dyn_depth:
        st.markdown("### Ist ein tieferes oder länger anhaltendes Extrem informativer?")
        depth_feature = st.radio(
            "Merkmal",
            ["extreme_depth", "duration_weeks"],
            horizontal=True,
            format_func=lambda x: (
                "Extreme Depth"
                if x == "extreme_depth"
                else "Extreme Duration"
            ),
            key="v311_depth_feature",
        )

        study = quantile_effect_study(
            releases,
            depth_feature,
            horizon_weeks=int(dyn_horizon),
            quantiles=4,
        )

        if study.empty:
            st.info(
                "Für diese Kombination liegen noch nicht genügend "
                "richtungsbewertbare Releases für Quartile vor."
            )
        else:
            depth_display = study.rename(
                columns={
                    "bucket": "Quartil",
                    "n": "n",
                    "feature_median": "Merkmals-Median",
                    "directional_return_median": "Dir. Median",
                    "directional_return_mean": "Dir. Mittel",
                    "hit_rate": "Hit Rate",
                }
            )
            st.dataframe(
                depth_display[
                    [
                        "Quartil",
                        "n",
                        "Merkmals-Median",
                        "Dir. Median",
                        "Dir. Mittel",
                        "Hit Rate",
                    ]
                ].style.format(
                    {
                        "Merkmals-Median": "{:.2f}",
                        "Dir. Median": "{:+.2%}",
                        "Dir. Mittel": "{:+.2%}",
                        "Hit Rate": "{:.1%}",
                    },
                    na_rep="—",
                ),
                use_container_width=True,
                hide_index=True,
            )

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=study["feature_median"],
                    y=study["directional_return_median"],
                    mode="lines+markers",
                    name="Quartile",
                )
            )
            fig.add_hline(y=0, line_dash="dot", opacity=.35)
            fig.update_layout(
                height=340,
                margin=dict(l=0, r=0, t=30, b=0),
                xaxis_title=(
                    "Extreme Depth"
                    if depth_feature == "extreme_depth"
                    else "Extreme Duration · Wochen"
                ),
                yaxis_title=f"Median directional Return · {dyn_horizon}W",
                title="Monotonie-Check",
            )
            tradingview_plotly_chart(fig, config=plotly_config())

        st.caption(
            "Die Quartile werden nur innerhalb des oben gewählten Lookbacks und "
            "Thresholds gebildet. Dadurch werden dieselben historischen Episoden "
            "nicht künstlich mehrfach über verschiedene Sensitivitätsdefinitionen gezählt."
        )

    with dyn_flow:
        st.markdown("### Welche Flow-Messung trägt die meiste Information?")
        flow_lag = st.radio(
            "Velocity-Horizont",
            [1, 2, 4],
            index=1,
            horizontal=True,
            format_func=lambda x: f"{x}W",
            key="v311_flow_lag",
        )

        flow_study = compare_flow_measures(
            releases,
            horizon_weeks=int(dyn_horizon),
            lag_weeks=int(flow_lag),
            quantiles=4,
        )

        if flow_study.empty:
            st.info(
                "Für diese Kombination liegen noch nicht genügend "
                "richtungsbewertbare Releases für den Flow-Vergleich vor."
            )
        else:
            flow_labels = {
                f"pct_release_velocity_{flow_lag}w": f"Percentile Velocity {flow_lag}W",
                f"raw_release_velocity_{flow_lag}w": f"Raw Contracts Velocity {flow_lag}W",
                f"net_oi_release_velocity_{flow_lag}w": f"Net/OI Velocity {flow_lag}W",
                "pct_release_acceleration": "Percentile Acceleration 1W vs 4W",
                "raw_release_acceleration": "Raw Acceleration 1W vs 4W",
                "net_oi_release_acceleration": "Net/OI Acceleration 1W vs 4W",
            }

            flow_display = flow_study.copy()
            flow_display["Messung"] = flow_display["feature"].map(flow_labels).fillna(
                flow_display["feature"]
            )
            flow_display = flow_display.rename(
                columns={
                    "bucket": "Quartil",
                    "n": "n",
                    "feature_median": "Flow-Median",
                    "directional_return_median": "Dir. Median",
                    "directional_return_mean": "Dir. Mittel",
                    "hit_rate": "Hit Rate",
                }
            )

            st.dataframe(
                flow_display[
                    [
                        "Messung",
                        "Quartil",
                        "n",
                        "Flow-Median",
                        "Dir. Median",
                        "Dir. Mittel",
                        "Hit Rate",
                    ]
                ].style.format(
                    {
                        "Flow-Median": "{:+.4f}",
                        "Dir. Median": "{:+.2%}",
                        "Dir. Mittel": "{:+.2%}",
                        "Hit Rate": "{:.1%}",
                    },
                    na_rep="—",
                ),
                use_container_width=True,
                hide_index=True,
            )

            available_features = list(flow_study["feature"].dropna().unique())
            chosen_feature = st.selectbox(
                "Messung visualisieren",
                available_features,
                format_func=lambda x: flow_labels.get(x, x),
                key="v311_flow_feature",
            )
            line = flow_study[flow_study["feature"] == chosen_feature].copy()

            if not line.empty:
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=line["feature_median"],
                        y=line["directional_return_median"],
                        mode="lines+markers",
                        name=flow_labels.get(chosen_feature, chosen_feature),
                    )
                )
                fig.add_hline(y=0, line_dash="dot", opacity=.35)
                fig.update_layout(
                    height=340,
                    margin=dict(l=0, r=0, t=30, b=0),
                    xaxis_title=flow_labels.get(chosen_feature, chosen_feature),
                    yaxis_title=f"Median directional Return · {dyn_horizon}W",
                    title="Flow-Stärke vs. späteres Ergebnis",
                )
                tradingview_plotly_chart(fig, config=plotly_config())

        st.markdown(
            """
            **Interpretation:** Positive Release-Velocity bedeutet immer Bewegung
            *aus* dem jeweiligen Extrem. Damit können oberes und unteres Extrem
            gemeinsam untersucht werden. Percentile, Raw Contracts und Net/OI
            bleiben getrennte Messfamilien; es wird noch kein Composite Score gebaut.
            """
        )

    with dyn_scope:
        st.markdown("### Welche offenen Fragen beantwortet V3.11 bereits?")
        coverage = research_question_coverage()
        st.dataframe(
            coverage,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown(
            """
            **Noch nicht in V3.11B enthalten:** exakte Cross-Group-Timestamps,
            marginaler Mehrwert von Asset Manager / Leveraged Funds sowie
            ATR-/MFE-basierte Move-Maturity. Diese Punkte benötigen einen zweiten
            Event-Layer, damit nicht Bestätigung und Timing wieder vermischt werden.
            """
        )

        st.download_button(
            "Episode-Datensatz als CSV exportieren",
            data=dynamics_events.to_csv(index=False).encode("utf-8"),
            file_name=(
                f"positioning_dynamics_{market_name.replace(' ', '_')}_"
                f"{group_key}_{basis}.csv"
            ),
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("#### Methodische Leitplanken")
    st.markdown(
        """
        - Produktionsparameter bleiben unverändert.
        - Sensitivitätsdefinitionen werden nicht nach dem höchsten In-Sample-Return ausgewählt.
        - Depth-/Duration-/Flow-Quartile verwenden nur **eine** gewählte Window/Threshold-Kombination.
        - Für eine Produktionsänderung sind anschließend Zeit-Splits, Market-Cluster-Robustheit
          und ein gesperrter Out-of-Sample-Test erforderlich.
        """
    )


with tab1:
    section_line("26W vs. 52W", "Research-Entscheidung · kein Produktionsparameterwechsel")
    definition(
        "Die beiden Fenster werden anhand von Überschneidung, unabhängigen "
        "Extrem-Episoden und Forward-Renditen verglichen. Die Seite entscheidet "
        "nicht automatisch, welches Fenster verwendet werden soll."
    )
    st.markdown("### 26 Wochen vs. 52 Wochen")

    overlap = comparison["overlap"]

    a, b, c, d = st.columns(4)

    with a:
        metric_card(
            "26W EXTREM-WOCHEN",
            str(overlap.get("extreme_weeks_26", 0)),
            "im gemeinsamen gültigen Zeitraum",
        )

    with b:
        metric_card(
            "52W EXTREM-WOCHEN",
            str(overlap.get("extreme_weeks_52", 0)),
            "im gemeinsamen gültigen Zeitraum",
        )

    with c:
        metric_card(
            "P(52W EXTREM | 26W)",
            pct(overlap.get("p_52_given_26")),
            "Überschneidung der Extremdefinitionen",
        )

    with d:
        metric_card(
            "RICHTUNGS-ÜBEREINSTIMMUNG",
            pct(overlap.get("direction_agreement_when_both")),
            "wenn beide gleichzeitig extrem sind",
        )

    st.caption(
        f"P(26W extrem | 52W extrem) = "
        f"{pct(overlap.get('p_26_given_52'))}. "
        "Eine geringe Überschneidung bedeutet, dass 26W und 52W praktisch "
        "unterschiedliche Signale definieren."
    )

    st.markdown("#### Episoden statt bloßer Wochenzählung")

    episodes = comparison["episodes"].copy()
    if episodes.empty:
        st.info("Keine Extrem-Episoden im verfügbaren Zeitraum.")
    else:
        st.dataframe(
            episodes.style.format(
                {
                    "Median Episodendauer": "{:.1f} Wochen",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("#### Forward-Ergebnisse nach neuem Extrem und Release")

    summary = comparison["event_summary"].copy()

    if summary.empty:
        st.info("Keine ausreichenden Events mit Preis-Folgedaten.")
    else:
        display_summary = summary.drop(
            columns=["Dir. Hit Rate"],
            errors="ignore",
        )
        formats = {
            "Upper Median": "{:+.2%}",
            "Lower Median": "{:+.2%}",
            "Dir. Median": "{:+.2%}",
            "Dir. Mittel": "{:+.2%}",
        }

        st.dataframe(
            display_summary.style.format(formats, na_rep="—"),
            use_container_width=True,
            hide_index=True,
        )

        if polarity == 0:
            st.caption(
                "Für die ausgewählte Tradergruppe werden Upper- und Lower-Events "
                "getrennt als rohe Forward-Renditen gezeigt. Eine künstliche "
                "bullish/bearish-Konvention wird nicht eingeführt."
            )
        else:
            st.caption(
                "Dir.-Werte sind richtungsbereinigt nach der festgelegten "
                "Producer/Merchant-Hypothese. Consecutive Extreme Weeks werden "
                "als eine Episode behandelt."
            )

    st.markdown("#### Was hier entschieden werden soll")
    st.markdown(
        """
        Die Seite kürt **nicht automatisch** 26W oder 52W. Relevant sind gemeinsam:
        Überschneidung, Anzahl unabhängiger Episoden, Episodendauer und die
        publizierbaren 4W/8W-Ergebnisse nach Eintritt bzw. Release. Danach kann
        ein Indexfenster bewusst gewählt und wieder eingefroren werden.
        """
    )


with tab2:
    section_line("Release Decay", "W0 bis W4")
    definition(
        "Release Decay prüft, wie sich die historischen Forward-Renditen verändern, "
        "wenn der Einstieg nach einem beobachteten Release um 0 bis 4 Wochen verzögert wird."
    )
    st.markdown("### Release Decay · wie schnell altert ein Release?")
    st.caption(
        "W0 bedeutet Einstieg beim ersten handelbaren Preis nach der Veröffentlichung "
        "des Release-Reports. W1 bis W4 verschieben den Einstieg jeweils um eine weitere Woche."
    )

    decay_summary = decay["summary"].copy()

    if decay_summary.empty:
        st.info("Keine ausreichenden historischen Release-Ereignisse.")
    else:
        decay_display = decay_summary.drop(
            columns=["Dir. Hit Rate"],
            errors="ignore",
        )
        st.dataframe(
            decay_display.style.format(
                {
                    "Upper Median": "{:+.2%}",
                    "Lower Median": "{:+.2%}",
                    "Dir. Median": "{:+.2%}",
                    "Dir. Mittel": "{:+.2%}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

        if polarity:
            for horizon in ("4W", "8W"):
                fig_data = decay_summary[
                    decay_summary["Horizont"] == horizon
                ].copy()

                if fig_data.empty:
                    continue

                fig = go.Figure()

                for window in ("26W", "52W"):
                    line = fig_data[
                        fig_data["Indexfenster"] == window
                    ].copy()

                    if line.empty:
                        continue

                    line["Delay"] = (
                        line["Einstieg nach Release"]
                        .str.replace("W", "", regex=False)
                        .astype(int)
                    )

                    fig.add_trace(
                        go.Scatter(
                            x=line["Delay"],
                            y=line["Dir. Median"],
                            mode="lines+markers",
                            name=window,
                        )
                    )

                fig.add_hline(y=0, line_dash="dot", opacity=.35)
                fig.update_layout(
                    height=360,
                    margin=dict(l=0, r=0, t=30, b=0),
                    xaxis_title="Wochen nach Release",
                    yaxis_title=f"Median richtungsbereinigte Rendite · {horizon}",
                    title=f"Release Decay · {horizon}-Forward",
                )
                tradingview_chart(
                    fig,
                    date_axis=False,
                    uirevision=f"release-decay-{horizon}",
                )
                tradingview_plotly_chart(
                    fig,
                    config=plotly_config(),
                )

        else:
            st.info(
                "Für diese Tradergruppe wird kein richtungsbereinigter Decay-Chart "
                "gezeichnet. Upper-/Lower-Medianwerte bleiben separat sichtbar."
            )

    st.markdown(
        """
        **Praktische Frage:** Wenn W0/W1 klar stärker sind als W3/W4, ist ein
        drei Wochen alter Release wahrscheinlich bereits ein fortgeschrittenes
        Positionierungsereignis. Wenn die Ergebnisse stabil bleiben, wäre ein
        später Einstieg historisch weniger problematisch. Es wird keine feste
        W3-Regel vorgegeben.
        """
    )


with tab3:
    section_line("Nullmodell", "Circular Time Shift")
    definition(
        "Das Nullmodell verschiebt den gesamten Event-Zeitplan gegen die Preisreihe. "
        "Event-Abstände und Cluster bleiben erhalten, die ursprüngliche Verbindung "
        "zu späteren Renditen wird zerstört."
    )
    st.markdown("### Nullmodell · Circular Time Shift")

    st.caption(
        "Das Nullmodell verschiebt den kompletten historischen Event-Zeitplan "
        "zirkulär gegen die Preisreihe. Abstände, Cluster und Richtungen der "
        "COT-Events bleiben erhalten; ihre ursprüngliche zeitliche Verbindung "
        "zur späteren Preisbewegung wird zerstört."
    )

    if polarity == 0:
        st.warning(
            "Für diese Tradergruppe ist noch keine belastbare Richtungs-Konvention "
            "definiert. Deshalb wird kein directional Hit-Rate-Nullmodell erzeugt. "
            "26W/52W und die rohen Release-Decay-Ergebnisse bleiben trotzdem nutzbar."
        )
    else:
        n1, n2, n3, n4 = st.columns(4)

        with n1:
            null_window = st.selectbox(
                "Indexfenster",
                [26, 52],
                index=0,
                format_func=lambda x: f"{x} Wochen",
            )

        with n2:
            null_event = st.selectbox(
                "Event",
                ["RELEASE", "EXTREM-EINTRITT"],
                index=0,
            )

        with n3:
            null_horizon = st.selectbox(
                "Forward-Horizont",
                [4, 8],
                index=1,
                format_func=lambda x: f"{x} Wochen",
            )

        with n4:
            null_sims = st.selectbox(
                "Simulationen",
                [1000, 2000, 5000, 10000],
                index=1,
            )

        if st.button(
            "Nullmodell berechnen",
            type="primary",
            use_container_width=True,
        ):
            with st.spinner(
                f"{null_sims:,} Circular-Time-Shifts werden berechnet …"
            ):
                result = circular_shift_null_model(
                    enriched,
                    group_key=group_key,
                    basis=basis,
                    prices=prices,
                    index_weeks=int(null_window),
                    event_type=null_event,
                    horizon_weeks=int(null_horizon),
                    upper=INDEX_UPPER,
                    lower=INDEX_LOWER,
                    polarity=polarity,
                    simulations=int(null_sims),
                    seed=42,
                )

            st.session_state["research_null_result"] = result
            st.session_state["research_null_meta"] = {
                "window": null_window,
                "event": null_event,
                "horizon": null_horizon,
                "sims": null_sims,
                "market": market_name,
                "group": group_key,
                "basis": basis,
            }

        result = st.session_state.get("research_null_result")
        meta = st.session_state.get("research_null_meta")

        current_meta = {
            "market": market_name,
            "group": group_key,
            "basis": basis,
        }

        if (
            result
            and meta
            and all(meta.get(k) == v for k, v in current_meta.items())
        ):
            if result.get("observed_n", 0) == 0:
                st.info("Keine ausreichenden Events für dieses Nullmodell.")
            else:
                m1, m2, m3, m4 = st.columns(4)

                with m1:
                    metric_card(
                        "REALE MEDIAN-RENDITE",
                        pct(result.get("observed_median"), 2),
                        f"n = {result.get('observed_n', 0)} Events",
                    )

                with m2:
                    metric_card(
                        "NULL-MEDIAN-RENDITE",
                        pct(result.get("null_median_return"), 2),
                        "Median über die Circular-Time-Shifts",
                    )

                with m3:
                    metric_card(
                        "NULL 95%-BEREICH",
                        (
                            f"{pct(result.get('null_return_low'), 2)} – "
                            f"{pct(result.get('null_return_high'), 2)}"
                        ),
                        "Median-Rendite unter dem Nullmodell",
                    )

                with m4:
                    metric_card(
                        "EMPIRISCHES p · MEDIAN",
                        number(result.get("median_empirical_p"), 3),
                        "Anteil Null-Shifts ≥ beobachteter Median",
                    )

                null_df = result.get("null", pd.DataFrame())

                if null_df is not None and not null_df.empty:
                    fig = go.Figure()
                    fig.add_trace(
                        go.Histogram(
                            x=null_df["median_return"],
                            nbinsx=30,
                            name="Nullverteilung",
                        )
                    )
                    fig.add_vline(
                        x=result["observed_median"],
                        line_dash="dash",
                        annotation_text="beobachtet",
                    )
                    fig.update_layout(
                        height=380,
                        margin=dict(l=0, r=0, t=30, b=0),
                        xaxis_title="Richtungsbereinigte Median-Rendite",
                        yaxis_title="Simulationen",
                        title=(
                            f"{meta['window']}W · {meta['event']} · "
                            f"{meta['horizon']}W Forward"
                        ),
                    )
                    tradingview_chart(
                        fig,
                        date_axis=False,
                        uirevision="null-model-histogram",
                    )
                    tradingview_plotly_chart(
                        fig,
                        config=plotly_config(),
                    )

                st.caption(
                    "Trefferquoten werden hier bewusst nicht angezeigt, weil die "
                    "bestehende Research-Logik keine unbedingte Markt-Basisrate "
                    "für diese Event-Hit-Rate mitführt. Der dargestellte empirische "
                    "p-Wert bezieht sich auf die Median-Rendite des per-market timing null."
                )

    st.markdown("#### Methodische Grenze")
    st.markdown(
        """
        Ein vollständiger Multiple-Testing-Test für die komplette Watchlist müsste
        den **gesamten Marktuniversums-Selektionsprozess** gemeinsam simulieren. Das hier
        integrierte Circular-Time-Shift-Modell ist bewusst der erste, saubere
        Test der Event-Timing-Hypothese pro Markt und keine Behauptung über
        family-wise Signifikanz der gesamten Watchlist.
        """
    )


with tab4:
    section_line(
        "Spec-Flow & Divergenz",
        "robust · OI-normalisiert · no look-ahead",
    )
    definition(
        "Die neue Definition trennt 4W-Preisimpuls, 4W-Spekulanten-Flow und den "
        "8W-Pfad. Die alte Legacy-NC-Definition bleibt parallel erhalten. Es werden "
        "hier bewusst keine Forward-Returns zur Auswahl der Definition verwendet."
    )

    st.markdown("### Methodik")
    st.code(
        f"""
Preis:
  r_4w = log(Dienstagsschluss_t / Dienstagsschluss_t-4W)
  z_price = robust z gegen das vorangehende {NC_DIV_STANDARDIZE_HIST_W}W-Kalenderfenster

Flow:
  net_oi = (Long - Short) / Open Interest
  d_flow_4w = net_oi_t - net_oi_t-4W
  z_flow = robust z gegen das vorangehende {NC_DIV_STANDARDIZE_HIST_W}W-Kalenderfenster

Pfad:
  rho = Spearman(Preis, net_oi) über {NC_DIV_PATH_WINDOW_W}W = {NC_DIV_PATH_WINDOW_W + 1} exakte Wochenpunkte

Bullische Divergenz:
  z_price <= -{NC_DIV_Z_THRESHOLD:.1f} UND z_flow >= +{NC_DIV_Z_THRESHOLD:.1f} UND rho < 0

Bärische Divergenz:
  Vorzeichen gespiegelt

Robuste Streuung:
  IQR / 1.349

Wichtig:
  Referenzfenster wird um 1 Beobachtung nach hinten verschoben; t beeinflusst seine eigene Standardisierung nicht.
  Fehlende COT-Wochen werden für 4W/8W nicht interpoliert.
        """.strip(),
        language="text",
    )

    # Selected-market legacy source for apples-to-apples old/new comparison.
    legacy_error = None
    legacy_enriched = pd.DataFrame()
    legacy_aligned = pd.DataFrame()
    try:
        legacy_universe = load_cftc_universe()
        legacy_resolved = resolve_market(market, legacy_universe)
        if legacy_resolved:
            legacy_raw = load_history(legacy_resolved["cftc_contract_market_code"])
            if not legacy_raw.empty:
                legacy_enriched = enrich_cot(
                    legacy_raw,
                    weeks=26,
                    validation_weeks=NET_VALIDATION_WEEKS,
                    range_weeks=26,
                )
                price_start = min(
                    pd.Timestamp(legacy_raw["report_date"].min()),
                    pd.Timestamp(raw["report_date"].min()),
                )
                structural_prices = load_prices(price_ticker, start=price_start)
                legacy_aligned = attach_cot_prices(legacy_enriched, structural_prices)
                modern_aligned_research = attach_cot_prices(enriched, structural_prices)
            else:
                modern_aligned_research = attach_cot_prices(enriched, prices)
        else:
            modern_aligned_research = attach_cot_prices(enriched, prices)
    except Exception as exc:
        legacy_error = str(exc)
        modern_aligned_research = attach_cot_prices(enriched, prices)

    spec_key = "managed_money" if report_type == "disaggregated" else "leveraged_funds"
    spec_label = "Managed Money" if spec_key == "managed_money" else "Leveraged Funds"
    hedger_key = "producer" if report_type == "disaggregated" else "dealer"
    hedger_label = "Producer / Merchant" if hedger_key == "producer" else "Dealer / Intermediary"

    modern_events = historical_divergence_events(
        modern_aligned_research,
        long_col=f"{spec_key}_long",
        short_col=f"{spec_key}_short",
        group_label=spec_label,
    )

    modern_audit = price_alignment_audit(modern_aligned_research)
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        metric_card(
            "REPORT",
            DATASETS[report_type]["label"],
            f"primärer Spec-Proxy: {spec_label}",
        )
    with a2:
        metric_card(
            "PREIS-AUSRICHTUNG",
            f"{modern_audit['valid']} / {modern_audit['n']}",
            "gleiche ISO-Woche · Preis niemals nach COT-Stichtag",
        )
    with a3:
        metric_card(
            "NEUE EPISODEN",
            str(len(modern_events)),
            "volle bewertbare Historie dieser Reportserie",
        )
    with a4:
        metric_card(
            "OI-NORMALISIERUNG",
            "AKTIV" if NC_DIV_USE_OI_NORM else "INAKTIV",
            "verhindert Messung bloßen Marktwachstums",
        )

    st.markdown("### Redundanzprüfung · beide Datenquellen")
    redundancy_rows = []

    if not legacy_enriched.empty:
        legacy_red = redundancy_metrics(
            legacy_enriched,
            hedger_key="commercial",
            speculative_key="noncommercial",
            nonreportable_key="retail",
            flow_weeks=NC_DIV_FLOW_WINDOW_W,
        )
        redundancy_rows.append({
            "Datenquelle": "Legacy",
            "Paar": "Commercial vs. Non-Commercial",
            "Pearson Δ4W raw": legacy_red["pearson_raw"],
            "Pearson Δ4W Net/OI": legacy_red["pearson_oi"],
            "Erklärte Varianz": legacy_red["explained_variance"],
            "Restvarianz": legacy_red["residual_variance"],
            "NonReportable-Anteil Restdifferenz (R²)": legacy_red["nonreportable_difference_r2"],
            "N": legacy_red["n"],
            "Einordnung": legacy_red["interpretation"],
        })

    modern_red = redundancy_metrics(
        enriched,
        hedger_key=hedger_key,
        speculative_key=spec_key,
        nonreportable_key="nonreportable",
        flow_weeks=NC_DIV_FLOW_WINDOW_W,
    )
    redundancy_rows.append({
        "Datenquelle": DATASETS[report_type]["label"],
        "Paar": f"{hedger_label} vs. {spec_label}",
        "Pearson Δ4W raw": modern_red["pearson_raw"],
        "Pearson Δ4W Net/OI": modern_red["pearson_oi"],
        "Erklärte Varianz": modern_red["explained_variance"],
        "Restvarianz": modern_red["residual_variance"],
        "NonReportable-Anteil Restdifferenz (R²)": modern_red["nonreportable_difference_r2"],
        "N": modern_red["n"],
        "Einordnung": modern_red["interpretation"],
    })

    redundancy_df = pd.DataFrame(redundancy_rows)
    st.dataframe(
        redundancy_df.style.format({
            "Pearson Δ4W raw": "{:+.3f}",
            "Pearson Δ4W Net/OI": "{:+.3f}",
            "Erklärte Varianz": "{:.1%}",
            "Restvarianz": "{:.1%}",
            "NonReportable-Anteil Restdifferenz (R²)": "{:.1%}",
        }, na_rep="—"),
        use_container_width=True,
        hide_index=True,
    )

    if np.isfinite(modern_red["pearson_raw"]) and abs(modern_red["pearson_raw"]) > 0.85:
        st.warning(
            "|r| > 0,85: Der moderne spekulative Flow ist in diesem Markt weitgehend eine "
            "Umformulierung der Hedger-Gegenseite. Er darf in der UI nicht als unabhängige "
            "zweite Bestätigung gezählt werden."
        )
    elif np.isfinite(modern_red["pearson_raw"]) and abs(modern_red["pearson_raw"]) < 0.60:
        st.info(
            "|r| < 0,60: Die moderne spekulative Gruppe besitzt hier strukturell plausiblen "
            "zusätzlichen Informationsgehalt gegenüber der Hedger-Seite."
        )
    else:
        st.caption(
            "Die Kopplung liegt im mittleren Bereich. Der Flow wird als Kontext gezeigt, "
            "aber nicht automatisch als unabhängige Bestätigung behandelt."
        )

    st.markdown("### Alt vs. neu · gleiche Legacy-Datenbasis")
    if legacy_aligned.empty:
        st.warning("Legacy Alt-vs.-Neu konnte für diesen Markt nicht aufgebaut werden.")
        if legacy_error:
            with st.expander("Technische Details"):
                st.code(legacy_error)
    else:
        legacy_old_events = historical_nc_divergences_legacy(
            legacy_aligned,
            lookback_weeks=NC_DIVERGENCE_WEEKS,
            min_confirming_weeks=NC_CONFIRMING_WEEKS,
            min_active_leg_weeks=min(2, NC_DIVERGENCE_WEEKS),
            min_price_move_pct=NC_MIN_PRICE_MOVE_PCT,
            min_net_change_pct=NC_MIN_NET_CHANGE_GROSS_PCT,
            min_active_leg_pct=NC_MIN_ACTIVE_LEG_GROSS_PCT,
            active_leg_share=NC_MIN_ACTIVE_BUILD_SHARE,
        )
        legacy_new_events = historical_divergence_events(
            legacy_aligned,
            long_col="noncommercial_long",
            short_col="noncommercial_short",
            group_label="Legacy Non-Commercial · neue Definition",
        )
        comp = compare_legacy_and_new_events(legacy_old_events, legacy_new_events)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("ALT", str(comp["legacy_signals"]), "Legacy-Episoden")
        with c2:
            metric_card("NEU", str(comp["new_signals"]), "robuste Legacy-NC-Episoden")
        with c3:
            metric_card(
                "ÜBERSCHNEIDUNG",
                pct(comp["overlap_share_union"]),
                "Anteil gemeinsamer Ereigniswochen an der Vereinigungsmenge",
            )
        with c4:
            metric_card(
                "NEU · MODERN",
                str(len(modern_events)),
                f"{spec_label} · nicht 1:1 mit Legacy NC gleichzusetzen",
            )

        yearly = yearly_signal_counts(legacy_old_events, legacy_new_events)
        st.markdown("#### Signale pro Jahr · Zeitdrift")
        if yearly.empty:
            st.info("Keine ausreichenden Ereignisse für die Jahresverteilung.")
        else:
            st.dataframe(yearly, use_container_width=True, hide_index=True)
            st.caption(
                "Die Jahreszählung dient nur der Driftprüfung. Es werden keine späteren Returns "
                "oder Performancekennzahlen zur Auswahl der Definition verwendet."
            )

        st.markdown("#### Moderne Divergenzereignisse")
        if modern_events.empty:
            st.info("Keine modernen Divergenzepisoden im bewertbaren Zeitraum.")
        else:
            modern_display = modern_events.tail(80).sort_values("event_date", ascending=False).copy()
            st.dataframe(
                modern_display.style.format({
                    "r_4w": "{:+.2%}",
                    "d_flow_4w": "{:+.4f}",
                    "z_price": "{:+.2f}",
                    "z_flow": "{:+.2f}",
                    "rho": "{:+.2f}",
                    "divergence_strength": "{:.2f}",
                    "divergence_strength_percentile": "{:.1f}",
                }, na_rep="—"),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown(f"### {UNIVERSE_MARKET_COUNT}-Märkte-Strukturcheck")
    st.caption(
        f"Dieser Check lädt die volle bewertbare Historie aller {UNIVERSE_MARKET_COUNT} Märkte und vergleicht "
        "Signalhäufigkeit, Volatilitätsabhängigkeit, Zeitdrift und Redundanz. Er wird nur "
        "auf Knopfdruck ausgeführt, weil mehrere CFTC-/Preisreihen geladen werden müssen."
    )

    if st.button(
        f"{UNIVERSE_MARKET_COUNT} Märkte strukturell prüfen",
        type="primary",
        use_container_width=True,
        key="run_nc_structural_scan",
    ):
        market_rows = []
        yearly_rows = []
        failures = []

        try:
            legacy_universe_all = load_cftc_universe()
            modern_universes = {
                "disaggregated": load_report_universe("disaggregated"),
                "tff": load_report_universe("tff"),
            }
        except Exception as exc:
            st.error("Die Universen für den Marktuniversums-Check konnten nicht geladen werden.")
            st.code(str(exc))
            legacy_universe_all = pd.DataFrame()
            modern_universes = {}

        if not legacy_universe_all.empty and modern_universes:
            progress = st.progress(0.0, text="Strukturcheck startet …")
            all_markets = [
                (ac, m)
                for ac, markets in CLASSIC_MARKETS.items()
                for m in markets
            ]

            for idx, (ac, cfg) in enumerate(all_markets, start=1):
                progress.progress(
                    idx / len(all_markets),
                    text=f"{idx}/{len(all_markets)} · {cfg['name']}",
                )
                try:
                    lres = resolve_market(cfg, legacy_universe_all)
                    if not lres:
                        raise RuntimeError("Legacy-Serie nicht aufgelöst")
                    lraw = load_history(lres["cftc_contract_market_code"])
                    if lraw.empty:
                        raise RuntimeError("Legacy-Historie leer")
                    lenr = enrich_cot(lraw, weeks=26, validation_weeks=NET_VALIDATION_WEEKS, range_weeks=26)

                    rtype = primary_report_for_asset_class(ac)
                    mres = resolve_report_market(cfg, modern_universes[rtype])
                    if not mres:
                        raise RuntimeError("Moderne Reportserie nicht aufgelöst")
                    mraw = load_report_history(rtype, mres["cftc_contract_market_code"])
                    if mraw.empty:
                        raise RuntimeError("Moderne Historie leer")
                    menr = enrich_report_positioning(
                        mraw,
                        report_type=rtype,
                        index_weeks=26,
                        validation_weeks=NET_VALIDATION_WEEKS,
                    )

                    pstart = min(pd.Timestamp(lraw["report_date"].min()), pd.Timestamp(mraw["report_date"].min()))
                    px = load_prices(cfg["ticker"], start=pstart)
                    if px.empty:
                        raise RuntimeError("Preisreihe leer")

                    laligned = attach_cot_prices(lenr, px)
                    malign = attach_cot_prices(menr, px)

                    old_ev = historical_nc_divergences_legacy(
                        laligned,
                        lookback_weeks=NC_DIVERGENCE_WEEKS,
                        min_confirming_weeks=NC_CONFIRMING_WEEKS,
                        min_active_leg_weeks=min(2, NC_DIVERGENCE_WEEKS),
                        min_price_move_pct=NC_MIN_PRICE_MOVE_PCT,
                        min_net_change_pct=NC_MIN_NET_CHANGE_GROSS_PCT,
                        min_active_leg_pct=NC_MIN_ACTIVE_LEG_GROSS_PCT,
                        active_leg_share=NC_MIN_ACTIVE_BUILD_SHARE,
                    )
                    new_legacy_ev = historical_divergence_events(
                        laligned,
                        long_col="noncommercial_long",
                        short_col="noncommercial_short",
                        group_label="Legacy NC",
                    )
                    skey = "managed_money" if rtype == "disaggregated" else "leveraged_funds"
                    hkey = "producer" if rtype == "disaggregated" else "dealer"
                    modern_ev = historical_divergence_events(
                        malign,
                        long_col=f"{skey}_long",
                        short_col=f"{skey}_short",
                        group_label=skey,
                    )
                    red_l = redundancy_metrics(
                        lenr,
                        hedger_key="commercial",
                        speculative_key="noncommercial",
                        nonreportable_key="retail",
                        flow_weeks=NC_DIV_FLOW_WINDOW_W,
                    )
                    red_m = redundancy_metrics(
                        menr,
                        hedger_key=hkey,
                        speculative_key=skey,
                        nonreportable_key="nonreportable",
                        flow_weeks=NC_DIV_FLOW_WINDOW_W,
                    )
                    hist = build_divergence_history(
                        laligned,
                        long_col="noncommercial_long",
                        short_col="noncommercial_short",
                    )
                    vol = float(pd.to_numeric(hist["r_4w"], errors="coerce").abs().median())
                    valid_dates = pd.to_datetime(hist.loc[hist["r_4w"].notna(), "report_date"])
                    span_years = max(
                        1.0,
                        (valid_dates.max() - valid_dates.min()).days / 365.25,
                    ) if not valid_dates.empty else np.nan
                    comp_m = compare_legacy_and_new_events(old_ev, new_legacy_ev)

                    market_rows.append({
                        "Assetklasse": ac,
                        "Markt": cfg["name"],
                        "Symbol": cfg["symbol"],
                        "Median |4W Log-Rendite|": vol,
                        "Alt Signale": len(old_ev),
                        "Neu Legacy": len(new_legacy_ev),
                        "Neu Modern": len(modern_ev),
                        "Alt/Jahr": len(old_ev) / span_years if np.isfinite(span_years) else np.nan,
                        "Neu/Jahr": len(new_legacy_ev) / span_years if np.isfinite(span_years) else np.nan,
                        "Overlap Alt/Neu": comp_m["overlap_share_union"],
                        "Legacy r": red_l["pearson_raw"],
                        "Modern r": red_m["pearson_raw"],
                        "Modern Restvarianz": red_m["residual_variance"],
                    })

                    for definition_name, events in (
                        ("Alt", old_ev),
                        ("Neu Legacy", new_legacy_ev),
                        ("Neu Modern", modern_ev),
                    ):
                        if events is None or events.empty:
                            continue
                        tmp = events.copy()
                        tmp["Jahr"] = pd.to_datetime(tmp["event_date"]).dt.year
                        for year, n in tmp.groupby("Jahr").size().items():
                            yearly_rows.append({
                                "Jahr": int(year),
                                "Definition": definition_name,
                                "Signale": int(n),
                            })
                except Exception as exc:
                    failures.append({"Markt": cfg["name"], "Fehler": str(exc)})

            progress.empty()
            st.session_state["nc_structural_markets"] = pd.DataFrame(market_rows)
            st.session_state["nc_structural_yearly"] = pd.DataFrame(yearly_rows)
            st.session_state["nc_structural_failures"] = pd.DataFrame(failures)

    scan_df = st.session_state.get("nc_structural_markets", pd.DataFrame())
    scan_yearly = st.session_state.get("nc_structural_yearly", pd.DataFrame())
    scan_failures = st.session_state.get("nc_structural_failures", pd.DataFrame())

    if scan_df is not None and not scan_df.empty:
        st.markdown("#### Signalverteilung über Märkte")
        st.dataframe(
            scan_df.style.format({
                "Median |4W Log-Rendite|": "{:.2%}",
                "Alt/Jahr": "{:.2f}",
                "Neu/Jahr": "{:.2f}",
                "Overlap Alt/Neu": "{:.1%}",
                "Legacy r": "{:+.3f}",
                "Modern r": "{:+.3f}",
                "Modern Restvarianz": "{:.1%}",
            }, na_rep="—"),
            use_container_width=True,
            hide_index=True,
        )

        valid_old = scan_df[["Median |4W Log-Rendite|", "Alt/Jahr"]].dropna()
        valid_new = scan_df[["Median |4W Log-Rendite|", "Neu/Jahr"]].dropna()
        old_vol_corr = (
            valid_old["Median |4W Log-Rendite|"].corr(valid_old["Alt/Jahr"])
            if len(valid_old) >= 3 else np.nan
        )
        new_vol_corr = (
            valid_new["Median |4W Log-Rendite|"].corr(valid_new["Neu/Jahr"])
            if len(valid_new) >= 3 else np.nan
        )

        v1, v2 = st.columns(2)
        with v1:
            metric_card(
                "VOLATILITÄTSABHÄNGIGKEIT ALT",
                number(old_vol_corr, 3),
                "Korrelation Median |4W-Return| vs. Signale/Jahr",
            )
        with v2:
            metric_card(
                "VOLATILITÄTSABHÄNGIGKEIT NEU",
                number(new_vol_corr, 3),
                "näher an 0 = gleichmäßigere Signalhäufigkeit über Märkte",
            )

        if scan_yearly is not None and not scan_yearly.empty:
            st.markdown("#### Signale pro Jahr · gesamtes Universum")
            yearly_pivot = (
                scan_yearly.groupby(["Jahr", "Definition"])["Signale"]
                .sum()
                .unstack(fill_value=0)
                .reset_index()
                .sort_values("Jahr")
            )
            st.dataframe(yearly_pivot, use_container_width=True, hide_index=True)

        if scan_failures is not None and not scan_failures.empty:
            with st.expander(f"Nicht auswertbare Märkte ({len(scan_failures)})"):
                st.dataframe(scan_failures, use_container_width=True, hide_index=True)

    st.warning(
        "Entscheidungsregel dieser Research-Seite: Die neue Definition wird nicht danach ausgewählt, "
        "welche Variante spätere Renditen besser erklärt. Entscheidend sind strukturelle Plausibilität, "
        "geringere Volatilitätsabhängigkeit, keine offensichtliche Zeitdrift und die Redundanz zum Hedger-Flow."
    )
