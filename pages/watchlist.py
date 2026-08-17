from __future__ import annotations

from html import escape

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
from src.positioning_regime import (
    classify_regime_stage,
    load_cross_group_context,
    load_price_structure,
)
from src.style import apply_style, empty_state, page_header
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

STAGE_ORDER = {
    "CONTEXT READY": 5,
    "REGIME CONFIRMED": 4,
    "CROSS-GROUP SHIFT": 3,
    "IN TRANSITION": 2,
    "EXTREME WATCH": 1,
    "NORMAL": 0,
}


def de_date(value):
    if value is None or pd.isna(value):
        return "—"
    return pd.Timestamp(value).strftime("%d.%m.%Y")


def market_name_de(value):
    return MARKET_NAME_DE.get(value, value)


def _finite(value, default=np.nan):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if np.isfinite(value) else default


def _fmt(value, digits=1):
    value = _finite(value)
    return "—" if not np.isfinite(value) else f"{value:.{digits}f}"


def _tone_class(tone: str) -> str:
    return {
        "good": "rg-good",
        "warn": "rg-warn",
        "bad": "rg-bad",
        "bull": "rg-good",
        "bear": "rg-bad",
    }.get(str(tone), "rg-neutral")


def _commercial_state(row: pd.Series) -> str:
    phase = str(row.get("cycle_phase", "")).upper()
    ed = int(row.get("extreme_direction", 0) or 0)
    if phase == "RELEASE":
        return "LEAVING EXTREME"
    if phase == "EXTREME" and ed > 0:
        return "FULL HEDGE"
    if phase == "EXTREME" and ed < 0:
        return "LOWER EXTREME"
    return "NORMAL"


def _commercial_transition(row: pd.Series) -> tuple[str, str]:
    phase = str(row.get("cycle_phase", "")).upper()
    raw = str(row.get("transition_state", "") or "").upper()
    if phase == "RELEASE":
        return "CONFIRMED", "good"
    if "EARLY RELEASE" in raw:
        return "EARLY", "warn"
    if "DEEPENING" in raw:
        return "DEEPENING", "bad"
    return "WAITING", "neutral"


def _expected_direction(row: pd.Series) -> int:
    value = int(row.get("context_direction", 0) or 0)
    if value == 0:
        value = int(row.get("extreme_direction", 0) or 0)
    return int(np.sign(value))


def _direction_text(direction: int) -> str:
    return "BULLISH" if direction > 0 else "BEARISH" if direction < 0 else "NEUTRAL"


def _commercial_toward_release(row: pd.Series) -> bool:
    phase = str(row.get("cycle_phase", "")).upper()
    return phase == "RELEASE" or "EARLY RELEASE" in str(row.get("transition_state", "")).upper()


def _season_context(row: pd.Series, expected_direction: int) -> dict:
    if not str(row.get("ticker", "") or "").strip() or expected_direction == 0:
        return {"compact": "—", "overall": "N/V", "overall_rank": 0, "detail": "Kein Preis-Ticker"}
    return calculate_market_20y_multi_seasonality(
        ticker=str(row.get("ticker", "")),
        cot_direction=int(expected_direction),
    )


