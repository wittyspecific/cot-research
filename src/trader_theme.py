from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st


def apply_trader_dark_theme() -> None:
    """Shared V3.29 trader-first dark UI layer; no model logic."""
    st.markdown(
        """
        <style>
        :root {
          --qa-bg:#0b0f14; --qa-soft:#10161e; --qa-panel:#131b24;
          --qa-panel2:#18222d; --qa-border:rgba(151,166,186,.16);
          --qa-border2:rgba(151,166,186,.26); --qa-text:#edf2f7;
          --qa-muted:#8f9baa; --qa-green:#56b78b; --qa-red:#d36d72;
          --qa-amber:#d5a24f; --qa-blue:#62a6c9;
        }
        html,body,[data-testid="stAppViewContainer"],.stApp{background:var(--qa-bg)!important;color:var(--qa-text)!important}
        [data-testid="stHeader"]{background:rgba(11,15,20,.9)!important;border-bottom:1px solid var(--qa-border)!important}
        [data-testid="stSidebar"]{background:#0d1218!important;border-right:1px solid var(--qa-border)!important}
        [data-testid="stMainBlockContainer"]{max-width:1500px;padding-top:1.5rem;padding-bottom:4rem}
        h1,h2,h3,h4,h5{color:var(--qa-text)!important;letter-spacing:-.015em}
        p,label,.stCaption,[data-testid="stMarkdownContainer"]{color:#d4dce5}
        .qa-kicker{color:var(--qa-blue);font-size:.72rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:.35rem}
        .qa-title{color:var(--qa-text);font-size:clamp(1.55rem,2vw,2.2rem);font-weight:760;line-height:1.08}
        .qa-subtitle{color:var(--qa-muted);font-size:.92rem;margin:.48rem 0 1.1rem;max-width:920px}
        .qa-card{background:var(--qa-panel);border:1px solid var(--qa-border);border-radius:14px;padding:.9rem 1rem;min-height:94px;box-shadow:inset 0 1px 0 rgba(255,255,255,.025),0 8px 22px rgba(0,0,0,.14)}
        .qa-card-label{color:var(--qa-muted);font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:.42rem}
        .qa-card-value{color:var(--qa-text);font-size:1.04rem;font-weight:720;line-height:1.2}
        .qa-card-note{color:var(--qa-muted);font-size:.76rem;margin-top:.38rem;line-height:1.3}
        .qa-summary{background:var(--qa-soft);border:1px solid var(--qa-border);border-radius:14px;padding:.85rem 1rem;margin:.65rem 0 1rem}
        .qa-badge{display:inline-flex;align-items:center;border-radius:999px;padding:.22rem .52rem;border:1px solid var(--qa-border2);font-size:.68rem;font-weight:720;white-space:nowrap}
        .qa-positive{color:#9bd7bb;background:rgba(86,183,139,.11);border-color:rgba(86,183,139,.30)}
        .qa-negative{color:#efaaad;background:rgba(211,109,114,.11);border-color:rgba(211,109,114,.30)}
        .qa-warning{color:#e7c98c;background:rgba(213,162,79,.11);border-color:rgba(213,162,79,.30)}
        .qa-info{color:#9bc9df;background:rgba(98,166,201,.10);border-color:rgba(98,166,201,.28)}
        .qa-neutral{color:#c0c8d2;background:rgba(170,180,192,.08)}
        .qa-muted{color:#8f9baa;background:rgba(143,155,170,.06)}
        [data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--qa-border)!important;background:rgba(19,27,36,.58);border-radius:14px}
        [data-baseweb="tab-list"]{gap:.35rem;background:transparent;border-bottom:1px solid var(--qa-border)}
        [data-baseweb="tab"]{background:transparent!important;color:var(--qa-muted)!important;font-weight:650}
        [aria-selected="true"][data-baseweb="tab"]{color:var(--qa-text)!important}
        [data-baseweb="select"]>div,[data-baseweb="input"]>div,.stTextInput input{background:var(--qa-panel)!important;border-color:var(--qa-border2)!important;color:var(--qa-text)!important}
        .stButton>button{background:var(--qa-panel2);color:var(--qa-text);border:1px solid var(--qa-border2);border-radius:10px;font-weight:680}
        .stButton>button:hover{border-color:rgba(98,166,201,.52);background:#1b2834;color:#fff}
        [data-testid="stDataFrame"]{border:1px solid var(--qa-border);border-radius:12px;overflow:hidden}
        details{border-color:var(--qa-border)!important;background:rgba(16,22,30,.38)!important;border-radius:12px!important}
        .stAlert{background:var(--qa-panel)!important;border-color:var(--qa-border2)!important;color:var(--qa-text)!important}
        </style>
        """,
        unsafe_allow_html=True,
    )


