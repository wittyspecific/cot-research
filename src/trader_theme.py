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

# V3.29.5 · UNIFIED DARK SURFACE THEME
_v32950_base_apply_trader_dark_theme = apply_trader_dark_theme


def _v32950_unified_trader_surface_overlay() -> None:
    st.markdown(
        """
        <style>
        :root {
            --qa-bg: #0B0F14;
            --qa-surface: #0B0F14;
            --qa-control: #111923;
            --qa-control-hover: #151F2A;
            --qa-border: #29333E;
            --qa-border-soft: #202A34;
            --qa-text: #F3F6FB;
            --qa-text-soft: #C4CDD7;
            --qa-muted: #8F9BAA;
            --qa-blue: #62A6C9;
        }

        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {
            background: var(--qa-bg) !important;
            background-color: var(--qa-bg) !important;
            color: var(--qa-text) !important;
        }

        [data-testid="stAppViewContainer"] h1 {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
        }

        [data-testid="stAppViewContainer"] h2,
        [data-testid="stAppViewContainer"] h3,
        [data-testid="stAppViewContainer"] h4,
        [class*="kicker"],
        [class*="eyebrow"],
        [class*="section-title"],
        [class*="section_title"],
        [class*="overline"] {
            color: var(--qa-blue) !important;
            -webkit-text-fill-color: var(--qa-blue) !important;
        }

        [data-testid="stAppViewContainer"] p,
        [data-testid="stAppViewContainer"] label,
        [data-testid="stAppViewContainer"] li {
            color: var(--qa-text) !important;
        }

        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] *,
        small,
        [class*="subtitle"],
        [class*="meta"] {
            color: var(--qa-muted) !important;
            -webkit-text-fill-color: var(--qa-muted) !important;
        }

        /* New research cards: same background as page, hierarchy through border */
        .trader-card,
        .research-card,
        .state-card,
        .signal-card,
        .metric-card,
        .summary-card {
            background: var(--qa-surface) !important;
            background-color: var(--qa-surface) !important;
            border: 1px solid var(--qa-border) !important;
            box-shadow: none !important;
            color: var(--qa-text) !important;
        }

        .trader-card *,
        .research-card *,
        .state-card *,
        .signal-card *,
        .metric-card *,
        .summary-card * {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
        }

        /* Remove any remaining explicit white surfaces in research pages */
        [data-testid="stAppViewContainer"] [style*="background: white"],
        [data-testid="stAppViewContainer"] [style*="background:white"],
        [data-testid="stAppViewContainer"] [style*="background-color: white"],
        [data-testid="stAppViewContainer"] [style*="background-color:white"],
        [data-testid="stAppViewContainer"] [style*="background: #fff"],
        [data-testid="stAppViewContainer"] [style*="background:#fff"],
        [data-testid="stAppViewContainer"] [style*="background: #ffffff"],
        [data-testid="stAppViewContainer"] [style*="background:#ffffff"],
        [data-testid="stAppViewContainer"] [style*="background: #FFFFFF"],
        [data-testid="stAppViewContainer"] [style*="background:#FFFFFF"] {
            background: var(--qa-surface) !important;
            background-color: var(--qa-surface) !important;
            color: var(--qa-text) !important;
            border-color: var(--qa-border) !important;
            box-shadow: none !important;
        }

        [data-testid="stAppViewContainer"] [style*="background: white"] *,
        [data-testid="stAppViewContainer"] [style*="background:white"] *,
        [data-testid="stAppViewContainer"] [style*="background-color: white"] *,
        [data-testid="stAppViewContainer"] [style*="background-color:white"] *,
        [data-testid="stAppViewContainer"] [style*="background: #fff"] *,
        [data-testid="stAppViewContainer"] [style*="background:#fff"] *,
        [data-testid="stAppViewContainer"] [style*="background: #ffffff"] *,
        [data-testid="stAppViewContainer"] [style*="background:#ffffff"] *,
        [data-testid="stAppViewContainer"] [style*="background: #FFFFFF"] *,
        [data-testid="stAppViewContainer"] [style*="background:#FFFFFF"] * {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
        }

        [data-testid="stBaseButton-secondary"],
        [data-testid="stPageLink"] a {
            background: var(--qa-surface) !important;
            background-color: var(--qa-surface) !important;
            color: var(--qa-text) !important;
            border: 1px solid var(--qa-border) !important;
            box-shadow: none !important;
        }

        [data-testid="stBaseButton-secondary"] *,
        [data-testid="stPageLink"] a * {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
        }

        [data-testid="stTextInput"] div[data-baseweb="input"],
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] div[data-baseweb="input"],
        [data-testid="stNumberInput"] input,
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
            background: var(--qa-control) !important;
            background-color: var(--qa-control) !important;
            color: var(--qa-text) !important;
            border-color: var(--qa-border) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
            box-shadow: none !important;
        }

        [data-testid="stSelectbox"] div[data-baseweb="select"] *,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] *,
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
        }

        div[data-baseweb="popover"],
        div[data-baseweb="menu"],
        ul[role="listbox"],
        [role="option"] {
            background: var(--qa-control) !important;
            background-color: var(--qa-control) !important;
            color: var(--qa-text) !important;
        }

        [role="option"]:hover,
        [role="option"][aria-selected="true"] {
            background: var(--qa-control-hover) !important;
            background-color: var(--qa-control-hover) !important;
        }

        [data-testid="stExpander"],
        [data-testid="stForm"],
        [data-testid="stVerticalBlockBorderWrapper"] > div {
            background: var(--qa-surface) !important;
            background-color: var(--qa-surface) !important;
            border-color: var(--qa-border) !important;
            box-shadow: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_trader_dark_theme() -> None:
    _v32950_base_apply_trader_dark_theme()
    _v32950_unified_trader_surface_overlay()

# V3.30.0 · HEDGE FUND UI FOUNDATION
_v3300_base_apply_trader_dark_theme = apply_trader_dark_theme


def apply_trader_dark_theme() -> None:
    _v3300_base_apply_trader_dark_theme()

    from src.ui.hedgefund import apply_hedgefund_theme

    apply_hedgefund_theme()

# V3.30.1 · VISIBLE HEDGE FUND COMPONENT MIGRATION
_v3301_base_apply_trader_dark_theme = apply_trader_dark_theme


def _v3301_visible_component_css() -> None:
    st.markdown(
        """
        <style>
        /* ---------------------------------------------------------
           V3.30.1 visible institutional shell
           --------------------------------------------------------- */
        [data-testid="stMainBlockContainer"] {
            max-width: 1540px !important;
            padding-top: 1.4rem !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }

        [data-testid="stSidebar"] {
            background:
                linear-gradient(
                    180deg,
                    #07101A 0%,
                    #09131D 55%,
                    #081018 100%
                ) !important;
            border-right: 1px solid #1B2A38 !important;
        }

        [data-testid="stSidebar"] [data-testid="stPageLink"] a {
            min-height: 42px !important;
            padding: .48rem .72rem !important;
            border-radius: 8px !important;
            transition:
                background .15s ease,
                border-color .15s ease,
                color .15s ease !important;
        }

        [data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {
            background: #0E1A26 !important;
            border-color: #223849 !important;
        }

        [data-testid="stSidebar"] [aria-current="page"],
        [data-testid="stSidebar"] a[aria-current="page"] {
            background:
                linear-gradient(
                    90deg,
                    rgba(98,166,201,.17),
                    rgba(98,166,201,.045)
                ) !important;
            color: #F3F6FB !important;
            border-color: rgba(98,166,201,.34) !important;
            box-shadow:
                inset 3px 0 0 #62A6C9 !important;
        }

        /* ---------------------------------------------------------
           Hedge-fund page header
           --------------------------------------------------------- */
        .hf330-page-head {
            position: relative;
            margin: 0 0 1.15rem 0;
            padding: .4rem 0 1rem 0;
            border-bottom: 1px solid #1A2835;
        }

        .hf330-page-head::after {
            content: "";
            position: absolute;
            bottom: -1px;
            left: 0;
            width: 76px;
            height: 1px;
            background:
                linear-gradient(
                    90deg,
                    #62A6C9,
                    rgba(98,166,201,0)
                );
        }

        .hf330-kicker {
            color: #62A6C9 !important;
            font-size: .70rem;
            font-weight: 800;
            line-height: 1.2;
            letter-spacing: .16em;
            text-transform: uppercase;
            margin-bottom: .48rem;
        }

        .hf330-title {
            color: #F3F6FB !important;
            font-size: clamp(1.8rem, 2.5vw, 2.65rem);
            font-weight: 780;
            line-height: 1.02;
            letter-spacing: -.034em;
            margin: 0;
        }

        .hf330-subtitle {
            color: #95A3B3 !important;
            font-size: .94rem;
            line-height: 1.55;
            max-width: 940px;
            margin-top: .6rem;
        }

        /* ---------------------------------------------------------
           Institutional data card
           --------------------------------------------------------- */
        .hf330-card {
            position: relative;
            min-height: 112px;
            padding: .95rem 1rem .9rem 1rem;
            border: 1px solid #22303D;
            border-radius: 10px;
            background:
                radial-gradient(
                    circle at 100% 0%,
                    rgba(98,166,201,.055),
                    transparent 38%
                ),
                linear-gradient(
                    180deg,
                    rgba(17,29,41,.98),
                    rgba(13,23,34,.98)
                );
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,.025),
                0 12px 28px rgba(0,0,0,.14);
            overflow: hidden;
        }

        .hf330-card::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--hf330-accent, #62A6C9);
            opacity: .78;
        }

        .hf330-card-label {
            color: #95A3B3 !important;
            font-size: .66rem;
            font-weight: 800;
            letter-spacing: .115em;
            text-transform: uppercase;
            margin-bottom: .55rem;
        }

        .hf330-card-value {
            color: var(--hf330-accent, #F3F6FB) !important;
            font-size: 1.16rem;
            line-height: 1.18;
            font-weight: 780;
            letter-spacing: -.01em;
            word-break: break-word;
        }

        .hf330-card-note {
            color: #95A3B3 !important;
            font-size: .74rem;
            line-height: 1.38;
            margin-top: .5rem;
        }

        .hf330-card-note:empty {
            display: none;
        }

        /* ---------------------------------------------------------
           Thesis / summary bar
           --------------------------------------------------------- */
        .hf330-summary {
            position: relative;
            display: flex;
            gap: .72rem;
            align-items: flex-start;
            background:
                linear-gradient(
                    90deg,
                    rgba(98,166,201,.075),
                    rgba(13,23,34,.88) 28%,
                    rgba(13,23,34,.88)
                );
            border: 1px solid #22303D;
            border-radius: 10px;
            color: #D8E0E9 !important;
            padding: .85rem 1rem;
            margin: .72rem 0 1.05rem 0;
            line-height: 1.52;
            font-size: .88rem;
        }

        .hf330-summary::before {
            content: "◈";
            color: #62A6C9;
            flex: 0 0 auto;
            font-size: .94rem;
            margin-top: .03rem;
        }

        /* ---------------------------------------------------------
           Make Streamlit bordered containers look like mockup panels
           --------------------------------------------------------- */
        [data-testid="stVerticalBlockBorderWrapper"] > div {
            background:
                linear-gradient(
                    180deg,
                    rgba(17,29,41,.72),
                    rgba(13,23,34,.72)
                ) !important;
            border: 1px solid #22303D !important;
            border-radius: 10px !important;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,.02) !important;
        }

        /* Tabs closer to mockup */
        [data-baseweb="tab-list"] {
            min-height: 42px !important;
            gap: 1.25rem !important;
            border-bottom: 1px solid #22303D !important;
        }

        [data-baseweb="tab"] {
            font-size: .82rem !important;
            font-weight: 680 !important;
            padding: .55rem 0 .65rem !important;
        }

        /* Dataframes get less rounded / more terminal-like */
        [data-testid="stDataFrame"] {
            border-radius: 8px !important;
            border-color: #22303D !important;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,.015) !important;
        }

        /* Expander as institutional utility row */
        [data-testid="stExpander"] {
            border-radius: 8px !important;
            background: #0D1722 !important;
            border-color: #22303D !important;
        }

        /* Form / select controls */
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
        [data-testid="stTextInput"] div[data-baseweb="input"],
        [data-testid="stNumberInput"] div[data-baseweb="input"] {
            min-height: 40px !important;
            border-radius: 8px !important;
            background: #0D1722 !important;
            border-color: #22303D !important;
        }

        .stButton > button {
            min-height: 38px !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_trader_dark_theme() -> None:
    _v3301_base_apply_trader_dark_theme()
    _v3301_visible_component_css()


def _v3301_tone_color(
    value: Any,
    tone: str | None = None,
) -> str:
    resolved = str(
        tone or tone_for(value)
    ).lower()

    return {
        "positive": "#65D98B",
        "negative": "#FF7373",
        "warning": "#F2B84B",
        "info": "#62A6C9",
        "transition": "#79B8FF",
        "purple": "#B59BFF",
        "muted": "#7F8B99",
        "neutral": "#F3F6FB",
    }.get(
        resolved,
        "#F3F6FB",
    )


def render_page_header(
    kicker: str,
    title: str,
    subtitle: str,
) -> None:
    st.markdown(
        (
            '<div class="hf330-page-head">'
            f'<div class="hf330-kicker">{escape(str(kicker))}</div>'
            f'<div class="hf330-title">{escape(str(title))}</div>'
            f'<div class="hf330-subtitle">{escape(str(subtitle or ""))}</div>'
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
    accent = _v3301_tone_color(
        value,
        tone,
    )

    display = (
        "—"
        if value in (
            None,
            "",
        )
        else str(value)
    )

    st.markdown(
        (
            '<div class="hf330-card" '
            f'style="--hf330-accent:{accent}">'
            f'<div class="hf330-card-label">{escape(str(label))}</div>'
            f'<div class="hf330-card-value">{escape(display)}</div>'
            f'<div class="hf330-card-note">{escape(str(note or ""))}</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def render_summary(
    text: str,
) -> None:
    st.markdown(
        (
            '<div class="hf330-summary">'
            f'{escape(str(text or ""))}'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

# V3.30.2 · FULL HEDGE FUND UI MIGRATION
_v3302_base_apply_trader_dark_theme = apply_trader_dark_theme


def apply_trader_dark_theme() -> None:
    _v3302_base_apply_trader_dark_theme()

    from src.ui.hedgefund import apply_hedgefund_theme

    apply_hedgefund_theme()


def render_page_header(kicker, title, subtitle) -> None:
    from src.ui.hedgefund import render_page_header as _hf_render_page_header

    _hf_render_page_header(kicker, title, subtitle)


def render_card(label, value, note="", *, tone=None) -> None:
    from src.ui.hedgefund import render_card as _hf_render_card

    _hf_render_card(
        label,
        value,
        note,
        tone=tone,
    )


def render_summary(text) -> None:
    from src.ui.hedgefund import render_summary as _hf_render_summary

    _hf_render_summary(text)