def _build_pipeline_rows(all_markets: pd.DataFrame) -> pd.DataFrame:
    if all_markets is None or all_markets.empty:
        return pd.DataFrame()

    active = all_markets[
        all_markets["cycle_phase"].astype(str).str.upper().isin(["EXTREME", "RELEASE"])
    ].copy()
    rows = []
    for _, row in active.iterrows():
        direction = _expected_direction(row)
        commercial_transition_active = _commercial_toward_release(row)

        # Divide & conquer: detailed CFTC groups are only queried after the
        # Commercial state itself starts to transition. Pure extremes stay cheap.
        if commercial_transition_active:
            cross = load_cross_group_context(
                str(row.get("asset_class", "")),
                str(row.get("cftc_code", "")),
                direction,
            )
        else:
            cross = {
                "institutional_label": "Asset Manager / Producer",
                "trend_label": "Leveraged / Managed Money",
                "institutional": {},
                "trend": {},
                "nonreportable": {},
                "nonreportable_percentile": np.nan,
                "error": None,
            }

        preliminary = classify_regime_stage(
            cycle_phase=str(row.get("cycle_phase", "")),
            commercial_transition=str(row.get("transition_state", "")),
            institutional=cross.get("institutional"),
            trend=cross.get("trend"),
            nonreportable=cross.get("nonreportable"),
            price=None,
        )

        # Price and seasonality are intentionally late-stage context. They are
        # not downloaded for a static Commercial extreme.
        if preliminary["stage"] >= 3:
            price = load_price_structure(str(row.get("ticker", "")), direction)
            season = _season_context(row, direction)
        else:
            price = {"label": "WARTET", "tone": "neutral", "confirming": False}
            season = {"compact": "—", "overall": "WARTET", "overall_rank": 0, "detail": "Erst nach Cross-Group Shift"}

        stage = classify_regime_stage(
            cycle_phase=str(row.get("cycle_phase", "")),
            commercial_transition=str(row.get("transition_state", "")),
            institutional=cross.get("institutional"),
            trend=cross.get("trend"),
            nonreportable=cross.get("nonreportable"),
            price=price,
        )

        inst = dict(cross.get("institutional") or {})
        trend = dict(cross.get("trend") or {})
        nr = dict(cross.get("nonreportable") or {})
        trans_label, trans_tone = _commercial_transition(row)

        rows.append({
            **row.to_dict(),
            "expected_direction": direction,
            "direction_label": _direction_text(direction),
            "commercial_state_ui": _commercial_state(row),
            "commercial_transition_ui": trans_label,
            "commercial_transition_tone": trans_tone,
            "institutional_label": cross.get("institutional_label", "Institutionell"),
            "institutional_pct": inst.get("percentile", np.nan),
            "institutional_delta_1w": inst.get("delta_1w", np.nan),
            "institutional_delta_2w": inst.get("delta_2w", np.nan),
            "institutional_delta_4w": inst.get("delta_4w", np.nan),
            "institutional_trend": inst.get("label", "WARTET"),
            "institutional_tone": inst.get("tone", "neutral"),
            "institutional_aligned": bool(inst.get("aligned", False)),
            "trend_group_label": cross.get("trend_label", "Trend-Funds"),
            "trend_pct": trend.get("percentile", np.nan),
            "trend_delta_1w": trend.get("delta_1w", np.nan),
            "trend_delta_2w": trend.get("delta_2w", np.nan),
            "trend_delta_4w": trend.get("delta_4w", np.nan),
            "trend_group_state": trend.get("label", "WARTET"),
            "trend_group_tone": trend.get("tone", "neutral"),
            "trend_group_aligned": bool(trend.get("aligned", False)),
            "nonreportable_pct": cross.get("nonreportable_percentile", np.nan),
            "nonreportable_state": nr.get("label", "WARTET"),
            "nonreportable_tone": nr.get("tone", "neutral"),
            "nonreportable_contrarian": bool(nr.get("contrarian", False)),
            "price_state": price.get("label", "—"),
            "price_tone": price.get("tone", "neutral"),
            "price_confirming": bool(price.get("confirming", False)),
            "season_compact": season.get("compact", "—"),
            "season_overall": season.get("overall", "N/V"),
            "season_rank": int(season.get("overall_rank", 0) or 0),
            "season_detail": season.get("detail", ""),
            "regime_stage": int(stage["stage"]),
            "regime_status": stage["label"],
            "regime_tone": stage["tone"],
            "cross_group_error": cross.get("error"),
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["_abs_commercial_extreme"] = (pd.to_numeric(out["commercial_net_percentile"], errors="coerce") - 50.0).abs()
    return out.sort_values(
        ["regime_stage", "_abs_commercial_extreme", "market_name"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def _pipeline_css():
    st.html("""
    <style>
    .rg-kpi-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:10px 0 22px}
    .rg-kpi{background:#fff;border:1px solid #e4e9f0;border-radius:12px;padding:17px 18px;min-height:92px;box-shadow:0 1px 2px rgba(15,23,42,.025)}
    .rg-kpi-label{font-size:11px;font-weight:650;color:#667085;margin-bottom:9px;letter-spacing:.01em}
    .rg-kpi-value{font-size:25px;line-height:1;font-weight:720;color:#101828}
    .rg-kpi-sub{font-size:10px;color:#98a2b3;margin-top:8px}
    .rg-note{background:#fff;border:1px solid #e4e9f0;border-radius:10px;padding:13px 15px;color:#667085;font-size:12px;margin:0 0 22px}
    .rg-stagebar{display:flex;gap:5px;margin-top:7px}.rg-stage-dot{height:6px;flex:1;border-radius:99px;background:#e7ebf0}.rg-stage-dot.on{background:#22c55e}.rg-stage-dot.warn{background:#f59e0b}.rg-stage-dot.bad{background:#ef4444}
    .rg-table-wrap{background:#fff;border:1px solid #e3e8ef;border-radius:13px;overflow-x:auto;box-shadow:0 1px 2px rgba(15,23,42,.025)}
    table.rg-table{width:100%;border-collapse:separate;border-spacing:0;min-width:1450px;font-size:11px;color:#344054}
    .rg-table th{background:#fbfcfe;color:#667085;font-size:9px;font-weight:700;letter-spacing:.045em;text-transform:uppercase;text-align:left;padding:10px 10px;border-bottom:1px solid #e6eaf0;white-space:nowrap}
    .rg-table th.group{text-align:center;color:#475467;background:#f8fafc}
    .rg-table td{padding:12px 10px;border-bottom:1px solid #eef1f5;vertical-align:middle;background:#fff}
    .rg-table tr:last-child td{border-bottom:0}.rg-table tr:hover td{background:#fbfdfb}
    .rg-market{display:flex;align-items:center;gap:9px;min-width:180px}.rg-star{color:#98a2b3;font-size:15px}.rg-market a{color:#101828;text-decoration:none;font-weight:650}.rg-market a:hover{color:#16a34a}.rg-symbol{font-size:9px;color:#98a2b3;margin-top:2px}
    .rg-pct{font-size:14px;font-weight:720;color:#101828}.rg-sub{font-size:9px;color:#98a2b3;margin-top:3px;white-space:nowrap}
    .rg-chip{display:inline-flex;align-items:center;padding:4px 7px;border-radius:6px;font-size:9px;font-weight:700;white-space:nowrap;border:1px solid transparent}
    .rg-good{color:#15803d;background:#eefbf2;border-color:#d7f3df}.rg-warn{color:#b45309;background:#fff8e8;border-color:#fce9b8}.rg-bad{color:#dc2626;background:#fff1f1;border-color:#ffdada}.rg-neutral{color:#667085;background:#f5f7f9;border-color:#e7ebef}
    .rg-arrow-good{color:#16a34a;font-weight:700}.rg-arrow-bad{color:#ef4444;font-weight:700}.rg-arrow-neutral{color:#98a2b3}
    .rg-status{font-size:9px;font-weight:750;line-height:1.25;text-transform:uppercase}.rg-status.good{color:#15803d}.rg-status.warn{color:#b45309}.rg-status.bad{color:#dc2626}.rg-status.neutral{color:#667085}
    .rg-legend{display:grid;grid-template-columns:repeat(5,1fr);gap:0;margin-top:0;background:#fff;border:1px solid #e3e8ef;border-top:0;border-radius:0 0 13px 13px;padding:14px 16px}
    .rg-legend-block{padding:0 14px;border-right:1px solid #eef1f5}.rg-legend-block:last-child{border-right:0}.rg-legend-title{font-size:9px;font-weight:750;color:#475467;text-transform:uppercase;margin-bottom:7px}.rg-legend-line{font-size:9px;color:#667085;line-height:1.7}
    @media(max-width:1100px){.rg-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.rg-legend{grid-template-columns:1fr 1fr}.rg-legend-block{border-right:0;border-bottom:1px solid #eef1f5;padding:10px}}
    </style>
    """)


def _kpis(df: pd.DataFrame, report_date):
    counts = {stage: int((df["regime_stage"] == stage).sum()) for stage in range(1, 6)} if not df.empty else {}
    cards = [
        ("COT-Report", de_date(report_date), "letzter verfügbarer Report"),
        ("Extreme Watch", str(counts.get(1, 0)), "Commercial 156W historisch extrem"),
        ("In Transition", str(counts.get(2, 0)), "Commercial beginnt sich zu lösen"),
        ("Cross-Group Shift", str(counts.get(3, 0)), "andere Gruppen reagieren"),
        ("Regime / Context", str(counts.get(4, 0) + counts.get(5, 0)), f"davon {counts.get(5,0)} mit Preisbestätigung"),
    ]
    html = '<div class="rg-kpi-grid">' + ''.join(
        f'<div class="rg-kpi"><div class="rg-kpi-label">{escape(a)}</div><div class="rg-kpi-value">{escape(b)}</div><div class="rg-kpi-sub">{escape(c)}</div></div>'
        for a, b, c in cards
    ) + '</div>'
    st.html(html)


def _delta_html(value: float, direction_to_release: int | None = None) -> str:
    value = _finite(value)
    if not np.isfinite(value):
        return '<span class="rg-arrow-neutral">—</span>'
    arrow = "↑" if value > 0 else "↓" if value < 0 else "→"
    cls = "rg-arrow-neutral"
    if direction_to_release is not None and value != 0:
        # For Commercial, direction_to_release is -extreme_direction.
        cls = "rg-arrow-good" if np.sign(value) == np.sign(direction_to_release) else "rg-arrow-bad"
    return f'<span class="{cls}">{arrow} {value:+.1f}</span>'


def _stage_dots(stage: int) -> str:
    dots = []
    for i in range(1, 6):
        dots.append(f'<span class="rg-stage-dot {"on" if i <= int(stage) else ""}"></span>')
    return '<div class="rg-stagebar">' + ''.join(dots) + '</div>'


def _market_rows_html(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    rows = []
    for _, r in df.iterrows():
        symbol = escape(str(r.get("symbol", "")))
        name = escape(str(market_name_de(r.get("market_name", ""))))
        state = escape(str(r.get("commercial_state_ui", "—")))
        trans = escape(str(r.get("commercial_transition_ui", "—")))
        trans_cls = _tone_class(str(r.get("commercial_transition_tone", "neutral")))
        commercial_delta = _finite(r.get("commercial_percentile_change_4w"))
        release_direction = -int(r.get("extreme_direction", 0) or 0)
        inst_cls = _tone_class(str(r.get("institutional_tone", "neutral")))
        trend_cls = _tone_class(str(r.get("trend_group_tone", "neutral")))
        nr_cls = _tone_class(str(r.get("nonreportable_tone", "neutral")))
        px_cls = _tone_class(str(r.get("price_tone", "neutral")))
        stage_tone = str(r.get("regime_tone", "neutral"))
        season_tone = "rg-good" if int(r.get("season_rank", 0) or 0) >= 3 else "rg-warn" if int(r.get("season_rank", 0) or 0) == 2 else "rg-neutral"
        rows.append(f"""
        <tr>
          <td><div class="rg-market"><span class="rg-star">☆</span><div><a href="?open_market={symbol}">{name}</a><div class="rg-symbol">{symbol} · {escape(str(r.get('asset_class','')))}</div></div></div></td>
          <td><div class="rg-pct">{_fmt(r.get('commercial_net_percentile'))}</div><div class="rg-sub">156W Percentile</div></td>
          <td><span class="rg-chip rg-neutral">{state}</span></td>
          <td>{_delta_html(commercial_delta, release_direction)}<div class="rg-sub">Δ4W</div></td>
          <td><span class="rg-chip {trans_cls}">{trans}</span></td>
          <td><div class="rg-pct">{_fmt(r.get('institutional_pct'))}</div><div class="rg-sub">{escape(str(r.get('institutional_label','')))}</div></td>
          <td><span class="rg-chip {inst_cls}">{escape(str(r.get('institutional_trend','WARTET')))}</span><div class="rg-sub">Δ4W {_fmt(r.get('institutional_delta_4w'))}</div></td>
          <td><div class="rg-pct">{_fmt(r.get('trend_pct'))}</div><div class="rg-sub">{escape(str(r.get('trend_group_label','')))}</div></td>
          <td><span class="rg-chip {trend_cls}">{escape(str(r.get('trend_group_state','WARTET')))}</span><div class="rg-sub">Δ4W {_fmt(r.get('trend_delta_4w'))}</div></td>
          <td><div class="rg-pct">{_fmt(r.get('nonreportable_pct'))}</div><div class="rg-sub">156W Percentile</div></td>
          <td><span class="rg-chip {nr_cls}">{escape(str(r.get('nonreportable_state','WARTET')))}</span></td>
          <td><span class="rg-chip {px_cls}">{escape(str(r.get('price_state','—')))}</span></td>
          <td><span class="rg-chip {season_tone}" title="{escape(str(r.get('season_detail','')))}">{escape(str(r.get('season_compact','—')))}</span></td>
          <td><div class="rg-status {escape(stage_tone)}">{escape(str(r.get('regime_status','—')))}</div>{_stage_dots(int(r.get('regime_stage',0) or 0))}</td>
          <td style="text-align:right;color:#98a2b3;font-size:18px">›</td>
        </tr>
        """)
    return ''.join(rows)


def _render_table(df: pd.DataFrame):
    if df.empty:
        empty_state("Keine Märkte in dieser Phase", "Für den aktuellen Report erfüllt kein Markt diesen Pipeline-Zustand.")
        return
    html = f"""
    <div class="rg-table-wrap">
      <table class="rg-table">
        <thead>
          <tr>
            <th rowspan="2">Markt</th>
            <th class="group" colspan="4">1 · Commercial / Hedger</th>
            <th class="group" colspan="2">2 · Institutionell</th>
            <th class="group" colspan="2">3 · Trend-Funds</th>
            <th class="group" colspan="2">4 · Nonreportable</th>
            <th class="group" colspan="2">Kontext</th>
            <th class="group" colspan="2">Regime</th>
          </tr>
          <tr>
            <th>156W Pctl</th><th>State</th><th>Transition</th><th>Release</th>
            <th>156W Pctl</th><th>Trend 1–4W</th>
            <th>156W Pctl</th><th>Trend 1–4W</th>
            <th>156W Pctl</th><th>Konträr</th>
            <th>Price</th><th>Season</th><th>Status</th><th></th>
          </tr>
        </thead>
        <tbody>{_market_rows_html(df)}</tbody>
      </table>
    </div>
    <div class="rg-legend">
      <div class="rg-legend-block"><div class="rg-legend-title">Commercial State</div><div class="rg-legend-line">FULL HEDGE / LOWER EXTREME = historisch extrem.<br>Das Extrem allein ist kein Signal.</div></div>
      <div class="rg-legend-block"><div class="rg-legend-title">Transition</div><div class="rg-legend-line">Δ1W / Δ2W / Δ4W beobachten.<br>EARLY = Extrem beginnt sich zu lösen.</div></div>
      <div class="rg-legend-block"><div class="rg-legend-title">Cross-Group</div><div class="rg-legend-line">Asset Manager / Producer und Leveraged / Managed Money werden separat überwacht.</div></div>
      <div class="rg-legend-block"><div class="rg-legend-title">Nonreportable</div><div class="rg-legend-line">Konträrer Kontext. Nicht automatisch mit „Retail“ gleichsetzen.</div></div>
      <div class="rg-legend-block"><div class="rg-legend-title">5 Phasen</div><div class="rg-legend-line">Extreme → Transition → Cross-Group → Confirmed → Context Ready.<br>S&amp;D bleibt manuelle Trade-Entscheidung.</div></div>
    </div>
    """
    st.html(html)


def _trader_direction_label(row: pd.Series) -> tuple[str, str]:
    direction = int(row.get("expected_direction", 0) or 0)
    stage = int(row.get("regime_stage", 0) or 0)
    if direction > 0:
        return ("BULLISH" if stage >= 4 else "BULLISH WATCH", "bull")
    if direction < 0:
        return ("BEARISH" if stage >= 4 else "BEARISH WATCH", "bear")
    return ("NEUTRAL", "neutral")


def _trader_phase_summary(stage: int) -> str:
    return {
        1: "Commercials historisch extrem",
        2: "Hedge beginnt sich zu lösen",
        3: "Weitere CFTC-Gruppen drehen mit",
        4: "Positionierungsregime bestätigt",
        5: "Positionierung + Preis bestätigt",
    }.get(int(stage), "Kein aktiver Regime-Zyklus")


def _trader_next_step(row: pd.Series) -> str:
    stage = int(row.get("regime_stage", 0) or 0)
    if stage <= 0:
        return "Auf neues 156W-Extrem warten"
    if stage == 1:
        return "Auf Transition warten"
    if stage == 2:
        return "Auf Cross-Group Shift warten"
    if stage == 3:
        if str(row.get("cycle_phase", "")).upper() != "RELEASE":
            return "Auf Commercial Release warten"
        if not bool(row.get("institutional_aligned", False)):
            return "Institutionelle Bestätigung fehlt"
        if not bool(row.get("trend_group_aligned", False)):
            return "Trend-Funds-Bestätigung fehlt"
        if not bool(row.get("nonreportable_contrarian", False)):
            return "Konträrer Kontext fehlt"
        return "Auf vollständige Regime-Bestätigung warten"
    if stage == 4:
        return "Auf Preisbestätigung warten"
    return "S&D-Setup prüfen"


def _trader_context(row: pd.Series) -> str:
    stage = int(row.get("regime_stage", 0) or 0)
    if stage < 4:
        return '<span class="tw-muted">—</span>'

    price = escape(str(row.get("price_state", "—")))
    season = escape(str(row.get("season_overall", "N/V")))
    price_cls = _tone_class(str(row.get("price_tone", "neutral")))

    if stage >= 5:
        return (
            f'<span class="tw-context-ok">✓ Preis · {price}</span>'
            f'<div class="tw-context-sub">Saison · {season}</div>'
        )

    return (
        f'<span class="rg-chip {price_cls}">{price}</span>'
        f'<div class="tw-context-sub">Saison · {season}</div>'
    )


def _trader_rows_html(df: pd.DataFrame) -> str:
    rows = []
    for _, row in df.iterrows():
        symbol = escape(str(row.get("symbol", "")))
        name = escape(str(market_name_de(row.get("market_name", ""))))
        asset_class = escape(str(row.get("asset_class", "")))
        stage = int(row.get("regime_stage", 0) or 0)
        stage_label = escape(str(row.get("regime_status", "NORMAL")))
        direction_label, direction_class = _trader_direction_label(row)
        summary = escape(_trader_phase_summary(stage))
        next_step = escape(_trader_next_step(row))

        rows.append(
            f"""
            <tr>
              <td>
                <div class="tw-market">
                  <span class="tw-star">☆</span>
                  <div>
                    <a href="?open_market={symbol}">{name}</a>
                    <div class="tw-sub">{symbol} · {asset_class}</div>
                  </div>
                </div>
              </td>
              <td>
                <div class="tw-direction {direction_class}">{escape(direction_label)}</div>
              </td>
              <td>
                <div class="tw-phase-head">
                  <strong>{stage_label}</strong>
                  <span>{stage}/5</span>
                </div>
                {_stage_dots(stage)}
              </td>
              <td>
                <div class="tw-summary">{summary}</div>
              </td>
              <td>
                <div class="tw-next">{next_step}</div>
              </td>
              <td>
                {_trader_context(row)}
              </td>
              <td class="tw-open">›</td>
            </tr>
            """
        )
    return "".join(rows)


def _render_trader_table(df: pd.DataFrame):
    if df.empty:
        empty_state(
            "Keine Märkte in dieser Phase",
            "Für den aktuellen Report erfüllt kein Markt diesen Pipeline-Zustand.",
        )
        return

    st.html(
        f"""
        <style>
        .tw-wrap{{
            background:#fff;
            border:1px solid #e3e8ef;
            border-radius:13px;
            overflow:hidden;
            box-shadow:0 1px 2px rgba(15,23,42,.025);
        }}
        table.tw-table{{
            width:100%;
            border-collapse:collapse;
            table-layout:fixed;
            color:#344054;
        }}
        .tw-table th{{
            background:#fbfcfe;
            color:#667085;
            font-size:9px;
            font-weight:750;
            letter-spacing:.055em;
            text-transform:uppercase;
            text-align:left;
            padding:11px 12px;
            border-bottom:1px solid #e6eaf0;
        }}
        .tw-table td{{
            padding:14px 12px;
            border-bottom:1px solid #eef1f5;
            vertical-align:middle;
            background:#fff;
        }}
        .tw-table tr:last-child td{{border-bottom:0}}
        .tw-table tr:hover td{{background:#fbfdfb}}
        .tw-market{{display:flex;align-items:center;gap:9px}}
        .tw-star{{font-size:15px;color:#98a2b3}}
        .tw-market a{{font-size:12px;color:#101828;text-decoration:none;font-weight:720}}
        .tw-market a:hover{{color:#16a34a}}
        .tw-sub{{font-size:9px;color:#98a2b3;margin-top:3px}}
        .tw-direction{{font-size:10px;font-weight:800;letter-spacing:.025em}}
        .tw-direction.bull{{color:#15803d}}
        .tw-direction.bear{{color:#dc2626}}
        .tw-direction.neutral{{color:#667085}}
        .tw-phase-head{{display:flex;align-items:center;justify-content:space-between;gap:8px}}
        .tw-phase-head strong{{font-size:10px;color:#344054}}
        .tw-phase-head span{{font-size:9px;color:#98a2b3}}
        .tw-summary{{font-size:11px;font-weight:630;color:#475467;line-height:1.4}}
        .tw-next{{font-size:11px;font-weight:700;color:#101828;line-height:1.4}}
        .tw-context-ok{{font-size:10px;font-weight:750;color:#15803d}}
        .tw-context-sub{{font-size:9px;color:#98a2b3;margin-top:4px}}
        .tw-muted{{font-size:11px;color:#c0c7d1}}
        .tw-open{{text-align:right;color:#98a2b3;font-size:19px}}
        .tw-table .rg-stagebar{{max-width:120px;margin-top:7px}}
        .tw-table th:nth-child(1){{width:17%}}
        .tw-table th:nth-child(2){{width:12%}}
        .tw-table th:nth-child(3){{width:17%}}
        .tw-table th:nth-child(4){{width:19%}}
        .tw-table th:nth-child(5){{width:22%}}
        .tw-table th:nth-child(6){{width:11%}}
        .tw-table th:nth-child(7){{width:2%}}
        @media(max-width:1050px){{
            .tw-table th:nth-child(4),.tw-table td:nth-child(4){{display:none}}
            .tw-table th:nth-child(1){{width:22%}}
            .tw-table th:nth-child(2){{width:15%}}
            .tw-table th:nth-child(3){{width:22%}}
            .tw-table th:nth-child(5){{width:25%}}
            .tw-table th:nth-child(6){{width:14%}}
            .tw-table th:nth-child(7){{width:2%}}
        }}
        </style>
        <div class="tw-wrap">
          <table class="tw-table">
            <thead>
              <tr>
                <th>Markt</th>
                <th>Richtung</th>
                <th>Regime</th>
                <th>Was passiert?</th>
                <th>Nächster Schritt</th>
                <th>Kontext</th>
                <th></th>
              </tr>
            </thead>
            <tbody>{_trader_rows_html(df)}</tbody>
          </table>
        </div>
        """
    )


_pipeline_css()
page_header(
    "Research · Positioning Regime",
    "COT Positioning Watchlist",
    "Institutionelle Positionierungszyklen Schritt für Schritt beobachten. Erst das Zusammenspiel erzeugt Trade-Kontext.",
    "V3.10.0 · DIVIDE & CONQUER",
)

with st.spinner("Commercial-156W-Zustände werden geprüft …"):
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
with st.spinner("Transitions und CFTC-Gruppen werden nach Pipeline-Stufe ergänzt …"):
    pipeline = _build_pipeline_rows(all_markets)

# Click-through from custom HTML table.
open_symbol = str(st.query_params.get("open_market", "") or "").strip()
if open_symbol and not pipeline.empty:
    match = pipeline[pipeline["symbol"].astype(str).eq(open_symbol)]
    if not match.empty:
        r = match.iloc[0]
        handoff = {"asset_class": r["asset_class"], "market_name": r["market_name"]}
        st.session_state["selected_market"] = handoff
        st.session_state["_market_context_handoff"] = handoff
        st.query_params.clear()
        st.switch_page("pages/marktanalyse.py")

_kpis(pipeline, scan.get("latest_report"))
st.html(
    '<div class="rg-note"><b>Teile &amp; herrsche:</b> Commercial Net Percentile 156W ist die Ausgangslage. '
    'Ein Extrem erhöht nur die Aufmerksamkeit. Erst Transition → andere CFTC-Gruppen → konträrer Nonreportable-Kontext → Preisstruktur erzeugen schrittweise Evidenz. '
    '<b>Der 26W-COT-Index ist aus dieser Hauptansicht entfernt</b> und bleibt nur im Advanced Research / als ML-Feature erhalten.</div>'
)

if pipeline.empty:
    empty_state("Keine aktiven Positionierungszyklen", "Aktuell steht kein Markt in einer 156W-Extrem- oder aktiven Release-Phase.")
else:
    c1, c2, c3 = st.columns([1.25, 1, 1], gap="small")
    with c1:
        view = st.radio(
            "Phase",
            ["Alle", "Extreme", "Transition", "Cross-Group", "Confirmed", "Context Ready"],
            horizontal=True,
            label_visibility="collapsed",
        )
    with c2:
        segment = st.selectbox("Segment", ["Alle", "FINANZWERTE", "ROHSTOFFE"], label_visibility="collapsed")
    with c3:
        direction_filter = st.selectbox("Richtung", ["Alle Richtungen", "Bullish Reversal", "Bearish Reversal"], label_visibility="collapsed")

    filtered = pipeline.copy()
    stage_map = {"Extreme": 1, "Transition": 2, "Cross-Group": 3, "Confirmed": 4, "Context Ready": 5}
    if view in stage_map:
        filtered = filtered[filtered["regime_stage"] == stage_map[view]]
    if segment != "Alle":
        filtered = filtered[filtered["segment"].astype(str).eq(segment)]
    if direction_filter == "Bullish Reversal":
        filtered = filtered[pd.to_numeric(filtered["expected_direction"], errors="coerce") > 0]
    elif direction_filter == "Bearish Reversal":
        filtered = filtered[pd.to_numeric(filtered["expected_direction"], errors="coerce") < 0]

    trader_view = filtered.reset_index(drop=True)
    _render_trader_table(trader_view)

    with st.expander("Quant-Details · COT-Gruppen & Rohdaten", expanded=False):
        st.caption(
            "Vollständige Research-Ansicht für Quant-Kontrolle. "
            "Die Trader-Watchlist oben verwendet ausschließlich die bereits berechnete Regime-Verdichtung."
        )
        _render_table(trader_view)

    with st.expander("Pipeline-Logik & 1–4W-Beobachtung", expanded=False):
        st.markdown(f"""
**1 · Commercial 156W State**
`≥ {NET_UPPER_PERCENTILE}` oder `≤ {NET_LOWER_PERCENTILE}` bedeutet nur **historisch extrem**. Keine Richtung wird daraus automatisch abgeleitet.

**2 · Commercial Transition**
Wir beobachten `Δ1W`, `Δ2W` und `Δ4W`. Eine Bewegung aus dem Extrem wird zunächst als **EARLY** geführt. Erst der tatsächliche Zonenaustritt ist ein bestätigter Commercial Release.

**3 · Cross-Group Shift**
Bei Finanzwerten: **Asset Manager + Leveraged Funds**. Bei Rohstoffen: **Producer/Merchant + Managed Money**. Entscheidend ist nicht nur der aktuelle Percentile-Wert, sondern ob sich die jeweilige Netto-Position über 1–4 Wochen in Richtung des möglichen neuen Regimes verändert.

**4 · Nonreportable Context**
Die kleineren, nicht meldepflichtigen Positionen werden als konträrer Kontext beobachtet. `Nonreportable` wird bewusst **nicht** automatisch als Retail bezeichnet.

**5 · Price / Seasonality**
Preisstruktur und Saisonalität werden erst spät ergänzt. **CONTEXT READY ist noch kein Trade**: Supply-&-Demand-Zone, Entry, SL und TP bleiben im Trade Planner eine separate manuelle Entscheidung.

Der **26W-COT-Index bleibt erhalten**, ist aber aus der operativen Watchlist entfernt. Er bleibt im Advanced Research und in historischen Snapshots für spätere ML-/Out-of-Sample-Vergleiche verfügbar.
""")

if not scan["errors"].empty:
    with st.expander(f"Datenprobleme · {len(scan['errors'])} Märkte", expanded=False):
        st.dataframe(scan["errors"], use_container_width=True, hide_index=True)
