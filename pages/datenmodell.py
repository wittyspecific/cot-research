
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.analysis import enrich_cot
from src.cftc import load_cftc_universe, load_history, resolve_market
from src.cftc_reports import (
    DATASETS,
    load_report_history,
    load_report_universe,
    primary_report_for_asset_class,
    resolve_report_market,
)
from src.config import COT_INDEX_WEEKS, NET_VALIDATION_WEEKS
from src.markets import CLASSIC_MARKETS
from src.publication import publication_info
from src.report_analysis import (
    enrich_report_positioning,
    latest_group_table,
    raw_oi_relation,
)
from src.style import (
    apply_style,
    context_strip,
    definition,
    page_header,
    section_line,
    metric_card,
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


def fmt_date(value):
    if value is None or pd.isna(value):
        return "—"
    return pd.Timestamp(value).strftime("%d.%m.%Y")


page_header(
    "Kontrollansicht · CFTC-Rohdaten",
    "CFTC Datenmodell",
    "Welche Händlergruppen und Normalisierungen liegen unter der Marktanalyse?",
    "UI HOTFIX · V3.3.1",
)

back_col, detail_col, research_col = st.columns([0.28, 0.36, 0.36])
with back_col:
    st.page_link(
        "pages/watchlist.py",
        label="← Watchlist",
        icon=":material/arrow_back:",
    )
with detail_col:
    if st.button(
        "Marktanalyse · gleicher Markt",
        key="data_to_market",
        use_container_width=True,
    ):
        context = st.session_state.get("selected_market")
        if context:
            st.session_state["_market_context_handoff"] = context
        st.switch_page("pages/marktanalyse.py")
with research_col:
    if st.button(
        "Research Lab · gleicher Markt",
        key="data_to_research",
        use_container_width=True,
    ):
        context = st.session_state.get("selected_market")
        if context:
            st.session_state["_market_context_handoff"] = context
        st.switch_page("pages/research_lab.py")

st.caption(
    "Kontrollseite für report-spezifische CFTC-Kategorien. "
    "Sie verändert die Legacy-Watchlist noch nicht."
)

_context = st.session_state.pop("_market_context_handoff", None)
_selected = st.session_state.get("selected_market")

if _context:
    st.session_state["v3_asset_class"] = _context["asset_class"]
    st.session_state["v3_market"] = _context["market_name"]
elif _selected and "v3_asset_class" not in st.session_state:
    st.session_state["v3_asset_class"] = _selected["asset_class"]
    st.session_state["v3_market"] = _selected["market_name"]



with st.sidebar:
    st.markdown("## Markt")

    asset_class = st.selectbox(
        "Assetklasse",
        list(CLASSIC_MARKETS.keys()),
        format_func=lambda x: ASSET_CLASS_DE.get(x, x),
        key="v3_asset_class",
    )

    names = [m["name"] for m in CLASSIC_MARKETS[asset_class]]
    if st.session_state.get("v3_market") not in names:
        st.session_state["v3_market"] = names[0]

    market_name = st.selectbox(
        "Kontrakt",
        names,
        format_func=lambda x: MARKET_NAME_DE.get(x, x),
        key="v3_market",
    )

    market = next(
        m for m in CLASSIC_MARKETS[asset_class]
        if m["name"] == market_name
    )

    st.session_state["selected_market"] = {
        "asset_class": asset_class,
        "market_name": market_name,
    }

    st.markdown("---")
    st.markdown("## Feste Berechnung")
    st.markdown(
        f"**Index:** {COT_INDEX_WEEKS} Wochen  \n"
        f"**Perzentilhistorie:** {NET_VALIDATION_WEEKS} Wochen  \n"
        "**Normalisierung:** Net / Open Interest"
    )

report_type = primary_report_for_asset_class(asset_class)
report_label = DATASETS[report_type]["label"]

try:
    universe = load_report_universe(report_type)
    resolved = resolve_report_market(market, universe)
except Exception as exc:
    st.error(f"{report_label} konnte nicht geladen werden.")
    with st.expander("Technische Details"):
        st.code(str(exc))
    st.stop()

if not resolved:
    st.error(
        f"Keine eindeutige {report_label}-Serie für diesen Markt gefunden."
    )
    st.stop()

code = resolved["cftc_contract_market_code"]

try:
    raw = load_report_history(report_type, code)
except Exception as exc:
    st.error("Die report-spezifische Historie konnte nicht geladen werden.")
    with st.expander("Technische Details"):
        st.code(str(exc))
    st.stop()

if raw.empty:
    st.warning("Keine Daten in der report-spezifischen Historie gefunden.")
    st.stop()

enriched = enrich_report_positioning(
    raw,
    report_type=report_type,
    index_weeks=COT_INDEX_WEEKS,
    validation_weeks=NET_VALIDATION_WEEKS,
)

latest = enriched.iloc[-1]
pub = publication_info(latest["report_date"])

section_line("Aktive CFTC-Sicht", report_label)

context_strip(
    [
        ("Report", report_label),
        ("CFTC-Code", str(code)),
        ("Positionsdatum", fmt_date(latest["report_date"])),
        ("Publikation", fmt_date(pub["publication_date"])),
    ]
)

definition(
    "Raw Net = Long minus Short in absoluten Kontrakten. Net/OI = dieselbe "
    "Netto-Position relativ zum Open Interest. Beide Reihen bleiben parallel "
    "sichtbar; es wird kein Gesamtscore daraus gebildet."
)

st.caption(
    f"Offizielle Serie: {resolved.get('market_and_exchange_names', '')}. "
    "Positionsdatum und Informationsverfügbarkeit werden getrennt geführt."
)

if report_type == "disaggregated":
    st.info(
        "Rohstoffmodell: Producer/Merchant wird separat von Swap Dealers und "
        "Managed Money ausgewiesen. Der frühere Legacy-Commercial-Bucket "
        "wird deshalb nicht mehr pauschal als physischer Hedger interpretiert."
    )
else:
    st.info(
        "Finanzmodell: TFF trennt Dealer/Intermediary, Asset Manager und "
        "Leveraged Funds. Dealer werden bewusst nicht automatisch als "
        "'Hedger' bezeichnet."
    )

table = latest_group_table(enriched, report_type)

st.markdown("### Positionierung · Raw und OI-normalisiert")

st.dataframe(
    table.style.format(
        {
            "Netto": "{:+,.0f}",
            "Raw-Netto-%ile": "{:.1f}",
            "Netto/OI": "{:+.2%}",
            "Netto/OI-%ile": "{:.1f}",
            "COT-Index 26W": "{:.1f}",
            "Netto Δ4W": "{:+,.0f}",
            "Netto/OI Δ4W": "{:+.2%}",
        },
        na_rep="—",
    ),
    use_container_width=True,
    hide_index=True,
)

primary_key = "producer" if report_type == "disaggregated" else "dealer"

raw_pct = float(
    latest.get(f"{primary_key}_raw_percentile", np.nan)
)
oi_pct = float(
    latest.get(f"{primary_key}_net_oi_percentile", np.nan)
)

relation = raw_oi_relation(raw_pct, oi_pct)

st.markdown("### Raw Net vs. Net/OI")

a, b, c = st.columns(3)

with a:
    metric_card(
        "RAW NET %ILE",
        "—" if np.isnan(raw_pct) else f"{raw_pct:.1f}",
        "156W auf absoluten Kontrakten",
    )

with b:
    metric_card(
        "NET/OI %ILE",
        "—" if np.isnan(oi_pct) else f"{oi_pct:.1f}",
        "156W relativ zur Marktgröße",
    )

with c:
    metric_card(
        "VERGLEICH",
        relation,
        "Kein zusammengesetzter Score",
    )

st.caption(
    "Raw Net wird nicht ersetzt. Ein Konflikt zwischen Raw-Perzentil und "
    "Net/OI-Perzentil wird sichtbar gemacht, aber in V3.0 noch nicht in "
    "eine neue CONFIRMED-Regel gepresst."
)

st.markdown("### Legacy-Referenz")

try:
    legacy_universe = load_cftc_universe()
    legacy_resolved = resolve_market(market, legacy_universe)

    legacy_raw = (
        load_history(legacy_resolved["cftc_contract_market_code"])
        if legacy_resolved
        else pd.DataFrame()
    )

    legacy = (
        enrich_cot(
            legacy_raw,
            weeks=COT_INDEX_WEEKS,
            validation_weeks=NET_VALIDATION_WEEKS,
            range_weeks=COT_INDEX_WEEKS,
        )
        if not legacy_raw.empty
        else pd.DataFrame()
    )

except Exception as exc:
    legacy = pd.DataFrame()
    st.warning(f"Legacy-Referenz konnte nicht geladen werden: {exc}")

if not legacy.empty:
    ll = legacy.dropna(
        subset=[
            "commercial_net_percentile",
            "commercial_net_oi_percentile",
        ]
    )

    if not ll.empty:
        lr = ll.iloc[-1]

        ref = pd.DataFrame(
            [
                {
                    "Report": "Legacy · Futures Only",
                    "Kategorie": "Commercial",
                    "Raw Net": lr["commercial_net"],
                    "Raw-Netto-%ile": lr["commercial_net_percentile"],
                    "Net/OI": lr["commercial_net_oi"],
                    "Net/OI-%ile": lr["commercial_net_oi_percentile"],
                    "COT-Index 26W": lr["commercial_index"],
                }
            ]
        )

        st.dataframe(
            ref.style.format(
                {
                    "Raw Net": "{:+,.0f}",
                    "Raw-Netto-%ile": "{:.1f}",
                    "Net/OI": "{:+.2%}",
                    "Net/OI-%ile": "{:.1f}",
                    "COT-Index 26W": "{:.1f}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "Legacy bleibt als Referenz sichtbar, ist für die neue "
            "report-spezifische Interpretation aber nicht automatisch "
            "die Hauptkategorie."
        )

st.markdown("### Publikationslag · Backtest-Regel")

st.markdown(
    """
- **Report Date** = Positionen zum CFTC-Stichtag, normalerweise Dienstag.
- **Publication Date** = Zeitpunkt, an dem die Information öffentlich wurde; normalerweise Freitag 15:30 ET.
- Historische Forward-Tests dürfen **nicht** am Dienstag starten.
- Dokumentierte Sonderveröffentlichungen 2023 und 2025 werden mit den tatsächlichen CFTC-Daten behandelt.
- Für gewöhnliche ältere Wochen nutzt der Bot einen konservativen Verfügbarkeitsanker, weil die CFTC keine vollständige historische Liste aller Release-Daten veröffentlicht.
    """
)

st.warning(
    "Die Watchlist bleibt in V3.0 noch Legacy-basiert. Erst nach "
    "Plausibilitätsprüfung der neuen Disaggregated-/TFF-Reihen sollte "
    "ihre Produktionslogik migriert werden."
)
