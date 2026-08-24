from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st


# V3.30.2 · FULL HEDGE FUND UI MIGRATION

TOKENS = {
    "bg": "#081018",
    "surface": "#0D1722",
    "surface_raised": "#111D29",
    "surface_hover": "#142230",
    "border": "#22303D",
    "border_soft": "#1A2632",
    "text": "#F3F6FB",
    "text_soft": "#C8D1DC",
    "muted": "#95A3B3",
    "blue": "#62A6C9",
    "blue_soft": "#79B8FF",
    "green": "#65D98B",
    "red": "#FF7373",
    "amber": "#F2B84B",
    "purple": "#B59BFF",
}


def _configure_plotly() -> None:
    try:
        import plotly.graph_objects as go
        import plotly.io as pio
    except Exception:
        return

    if "quant_hf_dark" not in pio.templates:
        pio.templates["quant_hf_dark"] = go.layout.Template(
            layout=go.Layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(
                    color=TOKENS["text_soft"],
                    family=(
                        "Inter, ui-sans-serif, system-ui, -apple-system, "
                        "BlinkMacSystemFont, Segoe UI, sans-serif"
                    ),
                    size=12,
                ),
                colorway=[
                    TOKENS["blue"],
                    TOKENS["green"],
                    TOKENS["red"],
                    TOKENS["amber"],
                    TOKENS["purple"],
                    TOKENS["blue_soft"],
                ],
                xaxis=dict(
                    gridcolor=TOKENS["border_soft"],
                    zerolinecolor=TOKENS["border"],
                    linecolor=TOKENS["border"],
                    tickfont=dict(color=TOKENS["muted"]),
                    title_font=dict(color=TOKENS["muted"]),
                ),
                yaxis=dict(
                    gridcolor=TOKENS["border_soft"],
                    zerolinecolor=TOKENS["border"],
                    linecolor=TOKENS["border"],
                    tickfont=dict(color=TOKENS["muted"]),
                    title_font=dict(color=TOKENS["muted"]),
                ),
                legend=dict(
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(color=TOKENS["muted"]),
                ),
                hoverlabel=dict(
                    bgcolor=TOKENS["surface_raised"],
                    bordercolor=TOKENS["border"],
                    font=dict(color=TOKENS["text"]),
                ),
            )
        )

    pio.templates.default = "quant_hf_dark"


