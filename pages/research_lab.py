
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
from src.positioning_cross_market import (
    aggregate_cross_market_scans,
    candidate_flow_overlap,
    cross_market_candidate_detail,
    cross_market_coverage_diagnostic,
    cross_market_findings,
    cross_market_flow_redundancy,
    cross_market_leave_one_out,
    cross_market_neighborhood_summary,
    cross_market_parameter_neighborhood,
    evaluate_pre_oos_decision_gate,
    fixed_parameter_region_matrix,
    leave_one_out_summary,
)
from src.positioning_robustness import (
    build_pre_oos_freeze_snapshot,
    candidate_freeze_id,
    candidate_overlap_table,
    candidate_review_label,
    distinct_candidate_shortlist,
    flow_monotonicity_diagnostic,
    freeze_snapshot_json,
    frozen_candidates_from_scan,
    incremental_value_table,
    monotonicity_summary,
    overlap_redundancy_summary,
    reviewed_shortlist,
    scan_parameter_robustness,
    scanner_findings,
    strict_monotonicity_assessment,
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

# V3.20.0 · ADVANCED DIRECT ACCESS GUARD
_v3200_trader = dict(st.session_state.get("auth_trader") or {})
if (
    not _v3200_trader
    or str(_v3200_trader.get("role", "TRADER")).upper() != "ADMIN"
):
    st.error("Kein Zugriff auf den Advanced-Bereich.")
    st.stop()



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



CORE_FX_RESEARCH_MARKETS = (
    "Euro FX",
    "British Pound",
    "Japanese Yen",
    "Swiss Franc",
    "Canadian Dollar",
    "Australian Dollar",
    "New Zealand Dollar",
)


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def _cross_market_scan_one(
    market_name_value: str,
    group_key_value: str,
    state_basis_value: str,
    horizon_value: int,
) -> tuple[pd.DataFrame, dict]:
    asset_class_value = "Currencies"
    market_spec = next(
        m for m in CLASSIC_MARKETS[asset_class_value]
        if m["name"] == market_name_value
    )
    report_type_value = primary_report_for_asset_class(asset_class_value)

    universe_value = load_report_universe(report_type_value)
    resolved_value = resolve_report_market(market_spec, universe_value)
    if not resolved_value:
        raise ValueError(
            f"Keine CFTC-Serie für {market_name_value} auflösbar."
        )

    raw_value = load_report_history(
        report_type_value,
        resolved_value["cftc_contract_market_code"],
    )
    if raw_value.empty:
        raise ValueError(
            f"Keine CFTC-Historie für {market_name_value}."
        )

    enriched_value = enrich_report_positioning(
        raw_value,
        report_type=report_type_value,
        index_weeks=26,
        validation_weeks=NET_VALIDATION_WEEKS,
    )

    prices_value = load_prices(
        market_spec["ticker"],
        start=raw_value["report_date"].min(),
    )
    if prices_value.empty:
        raise ValueError(
            f"Keine Preisreihe für {market_name_value} / {market_spec['ticker']}."
        )

    events_value = build_positioning_episode_dataset(
        enriched_value,
        group_key_value,
        prices=prices_value,
        state_basis=state_basis_value,
        windows=(104, 156, 208),
        thresholds=(70, 75, 80, 85, 90, 95),
        horizons=(1, 2, 4, 8, 12),
        polarity=1,
    )

    scan_value, meta_value = scan_parameter_robustness(
        events_value,
        horizon_weeks=int(horizon_value),
        flow_quantiles=(0.50, 0.75),
        train_share=0.60,
        validation_share=0.20,
        min_train=8,
        min_validation=4,
    )
    return scan_value, meta_value, events_value



page_header(
    "Research · Positioning Dynamics",
    "Positioning Dynamics Research",
    "Research-Prozess: Structural State → Flow Dynamics → Validation → Reviewed Hypotheses → Frozen OOS.",
    "V3.12B · VERTICAL POSITIONING WORKFLOW",
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



section_line(
    "1 · Research Context",
    "Datensatz und Auswertungsrahmen · jede Änderung definiert einen neuen Research-Kontext",
)

ctx_a, ctx_b = st.columns(2)

with ctx_a:
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
        "Markt / Kontrakt",
        names,
        format_func=lambda x: MARKET_NAME_DE.get(x, x),
        key="research_market",
    )

with ctx_b:
    market = next(
        m for m in CLASSIC_MARKETS[asset_class]
        if m["name"] == market_name
    )

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
        key=f"research_group|{asset_class}",
    )

    basis = st.radio(
        "State-Basis",
        ["net_oi", "raw"],
        index=0,
        horizontal=True,
        format_func=lambda x: (
            "Net / Open Interest"
            if x == "net_oi"
            else "Raw Net"
        ),
        help=(
            "Diese Auswahl definiert nur den strukturellen State. "
            "Der Flow-Scanner untersucht Percentile-, Raw- und Net/OI-Dynamik parallel."
        ),
        key=f"research_state_basis|{asset_class}|{market_name}",
    )

st.session_state["selected_market"] = {
    "asset_class": asset_class,
    "market_name": market_name,
}

ctx_c, ctx_d = st.columns([0.62, 0.38])

with ctx_c:
    dyn_horizon = st.radio(
        "Forward-Horizont",
        [4, 8, 12],
        index=1,
        horizontal=True,
        format_func=lambda x: f"{x}W",
        key=f"v312_research_horizon|{asset_class}|{market_name}|{group_key}|{basis}",
    )

with ctx_d:
    st.markdown("**Flow-Familien im Scan**")
    st.caption("Percentile · Raw Contracts · Net/OI · Velocity · Acceleration")

price_ticker = market["ticker"]
with st.expander("Advanced · Preis-Proxy / Datenquelle", expanded=False):
    price_ticker = st.text_input(
        "Preis-Ticker überschreiben",
        value=market["ticker"],
        key=f"research_price_ticker|{asset_class}|{market_name}",
        help=(
            "Standardmäßig wird der im Marktmodell hinterlegte Preis-Proxy verwendet. "
            "Nur für gezielte Daten-Audits überschreiben."
        ),
    )

research_context_key = (
    f"{asset_class}|{market_name}|{group_key}|{basis}|"
    f"{str(price_ticker).upper()}|{int(dyn_horizon)}W"
)

st.caption(
    "Research Context ID · "
    f"{MARKET_NAME_DE.get(market_name, market_name)} · "
    f"{group_labels[group_key]} · "
    f"{'Net/OI' if basis == 'net_oi' else 'Raw Net'} · "
    f"{int(dyn_horizon)}W"
)


# Directional interpretation is deliberately narrow.
if report_type == "disaggregated" and group_key == "producer":
    polarity = 1
    directional_label = (
        "Producer/Merchant: oberes Extrem = bullish, "
        "unteres Extrem = bearish."
    )
