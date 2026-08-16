from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.config import (
    COMMERCIAL_RANGE_WEEKS,
    COT_INDEX_WEEKS,
    INDEX_LOWER,
    INDEX_UPPER,
    NET_LOWER_PERCENTILE,
    NET_UPPER_PERCENTILE,
    NET_VALIDATION_WEEKS,
    RELEASE_ACTIVE_WEEKS,
)
from src.style import (
    apply_style,
    context_strip,
    definition,
    empty_state,
    page_header,
    section_line,
)
from src.watchlist import scan_classic_markets
from src.watchlist_seasonality import calculate_market_20y_multi_seasonality


apply_style()


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


def de_date(value):
    if value is None or pd.isna(value):
        return "—"
    return pd.Timestamp(value).strftime("%d.%m.%Y")


def market_name_de(value):
    return MARKET_NAME_DE.get(value, value)


def current_direction(cot_index: float) -> int:
    if not np.isfinite(cot_index):
        return 0
    if cot_index >= INDEX_UPPER:
        return 1
    if cot_index <= INDEX_LOWER:
        return -1
    return 0


def level_label(value: float, low: float, high: float) -> str:
    if not np.isfinite(value):
        return "N/V"
    if value >= high:
        return "HOCH"
    if value <= low:
        return "TIEF"
    return "MITTE"


def confirmation_flags(row) -> dict:
    cot = float(row.get("commercial_index", np.nan))
    comm = float(row.get("commercial_net_percentile", np.nan))
    nc = float(row.get("noncommercial_net_percentile", np.nan))
    retail = float(row.get("retail_net_percentile", np.nan))
    direction = current_direction(cot)

    if direction > 0:
        cot_ok = np.isfinite(cot) and cot >= INDEX_UPPER
        comm_ok = np.isfinite(comm) and comm >= NET_UPPER_PERCENTILE
        nc_ok = np.isfinite(nc) and nc <= NET_LOWER_PERCENTILE
        retail_ok = np.isfinite(retail) and retail <= NET_LOWER_PERCENTILE
    elif direction < 0:
        cot_ok = np.isfinite(cot) and cot <= INDEX_LOWER
        comm_ok = np.isfinite(comm) and comm <= NET_LOWER_PERCENTILE
        nc_ok = np.isfinite(nc) and nc >= NET_UPPER_PERCENTILE
        retail_ok = np.isfinite(retail) and retail >= NET_UPPER_PERCENTILE
    else:
        cot_ok = comm_ok = nc_ok = retail_ok = False

    return {
        "direction": direction,
        "cot_ok": bool(cot_ok),
        "comm_ok": bool(comm_ok),
        "nc_ok": bool(nc_ok),
        "retail_ok": bool(retail_ok),
        "count": (
            int(cot_ok)
            + int(comm_ok)
            + int(nc_ok)
            + int(retail_ok)
        ),
    }


def readable_value(value: float, ok: bool, *, cot: bool = False) -> str:
    if not np.isfinite(value):
        return "—"

    mark = "✓" if ok else "–"

    if cot:
        if value >= INDEX_UPPER:
            level = "EXTREM HOCH"
        elif value <= INDEX_LOWER:
            level = "EXTREM TIEF"
        else:
            level = "MITTE"
    else:
        level = level_label(value, NET_LOWER_PERCENTILE, NET_UPPER_PERCENTILE)

    return f"{mark} {level} · {value:.1f}"


def confirmation_label(count: int) -> str:
    if count >= 4:
        return "4/4 · VOLL"
    if count == 3:
        return "3/4 · STARK"
    if count == 2:
        return "2/4 · TEILWEISE"
    return "1/4 · NUR COT"


def bias_label(direction: int) -> str:
    if direction > 0:
        return "▲ BULLISH"
    if direction < 0:
        return "▼ BÄRISCH"
    return "—"


