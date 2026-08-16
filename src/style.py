
from __future__ import annotations

from html import escape
import uuid

import pandas as pd
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components


# ---------------------------------------------------------------------------
# VISUAL TOKENS · single source of truth for the UI
# ---------------------------------------------------------------------------
COLORS = {
    "bg": "#0B1320",
    "surface": "#121D2E",
    "surface_alt": "#17243A",
    "surface_deep": "#0F1928",
    "line": "#35485F",
    "line_soft": "#26384D",
    "text": "#F3F7FC",
    "muted": "#B3C0D0",
    "muted_2": "#8596AC",
    "accent": "#7EB9E6",
    "bull": "#78D2A0",
    "bear": "#EB8A8A",
}

# Semantic chart palette. These colors stay fixed across all charts so the
# same market participant is visually recognizable everywhere. The palette is
# deliberately high-contrast on the dark dashboard background.
CHART_COLORS = {
    "commercial": "#19C7FF",       # bright cyan
    "noncommercial": "#FF9D00",    # amber / orange
    "retail": "#9BE600",           # lime green
    "speculative": "#B887FF",      # violet
    "price": "#F2F6FC",            # near-white
    "range_high": "#50D6A4",       # mint
    "range_low": "#FF7474",        # soft red
    "reference": "#7F93AA",        # muted blue-grey
}

CHART_COLORWAY = [
    CHART_COLORS["commercial"],
    CHART_COLORS["noncommercial"],
    CHART_COLORS["retail"],
    CHART_COLORS["speculative"],
    "#FFD166",
    "#4DD4AC",
    "#EF7FBF",
    "#7DA6FF",
]

SPACING = {
    "page_top": "1.8rem",
    "page_bottom": "4rem",
    "section": "2rem",
    "row_y": "0.82rem",
    "row_x": "0.9rem",
    "tight": "0.45rem",
}

TYPE = {
    "body": "0.94rem",
    "body_small": "0.81rem",
    "metric": "1.22rem",
    "title": "2.05rem",
    "tracking": "0.10em",
}


def _css_vars() -> str:
    tokens = {
        "--bg": COLORS["bg"],
        "--surface": COLORS["surface"],
        "--surface-alt": COLORS["surface_alt"],
        "--surface-deep": COLORS["surface_deep"],
        "--line": COLORS["line"],
        "--line-soft": COLORS["line_soft"],
        "--text": COLORS["text"],
        "--muted": COLORS["muted"],
        "--muted-2": COLORS["muted_2"],
        "--accent": COLORS["accent"],
        "--bull": COLORS["bull"],
        "--bear": COLORS["bear"],
        "--space-page-top": SPACING["page_top"],
        "--space-page-bottom": SPACING["page_bottom"],
        "--space-section": SPACING["section"],
        "--space-row-y": SPACING["row_y"],
        "--space-row-x": SPACING["row_x"],
        "--space-tight": SPACING["tight"],
        "--font-body": TYPE["body"],
        "--font-small": TYPE["body_small"],
        "--font-metric": TYPE["metric"],
        "--font-title": TYPE["title"],
        "--tracking": TYPE["tracking"],
    }
    return "\n".join(f"{key}:{value};" for key, value in tokens.items())


