from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except ImportError:  # pragma: no cover
    px = None

from src.cftc_reports import (
    DATASETS,
    load_report_history,
    load_report_universe,
    primary_report_for_asset_class,
    resolve_report_market,
)
from src.cot_price_analog import (
    analyze_historical_analogs,
    normalized_analog_paths,
)
from src.markets import CLASSIC_MARKETS
from src.prices import load_prices
from src.report_analysis import enrich_report_positioning
from src.style import (
    apply_style,
    context_strip,
    metric_card,
    page_header,
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


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return np.nan
    return value if np.isfinite(value) else np.nan


def _pct(value, digits=1):
    value = _finite(value)
    return (
        "—"
        if not np.isfinite(value)
        else f"{value:+.{digits}%}"
    )


def _sim(value):
    value = _finite(value)
    return (
        "—"
        if not np.isfinite(value)
        else f"{value:.0f}%"
    )


page_header(
    "Research · COT × Price",
    "COT × Price Historical Analog",
    "Welche historischen Preis- und COT-Setups sahen dem heutigen Zustand ähnlich – und was passierte anschließend?",
    "V3.25.0 · HISTORICAL ANALOG LAB",
)

st.caption(
    "Research only · kein Entry-Signal · keine Watchlist-Änderung. "
    "Similarity = 50% Preisstruktur + 25% COT-Level + 25% COT-Flow. "
    "Historische Matches werden zeitlich voneinander getrennt, damit nicht mehrere Wochen desselben Ereignisses als unabhängige Treffer gezählt werden."
)

_selected = st.session_state.get(
    "selected_market"
)

if (
    _selected
    and "cpa_asset_class"
    not in st.session_state
):
    st.session_state[
        "cpa_asset_class"
    ] = _selected.get(
        "asset_class"
    )
    st.session_state[
        "cpa_market"
    ] = _selected.get(
        "market_name"
    )

with st.container(border=True):
    c1, c2, c3, c4 = st.columns(
        [1.1, 1.4, 0.8, 0.9],
        gap="small",
    )

    with c1:
        asset_class = st.selectbox(
            "Assetklasse",
            list(CLASSIC_MARKETS.keys()),
            format_func=lambda x: ASSET_CLASS_DE.get(
                x,
                x,
            ),
            key="cpa_asset_class",
        )

    markets = CLASSIC_MARKETS[
        asset_class
    ]
    market_names = [
        item["name"]
        for item in markets
    ]

    if (
        st.session_state.get(
            "cpa_market"
        )
        not in market_names
    ):
        st.session_state[
            "cpa_market"
        ] = market_names[0]

    with c2:
        market_name = st.selectbox(
            "Markt",
            market_names,
            key="cpa_market",
        )

    with c3:
        top_n = st.selectbox(
            "Matches",
            [5, 8, 10, 12],
            index=1,
        )

    with c4:
        horizon = st.selectbox(
            "Outcome",
            [4, 8, 12],
            index=1,
            format_func=lambda x: f"{x}W",
        )

    market = next(
        item
        for item in markets
        if item["name"] == market_name
    )
    price_ticker = market[
        "ticker"
    ]

    st.session_state[
        "selected_market"
    ] = {
        "asset_class": asset_class,
        "market_name": market_name,
    }

    st.caption(
        f"Preis-Proxy automatisch: **{price_ticker}** · "
        "Match-Abstand mindestens 13 Wochen · die letzten 26 Wochen werden nicht als historische Analogs verwendet."
    )

price_start = (
    pd.Timestamp.today().normalize()
    - pd.DateOffset(years=35)
)

with st.spinner(
    "Preis- und COT-Historie wird für Analog-Suche aufgebaut …"
):
    prices = load_prices(
        price_ticker,
        start=price_start,
    )

if prices is None or prices.empty:
    st.error(
        "Keine Preisreihe verfügbar."
    )
    st.stop()

report_type = primary_report_for_asset_class(
    asset_class
)
flow_error = None
enriched = pd.DataFrame()
resolved = None

try:
    universe = load_report_universe(
        report_type
    )
    resolved = resolve_report_market(
        market,
        universe,
    )

    if resolved:
        raw = load_report_history(
            report_type,
            resolved[
                "cftc_contract_market_code"
            ],
        )

        if (
            raw is not None
            and not raw.empty
        ):
            enriched = enrich_report_positioning(
                raw,
                report_type=report_type,
                index_weeks=26,
                validation_weeks=156,
            )
except Exception as exc:
    flow_error = (
        f"{type(exc).__name__}: {exc}"
    )

if enriched.empty:
    st.error(
        "Keine ausreichende COT-Historie verfügbar."
    )
    if flow_error:
        st.caption(flow_error)
    st.stop()

result = analyze_historical_analogs(
    prices,
    enriched,
    report_type,
    top_n=int(top_n),
    min_spacing_weeks=13,
    exclude_recent_weeks=26,
    excursion_horizon_weeks=int(
        horizon
    ),
)

if not result.get("available"):
    st.warning(
        result.get(
            "reason",
            "Keine ausreichend ähnlichen historischen Setups verfügbar.",
        )
    )
    st.stop()

current = result["current"]
matches = result["matches"].copy()
aggregate = result["aggregate"]

context_strip(
    [
        ("Markt", market_name),
        ("Preis-Proxy", price_ticker),
        (
            "COT-Report",
            DATASETS.get(
                report_type,
                {},
            ).get(
                "label",
                report_type,
            ),
        ),
        (
            "COT verfügbar ab",
            pd.Timestamp(
                current[
                    "availability_date"
                ]
            ).date().isoformat(),
        ),
    ]
)


section_line(
    "1 · Historical Analog Read",
    f"kompakter Read über {horizon} Wochen",
)

outcome_col = f"return_{horizon}w"
outcome_series = pd.to_numeric(
    matches.get(
        outcome_col
    ),
    errors="coerce",
).dropna()

match_count = int(
    outcome_series.shape[0]
)
bullish_count = int(
    (outcome_series > 0).sum()
)
bearish_count = int(
    (outcome_series < 0).sum()
)
flat_count = int(
    (outcome_series == 0).sum()
)

bullish_rate = (
    bullish_count / match_count
    if match_count
    else np.nan
)
bearish_rate = (
    bearish_count / match_count
    if match_count
    else np.nan
)
median_return = (
    float(
        outcome_series.median()
    )
    if match_count
    else np.nan
)

h1, h2, h3, h4 = st.columns(4)

with h1:
    metric_card(
        "MATCHES",
        str(
            match_count
        ),
        "zeitlich unabhängige historische Fälle",
    )

with h2:
    metric_card(
        "BULLISH",
        (
            "—"
            if not np.isfinite(
                bullish_rate
            )
            else f"{bullish_rate:.0%}"
        ),
        f"{bullish_count} von {match_count} Fällen",
    )

with h3:
    metric_card(
        "BEARISH",
        (
            "—"
            if not np.isfinite(
                bearish_rate
            )
            else f"{bearish_rate:.0%}"
        ),
        f"{bearish_count} von {match_count} Fällen",
    )

with h4:
    metric_card(
        f"MEDIAN {horizon}W",
        _pct(
            median_return
        ),
        "historischer Median-Return",
    )

if match_count == 0:
    st.info(
        "Für den gewählten Horizont liegen keine auswertbaren historischen Outcomes vor."
    )
else:
    summary = (
        f"Hier wurden {match_count} unabhängige historische Matches gefunden. "
        f"Über {horizon} Wochen waren {bullish_count} Fälle bullish, {bearish_count} Fälle bearish"
        + (
            f" und {flat_count} Fälle unverändert. "
            if flat_count
            else ". "
        )
        + f"Der mediane {horizon}W-Return lag bei {_pct(median_return)}. "
        + "Das ist Research-Evidence und kein Entry-Signal."
    )

    if bearish_count > bullish_count:
        st.error(summary)
    elif bullish_count > bearish_count:
        st.success(summary)
    else:
        st.info(summary)

with st.expander(
    "Historische Match-Details",
    expanded=False,
):
    st.caption(
        "Similarity = 50% Preisstruktur + 25% COT-Level + 25% COT-Flow. "
        "Die Detailtabelle bleibt verfügbar, wird aber nicht mehr als Hauptblock in den Vordergrund gestellt."
    )

    top_cards = st.columns(
        min(
            3,
            len(matches),
        )
    )

    for col, (_, row) in zip(
        top_cards,
        matches.head(3).iterrows(),
    ):
        with col:
            metric_card(
                pd.Timestamp(
                    row["availability_date"]
                ).date().isoformat(),
                _sim(
                    row.get(
                        "similarity"
                    )
                ),
                (
                    f"{horizon}W "
                    f"{_pct(row.get(f'return_{horizon}w'))}"
                ),
            )

    show = matches.copy()
    show["Analog"] = pd.to_datetime(
        show["availability_date"],
        errors="coerce",
    ).dt.date.astype(str)

    show = show.rename(
        columns={
            "similarity": "Similarity",
            "price_similarity": "Price",
            "cot_level_similarity": "COT Level",
            "cot_flow_similarity": "COT Flow",
            "return_2w": "+2W",
            "return_4w": "+4W",
            "return_8w": "+8W",
            "return_12w": "+12W",
            "mae": f"MAE {horizon}W",
            "mfe": f"MFE {horizon}W",
        }
    )

    analog_cols = [
        "Analog",
        "Similarity",
        "Price",
        "COT Level",
        "COT Flow",
        "+2W",
        "+4W",
        "+8W",
        "+12W",
        f"MAE {horizon}W",
        f"MFE {horizon}W",
    ]

    st.dataframe(
        show[
            [
                col
                for col in analog_cols
                if col in show.columns
            ]
        ].style.format(
            {
                "Similarity": "{:.0f}%",
                "Price": "{:.0f}%",
                "COT Level": "{:.0f}%",
                "COT Flow": "{:.0f}%",
                "+2W": "{:+.1%}",
                "+4W": "{:+.1%}",
                "+8W": "{:+.1%}",
                "+12W": "{:+.1%}",
                f"MAE {horizon}W": "{:+.1%}",
                f"MFE {horizon}W": "{:+.1%}",
            },
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )


section_line(
    "2 · Price Path Comparison",
    "Current 13W Lookback vs. Top-3 historische Analogs · historische Pfade zeigen zusätzlich den gewählten Forward-Horizont",
)

path_frame = normalized_analog_paths(
    prices,
    current_anchor=pd.Timestamp(
        current["availability_date"]
    ),
    historical_anchors=[
        pd.Timestamp(value)
        for value in matches[
            "availability_date"
        ].head(3)
    ],
    lookback_weeks=13,
    forward_weeks=int(
        horizon
    ),
)

if not path_frame.empty:
    if px is not None:
        fig = px.line(
            path_frame,
            x="relative_day",
            y="normalized",
            color="analog",
            labels={
                "relative_day": "Tage relativ zum Setup",
                "normalized": "Preis indexiert auf Setup = 100",
                "analog": "Setup",
            },
        )
        fig.add_vline(
            x=0,
            line_dash="dash",
            line_width=1,
        )
        fig.update_layout(
            height=500,
            margin=dict(
                l=10,
                r=10,
                t=15,
                b=10,
            ),
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displaylogo": False,
            },
        )
    else:
        pivot = path_frame.pivot_table(
            index="relative_day",
            columns="analog",
            values="normalized",
            aggfunc="last",
        )
        st.line_chart(
            pivot,
            use_container_width=True,
        )


section_line(
    "3 · Methodik / Grenzen",
    "Analog-Suche ist eine Research-Methode, kein fertiges probabilistisches Modell",
)

st.markdown(
    """
- **Kein Look-Ahead bei COT:** Ein Tuesday-COT-Snapshot wird konservativ erst ab `report_date + 3 Tage` als verfügbar behandelt.
- **COT-Dynamik zählt mit:** Verglichen werden Net/OI-Level, rollierende Percentiles sowie 1W/2W/4W-Net/OI-Änderungen und 4W Long-/Short-Aufbau.
- **Preis wird normalisiert:** Verglichen werden Returns, Drawdown, Trend relativ zu 13W/26W-Mittel und 13W-Volatilität – nicht der absolute Future-Preis.
- **Unabhängigere Treffer:** Ausgewählte Analogs müssen mindestens 13 Wochen auseinanderliegen; die letzten 26 Wochen werden als historische Kandidaten ausgeschlossen.
- **Forward Outcomes:** 2W/4W/8W/12W werden mit festen Horizonten ausgewertet. MAE/MFE verwenden High/Low, sofern der Preis-Proxy diese liefert.
- **Futures-Roll-Risiko:** Der bestehende Preis-Proxy kann Continuous-Future-/Roll-Effekte enthalten. Diese Research-Version korrigiert Roll-Gaps noch nicht explizit.
- **Keine 80%-Gewinnwahrscheinlichkeit:** `4/5 positive` bedeutet nur vier positive historische Outcomes in fünf unabhängigen Matches – nicht eine kalibrierte 80%-Trade-Wahrscheinlichkeit.
"""
)
