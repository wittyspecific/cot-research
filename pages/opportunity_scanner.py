from __future__ import annotations

from pathlib import Path
import runpy

import pandas as pd
import streamlit as st

from src.markets import CLASSIC_MARKETS
from src.research_panel_v1 import (
    seasonality_scan_asset_class,
)
from src.trader_theme import (
    apply_trader_dark_theme,
    render_page_header,
)


# V3.29.3 · LEGACY WATCHLIST LOGIC RESTORED
# The old Watchlist remains the authoritative COT discovery layer.
# It is executed unchanged inside the Opportunity Scanner.
# No replacement score or parallel watchlist model is used here.

ROOT = Path(__file__).resolve().parents[1]
LEGACY_WATCHLIST = ROOT / "pages" / "watchlist.py"


apply_trader_dark_theme()

render_page_header(
    "RESEARCH · DISCOVERY",
    "Opportunity Scanner",
    (
        "Die bewährte Beobachtungslisten-Logik ist wieder der primäre "
        "COT-Discovery-Layer. Seasonality bleibt als separates Wendefenster."
    ),
)

st.caption(
    "V3.29.3 · Beobachtungsliste = originale Watchlist-Logik · "
    "keine neue Ersatzbewertung"
)


if not LEGACY_WATCHLIST.exists():
    st.error(
        "Die originale Beobachtungsliste ist nicht verfügbar."
    )
    st.stop()


watchlist_tab, seasonality_tab = st.tabs(
    [
        "Beobachtungsliste",
        "Seasonality Scanner",
    ]
)


with watchlist_tab:
    st.session_state[
        "v3293_embedded_legacy_watchlist"
    ] = True

    # Important:
    # Execute the existing Watchlist page itself instead of recreating its
    # ranking / macro-micro / signal-age logic in a second model.
    #
    # This intentionally preserves the exact existing watchlist mechanics.
    runpy.run_path(
        str(LEGACY_WATCHLIST),
        run_name="__main__",
    )


@st.cache_data(
    ttl=21600,
    show_spinner=False,
)
def _season_scan(
    asset_class: str,
):
    return seasonality_scan_asset_class(
        asset_class
    )


with seasonality_tab:
    st.markdown(
        "### Saisonale Wendefenster"
    )

    st.caption(
        "Seasonality bleibt Timing-Kontext. "
        "Sie ersetzt nicht die Beobachtungslisten-Entscheidungslogik."
    )

    asset_classes = list(
        CLASSIC_MARKETS.keys()
    )

    if not asset_classes:
        st.info(
            "Insufficient Data"
        )
    else:
        asset_class = st.selectbox(
            "Assetklasse",
            asset_classes,
            key="v3293_season_asset_class",
        )

        with st.spinner(
            "Seasonality-Märkte werden ausgewertet …"
        ):
            rows = _season_scan(
                asset_class
            )

        if not rows:
            st.info(
                "No Current Signal"
            )
        else:
            frame = pd.DataFrame(
                rows
            )

            show = pd.DataFrame(
                {
                    "Markt": frame[
                        "market"
                    ],
                    "Nächster Turn": frame[
                        "turn_type"
                    ],
                    "Distanz": frame[
                        "distance_days"
                    ].map(
                        lambda value: (
                            "—"
                            if pd.isna(
                                value
                            )
                            else f"{int(value):+d}T"
                        )
                    ),
                    "Robustheit": frame[
                        "robustness"
                    ],
                    "20T": frame[
                        "direction_20t"
                    ],
                    "40T": frame[
                        "direction_40t"
                    ],
                    "60T": frame[
                        "direction_60t"
                    ],
                    "COT am Turn": frame[
                        "cot_confirmation"
                    ],
                }
            )

            st.dataframe(
                show,
                use_container_width=True,
                hide_index=True,
            )

            c1, c2 = st.columns(
                [
                    2,
                    1,
                ]
            )

            with c1:
                selected = st.selectbox(
                    "Markt für Detailanalyse",
                    show[
                        "Markt"
                    ].tolist(),
                    key="v3293_season_open_market",
                )

            with c2:
                st.write("")
                st.write("")

                if st.button(
                    "In Marktanalyse öffnen",
                    key="v3293_open_season_market",
                    use_container_width=True,
                ):
                    st.session_state[
                        "research_market_handoff"
                    ] = {
                        "kind": "classic",
                        "asset_class": asset_class,
                        "market_name": selected,
                    }

                    st.switch_page(
                        "pages/market_analysis_hub.py"
                    )


with st.expander(
    "Methodik",
    expanded=False,
):
    st.markdown(
        """
        **Beobachtungsliste:** verwendet wieder direkt die bestehende
        `pages/watchlist.py` und damit deren originale Ranking-, Macro-/Micro-COT-,
        Signal-Age- und Trigger-Logik.

        **Seasonality Scanner:** bleibt ein unabhängiges Wendefenster und
        verändert die Watchlist-Klassifikation nicht.

        Die neue V3.29-Research-Struktur bleibt bestehen; geändert wurde nur,
        welche Logik im Discovery-Layer maßgeblich ist.
        """
    )