elif report_type == "tff" and group_key == "dealer":
    polarity = 0
    directional_label = (
        "TFF Dealer/Intermediary: Positioning Dynamics testet die bestehende "
        "Release-Richtung als Research-Hypothese. Legacy-Module bleiben "
        "bewusst ohne automatische Dealer-Richtung."
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
        ("State-Basis", "Net/OI" if basis == "net_oi" else "Raw Net"),
        ("Forward", f"{int(dyn_horizon)}W"),
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


st.markdown(
    """
    **Research Workflow**

    `1 Context` → `2 Structural State` → `3 Flow Dynamics` →
    `4 Candidate Validation` → `5 Reviewed Hypotheses` → `6 Frozen OOS`
    """
)

tab5 = st.container()


with tab5:
    section_line(
        "2 · Structural State",
        "Welcher langfristige Positionierungszustand trägt robuste Information?",
    )
    definition(
        "State und Flow werden bewusst getrennt. Die State-Basis bestimmt den "
        "strukturellen Positionierungszustand. Parallel prüft der Flow-Scanner "
        "Percentile-, Raw-Contract- und Net/OI-Dynamik. Keine dieser Research-"
        "Auswertungen verändert automatisch die Produktionslogik."
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

    ctrl2, ctrl3 = st.columns(2)
    with ctrl2:
        dyn_window = st.selectbox(
            "Detail-Lookback",
            [104, 156, 208],
            index=1,
            format_func=lambda x: f"{x} Wochen",
            key=f"v311_dyn_window|{research_context_key}",
        )
    with ctrl3:
        dyn_threshold = st.selectbox(
            "Detail-Threshold",
            [70, 75, 80, 85, 90, 95],
            index=2,
            format_func=lambda x: f"{x}/{100-x}",
            key=f"v311_dyn_threshold|{research_context_key}",
        )

    st.caption(
        "Detail-Lookback und Detail-Threshold steuern nur die folgenden "
        "Detailansichten. Der Robustness Scanner untersucht weiterhin automatisch "
        "alle 104/156/208W- und Threshold-Kandidaten."
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

    # Legacy UI markers retained for regression history:
    # Depth & Duration
    # Velocity & Acceleration
    # Auto Scanner
    # Research Scope
    dyn_state = st.container()
    dyn_depth = st.container()
    dyn_flow = st.container()
    dyn_scanner = st.container()

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
        st.markdown("### Extreme Depth & Duration")
        st.caption(
            "Zweite Ebene des Structural-State-Tests: Nicht nur ob ein Extrem "
            "vorliegt, sondern wie tief und wie lange es historisch bestand."
        )
        st.markdown("#### Ist ein tieferes oder länger anhaltendes Extrem informativer?")
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

    section_line(
        "3 · Flow Dynamics",
        "Welche Veränderung der Positionierung liefert Timing-Information?",
    )

    with dyn_flow:
        st.caption(
            "State und Flow konkurrieren nicht um denselben Job. Der Structural "
            "State beschreibt den langfristigen Zustand; Flow misst, wie sich "
            "Positionierung daraus heraus bewegt."
        )
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

    section_line(
        "4 · Candidate Validation",
        "Train + Validation · Sample · Neighborhood · Incremental Value · Overlap · Monotonicity",
    )

    with dyn_scanner:
        st.markdown("### Parameter & Robustness Scanner")
        st.caption(
            "Automatische Suche nach stabilen Parameterregionen. Das Ranking basiert "
            "ausschließlich auf Train + Validation, Stichprobengröße und "
            "Parameter-Nachbarschaft. OOS wird nicht für Ranking oder Score verwendet."
        )

        if dynamics_polarity == 0:
            st.info(
                "Der automatische Richtungs-Scanner ist für diese Tradergruppe deaktiviert, "
                "weil keine bullish/bearish Release-Hypothese festgelegt ist."
            )
        else:
            robustness_scan, robustness_meta = scan_parameter_robustness(
                dynamics_events,
                horizon_weeks=int(dyn_horizon),
                flow_quantiles=(0.50, 0.75),
                train_share=0.60,
                validation_share=0.20,
                min_train=8,
                min_validation=4,
            )
            findings = scanner_findings(robustness_scan)

            if robustness_scan.empty:
                st.info(
                    "Für einen belastbaren Train/Validation/OOS-Scan ist in dieser "
                    "Markt-/Tradergruppen-Kombination noch nicht genügend Historie vorhanden."
                )
            else:
                best_state = findings.get("top_state")
                best_flow = findings.get("top_flow")

                best_state_text = (
                    "—"
                    if not best_state
                    else (
                        f"{int(best_state['window_weeks'])}W · "
                        f"{best_state['threshold_upper']:.0f}/"
                        f"{best_state['threshold_lower']:.0f}"
                    )
                )

                flow_name_map = {
                    "pct_release_velocity_1w": "Percentile Velocity 1W",
                    "pct_release_velocity_2w": "Percentile Velocity 2W",
                    "pct_release_velocity_4w": "Percentile Velocity 4W",
                    "raw_release_velocity_1w": "Raw Velocity 1W",
                    "raw_release_velocity_2w": "Raw Velocity 2W",
                    "raw_release_velocity_4w": "Raw Velocity 4W",
                    "net_oi_release_velocity_1w": "Net/OI Velocity 1W",
                    "net_oi_release_velocity_2w": "Net/OI Velocity 2W",
                    "net_oi_release_velocity_4w": "Net/OI Velocity 4W",
                    "pct_release_acceleration": "Percentile Acceleration",
                    "raw_release_acceleration": "Raw Acceleration",
                    "net_oi_release_acceleration": "Net/OI Acceleration",
                }
                best_flow_text = (
                    "—"
                    if not best_flow
                    else flow_name_map.get(
                        str(best_flow["feature"]),
                        str(best_flow["feature"]),
                    )
                )

                r1, r2, r3, r4 = st.columns(4)
                with r1:
                    metric_card(
                        "KANDIDATEN",
                        str(int(robustness_meta.get("candidate_count", 0))),
                        f"{int(robustness_meta.get('eligible_count', 0))} mit Mindest-Sample",
                    )
                with r2:
                    metric_card(
                        "ROBUST",
                        str(int(robustness_meta.get("robust_count", 0))),
                        "Score ≥ 75 · Train + Validation",
                    )
                with r3:
                    metric_card(
                        "TOP STATE",
                        best_state_text,
                        (
                            "—"
                            if not best_state
                            else f"Score {best_state['robustness_score']:.1f}/100"
                        ),
                    )
                with r4:
                    metric_card(
                        "TOP FLOW",
                        best_flow_text,
                        (
                            "—"
                            if not best_flow
                            else f"Score {best_flow['robustness_score']:.1f}/100"
                        ),
                    )

                st.markdown("#### Automatisches Ranking · OOS verborgen")
                top_scan = robustness_scan[
                    robustness_scan["sample_ok"].fillna(False)
                ].head(20).copy()

                if top_scan.empty:
                    st.info("Keine Kandidaten erfüllen aktuell das Mindest-Sample.")
                else:
                    top_scan["Parameter"] = top_scan.apply(
                        lambda r: (
                            f"{int(r['window_weeks'])}W · "
                            f"{r['threshold_upper']:.0f}/{r['threshold_lower']:.0f}"
                        ),
                        axis=1,
                    )
                    top_scan["Flow"] = top_scan.apply(
                        lambda r: (
                            "STATE ONLY"
                            if r["candidate_type"] == "STATE"
                            else (
                                f"{flow_name_map.get(str(r['feature']), str(r['feature']))} "
                                f"· Top {100 - int(round(float(r['flow_quantile']) * 100))}%"
                            )
                        ),
                        axis=1,
                    )

                    ranking_display = top_scan[
                        [
                            "rank_train_validation",
                            "Parameter",
                            "Flow",
                            "n_train",
                            "train_median",
                            "n_validation",
                            "validation_median",
                            "neighbor_positive_share",
                            "robustness_score",
                            "status",
                        ]
                    ].rename(
                        columns={
                            "rank_train_validation": "Rang",
                            "n_train": "n Train",
                            "train_median": "Train Median",
                            "n_validation": "n Validation",
                            "validation_median": "Validation Median",
                            "neighbor_positive_share": "Nachbarschaft positiv",
                            "robustness_score": "Robustness",
                            "status": "Status",
                        }
                    )

                    st.dataframe(
                        ranking_display.style.format(
                            {
                                "Rang": "{:.0f}",
                                "Train Median": "{:+.2%}",
                                "Validation Median": "{:+.2%}",
                                "Nachbarschaft positiv": "{:.0%}",
                                "Robustness": "{:.1f}",
                            },
                            na_rep="—",
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )


                st.markdown("#### Pre-OOS Diagnose")
                st.caption(
                    "Bevor Locked OOS geöffnet wird, prüft dieser Block, ob die "
                    "Top-Kandidaten tatsächlich unterschiedliche Information enthalten "
                    "und ob stärkere Flow-Dynamik geordnet mit besseren Returns zusammenhängt."
                )

                diag_left, diag_right = st.columns(2)

                with diag_left:
                    st.markdown("##### Event Overlap · Top Flow")
                    overlap_diag = candidate_overlap_table(
                        dynamics_events,
                        robustness_scan,
                        top_n=6,
                    )
                    if overlap_diag.empty:
                        st.info("Noch nicht genügend vergleichbare Flow-Kandidaten.")
                    else:
                        overlap_display = overlap_diag.head(12).rename(
                            columns={
                                "candidate_a": "Kandidat A",
                                "candidate_b": "Kandidat B",
                                "n_a": "n A",
                                "n_b": "n B",
                                "intersection": "Gemeinsam",
                                "jaccard": "Jaccard",
                                "overlap_coefficient": "Overlap",
                                "interpretation": "Einordnung",
                            }
                        )
                        st.dataframe(
                            overlap_display.style.format(
                                {
                                    "Jaccard": "{:.0%}",
                                    "Overlap": "{:.0%}",
                                },
                                na_rep="—",
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )
                        st.caption(
                            "Jaccard ≥ 80% bedeutet: Zwei scheinbar verschiedene "
                            "Flow-Messungen wählen nahezu dieselben historischen Episoden. "
                            "Sie sollten dann nicht als unabhängige Information behandelt werden."
                        )

                with diag_right:
                    st.markdown("##### Incremental Value · Flow vs. State")
                    incremental_diag = incremental_value_table(
                        robustness_scan,
                        top_n=15,
                    )
                    if incremental_diag.empty:
                        st.info("Noch keine Flow-Kandidaten mit passender State-Baseline.")
                    else:
                        incremental_display = incremental_diag.copy()
                        incremental_display["Flow"] = incremental_display["feature"].map(
                            flow_name_map
                        ).fillna(incremental_display["feature"])
                        incremental_display["Filter"] = incremental_display["flow_quantile"].map(
                            lambda q: f"Top {100 - int(round(float(q) * 100))}%"
                        )
                        incremental_display = incremental_display[
                            [
                                "parameter",
                                "Flow",
                                "Filter",
                                "validation_median_lift",
                                "validation_hit_rate_lift",
                                "validation_sample_retention",
                                "neighbor_positive_share",
                            ]
                        ].rename(
                            columns={
                                "parameter": "Parameter",
                                "validation_median_lift": "Val Median Lift",
                                "validation_hit_rate_lift": "Val Hit Lift",
                                "validation_sample_retention": "Val Sample behalten",
                                "neighbor_positive_share": "Nachbarschaft positiv",
                            }
                        )
                        st.dataframe(
                            incremental_display.style.format(
                                {
                                    "Val Median Lift": "{:+.2%}",
                                    "Val Hit Lift": "{:+.1%}",
                                    "Val Sample behalten": "{:.0%}",
                                    "Nachbarschaft positiv": "{:.0%}",
                                },
                                na_rep="—",
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )
                        st.caption(
                            "Ein Flow-Filter ist nur dann interessant, wenn der zusätzliche "
                            "Validation-Effekt den Verlust an Episoden rechtfertigt."
                        )

                eligible_flow_diag = robustness_scan[
                    robustness_scan["sample_ok"].fillna(False)
                    & robustness_scan["candidate_type"].eq("FLOW")
                ].sort_values(
                    ["rank_train_validation", "robustness_score"],
                    ascending=[True, False],
                ).head(8)

                st.markdown("##### Monotonicity · wird stärkerer Flow tatsächlich besser?")
                if eligible_flow_diag.empty:
                    st.info("Keine Flow-Kandidaten mit ausreichendem Sample.")
                else:
                    mono_indices = list(eligible_flow_diag.index)

                    def _mono_label(idx):
                        row = robustness_scan.loc[idx]
                        feature_label = flow_name_map.get(
                            str(row["feature"]),
                            str(row["feature"]),
                        )
                        return (
                            f"Rang {int(row['rank_train_validation'])} · "
                            f"{int(row['window_weeks'])}W "
                            f"{row['threshold_upper']:.0f}/{row['threshold_lower']:.0f} · "
                            f"{feature_label} · "
                            f"Top {100 - int(round(float(row['flow_quantile']) * 100))}%"
                        )

                    mono_idx = st.selectbox(
                        "Flow-Kandidat für Monotonieprüfung",
                        mono_indices,
                        format_func=_mono_label,
                        key=f"v311c1_monotonic_candidate|{research_context_key}",
                    )
                    mono_candidate = robustness_scan.loc[mono_idx]
                    mono_diag = flow_monotonicity_diagnostic(
                        dynamics_events,
                        mono_candidate,
                    )
                    mono_summary = monotonicity_summary(mono_diag)

                    if mono_diag.empty:
                        st.info(
                            "Für diesen Kandidaten können aus dem Train-Segment "
                            "keine stabilen Flow-Quartile gebildet werden."
                        )
                    else:
                        m1, m2, m3, m4 = st.columns(4)
                        with m1:
                            metric_card(
                                "TRAIN MONOTON",
                                (
                                    "—"
                                    if pd.isna(mono_summary["train_positive_steps"])
                                    else f"{mono_summary['train_positive_steps']:.0%}"
                                ),
                                "Anteil positiver Q1→Q4 Schritte",
                            )
                        with m2:
                            metric_card(
                                "VALIDATION MONOTON",
                                (
                                    "—"
                                    if pd.isna(mono_summary["validation_positive_steps"])
                                    else f"{mono_summary['validation_positive_steps']:.0%}"
                                ),
                                "gleiche Train-Quartilgrenzen",
                            )
                        with m3:
                            metric_card(
                                "PARAMETER-NACHBARSCHAFT",
                                (
                                    "—"
                                    if pd.isna(mono_candidate["neighbor_positive_share"])
                                    else f"{mono_candidate['neighbor_positive_share']:.0%}"
                                ),
                                f"{int(mono_candidate['neighbor_count'])} direkte Nachbarn",
                            )
                        with m4:
                            metric_card(
                                "SAMPLE",
                                (
                                    f"{int(mono_candidate['n_train'])} / "
                                    f"{int(mono_candidate['n_validation'])}"
                                ),
                                "Train / Validation",
                            )

                        mono_display = mono_diag.rename(
                            columns={
                                "bucket": "Flow Quartil",
                                "n_train": "n Train",
                                "train_feature_median": "Train Flow Median",
                                "train_median": "Train Return",
                                "train_hit_rate": "Train Hit",
                                "n_validation": "n Validation",
                                "validation_feature_median": "Val Flow Median",
                                "validation_median": "Val Return",
                                "validation_hit_rate": "Val Hit",
                            }
                        )
                        st.dataframe(
                            mono_display.style.format(
                                {
                                    "Train Flow Median": "{:+.4f}",
                                    "Train Return": "{:+.2%}",
                                    "Train Hit": "{:.1%}",
                                    "Val Flow Median": "{:+.4f}",
                                    "Val Return": "{:+.2%}",
                                    "Val Hit": "{:.1%}",
                                },
                                na_rep="—",
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )

                        st.caption(
                            "Legacy-Schrittquote: Die 2-von-3-Zahl bleibt nur deskriptiv. "
                            "Die eigentliche Bewertung erfolgt ausschließlich im "
                            "Strict-Monotonicity-Block C.2."
                        )

                st.caption(
                    "Alle Pre-OOS-Diagnosen verwenden ausschließlich Train + Validation. "
                    "Locked OOS bleibt unangetastet."
                )


                st.markdown("##### Strict Monotonicity · C.2")
                st.caption(
                    "Die frühere 2-von-3-Schritt-Heuristik wird nicht mehr als "
                    "Monotonie interpretiert. Entscheidend sind vollständige Ordnung, "
                    "Spearman-Rangrelation, Q4−Q1-Spread und Replikation."
                )

                if not eligible_flow_diag.empty:
                    strict_assessment = strict_monotonicity_assessment(mono_diag)

                    s1, s2, s3, s4 = st.columns(4)
                    with s1:
                        metric_card(
                            "ORDERED TRAIN",
                            "✓" if strict_assessment["train_ordered"] else "✗",
                            "Q1 < Q2 < Q3 < Q4",
                        )
                    with s2:
                        metric_card(
                            "ORDERED VALIDATION",
                            "✓" if strict_assessment["validation_ordered"] else "✗",
                            "gleiche Train-Buckets",
                        )
                    with s3:
                        metric_card(
                            "SPEARMAN TRAIN",
                            (
                                "—"
                                if pd.isna(strict_assessment["train_spearman"])
                                else f"{strict_assessment['train_spearman']:+.2f}"
                            ),
                            "Quartilrang ↔ Return",
                        )
                    with s4:
                        metric_card(
                            "SPEARMAN VALIDATION",
                            (
                                "—"
                                if pd.isna(strict_assessment["validation_spearman"])
                                else f"{strict_assessment['validation_spearman']:+.2f}"
                            ),
                            "Quartilrang ↔ Return",
                        )

                    s5, s6, s7, s8 = st.columns(4)
                    with s5:
                        metric_card(
                            "Q4 − Q1 TRAIN",
                            (
                                "—"
                                if pd.isna(strict_assessment["train_q4_q1_spread"])
                                else f"{strict_assessment['train_q4_q1_spread']:+.2%}"
                            ),
                            "Top-Flow minus Bottom-Flow",
                        )
                    with s6:
                        metric_card(
                            "Q4 − Q1 VALIDATION",
                            (
                                "—"
                                if pd.isna(strict_assessment["validation_q4_q1_spread"])
                                else f"{strict_assessment['validation_q4_q1_spread']:+.2%}"
                            ),
                            "Replication außerhalb Train",
                        )
                    with s7:
                        metric_card(
                            "REPLIZIERTE RICHTUNG",
                            "✓" if strict_assessment["replicated_direction"] else "✗",
                            "Spread + Spearman in beiden positiv",
                        )
                    with s8:
                        metric_card(
                            "STRICT VERDICT",
                            strict_assessment["verdict"],
                            "kein OOS verwendet",
                        )

                    verdict = strict_assessment["verdict"]
                    if verdict == "STRONG REPLICATED EFFECT":
                        st.success(
                            "STRONG REPLICATED EFFECT: Die Flow-Stärke ist in Train "
                            "und Validation vollständig geordnet und zeigt einen starken "
                            "positiven Rangzusammenhang."
                        )
                    elif verdict == "MODERATE REPLICATED EFFECT":
                        st.success(
                            "MODERATE REPLICATED EFFECT: Der positive Zusammenhang "
                            "repliziert, ist aber nicht in allen Quartilen perfekt geordnet."
                        )
                    elif verdict == "WEAK POSITIVE TREND · NOT MONOTONIC":
                        st.info(
                            "WEAK POSITIVE TREND · NOT MONOTONIC: Q4 schlägt Q1 in "
                            "Train und Validation, aber die Zwischenquartile sind nicht "
                            "sauber geordnet. Keine lineare 'mehr Flow = besser'-Regel ableiten."
                        )
                    else:
                        st.warning(
                            "NOT MONOTONIC: Der Flow-Effekt repliziert nicht ausreichend. "
                            "Ein hoher Scanner-Score allein genügt nicht."
                        )

                st.markdown("##### Pre-OOS Shortlist · unterschiedliche Hypothesen")
                redundancy = overlap_redundancy_summary(
                    dynamics_events,
                    robustness_scan,
                    top_n=6,
                    overlap_threshold=0.80,
                )
                shortlist = distinct_candidate_shortlist(
                    dynamics_events,
                    robustness_scan,
                    max_total=4,
                    overlap_threshold=0.80,
                )

                q1, q2, q3 = st.columns(3)
                with q1:
                    metric_card(
                        "TOP-FLOW-PAARE",
                        str(int(redundancy.get("pairs", 0))),
                        "paarweise verglichen",
                    )
                with q2:
                    metric_card(
                        "REDUNDANT ≥ 80%",
                        str(int(redundancy.get("redundant_pairs", 0))),
                        "Jaccard Event Overlap",
                    )
                with q3:
                    metric_card(
                        "MAX EVENT OVERLAP",
                        (
                            "—"
                            if pd.isna(redundancy.get("max_jaccard", np.nan))
                            else f"{redundancy['max_jaccard']:.0%}"
                        ),
                        "Train + Validation",
                    )

                if shortlist.empty:
                    st.info("Noch keine belastbare nicht-redundante Shortlist.")
                else:
                    shortlist_display = shortlist.copy()
                    shortlist_display["Parameter"] = shortlist_display.apply(
                        lambda r: (
                            f"{int(r['window_weeks'])}W · "
                            f"{r['threshold_upper']:.0f}/{r['threshold_lower']:.0f}"
                        ),
                        axis=1,
                    )
                    shortlist_display["Hypothese"] = shortlist_display.apply(
                        lambda r: (
                            "STATE ONLY"
                            if r["candidate_type"] == "STATE"
                            else flow_name_map.get(str(r["feature"]), str(r["feature"]))
                        ),
                        axis=1,
                    )

                    st.dataframe(
                        shortlist_display[
                            [
                                "shortlist_rank",
                                "Parameter",
                                "Hypothese",
                                "robustness_score",
                                "n_train",
                                "n_validation",
                                "neighbor_positive_share",
                                "max_overlap_with_selected_flow",
                                "shortlist_reason",
                            ]
                        ].rename(
                            columns={
                                "shortlist_rank": "Shortlist",
                                "robustness_score": "Robustness",
                                "n_train": "n Train",
                                "n_validation": "n Validation",
                                "neighbor_positive_share": "Nachbarschaft positiv",
                                "max_overlap_with_selected_flow": "Max Flow-Overlap",
                                "shortlist_reason": "Rolle",
                            }
                        ).style.format(
                            {
                                "Shortlist": "{:.0f}",
                                "Robustness": "{:.1f}",
                                "Nachbarschaft positiv": "{:.0%}",
                                "Max Flow-Overlap": "{:.0%}",
                            },
                            na_rep="—",
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.caption(
                        "Die Shortlist enthält maximal einen strukturellen State-Baseline-"
                        "Kandidaten plus Flow-Hypothesen mit weniger als 80% Jaccard-Overlap. "
                        "Diese Liste sollte vor dem OOS-Reveal eingefroren werden."
                    )

                st.caption(
                    "C.2 verändert weder Scanner-Ranking noch Produktionsparameter. "
                    "Es verschärft ausschließlich die Diagnose vor dem Locked-OOS-Test."
                )




                section_line(
                    "4B · Cross-Market Robustness",
                    "Repliziert dieselbe Hypothese über mehrere Kern-FX-Märkte?",
                )
                st.caption(
                    "Dieser Layer prüft Parameterdefinitionen über EUR · JPY · GBP · "
                    "CHF · CAD · AUD · NZD. Jeder Markt besitzt seinen eigenen "
                    "chronologischen Train/Validation/OOS-Split. Aggregiert werden "
                    "ausschließlich Train + Validation. Kein OOS fließt in diesen "
                    "Cross-Market Score ein."
                )

                if asset_class != "Currencies" or group_key != "dealer":
                    st.info(
                        "Cross-Market Robustness ist in V3.12C zunächst auf den "
                        "TFF-Dealer-Research der sieben Kern-FX-Märkte begrenzt."
                    )
                else:
                    selected_fx_markets = st.multiselect(
                        "FX-Märkte im Robustness-Test",
                        options=list(CORE_FX_RESEARCH_MARKETS),
                        default=list(CORE_FX_RESEARCH_MARKETS),
                        format_func=lambda x: MARKET_NAME_DE.get(x, x),
                        key=(
                            f"v312c_fx_markets|{group_key}|{basis}|"
                            f"{int(dyn_horizon)}"
                        ),
                    )

                    run_cross_market = st.button(
                        "Core-FX Robustness berechnen",
                        use_container_width=True,
                        key=(
                            f"v312c_run|{group_key}|{basis}|"
                            f"{int(dyn_horizon)}"
                        ),
                        disabled=len(selected_fx_markets) < 3,
                    )

                    cross_result_key = (
                        f"v312c_result|{group_key}|{basis}|"
                        f"{int(dyn_horizon)}|"
                        f"{'|'.join(sorted(selected_fx_markets))}"
                    )

                    if run_cross_market:
                        scans_by_market = {}
                        events_by_market = {}
                        cross_errors = {}

                        progress = st.progress(
                            0.0,
                            text="Core-FX-Märkte werden geprüft …",
                        )
                        total_fx = max(1, len(selected_fx_markets))

                        for idx, fx_market in enumerate(selected_fx_markets):
                            try:
                                (
                                    market_scan,
                                    _market_meta,
                                    market_events,
                                ) = _cross_market_scan_one(
                                    fx_market,
                                    group_key,
                                    basis,
                                    int(dyn_horizon),
                                )
                                if market_scan is not None and not market_scan.empty:
                                    scans_by_market[fx_market] = market_scan
                                    events_by_market[fx_market] = market_events
                                else:
                                    cross_errors[fx_market] = "keine Scanner-Kandidaten"
                            except Exception as exc:
                                cross_errors[fx_market] = str(exc)

                            progress.progress(
                                (idx + 1) / total_fx,
                                text=(
                                    f"{MARKET_NAME_DE.get(fx_market, fx_market)} "
                                    f"· {idx + 1}/{total_fx}"
                                ),
                            )

                        progress.empty()

                        cross_scan = aggregate_cross_market_scans(
                            scans_by_market,
                            min_markets=max(
                                3,
                                min(4, len(scans_by_market)),
                            ),
                        )
                        st.session_state[cross_result_key] = {
                            "scan": cross_scan,
                            "scans_by_market": scans_by_market,
                            "events_by_market": events_by_market,
                            "errors": cross_errors,
                        }

                    cross_payload = st.session_state.get(cross_result_key)

                    if cross_payload:
                        cross_scan = cross_payload.get("scan", pd.DataFrame())
                        scans_by_market = cross_payload.get(
                            "scans_by_market",
                            {},
                        )
                        events_by_market = cross_payload.get(
                            "events_by_market",
                            {},
                        )
                        cross_errors = cross_payload.get("errors", {})

                        if cross_errors:
                            with st.expander(
                                "Datenhinweise · nicht geladene Märkte",
                                expanded=False,
                            ):
                                for error_market, error_text in cross_errors.items():
                                    st.caption(
                                        f"{MARKET_NAME_DE.get(error_market, error_market)}: "
                                        f"{error_text}"
                                    )

                        if cross_scan is None or cross_scan.empty:
                            st.warning(
                                "Für die gewählten Märkte konnte noch keine "
                                "gemeinsame robuste Kandidatenmenge gebildet werden."
                            )
                        else:
                            cross_findings = cross_market_findings(cross_scan)
                            top_cross_state = cross_findings.get("top_state")
                            top_cross_flow = cross_findings.get("top_flow")

                            def _cross_candidate_text(row):
                                if not row:
                                    return "—"
                                base = (
                                    f"{int(row['window_weeks'])}W · "
                                    f"{row['threshold_upper']:.0f}/"
                                    f"{row['threshold_lower']:.0f}"
                                )
                                if row["candidate_type"] == "STATE":
                                    return base
                                return (
                                    f"{base} · "
                                    f"{flow_name_map.get(str(row['feature']), str(row['feature']))}"
                                )

                            cm1, cm2, cm3, cm4 = st.columns(4)
                            with cm1:
                                metric_card(
                                    "MÄRKTE GELADEN",
                                    str(len(scans_by_market)),
                                    f"von {len(selected_fx_markets)} gewählt",
                                )
                            with cm2:
                                metric_card(
                                    "CROSS-MARKET ROBUST",
                                    str(int(cross_findings.get("robust_count", 0))),
                                    "breit replizierte Kandidaten",
                                )
                            with cm3:
                                metric_card(
                                    "TOP STATE",
                                    _cross_candidate_text(top_cross_state),
                                    (
                                        "—"
                                        if not top_cross_state
                                        else (
                                            f"Score "
                                            f"{top_cross_state['cross_market_score']:.1f}/100"
                                        )
                                    ),
                                )
                            with cm4:
                                metric_card(
                                    "TOP FLOW",
                                    _cross_candidate_text(top_cross_flow),
                                    (
                                        "—"
                                        if not top_cross_flow
                                        else (
                                            f"Score "
                                            f"{top_cross_flow['cross_market_score']:.1f}/100"
                                        )
                                    ),
                                )

                            eligible_cross = cross_scan[
                                cross_scan["cross_market_rank"].notna()
                            ].sort_values("cross_market_rank").head(30).copy()

                            eligible_cross["Parameter"] = eligible_cross.apply(
                                lambda r: (
                                    f"{int(r['window_weeks'])}W · "
                                    f"{r['threshold_upper']:.0f}/"
                                    f"{r['threshold_lower']:.0f}"
                                ),
                                axis=1,
                            )
                            eligible_cross["Hypothese"] = eligible_cross.apply(
                                lambda r: (
                                    "STATE ONLY"
                                    if r["candidate_type"] == "STATE"
                                    else flow_name_map.get(
                                        str(r["feature"]),
                                        str(r["feature"]),
                                    )
                                ),
                                axis=1,
                            )

                            st.markdown("### Cross-Market Ranking")
                            st.dataframe(
                                eligible_cross[
                                    [
                                        "cross_market_rank",
                                        "Parameter",
                                        "Hypothese",
                                        "markets_eligible",
                                        "positive_validation_share",
                                        "train_validation_positive_share",
                                        "median_validation_return",
                                        "median_validation_hit_rate",
                                        "median_single_market_robustness",
                                        "cross_market_score",
                                        "cross_market_status",
                                    ]
                                ].rename(
                                    columns={
                                        "cross_market_rank": "Rang",
                                        "markets_eligible": "Märkte",
                                        "positive_validation_share": "Val positiv",
                                        "train_validation_positive_share": "Train+Val positiv",
                                        "median_validation_return": "Median Val Return",
                                        "median_validation_hit_rate": "Median Val Hit",
                                        "median_single_market_robustness": "Median Single-Market Robustness",
                                        "cross_market_score": "Cross-Market Score",
                                        "cross_market_status": "Status",
                                    }
                                ).style.format(
                                    {
                                        "Rang": "{:.0f}",
                                        "Val positiv": "{:.0%}",
                                        "Train+Val positiv": "{:.0%}",
                                        "Median Val Return": "{:+.2%}",
                                        "Median Val Hit": "{:.1%}",
                                        "Median Single-Market Robustness": "{:.1f}",
                                        "Cross-Market Score": "{:.1f}",
                                    },
                                    na_rep="—",
                                ),
                                use_container_width=True,
                                hide_index=True,
                            )

                            detail_indices = list(eligible_cross.index[:15])
                            if detail_indices:
                                chosen_cross_idx = st.selectbox(
                                    "Kandidat marktweise prüfen",
                                    options=detail_indices,
                                    format_func=lambda idx: (
                                        f"Rang "
                                        f"{int(cross_scan.loc[idx, 'cross_market_rank'])} · "
                                        f"{int(cross_scan.loc[idx, 'window_weeks'])}W "
                                        f"{cross_scan.loc[idx, 'threshold_upper']:.0f}/"
                                        f"{cross_scan.loc[idx, 'threshold_lower']:.0f} · "
                                        f"{'STATE ONLY' if cross_scan.loc[idx, 'candidate_type'] == 'STATE' else flow_name_map.get(str(cross_scan.loc[idx, 'feature']), str(cross_scan.loc[idx, 'feature']))}"
                                    ),
                                    key=(
                                        f"v312c_detail|{group_key}|{basis}|"
                                        f"{int(dyn_horizon)}"
                                    ),
                                )
                                chosen_cross = cross_scan.loc[chosen_cross_idx]
                                market_detail = cross_market_candidate_detail(
                                    scans_by_market,
                                    chosen_cross,
                                )

                                st.markdown("### Marktweise Replikation")
                                st.dataframe(
                                    market_detail.rename(
                                        columns={
                                            "market_name": "Markt",
                                            "n_train": "n Train",
                                            "train_median": "Train Median",
                                            "train_hit_rate": "Train Hit",
                                            "n_validation": "n Validation",
                                            "validation_median": "Validation Median",
                                            "validation_hit_rate": "Validation Hit",
                                            "neighbor_positive_share": "Nachbarschaft positiv",
                                            "robustness_score": "Single-Market Robustness",
                                            "status": "Single-Market Status",
                                        }
                                    ).style.format(
                                        {
                                            "Train Median": "{:+.2%}",
                                            "Train Hit": "{:.1%}",
                                            "Validation Median": "{:+.2%}",
                                            "Validation Hit": "{:.1%}",
                                            "Nachbarschaft positiv": "{:.0%}",
                                            "Single-Market Robustness": "{:.1f}",
                                        },
                                        na_rep="—",
                                    ),
                                    use_container_width=True,
                                    hide_index=True,
                                )


                            section_line(
                                "4C · Cross-Market Diagnostics",
                                "Redundanz · Coverage · Leave-One-Market-Out · Parameter Neighborhood",
                            )
                            st.caption(
                                "Dieser Block härtet die Cross-Market-Hypothese vor OOS. "
                                "Er verwendet ausschließlich TRAIN+VALIDATION und die pro "
                                "Markt im TRAIN eingefrorenen Flow-Cutoffs."
                            )

                            coverage_scan = cross_market_coverage_diagnostic(
                                cross_scan
                            )
                            coverage_match = coverage_scan.loc[
                                coverage_scan.index == chosen_cross_idx
                            ]
                            if coverage_match.empty:
                                coverage_match = coverage_scan.loc[
                                    (
                                        coverage_scan["candidate_type"].astype(str)
                                        == str(chosen_cross["candidate_type"])
                                    )
                                    & (
                                        coverage_scan["window_weeks"]
                                        == chosen_cross["window_weeks"]
                                    )
                                    & (
                                        coverage_scan["threshold_upper"]
                                        == chosen_cross["threshold_upper"]
                                    )
                                    & (
                                        coverage_scan["feature"].astype(str)
                                        == str(chosen_cross["feature"])
                                    )
                                ]

                            if not coverage_match.empty:
                                coverage_row = coverage_match.iloc[0]
                                st.markdown(
                                    "### Coverage · positiv / eligible / total"
                                )
                                cv1, cv2, cv3 = st.columns(3)
                                with cv1:
                                    metric_card(
                                        "VALIDATION POSITIV",
                                        (
                                            f"{int(coverage_row['positive_validation_markets'])}"
                                            f" / {int(coverage_row['markets_eligible'])}"
                                        ),
                                        "nur Märkte mit ausreichendem Sample",
                                    )
                                with cv2:
                                    metric_card(
                                        "POSITIV / GESAMT",
                                        (
                                            f"{coverage_row['positive_of_total_share']:.0%}"
                                        ),
                                        str(coverage_row["coverage_text"]),
                                    )
                                with cv3:
                                    metric_card(
                                        "NICHT AUSREICHEND",
                                        str(
                                            int(
                                                coverage_row[
                                                    "markets_insufficient"
                                                ]
                                            )
                                        ),
                                        "nicht als negativ interpretieren",
                                    )

                            st.markdown("### Leave-One-Market-Out")
                            lomo = cross_market_leave_one_out(
                                scans_by_market,
                                chosen_cross,
                                min_markets=max(
                                    3,
                                    min(4, len(scans_by_market) - 1),
                                ),
                            )
                            lomo_summary = leave_one_out_summary(lomo)

                            lm1, lm2, lm3 = st.columns(3)
                            with lm1:
                                metric_card(
                                    "WORST SCORE",
                                    (
                                        "—"
                                        if not np.isfinite(
                                            lomo_summary["worst_score"]
                                        )
                                        else f"{lomo_summary['worst_score']:.1f}"
                                    ),
                                    "schlechtester Leave-One-Out Lauf",
                                )
                            with lm2:
                                metric_card(
                                    "MAX SCORE-ÄNDERUNG",
                                    (
                                        "—"
                                        if not np.isfinite(
                                            lomo_summary["max_abs_delta"]
                                        )
                                        else f"{lomo_summary['max_abs_delta']:.1f}"
                                    ),
                                    "Abhängigkeit von einem Einzelmarkt",
                                )
                            with lm3:
                                metric_card(
                                    "LOMO VERDICT",
                                    (
                                        "STABIL"
                                        if lomo_summary["stable"]
                                        else "NICHT STABIL"
                                    ),
                                    "Pre-OOS Diagnose",
                                )

                            if not lomo.empty:
                                st.dataframe(
                                    lomo.rename(
                                        columns={
                                            "omitted_market": "Markt entfernt",
                                            "markets_eligible": "Märkte eligible",
                                            "positive_validation_share": "Val positiv",
                                            "train_validation_positive_share": "Train+Val positiv",
                                            "cross_market_score": "Score",
                                            "score_delta": "Δ Score",
                                            "cross_market_status": "Status",
                                        }
                                    ).style.format(
                                        {
                                            "Val positiv": "{:.0%}",
                                            "Train+Val positiv": "{:.0%}",
                                            "Score": "{:.1f}",
                                            "Δ Score": "{:+.1f}",
                                        },
                                        na_rep="—",
                                    ),
                                    use_container_width=True,
                                    hide_index=True,
                                )

                            st.markdown("### Parameter Neighborhood")
                            cm_neighborhood = cross_market_parameter_neighborhood(
                                cross_scan,
                                chosen_cross,
                            )
                            cm_neighbor_summary = (
                                cross_market_neighborhood_summary(
                                    cm_neighborhood
                                )
                            )

                            pn1, pn2, pn3 = st.columns(3)
                            with pn1:
                                metric_card(
                                    "DIREKTE NACHBARN",
                                    str(
                                        cm_neighbor_summary[
                                            "neighbor_count"
                                        ]
                                    ),
                                    "Window / Threshold",
                                )
                            with pn2:
                                metric_card(
                                    "NACHBARN POSITIV",
                                    (
                                        "—"
                                        if not np.isfinite(
                                            cm_neighbor_summary[
                                                "positive_neighbor_share"
                                            ]
                                        )
                                        else (
                                            f"{cm_neighbor_summary['positive_neighbor_share']:.0%}"
                                        )
                                    ),
                                    "≥ 60% Validation-Märkte positiv",
                                )
                            with pn3:
                                metric_card(
                                    "REGION",
                                    (
                                        "STABIL"
                                        if cm_neighbor_summary[
                                            "stable_region"
                                        ]
                                        else "PUNKT / INSTABIL"
                                    ),
                                    "keine magische Einzelzelle bevorzugen",
                                )

                            if not cm_neighborhood.empty:
                                show_neighbor = cm_neighborhood.copy()
                                show_neighbor["Parameter"] = (
                                    show_neighbor.apply(
                                        lambda r: (
                                            f"{int(r['window_weeks'])}W · "
                                            f"{r['threshold_upper']:.0f}/"
                                            f"{r['threshold_lower']:.0f}"
                                        ),
                                        axis=1,
                                    )
                                )
                                st.dataframe(
                                    show_neighbor[
                                        [
                                            "neighbor_role",
                                            "Parameter",
                                            "markets_eligible",
                                            "positive_validation_share",
                                            "train_validation_positive_share",
                                            "median_validation_return",
                                            "cross_market_score",
                                            "cross_market_status",
                                        ]
                                    ].rename(
                                        columns={
                                            "neighbor_role": "Rolle",
                                            "markets_eligible": "Märkte",
                                            "positive_validation_share": "Val positiv",
                                            "train_validation_positive_share": "Train+Val positiv",
                                            "median_validation_return": "Median Val Return",
                                            "cross_market_score": "Score",
                                            "cross_market_status": "Status",
                                        }
                                    ).style.format(
                                        {
                                            "Val positiv": "{:.0%}",
                                            "Train+Val positiv": "{:.0%}",
                                            "Median Val Return": "{:+.2%}",
                                            "Score": "{:.1f}",
                                        },
                                        na_rep="—",
                                    ),
                                    use_container_width=True,
                                    hide_index=True,
                                )

                            st.markdown("### Flow Redundancy")
                            redundancy = cross_market_flow_redundancy(
                                events_by_market,
                                scans_by_market,
                                cross_scan,
                                top_n=8,
                                redundancy_threshold=0.80,
                            )

                            if redundancy.empty:
                                st.caption(
                                    "Für die aktuellen Top-Flow-Hypothesen konnte "
                                    "noch keine marktübergreifende Event-Redundanz "
                                    "berechnet werden."
                                )
                            else:
                                redundant_count = int(
                                    redundancy["redundant"].sum()
                                )
                                rd1, rd2, rd3 = st.columns(3)
                                with rd1:
                                    metric_card(
                                        "FLOW-PAARE",
                                        str(len(redundancy)),
                                        "Top-Hypothesen paarweise",
                                    )
                                with rd2:
                                    metric_card(
                                        "REDUNDANT ≥ 80%",
                                        str(redundant_count),
                                        "Median Jaccard über Märkte",
                                    )
                                with rd3:
                                    metric_card(
                                        "MAX MEDIAN OVERLAP",
                                        (
                                            f"{redundancy['median_jaccard'].max():.0%}"
                                        ),
                                        "TRAIN+VALIDATION Events",
                                    )

                                redundancy_display = redundancy.head(15).copy()
                                redundancy_display["Kandidat A"] = (
                                    redundancy_display.apply(
                                        lambda r: (
                                            f"R{int(r['rank_a'])} · "
                                            f"{int(r['window_a'])}W "
                                            f"{r['threshold_a']:.0f}/"
                                            f"{100-r['threshold_a']:.0f} · "
                                            f"{flow_name_map.get(str(r['feature_a']), str(r['feature_a']))}"
                                        ),
                                        axis=1,
                                    )
                                )
                                redundancy_display["Kandidat B"] = (
                                    redundancy_display.apply(
                                        lambda r: (
                                            f"R{int(r['rank_b'])} · "
                                            f"{int(r['window_b'])}W "
                                            f"{r['threshold_b']:.0f}/"
                                            f"{100-r['threshold_b']:.0f} · "
                                            f"{flow_name_map.get(str(r['feature_b']), str(r['feature_b']))}"
                                        ),
                                        axis=1,
                                    )
                                )
                                st.dataframe(
                                    redundancy_display[
                                        [
                                            "Kandidat A",
                                            "Kandidat B",
                                            "markets_compared",
                                            "median_jaccard",
                                            "max_jaccard",
                                            "interpretation",
                                        ]
                                    ].rename(
                                        columns={
                                            "markets_compared": "Märkte",
                                            "median_jaccard": "Median Jaccard",
                                            "max_jaccard": "Max Jaccard",
                                            "interpretation": "Verdict",
                                        }
                                    ).style.format(
                                        {
                                            "Median Jaccard": "{:.0%}",
                                            "Max Jaccard": "{:.0%}",
                                        },
                                        na_rep="—",
                                    ),
                                    use_container_width=True,
                                    hide_index=True,
                                )

                                st.caption(
                                    "Hoher Jaccard bedeutet: Zwei Flow-Definitionen "
                                    "selektieren über mehrere Märkte weitgehend dieselben "
                                    "Release-Episoden. Solche Kandidaten zählen nicht als "
                                    "zwei unabhängige Bestätigungen."
                                )


                            section_line(
                                "4D · Pre-OOS Decision Gate",
                                "Feste Regeln · PASS / HOLD / REJECT · keine Nachoptimierung",
                            )
                            st.caption(
                                "Kein neuer Parameter wird hier gesucht. Der bereits "
                                "gewählte Cross-Market-Kandidat wird nur gegen vorab "
                                "festgelegte Kriterien geprüft. OOS bleibt geschlossen."
                            )

                            core_universe_complete = (
                                set(selected_fx_markets)
                                == set(CORE_FX_RESEARCH_MARKETS)
                            )

                            gu1, gu2, gu3, gu4 = st.columns(4)
                            with gu1:
                                metric_card(
                                    "CORE-FX UNIVERSE",
                                    str(len(CORE_FX_RESEARCH_MARKETS)),
                                    "vorab definiert",
                                )
                            with gu2:
                                metric_card(
                                    "AUSGEWÄHLT",
                                    str(len(selected_fx_markets)),
                                    (
                                        "VOLLSTÄNDIG"
                                        if core_universe_complete
                                        else "UNVOLLSTÄNDIG"
                                    ),
                                )
                            with gu3:
                                metric_card(
                                    "GELADEN",
                                    str(len(scans_by_market)),
                                    (
                                        f"{max(0, len(selected_fx_markets) - len(scans_by_market))} "
                                        "fehlend / fehlgeschlagen"
                                    ),
                                )
                            with gu4:
                                metric_card(
                                    "ELIGIBLE",
                                    str(int(chosen_cross["markets_eligible"])),
                                    (
                                        f"{int(chosen_cross['positive_validation_markets'])} "
                                        "Validation positiv"
                                    ),
                                )

                            if not core_universe_complete:
                                st.warning(
                                    "Für einen Pre-OOS PASS müssen alle sieben "
                                    "vorab definierten Core-FX-Märkte ausgewählt "
                                    "bleiben. Märkte mit schwachem oder unzureichendem "
                                    "Ergebnis dürfen nicht nachträglich aus dem "
                                    "Universum entfernt werden."
                                )

                            st.markdown("### Fixed 3×3 Parameter Region")
                            st.caption(
                                "Ausschließlich die bereits vorgegebenen Zellen "
                                "104/156/208W × 70/75/80 werden betrachtet. Es werden "
                                "keine Zwischenwerte wie 74/26 oder 76/24 erzeugt."
                            )

                            fixed_region = fixed_parameter_region_matrix(
                                cross_scan,
                                chosen_cross,
                                windows=(104, 156, 208),
                                thresholds=(70.0, 75.0, 80.0),
                            )

                            if not fixed_region.empty:
                                score_matrix = (
                                    fixed_region.pivot(
                                        index="window_weeks",
                                        columns="threshold_upper",
                                        values="cross_market_score",
                                    )
                                    .reindex(index=[104, 156, 208])
                                    .reindex(columns=[70.0, 75.0, 80.0])
                                )
                                score_matrix.index = [
                                    f"{int(x)}W"
                                    for x in score_matrix.index
                                ]
                                score_matrix.columns = [
                                    f"{int(x)}/{int(100-x)}"
                                    for x in score_matrix.columns
                                ]

                                st.dataframe(
                                    score_matrix.style.format(
                                        "{:.1f}",
                                        na_rep="—",
                                    ),
                                    use_container_width=True,
                                )

                                with st.expander(
                                    "3×3 Details · Replikation & Status",
                                    expanded=False,
                                ):
                                    st.dataframe(
                                        fixed_region[
                                            [
                                                "window_weeks",
                                                "threshold_upper",
                                                "markets_eligible",
                                                "positive_validation_share",
                                                "train_validation_positive_share",
                                                "median_validation_return",
                                                "cross_market_score",
                                                "cross_market_status",
                                            ]
                                        ].rename(
                                            columns={
                                                "window_weeks": "Window",
                                                "threshold_upper": "Threshold",
                                                "markets_eligible": "Eligible",
                                                "positive_validation_share": "Val positiv",
                                                "train_validation_positive_share": "Train+Val positiv",
                                                "median_validation_return": "Median Val Return",
                                                "cross_market_score": "Score",
                                                "cross_market_status": "Status",
                                            }
                                        ).style.format(
                                            {
                                                "Window": "{:.0f}W",
                                                "Threshold": "{:.0f}",
                                                "Val positiv": "{:.0%}",
                                                "Train+Val positiv": "{:.0%}",
                                                "Median Val Return": "{:+.2%}",
                                                "Score": "{:.1f}",
                                            },
                                            na_rep="—",
                                        ),
                                        use_container_width=True,
                                        hide_index=True,
                                    )

                            overlap_summary = candidate_flow_overlap(
                                redundancy,
                                chosen_cross.get("cross_market_rank"),
                            )

                            gate = evaluate_pre_oos_decision_gate(
                                chosen_cross,
                                selected_markets_total=len(
                                    selected_fx_markets
                                ),
                                loaded_markets_total=len(scans_by_market),
                                lomo_summary=lomo_summary,
                                neighborhood_summary=cm_neighbor_summary,
                                max_median_jaccard=overlap_summary[
                                    "max_median_jaccard"
                                ],
                                core_universe_size=len(
                                    CORE_FX_RESEARCH_MARKETS
                                ),
                            )

                            verdict = gate["verdict"]

                            gv1, gv2, gv3, gv4 = st.columns(4)
                            with gv1:
                                metric_card(
                                    "PRE-OOS VERDICT",
                                    verdict,
                                    "kein Produktionssignal",
                                )
                            with gv2:
                                metric_card(
                                    "PASS",
                                    str(gate["pass_count"]),
                                    "Kriterien erfüllt",
                                )
                            with gv3:
                                metric_card(
                                    "WATCH",
                                    str(gate["watch_count"]),
                                    "vor Freeze klären",
                                )
                            with gv4:
                                metric_card(
                                    "FAIL",
                                    str(gate["fail_count"]),
                                    "harte / weiche Schwäche",
                                )

                            gate_display = gate["criteria"].rename(
                                columns={
                                    "criterion": "Kriterium",
                                    "status": "Status",
                                    "value": "Aktueller Wert",
                                    "rule": "Feste Regel",
                                }
                            )
                            st.dataframe(
                                gate_display,
                                use_container_width=True,
                                hide_index=True,
                            )

                            if verdict == "PASS":
                                st.success(
                                    "PRE-OOS PASS: Der Kandidat erfüllt die "
                                    "festgelegten Pre-OOS-Kriterien. Das ist noch "
                                    "keine Produktionsfreigabe; erst jetzt wäre ein "
                                    "Freeze methodisch vertretbar."
                                )
                            elif verdict == "HOLD":
                                st.warning(
                                    "PRE-OOS HOLD: Kein OOS öffnen. Der Kandidat "
                                    "hat relevante Evidenz, erfüllt aber mindestens "
                                    "ein Pre-OOS-Kriterium noch nicht sauber. Keine "
                                    "Parameter nachoptimieren."
                                )
                            else:
                                st.error(
                                    "PRE-OOS REJECT: Mindestens ein Kernkriterium "
                                    "scheitert. Dieser Kandidat sollte in dieser "
                                    "Research-Runde nicht ins OOS gelangen."
                                )

                            st.caption(
                                "Interpretation: Gesucht wird keine magische Einzelzelle, "
                                "sondern eine Definition, die in möglichst vielen Märkten "
                                "mit ausreichendem Sample in Train UND Validation dieselbe "
                                "Richtung zeigt. Der Cross-Market Score verwendet bewusst "
                                "kein OOS und bevorzugt Breite vor maximalem Einzelmarkt-Return."
                            )

                # Legacy test marker: Reviewed Shortlist · manuelle Bestätigung
                section_line(
                    "5 · Reviewed Hypotheses",
                    "Welche Research-Hypothesen werden tatsächlich in den OOS-Test übernommen?",
                )
                st.caption(
                    "Die automatische Shortlist ist nur ein Vorschlag. Vor OOS "
                    "werden die Hypothesen bewusst ausgewählt und erhalten damit "
                    "einen dokumentierten Research-Status."
                )
                st.caption(
                    "Nicht ausgewählte Kandidaten gelten für diesen OOS-Test als "
                    "vor OOS verworfen und dürfen später nicht aufgrund ihres OOS-"
                    "Ergebnisses nachträglich aufgenommen werden."
                )

                shortlist_option_ids = []
                shortlist_label_map = {}
                for _, shortlist_row in shortlist.iterrows():
                    option_id = candidate_freeze_id(shortlist_row)
                    shortlist_option_ids.append(option_id)
                    shortlist_label_map[option_id] = candidate_review_label(shortlist_row)

                review_state_key = (
                    f"v311c4_reviewed_ids|{research_context_key}"
                )

                default_review_ids = shortlist_option_ids
                selected_review_ids = st.multiselect(
                    "Research-Hypothesen für OOS auswählen",
                    options=shortlist_option_ids,
                    default=st.session_state.get(
                        review_state_key,
                        default_review_ids,
                    ),
                    format_func=lambda candidate_id: shortlist_label_map.get(
                        candidate_id,
                        candidate_id,
                    ),
                    key=f"{review_state_key}|widget",
                )
                st.session_state[review_state_key] = list(selected_review_ids)

                reviewed_freeze_shortlist = reviewed_shortlist(
                    shortlist,
                    selected_review_ids,
                )

                if reviewed_freeze_shortlist.empty:
                    st.warning(
                        "Mindestens eine Research-Hypothese muss ausgewählt werden."
                    )
                else:
                    reviewed_display = reviewed_freeze_shortlist.copy()
                    reviewed_display["Hypothese"] = reviewed_display.apply(
                        candidate_review_label,
                        axis=1,
                    )
                    st.dataframe(
                        reviewed_display[
                            [
                                "shortlist_rank",
                                "Hypothese",
                                "n_train",
                                "n_validation",
                                "robustness_score",
                                "shortlist_reason",
                            ]
                        ].rename(
                            columns={
                                "shortlist_rank": "Auto-Rang",
                                "n_train": "n Train",
                                "n_validation": "n Validation",
                                "robustness_score": "Robustness",
                                "shortlist_reason": "Rolle",
                            }
                        ).style.format(
                            {
                                "Auto-Rang": "{:.0f}",
                                "Robustness": "{:.1f}",
                            },
                            na_rep="—",
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                reviewed_signature = "|".join(
                    sorted(str(x) for x in selected_review_ids)
                )
                # Legacy test marker: Pre-OOS Freeze Gate
                section_line(
                    "6 · Frozen OOS",
                    "Hypothesen dokumentieren → Freeze → ausschließlich Frozen-Only OOS",
                )
                st.caption(
                    "Freeze bedeutet nur: Die vor OOS gewählten Research-Hypothesen "
                    "werden unveränderlich dokumentiert. Die Produktionslogik bleibt "
                    "weiterhin unangetastet."
                )

                freeze_key = (
                    f"{research_context_key}|{reviewed_signature}"
                )
                freeze_state_key = "v311c3_frozen_snapshot"
                freeze_context_key = "v311c3_frozen_context_key"

                current_freeze = st.session_state.get(freeze_state_key)
                freeze_matches_current = bool(
                    current_freeze
                    and st.session_state.get(freeze_context_key) == freeze_key
                )

                if st.button(
                    "Shortlist jetzt einfrieren",
                    type="primary",
                    use_container_width=True,
                    key="v311c3_freeze_button",
                    disabled=reviewed_freeze_shortlist.empty,
                ):
                    snapshot = build_pre_oos_freeze_snapshot(
                        reviewed_freeze_shortlist,
                        market_name=market_name,
                        group_key=group_key,
                        basis=basis,
                        horizon_weeks=int(dyn_horizon),
                    )
                    st.session_state[freeze_state_key] = snapshot
                    st.session_state[freeze_context_key] = freeze_key
                    current_freeze = snapshot
                    freeze_matches_current = True

                previous_freeze = st.session_state.get(freeze_state_key)
                previous_context = st.session_state.get(freeze_context_key)
                if previous_freeze and previous_context != freeze_key:
                    st.warning(
                        "Auswahl geändert: Ein früherer Freeze passt nicht mehr zur "
                        "aktuellen Reviewed Shortlist und muss vor OOS erneut eingefroren werden."
                    )

                if freeze_matches_current:
                    st.success(
                        "Research-Shortlist eingefroren. OOS darf jetzt ausschließlich "
                        "für diese unveränderte Hypothesenliste betrachtet werden."
                    )
                    st.code(
                        current_freeze["freeze_hash_sha256"],
                        language=None,
                    )
                    st.download_button(
                        "Frozen Pre-OOS Snapshot herunterladen",
                        data=freeze_snapshot_json(current_freeze),
                        file_name=(
                            f"pre_oos_freeze_"
                            f"{market_name.replace(' ', '_')}_"
                            f"{group_key}_{basis}_{int(dyn_horizon)}W.json"
                        ),
                        mime="application/json",
                        use_container_width=True,
                        key="v311c3_freeze_download",
                    )
                else:
                    st.warning(
                        "OOS bleibt gesperrt. Die Shortlist ist noch NICHT eingefroren."
                    )
                st.markdown("#### Was der Score belohnt")
                st.markdown(
                    """
                    - **Train positiv**, aber mit geringerem Gewicht als Validation.
                    - **Validation positiv** und ähnliche Effektgröße wie im Train.
                    - **ausreichende Fallzahl** in beiden Entwicklungssegmenten.
                    - **Parameter-Nachbarschaft**: angrenzende Lookbacks/Thresholds sollen
                      ebenfalls positiv sein. Ein isolierter historischer Peak wird bestraft.
                    - **Kein OOS-Anteil**: OOS beeinflusst weder Rang noch Robustness Score.
                    """
                )

                st.caption(
                    "Flow-Cutoffs werden ausschließlich aus dem Train-Segment geschätzt "
                    "und danach unverändert auf Validation/OOS angewendet. Dadurch kann "
                    "spätere Historie die Quantil-Grenze nicht rückwirkend optimieren."
                )

                current_freeze = st.session_state.get("v311c3_frozen_snapshot")
                freeze_key = f"{research_context_key}|{reviewed_signature}"
                current_freeze_ok = bool(
                    current_freeze
                    and st.session_state.get("v311c3_frozen_context_key") == freeze_key
                )

                if not current_freeze_ok:
                    st.info(
                        "OOS REVEAL GESPERRT · Zuerst die aktuelle Pre-OOS-Shortlist "
                        "über den Freeze Gate einfrieren."
                    )
                else:
                    with st.expander(
                        "Frozen OOS Reveal",
                        expanded=False,
                    ):
                        st.warning(
                            "OOS wird nicht für Ranking oder Score verwendet. Nach dem Öffnen "
                            "sollten Parameter nicht anhand dieses Ergebnisses nachjustiert werden; "
                            "sonst ist dieses Segment für die nächste Iteration nicht mehr wirklich locked."
                        )

                        st.markdown("##### FROZEN-ONLY OOS")
                        st.caption(
                            "Nur die vor OOS eingefrorenen Hypothesen werden angezeigt. "
                            "Nicht ausgewählte Scanner-Kandidaten bleiben unsichtbar, selbst "
                            "wenn ihr OOS-Ergebnis besser wäre."
                        )

                        oos_display = frozen_candidates_from_scan(
                            robustness_scan,
                            current_freeze,
                        ).copy()

                        if oos_display.empty:
                            st.warning(
                                "Die eingefrorenen Kandidaten konnten im aktuellen Scanner "
                                "nicht eindeutig rekonstruiert werden. OOS wird nicht angezeigt."
                            )
                        else:
                            oos_display["Parameter"] = oos_display.apply(
                                lambda r: (
                                    f"{int(r['window_weeks'])}W · "
                                    f"{r['threshold_upper']:.0f}/{r['threshold_lower']:.0f}"
                                ),
                                axis=1,
                            )
                            oos_display["Flow"] = oos_display.apply(
                                lambda r: (
                                    "STATE ONLY"
                                    if r["candidate_type"] == "STATE"
                                    else flow_name_map.get(
                                        str(r["feature"]),
                                        str(r["feature"]),
                                    )
                                ),
                                axis=1,
                            )

                            st.dataframe(
                                oos_display[
                                    [
                                        "rank_train_validation",
                                        "Parameter",
                                        "Flow",
                                        "robustness_score",
                                        "n_oos",
                                        "oos_median",
                                        "oos_hit_rate",
                                        "oos_status",
                                    ]
                                ].rename(
                                    columns={
                                        "rank_train_validation": "Train/Val Rang",
                                        "robustness_score": "Robustness",
                                        "n_oos": "n OOS",
                                        "oos_median": "OOS Median",
                                        "oos_hit_rate": "OOS Hit Rate",
                                        "oos_status": "OOS Status",
                                    }
                                ).style.format(
                                    {
                                        "Train/Val Rang": "{:.0f}",
                                        "Robustness": "{:.1f}",
                                        "OOS Median": "{:+.2%}",
                                        "OOS Hit Rate": "{:.1%}",
                                    },
                                    na_rep="—",
                                ),
                                use_container_width=True,
                                hide_index=True,
                            )

                st.caption(
                    "V3.11C ist weiterhin ein Single-Market-Scanner. Ein Kandidat wird "
                    "dadurch noch nicht produktionsreif: Markt-Cluster-/Universumsrobustheit "
                    "und Cross-Group Confirmation Cost folgen separat."
                )

    with st.expander(
        "Methodik · Scope, offene Fragen & Export",
        expanded=False,
    ):
        st.markdown("### Welche offenen Fragen beantwortet Positioning Dynamics bereits?")
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


with st.expander(
    "Archiv · Legacy Research",
    expanded=False,
):
    st.caption(
        "26W/52W, Release Decay, Nullmodell und Spec-Flow/Divergenz bleiben "
        "für Reproduzierbarkeit im Code erhalten, gehören aber nicht mehr zum "
        "primären Positioning-Dynamics-Workflow."
    )
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "26W vs. 52W",
            "Release Decay",
            "Nullmodell",
            "Spec-Flow & Divergenz",
        ]
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
