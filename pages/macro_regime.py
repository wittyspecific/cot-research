from __future__ import annotations

import pandas as pd
import streamlit as st

from src.research_panel_v1 import (
    MacroRegimeState,
    macro_regime_snapshot,
)
from src.trader_theme import apply_trader_dark_theme
from src.ui.research_terminal import (
    apply_terminal_theme,
    header,
    regime_path,
    section,
    stat_grid,
)


# V3.30.3 · ACTUAL RESEARCH TERMINAL REDESIGN

apply_trader_dark_theme()
apply_terminal_theme()

header(
    "RESEARCH · STRATEGIC REGIME",
    "Makro-Regime",
    "Business Cycle, Macro Momentum und Positionierung werden hier als strategischer Regime-Kontext gelesen. Keine Entry-Mechanik.",
)


@st.cache_data(
    ttl=21600,
    show_spinner=False,
)
def _load_macro(
    force_refresh: bool = False,
):
    return macro_regime_snapshot(
        force_refresh=force_refresh
    ).to_dict()


_, refresh_col = st.columns(
    [5, 1],
    vertical_alignment="bottom",
)

with refresh_col:
    refresh = st.button(
        "Makro aktualisieren",
        use_container_width=True,
    )

if refresh:
    st.cache_data.clear()


with st.spinner(
    "Makro- und Cross-Asset-Regime wird geladen …"
):
    payload = _load_macro(
        refresh
    )


state = MacroRegimeState(
    **{
        k: v
        for k, v in payload.items()
        if k in MacroRegimeState.__dataclass_fields__
    }
)


if not state.available:
    st.warning(
        state.reason
        or "Insufficient Data"
    )


tabs = st.tabs(
    [
        "Overview",
        "Business Cycle",
        "Macro × COT",
        "Risk Conditions",
    ]
)


