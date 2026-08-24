from __future__ import annotations

import pandas as pd
import streamlit as st

from src.research_panel_v1 import currency_strength_snapshot
from src.trader_theme import apply_trader_dark_theme
from src.ui.research_terminal import (
    apply_terminal_theme,
    header,
    section,
    stat_grid,
)


# V3.30.3 · ACTUAL RESEARCH TERMINAL REDESIGN

apply_trader_dark_theme()
apply_terminal_theme()

header(
    "RESEARCH · RELATIVE FX",
    "Währungsstärke",
    "Stärke wird relativ gelesen: strukturelle COT-Positionierung dient der Paarselektion, nicht dem Entry.",
)


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def _snapshot():
    return currency_strength_snapshot()


with st.spinner(
    "Relative Currency-COT-Struktur wird geladen …"
):
    ranking_rows, pair_rows = _snapshot()


rank_tab, pair_tab = st.tabs(
    [
        "Currency Ranking",
        "Pair Opportunities",
    ]
)


with rank_tab:
    section(
        "Currency Ranking",
        "Stärkste gegen schwächste strukturelle Währung — transparent und ohne erfundenen USD-COT-Report.",
    )

    if not ranking_rows:
        st.info(
            "Insufficient Data"
        )
    else:
        ranking = pd.DataFrame(
            ranking_rows
        )

        strongest = ranking.iloc[0]
        weakest = ranking.iloc[-1]

        spread = (
            float(
                strongest["Relative COT-Stärke"]
                or 0
            )
            - float(
                weakest["Relative COT-Stärke"]
                or 0
            )
        )

        stat_grid(
            [
                (
                    "Stärkste Währung",
                    strongest["Währung"],
                    strongest["Struktureller Bias"],
                ),
                (
                    "Schwächste Währung",
                    weakest["Währung"],
                    weakest["Struktureller Bias"],
                ),
                (
                    "Relative Spreizung",
                    f"{spread:.0f}",
                    "größer = klarere relative Struktur",
                ),
            ]
        )

        st.dataframe(
            ranking.style.format(
                {
                    "Relative COT-Stärke": "{:+.0f}",
                    "Persistenz": "{:.0%}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )


with pair_tab:
    section(
        "Pair Opportunities",
        "Base minus Quote. Favor und Watch priorisieren Research — nicht automatische Trades.",
    )

    if not pair_rows:
        st.info(
            "No Current Signal"
        )
    else:
        pairs = pd.DataFrame(
            pair_rows
        )

        favorable = pairs[
            pairs["Alignment"].isin(
                [
                    "FAVOR",
                    "WATCH",
                ]
            )
        ]

        favor_count = int(
            pairs["Alignment"]
            .astype(str)
            .eq("FAVOR")
            .sum()
        )

        watch_count = int(
            pairs["Alignment"]
            .astype(str)
            .eq("WATCH")
            .sum()
        )

        stat_grid(
            [
                (
                    "Pairs",
                    len(pairs),
                    "gescannte Relative-Strukturen",
                ),
                (
                    "Favor",
                    favor_count,
                    "höchste Konfluenz",
                ),
                (
                    "Watch",
                    watch_count,
                    "Research beobachten",
                ),
            ]
        )

        st.dataframe(
            pairs.style.format(
                {
                    "Stärke-Differenz": "{:+.0f}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

        choices = (
            favorable["Pair"].tolist()
            if not favorable.empty
            else pairs["Pair"].tolist()
        )

        c1, c2 = st.columns(
            [2.2, 1],
            vertical_alignment="bottom",
        )

        with c1:
            selected = st.selectbox(
                "Pair für Marktanalyse",
                choices,
                key="v3290_currency_pair_open",
            )

        with c2:
            if st.button(
                "In Marktanalyse öffnen",
                key="v3290_currency_open_button",
                use_container_width=True,
                type="primary",
            ):
                st.session_state["research_market_handoff"] = {
                    "kind": "fx",
                    "pair": selected,
                }

                st.switch_page(
                    "pages/market_analysis_hub.py"
                )


with st.expander(
    "Methodik & Einschränkungen",
    expanded=False,
):
    st.markdown(
        "Nicht-USD-Währungen werden über ihren TFF-Future relativ zum USD gelesen. "
        "Pair Opportunity = **Base minus Quote**. USD ist Null-Basis, kein synthetischer Report. "
        "Fehlende Daten werden nicht ersetzt."
    )
