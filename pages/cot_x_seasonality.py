from __future__ import annotations
# V3.22.10.2 · TEXT COLOR UI
# V3.22.10.1 · HTML RENDER FIX
# V3.22.10 · COT × SEASONALITY TURN UI

import html

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
from src.cot_x_seasonality import (
    build_group_flow_map,
    seasonal_edge_context,
    simple_cot_seasonality_turn_read,
    simple_turn_group_selection,
)
from src.markets import CLASSIC_MARKETS
from src.prices import load_prices
from src.report_analysis import enrich_report_positioning
from src.seasonality_edge_research import (
    current_phase_day,
    nearest_turn_context,
    seasonal_template,
    stability_table,
)
from src.style import (
    apply_style,
    context_strip,
    definition,
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

FLOW_LABEL_DE = {
    "STRONG BULLISH": "stark bullish",
    "BULLISH": "bullish",
    "SLIGHT BULLISH": "leicht bullish",
    "BULLISH DELEVERAGING": "bullish · Positionsabbau",
    "STRONG BEARISH": "stark bearish",
    "BEARISH": "bearish",
    "SLIGHT BEARISH": "leicht bearish",
    "BEARISH DELEVERAGING": "bearish · Positionsabbau",
    "TWO-SIDED": "beidseitiger Aufbau",
    "DELEVERAGING": "beidseitiger Abbau",
    "NEUTRAL": "neutral",
    "MIXED": "gemischt",
}

EVOLUTION_DE = {
    "BULLISH → BEARISH REVERSAL": "bullish → bearishe Umkehr",
    "BULLISH → BEARISH → STALLING": "bullish → bearish → stockend",
    "BULLISH → BEARISH → REBOUND": "bullish → bearish → Gegenreaktion",
    "BEARISH → BULLISH REVERSAL": "bearish → bullishe Umkehr",
    "BEARISH → BULLISH → STALLING": "bearish → bullish → stockend",
    "BEARISH → BULLISH → PULLBACK": "bearish → bullish → Rücklauf",
    "PERSISTENT BULLISH": "durchgehend bullish",
    "PERSISTENT BEARISH": "durchgehend bearish",
    "RECENT BEARISH": "zuletzt bearish",
    "RECENT BULLISH": "zuletzt bullish",
    "MIXED / TRANSITION": "gemischt / Übergang",
}

TURN_STATE_DE = {
    "SUPPORTS TURN": "unterstützt den Turn",
    "REVERSAL INTO TURN": "dreht in Turn-Richtung",
    "EARLY SUPPORT": "frühe Unterstützung",
    "OPPOSES TURN": "widerspricht dem Turn",
    "RECENTLY OPPOSES": "zuletzt gegen den Turn",
    "MIXED / TRANSITION": "gemischt / Übergang",
    "STRONG CONTRARIAN SUPPORT": "stark konträr unterstützend",
    "CONTRARIAN SUPPORT": "konträr unterstützend",
    "CONTRARIANLY OPPOSES": "konträr gegen den Turn",
    "NEUTRAL / MIXED": "neutral / gemischt",
    "N/V": "n/v",
}

TONE = {
    "bullish": {
        "bg": "#ecfdf3",
        "border": "#22c55e",
        "text": "#166534",
        "soft": "#dcfce7",
    },
    "bearish": {
        "bg": "#fff1f2",
        "border": "#ef4444",
        "text": "#991b1b",
        "soft": "#fee2e2",
    },
    "warning": {
        "bg": "#fffbeb",
        "border": "#f59e0b",
        "text": "#92400e",
        "soft": "#fef3c7",
    },
    "neutral": {
        "bg": "#f8fafc",
        "border": "#cbd5e1",
        "text": "#334155",
        "soft": "#f1f5f9",
    },
    "momentum": {
        "bg": "#eff6ff",
        "border": "#3b82f6",
        "text": "#1e40af",
        "soft": "#dbeafe",
    },
}


def _finite(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return np.nan
    return x if np.isfinite(x) else np.nan


def _pct(value, digits=2):
    x = _finite(value)
    return "—" if not np.isfinite(x) else f"{x:+.{digits}%}"


def _contracts(value):
    x = _finite(value)
    return "—" if not np.isfinite(x) else f"{x:+,.0f}"


def _esc(value):
    return html.escape(str(value))


def _tone_for_direction(direction):
    direction = int(direction or 0)
    if direction > 0:
        return "bullish"
    if direction < 0:
        return "bearish"
    return "neutral"


def _render_inline_html(markup):
    """Render inline HTML without Markdown treating nested indentation as code."""
    compact = "".join(
        line.strip()
        for line in str(markup).splitlines()
        if line.strip()
    )
    st.markdown(
        compact,
        unsafe_allow_html=True,
    )

def _direction_text_color(direction):
    direction = int(direction or 0)
    if direction > 0:
        return TONE["bullish"]["text"]
    if direction < 0:
        return TONE["bearish"]["text"]
    return TONE["neutral"]["text"]

def _status_card(
    title,
    value,
    subtitle="",
    *,
    tone="neutral",
    emphasis=False,
):
    palette = TONE.get(
        tone,
        TONE["neutral"],
    )

    markup = f"""
    <div style="
        background:#ffffff;
        border:1px solid #dbe3ee;
        border-radius:12px;
        padding:15px 16px;
        min-height:108px;
    ">
        <div style="
            font-size:11px;
            font-weight:700;
            letter-spacing:.06em;
            text-transform:uppercase;
            color:#64748b;
            margin-bottom:7px;
        ">{_esc(title)}</div>
        <div style="
            font-size:23px;
            line-height:1.08;
            font-weight:800;
            color:{palette['text']};
            margin-bottom:7px;
        ">{_esc(value)}</div>
        <div style="
            font-size:12px;
            line-height:1.35;
            color:#64748b;
        ">{_esc(subtitle)}</div>
    </div>
    """

    _render_inline_html(
        markup
    )




def _banner(
    title,
    subtitle,
    *,
    tone="neutral",
):
    palette = TONE.get(
        tone,
        TONE["neutral"],
    )

    markup = f"""
    <div style="
        padding:10px 2px 12px 2px;
        margin-top:4px;
        margin-bottom:6px;
    ">
        <div style="
            font-size:18px;
            font-weight:800;
            color:{palette['text']};
            margin-bottom:3px;
        ">{_esc(title)}</div>
        <div style="
            font-size:13px;
            color:#64748b;
        ">{_esc(subtitle)}</div>
    </div>
    """

    _render_inline_html(
        markup
    )




def _flow_label(window):
    window = dict(window or {})
    label = str(window.get("label", "N/V"))
    return FLOW_LABEL_DE.get(
        label,
        label.lower() if label != "N/V" else "n/v",
    )


def _flow_chip(window):
    window = dict(window or {})
    direction = int(
        window.get("direction", 0) or 0
    )
    color = _direction_text_color(
        direction
    )
    text = _flow_label(window)

    return (
        f'<span style="'
        f'color:{color};'
        f'font-size:12px;'
        f'font-weight:800;'
        f'white-space:nowrap;'
        f'">{_esc(text)}</span>'
    )



def _turn_state(read):
    read = dict(read or {})
    state = str(
        read.get("state", "N/V")
    )
    return TURN_STATE_DE.get(
        state,
        state.lower(),
    )


def _relation_tone(read, turn_direction):
    read = dict(read or {})
    target_tone = _tone_for_direction(
        turn_direction
    )

    if read.get("supports"):
        return target_tone

    if read.get("opposes"):
        return (
            "bullish"
            if target_tone == "bearish"
            else "bearish"
            if target_tone == "bullish"
            else "warning"
        )

    return "warning"


def _group_card(
    title,
    subtitle,
    summary,
    read,
    turn_direction,
    *,
    momentum=False,
):
    summary = dict(
        summary or {}
    )
    read = dict(
        read or {}
    )

    if not summary.get(
        "available"
    ):
        _status_card(
            title,
            "keine Daten",
            subtitle,
            tone="neutral",
            emphasis=momentum,
        )
        return

    relation_tone = (
        _relation_tone(
            read,
            turn_direction,
        )
    )
    relation_color = TONE[
        relation_tone
    ]["text"]

    evolution = EVOLUTION_DE.get(
        str(
            summary.get(
                "evolution",
                "N/V",
            )
        ),
        str(
            summary.get(
                "evolution",
                "N/V",
            )
        ).lower(),
    )

    border = (
        "2px solid #3b82f6"
        if momentum
        else "1px solid #dbe3ee"
    )

    markup = f"""
    <div style="
        background:#ffffff;
        border:{border};
        border-radius:12px;
        padding:16px;
        min-height:235px;
    ">
        <div style="
            font-size:18px;
            font-weight:800;
            color:#0f172a;
            margin-bottom:2px;
        ">{_esc(title)}</div>

        <div style="
            font-size:11px;
            color:#64748b;
            min-height:30px;
            margin-bottom:13px;
        ">{_esc(subtitle)}</div>

        <div style="
            display:grid;
            grid-template-columns:1fr 1fr 1fr;
            gap:8px;
            margin-bottom:15px;
        ">
            <div>
                <div style="
                    font-size:10px;
                    color:#94a3b8;
                    margin-bottom:3px;
                ">4W</div>
                {_flow_chip(summary.get('w4'))}
            </div>
            <div>
                <div style="
                    font-size:10px;
                    color:#94a3b8;
                    margin-bottom:3px;
                ">2W</div>
                {_flow_chip(summary.get('w2'))}
            </div>
            <div>
                <div style="
                    font-size:10px;
                    color:#94a3b8;
                    margin-bottom:3px;
                ">1W</div>
                {_flow_chip(summary.get('w1'))}
            </div>
        </div>

        <div style="
            font-size:11px;
            color:#64748b;
            margin-bottom:4px;
        ">Verlauf</div>

        <div style="
            font-size:13px;
            font-weight:700;
            color:#334155;
            min-height:38px;
            margin-bottom:10px;
        ">{_esc(evolution)}</div>

        <div style="
            font-size:13px;
            font-weight:800;
            color:{relation_color};
        ">{_esc(_turn_state(read))}</div>
    </div>
    """

    _render_inline_html(
        markup
    )




def _localized_final_read(
    final_read,
):
    final_read = dict(final_read or {})
    direction = int(
        final_read.get(
            "direction",
            0,
        ) or 0
    )
    quality = str(
        final_read.get(
            "quality",
            "MIXED",
        )
    )

    if direction < 0:
        headline = "BEARISHES TOP"
        tone = "bearish"
    elif direction > 0:
        headline = "BULLISHES BOTTOM"
        tone = "bullish"
    else:
        headline = "KEIN KLARER TURN"
        tone = "neutral"

    quality_text = {
        "STRONG": "STARK BESTÄTIGT",
        "MODERATE+": "MODERAT+ BESTÄTIGT",
        "MODERATE": "MODERAT BESTÄTIGT",
        "MIXED": "GEMISCHT",
        "CONFLICT": "KONFLIKT",
        "WEAK / OPPOSED": "SCHWACH / WIDERSPROCHEN",
        "NO ACTIVE TURN": "KEIN AKTIVER TURN",
    }.get(
        quality,
        quality,
    )

    if quality in {
        "MIXED",
        "CONFLICT",
        "WEAK / OPPOSED",
        "NO ACTIVE TURN",
    }:
        tone = (
            "warning"
            if quality != "NO ACTIVE TURN"
            else "neutral"
        )

    return {
        "headline": headline,
        "quality_text": quality_text,
        "tone": tone,
    }


page_header(
    "Research · COT × Seasonality",
    "COT × Seasonality",
    "Einfacher Turn-Check: robuste Seasonality + Commercial-Seite + Momentum-Funds + Nonreportables.",
    "V3.22.10 · TURN UI",
)

st.caption(
    "Research only · keine Watchlist-Änderung · kein Entry-Signal · kein Composite Score."
)

_context = st.session_state.pop(
    "_market_context_handoff",
    None,
)
_selected = st.session_state.get(
    "selected_market"
)

if _context:
    st.session_state[
        "cxs_asset_class"
    ] = _context["asset_class"]
    st.session_state[
        "cxs_market"
    ] = _context["market_name"]
elif (
    _selected
    and "cxs_asset_class"
    not in st.session_state
):
    st.session_state[
        "cxs_asset_class"
    ] = _selected["asset_class"]
    st.session_state[
        "cxs_market"
    ] = _selected["market_name"]

with st.container(border=True):
    c1, c2 = st.columns(
        2,
        gap="small",
    )

    with c1:
        asset_class = st.selectbox(
            "Assetklasse",
            list(
                CLASSIC_MARKETS.keys()
            ),
            format_func=lambda x: (
                ASSET_CLASS_DE.get(x, x)
            ),
            key="cxs_asset_class",
        )

    markets = CLASSIC_MARKETS[
        asset_class
    ]
    names = [
        market["name"]
        for market in markets
    ]

    if (
        st.session_state.get(
            "cxs_market"
        )
        not in names
    ):
        st.session_state[
            "cxs_market"
        ] = names[0]

    with c2:
        market_name = st.selectbox(
            "Markt",
            names,
            key="cxs_market",
        )

    market = next(
        item
        for item in markets
        if item["name"] == market_name
    )
    price_ticker = market["ticker"]

    st.session_state[
        "selected_market"
    ] = {
        "asset_class": asset_class,
        "market_name": market_name,
    }

    st.caption(
        f"Preis-Proxy automatisch: **{price_ticker}** · "
        "Seasonality: 20J Primärhistorie, Robustheit über 10J/15J/20J/30J."
    )

price_start = (
    pd.Timestamp.today().normalize()
    - pd.DateOffset(years=35)
)

prices = load_prices(
    price_ticker,
    start=price_start,
)

if prices.empty:
    st.error(
        "Keine Preisreihe verfügbar."
    )
    st.stop()

template = seasonal_template(
    prices,
    years=20,
)

phase_day = current_phase_day(
    prices
)

turn = nearest_turn_context(
    template,
    phase_day,
)

stability = stability_table(
    prices
)

seasonal = seasonal_edge_context(
    stability,
    turn,
)

report_type = (
    primary_report_for_asset_class(
        asset_class
    )
)

flow_error = None

group_flow_map = {
    "available": False,
    "report_type": report_type,
    "groups": {},
    "group_order": [],
}

enriched = pd.DataFrame()

try:
    universe = load_report_universe(
        report_type
    )
    resolved = resolve_report_market(
        market,
        universe,
    )

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
            enriched = (
                enrich_report_positioning(
                    raw,
                    report_type=report_type,
                    index_weeks=26,
                    validation_weeks=156,
                )
            )

            group_flow_map = (
                build_group_flow_map(
                    enriched,
                    report_type,
                )
            )

except Exception as exc:
    flow_error = (
        f"{type(exc).__name__}: "
        f"{exc}"
    )

groups = simple_turn_group_selection(
    group_flow_map
)

final_read = (
    simple_cot_seasonality_turn_read(
        seasonal,
        groups,
    )
)

context_strip(
    [
        ("Markt", market_name),
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
            "Letzter Preis",
            str(
                pd.Timestamp(
                    prices.index.max()
                ).date()
            ),
        ),
    ]
)

# ------------------------------------------------------------------
# 1 · SEASONAL TURN
# ------------------------------------------------------------------
section_line(
    "1 · Seasonal Turn",
    "Kommt ein Top/Bottom und ist die anschließende 40T/60T-Struktur robust?",
)

season_read = final_read[
    "seasonality"
]

turn_direction = int(
    season_read.get(
        "turn_direction",
        0,
    ) or 0
)

turn_tone = (
    "bearish"
    if turn_direction < 0
    else "bullish"
    if turn_direction > 0
    else "neutral"
)

distance = season_read.get(
    "distance_days"
)

if distance is None:
    distance_text = "—"
elif int(distance) == 0:
    distance_text = "HEUTE"
else:
    distance_text = (
        f"{int(distance):+d}T"
    )

h40 = dict(
    season_read.get(
        "h40"
    ) or {}
)
h60 = dict(
    season_read.get(
        "h60"
    ) or {}
)

s1, s2, s3 = st.columns(3)

with s1:
    _status_card(
        "Seasonal Turn",
        str(
            season_read.get(
                "turn_type",
                "N/V",
            )
        ),
        f"Distanz {distance_text}",
        tone=turn_tone,
        emphasis=True,
    )

with s2:
    _status_card(
        "40T Forward",
        str(
            h40.get(
                "label",
                "N/V",
            )
        ),
        (
            f"Median Edge "
            f"{_pct(h40.get('median_edge'))}"
        ),
        tone=_tone_for_direction(
            h40.get(
                "direction",
                0,
            )
        ),
    )

with s3:
    _status_card(
        "60T Forward",
        str(
            h60.get(
                "label",
                "N/V",
            )
        ),
        (
            f"Median Edge "
            f"{_pct(h60.get('median_edge'))}"
        ),
        tone=_tone_for_direction(
            h60.get(
                "direction",
                0,
            )
        ),
    )

season_quality = str(
    season_read.get(
        "quality",
        "MIXED",
    )
)

if (
    turn_direction < 0
    and season_quality == "ROBUST"
):
    _banner(
        "SEASONAL TOP · ROBUST BEARISH",
        (
            f"Top in {distance_text} · "
            "40T und 60T bestätigen die bearishe Forward-Struktur."
        ),
        tone="bearish",
    )

elif (
    turn_direction > 0
    and season_quality == "ROBUST"
):
    _banner(
        "SEASONAL BOTTOM · ROBUST BULLISH",
        (
            f"Bottom in {distance_text} · "
            "40T und 60T bestätigen die bullishe Forward-Struktur."
        ),
        tone="bullish",
    )

elif season_quality == "CONFLICT":
    _banner(
        "SEASONAL TURN · KONFLIKT",
        (
            "Kalender-Turn und 40T/60T-Forward-Struktur "
            "zeigen nicht dieselbe Richtung."
        ),
        tone="warning",
    )

else:
    _banner(
        (
            f"SEASONAL "
            f"{season_read.get('turn_type', 'TURN')} · "
            f"{season_quality}"
        ),
        (
            "Der Turn ist vorhanden, aber die "
            "40T/60T-Robustheit ist noch nicht vollständig."
        ),
        tone="warning",
    )

# ------------------------------------------------------------------
# 2 · THREE GROUPS
# ------------------------------------------------------------------
section_line(
    "2 · Wer unterstützt den Turn?",
    "4W Struktur → 2W Veränderung → 1W aktuell",
)

commercial = groups[
    "commercial"
]
momentum = groups[
    "momentum"
]
nonrep = groups[
    "nonreportable"
]

if report_type == "tff":
    commercial_subtitle = (
        "Dealer / Intermediary · FX/TFF-Kontext · "
        "nicht identisch mit Producer/Merchant"
    )
    momentum_subtitle = (
        "Leveraged Funds · kurzfristiger Momentum-/Trend-Flow"
    )
else:
    commercial_subtitle = (
        "Producer / Merchant · Commercial/Hedger-Flow"
    )
    momentum_subtitle = (
        "Managed Money · spekulativer Momentum-/Trend-Flow"
    )

nonrep_subtitle = (
    "Residualer Kontra-Kontext · "
    "nicht als echtes Retail interpretiert"
)

g1, g2, g3 = st.columns(3)

with g1:
    _group_card(
        "Commercial-Seite",
        commercial_subtitle,
        commercial,
        final_read[
            "commercial"
        ],
        turn_direction,
    )

with g2:
    _group_card(
        "Momentum-Funds",
        momentum_subtitle,
        momentum,
        final_read[
            "momentum"
        ],
        turn_direction,
        momentum=True,
    )

with g3:
    _group_card(
        "Nonreportables (konträr)",
        nonrep_subtitle,
        nonrep,
        final_read[
            "nonreportable"
        ],
        turn_direction,
    )

st.caption(
    "Momentum-Funds sind für das kurzfristige Turn-Timing besonders wichtig. "
    "Commercials liefern Smart-Money-/Hedging-Kontext. "
    "Nonreportables werden ausschließlich konträr als Zusatzkontext gelesen."
)

# ------------------------------------------------------------------
# 3 · FINAL READ
# ------------------------------------------------------------------
section_line(
    "3 · Finaler Research Read",
    "Ist das erwartete Top/Bottom durch Positionierung bestätigt?",
)

localized = _localized_final_read(
    final_read
)

_banner(
    (
        f"{localized['headline']} · "
        f"{localized['quality_text']}"
    ),
    (
        "Seasonality + Commercial-Seite + Momentum-Funds "
        "+ Nonreportables werden regelbasiert zusammengeführt."
    ),
    tone=localized[
        "tone"
    ],
)

supporters = list(
    final_read.get(
        "supporters",
        [],
    )
)

opponents = list(
    final_read.get(
        "opponents",
        [],
    )
)

v1, v2 = st.columns(2)

with v1:
    _status_card(
        "Unterstützt den Turn",
        (
            " · ".join(
                supporters
            )
            if supporters
            else "niemand klar"
        ),
        "Seasonality wird separat oben bewertet.",
        tone=turn_tone,
    )

with v2:
    opposite_tone = (
        "bullish"
        if turn_tone == "bearish"
        else "bearish"
        if turn_tone == "bullish"
        else "neutral"
    )
    _status_card(
        "Widerspricht dem Turn",
        (
            " · ".join(
                opponents
            )
            if opponents
            else "kein klarer Widerspruch"
        ),
        "Gemischt zählt weder als Support noch als Widerspruch.",
        tone=(
            opposite_tone
            if opponents
            else "neutral"
        ),
    )

missing = []

if (
    "Commercial-Seite"
    not in supporters
):
    missing.append(
        "Commercial-Seite"
    )

if (
    "Momentum-Funds"
    not in supporters
):
    missing.append(
        "Momentum-Funds"
    )

if missing:
    st.info(
        "**Für eine stärkere Turn-Bestätigung fehlt aktuell:** "
        + " · ".join(missing)
    )
else:
    st.success(
        "**Commercial-Seite und Momentum-Funds bestätigen den Turn gemeinsam.**"
    )

definition(
    "Der finale Zustand entsteht regelbasiert, nicht über einen Punktescore. "
    "Die jüngeren 2W/1W-Flows werden für das Turn-Timing stärker beachtet als "
    "die ältere 4W-Struktur. Asset Manager bleiben außerhalb des finalen Turn-Reads."
)

# ------------------------------------------------------------------
# DETAILS
# ------------------------------------------------------------------
with st.expander(
    "Details · Long / Short / Net Deltas",
    expanded=False,
):
    detail_rows = []

    for label, summary in (
        (
            "Commercial-Seite",
            commercial,
        ),
        (
            "Momentum-Funds",
            momentum,
        ),
        (
            "Nonreportables",
            nonrep,
        ),
    ):
        if not summary.get(
            "available"
        ):
            continue

        for window_name, key in (
            ("4W", "w4"),
            ("2W", "w2"),
            ("1W", "w1"),
        ):
            window = dict(
                summary.get(
                    key
                ) or {}
            )

            detail_rows.append(
                {
                    "Gruppe": label,
                    "Fenster": window_name,
                    "Long Δ": window.get(
                        "long_delta",
                        np.nan,
                    ),
                    "Short Δ": window.get(
                        "short_delta",
                        np.nan,
                    ),
                    "Net Δ": window.get(
                        "net_delta",
                        np.nan,
                    ),
                    "Net/OI Δ": window.get(
                        "net_oi_delta",
                        np.nan,
                    ),
                    "Mechanik": window.get(
                        "mechanics",
                        "",
                    ),
                }
            )

    if detail_rows:
        detail = pd.DataFrame(
            detail_rows
        )

        st.dataframe(
            detail.style.format(
                {
                    "Long Δ": "{:+,.0f}",
                    "Short Δ": "{:+,.0f}",
                    "Net Δ": "{:+,.0f}",
                    "Net/OI Δ": "{:+.3%}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

    if (
        report_type == "tff"
        and groups.get(
            "asset_manager",
            {},
        ).get(
            "available"
        )
    ):
        st.markdown(
            "#### Asset Manager · langfristiger Kontext"
        )

        am = groups[
            "asset_manager"
        ]

        am_rows = []

        for window_name, key in (
            ("4W", "w4"),
            ("2W", "w2"),
            ("1W", "w1"),
        ):
            window = dict(
                am.get(
                    key
                ) or {}
            )

            am_rows.append(
                {
                    "Fenster": window_name,
                    "Flow": _flow_label(
                        window
                    ),
                    "Net Δ": window.get(
                        "net_delta",
                        np.nan,
                    ),
                    "Mechanik": window.get(
                        "mechanics",
                        "",
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(
                am_rows
            ).style.format(
                {
                    "Net Δ": "{:+,.0f}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "Asset Manager bleiben bewusst außerhalb des finalen Turn-Reads: "
            "sie dienen nur als langsamerer institutioneller Regime-Kontext."
        )

with st.expander(
    "Details · Seasonality Robustness",
    expanded=False,
):
    season_detail = stability[
        stability[
            "horizon_days"
        ].isin(
            [40, 60]
        )
    ].copy()

    if not season_detail.empty:
        show = season_detail[
            [
                "history_years",
                "horizon_days",
                "sample_size",
                "direction",
                "positive_rate",
                "hit_rate_edge_pp",
                "median_return",
                "median_edge",
            ]
        ].rename(
            columns={
                "history_years": "Historie",
                "horizon_days": "Forward",
                "sample_size": "N",
                "direction": "Richtung",
                "positive_rate": "Positiv",
                "hit_rate_edge_pp": "Δ Trefferquote",
                "median_return": "Median",
                "median_edge": "Median Edge",
            }
        )

        st.dataframe(
            show.style.format(
                {
                    "Historie": "{:.0f}J",
                    "Forward": "{:.0f}T",
                    "Positiv": "{:.0%}",
                    "Δ Trefferquote": "{:+.1f} Pp.",
                    "Median": "{:+.2%}",
                    "Median Edge": "{:+.2%}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

if flow_error:
    st.caption(
        f"COT-Datenhinweis: {flow_error}"
    )
