from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.config import (
    COMMERCIAL_RANGE_WEEKS, COT_INDEX_WEEKS, INDEX_LOWER, INDEX_UPPER,
    NET_LOWER_PERCENTILE, NET_UPPER_PERCENTILE, NET_VALIDATION_WEEKS, RELEASE_ACTIVE_WEEKS,
)
from src.style import apply_style, context_strip, definition, empty_state, page_header, section_line, terminal_cell
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


def _finite(value):
    try:
        x = float(value)
        return x if np.isfinite(x) else np.nan
    except (TypeError, ValueError):
        return np.nan


def _level(value):
    x = _finite(value)
    if not np.isfinite(x):
        return "N/V"
    if x >= NET_UPPER_PERCENTILE:
        return "HOCH"
    if x <= NET_LOWER_PERCENTILE:
        return "TIEF"
    return "MITTE"


def _release_flags(row) -> dict:
    direction = int(row.get("cycle_direction", 0) or 0)
    comm = _finite(row.get("commercial_net_percentile"))
    nc = _finite(row.get("noncommercial_net_percentile"))
    retail = _finite(row.get("retail_net_percentile"))
    release_ok = str(row.get("cycle_phase", "")).upper() == "RELEASE" and direction != 0
    if direction > 0:
        comm_ok = np.isfinite(comm) and comm >= NET_UPPER_PERCENTILE
        nc_ok = np.isfinite(nc) and nc <= NET_LOWER_PERCENTILE
        retail_ok = np.isfinite(retail) and retail <= NET_LOWER_PERCENTILE
    elif direction < 0:
        comm_ok = np.isfinite(comm) and comm <= NET_LOWER_PERCENTILE
        nc_ok = np.isfinite(nc) and nc >= NET_UPPER_PERCENTILE
        retail_ok = np.isfinite(retail) and retail >= NET_UPPER_PERCENTILE
    else:
        comm_ok = nc_ok = retail_ok = False
    count = int(release_ok) + int(comm_ok) + int(nc_ok) + int(retail_ok)
    return {
        "direction": direction,
        "release_ok": release_ok,
        "comm_ok": comm_ok,
        "nc_ok": nc_ok,
        "retail_ok": retail_ok,
        "count": count,
    }


def _confirmation_label(count):
    return (
        "4/4 Voll" if count >= 4 else
        "3/4 Stark" if count == 3 else
        "2/4 Teilweise" if count == 2 else
        "1/4 Release" if count == 1 else "—"
    )


def _open_market(row):
    handoff = {"asset_class": row["asset_class"], "market_name": row["market_name"]}
    st.session_state["selected_market"] = handoff
    st.session_state["_market_context_handoff"] = handoff
    st.switch_page("pages/marktanalyse.py")


