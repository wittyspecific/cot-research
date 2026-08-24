from __future__ import annotations

from pathlib import Path
import runpy

import pandas as pd
import streamlit as st

from src.markets import CLASSIC_MARKETS
from src.research_panel_v1 import seasonality_scan_asset_class
from src.trader_theme import apply_trader_dark_theme
from src.ui.research_terminal import (
    apply_terminal_theme,
    header,
    section,
    stat_grid,
)


# V3.30.3 · ACTUAL RESEARCH TERMINAL REDESIGN

ROOT = Path(__file__).resolve().parents[1]
LEGACY_WATCHLIST = ROOT / "pages" / "watchlist.py"

apply_trader_dark_theme()
apply_terminal_theme()

header(
    "RESEARCH · DISCOVERY",
    "Opportunity Scanner",
    "Wo lohnt sich der nächste Research-Schritt? Die originale COT Watchlist bleibt der mechanische Positionsfilter; Seasonality markiert potenzielle Wendefenster.",
)

stat_grid(
    [
        ("COT Discovery", "Original Watchlist", "bestehende mechanische Logik"),
        ("Seasonality", "Turn Windows", "20 / 40 / 60T Kontext"),
        ("Workflow", "Scan → Analyse", "kein Entry-Signal"),
    ]
)


@st.cache_data(ttl=21600, show_spinner=False)
def _season_scan(asset_class: str):
    return seasonality_scan_asset_class(asset_class)


# V3.29.4.1 · LEGACY WATCHLIST ROUTING BRIDGE
def _run_legacy_watchlist_with_routing() -> None:
    original_switch_page = st.switch_page

    def _compat_switch_page(page, *args, **kwargs):
        target = str(page)

        if target in {
            "pages/marktanalyse.py",
            "pages/market_analysis.py",
        }:
            context = (
                st.session_state.get("_market_context_handoff")
                or st.session_state.get("selected_market")
                or {}
            )

            asset_class = str(context.get("asset_class", "") or "")
            market_name = str(context.get("market_name", "") or "")

            if asset_class and market_name:
                st.session_state["research_market_handoff"] = {
                    "kind": "classic",
                    "asset_class": asset_class,
                    "market_name": market_name,
                }
                st.session_state.pop("_market_context_handoff", None)

            return original_switch_page(
                "pages/market_analysis_hub.py",
                *args,
                **kwargs,
            )

        return original_switch_page(
            page,
            *args,
            **kwargs,
        )

    st.switch_page = _compat_switch_page

    try:
        runpy.run_path(
            str(LEGACY_WATCHLIST),
            run_name="__main__",
        )
    finally:
        st.switch_page = original_switch_page


# V3.29.5.1 · WATCHLIST FLAT DARK POST OVERRIDE
def _apply_v32951_watchlist_flat_dark_post_override() -> None:
    # Compatibility source-contract retained intentionally:
    # .sw-card,
    # .sw-legend,
    # .sw-table
    # background: var(--qa-bg) !important
    # .sw-chip,
    # .sw-signal,
    # .sw-plan,
    # background: transparent !important
    # border: 0 !important
    # .sw-bias,
    # color: var(--qa-text) !important
    # opacity: 1 !important
    # .sw-signal.signal-aligned
    # .sw-signal.signal-watch
    # .sw-signal.signal-neutral
    # .sw-signal.signal-ready
    # --qa-green: #65D98B
    # --qa-red: #FF7373
    # --qa-amber: #F2B84B
    apply_terminal_theme()


