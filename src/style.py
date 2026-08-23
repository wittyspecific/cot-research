from __future__ import annotations

from html import escape
import uuid

import pandas as pd
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components


# ---------------------------------------------------------------------------
# V3.9.0 UI TOKENS · minimalist research / trading workspace
# ---------------------------------------------------------------------------
COLORS = {
    "bg": "#F6F8FB",
    "surface": "#FFFFFF",
    "surface_alt": "#F9FAFB",
    "surface_deep": "#F3F6FA",
    "line": "#E4E9F0",
    "line_soft": "#EEF1F5",
    "text": "#111827",
    "muted": "#6B7280",
    "muted_2": "#9CA3AF",
    "accent": "#16A34A",
    "accent_soft": "#ECFDF3",
    "bull": "#16A34A",
    "bear": "#DC2626",
    "warn": "#D97706",
    "info": "#2563EB",
}

CHART_COLORS = {
    "commercial": "#16A34A",
    "noncommercial": "#2563EB",
    "retail": "#F59E0B",
    "speculative": "#7C3AED",
    "price": "#111827",
    "range_high": "#22C55E",
    "range_low": "#EF4444",
    "reference": "#94A3B8",
}

CHART_COLORWAY = [
    CHART_COLORS["commercial"],
    CHART_COLORS["noncommercial"],
    CHART_COLORS["retail"],
    CHART_COLORS["speculative"],
    "#0891B2",
    "#DB2777",
    "#4F46E5",
    "#65A30D",
]

SPACING = {
    "page_top": "1.55rem",
    "page_bottom": "4rem",
    "section": "1.55rem",
}

TYPE = {
    "body": "0.91rem",
    "body_small": "0.78rem",
    "metric": "1.45rem",
    "title": "2.0rem",
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
        "--accent-soft": COLORS["accent_soft"],
        "--bull": COLORS["bull"],
        "--bear": COLORS["bear"],
        "--warn": COLORS["warn"],
        "--info": COLORS["info"],
        "--font-body": TYPE["body"],
        "--font-small": TYPE["body_small"],
        "--font-metric": TYPE["metric"],
        "--font-title": TYPE["title"],
    }
    return "\n".join(f"{key}:{value};" for key, value in tokens.items())