def apply_style():
    st.markdown(
        f"""
        <style>
        :root {{
            {_css_vars()}
        }}

        html, body, [class*="css"] {{
            font-variant-numeric: tabular-nums lining-nums;
        }}

        .stApp {{
            background: var(--bg);
            color: var(--text);
        }}

        [data-testid="stSidebar"] {{
            background: var(--surface);
            border-right: 1px solid var(--line);
        }}

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label {{
            color: var(--muted) !important;
        }}

        [data-testid="stSidebar"] * {{
            font-size: var(--font-body);
        }}

        .block-container {{
            max-width: 1440px;
            padding-top: var(--space-page-top);
            padding-bottom: var(--space-page-bottom);
        }}

        h1 {{
            color: var(--text) !important;
            font-size: var(--font-title) !important;
            font-weight: 620 !important;
            letter-spacing: -0.025em !important;
            margin: 0 !important;
        }}

        h2, h3, h4 {{
            color: var(--muted) !important;
            text-transform: uppercase;
            letter-spacing: var(--tracking) !important;
            font-weight: 620 !important;
        }}

        h2 {{
            font-size: 0.82rem !important;
            margin-top: var(--space-section) !important;
        }}

        h3 {{
            font-size: 0.76rem !important;
            margin-top: var(--space-section) !important;
        }}

        h4 {{
            font-size: 0.72rem !important;
            margin-top: 1.2rem !important;
        }}

        p, li, label {{
            font-size: var(--font-body);
            line-height: 1.62;
        }}

        [data-testid="stCaptionContainer"] p {{
            color: var(--muted) !important;
            font-size: var(--font-small) !important;
            line-height: 1.5;
        }}

        a {{
            color: var(--accent) !important;
        }}

        hr {{
            border-color: var(--line-soft) !important;
        }}

        /* No rounded consumer-app styling. */
        button,
        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        input,
        textarea,
        [data-testid="stExpander"] details,
        [data-testid="stAlert"] {{
            border-radius: 0 !important;
            box-shadow: none !important;
        }}

        [data-testid="stButton"] button {{
            background: transparent !important;
            color: var(--text) !important;
            border: 1px solid var(--line) !important;
            min-height: 2.10rem;
            font-size: var(--font-small) !important;
            font-weight: 620 !important;
            letter-spacing: 0.01em;
            padding: 0.30rem 0.48rem !important;
        }}

        [data-testid="stButton"] button:hover {{
            border-color: var(--accent) !important;
            color: var(--accent) !important;
        }}

        [data-testid="stPageLink"] a {{
            border: 1px solid var(--line) !important;
            border-radius: 0 !important;
            background: var(--surface-alt) !important;
            min-height: 2.55rem;
            padding: 0.58rem 0.78rem !important;
        }}

        [data-testid="stPageLink"] a:hover {{
            border-color: var(--accent) !important;
        }}

        .terminal-header {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 1rem;
            align-items: end;
            border-bottom: 1px solid var(--line);
            padding-bottom: 0.8rem;
            margin-bottom: 0.55rem;
        }}

        .terminal-eyebrow {{
            color: var(--muted-2);
            font-size: 0.70rem;
            font-weight: 650;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            margin-bottom: 0.28rem;
        }}

        .terminal-build {{
            color: var(--muted);
            border-left: 1px solid var(--line);
            padding-left: 0.8rem;
            font-size: 0.67rem;
            letter-spacing: 0.11em;
            text-transform: uppercase;
            white-space: nowrap;
        }}

        .page-question {{
            display: flex;
            gap: 0.55rem;
            align-items: baseline;
            color: var(--text);
            font-size: 1.02rem;
            padding: 0.42rem 0 0.82rem 0;
            margin-bottom: 0.35rem;
        }}

        .page-question span {{
            color: var(--accent);
            font-size: 0.65rem;
            font-weight: 700;
            letter-spacing: 0.15em;
            text-transform: uppercase;
            white-space: nowrap;
        }}

        .context-strip {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            border-top: 1px solid var(--line);
            border-bottom: 1px solid var(--line);
            margin: 1rem 0 1.25rem 0;
            background: var(--surface);
        }}

        .context-item {{
            min-width: 0;
            padding: 0.78rem 0.85rem;
            border-right: 1px solid var(--line-soft);
        }}

        .context-item:last-child {{
            border-right: 0;
        }}

        .context-label {{
            color: var(--muted-2);
            font-size: 0.64rem;
            letter-spacing: 0.13em;
            text-transform: uppercase;
            margin-bottom: 0.18rem;
        }}

        .context-value {{
            color: var(--text);
            font-size: 1.02rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .stage-summary {{
            border-top: 1px solid var(--line);
            margin: 0.9rem 0 1.55rem 0;
        }}

        .stage-row {{
            display: grid;
            grid-template-columns: 150px minmax(250px, 0.9fr) minmax(340px, 1.35fr);
            gap: 1rem;
            align-items: center;
            min-height: 64px;
            padding: var(--space-row-y) var(--space-row-x);
            border-bottom: 1px solid var(--line-soft);
            background: var(--surface);
        }}

        .stage-number {{
            color: var(--accent);
            font-size: 0.64rem;
            font-weight: 700;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            margin-right: 0.35rem;
        }}

        .stage-label {{
            color: var(--muted);
            font-size: 0.67rem;
            font-weight: 650;
            letter-spacing: 0.11em;
            text-transform: uppercase;
        }}

        .stage-primary {{
            color: var(--text);
            font-size: 1.02rem;
            font-weight: 570;
        }}

        .stage-detail {{
            color: var(--muted);
            font-size: var(--font-small);
            line-height: 1.46;
        }}

        .direction-bull {{
            color: var(--bull) !important;
        }}

        .direction-bear {{
            color: var(--bear) !important;
        }}

        .section-line {{
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: baseline;
            border-bottom: 1px solid var(--line);
            padding: 0 0 0.38rem 0;
            margin: var(--space-section) 0 0.58rem 0;
        }}

        .section-line .name {{
            color: var(--muted);
            font-size: 0.73rem;
            font-weight: 700;
            letter-spacing: 0.13em;
            text-transform: uppercase;
        }}

        .section-line .meta {{
            color: var(--muted-2);
            font-size: 0.73rem;
        }}

        .definition {{
            color: var(--muted);
            border-left: 2px solid var(--line);
            padding: 0.25rem 0 0.25rem 0.62rem;
            margin: 0.2rem 0 0.72rem 0;
            font-size: var(--font-small);
            line-height: 1.5;
        }}

        .empty-state {{
            background: var(--surface);
            border-top: 1px solid var(--line);
            border-bottom: 1px solid var(--line);
            padding: 1.15rem 0.8rem;
            margin: 0.55rem 0 1rem 0;
        }}

        .empty-state strong {{
            display: block;
            color: var(--text);
            font-size: 0.84rem;
            font-weight: 560;
            margin-bottom: 0.18rem;
        }}

        .empty-state span {{
            color: var(--muted);
            font-size: var(--font-small);
        }}

        .metric {{
            background: var(--surface);
            border-top: 1px solid var(--line);
            border-bottom: 1px solid var(--line);
            min-height: 98px;
            padding: 0.72rem 0.72rem;
        }}

        .metric small {{
            display: block;
            color: var(--muted-2);
            font-size: 0.64rem;
            font-weight: 650;
            letter-spacing: 0.11em;
            text-transform: uppercase;
            margin-bottom: 0.38rem;
        }}

        .metric .value {{
            color: var(--text);
            font-size: var(--font-metric);
            font-weight: 570;
            line-height: 1.18;
        }}

        .metric .note {{
            color: var(--muted);
            font-size: 0.73rem;
            margin-top: 0.28rem;
            line-height: 1.4;
        }}

        .signalbox {{
            background: var(--surface);
            border-top: 1px solid var(--line);
            border-bottom: 1px solid var(--line);
            padding: 0.8rem 0.75rem;
            min-height: 220px;
        }}

        .signalbox small {{
            color: var(--muted-2);
            letter-spacing: 0.12em;
            font-size: 0.64rem;
        }}

        .signalbox .signal {{
            color: var(--text);
            font-size: var(--font-metric);
            font-weight: 570;
            margin: 0.45rem 0 0.7rem 0;
        }}

        .signalbox .signal-small {{
            font-size: 1.02rem;
        }}

        .signalbox p {{
            color: var(--muted);
            line-height: 1.62;
            font-size: var(--font-small);
        }}

        .watch-row {{
            background: var(--surface-deep);
            border-bottom: 1px solid var(--line-soft);
            padding: 0.16rem 0;
        }}

        .watch-row-note {{
            color: var(--muted);
            font-size: 0.73rem;
            margin: -0.08rem 0 0.38rem 0.2rem;
        }}

        div[data-testid="stDataFrame"],
        div[data-testid="stPlotlyChart"] {{
            border: 1px solid var(--line) !important;
            background: var(--surface) !important;
        }}

        div[data-testid="stDataFrame"] {{
            font-variant-numeric: tabular-nums;
        }}

        div[data-testid="stTabs"] button {{
            text-transform: uppercase;
            letter-spacing: 0.055em;
            font-size: 0.70rem;
            font-weight: 650;
            color: var(--muted);
            padding-left: 0.55rem;
            padding-right: 0.55rem;
        }}

        div[data-testid="stTabs"] button[aria-selected="true"] {{
            color: var(--text);
            border-bottom-color: var(--accent) !important;
        }}

        [data-testid="stAlert"] {{
            background: var(--surface) !important;
            border: 1px solid var(--line) !important;
            color: var(--text) !important;
        }}

        [data-testid="stExpander"] details {{
            background: var(--surface) !important;
            border: 1px solid var(--line) !important;
        }}

        [data-testid="stExpander"] summary {{
            color: var(--text) !important;
            font-weight: 600;
        }}


        .terminal-cell {{
            min-height: 3.05rem;
            padding: 0.28rem 0.16rem 0.30rem 0.16rem;
        }}

        .terminal-cell .primary {{
            color: var(--text);
            font-size: 0.84rem;
            font-weight: 550;
            line-height: 1.25;
            white-space: normal;
        }}

        .terminal-cell .secondary {{
            color: var(--muted-2);
            font-size: 0.70rem;
            line-height: 1.25;
            margin-top: 0.12rem;
        }}

        .terminal-table-head {{
            color: var(--muted-2);
            font-size: 0.62rem;
            font-weight: 700;
            letter-spacing: 0.11em;
            text-transform: uppercase;
            padding: 0.20rem 0.12rem 0.34rem 0.12rem;
        }}

        .terminal-row-divider {{
            height: 1px;
            background: var(--line-soft);
            margin: 0.12rem 0 0.18rem 0;
        }}

        .terminal-row-meta {{
            color: var(--muted-2);
            font-size: 0.70rem;
            line-height: 1.35;
            margin: -0.02rem 0 0.30rem 0;
        }}

        .terminal-row-meta strong {{
            color: var(--muted);
            font-weight: 560;
        }}

        @media(max-width: 1180px) {{
            .block-container {{
                max-width: 100%;
                padding-left: 1.2rem;
                padding-right: 1.2rem;
            }}
            .terminal-cell .primary {{
                font-size: 0.78rem;
            }}
            .terminal-cell .secondary {{
                font-size: 0.66rem;
            }}
        }}

        @media(max-width: 980px) {{
            .terminal-header {{
                grid-template-columns: 1fr;
            }}
            .terminal-build {{
                border-left: 0;
                padding-left: 0;
            }}
            .context-strip {{
                grid-template-columns: 1fr 1fr;
            }}
            .stage-row {{
                grid-template-columns: 1fr;
                gap: 0.22rem;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )



def page_header(eyebrow: str, title: str, question: str, build: str):
    st.html(
        (
            '<div class="terminal-header">'
            '<div>'
            f'<div class="terminal-eyebrow">{escape(eyebrow)}</div>'
            f'<h1>{escape(title)}</h1>'
            '</div>'
            f'<div class="terminal-build">{escape(build)}</div>'
            '</div>'
            '<div class="page-question">'
            '<span>Frage</span>'
            f'{escape(question)}'
            '</div>'
        )
    )


def context_strip(items):
    cells = []
    for label, value in items:
        label_e = escape(str(label))
        value_e = escape(str(value))
        cells.append(
            '<div class="context-item">'
            f'<div class="context-label">{label_e}</div>'
            f'<div class="context-value" title="{value_e}">{value_e}</div>'
            '</div>'
        )
    st.html('<div class="context-strip">' + ''.join(cells) + '</div>')


def stage_summary(rows):
    parts = ['<div class="stage-summary">']
    for idx, row in enumerate(rows, start=1):
        tone = row.get("tone", "")
        tone_class = (
            " direction-bull"
            if tone == "bull"
            else " direction-bear"
            if tone == "bear"
            else ""
        )
        parts.extend([
            '<div class="stage-row">',
            '<div>',
            f'<span class="stage-number">Stufe {idx}</span>',
            f'<span class="stage-label">{escape(str(row["label"]))}</span>',
            '</div>',
            f'<div class="stage-primary{tone_class}">{escape(str(row["primary"]))}</div>',
            f'<div class="stage-detail">{escape(str(row["detail"]))}</div>',
            '</div>',
        ])
    parts.append('</div>')
    st.html(''.join(parts))


def section_line(name: str, meta: str = ""):
    st.html(
        '<div class="section-line">'
        f'<div class="name">{escape(name)}</div>'
        f'<div class="meta">{escape(meta)}</div>'
        '</div>'
    )


def definition(text: str):
    st.html(f'<div class="definition">{escape(text)}</div>')


def empty_state(title: str, detail: str):
    st.html(
        '<div class="empty-state">'
        f'<strong>{escape(title)}</strong>'
        f'<span>{escape(detail)}</span>'
        '</div>'
    )


def metric_card(label, value, note=""):
    st.html(
        '<div class="metric">'
        f'<small>{escape(str(label))}</small>'
        f'<div class="value">{escape(str(value))}</div>'
        f'<div class="note">{escape(str(note))}</div>'
        '</div>'
    )


def terminal_cell(primary: str, secondary: str = "", tone: str = ""):
    tone_class = (
        " direction-bull"
        if tone == "bull"
        else " direction-bear"
        if tone == "bear"
        else ""
    )
    secondary_html = (
        f'<div class="secondary">{escape(str(secondary))}</div>'
        if secondary else ""
    )
    st.html(
        '<div class="terminal-cell">'
        f'<div class="primary{tone_class}">{escape(str(primary))}</div>'
        f'{secondary_html}'
        '</div>'
    )


def terminal_table_head(text: str):
    st.html(f'<div class="terminal-table-head">{escape(str(text))}</div>')


def row_divider():
    st.html('<div class="terminal-row-divider"></div>')


def row_meta(text: str):
    st.html(f'<div class="terminal-row-meta">{escape(str(text))}</div>')


# ---------------------------------------------------------------------------
# PLOTLY · TradingView-like interaction
# ---------------------------------------------------------------------------
PLOTLY_CONFIG = {
    "scrollZoom": True,
    "doubleClick": "reset+autosize",
    "displaylogo": False,
    "responsive": True,
    "displayModeBar": "hover",
    "showAxisDragHandles": True,
    "showAxisRangeEntryBoxes": True,
    "modeBarButtonsToRemove": [
        "select2d",
        "lasso2d",
    ],
}


def plotly_config() -> dict:
    """Return a fresh Plotly config for Plotly charts."""
    return dict(PLOTLY_CONFIG)


TRADINGVIEW_Y_SCALE_SENSITIVITY = 1.55
TRADINGVIEW_Y_SCALE_HITBOX_MIN_PX = 44


def _tradingview_y_scale_post_script() -> str:
    """Return browser-side TradingView-like Y-axis scale interaction."""
    return r'''
(function () {
  const gd = document.getElementById('{plot_id}');
  if (!gd || gd.__cotTradingViewYScaleInstalled) return;
  gd.__cotTradingViewYScaleInstalled = true;

  const root = gd.parentElement || document.body;
  root.style.position = 'relative';

  const style = document.createElement('style');
  style.textContent = `
    html, body { margin: 0; padding: 0; overflow: hidden; background: transparent; }
    .cot-tv-y-scale-hitbox {
      position: absolute;
      z-index: 1000;
      cursor: ns-resize;
      background: transparent;
      touch-action: none;
      user-select: none;
      -webkit-user-select: none;
    }
    .cot-tv-y-scale-hitbox.dragging { cursor: ns-resize; }
  `;
  document.head.appendChild(style);

  const hitbox = document.createElement('div');
  hitbox.className = 'cot-tv-y-scale-hitbox';
  hitbox.title = 'Y-Skala ziehen: vertikal strecken / stauchen';
  root.appendChild(hitbox);

  function axisEntries() {
    const fl = gd._fullLayout || {};
    return Object.keys(fl)
      .filter((key) => /^yaxis\d*$/.test(key))
      .map((key) => [key, fl[key]])
      .filter(([, axis]) => axis && axis.visible !== false && axis.fixedrange !== true);
  }

  function rightAxisEntry() {
    const entries = axisEntries();
    const right = entries.filter(([, axis]) => axis.side === 'right');
    if (right.length) {
      right.sort((a, b) => Number(a[1].position || 1) - Number(b[1].position || 1));
      return right[right.length - 1];
    }
    return entries.length ? entries[0] : null;
  }

  function updateHitbox() {
    const fl = gd._fullLayout;
    const entry = rightAxisEntry();
    if (!fl || !fl._size || !entry) {
      hitbox.style.display = 'none';
      return;
    }

    const size = fl._size;
    const rect = gd.getBoundingClientRect();
    const axis = entry[1];
    const side = axis.side || 'left';
    const minWidth = 44;

    hitbox.style.display = 'block';
    hitbox.style.top = `${Math.max(0, size.t)}px`;
    hitbox.style.height = `${Math.max(1, size.h)}px`;

    if (side === 'right') {
      const axisX = size.l + size.w;
      const available = Math.max(minWidth, rect.width - axisX);
      hitbox.style.left = `${Math.max(0, axisX)}px`;
      hitbox.style.width = `${available}px`;
      hitbox.style.right = 'auto';
    } else {
      const available = Math.max(minWidth, size.l);
      hitbox.style.left = '0px';
      hitbox.style.width = `${available}px`;
      hitbox.style.right = 'auto';
    }
  }

  let drag = null;
  let pendingClientY = null;
  let animationFrame = null;

  function applyScale() {
    animationFrame = null;
    if (!drag || pendingClientY === null) return;

    const dy = pendingClientY - drag.startY;
    const factor = Math.exp(
      (dy / Math.max(80, drag.plotHeight)) * 1.55
    );
    const half = Math.max(Number.EPSILON, drag.halfSpan * factor);
    let range;

    if (drag.reversed) {
      range = [drag.center + half, drag.center - half];
    } else {
      range = [drag.center - half, drag.center + half];
    }

    const update = {};
    update[`${drag.axisKey}.range`] = range;
    update[`${drag.axisKey}.autorange`] = false;

    // Only the Y-axis display range is changed. X range and source data stay untouched.
    Plotly.relayout(gd, update);
  }

  hitbox.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;

    const entry = rightAxisEntry();
    if (!entry) return;

    const [axisKey, axis] = entry;
    const range = Array.isArray(axis.range) ? axis.range.map(Number) : null;
    if (!range || range.length !== 2 || !range.every(Number.isFinite)) return;

    const start = range[0];
    const end = range[1];
    const span = Math.abs(end - start);
    if (!Number.isFinite(span) || span <= 0) return;

    drag = {
      pointerId: event.pointerId,
      axisKey,
      startY: event.clientY,
      center: (start + end) / 2,
      halfSpan: span / 2,
      reversed: end < start,
      plotHeight: Math.max(
        1,
        Number(axis._length || (gd._fullLayout._size || {}).h || 1)
      ),
    };

    pendingClientY = event.clientY;
    hitbox.classList.add('dragging');
    hitbox.setPointerCapture(event.pointerId);
    event.preventDefault();
    event.stopPropagation();
  });

  hitbox.addEventListener('pointermove', (event) => {
    if (!drag || event.pointerId !== drag.pointerId) return;
    pendingClientY = event.clientY;
    if (animationFrame === null) {
      animationFrame = requestAnimationFrame(applyScale);
    }
    event.preventDefault();
    event.stopPropagation();
  });

  function finishDrag(event) {
    if (!drag || (event && event.pointerId !== drag.pointerId)) return;
    if (animationFrame !== null) {
      cancelAnimationFrame(animationFrame);
      animationFrame = null;
      applyScale();
    }
    try {
      if (event && hitbox.hasPointerCapture(event.pointerId)) {
        hitbox.releasePointerCapture(event.pointerId);
      }
    } catch (_) {}
    drag = null;
    pendingClientY = null;
    hitbox.classList.remove('dragging');
  }

  hitbox.addEventListener('pointerup', finishDrag);
  hitbox.addEventListener('pointercancel', finishDrag);

  // Double-click on the price scale restores only that Y-axis to autorange.
  hitbox.addEventListener('dblclick', (event) => {
    const entry = rightAxisEntry();
    if (!entry) return;
    const update = {};
    update[`${entry[0]}.autorange`] = true;
    Plotly.relayout(gd, update);
    event.preventDefault();
    event.stopPropagation();
  });

  gd.on('plotly_relayout', updateHitbox);
  gd.on('plotly_afterplot', updateHitbox);

  if (window.ResizeObserver) {
    const observer = new ResizeObserver(updateHitbox);
    observer.observe(gd);
    gd.__cotTradingViewYScaleObserver = observer;
  } else {
    window.addEventListener('resize', updateHitbox);
  }

  updateHitbox();
})();
'''


def tradingview_plotly_chart(
    fig,
    *,
    config: dict | None = None,
    height: int | None = None,
) -> None:
    """Render Plotly with centered TradingView-like right-axis scaling.

    Vertical dragging on the right-hand Y scale changes only its visible range.
    The range midpoint remains fixed and an exponential drag mapping keeps the
    interaction smooth. Trace data and the X-axis are not modified.
    """
    # Apply the semantic palette here as well, so callers get consistent
    # participant colors even if they use the renderer without first calling
    # ``tradingview_chart``.
    _apply_semantic_chart_colors(fig)
    fig.update_layout(colorway=CHART_COLORWAY)

    merged_config = plotly_config()
    if config:
        merged_config.update(config)

    chart_height = int(height or fig.layout.height or 450)
    div_id = f"cot-tv-{uuid.uuid4().hex}"
    html = pio.to_html(
        fig,
        config=merged_config,
        include_plotlyjs="cdn",
        full_html=False,
        default_width="100%",
        default_height=f"{chart_height}px",
        div_id=div_id,
        post_script=_tradingview_y_scale_post_script(),
    )

    components.html(
        html,
        height=chart_height + 6,
        scrolling=False,
    )


def _semantic_chart_color(trace_name: str | None) -> str | None:
    """Return a stable semantic color from a Plotly trace name.

    Non-Commercial is checked before Commercial because the former contains
    the latter as a substring. Unknown traces fall back to Plotly's central
    high-contrast colorway.
    """
    name = str(trace_name or "").casefold()
    if not name:
        return None

    if "non-commercial" in name or "noncommercial" in name:
        return CHART_COLORS["noncommercial"]
    if "commercial" in name:
        return CHART_COLORS["commercial"]
    if "retail" in name or "nonreportable" in name or "non-reportable" in name:
        return CHART_COLORS["retail"]
    if any(token in name for token in ("managed money", "leveraged funds", "spec ", "spec-", "spekul")):
        return CHART_COLORS["speculative"]
    if "netto-hoch" in name or "range high" in name:
        return CHART_COLORS["range_high"]
    if "netto-tief" in name or "range low" in name:
        return CHART_COLORS["range_low"]
    if "preis" in name or "price" in name:
        return CHART_COLORS["price"]
    return None


def _apply_semantic_chart_colors(fig):
    """Apply participant colors without touching trace data or geometry."""
    for trace in fig.data:
        color = _semantic_chart_color(getattr(trace, "name", None))
        if color is None:
            continue

        # Scatter/line-like traces. Keep width, dash and all other styling.
        if hasattr(trace, "line"):
            try:
                trace.line.color = color
            except Exception:
                pass

        # Histogram/bar/marker-like traces.
        if hasattr(trace, "marker"):
            try:
                trace.marker.color = color
            except Exception:
                pass

    return fig


def tradingview_chart(
    fig,
    *,
    x_values=None,
    default_years: int | None = None,
    reset_y_range=None,
    date_axis: bool = False,
    uirevision: str | None = None,
):
    """
    Apply TradingView-like interaction without changing any underlying data.

    - default drag = pan
    - mouse wheel = zoom
    - unified x-hover + cursor spike
    - axis grids are deliberately quiet
    - date charts can expose 1J / 3J / 5J / MAX
    - both axes remain user-zoomable
    - single Y axes live on the right for TradingView-like scale dragging
    """
    _apply_semantic_chart_colors(fig)

    fig.update_layout(
        colorway=CHART_COLORWAY,
        dragmode="pan",
        hovermode="x unified",
        hoverdistance=120,
        spikedistance=-1,
        uirevision=uirevision or "cot-research-chart",
        paper_bgcolor=COLORS["bg"],
        plot_bgcolor=COLORS["surface_deep"],
        font=dict(
            color=COLORS["text"],
            size=12,
        ),
        hoverlabel=dict(
            bgcolor=COLORS["surface_alt"],
            bordercolor=COLORS["line"],
            font=dict(color=COLORS["text"], size=12),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text"]),
        ),
    )

    fig.update_xaxes(
        fixedrange=False,
        showgrid=True,
        gridcolor=COLORS["line_soft"],
        gridwidth=1,
        zeroline=False,
        showline=True,
        linecolor=COLORS["line"],
        tickfont=dict(color=COLORS["muted"]),
        showspikes=True,
        spikecolor=COLORS["muted_2"],
        spikethickness=1,
        spikemode="across",
        spikesnap="cursor",
    )
    fig.update_yaxes(
        fixedrange=False,
        showgrid=True,
        gridcolor=COLORS["line_soft"],
        gridwidth=1,
        zeroline=False,
        showline=True,
        linecolor=COLORS["line"],
        tickfont=dict(color=COLORS["muted"]),
        showspikes=True,
        spikecolor=COLORS["muted_2"],
        spikethickness=1,
        spikemode="across",
        spikesnap="cursor",
    )

    # Single-axis charts use a TradingView-like right-hand value scale.
    # Explicit dual-axis charts keep their own left/right configuration.
    if "yaxis2" not in fig.layout.to_plotly_json():
        fig.update_yaxes(side="right")

    if reset_y_range is not None:
        fig.update_yaxes(range=list(reset_y_range))

    if date_axis:
        fig.update_xaxes(
            type="date",
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1J", step="year", stepmode="backward"),
                    dict(count=3, label="3J", step="year", stepmode="backward"),
                    dict(count=5, label="5J", step="year", stepmode="backward"),
                    dict(step="all", label="MAX"),
                ],
                x=1,
                xanchor="right",
                y=1.055,
                yanchor="bottom",
                bgcolor=COLORS["surface_alt"],
                activecolor=COLORS["accent"],
                bordercolor=COLORS["line"],
                borderwidth=1,
                font=dict(color=COLORS["text"], size=10),
            ),
        )

        if x_values is not None and default_years:
            values = pd.to_datetime(pd.Series(x_values), errors="coerce").dropna()
            if not values.empty:
                end = values.max()
                start = max(
                    values.min(),
                    end - pd.DateOffset(years=int(default_years)),
                )
                fig.update_xaxes(range=[start, end])

    return fig
