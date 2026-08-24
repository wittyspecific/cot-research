from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.fx_relative_cot_analog import FX_PAIRS
from src.markets import CLASSIC_MARKETS
from src.prices import load_prices
from src.ui.seasonality_path_chart import render_seasonal_path_chart
from src.research_panel_v1 import (
    CotPositioningState,
    MacroRegimeState,
    SeasonalTurnState,
    cot_state_for_market,
    derive_trade_opportunity,
    fx_relative_cot_summary,
    historical_analog_for_fx,
    historical_analog_for_market,
    macro_regime_snapshot,
    market_context_for_classic,
    market_context_for_fx,
    market_names,
    seasonal_state_for_fx,
    seasonal_state_for_market,
)
from src.trader_theme import apply_trader_dark_theme
from src.ui.research_terminal import (
    apply_terminal_theme,
    evidence_panels,
    header,
    insights,
    section,
    stat_grid,
    thesis_hero,
)


# V3.30.3 · ACTUAL RESEARCH TERMINAL REDESIGN
# V3.30.4 · MOCKUP LAYOUT + HTML RENDER FIX

apply_trader_dark_theme()
apply_terminal_theme()

header(
    "RESEARCH",
    "Marktanalyse",
    "Eine institutionelle Trade-These pro Markt: Positionierung, Setup-State, Seasonality, Historical Analog und Market Context.",
)


@st.cache_data(ttl=3600, show_spinner=False)
def _cot(a: str, m: str):
    return cot_state_for_market(a, m).to_dict()


@st.cache_data(ttl=21600, show_spinner=False)
def _season(a: str, m: str):
    return seasonal_state_for_market(a, m).to_dict()


@st.cache_data(ttl=21600, show_spinner=False)
def _season_fx(p: str):
    return seasonal_state_for_fx(p).to_dict()


@st.cache_data(ttl=21600, show_spinner=False)
def _macro():
    return macro_regime_snapshot().to_dict()


# V3.30.6 · SEASONAL PATH IN MARKET ANALYSIS
@st.cache_data(ttl=21600, show_spinner=False)
def _seasonal_path_prices(ticker: str):
    start = (
        pd.Timestamp.today()
        .normalize()
        - pd.DateOffset(years=31)
    )

    return load_prices(
        ticker,
        start=start,
    )

handoff = st.session_state.pop(
    "research_market_handoff",
    None,
)

if handoff:
    if handoff.get("kind") == "fx":
        st.session_state["v3290_market_kind"] = "FX-Paar"
        st.session_state["v3290_fx_pair"] = handoff.get("pair")
    else:
        st.session_state["v3290_market_kind"] = "Markt"
        st.session_state["v3290_asset_class"] = handoff.get("asset_class")
        st.session_state["v3290_market_name"] = handoff.get("market_name")


# Compact top-right-style selector row
selector_left, selector_mid, selector_right = st.columns(
    [1.1, 1.25, 2.0],
    vertical_alignment="bottom",
)

with selector_left:
    kind = st.selectbox(
        "Analyse-Typ",
        ["Markt", "FX-Paar"],
        key="v3290_market_kind",
    )

if kind == "Markt":
    classes = list(
        CLASSIC_MARKETS.keys()
    )

    with selector_mid:
        asset_class = st.selectbox(
            "Assetklasse",
            classes,
            key="v3290_asset_class",
        )

    names = market_names(
        asset_class
    )

    if (
        st.session_state.get("v3290_market_name")
        not in names
    ):
        st.session_state["v3290_market_name"] = (
            names[0]
            if names
            else None
        )

    with selector_right:
        market_name = st.selectbox(
            "Markt",
            names,
            key="v3290_market_name",
        )

    selection = market_name
    selection_note = asset_class