def apply_hedgefund_theme() -> None:
    _configure_plotly()

    st.markdown(
        f"""
        <style>
        :root {{
            --hf-bg: {TOKENS["bg"]};
            --hf-surface: {TOKENS["surface"]};
            --hf-surface-raised: {TOKENS["surface_raised"]};
            --hf-surface-hover: {TOKENS["surface_hover"]};
            --hf-border: {TOKENS["border"]};
            --hf-border-soft: {TOKENS["border_soft"]};
            --hf-text: {TOKENS["text"]};
            --hf-text-soft: {TOKENS["text_soft"]};
            --hf-muted: {TOKENS["muted"]};
            --hf-blue: {TOKENS["blue"]};
            --hf-blue-soft: {TOKENS["blue_soft"]};
            --hf-green: {TOKENS["green"]};
            --hf-red: {TOKENS["red"]};
            --hf-amber: {TOKENS["amber"]};
            --hf-purple: {TOKENS["purple"]};
        }}

        /* APP SHELL */
        html, body, .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"],
        [data-testid="stSidebar"],
        [data-testid="stSidebarContent"] {{
            background: var(--hf-bg) !important;
            background-color: var(--hf-bg) !important;
            color: var(--hf-text) !important;
        }}

        [data-testid="stAppViewContainer"] {{
            background-image:
                radial-gradient(circle at 28% -10%, rgba(98,166,201,.07), transparent 35%),
                radial-gradient(circle at 92% 15%, rgba(121,184,255,.025), transparent 25%) !important;
        }}

        [data-testid="stMainBlockContainer"] {{
            max-width: 1540px !important;
            padding: 1.35rem 2rem 2.4rem 2rem !important;
        }}

        /* TYPOGRAPHY */
        h1, h2, h3, h4, h5, h6 {{
            color: var(--hf-text) !important;
            letter-spacing: -.018em !important;
        }}

        h1 {{ font-weight: 780 !important; }}
        h2, h3 {{ font-weight: 720 !important; }}
        p, li {{ color: var(--hf-text-soft) !important; }}
        label {{
            color: var(--hf-text-soft) !important;
            font-weight: 650 !important;
        }}

        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] *,
        small {{
            color: var(--hf-muted) !important;
        }}

        /* SIDEBAR */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #07101A 0%, #09131D 48%, #081018 100%) !important;
            border-right: 1px solid #1A2936 !important;
        }}

        [data-testid="stSidebar"] [data-testid="stPageLink"] a,
        [data-testid="stSidebar"] [data-testid="stButton"] button {{
            min-height: 42px !important;
            padding: .48rem .72rem !important;
            background: transparent !important;
            color: var(--hf-text-soft) !important;
            border: 1px solid transparent !important;
            border-radius: 8px !important;
            box-shadow: none !important;
        }}

        [data-testid="stSidebar"] [data-testid="stPageLink"] a *,
        [data-testid="stSidebar"] [data-testid="stButton"] button * {{
            color: inherit !important;
            -webkit-text-fill-color: currentColor !important;
        }}

        [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,
        [data-testid="stSidebar"] [data-testid="stButton"] button:hover {{
            background: #0D1924 !important;
            border-color: #223849 !important;
            color: var(--hf-text) !important;
        }}

        [data-testid="stSidebar"] [aria-current="page"],
        [data-testid="stSidebar"] a[aria-current="page"] {{
            background: linear-gradient(90deg, rgba(98,166,201,.17), rgba(98,166,201,.04)) !important;
            border-color: rgba(98,166,201,.32) !important;
            box-shadow: inset 3px 0 0 var(--hf-blue) !important;
            color: var(--hf-text) !important;
        }}

        [class*="brand"] strong,
        [class*="brand-title"],
        [class*="brand_title"],
        [class*="logo-title"],
        [class*="logo_title"],
        [class*="app-title"],
        [class*="app_title"] {{
            color: var(--hf-text) !important;
            -webkit-text-fill-color: var(--hf-text) !important;
        }}

        /* TABS */
        [data-baseweb="tab-list"] {{
            min-height: 42px !important;
            gap: 1.25rem !important;
            border-bottom: 1px solid var(--hf-border) !important;
        }}

        [data-baseweb="tab"] {{
            color: var(--hf-muted) !important;
            font-size: .82rem !important;
            font-weight: 680 !important;
            padding: .55rem 0 .65rem !important;
        }}

        [data-baseweb="tab"][aria-selected="true"] {{
            color: var(--hf-text) !important;
        }}

        [data-baseweb="tab-highlight"] {{
            background: var(--hf-blue) !important;
        }}

        /* INPUTS / DROPDOWNS */
        [data-testid="stTextInput"] div[data-baseweb="input"],
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] div[data-baseweb="input"],
        [data-testid="stNumberInput"] input,
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
        [data-testid="stDateInput"] div[data-baseweb="input"] {{
            min-height: 40px !important;
            background: var(--hf-surface) !important;
            background-color: var(--hf-surface) !important;
            color: var(--hf-text) !important;
            border-color: var(--hf-border) !important;
            border-radius: 8px !important;
            box-shadow: none !important;
            -webkit-text-fill-color: var(--hf-text) !important;
        }}

        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stSelectbox"] div[data-baseweb="select"] *,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] * {{
            color: var(--hf-text) !important;
            -webkit-text-fill-color: var(--hf-text) !important;
        }}

        [data-testid="stTextInput"] input::placeholder,
        [data-testid="stNumberInput"] input::placeholder {{
            color: var(--hf-muted) !important;
            -webkit-text-fill-color: var(--hf-muted) !important;
            opacity: 1 !important;
        }}

        div[data-baseweb="popover"],
        div[data-baseweb="menu"],
        ul[role="listbox"],
        [role="option"] {{
            background: var(--hf-surface-raised) !important;
            background-color: var(--hf-surface-raised) !important;
            color: var(--hf-text) !important;
        }}

        div[data-baseweb="popover"] *,
        div[data-baseweb="menu"] *,
        [role="option"] * {{
            color: var(--hf-text) !important;
            -webkit-text-fill-color: var(--hf-text) !important;
        }}

        [role="option"]:hover,
        [role="option"][aria-selected="true"] {{
            background: rgba(98,166,201,.12) !important;
        }}

        [data-testid="stMultiSelect"] [data-baseweb="tag"] {{
            background: #142230 !important;
            border-color: #294054 !important;
            color: var(--hf-text) !important;
        }}

        /* BUTTONS */
        [data-testid="stBaseButton-secondary"],
        [data-testid="stPageLink"] a {{
            min-height: 38px !important;
            background: var(--hf-surface) !important;
            color: var(--hf-text) !important;
            border: 1px solid var(--hf-border) !important;
            border-radius: 8px !important;
            box-shadow: none !important;
            font-weight: 680 !important;
        }}

        [data-testid="stBaseButton-secondary"] *,
        [data-testid="stPageLink"] a * {{
            color: var(--hf-text) !important;
            -webkit-text-fill-color: var(--hf-text) !important;
        }}

        [data-testid="stBaseButton-secondary"]:hover,
        [data-testid="stPageLink"] a:hover {{
            background: var(--hf-surface-hover) !important;
            border-color: rgba(98,166,201,.52) !important;
        }}

        [data-testid="stBaseButton-primary"] {{
            min-height: 38px !important;
            background: var(--hf-blue) !important;
            color: #061019 !important;
            border-color: var(--hf-blue) !important;
            border-radius: 8px !important;
            box-shadow: 0 7px 22px rgba(98,166,201,.13) !important;
            font-weight: 760 !important;
        }}

        [data-testid="stBaseButton-primary"] * {{
            color: #061019 !important;
            -webkit-text-fill-color: #061019 !important;
        }}

        /* CONTAINERS / CARDS */
        [data-testid="stVerticalBlockBorderWrapper"] > div,
        [data-testid="stForm"],
        [data-testid="stExpander"] {{
            background: linear-gradient(180deg, rgba(17,29,41,.87), rgba(13,23,34,.87)) !important;
            border: 1px solid var(--hf-border) !important;
            border-radius: 10px !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.018) !important;
        }}

        [data-testid="stMetric"] {{
            background: linear-gradient(180deg, rgba(17,29,41,.98), rgba(13,23,34,.98)) !important;
            border: 1px solid var(--hf-border) !important;
            border-radius: 10px !important;
            padding: .9rem 1rem !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.02), 0 11px 25px rgba(0,0,0,.12) !important;
        }}

        [data-testid="stMetric"] * {{
            color: var(--hf-text) !important;
            -webkit-text-fill-color: currentColor !important;
        }}

        .metric-card, .kpi-card, .dashboard-card, .stat-card, .summary-card,
        .user-card, .admin-card, .sidebar-card, .trader-card, .research-card,
        .state-card, .signal-card {{
            background: linear-gradient(180deg, rgba(17,29,41,.98), rgba(13,23,34,.98)) !important;
            border: 1px solid var(--hf-border) !important;
            border-radius: 10px !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.02), 0 11px 25px rgba(0,0,0,.12) !important;
            color: var(--hf-text) !important;
        }}

        /* TABLES */
        [data-testid="stDataFrame"] {{
            background: var(--hf-bg) !important;
            border: 1px solid var(--hf-border) !important;
            border-radius: 8px !important;
            overflow: hidden !important;
            --gdg-bg-cell: var(--hf-bg);
            --gdg-bg-cell-medium: var(--hf-surface);
            --gdg-bg-header: var(--hf-surface);
            --gdg-bg-header-hovered: var(--hf-surface-raised);
            --gdg-bg-header-has-focus: var(--hf-surface-raised);
            --gdg-text-dark: var(--hf-text);
            --gdg-text-medium: var(--hf-text-soft);
            --gdg-text-light: var(--hf-muted);
            --gdg-border-color: var(--hf-border);
            --gdg-horizontal-border-color: var(--hf-border-soft);
            --gdg-accent-color: var(--hf-blue);
            --gdg-accent-light: rgba(98,166,201,.12);
        }}

        [data-testid="stTable"] {{
            background: var(--hf-bg) !important;
            border: 1px solid var(--hf-border) !important;
            border-radius: 8px !important;
            overflow: hidden !important;
        }}

        [data-testid="stTable"] table {{
            background: var(--hf-bg) !important;
            border-collapse: collapse !important;
        }}

        [data-testid="stTable"] thead th {{
            background: var(--hf-surface) !important;
            color: var(--hf-muted) !important;
            border-color: var(--hf-border) !important;
            font-size: .72rem !important;
            text-transform: uppercase !important;
            letter-spacing: .05em !important;
        }}

        [data-testid="stTable"] tbody td {{
            background: var(--hf-bg) !important;
            color: var(--hf-text) !important;
            border-color: var(--hf-border-soft) !important;
        }}

        /* LEGACY WATCHLIST */
        .sw-wrap {{ color: var(--hf-text) !important; }}

        .sw-title, .sw-card-value, .sw-market-name, .sw-bias, .sw-plan {{
            color: var(--hf-text) !important;
            -webkit-text-fill-color: var(--hf-text) !important;
        }}

        .sw-kicker, .sw-card-label {{
            color: var(--hf-blue) !important;
            -webkit-text-fill-color: var(--hf-blue) !important;
        }}

        .sw-subtitle, .sw-legend-item, .sw-market-code {{
            color: var(--hf-muted) !important;
            -webkit-text-fill-color: var(--hf-muted) !important;
        }}

        .sw-card, .sw-legend, .sw-table {{
            background: linear-gradient(180deg, rgba(17,29,41,.97), rgba(13,23,34,.97)) !important;
            border: 1px solid var(--hf-border) !important;
            border-radius: 10px !important;
            box-shadow: none !important;
        }}

        .sw-header {{
            background: #0C1620 !important;
            color: var(--hf-muted) !important;
            border-bottom-color: var(--hf-border) !important;
        }}

        .sw-row, .sw-market, .sw-market > div {{
            background: var(--hf-bg) !important;
        }}

        .sw-row {{
            border-top-color: var(--hf-border-soft) !important;
        }}

        .sw-row:hover {{
            background: #0C1620 !important;
        }}

        .sw-market {{
            border-color: var(--hf-border) !important;
        }}

        .sw-chip, .sw-signal, .sw-plan,
        .sw-plan .sw-chip, .sw-row .sw-chip, .sw-row .sw-signal {{
            background: transparent !important;
            border: 0 !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            padding: 0 !important;
            min-height: 0 !important;
        }}

        .sw-chip *, .sw-signal *, .sw-plan * {{
            background: transparent !important;
        }}

        .sw-chip.macro-bull, .sw-chip.macro-bull *,
        .sw-chip.micro-bull, .sw-chip.micro-bull * {{
            color: var(--hf-green) !important;
            -webkit-text-fill-color: var(--hf-green) !important;
        }}

        .sw-chip.macro-bear, .sw-chip.macro-bear *,
        .sw-chip.micro-bear, .sw-chip.micro-bear * {{
            color: var(--hf-red) !important;
            -webkit-text-fill-color: var(--hf-red) !important;
        }}

        .sw-chip.macro-neutral, .sw-chip.macro-neutral *,
        .sw-chip.micro-neutral, .sw-chip.micro-neutral * {{
            color: var(--hf-text-soft) !important;
            -webkit-text-fill-color: var(--hf-text-soft) !important;
        }}

        .sw-signal.signal-aligned, .sw-signal.signal-aligned * {{
            color: var(--hf-green) !important;
            -webkit-text-fill-color: var(--hf-green) !important;
        }}

        .sw-signal.signal-watch, .sw-signal.signal-watch * {{
            color: var(--hf-amber) !important;
            -webkit-text-fill-color: var(--hf-amber) !important;
        }}

        .sw-signal.signal-neutral, .sw-signal.signal-neutral * {{
            color: var(--hf-text-soft) !important;
            -webkit-text-fill-color: var(--hf-text-soft) !important;
        }}

        .sw-signal.signal-ready, .sw-signal.signal-ready * {{
            color: var(--hf-purple) !important;
            -webkit-text-fill-color: var(--hf-purple) !important;
        }}

        .sw-bias, .sw-bias * {{
            color: var(--hf-text) !important;
            -webkit-text-fill-color: var(--hf-text) !important;
            opacity: 1 !important;
            font-weight: 720 !important;
        }}

        /* LOGIN */
        [data-testid="stTextInput"] label,
        [data-testid="stForm"] label {{
            color: var(--hf-text) !important;
            -webkit-text-fill-color: var(--hf-text) !important;
            opacity: 1 !important;
        }}

        /* NEUTRALIZE WHITE LEGACY SURFACES */
        [data-testid="stAppViewContainer"] [style*="background: white"],
        [data-testid="stAppViewContainer"] [style*="background:white"],
        [data-testid="stAppViewContainer"] [style*="background-color: white"],
        [data-testid="stAppViewContainer"] [style*="background-color:white"],
        [data-testid="stAppViewContainer"] [style*="background: #fff"],
        [data-testid="stAppViewContainer"] [style*="background:#fff"],
        [data-testid="stAppViewContainer"] [style*="background: #ffffff"],
        [data-testid="stAppViewContainer"] [style*="background:#ffffff"],
        [data-testid="stAppViewContainer"] [style*="background: #FFFFFF"],
        [data-testid="stAppViewContainer"] [style*="background:#FFFFFF"],
        [data-testid="stSidebar"] [style*="background: white"],
        [data-testid="stSidebar"] [style*="background:white"],
        [data-testid="stSidebar"] [style*="background: #fff"],
        [data-testid="stSidebar"] [style*="background:#fff"] {{
            background: linear-gradient(180deg, rgba(17,29,41,.98), rgba(13,23,34,.98)) !important;
            border-color: var(--hf-border) !important;
            color: var(--hf-text) !important;
            box-shadow: none !important;
        }}

        [data-testid="stAppViewContainer"] [style*="background: white"] *,
        [data-testid="stAppViewContainer"] [style*="background:white"] *,
        [data-testid="stAppViewContainer"] [style*="background-color: white"] *,
        [data-testid="stAppViewContainer"] [style*="background-color:white"] *,
        [data-testid="stAppViewContainer"] [style*="background: #fff"] *,
        [data-testid="stAppViewContainer"] [style*="background:#fff"] *,
        [data-testid="stAppViewContainer"] [style*="background: #ffffff"] *,
        [data-testid="stAppViewContainer"] [style*="background:#ffffff"] *,
        [data-testid="stAppViewContainer"] [style*="background: #FFFFFF"] *,
        [data-testid="stAppViewContainer"] [style*="background:#FFFFFF"] * {{
            color: var(--hf-text) !important;
            -webkit-text-fill-color: var(--hf-text) !important;
        }}

        /* V3.30 RESEARCH COMPONENTS */
        .hf-page-head {{
            position: relative;
            padding: .35rem 0 1rem 0;
            margin: 0 0 1.1rem 0;
            border-bottom: 1px solid var(--hf-border-soft);
        }}

        .hf-page-head::after {{
            content: "";
            position: absolute;
            left: 0;
            bottom: -1px;
            width: 78px;
            height: 1px;
            background: linear-gradient(90deg, var(--hf-blue), transparent);
        }}

        .hf-kicker {{
            color: var(--hf-blue) !important;
            font-size: .70rem;
            font-weight: 820;
            letter-spacing: .16em;
            text-transform: uppercase;
            margin-bottom: .45rem;
        }}

        .hf-title {{
            color: var(--hf-text) !important;
            font-size: clamp(1.8rem, 2.4vw, 2.55rem);
            font-weight: 790;
            letter-spacing: -.034em;
            line-height: 1.04;
        }}

        .hf-subtitle {{
            color: var(--hf-muted) !important;
            max-width: 940px;
            margin-top: .55rem;
            font-size: .94rem;
            line-height: 1.52;
        }}

        .hf-card {{
            position: relative;
            min-height: 108px;
            padding: .92rem 1rem;
            background:
                radial-gradient(circle at 100% 0%, rgba(98,166,201,.055), transparent 38%),
                linear-gradient(180deg, rgba(17,29,41,.98), rgba(13,23,34,.98));
            border: 1px solid var(--hf-border);
            border-radius: 10px;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.022), 0 12px 27px rgba(0,0,0,.13);
            overflow: hidden;
        }}

        .hf-card::before {{
            content: "";
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: var(--hf-accent, var(--hf-blue));
            opacity: .82;
        }}

        .hf-card-label {{
            color: var(--hf-muted);
            font-size: .66rem;
            font-weight: 820;
            letter-spacing: .11em;
            text-transform: uppercase;
        }}

        .hf-card-value {{
            color: var(--hf-accent, var(--hf-text));
            font-size: 1.13rem;
            line-height: 1.18;
            font-weight: 780;
            margin-top: .48rem;
        }}

        .hf-card-note {{
            color: var(--hf-muted);
            font-size: .74rem;
            line-height: 1.38;
            margin-top: .46rem;
        }}

        .hf-summary {{
            display: flex;
            gap: .68rem;
            align-items: flex-start;
            padding: .8rem .95rem;
            margin: .72rem 0 1rem 0;
            background: linear-gradient(90deg, rgba(98,166,201,.07), rgba(13,23,34,.88) 30%);
            border: 1px solid var(--hf-border);
            border-radius: 9px;
            color: var(--hf-text-soft);
            font-size: .87rem;
            line-height: 1.5;
        }}

        .hf-summary::before {{
            content: "◈";
            color: var(--hf-blue);
            flex: 0 0 auto;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(
    kicker: str,
    title: str,
    subtitle: str = "",
) -> None:
    st.markdown(
        (
            '<div class="hf-page-head">'
            f'<div class="hf-kicker">{escape(str(kicker))}</div>'
            f'<div class="hf-title">{escape(str(title))}</div>'
            f'<div class="hf-subtitle">{escape(str(subtitle or ""))}</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def render_card(
    label: str,
    value: Any,
    note: str = "",
    *,
    tone: str | None = None,
) -> None:
    probe = (
        str(tone or "")
        + " "
        + str(value or "")
    ).upper()

    if any(token in probe for token in (
        "POSITIVE", "BULL", "LONG", "BESTÄTIG", "CONFIRM", "FAVOR"
    )):
        accent = TOKENS["green"]
    elif any(token in probe for token in (
        "NEGATIVE", "BEAR", "SHORT", "WIDERSPRICHT", "CONFLICT"
    )):
        accent = TOKENS["red"]
    elif any(token in probe for token in (
        "WARNING", "WATCH"
    )):
        accent = TOKENS["amber"]
    elif any(token in probe for token in (
        "TRANSITION", "EARLY"
    )):
        accent = TOKENS["blue_soft"]
    elif "PURPLE" in probe:
        accent = TOKENS["purple"]
    else:
        accent = TOKENS["blue"]

    display = "—" if value in (None, "") else str(value)

    st.markdown(
        (
            f'<div class="hf-card" style="--hf-accent:{accent}">'
            f'<div class="hf-card-label">{escape(str(label))}</div>'
            f'<div class="hf-card-value">{escape(display)}</div>'
            f'<div class="hf-card-note">{escape(str(note or ""))}</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def render_summary(text: str) -> None:
    st.markdown(
        (
            '<div class="hf-summary">'
            f'{escape(str(text or ""))}'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

# V3.30.2.1 · UI API COMPATIBILITY REPAIR
def render_section_header(
    title: str,
    subtitle: str = "",
) -> None:
    subtitle_html = (
        f'<div class="hf-subtitle" style="margin-top:.18rem;font-size:.80rem">'
        f'{escape(str(subtitle))}</div>'
        if subtitle
        else ""
    )

    st.markdown(
        (
            '<div style="margin:.35rem 0 .75rem 0">'
            '<div class="hf-kicker" style="margin-bottom:.30rem">'
            f'{escape(str(title))}'
            '</div>'
            f'{subtitle_html}'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def render_metric_grid(
    metrics,
) -> None:
    items = list(metrics or [])

    if not items:
        return

    columns = st.columns(
        min(
            len(items),
            4,
        )
    )

    for index, metric in enumerate(items):
        column = columns[
            index % len(columns)
        ]

        with column:
            label = getattr(
                metric,
                "label",
                "",
            )
            value = getattr(
                metric,
                "value",
                "",
            )
            meta = getattr(
                metric,
                "meta",
                "",
            )
            tone = getattr(
                metric,
                "tone",
                None,
            )

            render_card(
                str(label),
                value,
                str(meta or ""),
                tone=tone,
            )


def render_status_chip(
    text: str,
    *,
    tone: str = "neutral",
) -> None:
    probe = (
        str(tone or "")
        + " "
        + str(text or "")
    ).upper()

    if any(token in probe for token in (
        "POSITIVE", "BULL", "LONG", "BESTÄTIG", "CONFIRM", "FAVOR"
    )):
        color = TOKENS["green"]
    elif any(token in probe for token in (
        "NEGATIVE", "BEAR", "SHORT", "WIDERSPRICHT", "CONFLICT"
    )):
        color = TOKENS["red"]
    elif any(token in probe for token in (
        "WARNING", "WATCH"
    )):
        color = TOKENS["amber"]
    elif any(token in probe for token in (
        "TRANSITION", "EARLY"
    )):
        color = TOKENS["blue_soft"]
    elif "PURPLE" in probe:
        color = TOKENS["purple"]
    else:
        color = TOKENS["text_soft"]

    st.markdown(
        (
            '<span style="'
            'display:inline-flex;align-items:center;'
            'min-height:24px;padding:.10rem .42rem;'
            'border-radius:5px;'
            f'color:{color};'
            f'background:{color}14;'
            f'border:1px solid {color}33;'
            'font-size:.71rem;font-weight:780;'
            'letter-spacing:.02em'
            '">'
            f'{escape(str(text))}'
            '</span>'
        ),
        unsafe_allow_html=True,
    )


def render_callout(
    text: str,
) -> None:
    render_summary(
        str(text or "")
    )


def render_divider() -> None:
    st.markdown(
        (
            '<div style="'
            'height:1px;'
            'background:#1A2632;'
            'margin:.85rem 0'
            '"></div>'
        ),
        unsafe_allow_html=True,
    )