def tone_for(value: Any) -> str:
    text = str(value or "").lower()
    if any(x in text for x in ("bullish", "positiv", "confirmed", "bestätigt", "favor")):
        return "positive"
    if any(x in text for x in ("bearish", "negativ", "avoid", "vermeiden")):
        return "negative"
    if any(x in text for x in ("conflict", "konflikt", "transition", "watch", "beobachten")):
        return "warning"
    if any(x in text for x in ("insufficient", "low confidence", "no current signal")):
        return "muted"
    return "neutral"


def badge(value: Any, tone: str | None = None) -> str:
    label = escape(str(value if value not in (None, "") else "—"))
    return f'<span class="qa-badge qa-{escape(tone or tone_for(value))}">{label}</span>'


def render_page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="qa-kicker">{escape(kicker)}</div>'
        f'<div class="qa-title">{escape(title)}</div>'
        f'<div class="qa-subtitle">{escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def render_card(label: str, value: Any, note: str = "", *, tone: str | None = None) -> None:
    st.markdown(
        '<div class="qa-card">'
        f'<div class="qa-card-label">{escape(label)}</div>'
        f'<div class="qa-card-value">{badge(value, tone)}</div>'
        f'<div class="qa-card-note">{escape(str(note or ""))}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_summary(text: str) -> None:
    st.markdown(f'<div class="qa-summary">{escape(str(text))}</div>', unsafe_allow_html=True)

# V3.29.0.3.1 · NATIVE DARK WIDGET OVERLAY
_v329031_base_apply_trader_dark_theme = apply_trader_dark_theme


def _v329031_dark_widget_overlay() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stDataFrame"],
        [data-testid="stDataFrame"] > div,
        [data-testid="stDataFrame"] canvas,
        [data-testid="stTable"],
        [data-testid="stTable"] > div {
            background-color: #131B24 !important;
            color: #EDF2F7 !important;
        }

        [data-baseweb="select"] > div,
        [data-baseweb="select"] input,
        [data-baseweb="popover"] > div,
        [role="listbox"],
        [role="option"] {
            background-color: #131B24 !important;
            color: #EDF2F7 !important;
            border-color: rgba(151, 166, 186, 0.26) !important;
        }

        [data-testid="stExpander"],
        [data-testid="stExpander"] details,
        [data-testid="stExpander"] summary {
            background-color: #131B24 !important;
            color: #EDF2F7 !important;
            border-color: rgba(151, 166, 186, 0.18) !important;
        }

        [data-testid="stButton"] button,
        [data-testid="stBaseButton-secondary"] {
            background-color: #18222D !important;
            color: #EDF2F7 !important;
            border-color: rgba(151, 166, 186, 0.26) !important;
        }

        [data-testid="stDataFrame"] * {
            --gdg-bg-cell: #131B24;
            --gdg-bg-cell-medium: #18222D;
            --gdg-text-dark: #EDF2F7;
            --gdg-text-medium: #C2CBD5;
            --gdg-border-color: rgba(151, 166, 186, 0.20);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_trader_dark_theme() -> None:
    _v329031_base_apply_trader_dark_theme()
    _v329031_dark_widget_overlay()

# V3.29.1 · SELECTBOX DARK OVERRIDE
_v32910_base_apply_trader_dark_theme = apply_trader_dark_theme


def _v32910_dark_selectbox_overlay() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSelectbox"] {
            color-scheme: dark !important;
        }

        [data-testid="stSelectbox"] div[data-baseweb="select"],
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div > div,
        [data-testid="stSelectbox"] [role="combobox"],
        [data-testid="stSelectbox"] input {
            background: #131B24 !important;
            background-color: #131B24 !important;
            color: #EDF2F7 !important;
            border-color: rgba(151, 166, 186, 0.28) !important;
            box-shadow: none !important;
            -webkit-text-fill-color: #EDF2F7 !important;
        }

        [data-testid="stSelectbox"] div[data-baseweb="select"] * {
            color: #EDF2F7 !important;
            -webkit-text-fill-color: #EDF2F7 !important;
        }

        [data-testid="stSelectbox"] svg {
            color: #9DAABA !important;
            fill: #9DAABA !important;
        }

        [data-baseweb="popover"],
        [data-baseweb="popover"] > div,
        [data-baseweb="menu"],
        [role="listbox"],
        [role="option"] {
            background: #131B24 !important;
            background-color: #131B24 !important;
            color: #EDF2F7 !important;
        }

        [role="option"]:hover,
        [role="option"][aria-selected="true"] {
            background: #1B2834 !important;
            background-color: #1B2834 !important;
            color: #FFFFFF !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_trader_dark_theme() -> None:
    _v32910_base_apply_trader_dark_theme()
    _v32910_dark_selectbox_overlay()

# V3.29.2 · TABLE CONTRAST THEME
_v32920_base_apply_trader_dark_theme = apply_trader_dark_theme


def _v32920_table_contrast_overlay() -> None:
    st.markdown(
        """
        <style>
        /*
        V3.29.2 · Trader table hierarchy
        Background        #0B0F14
        Cards             #131B24
        Header            #1A2029
        Rows              #0F151C
        Border            #29333E
        Primary text      #EDF2F7
        Secondary text    #929EAD
        */

        [data-testid="stDataFrame"] {
            background: #0F151C !important;
            border: 1px solid #29333E !important;
            border-radius: 12px !important;
            overflow: hidden !important;

            --gdg-bg-cell: #0F151C;
            --gdg-bg-cell-medium: #131B24;
            --gdg-bg-header: #1A2029;
            --gdg-bg-header-hovered: #202936;
            --gdg-bg-header-has-focus: #202936;
            --gdg-text-dark: #EDF2F7;
            --gdg-text-medium: #C3CCD6;
            --gdg-text-light: #929EAD;
            --gdg-border-color: #29333E;
            --gdg-horizontal-border-color: #202A34;
            --gdg-accent-color: #62A6C9;
            --gdg-accent-light: rgba(98, 166, 201, 0.14);
        }

        [data-testid="stDataFrame"] > div,
        [data-testid="stDataFrame"] canvas {
            background: #0F151C !important;
        }

        /*
        Native Streamlit tables (st.table) use real DOM cells.
        Keep them visually aligned with st.dataframe.
        */
        [data-testid="stTable"] {
            background: #0F151C !important;
            border: 1px solid #29333E !important;
            border-radius: 12px !important;
            overflow: hidden !important;
        }

        [data-testid="stTable"] table {
            border-collapse: collapse !important;
            width: 100% !important;
            background: #0F151C !important;
        }

        [data-testid="stTable"] thead th {
            background: #1A2029 !important;
            color: #AEB8C4 !important;
            border-bottom: 1px solid #33404D !important;
            border-right: 1px solid #29333E !important;
            font-weight: 700 !important;
            letter-spacing: 0.01em !important;
        }

        [data-testid="stTable"] tbody td,
        [data-testid="stTable"] tbody th {
            background: #0F151C !important;
            color: #EDF2F7 !important;
            border-bottom: 1px solid #202A34 !important;
            border-right: 1px solid #202A34 !important;
        }

        [data-testid="stTable"] tbody tr:hover td,
        [data-testid="stTable"] tbody tr:hover th {
            background: #141D26 !important;
        }

        /*
        Pandas Styler / HTML tables rendered through markdown or components.
        */
        .stMarkdown table,
        [data-testid="stMarkdownContainer"] table {
            width: 100% !important;
            border-collapse: separate !important;
            border-spacing: 0 !important;
            background: #0F151C !important;
            border: 1px solid #29333E !important;
            border-radius: 10px !important;
            overflow: hidden !important;
        }

        .stMarkdown table thead th,
        [data-testid="stMarkdownContainer"] table thead th {
            background: #1A2029 !important;
            color: #AEB8C4 !important;
            border-bottom: 1px solid #33404D !important;
            border-right: 1px solid #29333E !important;
        }

        .stMarkdown table tbody td,
        [data-testid="stMarkdownContainer"] table tbody td {
            background: #0F151C !important;
            color: #EDF2F7 !important;
            border-bottom: 1px solid #202A34 !important;
            border-right: 1px solid #202A34 !important;
        }

        .stMarkdown table tbody tr:hover td,
        [data-testid="stMarkdownContainer"] table tbody tr:hover td {
            background: #141D26 !important;
        }

        /*
        Keep the table visually calm: no heavy white focus frames.
        */
        [data-testid="stDataFrame"]:focus-within,
        [data-testid="stTable"]:focus-within {
            outline: 1px solid rgba(98, 166, 201, 0.42) !important;
            outline-offset: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_trader_dark_theme() -> None:
    _v32920_base_apply_trader_dark_theme()
    _v32920_table_contrast_overlay()
