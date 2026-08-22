from __future__ import annotations

# Imports required by the existing Advanced access guard
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


import numpy as np
import pandas as pd
import streamlit as st

from src.cftc_reports import (
    DATASETS,
    load_report_history,
    load_report_universe,
    primary_report_for_asset_class,
    resolve_report_market,
)
from src.cot_price_analog import analyze_historical_analogs
from src.fx_relative_cot_analog import (
    FX_PAIRS,
    analyze_fx_relative_analogs,
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


CURRENCY_ALIASES = {
    "EUR": ("EURO FX", "EURO"),
    "GBP": ("BRITISH POUND", "POUND"),
    "AUD": ("AUSTRALIAN DOLLAR", "AUSTRALIAN"),
    "NZD": ("NEW ZEALAND DOLLAR", "NEW ZEALAND"),
    "JPY": ("JAPANESE YEN", "YEN"),
    "CHF": ("SWISS FRANC", "SWISS"),
    "CAD": ("CANADIAN DOLLAR", "CANADIAN"),
}


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return np.nan
    return value if np.isfinite(value) else np.nan


def _pct(value, digits=1):
    value = _finite(value)
    if not np.isfinite(value):
        return "—"
    return f"{value:+.{digits}%}"


def _find_currency_market(currency: str) -> dict | None:
    if currency == "USD":
        return None

    markets = CLASSIC_MARKETS.get(
        "Currencies",
        [],
    )

    aliases = CURRENCY_ALIASES.get(
        currency,
        (),
    )

    for alias in aliases:
        for market in markets:
            name = str(
                market.get(
                    "name",
                    "",
                )
            ).upper()

            if alias in name:
                return market

    return None


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def _load_currency_cot(
    currency: str,
    report_type: str,
):
    market = _find_currency_market(
        currency
    )

    if market is None:
        return (
            pd.DataFrame(),
            None,
        )

    universe = load_report_universe(
        report_type
    )

    resolved = resolve_report_market(
        market,
        universe,
    )

    if not resolved:
        return (
            pd.DataFrame(),
            None,
        )

    raw = load_report_history(
        report_type,
        resolved[
            "cftc_contract_market_code"
        ],
    )

    if (
        raw is None
        or raw.empty
    ):
        return (
            pd.DataFrame(),
            resolved,
        )

    enriched = enrich_report_positioning(
        raw,
        report_type=report_type,
        index_weeks=26,
        validation_weeks=156,
    )

    return (
        enriched,
        resolved,
    )


page_header(
    "Advanced · Analog Diagnostics",
    "Analog Setup Diagnostics",
    "Detaillierte Preis- und COT-Fingerprints der Analog-Engines. "
    "Diese Informationen bleiben verfügbar, ohne die kompakten Research-Seiten zu überladen.",
    "V3.25.4 · ADVANCED DIAGNOSTICS",
)

st.caption(
    "Advanced only · keine zusätzliche Signal-Logik · keine Änderung an Similarity, "
    "Match-Auswahl oder Forward-Outcomes."
)

cot_tab, fx_tab = st.tabs(
    [
        "COT × Price",
        "FX Relative COT",
    ]
)


with cot_tab:
    section_line(
        "COT × Price · Current Setup Fingerprint",
        "Preisbewegung + COT-Level + 1W/2W/4W-Flow",
    )

    default_asset = st.session_state.get(
        "cpa_asset_class",
        "Currencies",
    )

    if default_asset not in CLASSIC_MARKETS:
        default_asset = list(
            CLASSIC_MARKETS.keys()
        )[0]

    asset_keys = list(
        CLASSIC_MARKETS.keys()
    )

    asset_class = st.selectbox(
        "Assetklasse",
        asset_keys,
        index=asset_keys.index(
            default_asset
        ),
        format_func=lambda x: ASSET_CLASS_DE.get(
            x,
            x,
        ),
        key="adv_analog_asset_class",
    )

    markets = CLASSIC_MARKETS[
        asset_class
    ]
    market_names = [
        item["name"]
        for item in markets
    ]

    preferred_market = st.session_state.get(
        "cpa_market"
    )

    market_index = (
        market_names.index(
            preferred_market
        )
        if preferred_market in market_names
        else 0
    )

    market_name = st.selectbox(
        "Markt",
        market_names,
        index=market_index,
        key="adv_analog_market",
    )

    market = next(
        item
        for item in markets
        if item["name"] == market_name
    )

    price_ticker = market[
        "ticker"
    ]

    price_start = (
        pd.Timestamp.today()
        .normalize()
        - pd.DateOffset(
            years=35
        )
    )

    with st.spinner(
        "COT × Price Fingerprint wird geladen …"
    ):
        prices = load_prices(
            price_ticker,
            start=price_start,
        )

        report_type = primary_report_for_asset_class(
            asset_class
        )

        universe = load_report_universe(
            report_type
        )

        resolved = resolve_report_market(
            market,
            universe,
        )

        enriched = pd.DataFrame()

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

    if (
        prices is None
        or prices.empty
        or enriched.empty
    ):
        st.warning(
            "Für diesen Markt ist aktuell keine ausreichende Preis-/COT-Historie verfügbar."
        )
    else:
        result = analyze_historical_analogs(
            prices,
            enriched,
            report_type,
            top_n=8,
            min_spacing_weeks=13,
            exclude_recent_weeks=26,
            excursion_horizon_weeks=8,
        )

        if not result.get(
            "available"
        ):
            st.warning(
                result.get(
                    "reason",
                    "Fingerprint nicht verfügbar.",
                )
            )
        else:
            current = result[
                "current"
            ]

            context_strip(
                [
                    (
                        "Markt",
                        market_name,
                    ),
                    (
                        "Preis-Proxy",
                        price_ticker,
                    ),
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
                        "COT Snapshot verfügbar",
                        pd.Timestamp(
                            current[
                                "availability_date"
                            ]
                        ).date().isoformat(),
                    ),
                ]
            )

            p1, p2, p3, p4 = st.columns(
                4
            )

            with p1:
                metric_card(
                    "PRICE 4W",
                    _pct(
                        current.get(
                            "price_return_4w"
                        )
                    ),
                    f"Close {current.get('close', np.nan):,.2f}",
                )

            with p2:
                metric_card(
                    "PRICE 13W",
                    _pct(
                        current.get(
                            "price_return_13w"
                        )
                    ),
                    "mittelfristige Preisbewegung",
                )

            with p3:
                metric_card(
                    "DRAWDOWN 26W",
                    _pct(
                        current.get(
                            "price_drawdown_26w"
                        )
                    ),
                    "Abstand zum 26W-Hoch",
                )

            with p4:
                metric_card(
                    "VS. MA26",
                    _pct(
                        current.get(
                            "price_vs_ma26"
                        )
                    ),
                    "Preis relativ zum 26W-Mittel",
                )

            group_rows = []

            for group in current.get(
                "groups",
                [],
            ):
                group_rows.append(
                    {
                        "Gruppe": group[
                            "label"
                        ],
                        "Rolle": group[
                            "role"
                        ],
                        "Net/OI": group.get(
                            "net_oi"
                        ),
                        "Net/OI Percentile": group.get(
                            "percentile"
                        ),
                        "1W Δ Net/OI": group.get(
                            "delta_1w"
                        ),
                        "2W Δ Net/OI": group.get(
                            "delta_2w"
                        ),
                        "4W Δ Net/OI": group.get(
                            "delta_4w"
                        ),
                        "4W Δ Long/OI": group.get(
                            "long_delta_4w"
                        ),
                        "4W Δ Short/OI": group.get(
                            "short_delta_4w"
                        ),
                    }
                )

            if group_rows:
                group_frame = pd.DataFrame(
                    group_rows
                )

                st.dataframe(
                    group_frame.style.format(
                        {
                            "Net/OI": "{:+.2%}",
                            "Net/OI Percentile": "{:.0f}",
                            "1W Δ Net/OI": "{:+.2%}",
                            "2W Δ Net/OI": "{:+.2%}",
                            "4W Δ Net/OI": "{:+.2%}",
                            "4W Δ Long/OI": "{:+.2%}",
                            "4W Δ Short/OI": "{:+.2%}",
                        },
                        na_rep="—",
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            if report_type == "tff":
                st.caption(
                    "TFF: Dealer / Intermediary = Intermediary-Kontext; "
                    "Asset Manager = institutioneller Block; Leveraged Funds = Momentum/Speculative."
                )
            else:
                st.caption(
                    "Disaggregated: Producer/Merchant = Commercial/Hedger; "
                    "Managed Money = Momentum/Speculative; Nonreportables = residualer/konträrer Kontext."
                )


with fx_tab:
    section_line(
        "FX Relative COT · Relative Setup Fingerprint",
        "positive Werte unterstützen die Base-Währung relativ zur Quote-Währung",
    )

    pair_options = list(
        FX_PAIRS.keys()
    )

    preferred_pair = st.session_state.get(
        "fx_relative_analog_pair"
    )

    pair_index = (
        pair_options.index(
            preferred_pair
        )
        if preferred_pair in pair_options
        else 0
    )

    pair = st.selectbox(
        "FX-Paar",
        pair_options,
        index=pair_index,
        key="adv_fx_relative_pair",
    )

    spec = FX_PAIRS[
        pair
    ]

    base = spec[
        "base"
    ]
    quote = spec[
        "quote"
    ]
    ticker = spec[
        "ticker"
    ]

    price_start = (
        pd.Timestamp.today()
        .normalize()
        - pd.DateOffset(
            years=35
        )
    )

    with st.spinner(
        f"{pair}: Relative COT Fingerprint wird geladen …"
    ):
        prices = load_prices(
            ticker,
            start=price_start,
        )

        report_type = primary_report_for_asset_class(
            "Currencies"
        )

        base_cot = pd.DataFrame()
        quote_cot = pd.DataFrame()

        if base != "USD":
            (
                base_cot,
                _,
            ) = _load_currency_cot(
                base,
                report_type,
            )

        if quote != "USD":
            (
                quote_cot,
                _,
            ) = _load_currency_cot(
                quote,
                report_type,
            )

    missing_leg = (
        (
            base != "USD"
            and base_cot.empty
        )
        or (
            quote != "USD"
            and quote_cot.empty
        )
    )

    if (
        prices is None
        or prices.empty
        or missing_leg
    ):
        st.warning(
            "Für dieses FX-Paar ist aktuell keine ausreichende Preis-/COT-Historie verfügbar."
        )
    else:
        result = analyze_fx_relative_analogs(
            prices,
            pair=pair,
            base_cot=base_cot,
            quote_cot=quote_cot,
            top_n=8,
            min_spacing_weeks=13,
            exclude_recent_weeks=26,
            outcome_horizon_weeks=8,
        )

        if not result.get(
            "available"
        ):
            st.warning(
                result.get(
                    "reason",
                    "FX Relative Fingerprint nicht verfügbar.",
                )
            )
        else:
            current = result[
                "current"
            ]

            context_strip(
                [
                    (
                        "FX-Paar",
                        pair,
                    ),
                    (
                        "Preis-Proxy",
                        ticker,
                    ),
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
                        "COT Snapshot",
                        pd.Timestamp(
                            current[
                                "report_date"
                            ]
                        ).date().isoformat(),
                    ),
                    (
                        "Verfügbar seit",
                        pd.Timestamp(
                            current[
                                "availability_date"
                            ]
                        ).date().isoformat(),
                    ),
                ]
            )

            p1, p2, p3, p4 = st.columns(
                4
            )

            with p1:
                metric_card(
                    "PRICE 4W",
                    _pct(
                        current.get(
                            "price_return_4w"
                        )
                    ),
                    f"{pair} · {current.get('close', np.nan):,.4f}",
                )

            with p2:
                metric_card(
                    "PRICE 13W",
                    _pct(
                        current.get(
                            "price_return_13w"
                        )
                    ),
                    "mittelfristige Paarbewegung",
                )

            with p3:
                metric_card(
                    "DRAWDOWN 26W",
                    _pct(
                        current.get(
                            "price_drawdown_26w"
                        )
                    ),
                    "Abstand zum 26W-Hoch",
                )

            with p4:
                metric_card(
                    "VS. MA26",
                    _pct(
                        current.get(
                            "price_vs_ma26"
                        )
                    ),
                    "Paar relativ zum 26W-Mittel",
                )

            rows = []

            for group in current.get(
                "groups",
                [],
            ):
                rows.append(
                    {
                        "Gruppe": group[
                            "group"
                        ],
                        "Rolle": group[
                            "role"
                        ],
                        "Relative Net/OI": group.get(
                            "relative_net_oi"
                        ),
                        "Relative Position": group.get(
                            "relative_percentile"
                        ),
                        "1W Relative Flow": group.get(
                            "relative_delta_1w"
                        ),
                        "2W Relative Flow": group.get(
                            "relative_delta_2w"
                        ),
                        "4W Relative Flow": group.get(
                            "relative_delta_4w"
                        ),
                    }
                )

            if rows:
                relative_frame = pd.DataFrame(
                    rows
                )

                st.dataframe(
                    relative_frame.style.format(
                        {
                            "Relative Net/OI": "{:+.2%}",
                            "Relative Position": "{:+.2f}",
                            "1W Relative Flow": "{:+.2%}",
                            "2W Relative Flow": "{:+.2%}",
                            "4W Relative Flow": "{:+.2%}",
                        },
                        na_rep="—",
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            if base == "USD":
                st.caption(
                    f"{pair}: {quote}-Future wird für die Paar-Richtung invertiert."
                )
            elif quote == "USD":
                st.caption(
                    f"{pair}: {base}-Future wird direkt in Paar-Richtung verwendet."
                )
            else:
                st.caption(
                    f"{pair}: Relative COT = {base}-COT minus {quote}-COT."
                )

            st.caption(
                "Kein DXY-COT wird künstlich als bilaterales USD-Leg verwendet. "
                "Dealer / Intermediary bleibt Intermediary-Kontext; Nonreportables bleiben residualer/konträrer Kontext."
            )