with tabs[0]:
    stat_grid(
        [
            (
                "Business Cycle",
                state.business_cycle_state,
                "strategisches Regime",
            ),
            (
                "Macro Momentum",
                state.macro_momentum_state,
                "Dynamik / Veränderung",
            ),
            (
                "COT Regime",
                state.cot_regime_state,
                state.alignment,
            ),
            (
                "Macro × COT State",
                state.macro_cot_state,
                state.trading_regime,
            ),
            (
                "Next-Regime Pressure",
                (
                    "—"
                    if state.transition_pressure_score is None
                    else f"{state.transition_pressure_score:.0f}/100"
                ),
                state.transition_pressure_label,
            ),
        ]
    )

    section(
        "Regime-Pfad",
        "Aktueller Business-Cycle-State innerhalb der strategischen Sequenz.",
    )

    regime_path(
        state.business_cycle_state
    )

    section(
        "Was bestätigt das nächste Regime?",
        f"Nächste beobachtete Richtung: {state.next_regime_direction}",
    )

    confirm = pd.DataFrame(
        state.transition_confirmation
    )

    if confirm.empty:
        st.caption(
            "Insufficient Data"
        )
    else:
        cols = [
            x
            for x in (
                "trigger",
                "status",
                "why",
            )
            if x in confirm.columns
        ]

        st.dataframe(
            confirm[cols]
            .rename(
                columns={
                    "trigger": "Trigger",
                    "status": "Status",
                    "why": "Warum",
                }
            )
            .head(7),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander(
        "Why this regime?",
        expanded=False,
    ):
        st.write(
            {
                "Business Cycle": state.business_cycle_state,
                "Macro Momentum": state.macro_momentum_state,
                "Macro × COT": state.macro_cot_state,
                "Alignment": state.alignment,
            }
        )


with tabs[1]:
    raw = dict(
        state.raw_result.get(
            "macro_result",
            {},
        )
        or {}
    )

    leading = dict(
        raw.get(
            "leading",
            {},
        )
        or {}
    )
    coincident = dict(
        raw.get(
            "coincident",
            {},
        )
        or {}
    )
    lagging = dict(
        raw.get(
            "lagging",
            {},
        )
        or {}
    )

    section(
        "Business Cycle",
        "Leading → Coincident → Lagging. Sequenz statt gleichgewichteter Datensammlung.",
    )

    stat_grid(
        [
            (
                "Zyklus",
                state.business_cycle_state,
                "strategischer Regime-State",
            ),
            (
                "Momentum",
                state.macro_momentum_state,
                "Velocity + zweite Ableitung",
            ),
            (
                "Leading",
                (
                    "—"
                    if leading.get("distance") is None
                    else f"{float(leading['distance']):+.2f}"
                ),
                "Distance vs. Equilibrium",
            ),
            (
                "Coincident",
                (
                    "—"
                    if coincident.get("distance") is None
                    else f"{float(coincident['distance']):+.2f}"
                ),
                "aktuelle Wirtschaftsaktivität",
            ),
        ]
    )

    table = pd.DataFrame(
        [
            {
                "Tier": "Leading",
                "Distance": leading.get("distance"),
                "13W Slope": leading.get("slope_13w"),
            },
            {
                "Tier": "Coincident",
                "Distance": coincident.get("distance"),
                "13W Slope": coincident.get("slope_13w"),
            },
            {
                "Tier": "Lagging",
                "Distance": lagging.get("distance"),
                "13W Slope": lagging.get("slope_13w"),
            },
        ]
    )

    st.dataframe(
        table.style.format(
            {
                "Distance": "{:+.2f}",
                "13W Slope": "{:+.2f}",
            },
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander(
        "Macro Evidence",
        expanded=False,
    ):
        st.json(
            {
                "leading": leading,
                "coincident": coincident,
                "lagging": lagging,
            }
        )


with tabs[2]:
    section(
        "Macro × COT",
        "Makro liefert die strategische Richtung; Positionierung kann Übergänge vorwegnehmen oder widersprechen.",
    )

    stat_grid(
        [
            (
                "Macro × COT",
                state.macro_cot_state,
                state.alignment,
            ),
            (
                "Trading Regime",
                state.trading_regime,
                "strategischer Bias",
            ),
            (
                "Risk-Off Breadth",
                (
                    "—"
                    if state.risk_off_breadth is None
                    else f"{state.risk_off_breadth:.0%}"
                ),
                (
                    "Persistenz —"
                    if state.risk_off_persistence is None
                    else f"Persistenz {state.risk_off_persistence:.0%}"
                ),
            ),
            (
                "Risk-On Breadth",
                (
                    "—"
                    if state.risk_on_breadth is None
                    else f"{state.risk_on_breadth:.0%}"
                ),
                (
                    "Persistenz —"
                    if state.risk_on_persistence is None
                    else f"Persistenz {state.risk_on_persistence:.0%}"
                ),
            ),
        ]
    )

    section(
        "Trader Opportunity Map",
        "Marktpräferenzen aus bestehender Macro × COT Engine — keine Entry-Signale.",
    )

    opp = pd.DataFrame(
        state.opportunity_map
    )

    if not opp.empty:
        cols = [
            x
            for x in (
                "market",
                "macro_bias",
                "cot_bias",
                "alignment",
                "setup_type",
                "preference",
            )
            if x in opp.columns
        ]

        st.dataframe(
            opp[cols]
            .rename(
                columns={
                    "market": "Markt",
                    "macro_bias": "Makro",
                    "cot_bias": "COT",
                    "alignment": "Alignment",
                    "setup_type": "Setup",
                    "preference": "Präferenz",
                }
            )
            .head(12),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander(
        "COT Evidence",
        expanded=False,
    ):
        mc = dict(
            state.raw_result.get(
                "macro_cot",
                {},
            )
            or {}
        )

        st.json(
            {
                "rates_positioning": mc.get(
                    "rates_positioning",
                    {},
                ),
                "cross_asset": mc.get(
                    "cross_asset",
                    {},
                ),
            }
        )


with tabs[3]:
    section(
        "Risk Conditions",
        "Liquidität und Duration bleiben Modifier des Regimes, nicht eigenständige Zyklusklassifikatoren.",
    )

    stat_grid(
        [
            (
                "Liquidität",
                state.liquidity_state,
                "Modifier, nicht Zyklus-Richtung",
            ),
            (
                "Treasury Duration",
                state.rates_positioning_state,
                "2Y / 5Y / 10Y / 30Y",
            ),
            (
                "Transition Pressure",
                (
                    "—"
                    if state.transition_pressure_score is None
                    else f"{state.transition_pressure_score:.0f}/100"
                ),
                "Next-Regime Pressure",
            ),
            (
                "Next Watch",
                state.next_regime_direction,
                "keine Rezessionswahrscheinlichkeit",
            ),
        ]
    )

    mc = dict(
        state.raw_result.get(
            "macro_cot",
            {},
        )
        or {}
    )

    with st.expander(
        "Cross-Asset Evidence",
        expanded=False,
    ):
        st.json(
            mc.get(
                "alignment_matrix",
                [],
            )
        )

    with st.expander(
        "Transition Triggers",
        expanded=False,
    ):
        st.json(
            list(
                state.transition_confirmation
            )
        )

    with st.expander(
        "Raw Diagnostics",
        expanded=False,
    ):
        st.json(
            state.raw_result
        )