def build_ranking(all_markets: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for _, row in all_markets.iterrows():
        flags = confirmation_flags(row)

        # Only current COT extremes enter the simple ranking.
        # Releases are kept separately below.
        if flags["direction"] == 0:
            continue

        cot = float(row["commercial_index"])
        comm = float(row["commercial_net_percentile"])
        nc = float(row["noncommercial_net_percentile"])
        retail = float(row["retail_net_percentile"])

        rows.append({
            "_asset_class": row["asset_class"],
            "_market_name": row["market_name"],
            "_symbol": row["symbol"],
            "_ticker": row.get("ticker", ""),
            "_direction": flags["direction"],
            "_confirmations": flags["count"],
            "Markt": f"{market_name_de(row['market_name'])} · {row['symbol']}",
            "Bias": bias_label(flags["direction"]),
            "COT": readable_value(cot, flags["cot_ok"], cot=True),
            "Commercials": readable_value(comm, flags["comm_ok"]),
            "Non-Commercials": readable_value(nc, flags["nc_ok"]),
            "Retail": readable_value(retail, flags["retail_ok"]),
            "Bestätigung": confirmation_label(flags["count"]),
        })

    ranking = pd.DataFrame(rows)
    if ranking.empty:
        return ranking

    # No hidden score. More confirmations first, alphabetical inside a tier.
    ranking = ranking.sort_values(
        ["_confirmations", "_direction", "Markt"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    return ranking


def open_ranked_market(row):
    handoff = {
        "asset_class": row["_asset_class"],
        "market_name": row["_market_name"],
    }
    st.session_state["selected_market"] = handoff
    st.session_state["_market_context_handoff"] = handoff
    st.switch_page("pages/marktanalyse.py")


def render_ranking_table(df: pd.DataFrame, key_prefix: str = "watchlist"):
    if df.empty:
        empty_state(
            "Aktuell befindet sich kein Markt in einem 26W-COT-Extrem.",
            "Die Watchlist zeigt ausschließlich aktuelle Commercial-Extreme.",
        )
        return

    h1, h2, h3, h4, h5, h6, h7, h8 = st.columns(
        [1.75, 0.9, 1.2, 1.25, 1.35, 1.2, 1.2, 1.45],
        gap="small",
    )
    h1.caption("MARKT")
    h2.caption("BIAS")
    h3.caption("COT")
    h4.caption("COMMERCIALS")
    h5.caption("NON-COMM.")
    h6.caption("RETAIL")
    h7.caption("BESTÄTIGUNG")
    h8.caption("SAISON 20/40/60T")

    for idx, row in df.reset_index(drop=True).iterrows():
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(
            [1.75, 0.9, 1.2, 1.25, 1.35, 1.2, 1.2, 1.45],
            gap="small",
            vertical_alignment="center",
        )

        with c1:
            if st.button(
                f"{row['Markt']}  →",
                key=f"{key_prefix}_market_{idx}_{row['_symbol']}",
                width="stretch",
                help="Direkt zur COT Marktanalyse dieses Marktes",
            ):
                open_ranked_market(row)

        with c2:
            bias = str(row["Bias"])
            if "BULLISH" in bias:
                st.markdown(":green[**▲ BULLISH**]")
            elif "BÄRISCH" in bias:
                st.markdown(":red[**▼ BÄRISCH**]")
            else:
                st.write("—")

        with c3:
            st.write(row["COT"])

        with c4:
            st.write(row["Commercials"])

        with c5:
            st.write(row["Non-Commercials"])

        with c6:
            st.write(row["Retail"])

        with c7:
            st.write(row["Bestätigung"])

        with c8:
            season = str(row.get("Saison 20/40/60T", "20· · 40· · 60·"))
            detail = str(row.get("_season_detail", ""))
            st.markdown(f"**{season}**", help=detail or None)

        st.markdown(
            "<div style='height:1px;background:rgba(255,255,255,0.08);margin:2px 0 8px 0;'></div>",
            unsafe_allow_html=True,
        )


def render_release_table(all_markets: pd.DataFrame):
    if all_markets.empty:
        return

    releases = all_markets[all_markets["cycle_phase"] == "RELEASE"].copy()
    if releases.empty:
        st.caption("Aktuell keine aktiven Releases.")
        return

    rows = []
    for _, row in releases.iterrows():
        direction = int(row.get("cycle_direction", 0) or 0)
        weeks = row.get("weeks_since_release", np.nan)
        rows.append({
            "Markt": f"{market_name_de(row['market_name'])} · {row['symbol']}",
            "Vorheriger Bias": bias_label(direction),
            "Release": f"vor {int(weeks)}W" if pd.notna(weeks) else "aktiv",
            "Netto": {
                "CONFIRMED": "BESTÄTIGT",
                "PARTIAL": "TEILWEISE",
                "UNCONFIRMED": "NICHT BESTÄTIGT",
            }.get(
                str(row.get("validation_status")),
                str(row.get("validation_status")),
            ),
        })

    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
    )


page_header(
    "COT Watchlist",
    "COT Watchlist",
    "Welche Märkte zeigen aktuell ein klares bullishes oder bärisches COT-Positionierungsbild?",
    "V3.4.4 · COT + NC-PERZENTIL + SAISON",
)

st.caption(
    "Einfache Vorauswahl für Swing- und Position-Trading. "
    "4/4 bis 1/4 zeigen die Zahl der erfüllten Positionierungsbedingungen. Non-Commercials sind dabei eine zusätzliche, aber nicht statistisch unabhängige Kontextbestätigung."
)

with st.spinner("CFTC-Märkte werden geprüft …"):
    scan = scan_classic_markets(
        cot_weeks=COT_INDEX_WEEKS,
        validation_weeks=NET_VALIDATION_WEEKS,
        range_weeks=COMMERCIAL_RANGE_WEEKS,
        upper=INDEX_UPPER,
        lower=INDEX_LOWER,
        validation_upper=NET_UPPER_PERCENTILE,
        validation_lower=NET_LOWER_PERCENTILE,
        release_active_weeks=RELEASE_ACTIVE_WEEKS,
    )

all_markets = scan["all_markets"].copy()
ranking = build_ranking(all_markets)

if not ranking.empty:
    seasonality_rows = []
    with st.spinner("20J / 20-40-60T-Saisonalität der COT-Extreme wird geprüft …"):
        for _, market_row in ranking.iterrows():
            seasonality_rows.append(
                calculate_market_20y_multi_seasonality(
                    ticker=str(market_row.get("_ticker", "")),
                    cot_direction=int(market_row["_direction"]),
                )
            )

    seasonality_df = pd.DataFrame(seasonality_rows)
    ranking["Saison 20/40/60T"] = seasonality_df["compact"].values
    ranking["_season_support"] = (seasonality_df["overall_rank"] >= 3).astype(bool).values
    ranking["_season_sort"] = seasonality_df["overall_rank"].astype(int).values
    ranking["_season_detail"] = seasonality_df["detail"].values

    # Primary hierarchy remains the transparent COT confirmation count.
    # Seasonality only orders markets inside the same 4/4, 3/4, 2/4 or 1/4 tier.
    ranking = ranking.sort_values(
        ["_confirmations", "_season_sort", "_direction", "Markt"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

fully_confirmed = (
    int((ranking["_confirmations"] == 4).sum())
    if not ranking.empty else 0
)
bullish_count = (
    int((ranking["_direction"] > 0).sum())
    if not ranking.empty else 0
)
bearish_count = (
    int((ranking["_direction"] < 0).sum())
    if not ranking.empty else 0
)
season_supported_count = (
    int(ranking["_season_support"].sum())
    if not ranking.empty and "_season_support" in ranking.columns else 0
)

context_strip(
    [
        ("COT-Report", de_date(scan["latest_report"])),
        ("COT-Extreme", str(len(ranking))),
        ("4/4 bestätigt", str(fully_confirmed)),
        ("Saison unterstützt", str(season_supported_count)),
    ]
)

definition(
    f"4/4 = COT + Commercial-Netto + Non-Commercial-Netto + Retail-Netto passen "
    f"zum selben Reversal-Bias. Bei bullish muss NC historisch tief, bei bearish "
    f"historisch hoch liegen. Commercials und Legacy NC sind mechanisch gekoppelt "
    f"und deshalb nicht als unabhängige Signale zu verstehen. Saison 20/40/60T "
    f"bleibt zusätzliche Confluence und verändert die 1/4–4/4-Bestätigung nicht."
)

section_line(
    "Aktuelle COT-Extreme",
    "4/4 zuerst · NC-Perzentil + Saison als zusätzliche Confluence",
)

st.caption(
    "Auf einen Marktnamen klicken → direkt zur vollständigen COT Marktanalyse. "
    "Saison = letzte 20 abgeschlossene Jahre / nächste 20, 40 und 60 Handelstage."
)

only_season_supported = st.toggle(
    "Nur Märkte mit überwiegend/stabil saisonaler Unterstützung anzeigen",
    value=False,
)

ranking_view = ranking.copy()
if only_season_supported and not ranking_view.empty:
    ranking_view = ranking_view[
        ranking_view["_season_support"]
    ].reset_index(drop=True)

tab_all, tab_bull, tab_bear = st.tabs(["Alle", "Bullish", "Bearish"])

with tab_all:
    render_ranking_table(ranking_view, key_prefix="all")

with tab_bull:
    bull = (
        ranking_view[ranking_view["_direction"] > 0].copy()
        if not ranking_view.empty else ranking_view
    )
    render_ranking_table(bull, key_prefix="bull")

with tab_bear:
    bear = (
        ranking_view[ranking_view["_direction"] < 0].copy()
        if not ranking_view.empty else ranking_view
    )
    render_ranking_table(bear, key_prefix="bear")


with st.expander("Wie wird Bullish / Bearish bestätigt?", expanded=False):
    st.markdown(
        f"""
**Bullish**

- COT-Index: **≥ {INDEX_UPPER}**
- Commercial-Netto: **≥ {NET_UPPER_PERCENTILE}. Perzentil**
- Retail-Netto: **≤ {NET_LOWER_PERCENTILE}. Perzentil**

**Bearish**

- COT-Index: **≤ {INDEX_LOWER}**
- Commercial-Netto: **≤ {NET_LOWER_PERCENTILE}. Perzentil**
- Retail-Netto: **≥ {NET_UPPER_PERCENTILE}. Perzentil**

Die **Range ist bewusst kein Teil dieses Rankings**. Sie bleibt in der
Marktanalyse als zusätzlicher Kontext sichtbar. So wird die Commercial-
Extreminformation nicht mehrfach als vermeintlich unabhängige Bestätigung gezählt.

**Saison 20 / 40 / 60T**

- historische Basis: letzte **20 abgeschlossene Jahre**
- Horizonte: nächste **20, 40 und 60 Handelstage**
- `20✓ · 40✓ · 60✓` = saisonal über alle drei Horizonte unterstützt
- `20✓ · 40✓ · 60✕` = kurzfristig/mittelfristig unterstützt, längerfristig gegenläufig
- `20✕ · 40✕ · 60✕` = saisonal auf allen drei Horizonten gegenläufig
- `·` = nicht genügend verlässliche Historie

Die Horizonte helfen bei der Einschätzung der **zeitlichen Persistenz**, sind aber keine automatische Exit- oder Haltedauerregel.
- `— GEMISCHT` = kein klarer saisonaler Richtungsvorteil
- `— N/V` = nicht genügend verlässliche Preishistorie

Die Saison ist eine **separate Confluence**. Ein 3/4-Markt wird durch eine
positive Saison nicht zu 4/4.
"""
    )


with st.expander("Aktive Releases", expanded=False):
    st.caption(
        "Releases stehen separat, weil der aktuelle COT-Index das Extrem bereits verlassen hat "
        "und daher nicht sinnvoll in das aktuelle 3-Bedingungen-Ranking gehört."
    )
    render_release_table(all_markets)


if not scan["errors"].empty:
    with st.expander(
        f"Datenprobleme · {len(scan['errors'])} Märkte nicht geladen",
        expanded=False,
    ):
        err = scan["errors"].copy()
        err["Markt"] = err["market_name"].map(market_name_de)
        err = err.rename(columns={
            "asset_class": "Assetklasse",
            "symbol": "Symbol",
            "error": "Fehler",
        })
        st.dataframe(
            err[["Markt", "Symbol", "Assetklasse", "Fehler"]],
            width="stretch",
            hide_index=True,
        )