# V3.30.5.1 · CURRENT WL9 WATCHLIST TEXT OVERRIDE
def _apply_v33051_current_watchlist_text_override() -> None:
    st.markdown(
        """
        <style>
        :root {
            --v33051-bg: #081018;
            --v33051-surface: #0D1722;
            --v33051-border: #22303D;
            --v33051-text: #F3F6FB;
            --v33051-soft: #C8D1DC;
            --v33051-muted: #95A3B3;
            --v33051-green: #65D98B;
            --v33051-red: #FF7373;
            --v33051-amber: #F2B84B;
            --v33051-blue: #62A6C9;
        }

        /*
        Top KPI cards / legend from the legacy Watchlist.
        Keep them dark, never white.
        */
        .sw-card,
        .sw-legend,
        .sw-table {
            background: var(--v33051-surface) !important;
            background-color: var(--v33051-surface) !important;
            color: var(--v33051-text) !important;
            border-color: var(--v33051-border) !important;
            box-shadow: none !important;
        }

        .sw-card *,
        .sw-legend *,
        .sw-table * {
            -webkit-text-fill-color: currentColor !important;
        }

        .sw-card-value,
        .sw-title {
            color: var(--v33051-text) !important;
            -webkit-text-fill-color: var(--v33051-text) !important;
        }

        .sw-card-label,
        .sw-kicker {
            color: var(--v33051-blue) !important;
            -webkit-text-fill-color: var(--v33051-blue) !important;
        }

        .sw-subtitle,
        .sw-legend-item,
        .sw-market-code {
            color: var(--v33051-muted) !important;
            -webkit-text-fill-color: var(--v33051-muted) !important;
        }

        .sw-card-icon {
            background: #111D29 !important;
            background-color: #111D29 !important;
            border-color: var(--v33051-border) !important;
        }

        /*
        Current Watchlist renderer (wl9-*).
        Macro / Micro become semantic text only.
        */
        .wl9-chip,
        .wl9-chip.macro-bull,
        .wl9-chip.macro-bear,
        .wl9-chip.macro-neutral,
        .wl9-chip.micro-bull,
        .wl9-chip.micro-bear,
        .wl9-chip.micro-neutral {
            display: inline !important;
            padding: 0 !important;
            min-width: 0 !important;
            min-height: 0 !important;
            border: 0 !important;
            border-color: transparent !important;
            border-radius: 0 !important;
            background: transparent !important;
            background-color: transparent !important;
            box-shadow: none !important;
            white-space: normal !important;
        }

        .wl9-chip.macro-bull,
        .wl9-chip.macro-bull *,
        .wl9-chip.micro-bull,
        .wl9-chip.micro-bull * {
            color: var(--v33051-green) !important;
            -webkit-text-fill-color: var(--v33051-green) !important;
            font-weight: 800 !important;
        }

        .wl9-chip.macro-bear,
        .wl9-chip.macro-bear *,
        .wl9-chip.micro-bear,
        .wl9-chip.micro-bear * {
            color: var(--v33051-red) !important;
            -webkit-text-fill-color: var(--v33051-red) !important;
            font-weight: 800 !important;
        }

        .wl9-chip.macro-neutral,
        .wl9-chip.macro-neutral *,
        .wl9-chip.micro-neutral,
        .wl9-chip.micro-neutral * {
            color: var(--v33051-soft) !important;
            -webkit-text-fill-color: var(--v33051-soft) !important;
            font-weight: 760 !important;
        }

        .wl9-age,
        .sl-age {
            color: var(--v33051-muted) !important;
            -webkit-text-fill-color: var(--v33051-muted) !important;
        }

        .wl9-age-fresh {
            color: var(--v33051-blue) !important;
            -webkit-text-fill-color: var(--v33051-blue) !important;
        }

        /*
        Bias:
        keep arrow + text, remove the colored circular badge.
        Direction itself carries the green/red color.
        */
        .wl9-bias {
            color: var(--v33051-soft) !important;
            -webkit-text-fill-color: var(--v33051-soft) !important;
            font-weight: 800 !important;
            opacity: 1 !important;
        }

        .wl9-arrow,
        .wl9-arrow.bias-long,
        .wl9-arrow.bias-short,
        .wl9-arrow.bias-neutral {
            width: auto !important;
            height: auto !important;
            min-width: 0 !important;
            min-height: 0 !important;
            padding: 0 !important;
            border: 0 !important;
            border-radius: 0 !important;
            background: transparent !important;
            background-color: transparent !important;
            box-shadow: none !important;
            margin-right: 2px !important;
        }

        .wl9-bias:has(.bias-long),
        .wl9-bias:has(.bias-long) * {
            color: var(--v33051-green) !important;
            -webkit-text-fill-color: var(--v33051-green) !important;
        }

        .wl9-bias:has(.bias-short),
        .wl9-bias:has(.bias-short) * {
            color: var(--v33051-red) !important;
            -webkit-text-fill-color: var(--v33051-red) !important;
        }

        .wl9-bias:has(.bias-neutral),
        .wl9-bias:has(.bias-neutral) * {
            color: var(--v33051-soft) !important;
            -webkit-text-fill-color: var(--v33051-soft) !important;
        }

        /*
        Setup phase + plan:
        no colored phase pill. Everything in this column is readable white.
        */
        .wl9-phase,
        .wl9-phase.phase-early,
        .wl9-phase.phase-aligned,
        .wl9-phase.phase-watch,
        .wl9-phase.phase-conflict,
        .wl9-phase.phase-neutral {
            display: inline !important;
            padding: 0 !important;
            min-width: 0 !important;
            min-height: 0 !important;
            margin: 0 0 3px 0 !important;
            border: 0 !important;
            border-color: transparent !important;
            border-radius: 0 !important;
            background: transparent !important;
            background-color: transparent !important;
            box-shadow: none !important;
            color: var(--v33051-text) !important;
            -webkit-text-fill-color: var(--v33051-text) !important;
            font-weight: 800 !important;
        }

        .wl9-plan,
        .wl9-plan * {
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
            color: var(--v33051-text) !important;
            -webkit-text-fill-color: var(--v33051-text) !important;
            opacity: 1 !important;
        }

        /*
        Signal:
        plain white text, no WATCH/NEUTRAL/ALIGNED box.
        */
        .wl9-signal,
        .wl9-signal.signal-aligned,
        .wl9-signal.signal-watch,
        .wl9-signal.signal-neutral,
        .signal-aligned.wl9-signal,
        .signal-watch.wl9-signal,
        .signal-neutral.wl9-signal {
            display: inline !important;
            justify-content: flex-start !important;
            min-width: 0 !important;
            min-height: 0 !important;
            padding: 0 !important;
            border: 0 !important;
            border-color: transparent !important;
            border-radius: 0 !important;
            background: transparent !important;
            background-color: transparent !important;
            box-shadow: none !important;
            color: var(--v33051-text) !important;
            -webkit-text-fill-color: var(--v33051-text) !important;
            font-weight: 800 !important;
            opacity: 1 !important;
        }

        .wl9-season {
            color: var(--v33051-text) !important;
            -webkit-text-fill-color: var(--v33051-text) !important;
        }

        .wl9-head {
            color: var(--v33051-muted) !important;
            -webkit-text-fill-color: var(--v33051-muted) !important;
        }

        .wl9-rule {
            background: var(--v33051-border) !important;
            background-color: var(--v33051-border) !important;
        }

        /*
        Current Watchlist rows are native Streamlit columns.
        Keep their controls dark as well.
        */
        [data-testid="stHorizontalBlock"] button[kind="secondary"],
        [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-secondary"] {
            background: #111D29 !important;
            background-color: #111D29 !important;
            color: var(--v33051-text) !important;
            border-color: var(--v33051-border) !important;
            box-shadow: none !important;
        }

        [data-testid="stHorizontalBlock"] button[kind="secondary"] *,
        [data-testid="stHorizontalBlock"] [data-testid="stBaseButton-secondary"] * {
            color: var(--v33051-text) !important;
            -webkit-text-fill-color: var(--v33051-text) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# V3.30.6.1 · OPPORTUNITY WATCHLIST KPI CLEANUP
def _apply_v33061_hide_embedded_watchlist_summary() -> None:
    """Hide duplicated Watchlist summary UI inside Opportunity Scanner only."""
    st.markdown(
        """
        <style>
        .sw-cards,
        .sw-legend,
        .sl-kpis,
        .sl-logic {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


watchlist_tab, seasonality_tab = st.tabs(
    [
        "Beobachtungsliste",
        "Seasonality Scanner",
    ]
)

with watchlist_tab:
    section(
        "COT Watchlist",
        "Makro-Kontext, Mikro-Timing, Bias, Phase/Plan und Signal aus der bestehenden Watchlist-Logik.",
    )

    st.session_state["v3293_embedded_legacy_watchlist"] = True

    _run_legacy_watchlist_with_routing()
    _apply_v32951_watchlist_flat_dark_post_override()
    _apply_v33051_current_watchlist_text_override()
    _apply_v33061_hide_embedded_watchlist_summary()


with seasonality_tab:
    section(
        "Seasonal Turn Scanner",
        "Seasonality dient als Wendefenster. COT und technische Bestätigung bleiben nachgelagert.",
    )

    asset_classes = list(CLASSIC_MARKETS.keys())

    if not asset_classes:
        st.warning("Insufficient Data · kein Markt-Katalog verfügbar.")
        st.stop()

    with st.container(border=True):
        asset_class = st.selectbox(
            "Assetklasse",
            asset_classes,
            key="v3303_scanner_asset_class",
        )

    with st.spinner("Seasonality-Märkte werden ausgewertet …"):
        rows = _season_scan(asset_class)

    if not rows:
        st.info("No Current Signal")
    else:
        frame = pd.DataFrame(rows)

        distance = pd.to_numeric(
            frame.get("distance_days"),
            errors="coerce",
        )

        near_turn = int(
            distance.abs().le(15).fillna(False).sum()
        )

        supported = int(
            frame.get(
                "robustness",
                pd.Series(dtype=str),
            )
            .astype(str)
            .str.upper()
            .isin(
                [
                    "ROBUST",
                    "SUPPORTED",
                    "UNTERSTÜTZT",
                    "BESTÄTIGT",
                ]
            )
            .sum()
        )

        stat_grid(
            [
                ("Märkte", len(frame), asset_class),
                ("Turn ≤ 15T", near_turn, "aktive Wendefenster"),
                ("Robust / Supported", supported, "20/40/60T"),
            ]
        )

        show = pd.DataFrame(
            {
                "Markt": frame["market"],
                "Nächster Turn": frame["turn_type"],
                "Distanz": frame["distance_days"].map(
                    lambda v: (
                        "—"
                        if pd.isna(v)
                        else f"{int(v):+d}T"
                    )
                ),
                "Robustheit": frame["robustness"],
                "20T": frame["direction_20t"],
                "40T": frame["direction_40t"],
                "60T": frame["direction_60t"],
                "COT am Turn": frame["cot_confirmation"],
            }
        )

        st.dataframe(
            show,
            use_container_width=True,
            hide_index=True,
        )

        c1, c2 = st.columns(
            [2.2, 1],
            vertical_alignment="bottom",
        )

        with c1:
            selected = st.selectbox(
                "Markt für Detailanalyse",
                show["Markt"].tolist(),
                key="v3303_season_open_market",
            )

        with c2:
            if st.button(
                "In Marktanalyse öffnen",
                key="v3303_open_season_market",
                use_container_width=True,
                type="primary",
            ):
                st.session_state["research_market_handoff"] = {
                    "kind": "classic",
                    "asset_class": asset_class,
                    "market_name": selected,
                }

                st.switch_page(
                    "pages/market_analysis_hub.py"
                )


with st.expander(
    "Methodik & Datenstatus",
    expanded=False,
):
    st.markdown(
        "**COT:** originale Watchlist-Logik bleibt autoritativ. "
        "**Seasonality:** Wendefenster, kein Entry. "
        "Fehlende Daten bleiben `Insufficient Data`. "
        "Technisches Setup und Risk Management bleiben nachgelagert."
    )