else:
    with selector_mid:
        st.caption(
            "Relative FX · Base minus Quote"
        )

    pairs = list(
        FX_PAIRS.keys()
    )

    if (
        st.session_state.get("v3290_fx_pair")
        not in pairs
    ):
        st.session_state["v3290_fx_pair"] = (
            pairs[0]
            if pairs
            else None
        )

    with selector_right:
        pair = st.selectbox(
            "FX-Paar",
            pairs,
            key="v3290_fx_pair",
        )

    selection = pair
    selection_note = "Relative FX Positioning"


macro_payload = _macro()

macro_state = MacroRegimeState(
    **{
        k: v
        for k, v in macro_payload.items()
        if k in MacroRegimeState.__dataclass_fields__
    }
)


if kind == "Markt":
    cot = CotPositioningState(
        **_cot(
            asset_class,
            market_name,
        )
    )

    seasonal = SeasonalTurnState(
        **_season(
            asset_class,
            market_name,
        )
    )

    context = market_context_for_classic(
        asset_class,
        market_name,
        macro_state=macro_state,
    )

    relative = None
else:
    relative = fx_relative_cot_summary(
        pair
    )

    diff = relative.get(
        "differential"
    )

    cot = CotPositioningState(
        bool(relative.get("available")),
        pair,
        "relative tff",
        "Base minus Quote",
        str(
            relative.get(
                "bias",
                "Insufficient Data",
            )
        ),
        "RELATIVE COT",
        diff,
        abs(float(diff))
        if diff is not None
        else None,
        None,
        None,
        None,
        "N/V",
        "N/V",
        "N/V",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "Relative FX Positioning",
        "N/V",
        None,
        None,
        None,
        "RELATIVE",
        (
            "Medium Confidence"
            if relative.get("available")
            else "Low Confidence"
        ),
        "",
    )

    seasonal = SeasonalTurnState(
        **_season_fx(pair)
    )

    context = market_context_for_fx(
        pair,
        macro_state=macro_state,
    )


opportunity = derive_trade_opportunity(
    cot,
    seasonal,
    context,
)


# Hero stays visible above every tab, like the approved mockup.
thesis_hero(
    selection,
    structural_bias=opportunity.structural_bias,
    setup_state=opportunity.setup_type,
    conviction=opportunity.conviction,
    setup_type=opportunity.trade_type,
    action=opportunity.preferred_action,
    thesis=opportunity.thesis,
    market_note=selection_note,
    setup_note=opportunity.trade_type,
)


tabs = st.tabs(
    [
        "Overview",
        "COT",
        "Seasonal Turn",
        "Historical Analog",
        "Market Context",
    ]
)


with tabs[0]:
    section(
        "Research-Konfluenz",
        "Was die aktuelle Trade-These unterstützt und was ihr widerspricht.",
    )

    evidence_panels(
        opportunity.supports,
        opportunity.conflicts,
    )

    with st.expander(
        "Why this regime?",
        expanded=False,
    ):
        st.write(
            {
                "COT": cot.structural_bias,
                "Seasonality": seasonal.turn_read,
                "Market Context": context.alignment,
                "Setup Type": opportunity.setup_type,
            }
        )