def _prepare_release_rows(all_markets: pd.DataFrame) -> pd.DataFrame:
    if all_markets.empty:
        return pd.DataFrame()
    releases = all_markets[all_markets["cycle_phase"].astype(str).str.upper().eq("RELEASE")].copy()
    if releases.empty:
        return releases
    rows = []
    for _, r in releases.iterrows():
        flags = _release_flags(r)
        d = flags["direction"]
        if not d:
            continue
        comm_v = _finite(r.get("commercial_net_percentile"))
        nc_v = _finite(r.get("noncommercial_net_percentile"))
        retail_v = _finite(r.get("retail_net_percentile"))
        rows.append({
            **r.to_dict(),
            "_direction": d,
            "_confirmations": flags["count"],
            "Signal": "BULLISH" if d > 0 else "BÄRISCH",
            "Bestätigung": _confirmation_label(flags["count"]),
            "Commercials": f"{'✓' if flags['comm_ok'] else '–'} {_level(comm_v)} · {comm_v:.1f}",
            "Non-Commercials": f"{'✓' if flags['nc_ok'] else '–'} {_level(nc_v)} · {nc_v:.1f}",
            "Retail": f"{'✓' if flags['retail_ok'] else '–'} {_level(retail_v)} · {retail_v:.1f}",
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["_confirmations", "_direction", "market_name"], ascending=[False, False, True]).reset_index(drop=True)


def _attach_seasonality(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    records = []
    for _, r in out.iterrows():
        records.append(calculate_market_20y_multi_seasonality(
            ticker=str(r.get("ticker", "")),
            cot_direction=int(r.get("_direction", 0)),
        ))
    season = pd.DataFrame(records)
    out["Saison"] = season["compact"].values
    out["_season_support"] = (season["overall_rank"] >= 3).values
    out["_season_detail"] = season["detail"].values
    return out


def _render_release_table(df: pd.DataFrame, key_prefix: str):
    if df.empty:
        empty_state(
            "Noch kein aktives Hedge-Release",
            "Ein Extrem allein ist kein Signal. Die Watchlist wartet auf das Verlassen der Hedge-Zone.",
        )
        return
    headers = st.columns([1.75, .85, 1.05, 1.2, 1.25, 1.1, 1.05, 1.25], gap="small")
    for c, t in zip(headers, ["MARKT", "SIGNAL", "RELEASE", "COMMERCIALS", "NON-COMM.", "RETAIL", "BESTÄTIGUNG", "SAISON"]):
        with c:
            st.caption(t)
    for i, r in df.iterrows():
        cols = st.columns([1.75, .85, 1.05, 1.2, 1.25, 1.1, 1.05, 1.25], gap="small", vertical_alignment="center")
        with cols[0]:
            if st.button(f"{market_name_de(r['market_name'])} · {r['symbol']}", key=f"{key_prefix}_{i}", use_container_width=True):
                _open_market(r)
        tone = "bull" if int(r["_direction"]) > 0 else "bear"
        with cols[1]:
            terminal_cell("↑ BULLISH" if tone == "bull" else "↓ BÄRISCH", tone=tone)
        with cols[2]:
            weeks = r.get("weeks_since_release", np.nan)
            terminal_cell("Jetzt" if pd.isna(weeks) or int(weeks) == 0 else f"vor {int(weeks)}W")
        with cols[3]:
            terminal_cell(str(r["Commercials"]))
        with cols[4]:
            terminal_cell(str(r["Non-Commercials"]))
        with cols[5]:
            terminal_cell(str(r["Retail"]))
        with cols[6]:
            terminal_cell(str(r["Bestätigung"]))
        with cols[7]:
            terminal_cell(str(r.get("Saison", "—")), str(r.get("_season_detail", ""))[:60])


def _render_extreme_watch(all_markets: pd.DataFrame):
    extreme = (
        all_markets[all_markets["cycle_phase"].astype(str).str.upper().eq("EXTREME")].copy()
        if not all_markets.empty else pd.DataFrame()
    )
    if extreme.empty:
        empty_state("Keine aktuellen Commercial-Extreme", "Aktuell steht kein Markt in einer Hedge-Extremzone.")
        return
    extreme["_abs_extreme"] = (pd.to_numeric(extreme["commercial_index"], errors="coerce") - 50).abs()
    extreme = extreme.sort_values(["_abs_extreme", "market_name"], ascending=[False, True]).head(24)
    rows = []
    for _, r in extreme.iterrows():
        ed = int(r.get("extreme_direction", 0) or 0)
        rows.append({
            "Markt": f"{market_name_de(r['market_name'])} · {r['symbol']}",
            "State": "FULL HEDGE" if ed > 0 else "LOW HEDGE",
            "COT Index": round(_finite(r.get("commercial_index")), 1),
            "Dauer": f"{int(r.get('extreme_duration', 0) or 0)}W",
            "Signal": "WAITING FOR RELEASE",
            "Commercial %ile": round(_finite(r.get("commercial_net_percentile")), 1),
            "NC %ile": round(_finite(r.get("noncommercial_net_percentile")), 1),
            "Retail %ile": round(_finite(r.get("retail_net_percentile")), 1),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


page_header(
    "Research · Scanner",
    "COT Watchlist",
    "Aktive Hedge-Releases zuerst. Full-Hedge-Extreme bleiben als Wartezustand sichtbar.",
    "V3.9.0 · STATE ≠ SIGNAL",
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
signals = _prepare_release_rows(all_markets)
if not signals.empty:
    with st.spinner("Saisonalität der aktiven Releases wird geprüft …"):
        signals = _attach_seasonality(signals)

if all_markets.empty:
    full_hedge_count = 0
else:
    phase = all_markets["cycle_phase"].astype(str).str.upper()
    extreme_direction = pd.to_numeric(all_markets.get("extreme_direction"), errors="coerce").fillna(0)
    full_hedge_count = int((phase.eq("EXTREME") & extreme_direction.gt(0)).sum())

release_count = len(signals)
fully_confirmed = int((signals.get("_confirmations", pd.Series(dtype=int)) == 4).sum()) if not signals.empty else 0
season_supported = int(signals.get("_season_support", pd.Series(dtype=bool)).sum()) if not signals.empty else 0

context_strip([
    ("COT-Report", de_date(scan["latest_report"])),
    ("Aktive Releases", str(release_count)),
    ("4/4 bestätigt", str(fully_confirmed)),
    ("Full Hedge Watch", str(full_hedge_count)),
])

definition(
    "COT 100 bedeutet FULL HEDGE / obere Extremzone – noch kein bullishes Signal. "
    "Erst das Verlassen dieser Zone erzeugt ein bullishes Hedge-Release. "
    "Analog entsteht ein bärisches Signal erst beim Verlassen der unteren Extremzone."
)

section_line("Aktive Signale", "Hedge-Release zuerst · Bestätigung danach")
if not signals.empty:
    tab_all, tab_bull, tab_bear = st.tabs(["Alle", "Bullish", "Bärisch"])
    with tab_all:
        _render_release_table(signals, "sig_all")
    with tab_bull:
        _render_release_table(signals[signals["_direction"] > 0].reset_index(drop=True), "sig_bull")
    with tab_bear:
        _render_release_table(signals[signals["_direction"] < 0].reset_index(drop=True), "sig_bear")
else:
    _render_release_table(signals, "sig_none")

section_line("Full Hedge Watch", "Extremzustände ohne Richtungs-Signal")
_render_extreme_watch(all_markets)

with st.expander("Signal-Logik verstehen", expanded=False):
    st.markdown(f"""
**Obere Extremzone (COT ≥ {INDEX_UPPER})**
State = **FULL HEDGE**. Noch kein bullishes Signal.
Erst beim Verlassen → **BULLISH RELEASE**.

**Untere Extremzone (COT ≤ {INDEX_LOWER})**
State = **LOW HEDGE / untere Extremzone**. Noch kein bärisches Signal.
Erst beim Verlassen → **BEARISH RELEASE**.

Commercial-Netto, Non-Commercial-Netto und Retail-Netto bestätigen anschließend den Release. Saison 20/40/60T bleibt separate Confluence.
""")

if not scan["errors"].empty:
    with st.expander(f"Datenprobleme · {len(scan['errors'])} Märkte", expanded=False):
        st.dataframe(scan["errors"], use_container_width=True, hide_index=True)
