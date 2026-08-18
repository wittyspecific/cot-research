
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config import (
    COMMERCIAL_RANGE_WEEKS,
    COT_INDEX_WEEKS,
    FORWARD_HORIZONS_WEEKS,
    INDEX_LOWER,
    INDEX_UPPER,
    NC_CONFIRMING_WEEKS,
    NC_DIVERGENCE_WEEKS,
    NC_MIN_ACTIVE_BUILD_SHARE,
    NC_MIN_ACTIVE_LEG_GROSS_PCT,
    NC_MIN_NET_CHANGE_GROSS_PCT,
    NC_MIN_PRICE_MOVE_PCT,
    NC_DIV_FLOW_WINDOW_W,
    NC_DIV_PATH_WINDOW_W,
    NC_DIV_PRICE_WINDOW_W,
    NC_DIV_STANDARDIZE_HIST_W,
    NC_DIV_USE_OI_NORM,
    NC_DIV_Z_THRESHOLD,
    NET_LOWER_PERCENTILE,
    NET_UPPER_PERCENTILE,
    NET_VALIDATION_WEEKS,
    RELEASE_ACTIVE_WEEKS,
    SEASONAL_FORWARD_HORIZONS_DAYS,
    SEASONAL_HISTORY_WINDOWS,
    SEASONAL_OUTLIER_IQR_FACTOR,
    SEASONAL_PRIMARY_HORIZON_DAYS,
)
from src.analysis import (
    attach_cot_prices,
    build_events,
    classify_positioning_bias,
    commercial_range_state,
    cot_index,
    enrich_cot,
    hedger_cycle_state,
    historical_hedger_releases,
    historical_nc_divergences_legacy,
    net_validation,
    nc_divergence_legacy,
    positioning_velocity_state,
    summarize_events,
    summarize_releases,
)
from src.cftc import load_cftc_universe, load_history, resolve_market
from src.cftc_reports import (
    DATASETS,
    load_report_history,
    load_report_universe,
    primary_report_for_asset_class,
    resolve_report_market,
)
from src.markets import CLASSIC_MARKETS
from src.prices import load_prices, price_alignment_audit
from src.publication import publication_info
from src.report_analysis import enrich_report_positioning
from src.positioning_regime import classify_regime_stage, load_cross_group_context, load_price_structure
from src.research_informed_positioning import load_fx_research_overlay, classify_trader_overlay
from src.nc_divergence import (
    build_divergence_history,
    current_divergence,
    historical_divergence_events,
    redundancy_metrics,
)
from src.seasonality import forward_statistics, seasonal_consistency, seasonal_forward_path
from src.watchlist_seasonality_core import (
    classify_asset_seasonality,
    summarize_multi_horizon,
)
from src.style import (
    apply_style,
    context_strip,
    definition,
    page_header,
    section_line,
    stage_summary,
    metric_card,
    plotly_config,
    tradingview_chart,
    tradingview_plotly_chart,
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
    "Soft Commodities": "Soft-Rohstoffe",
    "Indices": "Indizes",
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

STATUS_DE = {
    # Allgemeine Richtung
    "BULLISH": "BULLISCH",
    "BEARISH": "BÄRISCH",
    "NEUTRAL": "NEUTRAL",

    # Positionierungszustände
    "BULLISH CONFIRMED": "BULLISCH BESTÄTIGT",
    "BEARISH CONFIRMED": "BÄRISCH BESTÄTIGT",
    "BULLISH BIAS": "BULLISCHER BIAS",
    "BEARISH BIAS": "BÄRISCHER BIAS",
    "BULLISH INDEX EXTREME": "BULLISCHES INDEX-EXTREM",
    "BEARISH INDEX EXTREME": "BÄRISCHES INDEX-EXTREM",
    "BULLISH WATCH": "BULLISCH BEOBACHTEN",
    "BEARISH WATCH": "BÄRISCH BEOBACHTEN",

    # Validierung
    "NO CONFIRMATION": "KEINE BESTÄTIGUNG",
    "CONFIRMED": "BESTÄTIGT",
    "PARTIAL": "TEILWEISE BESTÄTIGT",
    "UNCONFIRMED": "NICHT BESTÄTIGT",

    # Range
    "NO RANGE DATA": "KEINE RANGE-DATEN",
    "AT / NEAR RANGE HIGH": "AM / NAHE RANGE-HOCH",
    "AT / NEAR RANGE LOW": "AM / NAHE RANGE-TIEF",
    "UPPER RANGE": "OBERE RANGE",
    "LOWER RANGE": "UNTERE RANGE",
    "MID RANGE": "MITTLERE RANGE",
    "HIGH": "HOCH",
    "LOW": "TIEF",

    # Velocity
    "NO VELOCITY DATA": "KEINE DYNAMIKDATEN",
    "COMMERCIAL NET RISING": "COMMERCIAL-NETTO STEIGT",
    "COMMERCIAL NET FALLING": "COMMERCIAL-NETTO FÄLLT",
    "COMMERCIAL NET FLAT": "COMMERCIAL-NETTO UNVERÄNDERT",
    "CONFIRMING BULLISH": "BESTÄTIGT BULLISCH",
    "NOT CONFIRMING BULLISH": "BESTÄTIGT BULLISCH NICHT",
    "CONFIRMING BEARISH": "BESTÄTIGT BÄRISCH",
    "NOT CONFIRMING BEARISH": "BESTÄTIGT BÄRISCH NICHT",
    "NO ACTIVE DIRECTION": "KEINE AKTIVE RICHTUNG",

    # Hedger-Zyklus
    "NO CYCLE DATA": "KEINE ZYKLUSDATEN",
    "NO ACTIVE CYCLE": "KEIN AKTIVER ZYKLUS",
    "ENTERING BULLISH EXTREME": "EINTRITT IN BULLISCHES EXTREM",
    "BULLISH EXTREME · PERSISTENCE": "BULLISCHES EXTREM · PERSISTENZ",
    "ENTERING BEARISH EXTREME": "EINTRITT IN BÄRISCHES EXTREM",
    "BEARISH EXTREME · PERSISTENCE": "BÄRISCHES EXTREM · PERSISTENZ",
    "BULLISH RELEASE": "BULLISCHER RELEASE",
    "BEARISH RELEASE": "BÄRISCHER RELEASE",
    "BULLISH RELEASE · ACTIVE": "BULLISCHER RELEASE · AKTIV",
    "BEARISH RELEASE · ACTIVE": "BÄRISCHER RELEASE · AKTIV",
    "POST-RELEASE / NO ACTIVE CYCLE": "NACH RELEASE / KEIN AKTIVER ZYKLUS",
    "FULL HEDGE": "FULL HEDGE",
    "FULL HEDGE · PERSISTENCE": "FULL HEDGE · PERSISTENZ",
    "LOW HEDGE": "LOW HEDGE",
    "LOW HEDGE · PERSISTENCE": "LOW HEDGE · PERSISTENZ",
    "EARLY RELEASE · STILL EXTREME": "FRÜHER RELEASE · NOCH IM EXTREM",
    "HEDGE DEEPENING": "HEDGE WIRD TIEFER",
    "HEDGE STABLE": "HEDGE STABIL",
    "CONFIRMED RELEASE": "RELEASE BESTÄTIGT",
    "NORMALIZED": "NORMALISIERT",
    "NORMAL": "NORMAL",
    "NO DATA": "KEINE DATEN",

    # NC-Divergenz
    "NOT ENOUGH DATA": "ZU WENIG DATEN",
    "INVALID BASE": "UNGÜLTIGE BERECHNUNGSBASIS",
    "BULLISH · ACTIVE LONG BUILD": "BULLISCH · AKTIVER LONG-AUFBAU",
    "BULLISH · SHORT COVERING": "BULLISCH · SHORT-EINDECKUNG",
    "BULLISH · NET BUILD": "BULLISCH · NETTO-AUFBAU",
    "BEARISH · ACTIVE SHORT BUILD": "BÄRISCH · AKTIVER SHORT-AUFBAU",
    "BEARISH · MIXED DISTRIBUTION": "BÄRISCH · GEMISCHTE DISTRIBUTION",
    "LONG LIQUIDATION / PROFIT TAKING": "LONG-LIQUIDATION / GEWINNMITNAHMEN",
    "BEARISH · NET REDUCTION": "BÄRISCH · NETTO-ABBAU",
    "NO DIVERGENCE": "KEINE DIVERGENZ",
    "BULLISH DIVERGENCE": "BULLISCHE DIVERGENZ",
    "BEARISH DIVERGENCE": "BÄRISCHE DIVERGENZ",
    "PRICE ALIGNMENT INVALID": "PREIS-AUSRICHTUNG UNGÜLTIG",
    "STRONGLY BULLISH FLOW": "STARK BULLISHER FLOW",
    "STRONGLY BEARISH FLOW": "STARK BÄRISCHER FLOW",
    "BULLISH FLOW": "BULLISHER FLOW",
    "BEARISH FLOW": "BÄRISCHER FLOW",
    "NEUTRAL FLOW": "NEUTRALER FLOW",
    "NO FLOW DATA": "KEINE FLOW-DATEN",
    "NO LEG DATA": "KEINE SCHENKELDATEN",
    "MISSING COT WEEK": "COT-WOCHE FEHLT",
    "ACTIVE LONG BUILD + SHORT COVERING": "LONG-AUFBAU + SHORT-EINDECKUNG",
    "LONG LIQUIDATION + ACTIVE SHORT BUILD": "LONG-LIQUIDATION + AKTIVER SHORT-AUFBAU",
    "ACTIVE LONG BUILD": "AKTIVER LONG-AUFBAU",
    "SHORT COVERING": "SHORT-EINDECKUNG",
    "ACTIVE SHORT BUILD": "AKTIVER SHORT-AUFBAU",
    "MIXED / LOW ACTIVITY": "GEMISCHT / GERINGE AKTIVITÄT",

    # Historische Gruppen
    "ALL RELEASES": "ALLE RELEASES",
    "BULLISH RELEASES": "BULLISCHE RELEASES",
    "BEARISH RELEASES": "BÄRISCHE RELEASES",
    "ALL INDEX SIGNALS": "ALLE INDEX-SIGNALE",
    "NETTO BESTÄTIGT": "NETTO BESTÄTIGT",
}

def de_status(value):
    if value is None:
        return "—"
    return STATUS_DE.get(str(value), str(value))

def de_date(value):
    if value is None or pd.isna(value):
        return "—"
    return pd.Timestamp(value).strftime("%d.%m.%Y")

def de_nearest(value):
    return {"HIGH": "Hoch", "LOW": "Tief"}.get(str(value), str(value))


page_header(
    "Research · Markt",
    "COT Marktanalyse",
    "Zustand, Hedge-Release und Bestätigung klar getrennt.",
    "V3.10.0 · POSITIONING REGIME",
)

nav_back_col, nav_hint_col = st.columns([0.22, 0.78])
with nav_back_col:
    st.page_link(
        "pages/watchlist.py",
        label="← COT Watchlist",
        icon=":material/arrow_back:",
    )
with nav_hint_col:
    st.caption(
        "Die Marktanalyse beschreibt sechs getrennte Research-Stufen. "
        "Sie erzeugt keine Einstiegs-, Stop- oder Kurszielvorschläge."
    )



# Markt-Kontext aus Watchlist / Research / Datenmodell übernehmen.
_pending_market = st.session_state.pop("_market_context_handoff", None)
_selected_market = st.session_state.get("selected_market")

if _pending_market:
    st.session_state["asset_class_select"] = _pending_market["asset_class"]
    st.session_state["market_select"] = _pending_market["market_name"]
elif _selected_market and "asset_class_select" not in st.session_state:
    st.session_state["asset_class_select"] = _selected_market["asset_class"]
    st.session_state["market_select"] = _selected_market["market_name"]

with st.sidebar:
    st.markdown("## Markt")
    asset_class = st.selectbox(
        "Assetklasse",
        list(CLASSIC_MARKETS.keys()),
        format_func=lambda x: ASSET_CLASS_DE.get(x, x),
        key="asset_class_select",
    )
    names = [m["name"] for m in CLASSIC_MARKETS[asset_class]]
    if st.session_state.get("market_select") not in names:
        st.session_state["market_select"] = names[0]
    market_name = st.selectbox(
        "Kontrakt",
        names,
        format_func=lambda x: MARKET_NAME_DE.get(x, x),
        key="market_select",
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
    st.markdown("## Feste Methodik")

    cot_weeks = COT_INDEX_WEEKS
    upper = INDEX_UPPER
    lower = INDEX_LOWER

    validation_weeks = NET_VALIDATION_WEEKS
    validation_upper = NET_UPPER_PERCENTILE
    validation_lower = NET_LOWER_PERCENTILE
    range_weeks = COMMERCIAL_RANGE_WEEKS

    nc_lookback = NC_DIVERGENCE_WEEKS
    nc_min_confirming = NC_CONFIRMING_WEEKS
    nc_min_price_move = NC_MIN_PRICE_MOVE_PCT
    nc_min_net_move = NC_MIN_NET_CHANGE_GROSS_PCT
    nc_min_active_leg = NC_MIN_ACTIVE_LEG_GROSS_PCT
    nc_active_share = NC_MIN_ACTIVE_BUILD_SHARE

    horizons = list(FORWARD_HORIZONS_WEEKS)

    seasonal_primary_horizon = SEASONAL_PRIMARY_HORIZON_DAYS
    seasonal_outlier_factor = SEASONAL_OUTLIER_IQR_FACTOR

    st.caption(
        f"COT-Index {cot_weeks}W · {upper}/{lower}  \n"
        f"Netto-Historie {validation_weeks}W · "
        f"{validation_upper}/{validation_lower}  \n"
        f"Commercial-Range {range_weeks}W  \n"
        f"Spec-Flow {NC_DIV_FLOW_WINDOW_W}W · Pfad {NC_DIV_PATH_WINDOW_W}W · "
        f"robuste Historie {NC_DIV_STANDARDIZE_HIST_W}W  \n"
        f"Legacy-NC parallel: {nc_lookback}W · {nc_min_confirming} bestätigende Wochen  \n"
        f"Forward {horizons[0]}W / {horizons[-1]}W · Saison-IQR {seasonal_outlier_factor:.2f}"
    )

    st.markdown("---")
    st.markdown("## Saisonalitätsdarstellung")
    seasonal_curve_windows = st.multiselect(
        "Saisonkurven anzeigen",
        list(SEASONAL_HISTORY_WINDOWS),
        default=[5, 10, 15, 30],
        format_func=lambda x: f"{x} Jahre",
        help="Nur Darstellung. Die statistische Konsistenzprüfung verwendet "
             "immer alle festgelegten Historienfenster.",
    )
    if not seasonal_curve_windows:
        seasonal_curve_windows = [10, 30]

    st.markdown("---")
    st.markdown("## Datenquelle")
    price_ticker = st.text_input("Preis-Ticker", value=market["ticker"])
    if market.get("price_note"):
        st.caption(market["price_note"])
    st.caption(
        "Tagespreise werden je COT-Stichtag auf den letzten Schlusskurs ≤ Dienstag ausgerichtet. Keine Freitag-Wochenaggregation."
    )

try:
    universe = load_cftc_universe()
except Exception as exc:
    st.error(
        "Die CFTC-Datenquelle konnte nicht geladen werden. "
        "Internetverbindung prüfen und die Seite neu laden."
    )
    with st.expander("Technische Details"):
        st.code(str(exc))
    st.stop()

resolved = resolve_market(market, universe)
if not resolved:
    st.error(
        f"Für {market['name']} konnte keine eindeutige klassische "
        "Legacy-COT-Serie aufgelöst werden."
    )
    st.stop()

code = resolved["cftc_contract_market_code"]

try:
    raw_cot = load_history(code)
except Exception as exc:
    st.error("Die historische COT-Serie konnte nicht geladen werden.")
    with st.expander("Technische Details"):
        st.code(str(exc))
    st.stop()

if raw_cot.empty:
    st.warning(
        "Für den ausgewählten Markt wurden keine historischen "
        "Legacy-COT-Daten gefunden."
    )
    st.stop()

cot = enrich_cot(
    raw_cot,
    weeks=cot_weeks,
    validation_weeks=validation_weeks,
    range_weeks=range_weeks,
)

# Display-only comparison layer: Legacy Non-Commercial position inside the
# same 26W Min/Max framework as Commercials and Retail.
cot["noncommercial_index"] = cot_index(
    cot["noncommercial_net"],
    cot_weeks,
)

valid = cot.dropna(
    subset=[
        "commercial_net_percentile",
        "noncommercial_net_percentile",
        "retail_net_percentile",
    ]
)

if valid.empty:
    st.warning(
        f"Für {market['name']} sind nicht genügend Wochen vorhanden, "
        f"um das Commercial-Netto-Perzentil über {validation_weeks} Wochen "
        "und die Bestätigungsdaten gleichzeitig zu berechnen."
    )
    st.stop()

latest = valid.iloc[-1]
latest_publication = publication_info(latest["report_date"])
positioning = classify_positioning_bias(
    latest,
    upper=upper,
    lower=lower,
    validation_upper=validation_upper,
    validation_lower=validation_lower,
)
range_state = commercial_range_state(latest)
cycle = hedger_cycle_state(
    cot,
    upper=validation_upper,
    lower=validation_lower,
    release_active_weeks=RELEASE_ACTIVE_WEEKS,
)
research_direction = int(cycle.get("direction", 0) or 0) if cycle.get("phase") == "RELEASE" else 0
context_direction = research_direction if research_direction else int(cycle.get("extreme_direction", 0) or 0)
velocity = positioning_velocity_state(latest, direction=context_direction)

prices = load_prices(price_ticker, raw_cot["report_date"].min())

seasonal_stats = forward_statistics(
    prices,
    history_windows=SEASONAL_HISTORY_WINDOWS,
    horizons=SEASONAL_FORWARD_HORIZONS_DAYS,
)
seasonal_state = seasonal_consistency(
    seasonal_stats,
    primary_horizon=10,
    required_windows=SEASONAL_HISTORY_WINDOWS,
    reference_years=30,
)

# Watchlist-identische 20J / 20-40-60T Confluence.
market_multi_seasonality = {}
for _horizon in (20, 40, 60):
    _rows = seasonal_stats[
        (seasonal_stats["historie_jahre"] == 20)
        & (seasonal_stats["horizont_tage"] == _horizon)
    ] if seasonal_stats is not None and not seasonal_stats.empty else pd.DataFrame()

    if _rows.empty:
        market_multi_seasonality[_horizon] = {
            "support": "N/V",
            "display": "— N/V",
            "supports": False,
            "detail": "Keine ausreichende 20J-Historie",
        }
    else:
        _row = _rows.iloc[0]
        market_multi_seasonality[_horizon] = classify_asset_seasonality(
            cot_direction=int(research_direction),
            sample_size=int(_row["stichprobe"]),
            positive_years=int(_row["positive_jahre"]),
            positive_rate=float(_row["trefferquote_positiv"]),
            base_rate=float(_row["basisrate_positiv"]),
            median_return=float(_row["median_rendite"]),
        )

market_multi_seasonality_summary = summarize_multi_horizon(
    market_multi_seasonality
)

seasonal_paths = {}
for years in seasonal_curve_windows:
    seasonal_paths[int(years)] = seasonal_forward_path(
        prices,
        years=int(years),
        max_forward_days=60,
        outlier_factor=float(seasonal_outlier_factor),
    )

cot_with_prices = attach_cot_prices(cot, prices)
price_audit = price_alignment_audit(cot_with_prices)

# Legacy-Definition bleibt parallel lauffähig und wird nur als Vergleich geführt.
nc_div_legacy = nc_divergence_legacy(
    cot_with_prices,
    lookback_weeks=int(nc_lookback),
    min_confirming_weeks=int(nc_min_confirming),
    min_active_leg_weeks=min(2, int(nc_lookback)),
    min_price_move_pct=float(nc_min_price_move),
    min_net_change_pct=float(nc_min_net_move),
    min_active_leg_pct=float(nc_min_active_leg),
    active_leg_share=float(nc_active_share),
)

# Neue robuste Definition zunächst ebenfalls auf Legacy NC berechnen. Sie dient als
# methodischer Kontrollpfad für den Alt-vs.-Neu-Vergleich.
nc_div_new_legacy = current_divergence(
    cot_with_prices,
    long_col="noncommercial_long",
    short_col="noncommercial_short",
    group_label="Legacy Non-Commercial",
)

# Primäre spekulative Ebene: Managed Money für Rohstoffe, Leveraged Funds für
# Finanz-Futures. Fällt die moderne Reportserie aus, wird transparent auf den
# neuen Legacy-NC-Pfad zurückgefallen.
modern_report_type = primary_report_for_asset_class(asset_class)
spec_group_key = "managed_money" if modern_report_type == "disaggregated" else "leveraged_funds"
spec_group_label = "Managed Money" if spec_group_key == "managed_money" else "Leveraged Funds"
modern_source_label = DATASETS[modern_report_type]["label"]
modern_aligned = pd.DataFrame()
modern_enriched = pd.DataFrame()
modern_resolved = None
modern_error = None

try:
    modern_universe = load_report_universe(modern_report_type)
    modern_resolved = resolve_report_market(market, modern_universe)
    if modern_resolved:
        modern_raw = load_report_history(
            modern_report_type,
            modern_resolved["cftc_contract_market_code"],
        )
        if not modern_raw.empty:
            modern_enriched = enrich_report_positioning(
                modern_raw,
                report_type=modern_report_type,
                index_weeks=COT_INDEX_WEEKS,
                validation_weeks=NET_VALIDATION_WEEKS,
            )
            modern_aligned = attach_cot_prices(modern_enriched, prices)
except Exception as exc:
    modern_error = str(exc)

if not modern_aligned.empty:
    spec_price_audit = price_alignment_audit(modern_aligned)
    spec_div = current_divergence(
        modern_aligned,
        long_col=f"{spec_group_key}_long",
        short_col=f"{spec_group_key}_short",
        group_label=spec_group_label,
    )
    spec_source = f"{spec_group_label} · {modern_source_label}"
    spec_latest = modern_enriched.iloc[-1]
    spec_level_pct = float(spec_latest.get(f"{spec_group_key}_net_oi_percentile", np.nan))
else:
    spec_price_audit = price_audit
    spec_div = nc_div_new_legacy
    spec_source = "Legacy Non-Commercial · Fallback"
    spec_level_pct = float(latest.get("noncommercial_net_percentile", np.nan))


validation_direction = (
    "BULLISH" if context_direction > 0
    else "BEARISH" if context_direction < 0
    else "NEUTRAL"
)
validation = net_validation(
    latest,
    validation_direction,
    upper=validation_upper,
    lower=validation_lower,
    cycle=cycle,
)

comm_net_pct = float(latest["commercial_net_percentile"])
retail_net_pct = float(latest["retail_net_percentile"])
nc_net_pct = float(latest["noncommercial_net_percentile"])
comm_oi_pct = float(latest["commercial_net_oi_percentile"])
retail_oi_pct = float(latest["retail_net_oi_percentile"])

oi_change_4w = float(latest["open_interest_change_4w"])
oi_change_4w_pct = float(latest["open_interest_change_4w_pct"])
oi_change_4w_percentile = float(latest["open_interest_change_4w_percentile"])

# V3.10.0 · Divide-and-conquer positioning regime context.
# The Commercial 156W cycle stays primary; detailed CFTC groups are separate
# confirmation layers and never retroactively redefine the Commercial state.
regime_cross = load_cross_group_context(asset_class, str(code), int(context_direction)) if int(context_direction) != 0 else {
    "institutional_label": "Institutionell", "trend_label": "Trend-Funds",
    "institutional": {}, "trend": {}, "nonreportable": {},
    "nonreportable_percentile": np.nan, "error": None,
}
regime_price = load_price_structure(price_ticker, int(context_direction)) if int(context_direction) != 0 else {
    "label": "N/V", "tone": "neutral", "confirming": False,
}
regime_stage = classify_regime_stage(
    cycle_phase=str(cycle.get("phase", "")),
    commercial_transition=str(cycle.get("transition", "")),
    institutional=regime_cross.get("institutional"),
    trend=regime_cross.get("trend"),
    nonreportable=regime_cross.get("nonreportable"),
    price=regime_price,
)

# V3.13A · Research-informed FX overlay.
# 156W Net/OI + soft 75/25 + raw Dealer release velocity 1–2W.
# Existing 80/20 production gates, FTMO risk and execution remain unchanged.
research_fx = load_fx_research_overlay(asset_class, str(code))
trader_overlay = classify_trader_overlay(
    research_fx,
    regime_stage=int(regime_stage.get("stage", 0) or 0),
    legacy_release=str(cycle.get("phase", "")).upper() == "RELEASE",
    price_confirming=bool(regime_price.get("confirming", False)),
)


# ------------------------------------------------------------------
# Compact research hierarchy
# ------------------------------------------------------------------
def _fmt_contracts(value):
    return "—" if pd.isna(value) else f"{value:+,.0f}"

def _fmt_pct(value, digits=1):
    return "—" if pd.isna(value) else f"{value:.{digits}f}"

def _nc_level_label(net_value, percentile):
    if pd.isna(percentile):
        return "KEINE LEVEL-DATEN"
    if percentile <= 20:
        return "EXTREM NETTO-SHORT" if net_value < 0 else "HISTORISCH NIEDRIGES NETTO"
    if percentile >= 80:
        return "EXTREM NETTO-LONG" if net_value > 0 else "HISTORISCH HOHES NETTO"
    return "MITTLERE POSITIONIERUNG"

def _flow_label(change_4w, percentile):
    if pd.isna(change_4w) or pd.isna(percentile):
        return "KEINE FLOW-DATEN"
    if change_4w > 0:
        return "NETTO STEIGT"
    if change_4w < 0:
        return "NETTO FÄLLT"
    return "NETTO UNVERÄNDERT"

def _acceleration_label(change_4w, acceleration):
    if pd.isna(change_4w) or pd.isna(acceleration):
        return "—"
    if (change_4w > 0 and acceleration > 0) or (change_4w < 0 and acceleration < 0):
        return "BESCHLEUNIGEND"
    if acceleration == 0:
        return "KONSTANT"
    return "VERLANGSAMEND / DREHEND"

weeks_since_release_text = (
    "—"
    if pd.isna(cycle.get("weeks_since_release", np.nan))
    else f"{int(cycle['weeks_since_release'])}W seit Release"
)

range_distance_text = (
    "—"
    if pd.isna(range_state.get("distance_pct", np.nan))
    else f"{range_state['distance_pct']:.1f}% vom {de_nearest(range_state['nearest'])}"
)

nc_flow_pct = float(latest["noncommercial_change_4w_percentile"])
nc_flow_change = float(latest["noncommercial_change_4w"])
nc_level_label = _nc_level_label(float(latest["noncommercial_net"]), nc_net_pct)
nc_flow_label = _flow_label(nc_flow_change, nc_flow_pct)
nc_index = float(latest.get("noncommercial_index", np.nan))

def _legacy_nc_crowding_context(
    commercial_pct,
    nc_pct,
    nc_change_4w,
    nc_change_pct,
):
    """
    Descriptive context only.

    Commercial and Legacy Non-Commercial positions are mechanically linked,
    so this must never be counted as an independent confirmation.
    """
    if any(pd.isna(v) for v in (commercial_pct, nc_pct)):
        return {
            "state": "N/V",
            "detail": "Nicht genügend Netto-Historie.",
            "tone": "",
        }

    if nc_pct >= validation_upper and commercial_pct <= validation_lower:
        if not pd.isna(nc_change_4w) and nc_change_4w < 0:
            return {
                "state": "LONG-CROWDING · DREHT AB",
                "detail": (
                    f"NC {nc_pct:.1f}. Perzentil vs. Commercial {commercial_pct:.1f}. "
                    f"NC Δ4W {_fmt_contracts(nc_change_4w)}; aus extremer Long-Positionierung "
                    "wird abgebaut. Das erhöht den Reversal-/Top-Watch-Kontext, "
                    "ist aber kein eigenständiges Top-Signal."
                ),
                "tone": "bear",
            }
        return {
            "state": "LONG-CROWDING · TREND AKTIV",
            "detail": (
                f"NC {nc_pct:.1f}. Perzentil vs. Commercial {commercial_pct:.1f}. "
                "Spekulanten sind historisch stark long, Commercials stark auf der "
                "Gegenseite. Ein Extrem allein bedeutet noch keinen Top."
            ),
            "tone": "",
        }

    if nc_pct <= validation_lower and commercial_pct >= validation_upper:
        if not pd.isna(nc_change_4w) and nc_change_4w > 0:
            return {
                "state": "SHORT-CROWDING · DREHT AB",
                "detail": (
                    f"NC {nc_pct:.1f}. Perzentil vs. Commercial {commercial_pct:.1f}. "
                    f"NC Δ4W {_fmt_contracts(nc_change_4w)}; extreme Short-Positionierung "
                    "wird zurückgenommen. Das erhöht den Reversal-/Bottom-Watch-Kontext, "
                    "ist aber kein eigenständiges Bottom-Signal."
                ),
                "tone": "bull",
            }
        return {
            "state": "SHORT-CROWDING · TREND AKTIV",
            "detail": (
                f"NC {nc_pct:.1f}. Perzentil vs. Commercial {commercial_pct:.1f}. "
                "Spekulanten sind historisch stark short, Commercials stark auf der "
                "Gegenseite. Ein Extrem allein bedeutet noch keinen Boden."
            ),
            "tone": "",
        }

    return {
        "state": "KEINE GEGENLÄUFIGE EXTREMLAGE",
        "detail": (
            f"NC {nc_pct:.1f}. Perzentil · Commercial {commercial_pct:.1f}. Perzentil. "
            "Aktuell liegt keine klassische Commercial-vs.-NC-Crowding-Konstellation vor."
        ),
        "tone": "",
    }

nc_crowding = _legacy_nc_crowding_context(
    comm_net_pct,
    nc_net_pct,
    nc_flow_change,
    nc_flow_pct,
)

# Primäre Stufe 5 verwendet den robusten, OI-normalisierten spekulativen Flow.
spec_flow_raw = float(spec_div.get("d_flow_raw_4w", np.nan))
spec_flow_oi = float(spec_div.get("d_flow_4w", np.nan))
spec_z_flow = float(spec_div.get("z_flow", np.nan))
spec_z_price = float(spec_div.get("z_price", np.nan))
spec_rho = float(spec_div.get("rho", np.nan))
spec_strength = float(spec_div.get("divergence_strength", np.nan))
spec_strength_pct = float(spec_div.get("divergence_strength_percentile", np.nan))
spec_strength_ref_n = int(spec_div.get("divergence_strength_reference_n", 0) or 0)
accel_label = _acceleration_label(
    float(latest["commercial_change_4w"]),
    float(latest["commercial_acceleration_4w"]),
)

def _index_context(value):
    if pd.isna(value):
        return "n/v"
    if value >= upper:
        return f"{value:.1f} · oberes Extrem ab {upper}"
    if value <= lower:
        return f"{value:.1f} · unteres Extrem bis {lower}"
    return f"{value:.1f} · neutral zwischen {lower} und {upper}"

def _percentile_context(value, high, low):
    if pd.isna(value):
        return "n/v"
    if value >= high:
        return f"{value:.1f} · historisch hoch ab {high}"
    if value <= low:
        return f"{value:.1f} · historisch niedrig bis {low}"
    return f"{value:.1f} · mittlerer Bereich"

def _direction_tone(text):
    value = str(text).upper()
    if "BULL" in value:
        return "bull"
    if "BÄR" in value or "BEAR" in value:
        return "bear"
    return ""

context_strip(
    [
        ("Markt", f"{market['symbol']} · {MARKET_NAME_DE.get(market['name'], market['name'])}"),
        ("CFTC-Code", str(code)),
        ("Positionen", de_date(latest["report_date"])),
        ("Veröffentlicht", de_date(latest_publication["publication_date"])),
    ]
)

st.caption(
    f"Offizielle CFTC-Serie: {resolved.get('market_and_exchange_names','')} · "
    f"Preis-Proxy: {price_ticker}"
)

action_a, action_b, action_c = st.columns([0.34, 0.33, 0.33])
with action_a:
    st.page_link(
        "pages/watchlist.py",
        label="← Watchlist",
        icon=":material/view_list:",
    )
with action_b:
    if st.button(
        "Research Lab · gleicher Markt",
        key="open_research_same_market",
        use_container_width=True,
    ):
        st.session_state["_market_context_handoff"] = {
            "asset_class": asset_class,
            "market_name": market_name,
        }
        st.switch_page("pages/research_lab.py")
with action_c:
    if st.button(
        "Datenmodell · gleicher Markt",
        key="open_data_same_market",
        use_container_width=True,
    ):
        st.session_state["_market_context_handoff"] = {
            "asset_class": asset_class,
            "market_name": market_name,
        }
        st.switch_page("pages/datenmodell.py")

definition(
    "Teile & herrsche: Commercial Net Percentile 156W ist nur die Ausgangslage. Ein historisches Extrem "
    "erhöht die Aufmerksamkeit, erzeugt aber keine Richtung. Danach werden Transition, detaillierte CFTC-Gruppen, "
    "Nonreportable-Kontext und Preisstruktur getrennt überwacht. Legacy Non-Commercial bleibt dabei keine zusätzliche unabhängige Bestätigung. "
    "Der 26W-COT-Index bleibt ausschließlich Advanced Research."
)

_inst = dict(regime_cross.get("institutional") or {})
_trend = dict(regime_cross.get("trend") or {})
_nr = dict(regime_cross.get("nonreportable") or {})

def _regime_ui_safe(value) -> str:
    return (
        str(value if value is not None else "—")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _regime_trader_next_step(stage: int, cycle_phase: str, nonreportable_contrarian: bool) -> str:
    if stage <= 0:
        return "Warten: Ein Commercial-156W-Extrem muss zuerst einen aktiven Positionierungszyklus eröffnen."
    if stage == 1:
        return "Warten: Der Commercial-Hedge muss beginnen, sich aus dem Extrem zu lösen."
    if stage == 2:
        return "Warten: Institutionelle Gruppe und Trend-Funds müssen den möglichen Regimewechsel bestätigen."
    if stage == 3:
        if str(cycle_phase).upper() != "RELEASE":
            return "Warten: Der Commercial muss die Extremzone tatsächlich verlassen und den Release bestätigen."
        if not nonreportable_contrarian:
            return "Warten: Der Nonreportable-Kontext muss die Gegenseite des neuen Regimes bestätigen."
        return "Warten: Die Positionierungsbedingungen für REGIME CONFIRMED sind noch nicht vollständig."
    if stage == 4:
        return "Warten: Die Preisstruktur muss das bestätigte Positionierungsregime nachvollziehen."
    return "Kontext vollständig entwickelt: Jetzt separat S&D-Zone, Entry, SL, TP und Risiko prüfen."


def _render_research_trader_overlay() -> None:
    if not bool(trader_overlay.get("calibrated", False)):
        return

    bias = _regime_ui_safe(trader_overlay.get("bias", "NEUTRAL"))
    confidence = _regime_ui_safe(trader_overlay.get("confidence", "WATCH"))
    timing = _regime_ui_safe(trader_overlay.get("timing", "WAITING"))
    action = _regime_ui_safe(trader_overlay.get("action", "WARTEN"))
    pct = research_fx.get("dealer_net_oi_percentile_156w", np.nan)
    v1 = research_fx.get("release_velocity_1w", np.nan)
    v2 = research_fx.get("release_velocity_2w", np.nan)
    flow = _regime_ui_safe(research_fx.get("flow_support", "—"))

    pct_txt = "—" if pd.isna(pct) else f"{float(pct):.1f}"
    v1_txt = "—" if pd.isna(v1) else f"{float(v1):+,.0f}"
    v2_txt = "—" if pd.isna(v2) else f"{float(v2):+,.0f}"

    st.html(
        f"""
        <style>
        .ri-wrap{{margin:10px 0 16px}}
        .ri-title{{font-size:10px;font-weight:800;letter-spacing:.07em;color:#667085;text-transform:uppercase;margin-bottom:8px}}
        .ri-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}}
        .ri-card{{background:#fff;border:1px solid #e3e8ef;border-radius:11px;padding:13px 14px;min-height:78px}}
        .ri-label{{font-size:9px;color:#667085;font-weight:760;letter-spacing:.055em;text-transform:uppercase}}
        .ri-value{{font-size:17px;color:#101828;font-weight:760;margin-top:5px;line-height:1.2}}
        .ri-sub{{font-size:9px;color:#98a2b3;margin-top:5px;line-height:1.35}}
        .ri-note{{font-size:9px;color:#667085;margin-top:8px;line-height:1.45}}
        @media(max-width:800px){{.ri-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
        </style>
        <div class="ri-wrap">
          <div class="ri-title">RESEARCH-INFORMED FX OVERLAY · V3.13A</div>
          <div class="ri-grid">
            <div class="ri-card"><div class="ri-label">BIAS</div><div class="ri-value">{bias}</div><div class="ri-sub">TFF Dealer Net/OI 156W · {pct_txt}</div></div>
            <div class="ri-card"><div class="ri-label">CONFIDENCE</div><div class="ri-value">{confidence}</div><div class="ri-sub">Raw Release Flow · {flow}</div></div>
            <div class="ri-card"><div class="ri-label">TIMING</div><div class="ri-value">{timing}</div><div class="ri-sub">orientiert 1W {v1_txt} · 2W {v2_txt}</div></div>
            <div class="ri-card"><div class="ri-label">ACTION</div><div class="ri-value">{action}</div><div class="ri-sub">S&amp;D / Entry / SL / TP separat</div></div>
          </div>
          <div class="ri-note">Research Freeze: 156W · soft 75/25 · Raw Velocity 1–2W · 8W Forward · Status HOLD. 75/25 ist nur Early-Watch; die bestehende 80/20-Regime-/Release-Logik und das FTMO-Risiko bleiben unverändert. Timing „DEVELOPED/LATE“ ist bewusst eine operative Heuristik, kein empirisch eingefrorener Maturity-Parameter.</div>
        </div>
        """
    )


def _render_regime_trader_overview() -> None:
    stage = int(regime_stage.get("stage", 0) or 0)
    stage = max(0, min(5, stage))
    direction = int(np.sign(context_direction))
    direction_label = "BULLISH" if direction > 0 else "BEARISH" if direction < 0 else "NEUTRAL"
    direction_class = "bull" if direction > 0 else "bear" if direction < 0 else "neutral"
    current_label = str(regime_stage.get("label", "NORMAL") or "NORMAL")

    inst_label = str(regime_cross.get("institutional_label", "Institutionell") or "Institutionell")
    trend_label = str(regime_cross.get("trend_label", "Trend-Funds") or "Trend-Funds")
    nr_contrarian = bool(_nr.get("contrarian", False))

    phase_rows = [
        (
            1,
            "EXTREME WATCH",
            f"Commercial 156W: {comm_net_pct:.1f}. Perzentil · {de_status(cycle.get('state', positioning['state']))}",
        ),
        (
            2,
            "IN TRANSITION",
            f"{de_status(cycle.get('transition', '—'))} · Δ1W {cycle.get('percentile_change_1w', np.nan):+.1f} · Δ2W {cycle.get('percentile_change_2w', np.nan):+.1f} · Δ4W {cycle.get('percentile_change_4w', np.nan):+.1f}",
        ),
        (
            3,
            "CROSS-GROUP SHIFT",
            f"{inst_label}: {_inst.get('label', 'WARTET')} · {trend_label}: {_trend.get('label', 'WARTET')}",
        ),
        (
            4,
            "REGIME CONFIRMED",
            f"Commercial Release: {'BESTÄTIGT' if str(cycle.get('phase', '')).upper() == 'RELEASE' else 'WARTET'} · Nonreportable: {_nr.get('label', 'WARTET')}",
        ),
        (
            5,
            "CONTEXT READY",
            f"Preisstruktur: {regime_price.get('label', '—')}",
        ),
    ]

    rows_html = []
    for number, label, detail in phase_rows:
        if stage > number:
            state_class, marker, state_text = "done", "✓", "abgeschlossen"
        elif stage == number:
            state_class, marker, state_text = "current", "●", "aktuell"
        else:
            state_class, marker, state_text = "waiting", "○", "wartet"
        rows_html.append(
            '<div class="ma-regime-row ' + state_class + '">'
            '<div class="ma-regime-marker">' + marker + '</div>'
            '<div class="ma-regime-row-body">'
            f'<div class="ma-regime-row-title"><span>{number} · {_regime_ui_safe(label)}</span><small>{_regime_ui_safe(state_text)}</small></div>'
            f'<div class="ma-regime-row-detail">{_regime_ui_safe(detail)}</div>'
            '</div></div>'
        )

    next_step = _regime_trader_next_step(stage, str(cycle.get("phase", "")), nr_contrarian)
    season_compact = str(market_multi_seasonality_summary.get("compact", "—") or "—")
    season_overall = str(market_multi_seasonality_summary.get("overall", "N/V") or "N/V")
    market_label = MARKET_NAME_DE.get(market["name"], market["name"])

    stage_explanation = {
        0: "Kein aktiver Positionierungszyklus.",
        1: "Commercials sind historisch extrem; daraus entsteht noch kein Signal.",
        2: "Der Commercial-Hedge beginnt sich zu lösen; der Regimewechsel ist noch unbestätigt.",
        3: "Andere CFTC-Gruppen reagieren bereits; der vollständige Positionierungs-Release fehlt noch.",
        4: "Das Positionierungsregime ist bestätigt; die Preisbestätigung fehlt noch.",
        5: "Positionierung und Preisstruktur bestätigen denselben Kontext.",
    }.get(stage, "")

    st.html(
        f"""
        <style>
        .ma-regime-card{{background:#fff;border:1px solid #e3e8ef;border-radius:14px;padding:20px 22px;margin:14px 0 18px;box-shadow:0 1px 2px rgba(15,23,42,.025);max-width:920px}}
        .ma-regime-eyebrow{{font-size:10px;font-weight:750;letter-spacing:.08em;text-transform:uppercase;color:#667085;margin-bottom:7px}}
        .ma-regime-headline{{font-size:24px;line-height:1.2;font-weight:760;color:#101828;margin:0 0 5px}}
        .ma-regime-headline .bull{{color:#15803d}}.ma-regime-headline .bear{{color:#dc2626}}.ma-regime-headline .neutral{{color:#667085}}
        .ma-regime-stage{{font-size:12px;font-weight:700;color:#475467;margin-bottom:5px}}
        .ma-regime-summary{{font-size:12px;color:#667085;line-height:1.55;margin-bottom:17px}}
        .ma-regime-flow{{display:flex;flex-direction:column;gap:7px}}
        .ma-regime-row{{display:flex;align-items:flex-start;gap:11px;border:1px solid #eef1f5;border-radius:9px;padding:10px 12px;background:#fbfcfd}}
        .ma-regime-row.done{{background:#f7fbf8;border-color:#e0f1e4}}.ma-regime-row.current{{background:#f0fdf4;border-color:#bbebc8;box-shadow:inset 3px 0 0 #16a34a}}.ma-regime-row.waiting{{opacity:.68}}
        .ma-regime-marker{{width:19px;min-width:19px;height:19px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;background:#eef2f6;color:#98a2b3;margin-top:1px}}
        .ma-regime-row.done .ma-regime-marker{{background:#dcfce7;color:#15803d}}.ma-regime-row.current .ma-regime-marker{{background:#16a34a;color:#fff}}
        .ma-regime-row-body{{min-width:0;flex:1}}.ma-regime-row-title{{display:flex;justify-content:space-between;gap:12px;align-items:baseline;font-size:11px;font-weight:760;color:#344054}}
        .ma-regime-row-title small{{font-size:9px;color:#98a2b3;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}}
        .ma-regime-row-detail{{font-size:10px;color:#667085;line-height:1.5;margin-top:3px;overflow-wrap:anywhere}}
        .ma-regime-next{{margin-top:14px;border:1px solid #dce7f5;background:#f8fbff;border-radius:9px;padding:11px 12px}}
        .ma-regime-next-label{{font-size:9px;font-weight:750;letter-spacing:.06em;text-transform:uppercase;color:#667085;margin-bottom:3px}}.ma-regime-next-text{{font-size:12px;font-weight:650;color:#344054;line-height:1.45}}
        .ma-regime-context{{margin-top:10px;border-top:1px solid #eef1f5;padding-top:10px;display:flex;flex-direction:column;gap:5px;font-size:10px;color:#667085}}
        .ma-regime-context strong{{color:#344054}}.ma-regime-foot{{font-size:9px;color:#98a2b3;margin-top:8px}}
        @media(max-width:700px){{.ma-regime-card{{padding:16px}}.ma-regime-headline{{font-size:20px}}.ma-regime-row-title{{display:block}}.ma-regime-row-title small{{display:block;margin-top:2px}}}}
        </style>
        <div class="ma-regime-card">
          <div class="ma-regime-eyebrow">Positioning Regime · {_regime_ui_safe(market_label)}</div>
          <div class="ma-regime-headline"><span class="{direction_class}">{_regime_ui_safe(direction_label)}</span> · {_regime_ui_safe(current_label)}</div>
          <div class="ma-regime-stage">PHASE {stage} / 5</div>
          <div class="ma-regime-summary">{_regime_ui_safe(stage_explanation)}</div>
          <div class="ma-regime-flow">{''.join(rows_html)}</div>
          <div class="ma-regime-next">
            <div class="ma-regime-next-label">Nächste Trader-Entscheidung</div>
            <div class="ma-regime-next-text">{_regime_ui_safe(next_step)}</div>
          </div>
          <div class="ma-regime-context">
            <div><strong>Preis:</strong> {_regime_ui_safe(regime_price.get('label', '—'))}</div>
            <div><strong>Saisonalität 20/40/60T:</strong> {_regime_ui_safe(season_compact)} · {_regime_ui_safe(season_overall)}</div>
          </div>
          <div class="ma-regime-foot">Saisonalität bleibt separate Confluence und verändert die Regime-Phase nicht. CONTEXT READY ist noch kein Trade.</div>
        </div>
        """
    )


_render_research_trader_overlay()
_render_regime_trader_overview()

stage_summary(
    [
        {
            "label": "1 · Commercial 156W",
            "primary": f"{comm_net_pct:.1f}. Perzentil · {de_status(cycle.get('state', positioning['state']))}",
            "detail": (
                f"Historischer Zustand · Extremgrenzen {validation_upper:.0f}/{validation_lower:.0f}. "
                "Noch kein Trade-Signal aus dem Extrem selbst."
            ),
            "tone": "",
        },
        {
            "label": "2 · Transition / Release",
            "primary": de_status(cycle.get("transition", "—")),
            "detail": (
                f"Δ1W {cycle.get('percentile_change_1w', np.nan):+.1f} · "
                f"Δ2W {cycle.get('percentile_change_2w', np.nan):+.1f} · "
                f"Δ4W {cycle.get('percentile_change_4w', np.nan):+.1f} Pkt · {weeks_since_release_text}."
            ),
            "tone": _direction_tone(cycle["state"]) if cycle.get("phase") == "RELEASE" else "",
        },
        {
            "label": f"3 · {regime_cross.get('institutional_label','Institutionell')}",
            "primary": str(_inst.get("label", "WARTET")),
            "detail": (
                ("156W —" if pd.isna(_inst.get("percentile", np.nan)) else f"156W {_inst.get('percentile'):.1f}")
                + (" · Δ4W —" if pd.isna(_inst.get("delta_4w", np.nan)) else f" · Δ4W {_inst.get('delta_4w'):+.1f}")
                + ". Beobachtet, ob institutionelle Positionierung über 1–4 Wochen mitdreht."
            ),
            "tone": "bull" if _inst.get("aligned") and context_direction > 0 else "bear" if _inst.get("aligned") and context_direction < 0 else "",
        },
        {
            "label": f"4 · {regime_cross.get('trend_label','Trend-Funds')}",
            "primary": str(_trend.get("label", "WARTET")),
            "detail": (
                ("156W —" if pd.isna(_trend.get("percentile", np.nan)) else f"156W {_trend.get('percentile'):.1f}")
                + (" · Δ4W —" if pd.isna(_trend.get("delta_4w", np.nan)) else f" · Δ4W {_trend.get('delta_4w'):+.1f}")
                + ". Trendposition wird auf Verlangsamung, Abbau oder echte Drehung geprüft."
            ),
            "tone": "bull" if _trend.get("aligned") and context_direction > 0 else "bear" if _trend.get("aligned") and context_direction < 0 else "",
        },
        {
            "label": "5 · Nonreportable",
            "primary": str(_nr.get("label", "WARTET")),
            "detail": (
                ("156W —" if pd.isna(regime_cross.get("nonreportable_percentile", np.nan)) else f"156W {regime_cross.get('nonreportable_percentile'):.1f}")
                + ". Konträrer Kontext; bewusst nicht automatisch als Retail bezeichnet."
            ),
            "tone": "",
        },
        {
            "label": "Regime / Kontext",
            "primary": str(regime_stage.get("label", "NORMAL")),
            "detail": (
                f"Preis: {regime_price.get('label','—')} · Saison: {seasonal_state['status']}. "
                "CONTEXT READY bleibt Vorstufe; S&D, Entry, SL und TP werden separat geplant."
            ),
            "tone": "bull" if regime_stage.get("stage", 0) >= 4 and context_direction > 0 else "bear" if regime_stage.get("stage", 0) >= 4 and context_direction < 0 else "",
        },
    ]
)


st.caption(
    "Backtest-Hinweis: Historische Forward-Renditen beginnen in V3.0 nicht "
    "mehr am COT-Positionsstichtag. Der Publikationslag wird berücksichtigt; "
    "dokumentierte Sonderveröffentlichungen 2023/2025 werden explizit behandelt."
)

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    [
        "1 · Commercial 156W",
        "2 · Netto & Flow",
        "3 · Transition & Release",
        "4 · Spec-Flow",
        "5 · Saisonalität",
        "Historie",
        "Methodik",
    ]
)



with tab1:
    section_line("Commercial Positioning · 156W", "Primärer Zustand · Extrem ≠ Signal")
    definition(
        "Commercial Net Percentile 156W = historischer Rang der aktuellen Commercial-Netto-Position. "
        "Das Perzentil bleibt immer sichtbar. Ein Extrem ist zunächst nur FULL/LOW HEDGE; erst das "
        "Verlassen der Zone erzeugt ein Richtungs-Signal."
    )

    fig_pct = go.Figure()
    fig_pct.add_trace(go.Scatter(
        x=cot["report_date"], y=cot["commercial_net_percentile"], mode="lines",
        name="Commercial-Netto-Perzentil · 156W", line=dict(width=2.4),
    ))
    fig_pct.add_trace(go.Scatter(
        x=cot["report_date"], y=cot["noncommercial_net_percentile"], mode="lines",
        name="Non-Commercial-Netto-Perzentil · 156W", line=dict(width=1.5, dash="dash"),
    ))
    fig_pct.add_trace(go.Scatter(
        x=cot["report_date"], y=cot["retail_net_percentile"], mode="lines",
        name="Retail-Netto-Perzentil · 156W", line=dict(width=1.3, dash="dot"),
    ))
    fig_pct.add_hline(y=validation_upper, line_dash="dash", opacity=.35)
    fig_pct.add_hline(y=validation_lower, line_dash="dash", opacity=.35)
    fig_pct.update_layout(
        height=430, margin=dict(l=0, r=0, t=25, b=0),
        yaxis=dict(range=[0, 100], title="156W Perzentil"), xaxis_title=None,
        legend=dict(orientation="h", y=1.08),
    )
    tradingview_chart(
        fig_pct, x_values=cot["report_date"], default_years=3,
        reset_y_range=(0, 100), date_axis=True,
        uirevision=f"commercial-156w-{market['symbol']}",
    )
    tradingview_plotly_chart(fig_pct, config=plotly_config())
    st.caption("Y-Skala rechts ziehen = vertikal stauchen / strecken")

    c1, c2, c3, c4 = st.columns(4, gap="small")
    with c1:
        metric_card("Commercial Netto · 156W", f"{comm_net_pct:.1f}", de_status(positioning["state"]))
    with c2:
        metric_card(
            "TRANSITION",
            de_status(cycle.get("transition", "—")),
            f"Δ1W {cycle.get('percentile_change_1w', np.nan):+.1f} · Δ4W {cycle.get('percentile_change_4w', np.nan):+.1f}",
        )
    with c3:
        metric_card(
            "RELEASE",
            de_status(cycle["state"]),
            "Signal aktiv" if cycle.get("phase") == "RELEASE" else "Noch kein Richtungs-Signal",
        )
    with c4:
        metric_card(
            "EPISODEN-EXTREM",
            "—" if pd.isna(cycle.get("extreme_percentile", np.nan)) else f"{cycle['extreme_percentile']:.1f}",
            f"Extremdauer {cycle.get('extreme_duration', 0)}W",
        )

    with st.expander("Advanced · 26W COT-Index anzeigen", expanded=False):
        st.caption(
            "Der 26W-COT-Index bleibt vollständig verfügbar, beeinflusst aber die primäre "
            "V3.10.0 State/Release-Logik nicht mehr."
        )
        fig_idx = go.Figure()
        fig_idx.add_trace(go.Scatter(
            x=cot["report_date"], y=cot["commercial_index"], mode="lines",
            name="Commercial COT-Index · 26W", line=dict(width=2),
        ))
        fig_idx.add_trace(go.Scatter(
            x=cot["report_date"], y=cot["noncommercial_index"], mode="lines",
            name="Non-Commercial COT-Index", line=dict(width=1.5, dash="dash"),
        ))
        fig_idx.add_trace(go.Scatter(
            x=cot["report_date"], y=cot["retail_index"], mode="lines",
            name="Retail COT-Index · 26W", line=dict(width=1.3, dash="dot"),
        ))
        fig_idx.add_hline(y=upper, line_dash="dash", opacity=.35)
        fig_idx.add_hline(y=lower, line_dash="dash", opacity=.35)
        fig_idx.update_layout(
            height=360, margin=dict(l=0, r=0, t=25, b=0),
            yaxis=dict(range=[0, 100], title="26W COT-Index"), xaxis_title=None,
            legend=dict(orientation="h", y=1.08),
        )
        tradingview_chart(
            fig_idx, x_values=cot["report_date"], default_years=3,
            reset_y_range=(0, 100), date_axis=True,
            uirevision=f"cot-index-advanced-{market['symbol']}",
        )
        tradingview_plotly_chart(fig_idx, config=plotly_config())

    crowd_a, crowd_b, crowd_c = st.columns([1.0, 1.0, 1.15], gap="small")
    with crowd_a:
        metric_card(
            "Non-Commercial Netto · 156W", f"{nc_net_pct:.1f}. Perzentil",
            f"Δ4W {_fmt_contracts(nc_flow_change)} · Advanced 26W Index {nc_index:.1f}",
        )
    with crowd_b:
        metric_card("COMMERCIAL ↔ NC", nc_crowding["state"], nc_crowding["detail"])
    with crowd_c:
        metric_card(
            "Saison · 20J / 20-40-60T",
            market_multi_seasonality_summary["compact"],
            market_multi_seasonality_summary["overall"],
        )

with tab2:
    section_line("Netto & Flow", "Rohpositionierung · 156W-Transition · 1W/4W/8W Dynamik")
    definition(
        "Das Commercial-156W-Perzentil ist der primäre Zustand. Zusätzlich werden "
        "dessen Δ1W/Δ4W sowie die Roh-Netto-Veränderungen gespeichert, damit State "
        "und Transition getrennt analysiert werden können."
    )
    st.markdown("### Netto-Positionierung")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=cot["report_date"],
        y=cot["commercial_net"],
        mode="lines",
        name="Commercial Netto",
    ))
    fig2.add_trace(go.Scatter(
        x=cot["report_date"],
        y=cot["retail_net"],
        mode="lines",
        name="Retail Netto",
    ))
    fig2.add_hline(y=0, line_dash="dot", opacity=.3)
    fig2.update_layout(
        height=430,
        margin=dict(l=0, r=0, t=25, b=0),
        xaxis_title=None,
        yaxis_title="Kontrakte",
        legend=dict(orientation="h", y=1.08),
    )
    tradingview_chart(
        fig2,
        x_values=cot["report_date"],
        default_years=3,
        date_axis=True,
        uirevision=f"net-positioning-{market['symbol']}",
    )
    tradingview_plotly_chart(
        fig2,
        config=plotly_config(),
    )

    st.markdown("#### Positionierungsdynamik · 1W / 4W / 8W")
    velocity_table = cot[[
        "report_date",
        "commercial_net", "commercial_change_1w", "commercial_change_4w", "commercial_change_8w",
        "commercial_change_4w_percentile", "commercial_acceleration_4w",
        "retail_net", "retail_change_1w", "retail_change_4w", "retail_change_8w",
        "noncommercial_net", "noncommercial_net_percentile",
        "noncommercial_change_1w", "noncommercial_change_4w", "noncommercial_change_8w",
        "noncommercial_change_4w_percentile",
        "open_interest_all", "open_interest_change_4w",
        "open_interest_change_4w_pct", "open_interest_change_4w_percentile",
    ]].tail(20).sort_values("report_date", ascending=False)
    velocity_table = velocity_table.rename(columns={
        "report_date": "COT-Datum",
        "commercial_net": "Commercial Netto",
        "commercial_change_1w": "Commercial Δ1W",
        "commercial_change_4w": "Commercial Δ4W",
        "commercial_change_8w": "Commercial Δ8W",
        "commercial_change_4w_percentile": "Commercial Δ4W Perzentil",
        "commercial_acceleration_4w": "Commercial 4W-Beschleunigung",
        "retail_net": "Retail Netto",
        "retail_change_1w": "Retail Δ1W",
        "retail_change_4w": "Retail Δ4W",
        "retail_change_8w": "Retail Δ8W",
        "noncommercial_net": "Non-Commercial Netto",
        "noncommercial_net_percentile": "NC Netto-Perzentil",
        "noncommercial_change_1w": "NC Δ1W",
        "noncommercial_change_4w": "NC Δ4W",
        "noncommercial_change_8w": "NC Δ8W",
        "noncommercial_change_4w_percentile": "NC Δ4W Perzentil",
        "open_interest_all": "Open Interest",
        "open_interest_change_4w": "OI Δ4W",
        "open_interest_change_4w_pct": "OI Δ4W %",
        "open_interest_change_4w_percentile": "OI Δ4W Perzentil",
    })
    st.dataframe(
        velocity_table.style.format({
            "Commercial Netto": "{:,.0f}",
            "Commercial Δ1W": "{:,.0f}",
            "Commercial Δ4W": "{:,.0f}",
            "Commercial Δ8W": "{:,.0f}",
            "Commercial Δ4W Perzentil": "{:.1f}",
            "Commercial 4W-Beschleunigung": "{:,.0f}",
            "Retail Netto": "{:,.0f}",
            "Retail Δ1W": "{:,.0f}",
            "Retail Δ4W": "{:,.0f}",
            "Retail Δ8W": "{:,.0f}",
            "Non-Commercial Netto": "{:,.0f}",
            "NC Netto-Perzentil": "{:.1f}",
            "NC Δ1W": "{:,.0f}",
            "NC Δ4W": "{:,.0f}",
            "NC Δ8W": "{:,.0f}",
            "NC Δ4W Perzentil": "{:.1f}",
            "Open Interest": "{:,.0f}",
            "OI Δ4W": "{:,.0f}",
            "OI Δ4W %": "{:.2f}%",
            "OI Δ4W Perzentil": "{:.1f}",
        }, na_rep="—"),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Open-Interest-Kontext")
    oi1, oi2, oi3 = st.columns(3)
    with oi1:
        metric_card("OPEN INTEREST", f"{latest['open_interest_all']:,.0f}", "aktuelle Kontrakte")
    with oi2:
        metric_card(
            "OI Δ 4W",
            f"{oi_change_4w:+,.0f}",
            f"{oi_change_4w_pct:+.2f}% über vier Wochen",
        )
    with oi3:
        metric_card(
            "OI Δ4W PERZENTIL",
            f"{oi_change_4w_percentile:.1f}",
            f"vs. {validation_weeks}W Historie · nur beschreibend",
        )

    st.markdown("#### Jüngste Reports")
    table = cot[[
        "report_date",
        "commercial_long",
        "commercial_short",
        "commercial_net",
        "commercial_index",
        "commercial_net_percentile",
        "commercial_net_oi_percentile",
        "retail_long",
        "retail_short",
        "retail_net",
        "retail_index",
        "retail_net_percentile",
        "retail_net_oi_percentile",
        "noncommercial_long",
        "noncommercial_short",
        "noncommercial_net",
        "noncommercial_net_percentile",
        "noncommercial_change_4w",
        "noncommercial_change_4w_percentile",
        "open_interest_all",
        "open_interest_change_4w",
        "open_interest_change_4w_pct",
        "open_interest_change_4w_percentile",
    ]].tail(30).sort_values("report_date", ascending=False)

    table = table.rename(columns={
        "report_date": "COT-Datum",
        "commercial_long": "Commercial Long",
        "commercial_short": "Commercial Short",
        "commercial_net": "Commercial Netto",
        "commercial_index": "Commercial COT-Index",
        "commercial_net_percentile": "Commercial Netto-Perzentil",
        "commercial_net_oi_percentile": "Commercial Netto/OI Perzentil",
        "retail_long": "Retail Long",
        "retail_short": "Retail Short",
        "retail_net": "Retail Netto",
        "retail_index": "Retail COT-Index",
        "retail_net_percentile": "Retail Netto-Perzentil",
        "retail_net_oi_percentile": "Retail Netto/OI Perzentil",
        "noncommercial_long": "Non-Commercial Long",
        "noncommercial_short": "Non-Commercial Short",
        "noncommercial_net": "Non-Commercial Netto",
        "noncommercial_net_percentile": "NC Netto-Perzentil",
        "noncommercial_change_4w": "NC Δ4W",
        "noncommercial_change_4w_percentile": "NC Δ4W Perzentil",
        "open_interest_all": "Open Interest",
        "open_interest_change_4w": "OI Δ4W",
        "open_interest_change_4w_pct": "OI Δ4W %",
        "open_interest_change_4w_percentile": "OI Δ4W Perzentil",
    })

    st.dataframe(
        table.style.format({
            "Commercial COT-Index": "{:.1f}",
            "Retail COT-Index": "{:.1f}",
            "Commercial Netto-Perzentil": "{:.1f}",
            "Retail Netto-Perzentil": "{:.1f}",
            "Commercial Netto/OI Perzentil": "{:.1f}",
            "Retail Netto/OI Perzentil": "{:.1f}",
            "Commercial Long-Positionen": "{:,.0f}",
            "Commercial Short-Positionen": "{:,.0f}",
            "Commercial Netto": "{:,.0f}",
            "Retail Long-Positionen": "{:,.0f}",
            "Retail Short-Positionen": "{:,.0f}",
            "Retail Netto": "{:,.0f}",
            "Non-Commercial Long-Positionen": "{:,.0f}",
            "Non-Commercial Short-Positionen": "{:,.0f}",
            "Non-Commercial Netto": "{:,.0f}",
            "NC Netto-Perzentil": "{:.1f}",
            "NC Δ4W": "{:,.0f}",
            "NC Δ4W Perzentil": "{:.1f}",
            "Open Interest": "{:,.0f}",
            "OI Δ4W": "{:,.0f}",
            "OI Δ4W %": "{:.2f}%",
            "OI Δ4W Perzentil": "{:.1f}",
        }, na_rep="—"),
        use_container_width=True,
        hide_index=True,
    )


with tab3:
    st.markdown("### Hedger-Zyklus · Eintritt, Persistenz, Release")
    st.caption(
        "Der Zyklus wird jetzt ausschließlich aus dem Commercial Net Percentile 156W abgeleitet. "
        "Entscheidend sind Extremdauer, Transition und das tatsächliche Verlassen der 156W-Zone."
    )

    c_left, c_right = st.columns([1.25, .75], gap="large")
    with c_left:
        cyc_fig = go.Figure()
        cyc_fig.add_trace(go.Scatter(
            x=cot["report_date"], y=cot["commercial_net_percentile"],
            name="Commercial-Netto-Perzentil · 156W", mode="lines", line=dict(width=2.4),
        ))
        cyc_fig.add_hline(y=validation_upper, line_dash="dash", opacity=.35)
        cyc_fig.add_hline(y=validation_lower, line_dash="dash", opacity=.35)
        cyc_fig.update_layout(
            height=420, margin=dict(l=0, r=0, t=25, b=0),
            yaxis=dict(range=[0,100], title="Commercial 156W Perzentil"),
            xaxis_title=None,
        )
        tradingview_chart(
            cyc_fig,
            x_values=cot["report_date"],
            default_years=3,
            reset_y_range=(0, 100),
            date_axis=True,
            uirevision=f"cycle-{market['symbol']}",
        )
        tradingview_plotly_chart(
            cyc_fig,
            config=plotly_config(),
        )

    with c_right:
        entry_txt = "—" if cycle.get("entry_date") is None else de_date(cycle["entry_date"])
        release_txt = "—" if cycle.get("release_date") is None else de_date(cycle["release_date"])
        st.markdown(
            f"""
            <div class="signalbox">
              <small>HEDGER-ZYKLUS</small>
              <div class="signal signal-small">{de_status(cycle["state"])}</div>
              <p>
                Eintritt ins Extrem: <b>{entry_txt}</b><br>
                Dauer des Extrems: <b>{cycle['extreme_duration']} Wochen</b><br>
                Release-Datum: <b>{release_txt}</b><br>
                Transition: <b>{de_status(cycle.get('transition', '—'))}</b><br>
                Episoden-Extrem 156W: <b>{'—' if pd.isna(cycle.get('extreme_percentile', np.nan)) else f"{cycle['extreme_percentile']:.1f}"}</b><br>
                Advanced 26W Extremindex: <b>{'—' if pd.isna(cycle.get('extreme_index', np.nan)) else f"{cycle['extreme_index']:.1f}"}</b><br>
                Episoden-Extremnetto: <b>{'—' if pd.isna(cycle['extreme_net']) else f"{cycle['extreme_net']:,.0f}"}</b>
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("#### Commercial-Netto-Range und Dynamik")
    range_fig = go.Figure()
    range_fig.add_trace(go.Scatter(
        x=cot["report_date"], y=cot["commercial_net"], name="Commercial Netto", mode="lines"
    ))
    range_fig.add_trace(go.Scatter(
        x=cot["report_date"], y=cot["commercial_range_high"], name=f"{range_weeks}W Netto-Hoch",
        mode="lines", line=dict(width=1, dash="dot")
    ))
    range_fig.add_trace(go.Scatter(
        x=cot["report_date"], y=cot["commercial_range_low"], name=f"{range_weeks}W Netto-Tief",
        mode="lines", line=dict(width=1, dash="dot")
    ))
    range_fig.update_layout(
        height=390, margin=dict(l=0, r=0, t=25, b=0),
        xaxis_title=None, yaxis_title="Kontrakte", legend=dict(orientation="h", y=1.08),
    )
    tradingview_chart(
        range_fig,
        x_values=cot["report_date"],
        default_years=3,
        date_axis=True,
        uirevision=f"commercial-range-{market['symbol']}",
    )
    tradingview_plotly_chart(
        range_fig,
        config=plotly_config(),
    )

with tab4:
    section_line("Stufe 5 · Spekulativer Flow", f"{spec_source}")
    definition(
        "Flow beschreibt, wie sich die spekulative Netto-Position relativ zum Open Interest verändert. "
        "Eine Divergenz liegt erst vor, wenn ein ungewöhnlicher 4W-Preisimpuls und ein ungewöhnlicher "
        "4W-Flow gegeneinander laufen und der 8W-Pfad eine negative Spearman-Korrelation zeigt."
    )

    if spec_price_audit["future_prices"] > 0:
        st.error(
            "Preis-/COT-Ausrichtung verletzt: Mindestens ein verwendeter Preis liegt nach dem COT-Stichtag. "
            "Die Divergenzwerte werden nicht als gültig behandelt."
        )
    elif spec_price_audit["invalid"] > 0:
        st.caption(
            f"Preis-Audit: {spec_price_audit['valid']} von {spec_price_audit['n']} COT-Wochen haben einen "
            "Preis aus derselben ISO-Woche und niemals nach dem Stichtag. Fehlende Wochen werden nicht interpoliert."
        )
    else:
        st.caption(
            "Preis-Audit bestanden: Für alle verfügbaren COT-Wochen stammt der verwendete Schlusskurs "
            "aus derselben Woche und liegt nie nach dem COT-Stichtag."
        )

    flow_left, flow_right = st.columns([1.15, .85], gap="large")

    with flow_left:
        chart_frame = modern_aligned if not modern_aligned.empty else cot_with_prices
        chart_long = f"{spec_group_key}_long" if not modern_aligned.empty else "noncommercial_long"
        chart_short = f"{spec_group_key}_short" if not modern_aligned.empty else "noncommercial_short"
        chart = chart_frame.copy()
        chart["spec_net_oi_chart"] = (
            pd.to_numeric(chart[chart_long], errors="coerce")
            - pd.to_numeric(chart[chart_short], errors="coerce")
        ) / pd.to_numeric(chart["open_interest_all"], errors="coerce").replace(0, np.nan)

        nc_fig = go.Figure()
        nc_fig.add_trace(go.Scatter(
            x=chart["report_date"],
            y=chart["cot_price"],
            name="Preis · Dienstag/COT",
            mode="lines",
            line=dict(width=1.6),
            yaxis="y",
        ))
        nc_fig.add_trace(go.Scatter(
            x=chart["report_date"],
            y=chart["spec_net_oi_chart"],
            name=f"{spec_div.get('group_label', 'Spec')} Netto / OI",
            mode="lines",
            line=dict(width=2),
            yaxis="y2",
        ))
        nc_fig.update_layout(
            height=440,
            margin=dict(l=0, r=0, t=25, b=0),
            xaxis_title=None,
            yaxis=dict(title="Preis"),
            yaxis2=dict(
                title="Netto / OI",
                overlaying="y",
                side="right",
                showgrid=False,
            ),
            legend=dict(orientation="h", y=1.08),
        )
        tradingview_chart(
            nc_fig,
            x_values=chart["report_date"],
            default_years=3,
            date_axis=True,
            uirevision=f"spec-flow-{market['symbol']}",
        )
        tradingview_plotly_chart(
            nc_fig,
            config=plotly_config(),
        )

    def _fmt_z(value):
        return "—" if pd.isna(value) else f"{value:+.2f}"

    def _fmt_rho(value):
        return "—" if pd.isna(value) else f"{value:+.2f}"

    def _fmt_strength(value):
        return "—" if pd.isna(value) else f"{value:.2f}"

    with flow_right:
        st.markdown(
            f"""
            <div class="signalbox">
              <small>SPEKULATIVER FLOW · {spec_div.get('group_label', '—')}</small>
              <div class="signal signal-small">{de_status(spec_div.get('flow_label'))}</div>
              <p>
                Netto Δ4W: <b>{_fmt_contracts(spec_flow_raw)} Kontrakte</b><br>
                Netto/OI Δ4W: <b>{'—' if pd.isna(spec_flow_oi) else f'{spec_flow_oi:+.4f}'}</b><br>
                Flow z: <b>{_fmt_z(spec_z_flow)}</b><br>
                Netto/OI-Level: <b>{'—' if pd.isna(spec_level_pct) else f'{spec_level_pct:.1f}. Perzentil'}</b><br><br>
                Schenkel: <b>{de_status(spec_div.get('flow_type'))}</b><br>
                Long Δ / Brutto: <b>{'—' if pd.isna(spec_div.get('long_change_pct', np.nan)) else f"{spec_div['long_change_pct']:+.2f}%"}</b><br>
                Short Δ / Brutto: <b>{'—' if pd.isna(spec_div.get('short_change_pct', np.nan)) else f"{spec_div['short_change_pct']:+.2f}%"}</b>
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Divergenz · getrennt vom Flow")
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        metric_card("PREIS z", _fmt_z(spec_z_price), f"4W Log-Rendite · Schwelle ±{NC_DIV_Z_THRESHOLD:.1f}")
    with d2:
        metric_card("FLOW z", _fmt_z(spec_z_flow), "4W Δ Netto/OI · robuste 156W-Historie")
    with d3:
        metric_card("SPEARMAN 8W", _fmt_rho(spec_rho), "9 exakte Wochenpunkte · negativ für Divergenz")
    with d4:
        strength_detail = (
            "historisches Perzentil —"
            if pd.isna(spec_strength_pct)
            else f"{spec_strength_pct:.1f}. Perzentil · n={spec_strength_ref_n} frühere Divergenzen in 156W"
        )
        metric_card("DIVERGENZ-STÄRKE", _fmt_strength(spec_strength), strength_detail)

    st.markdown(
        f"**Aktueller Divergenzbefund: {de_status(spec_div.get('status'))}**"
    )
    st.caption(
        "Bullisch: z Preis ≤ -1,0 UND z Flow ≥ +1,0 UND rho < 0. "
        "Bärisch: Vorzeichen gespiegelt. Es wird kein Gesamtscore aus z Preis, z Flow und rho gebildet."
    )

    # Mechanische Redundanz wird direkt im selben Markt sichtbar gemacht.
    legacy_redundancy = redundancy_metrics(
        cot,
        hedger_key="commercial",
        speculative_key="noncommercial",
        nonreportable_key="retail",
        flow_weeks=NC_DIV_FLOW_WINDOW_W,
    )
    if not modern_enriched.empty:
        modern_hedger_key = "producer" if modern_report_type == "disaggregated" else "dealer"
        modern_redundancy = redundancy_metrics(
            modern_enriched,
            hedger_key=modern_hedger_key,
            speculative_key=spec_group_key,
            nonreportable_key="nonreportable",
            flow_weeks=NC_DIV_FLOW_WINDOW_W,
        )
    else:
        modern_redundancy = None

    with st.expander("Redundanz · Commercial/Hedger vs. spekulativer Flow"):
        rows = [{
            "Quelle": "Legacy · Commercial vs. Non-Commercial",
            "Pearson raw": legacy_redundancy["pearson_raw"],
            "Pearson OI-normalisiert": legacy_redundancy["pearson_oi"],
            "Erklärte NC-Varianz": legacy_redundancy["explained_variance"],
            "Restvarianz": legacy_redundancy["residual_variance"],
            "NonReportable-Anteil Restdifferenz (R²)": legacy_redundancy["nonreportable_difference_r2"],
            "N": legacy_redundancy["n"],
            "Einordnung": legacy_redundancy["interpretation"],
        }]
        if modern_redundancy is not None:
            rows.append({
                "Quelle": f"{modern_source_label} · {('Producer' if modern_report_type == 'disaggregated' else 'Dealer')} vs. {spec_group_label}",
                "Pearson raw": modern_redundancy["pearson_raw"],
                "Pearson OI-normalisiert": modern_redundancy["pearson_oi"],
                "Erklärte NC-Varianz": modern_redundancy["explained_variance"],
                "Restvarianz": modern_redundancy["residual_variance"],
                "NonReportable-Anteil Restdifferenz (R²)": modern_redundancy["nonreportable_difference_r2"],
                "N": modern_redundancy["n"],
                "Einordnung": modern_redundancy["interpretation"],
            })
        red_df = pd.DataFrame(rows)
        st.dataframe(
            red_df.style.format({
                "Pearson raw": "{:+.3f}",
                "Pearson OI-normalisiert": "{:+.3f}",
                "Erklärte NC-Varianz": "{:.1%}",
                "Restvarianz": "{:.1%}",
                "NonReportable-Anteil Restdifferenz (R²)": "{:.1%}",
            }, na_rep="—"),
            use_container_width=True,
            hide_index=True,
        )
        if modern_redundancy is not None and abs(modern_redundancy.get("pearson_raw", np.nan)) > 0.85:
            st.warning(
                "|r| > 0,85: Hedger- und spekulativer Flow sind in diesem Markt weitgehend gekoppelt. "
                "Sie dürfen nicht als zwei unabhängige Bestätigungen gezählt werden."
            )
        elif modern_redundancy is not None and abs(modern_redundancy.get("pearson_raw", np.nan)) < 0.60:
            st.info(
                "|r| < 0,60: Ein zusätzlicher Informationsanteil des spekulativen Flows ist strukturell plausibel."
            )

    spec_hist_frame = modern_aligned if not modern_aligned.empty else cot_with_prices
    spec_hist_long = f"{spec_group_key}_long" if not modern_aligned.empty else "noncommercial_long"
    spec_hist_short = f"{spec_group_key}_short" if not modern_aligned.empty else "noncommercial_short"
    hist_divs_new = historical_divergence_events(
        spec_hist_frame,
        long_col=spec_hist_long,
        short_col=spec_hist_short,
        group_label=spec_div.get("group_label", "Spec"),
    )

    st.markdown("#### Historische neue Divergenz-Episoden")
    if hist_divs_new.empty:
        st.info("Keine historischen Episoden nach der neuen robusten Definition im bewertbaren Zeitraum.")
    else:
        display = hist_divs_new.tail(50).sort_values("event_date", ascending=False).copy()
        display["status"] = display["status"].map(de_status)
        display = display.rename(columns={
            "event_date": "Ereignisdatum",
            "group_label": "Tradergruppe",
            "status": "Status",
            "direction": "Richtung",
            "r_4w": "4W Log-Rendite",
            "d_flow_4w": "Netto/OI Δ4W",
            "z_price": "z Preis",
            "z_flow": "z Flow",
            "rho": "Spearman 8W",
            "divergence_strength": "Stärke",
            "divergence_strength_percentile": "Stärke-%ile",
            "divergence_strength_reference_n": "Stärke-Referenz n",
        })
        st.dataframe(
            display.style.format({
                "4W Log-Rendite": "{:+.2%}",
                "Netto/OI Δ4W": "{:+.4f}",
                "z Preis": "{:+.2f}",
                "z Flow": "{:+.2f}",
                "Spearman 8W": "{:+.2f}",
                "Stärke": "{:.2f}",
                "Stärke-%ile": "{:.1f}",
            }, na_rep="—"),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Legacy-Definition parallel anzeigen"):
        st.write(f"Aktuell: **{de_status(nc_div_legacy['status'])}**")
        st.caption(
            "Diese alte Definition bleibt nur für den strukturellen Alt-vs.-Neu-Vergleich erhalten. "
            "Sie wird nicht mehr als primäre Stufe 5 verwendet."
        )
        hist_legacy = historical_nc_divergences_legacy(
            cot_with_prices,
            lookback_weeks=int(nc_lookback),
            min_confirming_weeks=int(nc_min_confirming),
            min_active_leg_weeks=min(2, int(nc_lookback)),
            min_price_move_pct=float(nc_min_price_move),
            min_net_change_pct=float(nc_min_net_move),
            min_active_leg_pct=float(nc_min_active_leg),
            active_leg_share=float(nc_active_share),
        )
        st.write(f"Historische Legacy-Episoden: **{len(hist_legacy)}**")

    if modern_error:
        with st.expander("Hinweis zur modernen CFTC-Serie"):
            st.warning(
                "Die moderne Reportserie konnte in diesem Lauf nicht geladen werden. "
                "Stufe 5 verwendet deshalb transparent den neuen robusten Legacy-NC-Fallback."
            )
            st.code(modern_error)


with tab5:
    section_line("Stufe 6 · Saisonalität", "primär 10 Handelstage")
    definition(
        "Basisrate = unbedingte Positiv-Quote über alle Kalenderphasen desselben "
        "Marktes und Horizonts. Saisonale Positiv-Quoten werden nur zusammen mit "
        "dieser Vergleichsrate gezeigt."
    )
    st.markdown("### Saisonalität · statistisch kalibriert")
    st.caption(
        "Primäre Frage: Was geschah historisch in den nächsten 10 Handelstagen? "
        "Die Fenster 5/10/15/20/30 Jahre dienen ausschließlich als verschachtelter "
        "Konsistenzcheck und sind keine fünf unabhängigen Bestätigungen."
    )

    if prices.empty:
        st.warning(
            "Für den ausgewählten Preis-Ticker stehen keine ausreichenden Tagesdaten "
            "für die saisonale Analyse zur Verfügung."
        )
    else:
        if str(price_ticker).upper().endswith("=F"):
            st.warning(
                "Datenhinweis: Der Preis-Proxy ist ein Yahoo-Continuous-Future. "
                "Rollsprünge können jedes Jahr zu ähnlichen Kalenderzeiten auftreten "
                "und dadurch scheinbare saisonale Muster erzeugen. Die Saisonalität "
                "ist deshalb als deskriptiver Research-Kontext zu lesen. Für belastbare "
                "Produktionstests sollte eine rollbereinigte Futures-Reihe verwendet werden."
            )

        st.markdown("#### Hauptfrage · nächste 10 Handelstage")
        st.markdown(
            f"**{seasonal_state['status']}**  \n"
            f"{seasonal_state['window_detail']}  \n"
            f"{seasonal_state['reference_detail']}"
        )

        primary = seasonal_stats[
            seasonal_stats["horizont_tage"] == 10
        ].copy()

        if primary.empty:
            st.info("Keine ausreichenden historischen Stichproben für 10 Handelstage.")
        else:
            def _direction_text(row):
                med = row["median_rendite"]
                hit = row["trefferquote_positiv"]
                base = row["basisrate_positiv"]
                if pd.isna(med) or pd.isna(hit) or pd.isna(base):
                    return "—"
                if med > 0 and hit > base:
                    return "BULLISCH ↑"
                if med < 0 and hit < base:
                    return "BÄRISCH ↓"
                return "NEUTRAL ·"

            primary["Richtung"] = primary.apply(_direction_text, axis=1)
            primary["Positiv"] = (
                primary["positive_jahre"].astype("Int64").astype(str)
                + "/"
                + primary["stichprobe"].astype("Int64").astype(str)
            )
            primary["95%-KI"] = primary.apply(
                lambda r: (
                    "—"
                    if pd.isna(r["ki95_unten"]) or pd.isna(r["ki95_oben"])
                    else f"{r['ki95_unten']:.0%}–{r['ki95_oben']:.0%}"
                ),
                axis=1,
            )

            primary_table = primary[[
                "historie_jahre",
                "Richtung",
                "Positiv",
                "trefferquote_positiv",
                "ki95_unten",
                "ki95_oben",
                "basisrate_positiv",
                "abstand_basisrate_pp",
                "binomial_p",
                "median_rendite",
                "mittel_rendite",
                "standardabweichung",
                "minimum",
                "maximum",
            ]].copy()

            primary_table = primary_table.rename(columns={
                "historie_jahre": "Historienfenster",
                "trefferquote_positiv": "Positiv-Quote",
                "ki95_unten": "KI unten",
                "ki95_oben": "KI oben",
                "basisrate_positiv": "Markt-Basisrate",
                "abstand_basisrate_pp": "Abstand zur Basisrate (Pp.)",
                "binomial_p": "Exakter Binomial-p",
                "median_rendite": "Median-Rendite",
                "mittel_rendite": "Mittlere Rendite",
                "standardabweichung": "Standardabweichung",
                "minimum": "Schlechtestes Jahr",
                "maximum": "Bestes Jahr",
            })

            st.dataframe(
                primary_table.style.format({
                    "Historienfenster": "{:.0f} Jahre",
                    "Positiv-Quote": "{:.1%}",
                    "KI unten": "{:.1%}",
                    "KI oben": "{:.1%}",
                    "Markt-Basisrate": "{:.1%}",
                    "Abstand zur Basisrate (Pp.)": "{:+.1f}",
                    "Exakter Binomial-p": "{:.3f}",
                    "Median-Rendite": "{:+.2%}",
                    "Mittlere Rendite": "{:+.2%}",
                    "Standardabweichung": "{:.2%}",
                    "Schlechtestes Jahr": "{:+.2%}",
                    "Bestes Jahr": "{:+.2%}",
                }, na_rep="—"),
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                "Der p-Wert testet die beobachtete Positiv-Quote gegen die marktinterne "
                "Basisrate aller Kalenderphasen desselben Horizonts. Er wird nicht als "
                "Signifikanz-Badge verwendet. Die 95%-Intervalle sind Wilson-Intervalle. "
                "Die Basisraten beruhen auf überlappenden Forward-Renditen; die p-Werte "
                "sind daher explorativ und nicht als endgültiger Signifikanznachweis zu lesen."
            )

        st.markdown("#### 30-Jahre-Referenz · verschachtelte Horizonte")
        st.caption(
            "10 / 20 / 40 / 60 Handelstage beginnen am selben historischen Startpunkt. "
            "Sie sind ineinander verschachtelt und dürfen nicht als vier unabhängige "
            "Bestätigungen interpretiert werden."
        )

        reference = seasonal_stats[
            seasonal_stats["historie_jahre"] == 30
        ].copy()
        if reference.empty:
            available_year = (
                seasonal_stats["historie_jahre"].max()
                if not seasonal_stats.empty
                else np.nan
            )
            reference = seasonal_stats[
                seasonal_stats["historie_jahre"] == available_year
            ].copy()

        hcols = st.columns(4)
        for col, horizon in zip(hcols, (10, 20, 40, 60)):
            row = reference[reference["horizont_tage"] == horizon]
            with col:
                if row.empty:
                    metric_card(
                        f"{horizon} HANDELSTAGE",
                        "—",
                        "keine ausreichende Historie",
                    )
                else:
                    r = row.iloc[0]
                    metric_card(
                        f"{horizon} HANDELSTAGE",
                        f"{r['median_rendite']:+.2%}",
                        f"{int(r['positive_jahre'])}/{int(r['stichprobe'])} positiv · "
                        f"Basis {r['basisrate_positiv']:.0%}",
                    )

        st.markdown("#### Saisonaler Verlauf ab heute · nur Visualisierung")
        seasonal_fig = go.Figure()

        for years in seasonal_curve_windows:
            path = seasonal_paths.get(int(years))
            if path is None or path.empty:
                continue

            seasonal_fig.add_trace(go.Scatter(
                x=path["handelstage_voraus"],
                y=path["saisonale_rendite_pct"],
                mode="lines",
                name=f"{years} Jahre",
            ))

        seasonal_fig.add_hline(y=0, line_dash="dot", opacity=.35)
        for h in (10, 20, 40, 60):
            seasonal_fig.add_vline(x=h, line_dash="dot", opacity=.20)

        seasonal_fig.update_layout(
            height=430,
            margin=dict(l=0, r=0, t=25, b=0),
            xaxis_title="Handelstage ab heute",
            yaxis_title="Saisonale kumulierte Tendenz (%)",
            legend=dict(orientation="h", y=1.08),
        )
        tradingview_chart(
            seasonal_fig,
            date_axis=False,
            uirevision=f"seasonality-{market['symbol']}",
        )
        tradingview_plotly_chart(
            seasonal_fig,
            config=plotly_config(),
        )

        st.caption(
            f"Die Kurve verwendet – analog zur Grundidee des bereitgestellten TradingView-Indikators – "
            f"einen IQR-Ausreißerfaktor von {seasonal_outlier_factor:.2f}. "
            "Sie ist eine geglättete Visualisierung. Sämtliche Tabellenwerte darüber "
            "basieren auf den unveränderten realisierten Forward-Renditen."
        )

        st.markdown("#### Methodische Einordnung")
        st.markdown(
            """
            - **10 Handelstage** sind der feste primäre Saisonalitätshorizont.
            - **5/10/15/20/30 Jahre** werden immer gemeinsam ausgewertet; die Auswahl
              der sichtbaren Kurven verändert die Statistik nicht.
            - Das **30-Jahre-Fenster** dient als langfristige Referenz. Kürzere Fenster
              zeigen, ob das Muster in jüngerer Marktstruktur noch in dieselbe Richtung weist.
            - Ein Ergebnis wie **7/10 positiv** wird nicht als robust bezeichnet. Neben
              der Quote werden Basisrate, Konfidenzintervall und p-Wert sichtbar gemacht.
            - Die vier Forward-Horizonte sind **Zoomstufen derselben saisonalen Phase**
              und keine vier voneinander unabhängigen Belege.
            - Bei Continuous-Futures kann ein kalendergebundener Rollmechanismus selbst
              saisonal aussehen. Eine rollbereinigte Datenquelle bleibt deshalb die
              bevorzugte Grundlage für spätere Produktionsentscheidungen.
            """
        )

with tab6:
    section_line("Historische Ereignisstudien", "publikationslag-korrigiert")
    definition(
        "Diese Seite zeigt historische Event-Renditen. Die bestehende COT-Event-"
        "Logik berechnet zwar Trefferquoten, führt jedoch keine unbedingte "
        "Markt-Basisrate mit. Deshalb werden diese Trefferquoten in der UI "
        "bewusst nicht angezeigt; Median, Mittelwert und Ereigniszahl bleiben sichtbar."
    )
    st.markdown("### Historische Ereignisauswertung")
    st.caption(
        "Die primäre Release-Historie basiert jetzt auf dem Commercial Net Percentile 156W. "
        "Ein Extrem ist zunächst nur ein Zustand; die Richtungsrendite beginnt erst nach dem "
        "Verlassen der 156W-Zone. Die alte 26W-Index-Auswertung bleibt darunter als Vergleich."
    )

    if prices.empty:
        st.warning(
            f"Für den Preis-Ticker '{price_ticker}' konnten keine historischen "
            "Preise geladen werden. Die COT-Analyse funktioniert weiterhin."
        )
    else:
        event_horizons = tuple(
            sorted(set(int(h) for h in horizons))
        )

        st.markdown("#### Hedger-Release-Auswertung")
        release_events = historical_hedger_releases(
            cot=cot,
            prices=prices,
            upper=validation_upper,
            lower=validation_lower,
            horizons=event_horizons,
        )
        if release_events.empty:
            st.info("Keine auswertbaren historischen Hedger-Release-Ereignisse gefunden.")
        else:
            release_summary = summarize_releases(release_events, event_horizons)
            release_summary_de = release_summary.copy()
            if "group" in release_summary_de.columns:
                release_summary_de["group"] = release_summary_de["group"].map(de_status)
            release_summary_de = release_summary_de.rename(columns={
                "group": "Gruppe",
                "horizon": "Horizont",
                "events": "Ereignisse",
                "mean_return": "Mittlere Rendite",
                "median_return": "Median-Rendite",
            })
            if "hit_rate" in release_summary_de.columns:
                release_summary_de = release_summary_de.drop(columns=["hit_rate"])
            st.dataframe(
                release_summary_de.style.format({
                    "Mittlere Rendite": "{:.2%}",
                    "Median-Rendite": "{:.2%}",
                }, na_rep="—"),
                use_container_width=True,
                hide_index=True,
            )
            rel_cols = [
                "event_date", "publication_date", "trade_date", "release",
                "extreme_duration", "extreme_percentile", "extreme_index", "extreme_net",
                "release_commercial_net",
            ]
            rel_fmt = {
                "extreme_index": "{:.1f}",
                "extreme_net": "{:,.0f}",
                "release_commercial_net": "{:,.0f}",
            }
            for h in event_horizons:
                rel_cols += [f"return_{h}w", f"aligned_return_{h}w"]
                rel_fmt[f"return_{h}w"] = "{:.2%}"
                rel_fmt[f"aligned_return_{h}w"] = "{:.2%}"
            release_display = release_events[rel_cols].sort_values("event_date", ascending=False).copy()
            release_display["release"] = release_display["release"].map(de_status)
            release_display = release_display.rename(columns={
                "event_date": "Positionsdatum",
                "publication_date": "Veröffentlichung",
                "trade_date": "Backtest-Start",
                "release": "Release",
                "extreme_duration": "Extremdauer (W)",
                "extreme_percentile": "Extrem 156W",
                "extreme_index": "Advanced 26W Extrem-Index",
                "extreme_net": "Extrem-Netto",
                "release_commercial_net": "Commercial-Netto beim Release",
                **{f"return_{h}w": f"Rendite {h}W" for h in event_horizons},
                **{f"aligned_return_{h}w": f"Richtungsrendite {h}W" for h in event_horizons},
            })
            rel_fmt_de = {
                "Extrem 156W": "{:.1f}",
                "Advanced 26W Extrem-Index": "{:.1f}",
                "Extrem-Netto": "{:,.0f}",
                "Commercial-Netto beim Release": "{:,.0f}",
            }
            for h in event_horizons:
                rel_fmt_de[f"Rendite {h}W"] = "{:.2%}"
                rel_fmt_de[f"Richtungsrendite {h}W"] = "{:.2%}"
            st.dataframe(
                release_display.style.format(rel_fmt_de, na_rep="—"),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("#### Ursprüngliche Index-Extrem-Auswertung")
        events = build_events(
            cot=cot,
            prices=prices,
            upper=upper,
            lower=lower,
            validation_upper=validation_upper,
            validation_lower=validation_lower,
            horizons=event_horizons,
        )

        if events.empty:
            st.info(
                "Mit den aktuellen Schwellenwerten wurden keine "
                "auswertbaren historischen Extrem-Ereignisse gefunden."
            )
        else:
            summary = summarize_events(events, event_horizons)

            st.markdown("#### Nur Index vs. netto-bestätigt")
            summary_de = summary.copy()
            summary_de["group"] = summary_de["group"].map(de_status)
            summary_de = summary_de.rename(columns={
                "group": "Gruppe",
                "horizon": "Horizont",
                "events": "Ereignisse",
                "mean_return": "Mittlere Rendite",
                "median_return": "Median-Rendite",
            })
            if "hit_rate" in summary_de.columns:
                summary_de = summary_de.drop(columns=["hit_rate"])
            st.dataframe(
                summary_de.style.format({
                    "Mittlere Rendite": "{:.2%}",
                    "Median-Rendite": "{:.2%}",
                }, na_rep="—"),
                use_container_width=True,
                hide_index=True,
            )

            confirmed = events[events["validation"] == "CONFIRMED"]
            all_count = len(events)
            confirmed_count = len(confirmed)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                metric_card(
                    "INDEX-EREIGNISSE",
                    f"{all_count}",
                    "alle 80/20-Episoden",
                )
            with c2:
                metric_card(
                    "NETTO BESTÄTIGT",
                    f"{confirmed_count}",
                    "beide Netto-Perzentile bestätigen",
                )

            preferred_h = 8 if 8 in event_horizons else event_horizons[-1]
            row_all = summary[
                (summary["group"] == "ALL INDEX SIGNALS")
                & (summary["horizon"] == f"{preferred_h}W")
            ]
            row_conf = summary[
                (summary["group"] == "NET CONFIRMED")
                & (summary["horizon"] == f"{preferred_h}W")
            ]

            with c3:
                value = "—"
                if not row_all.empty and pd.notna(row_all.iloc[0]["median_return"]):
                    value = f"{row_all.iloc[0]['median_return']:+.2%}"
                metric_card(
                    f"ALLE · {preferred_h}W MEDIAN",
                    value,
                    "richtungsbereinigte Event-Rendite",
                )
            with c4:
                value = "—"
                if not row_conf.empty and pd.notna(row_conf.iloc[0]["median_return"]):
                    value = f"{row_conf.iloc[0]['median_return']:+.2%}"
                metric_card(
                    f"BESTÄTIGT · {preferred_h}W MEDIAN",
                    value,
                    "Index + Netto-Validierung",
                )

            event_cols = [
                "event_date",
                "publication_date",
                "trade_date",
                "signal",
                "validation",
                "commercial_index",
                "retail_index",
                "commercial_net",
                "commercial_net_percentile",
                "retail_net",
                "retail_net_percentile",
            ]
            fmt = {
                "commercial_index": "{:.1f}",
                "retail_index": "{:.1f}",
                "commercial_net": "{:,.0f}",
                "retail_net": "{:,.0f}",
                "commercial_net_percentile": "{:.1f}",
                "retail_net_percentile": "{:.1f}",
            }

            for h in event_horizons:
                event_cols += [
                    f"return_{h}w",
                    f"aligned_return_{h}w",
                ]
                fmt[f"return_{h}w"] = "{:.2%}"
                fmt[f"aligned_return_{h}w"] = "{:.2%}"

            st.markdown("#### Historische Ereignisse")
            event_display = events[event_cols].sort_values("event_date", ascending=False).copy()
            event_display["signal"] = event_display["signal"].map(de_status)
            event_display["validation"] = event_display["validation"].map(de_status)
            event_display = event_display.rename(columns={
                "event_date": "Positionsdatum",
                "publication_date": "Veröffentlichung",
                "trade_date": "Backtest-Start",
                "signal": "Signal",
                "validation": "Validierung",
                "commercial_index": "Commercial COT-Index",
                "retail_index": "Retail COT-Index",
                "commercial_net": "Commercial Netto",
                "commercial_net_percentile": "Commercial Netto-Perzentil",
                "retail_net": "Retail Netto",
                "retail_net_percentile": "Retail Netto-Perzentil",
                **{f"return_{h}w": f"Rendite {h}W" for h in event_horizons},
                **{f"aligned_return_{h}w": f"Richtungsrendite {h}W" for h in event_horizons},
            })
            fmt_de = {
                "Commercial COT-Index": "{:.1f}",
                "Retail COT-Index": "{:.1f}",
                "Commercial Netto": "{:,.0f}",
                "Retail Netto": "{:,.0f}",
                "Commercial Netto-Perzentil": "{:.1f}",
                "Retail Netto-Perzentil": "{:.1f}",
            }
            for h in event_horizons:
                fmt_de[f"Rendite {h}W"] = "{:.2%}"
                fmt_de[f"Richtungsrendite {h}W"] = "{:.2%}"
            st.dataframe(
                event_display.style.format(fmt_de, na_rep="—"),
                use_container_width=True,
                hide_index=True,
            )

with tab7:
    st.markdown("### V3.10.0 · Commercial 156W → Transition → Cross-Group Regime")
    st.code(
        f"""
PRIMÄRER ZUSTAND — COMMERCIAL NET PERCENTILE ({validation_weeks} Wochen)

FULL HEDGE:
  Commercial Netto-Perzentil >= {validation_upper}
  → Extremzustand, noch KEIN bullishes Signal

LOW HEDGE:
  Commercial Netto-Perzentil <= {validation_lower}
  → Extremzustand, noch KEIN bärisches Signal


TRANSITION
  Δ1W / Δ4W des Commercial-156W-Perzentils
  + Distanz zum Episoden-Extrem
  + Dauer der Extrem-Episode

EARLY RELEASE:
  Perzentil bewegt sich bereits zurück, liegt aber noch innerhalb der Extremzone
  → WATCH, noch KEIN Richtungs-Signal

CONFIRMED RELEASE:
  oberes Extrem wird nach unten verlassen → BULLISH RELEASE
  unteres Extrem wird nach oben verlassen → BEARISH RELEASE


BESTÄTIGUNG
  Commercial-Seite = vorausgegangenes Episoden-Extrem
  Retail = aktuelles 156W Netto-Perzentil auf der Gegenseite
  NC / Spec Flow = zusätzliche Bestätigungs- bzw. Kontextschicht

ADVANCED
  26W COT-Index + {range_weeks}W Commercial-Range bleiben vollständig verfügbar,
  lösen aber kein primäres V3.10.0-Signal aus.
        """.strip(),
        language="text",
    )

    st.markdown("### Interpretation")
    st.markdown(
        f"""
        - **Commercial Net Percentile 156W bleibt der zentrale sichtbare Wert.** Er beschreibt,
          wo die aktuelle Commercial-Netto-Position relativ zu den letzten {validation_weeks} Wochen liegt.
        - Ein Wert im oberen oder unteren Extrem ist zunächst **STATE, nicht SIGNAL**.
        - **Transition** misst die Bewegung dieses Zustands über Δ1W und Δ4W sowie die Distanz
          zum Extrem der laufenden Episode.
        - **Release** entsteht erst, wenn die 156W-Extremzone tatsächlich verlassen wird.
        - Die Commercial-Bestätigung eines Releases referenziert bewusst das vorausgegangene
          Episoden-Extrem. Der aktuelle Commercial-Wert liegt beim Release bereits außerhalb
          der Zone und darf das korrekte Signal nicht selbst entbestätigen.
        - Retail, Non-Commercial und Spec Flow bleiben als Bestätigung/Kontext erhalten.
        - Open Interest bleibt sekundärer Partizipationskontext.
        - Die historische Auswertung verwendet nur Informationen, die zum jeweiligen Report
          bereits verfügbar waren.
        """
    )

    st.markdown("### Positionierungsdynamik")
    st.markdown(
        """
        Für Commercials werden neben dem aktuellen 156W-Perzentil dessen **Δ1W, Δ4W und Δ8W**,
        die Distanz zum Episoden-Extrem und die Dauer der Extremphase gespeichert. Die bereits
        vorhandenen Veränderungen der absoluten Netto-Kontrakte bleiben parallel verfügbar.
        Dadurch werden Zustand und Bewegung getrennt statt in einem einzelnen Index vermischt.
        """
    )

    st.markdown("### 26W COT-Index & Commercial-Range · Advanced")
    st.markdown(
        f"""
        Der **{cot_weeks}W COT-Index** und die **{range_weeks}W Commercial-Range** werden nicht gelöscht.
        Sie bleiben in Charts, Research Lab und Trade-Snapshots erhalten und können später auch
        im Machine Learning gegen die 156W-State/Release-Logik getestet werden. Sie sind aber
        **keine Gate-Bedingung** für das primäre Release-Signal mehr.
        """
    )

    st.markdown("### Analysehierarchie")
    st.markdown(
        """
        Die erste Ebene zeigt Commercial 156W, Transition, Release und Bestätigung. Rohdaten,
        COT-Index, Range, zusätzliche Velocity-Metriken und methodische Details bleiben in den
        Advanced-Tabs verfügbar. Commercial und Legacy-NC werden dabei weiterhin **nicht als
        zwei unabhängige Bestätigungen** gezählt.
        """
    )

    st.markdown("### Non-Commercial-Niveau vs. Dynamik")
    st.markdown(
        f"""
        Non-Commercial bleibt als 156W-Netto-Perzentil, {cot_weeks}W-COT-Index und Flow-Dynamik
        verfügbar. Ein extremes NC-Level beschreibt vor allem Crowding/Positionierungsphase.
        Für einen möglichen Wendepunkt ist die Kombination aus Level und anschließend
        gegenläufig drehendem Flow interessanter als der statische Wert allein.
        """
    )

    st.markdown("### Eingefrorene Produktionsparameter")
    st.markdown(
        f"""
        - Primärer Commercial-State: **Netto-Perzentil über {NET_VALIDATION_WEEKS} Wochen**
        - 156W Extremgrenzen: **{NET_UPPER_PERCENTILE}/{NET_LOWER_PERCENTILE}**
        - Transition: **Δ1W / Δ4W / Δ8W**, Episoden-Extrem, Extremdauer
        - Release aktiv: **{RELEASE_ACTIVE_WEEKS} Wochen** nach Verlassen der Extremzone
        - Advanced COT-Index: **{COT_INDEX_WEEKS} Wochen**, Grenzen **{INDEX_UPPER}/{INDEX_LOWER}**
        - Advanced Commercial-Range: **{COMMERCIAL_RANGE_WEEKS} Wochen**
        - Legacy-NC-Divergenz (nur Vergleich): **{NC_DIVERGENCE_WEEKS} Wochen**
        - Neue Spec-Flow-Methodik: Preis **{NC_DIV_PRICE_WINDOW_W}W**, Flow **{NC_DIV_FLOW_WINDOW_W}W**, Pfad **{NC_DIV_PATH_WINDOW_W}W**
        - Robuste Flow-Historie: **{NC_DIV_STANDARDIZE_HIST_W}W**, z-Schwelle **{NC_DIV_Z_THRESHOLD:.1f}**
        - OI-Normalisierung: **{NC_DIV_USE_OI_NORM}**
        - COT-Forward-Horizonte: **{FORWARD_HORIZONS_WEEKS[0]} und {FORWARD_HORIZONS_WEEKS[1]} Wochen**
        - Saisonaler IQR-Faktor: **{SEASONAL_OUTLIER_IQR_FACTOR:.2f}**

        Die produktive Marktanalyse hat dafür keine Optimierungsregler. Varianten werden
        getrennt im Research Lab untersucht.
        """
    )

    st.markdown("### Bedingungs-Watchlist")
    st.markdown(
        f"""
        Die Haupt-Watchlist enthält nur **aktive 156W-Releases**, die ihre Bestätigungslogik
        erfüllen. Ein FULL/LOW HEDGE ohne verlassenes Extrem erscheint separat als **Watch / Waiting**.
        Der {range_weeks}W-Range-Wert und der 26W-COT-Index bleiben informativer Kontext und
        blockieren einen ansonsten gültigen 156W-Release nicht mehr.
        """
    )

    st.markdown("### Saisonalität")
    st.markdown(
        """
        Die Saisonalität bleibt vollständig von der COT-Logik getrennt. Der feste
        Primärhorizont beträgt **10 Handelstage**. Die Historienfenster
        **5/10/15/20/30 Jahre** werden immer gemeinsam berechnet, damit kein Fenster
        nachträglich anhand des attraktivsten Ergebnisses ausgewählt werden kann.

        Für jede Fensterlänge werden reale historische Forward-Renditen vom gleichen
        Handelsjahrespunkt berechnet. Die Positiv-Quote wird mit der **marktinternen
        Basisrate aller Kalenderphasen desselben Horizonts** verglichen.
        """
    )

    st.code(
        """
Primäre Saisonfrage:
  Was geschah historisch in den nächsten 10 Handelstagen?

Konsistenz:
  5J / 10J / 15J / 20J / 30J immer gemeinsam
  → Richtung je Fenster
  → Anzahl bullischer / bärischer Fenster
  → kein "ROBUST"-Label

Statistische Einordnung:
  positive Jahre / Stichprobe
  Markt-Basisrate aller Kalenderphasen
  Abstand zur Basisrate in Prozentpunkten
  exakter zweiseitiger Binomial-p-Wert
  95%-Wilson-Konfidenzintervall
  Median / Mittelwert / Streuung

Langfristige Referenz:
  30 Jahre

Horizonte:
  10 / 20 / 40 / 60 Handelstage
  → verschachtelte Zoomstufen
  → keine unabhängigen Bestätigungen

Saisonkurve:
  IQR-gefilterte Tagesbewegungen
  → ausschließlich Visualisierung
        """.strip(),
        language="text",
    )

    st.warning(
        "Continuous-Futures können kalendergebundene Rollsprünge enthalten. "
        "Für Saisonalität ist dies ein potenzieller Bias und nicht nur gewöhnliches Rauschen. "
        "Die aktuelle Yahoo-Reihe ist daher ein Research-Proxy; eine rollbereinigte "
        "Futures-Reihe wäre für eine belastbare Produktionsversion vorzuziehen."
    )

    st.markdown("### Hedger-Timing")
    st.markdown(
        """
        Ein Commercial-Extrem wird als **Setup** behandelt. Das erstmalige Verlassen
        der Extremzone wird separat als **Release** markiert. Dadurch wird nicht
        unterstellt, dass bereits das bloße Erreichen von 80/20 das Timing liefert.
        """
    )

    st.markdown("### Spekulativer Flow & Divergenz · V3.3.2")
    st.markdown(
        f"""
        Die primäre spekulative Gruppe ist **Managed Money** bei Disaggregated-Rohstoffreports
        und **Leveraged Funds** bei TFF-Finanzreports. Legacy Non-Commercial bleibt als
        Vergleichspfad erhalten. Die neue Methodik ist bewusst von den eingefrorenen
        Legacy-Produktionsparametern getrennt.

        Preis- und Positionsdaten werden auf den COT-Stichtag ausgerichtet: verwendet wird
        der letzte Tages-Schlusskurs **≤ Report-Dienstag**. Ein Preis aus einer späteren
        Sitzung ist unzulässig. Fehlt die passende COT-Woche, wird weder 4W- noch 8W-Pfad
        stillschweigend gestreckt.
        """
    )
    st.code(
        f"""
Preis:
  r_4w = log(Preis_t / Preis_t-{NC_DIV_PRICE_WINDOW_W}W)
  z_price = (r_4w - Median) / (IQR / 1.349)

Flow:
  spec_net_oi = (Long - Short) / Open Interest
  d_flow_4w = spec_net_oi_t - spec_net_oi_t-{NC_DIV_FLOW_WINDOW_W}W
  z_flow = robuste Standardisierung über das vorangehende {NC_DIV_STANDARDIZE_HIST_W}W-Kalenderfenster

Pfad:
  rho = Spearman(Preis, spec_net_oi) über {NC_DIV_PATH_WINDOW_W} Wochen = {NC_DIV_PATH_WINDOW_W + 1} Wochenpunkte

Bullische Divergenz:
  z_price <= -{NC_DIV_Z_THRESHOLD:.1f}
  z_flow  >= +{NC_DIV_Z_THRESHOLD:.1f}
  rho < 0

Bärische Divergenz:
  Vorzeichen gespiegelt

Divergenz-Stärke:
  min(|z_price|, |z_flow|) * |rho|
  plus historisches Stärke-Perzentil

Kein Look-ahead:
  Der aktuelle Wert t ist niemals Teil seiner eigenen {NC_DIV_STANDARDIZE_HIST_W}W-Referenzverteilung.

Long-/Short-Schenkel:
  bleiben als separater Befund erhalten; sie werden nicht in einen Gesamtscore eingerechnet.
        """.strip(),
        language="text",
    )

    with st.expander("Legacy-NC-Divergenz · nur Vergleich"):
        st.code(
            f"""
Bullisch Legacy:
  Preis {nc_lookback}W <= -{nc_min_price_move:.2f}%
  NC-Netto / vorheriges NC-Brutto >= +{nc_min_net_move:.2f}%
  NC-Netto steigt in mindestens {nc_min_confirming} von {nc_lookback} Wochen

Bärisch Legacy:
  Vorzeichen gespiegelt
            """.strip(),
            language="text",
        )

st.caption(
    f"Aufgelöster CFTC-Kontraktcode: {code} · Preis-Proxy: {price_ticker} · Spec Flow V3.3.2"
)