with tabs[1]:
    section(
        "COT Positioning",
        "Strukturelle Positionierung plus 4W / 2W / 1W Flow.",
    )

    if kind == "Markt":
        stat_grid(
            [
                (
                    "156W Struktur",
                    (
                        "—"
                        if cot.commercial_net_156w_percentile is None
                        else f"{cot.commercial_net_156w_percentile:.0f}"
                    ),
                    cot.structural_group,
                ),
                (
                    "26W COT-Index",
                    (
                        "—"
                        if cot.cot_index_26w is None
                        else f"{cot.cot_index_26w:.0f}"
                    ),
                    "Extrem / Fortsetzung",
                ),
                (
                    "Persistenz",
                    (
                        "—"
                        if cot.persistence is None
                        else f"{cot.persistence:.0%}"
                    ),
                    "1W / 2W / 4W",
                ),
                (
                    "Mikro-COT",
                    cot.micro_bias,
                    cot.momentum_context,
                ),
            ]
        )

        flow = pd.DataFrame(
            [
                {
                    "Fenster": "4W",
                    "Richtung": cot.direction_4w,
                    "Long Δ": cot.long_delta_4w,
                    "Short Δ": cot.short_delta_4w,
                    "Net Δ": cot.net_delta_4w,
                },
                {
                    "Fenster": "2W",
                    "Richtung": cot.direction_2w,
                    "Long Δ": cot.long_delta_2w,
                    "Short Δ": cot.short_delta_2w,
                    "Net Δ": cot.net_delta_2w,
                },
                {
                    "Fenster": "1W",
                    "Richtung": cot.direction_1w,
                    "Long Δ": cot.long_delta_1w,
                    "Short Δ": cot.short_delta_1w,
                    "Net Δ": cot.net_delta_1w,
                },
            ]
        )

        st.dataframe(
            flow.style.format(
                {
                    "Long Δ": "{:+.4f}",
                    "Short Δ": "{:+.4f}",
                    "Net Δ": "{:+.4f}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            f"Release: {cot.freshness_state} · Report {cot.report_date or '—'}"
        )
    else:
        base = dict(
            relative.get("base", {})
        )
        quote = dict(
            relative.get("quote", {})
        )

        stat_grid(
            [
                (
                    f"{FX_PAIRS[pair]['base']} COT",
                    base.get(
                        "structural_bias",
                        "Insufficient Data",
                    ),
                    (
                        "Score —"
                        if base.get("score") is None
                        else f"Score {base['score']:+.0f}"
                    ),
                ),
                (
                    f"{FX_PAIRS[pair]['quote']} COT",
                    quote.get(
                        "structural_bias",
                        "Insufficient Data",
                    ),
                    (
                        "Score —"
                        if quote.get("score") is None
                        else f"Score {quote['score']:+.0f}"
                    ),
                ),
                (
                    "Relative Differenz",
                    (
                        "—"
                        if relative.get("differential") is None
                        else f"{relative['differential']:+.0f}"
                    ),
                    relative.get(
                        "bias",
                        "No Current Signal",
                    ),
                ),
            ]
        )

    with st.expander(
        "COT Evidence",
        expanded=False,
    ):
        st.json(
            cot.to_dict()
        )


with tabs[2]:
    section(
        "Seasonal Turn",
        "Wendefenster plus 20 / 40 / 60T Robustheit und struktureller COT-Flow.",
    )

    stat_grid(
        [
            (
                "Turn",
                seasonal.turn_type,
                (
                    "Distanz —"
                    if seasonal.distance_days is None
                    else "HEUTE"
                    if seasonal.distance_days == 0
                    else f"Distanz {seasonal.distance_days:+d}T"
                ),
            ),
            (
                "Robustheit",
                seasonal.robustness,
                "20 / 40 / 60T",
            ),
            (
                "COT am Turn",
                seasonal.cot_confirmation,
                "4W / 2W / 1W",
            ),
            (
                "Turn Read",
                seasonal.turn_read,
                "Timing-Kontext",
            ),
        ]
    )

    section(
        "Saisonaler Verlauf",
        (
            "Derselbe saisonale Jahrespfad wie im Saisonalitäts-Labor: "
            "Median abgeschlossener Jahre, 25–75%-Band, Tops/Bottoms "
            "und aktuelle Jahresphase."
        ),
    )

    if kind == "Markt":
        _season_market_spec = next(
            (
                item
                for item in CLASSIC_MARKETS.get(asset_class, [])
                if item.get("name") == market_name
            ),
            None,
        )
        _season_path_ticker = (
            _season_market_spec.get("ticker")
            if _season_market_spec
            else None
        )
    else:
        _season_path_ticker = FX_PAIRS[pair].get("ticker")

    if not _season_path_ticker:
        st.info(
            "Insufficient Data · kein Preis-Ticker für den saisonalen Pfad."
        )
    else:
        with st.spinner("Saisonaler Jahrespfad wird geladen …"):
            _season_path_frame = _seasonal_path_prices(
                str(_season_path_ticker)
            )

        if _season_path_frame is None or _season_path_frame.empty:
            st.info(
                "Insufficient Data · keine ausreichende Preis-Historie "
                "für den saisonalen Jahrespfad."
            )
        else:
            render_seasonal_path_chart(
                _season_path_frame,
                history_years=20,
                key="v3306_seasonal_path_" + str(selection),
            )

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Forward": "20T",
                    "Richtung": seasonal.direction_20t,
                },
                {
                    "Forward": "40T",
                    "Richtung": seasonal.direction_40t,
                },
                {
                    "Forward": "60T",
                    "Richtung": seasonal.direction_60t,
                },
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander(
        "Transition Triggers",
        expanded=False,
    ):
        st.write(
            {
                "Unterstützer": list(
                    seasonal.supporters
                ),
                "Konflikte": list(
                    seasonal.conflicts
                ),
                "Turn": seasonal.turn_type,
                "Distanz": seasonal.distance_days,
            }
        )


with tabs[3]:
    left, right = st.columns(
        [1.62, 1],
        gap="medium",
    )

    with left:
        section(
            "Historische Analogs",
            "Ähnliche historische Setups. Keine kalibrierte Wahrscheinlichkeit.",
        )

        control_a, control_b, control_c = st.columns(
            [1, 1, .9],
            vertical_alignment="bottom",
        )

        with control_a:
            horizon = st.selectbox(
                "Forward",
                [4, 8, 12],
                index=1,
                format_func=lambda x: f"{x}W",
                key="v3290_analog_horizon",
            )

        with control_b:
            top_n = st.selectbox(
                "Matches",
                [5, 8, 10, 12],
                index=1,
                key="v3290_analog_matches",
            )

        with control_c:
            run_analog = st.button(
                "Berechnen",
                key="v3290_run_analog",
                type="primary",
                use_container_width=True,
            )

        if run_analog:
            with st.spinner(
                "Historische Setups werden gesucht …"
            ):
                analog = (
                    historical_analog_for_market(
                        asset_class,
                        market_name,
                        top_n=top_n,
                        horizon_weeks=horizon,
                    )
                    if kind == "Markt"
                    else historical_analog_for_fx(
                        pair,
                        top_n=top_n,
                        horizon_weeks=horizon,
                    )
                )

            if not analog.available:
                st.info(
                    analog.reason
                    or "No Current Signal"
                )
            else:
                matches = pd.DataFrame(
                    analog.top_matches
                )

                forward_col = (
                    f"{analog.horizon_weeks}W"
                )

                if (
                    not matches.empty
                    and forward_col in matches.columns
                ):
                    forward_returns = pd.to_numeric(
                        matches[forward_col],
                        errors="coerce",
                    ).dropna()
                else:
                    forward_returns = pd.Series(
                        dtype=float
                    )

                bullish_rate = (
                    float(
                        (
                            forward_returns > 0
                        ).mean()
                    )
                    if not forward_returns.empty
                    else None
                )

                bearish_rate = (
                    float(
                        (
                            forward_returns < 0
                        ).mean()
                    )
                    if not forward_returns.empty
                    else None
                )

                stat_grid(
                    [
                        (
                            "Bullish %",
                            (
                                "—"
                                if bullish_rate is None
                                else f"{bullish_rate:.0%}"
                            ),
                            "Forward Return > 0",
                        ),
                        (
                            "Bearish %",
                            (
                                "—"
                                if bearish_rate is None
                                else f"{bearish_rate:.0%}"
                            ),
                            "Forward Return < 0",
                        ),
                        (
                            f"Median {analog.horizon_weeks}W",
                            (
                                "—"
                                if analog.median_forward_return is None
                                else f"{analog.median_forward_return:+.2%}"
                            ),
                            analog.outcome_bias,
                        ),
                        (
                            "Matches",
                            analog.sample_size,
                            analog.sample_quality,
                        ),
                    ]
                )

                # Honest chart: anonymized forward-return distribution.
                # We do not pretend this is a full path if the engine only exposes final returns.
                # V3.30.5.1 · REAL MULTI-HORIZON ANALOG LINE CHART
                #
                # The analog engine already exposes fixed forward outcomes
                # (2W / 4W / 8W / 12W) for each selected historical match.
                # We connect only those real observation points.
                # No daily/intermediate price path is invented.
                _available_horizons = []
                for _weeks in (2, 4, 8, 12):
                    _column = next(
                        (
                            _candidate
                            for _candidate in (
                                f"{_weeks}W",
                                f"+{_weeks}W",
                                f"forward_return_{_weeks}w",
                                f"forward_{_weeks}w",
                            )
                            if _candidate in matches.columns
                        ),
                        None,
                    )

                    if _column is None:
                        continue

                    _series = pd.to_numeric(
                        matches[_column],
                        errors="coerce",
                    )

                    if _series.notna().any():
                        _available_horizons.append(
                            (_weeks, _column)
                        )

                _analog_fig = go.Figure()

                if len(_available_horizons) >= 2:
                    _matrix = pd.DataFrame(
                        {
                            int(_weeks): pd.to_numeric(
                                matches[_column],
                                errors="coerce",
                            )
                            for _weeks, _column
                            in _available_horizons
                        }
                    )

                    # Anonymous individual analogs in the background.
                    for _display_idx, (_, _row) in enumerate(
                        _matrix.head(12).iterrows(),
                        start=1,
                    ):
                        _xs = [0]
                        _ys = [0.0]

                        for _weeks in _matrix.columns:
                            _value = _row.get(_weeks)

                            if pd.notna(_value):
                                _xs.append(
                                    int(_weeks)
                                )
                                _ys.append(
                                    float(_value)
                                )

                        if len(_xs) < 3:
                            continue

                        _analog_fig.add_trace(
                            go.Scatter(
                                x=_xs,
                                y=_ys,
                                mode="lines",
                                name=f"Analog {_display_idx}",
                                line=dict(
                                    width=1,
                                    color="#607080",
                                ),
                                opacity=0.20,
                                hovertemplate=(
                                    "Woche %{x}<br>"
                                    "Forward %{y:.2%}"
                                    "<extra></extra>"
                                ),
                                showlegend=False,
                            )
                        )

                    _median = _matrix.median(
                        axis=0,
                        skipna=True,
                    )
                    _q25 = _matrix.quantile(
                        0.25,
                        axis=0,
                    )
                    _q75 = _matrix.quantile(
                        0.75,
                        axis=0,
                    )

                    def _analog_xy(_series):
                        _xs = [0]
                        _ys = [0.0]

                        for _weeks, _value in _series.items():
                            if pd.notna(_value):
                                _xs.append(
                                    int(_weeks)
                                )
                                _ys.append(
                                    float(_value)
                                )

                        return _xs, _ys

                    _mx, _my = _analog_xy(
                        _median
                    )
                    _lx, _ly = _analog_xy(
                        _q25
                    )
                    _ux, _uy = _analog_xy(
                        _q75
                    )

                    _analog_fig.add_trace(
                        go.Scatter(
                            x=_ux,
                            y=_uy,
                            mode="lines",
                            name="75%-Pfad",
                            line=dict(
                                width=1.6,
                                dash="dot",
                                color="#65D98B",
                            ),
                            opacity=0.75,
                        )
                    )

                    _analog_fig.add_trace(
                        go.Scatter(
                            x=_lx,
                            y=_ly,
                            mode="lines",
                            name="25%-Pfad",
                            line=dict(
                                width=1.6,
                                dash="dot",
                                color="#FF7373",
                            ),
                            opacity=0.75,
                        )
                    )

                    _analog_fig.add_trace(
                        go.Scatter(
                            x=_mx,
                            y=_my,
                            mode="lines+markers",
                            name="Median-Pfad",
                            line=dict(
                                width=3,
                                color="#62A6C9",
                            ),
                            marker=dict(
                                size=6,
                                color="#62A6C9",
                            ),
                        )
                    )

                    _tickvals = [
                        0,
                        *[
                            int(_weeks)
                            for _weeks, _
                            in _available_horizons
                        ],
                    ]

                else:
                    # If only the selected endpoint is available, show honest
                    # 0 -> horizon lines rather than fabricating a full path.
                    _endpoint = pd.to_numeric(
                        matches.get(
                            forward_col,
                            pd.Series(dtype=float),
                        ),
                        errors="coerce",
                    ).dropna()

                    _horizon = int(
                        analog.horizon_weeks
                    )

                    for _display_idx, _value in enumerate(
                        _endpoint.head(12),
                        start=1,
                    ):
                        _analog_fig.add_trace(
                            go.Scatter(
                                x=[0, _horizon],
                                y=[0.0, float(_value)],
                                mode="lines",
                                name=f"Analog {_display_idx}",
                                line=dict(
                                    width=1,
                                    color="#607080",
                                ),
                                opacity=0.24,
                                showlegend=False,
                            )
                        )

                    if not _endpoint.empty:
                        _median_endpoint = float(
                            _endpoint.median()
                        )
                        _q25_endpoint = float(
                            _endpoint.quantile(0.25)
                        )
                        _q75_endpoint = float(
                            _endpoint.quantile(0.75)
                        )

                        _analog_fig.add_trace(
                            go.Scatter(
                                x=[0, _horizon],
                                y=[0.0, _q75_endpoint],
                                mode="lines",
                                name="75%-Pfad",
                                line=dict(
                                    width=1.6,
                                    dash="dot",
                                    color="#65D98B",
                                ),
                            )
                        )

                        _analog_fig.add_trace(
                            go.Scatter(
                                x=[0, _horizon],
                                y=[0.0, _q25_endpoint],
                                mode="lines",
                                name="25%-Pfad",
                                line=dict(
                                    width=1.6,
                                    dash="dot",
                                    color="#FF7373",
                                ),
                            )
                        )

                        _analog_fig.add_trace(
                            go.Scatter(
                                x=[0, _horizon],
                                y=[0.0, _median_endpoint],
                                mode="lines+markers",
                                name="Median-Pfad",
                                line=dict(
                                    width=3,
                                    color="#62A6C9",
                                ),
                                marker=dict(
                                    size=6,
                                    color="#62A6C9",
                                ),
                            )
                        )

                    _tickvals = [
                        0,
                        _horizon,
                    ]

                if _analog_fig.data:
                    _analog_fig.add_hline(
                        y=0,
                        line_dash="dot",
                        line_color="#52606D",
                        opacity=0.55,
                    )

                    _analog_fig.update_layout(
                        height=390,
                        margin=dict(
                            l=0,
                            r=0,
                            t=24,
                            b=0,
                        ),
                        paper_bgcolor="#081018",
                        plot_bgcolor="#081018",
                        font=dict(
                            color="#C8D1DC",
                        ),
                        xaxis=dict(
                            title=None,
                            tickmode="array",
                            tickvals=_tickvals,
                            ticktext=[
                                "Setup"
                                if _week == 0
                                else f"{_week}W"
                                for _week in _tickvals
                            ],
                            gridcolor="#22303D",
                            linecolor="#22303D",
                            zeroline=False,
                        ),
                        yaxis=dict(
                            title="Forward Return",
                            tickformat=".1%",
                            gridcolor="#22303D",
                            linecolor="#22303D",
                            zeroline=False,
                        ),
                        legend=dict(
                            orientation="h",
                            y=1.10,
                            x=0,
                        ),
                        hovermode="x unified",
                    )

                    st.plotly_chart(
                        _analog_fig,
                        use_container_width=True,
                        config={
                            "displaylogo": False,
                            "displayModeBar": False,
                        },
                    )

                    if len(
                        _available_horizons
                    ) >= 2:
                        st.caption(
                            "Historische Analog-Pfade aus den tatsächlich "
                            "vorhandenen 2W / 4W / 8W / 12W Forward-Outcomes. "
                            "Zwischenpunkte werden nicht als echte Kursdaten "
                            "interpretiert."
                        )
                    else:
                        st.caption(
                            "Für diese Auswertung ist nur der gewählte "
                            "Forward-Endpunkt verfügbar. Gezeigt wird deshalb "
                            "nur die reale Veränderung vom Setup zum Endpunkt."
                        )

                st.caption(
                    analog.conclusion
                )
        else:
            st.caption(
                "Analog-Recherche wird auf Anforderung gerechnet."
            )

    with right:
        section(
            "Marktkontext",
            "Makro-, Volatilitäts- und Cross-Asset-Kontext.",
        )

        stat_grid(
            [
                (
                    "Volatilität",
                    context.volatility_regime_state,
                    "aktuelles Preisregime",
                ),
                (
                    "Intermarket",
                    context.intermarket_state,
                    "Cross-Asset",
                ),
                (
                    "Makro",
                    context.business_cycle_state,
                    context.macro_momentum_state,
                ),
            ]
        )

        insights(
            [
                (
                    "Trend",
                    (
                        f"COT 4W / 2W / 1W: "
                        f"{cot.direction_4w} / {cot.direction_2w} / {cot.direction_1w}"
                    ),
                    cot.direction_2w,
                ),
                (
                    "Saisonale Dynamik",
                    (
                        f"{seasonal.turn_type} · "
                        f"{seasonal.turn_read}"
                    ),
                    seasonal.turn_read,
                ),
                (
                    "Macro × COT",
                    (
                        f"{context.business_cycle_state} · "
                        f"{context.alignment}"
                    ),
                    context.alignment,
                ),
            ]
        )


with tabs[4]:
    section(
        "Market Context",
        "Makro, Volatilität und Cross-Asset sind Kontext — nicht Entry.",
    )

    stat_grid(
        [
            (
                "Makro-Regime",
                context.business_cycle_state,
                context.macro_momentum_state,
            ),
            (
                "Volatilität",
                context.volatility_regime_state,
                "aktuelles Preisregime",
            ),
            (
                "Cross-Asset",
                context.cross_asset_support_state,
                context.intermarket_state,
            ),
            (
                "Transition Pressure",
                (
                    "—"
                    if context.transition_pressure_score is None
                    else f"{context.transition_pressure_score:.0f}/100"
                ),
                "Next-Regime Pressure",
            ),
        ]
    )

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Layer": "Business Cycle",
                    "State": context.business_cycle_state,
                },
                {
                    "Layer": "Macro Momentum",
                    "State": context.macro_momentum_state,
                },
                {
                    "Layer": "Intermarket",
                    "State": context.intermarket_state,
                },
                {
                    "Layer": "Volatility",
                    "State": context.volatility_regime_state,
                },
                {
                    "Layer": "Cross-Asset",
                    "State": context.cross_asset_support_state,
                },
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander(
        "Macro Evidence",
        expanded=False,
    ):
        st.write(
            {
                "Risk-Off Breadth": context.risk_off_breadth,
                "Risk-On Breadth": context.risk_on_breadth,
                "Macro Bias": context.macro_bias,
            }
        )

    with st.expander(
        "Cross-Asset Evidence",
        expanded=False,
    ):
        st.write(
            {
                "Alignment": context.alignment,
                "COT Bias": context.cot_bias,
                "Intermarket": context.intermarket_state,
            }
        )

    with st.expander(
        "Raw Diagnostics",
        expanded=False,
    ):
        st.json(
            {
                "COT": cot.to_dict(),
                "Seasonality": seasonal.to_dict(),
                "Context": context.to_dict(),
            }
        )