def apply_style():
    st.markdown(
        f"""
        <style>
        :root {{ {_css_vars()} }}

        html, body, [class*="css"] {{
            font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
            font-variant-numeric: tabular-nums lining-nums;
        }}

        .stApp {{ background: var(--bg); color: var(--text); }}
        .block-container {{ max-width: 1480px; padding-top: 1.55rem; padding-bottom: 4rem; }}

        [data-testid="stSidebar"] {{
            background: #FFFFFF;
            border-right: 1px solid var(--line);
            min-width: 232px;
        }}
        [data-testid="stSidebar"] > div:first-child {{ padding-top: .75rem; }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label {{ color: var(--muted) !important; }}
        [data-testid="stSidebarNav"] span {{ font-size: .88rem !important; font-weight: 520; }}
        [data-testid="stSidebarNav"] a {{ border-radius: 9px !important; margin: 2px 8px !important; }}
        [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background: var(--accent-soft) !important;
            color: var(--accent) !important;
            font-weight: 650 !important;
        }}

        h1 {{
            color: var(--text) !important;
            font-size: var(--font-title) !important;
            line-height: 1.15 !important;
            font-weight: 700 !important;
            letter-spacing: -0.035em !important;
            margin: 0 !important;
        }}
        h2, h3, h4 {{ color: var(--text) !important; text-transform: none !important; letter-spacing: -0.012em !important; }}
        h2 {{ font-size: 1.18rem !important; font-weight: 680 !important; margin-top: 1.45rem !important; }}
        h3 {{ font-size: 1.02rem !important; font-weight: 650 !important; }}
        p, li, label {{ font-size: var(--font-body); line-height: 1.5; color: var(--text); }}
        [data-testid="stCaptionContainer"] p {{ color: var(--muted) !important; font-size: var(--font-small) !important; }}
        a {{ color: var(--accent) !important; }}
        hr {{ border-color: var(--line-soft) !important; }}

        [data-testid="stButton"] button,
        [data-testid="stFormSubmitButton"] button,
        [data-testid="stPageLink"] a {{
            border-radius: 9px !important;
            box-shadow: none !important;
            min-height: 2.45rem;
            font-weight: 620 !important;
            font-size: .83rem !important;
        }}
        [data-testid="stButton"] button,
        [data-testid="stPageLink"] a {{
            background: #FFFFFF !important;
            color: var(--text) !important;
            border: 1px solid var(--line) !important;
        }}
        [data-testid="stButton"] button:hover,
        [data-testid="stPageLink"] a:hover {{ border-color: #B7E4C4 !important; color: var(--accent) !important; }}
        [data-testid="stFormSubmitButton"] button[kind="primary"],
        [data-testid="stButton"] button[kind="primary"] {{
            background: var(--accent) !important;
            color: white !important;
            border-color: var(--accent) !important;
        }}

        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        input, textarea {{ border-radius: 9px !important; border-color: var(--line) !important; background: #FFFFFF !important; }}

        [data-testid="stAlert"] {{ border-radius: 10px !important; border: 1px solid var(--line) !important; box-shadow: none !important; }}
        [data-testid="stExpander"] details {{ border: 1px solid var(--line) !important; border-radius: 10px !important; background: #FFFFFF !important; }}

        .terminal-header {{
            display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem;
            padding: .2rem 0 .75rem 0; margin-bottom: .25rem;
        }}
        .terminal-eyebrow {{ color: var(--muted); font-size: .68rem; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; margin-bottom: .28rem; }}
        .terminal-build {{ color: var(--muted-2); font-size: .66rem; white-space: nowrap; }}
        .page-question {{ color: var(--muted); font-size: .88rem; margin-bottom: .95rem; }}
        .page-question span {{ display: none; }}

        .context-strip {{
            display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .75rem;
            margin: .8rem 0 1.15rem 0;
        }}
        .context-item {{ background: #FFFFFF; border: 1px solid var(--line); border-radius: 11px; padding: .85rem .95rem; min-width: 0; }}
        .context-label {{ color: var(--muted); font-size: .67rem; font-weight: 650; margin-bottom: .35rem; }}
        .context-value {{ color: var(--text); font-size: 1.08rem; font-weight: 650; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

        .stage-summary {{
            display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: .75rem; margin: .85rem 0 1.25rem 0;
        }}
        .stage-row {{ background: #FFFFFF; border: 1px solid var(--line); border-radius: 11px; padding: .85rem .9rem; min-height: 132px; }}
        .stage-number {{ color: var(--muted-2); font-size: .62rem; font-weight: 700; text-transform: uppercase; margin-right: .35rem; }}
        .stage-label {{ color: var(--muted); font-size: .67rem; font-weight: 650; }}
        .stage-primary {{ color: var(--text); font-size: 1.02rem; font-weight: 680; margin: .62rem 0 .36rem; }}
        .stage-detail {{ color: var(--muted); font-size: .75rem; line-height: 1.42; }}
        .direction-bull {{ color: var(--bull) !important; }}
        .direction-bear {{ color: var(--bear) !important; }}

        .section-line {{ display:flex; justify-content:space-between; gap:1rem; align-items:baseline; margin:1.55rem 0 .65rem; }}
        .section-line .name {{ color:var(--text); font-size:1rem; font-weight:680; }}
        .section-line .meta {{ color:var(--muted); font-size:.74rem; }}
        .definition {{ color: var(--muted); background:#FFFFFF; border:1px solid var(--line); border-radius:9px; padding:.7rem .8rem; margin:.25rem 0 .75rem; font-size:.78rem; line-height:1.45; }}
        .empty-state {{ background:#FFFFFF; border:1px solid var(--line); border-radius:11px; padding:1.05rem; margin:.5rem 0 1rem; }}
        .empty-state strong {{ display:block; color:var(--text); font-size:.88rem; margin-bottom:.2rem; }}
        .empty-state span {{ color:var(--muted); font-size:.78rem; }}

        .metric {{ background:#FFFFFF; border:1px solid var(--line); border-radius:11px; min-height:108px; padding:.85rem .9rem; }}
        .metric small {{ display:block; color:var(--muted); font-size:.68rem; font-weight:620; margin-bottom:.45rem; }}
        .metric .value {{ color:var(--text); font-size:var(--font-metric); font-weight:720; line-height:1.1; letter-spacing:-.025em; }}
        .metric .note {{ color:var(--muted); font-size:.73rem; margin-top:.38rem; line-height:1.35; }}

        .signalbox {{ background:#FFFFFF; border:1px solid var(--line); border-radius:11px; padding:.85rem; min-height:185px; }}
        .signalbox small {{ color:var(--muted); font-size:.67rem; }}
        .signalbox .signal {{ color:var(--text); font-size:1.2rem; font-weight:700; margin:.42rem 0 .6rem; }}
        .signalbox p {{ color:var(--muted); font-size:.76rem; line-height:1.45; }}

        .terminal-cell {{ min-height:48px; display:flex; flex-direction:column; justify-content:center; }}
        .terminal-cell .primary {{ color:var(--text); font-weight:620; font-size:.84rem; }}
        .terminal-cell .secondary {{ color:var(--muted); font-size:.72rem; margin-top:.12rem; }}
        .terminal-table-head {{ color:var(--muted); font-size:.66rem; font-weight:700; }}
        .terminal-row-divider {{ height:1px; background:var(--line-soft); margin:.12rem 0 .4rem; }}
        .terminal-row-meta {{ color:var(--muted); font-size:.71rem; }}
        .watch-row-note {{ color:var(--muted); font-size:.72rem; }}

        div[data-testid="stDataFrame"], div[data-testid="stPlotlyChart"] {{ background:#FFFFFF !important; border:1px solid var(--line) !important; border-radius:11px !important; overflow:hidden; }}
        div[data-testid="stTabs"] button {{ font-size:.76rem; font-weight:600; color:var(--muted); padding:.45rem .65rem; }}
        div[data-testid="stTabs"] button[aria-selected="true"] {{ color:var(--accent) !important; border-bottom-color:var(--accent) !important; }}

        .cot-brand {{ padding:.35rem .35rem .9rem; border-bottom:1px solid var(--line-soft); margin-bottom:.45rem; }}
        .cot-brand-row {{ display:flex; align-items:center; gap:.6rem; }}
        .cot-logo {{ width:31px; height:31px; border-radius:8px; background:var(--accent); color:#fff; display:flex; align-items:center; justify-content:center; font-size:1.05rem; font-weight:800; }}
        .cot-brand-title {{ color:var(--text); font-size:.9rem; font-weight:760; line-height:1.05; }}
        .cot-brand-sub {{ color:var(--muted); font-size:.65rem; margin-top:.13rem; }}
        .cot-user-card {{ background:var(--surface-alt); border:1px solid var(--line); border-radius:10px; padding:.65rem .7rem; margin:.6rem 0 .5rem; }}
        .cot-user-name {{ color:var(--text); font-size:.82rem; font-weight:650; }}
        .cot-user-meta {{ color:var(--muted); font-size:.67rem; margin-top:.12rem; }}

        @media (max-width: 900px) {{
            .context-strip {{ grid-template-columns:1fr 1fr; }}
            .stage-summary {{ grid-template-columns:1fr; }}
            .terminal-build {{ display:none; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(eyebrow: str, title: str, question: str, build: str):
    st.html(
        '<div class="terminal-header">'
        '<div>'
        f'<div class="terminal-eyebrow">{escape(eyebrow)}</div>'
        f'<h1>{escape(title)}</h1>'
        '</div>'
        f'<div class="terminal-build">{escape(build)}</div>'
        '</div>'
        f'<div class="page-question">{escape(question)}</div>'
    )


def context_strip(items):
    cells=[]
    for label,value in items:
        le,ve=escape(str(label)),escape(str(value))
        cells.append('<div class="context-item">'+f'<div class="context-label">{le}</div><div class="context-value" title="{ve}">{ve}</div></div>')
    st.html('<div class="context-strip">'+''.join(cells)+'</div>')


def stage_summary(rows):
    parts=['<div class="stage-summary">']
    for idx,row in enumerate(rows,start=1):
        tone=row.get('tone','')
        tone_class=' direction-bull' if tone=='bull' else ' direction-bear' if tone=='bear' else ''
        parts.append('<div class="stage-row">')
        parts.append(f'<div><span class="stage-number">Stufe {idx}</span><span class="stage-label">{escape(str(row["label"]))}</span></div>')
        parts.append(f'<div class="stage-primary{tone_class}">{escape(str(row["primary"]))}</div>')
        parts.append(f'<div class="stage-detail">{escape(str(row["detail"]))}</div></div>')
    parts.append('</div>')
    st.html(''.join(parts))


def section_line(name: str, meta: str = ""):
    st.html('<div class="section-line">'+f'<div class="name">{escape(name)}</div><div class="meta">{escape(meta)}</div></div>')


def definition(text: str):
    st.html(f'<div class="definition">{escape(text)}</div>')


def empty_state(title: str, detail: str):
    st.html('<div class="empty-state">'+f'<strong>{escape(title)}</strong><span>{escape(detail)}</span></div>')


def metric_card(label, value, note=""):
    st.html('<div class="metric">'+f'<small>{escape(str(label))}</small><div class="value">{escape(str(value))}</div><div class="note">{escape(str(note))}</div></div>')


def terminal_cell(primary: str, secondary: str = "", tone: str = ""):
    tone_class=' direction-bull' if tone=='bull' else ' direction-bear' if tone=='bear' else ''
    secondary_html=f'<div class="secondary">{escape(str(secondary))}</div>' if secondary else ''
    st.html('<div class="terminal-cell">'+f'<div class="primary{tone_class}">{escape(str(primary))}</div>{secondary_html}</div>')


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

# V3.29.2.1 · WORKSPACE DARK CONSISTENCY
_v32921_base_apply_style = apply_style


def _v32921_workspace_dark_overlay() -> None:
    st.markdown(
        """
        <style>
        :root {
            --qa-bg: #0B0F14;
            --qa-panel: #131B24;
            --qa-panel-2: #18222D;
            --qa-header: #1A2029;
            --qa-border: #29333E;
            --qa-text: #F3F6FB;
            --qa-text-soft: #C3CCD6;
            --qa-muted: #98A4B3;
            --qa-info: #62A6C9;
        }

        /* ---------------------------------------------------------
           Global titles / headings
           --------------------------------------------------------- */
        [data-testid="stAppViewContainer"] h1,
        [data-testid="stAppViewContainer"] h2,
        [data-testid="stAppViewContainer"] h3,
        [data-testid="stAppViewContainer"] h4,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] strong {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
        }

        /* Quant Research / branding */
        [class*="brand"],
        [class*="brand"] *,
        [class*="logo-title"],
        [class*="logo-title"] *,
        [class*="app-title"],
        [class*="app-title"] *,
        [class*="workspace-title"],
        [class*="workspace-title"] * {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
        }

        [class*="brand"] small,
        [class*="brand"] p,
        [class*="subtitle"],
        [class*="subtitle"] * {
            color: var(--qa-muted) !important;
            -webkit-text-fill-color: var(--qa-muted) !important;
        }

        /* ---------------------------------------------------------
           Neutralize legacy inline white cards.
           This catches the old dashboard KPI cards and sidebar user card
           without touching model/data code.
           --------------------------------------------------------- */
        [data-testid="stAppViewContainer"] [style*="background: white"],
        [data-testid="stAppViewContainer"] [style*="background:white"],
        [data-testid="stAppViewContainer"] [style*="background-color: white"],
        [data-testid="stAppViewContainer"] [style*="background-color:white"],
        [data-testid="stAppViewContainer"] [style*="background: #fff"],
        [data-testid="stAppViewContainer"] [style*="background:#fff"],
        [data-testid="stAppViewContainer"] [style*="background: #FFF"],
        [data-testid="stAppViewContainer"] [style*="background:#FFF"],
        [data-testid="stAppViewContainer"] [style*="background: #ffffff"],
        [data-testid="stAppViewContainer"] [style*="background:#ffffff"],
        [data-testid="stAppViewContainer"] [style*="background: #FFFFFF"],
        [data-testid="stAppViewContainer"] [style*="background:#FFFFFF"],
        [data-testid="stSidebar"] [style*="background: white"],
        [data-testid="stSidebar"] [style*="background:white"],
        [data-testid="stSidebar"] [style*="background-color: white"],
        [data-testid="stSidebar"] [style*="background-color:white"],
        [data-testid="stSidebar"] [style*="background: #fff"],
        [data-testid="stSidebar"] [style*="background:#fff"],
        [data-testid="stSidebar"] [style*="background: #ffffff"],
        [data-testid="stSidebar"] [style*="background:#ffffff"],
        [data-testid="stSidebar"] [style*="background: #FFFFFF"],
        [data-testid="stSidebar"] [style*="background:#FFFFFF"] {
            background: var(--qa-panel) !important;
            background-color: var(--qa-panel) !important;
            border-color: var(--qa-border) !important;
            color: var(--qa-text) !important;
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
        [data-testid="stAppViewContainer"] [style*="background:#FFFFFF"] *,
        [data-testid="stSidebar"] [style*="background: white"] *,
        [data-testid="stSidebar"] [style*="background:white"] *,
        [data-testid="stSidebar"] [style*="background-color: white"] *,
        [data-testid="stSidebar"] [style*="background-color:white"] *,
        [data-testid="stSidebar"] [style*="background: #fff"] *,
        [data-testid="stSidebar"] [style*="background:#fff"] *,
        [data-testid="stSidebar"] [style*="background: #ffffff"] *,
        [data-testid="stSidebar"] [style*="background:#ffffff"] *,
        [data-testid="stSidebar"] [style*="background: #FFFFFF"] *,
        [data-testid="stSidebar"] [style*="background:#FFFFFF"] * {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
        }

        /* Common legacy custom card class names */
        .metric-card,
        .kpi-card,
        .dashboard-card,
        .stat-card,
        .summary-card,
        .user-card,
        .admin-card,
        .sidebar-card {
            background: var(--qa-panel) !important;
            border: 1px solid var(--qa-border) !important;
            color: var(--qa-text) !important;
            box-shadow: none !important;
        }

        .metric-card *,
        .kpi-card *,
        .dashboard-card *,
        .stat-card *,
        .summary-card *,
        .user-card *,
        .admin-card *,
        .sidebar-card * {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
        }

        /* Native Streamlit metrics */
        [data-testid="stMetric"] {
            background: var(--qa-panel) !important;
            border: 1px solid var(--qa-border) !important;
            border-radius: 14px !important;
            padding: 0.85rem 1rem !important;
        }

        [data-testid="stMetric"] label,
        [data-testid="stMetric"] [data-testid="stMetricLabel"],
        [data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
        }

        /* ---------------------------------------------------------
           Sidebar user / logout
           --------------------------------------------------------- */
        [data-testid="stSidebar"] [data-testid="stButton"] button,
        [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"],
        [data-testid="stSidebar"] [data-testid="stPageLink"] a {
            background: var(--qa-panel) !important;
            color: var(--qa-text) !important;
            border: 1px solid var(--qa-border) !important;
            box-shadow: none !important;
        }

        [data-testid="stSidebar"] [data-testid="stButton"] button *,
        [data-testid="stSidebar"] [data-testid="stPageLink"] a * {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
        }

        /* ---------------------------------------------------------
           Dashboard quick access
           --------------------------------------------------------- */
        [data-testid="stMainBlockContainer"] [data-testid="stPageLink"] a {
            background: var(--qa-panel) !important;
            color: var(--qa-text) !important;
            border: 1px solid var(--qa-border) !important;
            box-shadow: none !important;
        }

        [data-testid="stMainBlockContainer"] [data-testid="stPageLink"] a:hover {
            background: var(--qa-panel-2) !important;
            border-color: rgba(98, 166, 201, 0.50) !important;
        }

        [data-testid="stMainBlockContainer"] [data-testid="stPageLink"] a * {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
        }

        /* ---------------------------------------------------------
           Login / text inputs
           --------------------------------------------------------- */
        [data-testid="stTextInput"] label,
        [data-testid="stTextInput"] label *,
        [data-testid="stForm"] label,
        [data-testid="stForm"] label * {
            color: var(--qa-text) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
            opacity: 1 !important;
        }

        [data-testid="stTextInput"] div[data-baseweb="input"],
        [data-testid="stTextInput"] div[data-baseweb="base-input"],
        [data-testid="stTextInput"] input {
            background: #111923 !important;
            background-color: #111923 !important;
            color: var(--qa-text) !important;
            border-color: var(--qa-border) !important;
            -webkit-text-fill-color: var(--qa-text) !important;
            caret-color: var(--qa-text) !important;
        }

        [data-testid="stTextInput"] input::placeholder {
            color: #7F8A99 !important;
            -webkit-text-fill-color: #7F8A99 !important;
            opacity: 1 !important;
        }

        [data-testid="stTextInput"] svg {
            color: var(--qa-text-soft) !important;
            fill: var(--qa-text-soft) !important;
        }

        /* Login form border / body */
        [data-testid="stForm"] {
            background: transparent !important;
            border-color: #394553 !important;
        }

        /*
        Keep primary actions such as "Anmelden" visually prominent.
        Secondary actions stay dark.
        */
        [data-testid="stForm"] [data-testid="stBaseButton-primary"] {
            background: var(--qa-info) !important;
            color: #081018 !important;
            border-color: var(--qa-info) !important;
        }

        [data-testid="stForm"] [data-testid="stBaseButton-primary"] * {
            color: #081018 !important;
            -webkit-text-fill-color: #081018 !important;
        }

        /* Secondary descriptive text */
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] *,
        small {
            color: var(--qa-muted) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_style() -> None:
    _v32921_base_apply_style()
    _v32921_workspace_dark_overlay()
# ---------------------------------------------------------------------------
# V3.29.4 · LEGACY WATCHLIST DARK OVERRIDE
# UI-only. The original watchlist mechanics and trading engines stay untouched.
# ---------------------------------------------------------------------------

_v32940_base_apply_style = apply_style


def _v32940_watchlist_dark_overlay() -> None:
    st.markdown(
        """
        <style>
        /* -------- Legacy Watchlist custom HTML -------- */
        .sw-wrap {
            color: #EDF2F7 !important;
        }

        .sw-title,
        .sw-card-value,
        .sw-market-name,
        .sw-bias,
        .sw-plan {
            color: #EDF2F7 !important;
            -webkit-text-fill-color: #EDF2F7 !important;
        }

        .sw-kicker,
        .sw-subtitle,
        .sw-card-label,
        .sw-legend-item,
        .sw-market-code {
            color: #929EAD !important;
            -webkit-text-fill-color: #929EAD !important;
        }

        .sw-card,
        .sw-legend,
        .sw-table {
            background: #0F151C !important;
            background-color: #0F151C !important;
            border-color: #29333E !important;
            box-shadow: none !important;
        }

        .sw-header {
            background: #1A2029 !important;
            background-color: #1A2029 !important;
            color: #AEB8C4 !important;
            -webkit-text-fill-color: #AEB8C4 !important;
            border-bottom-color: #33404D !important;
        }

        .sw-row {
            background: #0B0F14 !important;
            background-color: #0B0F14 !important;
            border-top-color: #202A34 !important;
        }

        .sw-row:hover {
            background: #111923 !important;
            background-color: #111923 !important;
        }

        .sw-market,
        .sw-market > div {
            background: transparent !important;
            background-color: transparent !important;
        }

        .sw-market-icon {
            background: #131B24 !important;
            background-color: #131B24 !important;
            color: #EDF2F7 !important;
        }

        /* Direction remains visible through restrained accent chips. */
        .sw-chip.macro-bull {
            background: rgba(34,197,94,.12) !important;
            color: #86EFAC !important;
        }

        .sw-chip.macro-bear {
            background: rgba(239,68,68,.12) !important;
            color: #FCA5A5 !important;
        }

        .sw-chip.macro-neutral {
            background: #18222D !important;
            color: #AEB8C4 !important;
        }

        .sw-chip.micro-bull {
            background: rgba(98,166,201,.14) !important;
            color: #93C5FD !important;
        }

        .sw-chip.micro-bear {
            background: rgba(239,68,68,.10) !important;
            color: #FCA5A5 !important;
        }

        .sw-chip.micro-neutral {
            background: #18222D !important;
            color: #AEB8C4 !important;
        }

        .sw-signal.signal-aligned {
            background: rgba(34,197,94,.12) !important;
            color: #86EFAC !important;
            border-color: rgba(34,197,94,.24) !important;
        }

        .sw-signal.signal-watch {
            background: rgba(245,158,11,.12) !important;
            color: #FBBF24 !important;
            border-color: rgba(245,158,11,.24) !important;
        }

        .sw-signal.signal-neutral {
            background: #18222D !important;
            color: #AEB8C4 !important;
            border-color: #29333E !important;
        }

        .sw-signal.signal-ready {
            background: rgba(168,85,247,.12) !important;
            color: #D8B4FE !important;
            border-color: rgba(168,85,247,.24) !important;
        }

        /* -------- Native Watchlist/filter controls -------- */
        [data-testid="stMainBlockContainer"] [data-testid="stBaseButton-secondary"],
        [data-testid="stMainBlockContainer"] [data-testid="stPageLink"] a {
            background: #131B24 !important;
            background-color: #131B24 !important;
            color: #EDF2F7 !important;
            border-color: #29333E !important;
            box-shadow: none !important;
        }

        [data-testid="stMainBlockContainer"] [data-testid="stBaseButton-secondary"] *,
        [data-testid="stMainBlockContainer"] [data-testid="stPageLink"] a * {
            color: #EDF2F7 !important;
            -webkit-text-fill-color: #EDF2F7 !important;
        }

        [data-testid="stMainBlockContainer"] [data-testid="stBaseButton-secondary"]:hover,
        [data-testid="stMainBlockContainer"] [data-testid="stPageLink"] a:hover {
            background: #18222D !important;
            background-color: #18222D !important;
            border-color: rgba(98,166,201,.55) !important;
        }

        [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
        [data-testid="stMainBlockContainer"] div[data-baseweb="select"] > div {
            background: #131B24 !important;
            background-color: #131B24 !important;
            color: #EDF2F7 !important;
            border-color: #29333E !important;
        }

        [data-testid="stSelectbox"] div[data-baseweb="select"] *,
        [data-testid="stMultiSelect"] div[data-baseweb="select"] *,
        [data-testid="stMainBlockContainer"] div[data-baseweb="select"] * {
            color: #EDF2F7 !important;
            -webkit-text-fill-color: #EDF2F7 !important;
        }

        [data-testid="stMultiSelect"] [data-baseweb="tag"] {
            background: #1A2632 !important;
            color: #EDF2F7 !important;
            border-color: #33404D !important;
        }

        div[data-baseweb="popover"],
        div[data-baseweb="menu"],
        ul[role="listbox"] {
            background: #131B24 !important;
            background-color: #131B24 !important;
            color: #EDF2F7 !important;
        }

        div[data-baseweb="popover"] li,
        div[data-baseweb="menu"] li,
        ul[role="listbox"] li,
        [role="option"] {
            background: #131B24 !important;
            background-color: #131B24 !important;
            color: #EDF2F7 !important;
            -webkit-text-fill-color: #EDF2F7 !important;
        }

        div[data-baseweb="popover"] li:hover,
        div[data-baseweb="menu"] li:hover,
        [role="option"]:hover,
        [role="option"][aria-selected="true"] {
            background: #1A2632 !important;
            background-color: #1A2632 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_style() -> None:
    _v32940_base_apply_style()
    _v32940_watchlist_dark_overlay()
