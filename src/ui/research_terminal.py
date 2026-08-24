from __future__ import annotations

from html import escape
from textwrap import dedent
from typing import Any, Iterable

import streamlit as st

from src.ui.hedgefund import TOKENS, apply_hedgefund_theme


# V3.30.4 · MOCKUP LAYOUT + HTML RENDER FIX


def _html(body: str) -> None:
    """Render raw HTML without Markdown turning indented tags into code blocks."""
    cleaned = dedent(str(body)).strip()

    if hasattr(st, "html"):
        st.html(cleaned)
    else:
        st.markdown(
            cleaned,
            unsafe_allow_html=True,
        )


def _tone(value: Any) -> str:
    text = str(value or "").upper()

    if any(x in text for x in (
        "BULL",
        "LONG",
        "BESTÄTIG",
        "CONFIRM",
        "FAVOR",
        "POSITIVE",
        "EXPANSION",
        "RECOVERY",
        "ALIGNED",
    )):
        return TOKENS["green"]

    if any(x in text for x in (
        "BEAR",
        "SHORT",
        "WIDERSPRICHT",
        "CONFLICT",
        "NEGATIVE",
        "CONTRACTION",
        "AVOID",
    )):
        return TOKENS["red"]

    if any(x in text for x in (
        "WATCH",
        "WARNING",
        "LATE",
        "SLOWDOWN",
    )):
        return TOKENS["amber"]

    if any(x in text for x in (
        "TRANSITION",
        "EARLY",
    )):
        return TOKENS["blue_soft"]

    return TOKENS["blue"]


def apply_terminal_theme() -> None:
    apply_hedgefund_theme()

    _html(
        """
        <style>
        .rt-shell {
            margin: 0 0 .85rem 0;
        }

        .rt-topline {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: .34rem;
        }

        .rt-kicker {
            color: #62A6C9;
            font-size: .66rem;
            font-weight: 850;
            letter-spacing: .16em;
            text-transform: uppercase;
        }

        .rt-version {
            color: #708090;
            font-size: .66rem;
            font-weight: 700;
            letter-spacing: .04em;
        }

        .rt-title {
            color: #F3F6FB;
            font-size: 1.86rem;
            font-weight: 790;
            line-height: 1.04;
            letter-spacing: -.034em;
            margin: 0;
        }

        .rt-subtitle {
            color: #8E9BAA;
            font-size: .84rem;
            line-height: 1.5;
            max-width: 980px;
            margin-top: .42rem;
        }

        .rt-rule {
            height: 1px;
            background: #1A2835;
            margin-top: .82rem;
        }

        .rt-section {
            margin: .78rem 0 .5rem 0;
        }

        .rt-section-title {
            color: #F3F6FB;
            font-size: .78rem;
            font-weight: 820;
            letter-spacing: .07em;
            text-transform: uppercase;
        }

        .rt-section-sub {
            color: #7F8C9C;
            font-size: .72rem;
            line-height: 1.4;
            margin-top: .16rem;
        }

        .rt-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
            gap: .62rem;
            margin: .62rem 0 .82rem 0;
        }

        .rt-stat {
            position: relative;
            min-height: 90px;
            padding: .74rem .82rem;
            background:
                radial-gradient(
                    circle at 100% 0%,
                    rgba(98,166,201,.045),
                    transparent 42%
                ),
                linear-gradient(
                    180deg,
                    #101B27 0%,
                    #0C1620 100%
                );
            border: 1px solid #22303D;
            border-radius: 8px;
            overflow: hidden;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,.018);
        }

        .rt-stat:before {
            content: "";
            position: absolute;
            left: 0;
            right: 0;
            top: 0;
            height: 2px;
            background: var(--rt-accent,#62A6C9);
            opacity: .86;
        }

        .rt-stat-label {
            color: #8391A1;
            font-size: .60rem;
            font-weight: 820;
            letter-spacing: .10em;
            text-transform: uppercase;
        }

        .rt-stat-value {
            color: var(--rt-accent,#F3F6FB);
            font-size: 1.04rem;
            font-weight: 790;
            line-height: 1.15;
            margin-top: .38rem;
        }

        .rt-stat-note {
            color: #798797;
            font-size: .66rem;
            line-height: 1.33;
            margin-top: .32rem;
        }

        /* ---------------------------------------------------------
           Market Analysis hero — based on the approved mockup
           --------------------------------------------------------- */
        .rt-hero,
        .rt-thesis-hero {
            display: grid;
            grid-template-columns: 1.35fr repeat(5, 1fr);
            gap: 0;
            margin: .72rem 0 .86rem 0;
            background:
                radial-gradient(
                    circle at 10% 15%,
                    rgba(98,166,201,.11),
                    transparent 30%
                ),
                linear-gradient(
                    110deg,
                    #101D29 0%,
                    #0D1823 45%,
                    #0A141E 100%
                );
            border: 1px solid #263C4E;
            border-radius: 10px;
            overflow: hidden;
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,.02),
                0 14px 34px rgba(0,0,0,.14);
        }

        .rt-thesis-market {
            padding: 1rem 1rem .95rem 1rem;
            min-height: 138px;
        }

        .rt-thesis-market-label {
            color: #62A6C9;
            font-size: .61rem;
            font-weight: 850;
            letter-spacing: .13em;
            text-transform: uppercase;
        }

        .rt-thesis-market-name {
            color: #F3F6FB;
            font-size: 1.65rem;
            font-weight: 820;
            line-height: 1;
            letter-spacing: -.035em;
            margin-top: .42rem;
        }

        .rt-thesis-market-sub {
            color: #8F9CAA;
            font-size: .71rem;
            line-height: 1.42;
            margin-top: .5rem;
        }

        .rt-thesis-cell {
            padding: 1rem .9rem .9rem .9rem;
            border-left: 1px solid #1E2D39;
            min-height: 138px;
        }

        .rt-thesis-label {
            color: #8391A1;
            font-size: .58rem;
            font-weight: 840;
            letter-spacing: .095em;
            text-transform: uppercase;
        }

        .rt-thesis-value {
            color: var(--rt-accent,#F3F6FB);
            font-size: .92rem;
            font-weight: 800;
            line-height: 1.22;
            margin-top: .48rem;
        }

        .rt-thesis-note {
            color: #72808F;
            font-size: .64rem;
            line-height: 1.38;
            margin-top: .46rem;
        }

        .rt-thesis-summary {
            grid-column: 1 / -1;
            color: #AEB9C4;
            font-size: .73rem;
            line-height: 1.48;
            padding: .68rem 1rem .76rem 1rem;
            border-top: 1px solid #1E2D39;
            background: rgba(6,13,20,.28);
        }

        /* ---------------------------------------------------------
           Context / insight panels
           --------------------------------------------------------- */
        .rt-panel {
            background:
                linear-gradient(
                    180deg,
                    rgba(15,26,37,.97),
                    rgba(11,20,29,.97)
                );
            border: 1px solid #22303D;
            border-radius: 9px;
            padding: .82rem .9rem;
        }

        .rt-panel-title {
            color: #F3F6FB;
            font-size: .71rem;
            font-weight: 820;
            letter-spacing: .07em;
            text-transform: uppercase;
            margin-bottom: .46rem;
        }

        .rt-insight {
            display: flex;
            gap: .55rem;
            align-items: flex-start;
            padding: .55rem .58rem;
            border: 1px solid #1C2B37;
            border-radius: 7px;
            background: #0D1722;
            margin-top: .42rem;
        }

        .rt-insight-dot {
            color: var(--rt-accent,#62A6C9);
            font-size: .76rem;
            line-height: 1.25rem;
        }

        .rt-insight-title {
            color: #D9E1E9;
            font-size: .65rem;
            font-weight: 800;
            letter-spacing: .05em;
            text-transform: uppercase;
        }

        .rt-insight-text {
            color: #8593A3;
            font-size: .66rem;
            line-height: 1.38;
            margin-top: .14rem;
        }

        .rt-evidence-grid {
            display: grid;
            grid-template-columns: repeat(2,minmax(0,1fr));
            gap: .62rem;
            margin: .6rem 0 .8rem 0;
        }

        .rt-evidence-item {
            color: #AEB9C4;
            font-size: .72rem;
            line-height: 1.4;
            padding: .20rem 0;
        }

        .rt-evidence-item.good:before {
            content: "●";
            color: #65D98B;
            font-size: .52rem;
            margin-right: .42rem;
        }

        .rt-evidence-item.bad:before {
            content: "●";
            color: #FF7373;
            font-size: .52rem;
            margin-right: .42rem;
        }

        .rt-regime-path {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: .38rem;
            margin: .68rem 0 .82rem 0;
            padding: .68rem;
            background: #0A141D;
            border: 1px solid #22303D;
            border-radius: 8px;
        }

        .rt-node {
            text-align: center;
            padding: .54rem .3rem;
            color: #73808F;
            font-size: .63rem;
            font-weight: 780;
            letter-spacing: .04em;
            text-transform: uppercase;
            border: 1px solid #1C2A36;
            border-radius: 6px;
            background: #0D1722;
        }

        .rt-node.active {
            color: #F3F6FB;
            border-color: #4D849F;
            background:
                linear-gradient(
                    180deg,
                    rgba(98,166,201,.15),
                    rgba(13,23,34,.96)
                );
            box-shadow: inset 0 2px 0 #62A6C9;
        }

        @media (max-width: 1100px) {
            .rt-thesis-hero {
                grid-template-columns: repeat(3,1fr);
            }

            .rt-thesis-market {
                grid-column: span 3;
            }

            .rt-thesis-cell {
                border-top: 1px solid #1E2D39;
            }
        }

        @media (max-width: 760px) {
            .rt-thesis-hero {
                grid-template-columns: 1fr;
            }

            .rt-thesis-market {
                grid-column: auto;
            }

            .rt-thesis-cell {
                border-left: 0;
                border-top: 1px solid #1E2D39;
            }

            .rt-evidence-grid {
                grid-template-columns: 1fr;
            }

            .rt-regime-path {
                grid-template-columns: repeat(2,1fr);
            }
        }
        </style>
        """
    )


def header(
    kicker: str,
    title: str,
    subtitle: str,
    version: str = "V3.30.4",
) -> None:
    _html(
        f"""
        <div class="rt-shell">
          <div class="rt-topline">
            <div class="rt-kicker">{escape(kicker)}</div>
            <div class="rt-version">{escape(version)}</div>
          </div>
          <div class="rt-title">{escape(title)}</div>
          <div class="rt-subtitle">{escape(subtitle)}</div>
          <div class="rt-rule"></div>
        </div>
        """
    )


def section(
    title: str,
    subtitle: str = "",
) -> None:
    _html(
        f"""
        <div class="rt-section">
          <div class="rt-section-title">{escape(title)}</div>
          <div class="rt-section-sub">{escape(subtitle)}</div>
        </div>
        """
    )


def stat_grid(
    items: Iterable[tuple[str, Any, str]],
) -> None:
    cards = []

    for label, value, note in items:
        accent = _tone(value)
        display = "—" if value in (None, "") else str(value)

        cards.append(
            (
                f'<div class="rt-stat" style="--rt-accent:{accent}">'
                f'<div class="rt-stat-label">{escape(str(label))}</div>'
                f'<div class="rt-stat-value">{escape(display)}</div>'
                f'<div class="rt-stat-note">{escape(str(note or ""))}</div>'
                '</div>'
            )
        )

    _html(
        '<div class="rt-grid">'
        + "".join(cards)
        + "</div>"
    )


def thesis_hero(
    market: str,
    *,
    structural_bias: Any,
    setup_state: Any,
    conviction: Any,
    setup_type: Any,
    action: Any,
    thesis: str,
    market_note: str = "",
    setup_note: str = "",
) -> None:
    fields = [
        (
            "Struktureller Bias",
            structural_bias,
            "Positionierungs-Regime",
        ),
        (
            "Setup-Status",
            setup_state,
            setup_note,
        ),
        (
            "Conviction",
            conviction,
            "Research-Konfluenz",
        ),
        (
            "Setup-Typ",
            setup_type,
            "Trade-Kategorie",
        ),
        (
            "Bevorzugte Aktion",
            action,
            "Entry bleibt technischer Layer",
        ),
    ]

    cells = []

    for label, value, note in fields:
        accent = _tone(value)

        cells.append(
            (
                f'<div class="rt-thesis-cell" style="--rt-accent:{accent}">'
                f'<div class="rt-thesis-label">{escape(str(label))}</div>'
                f'<div class="rt-thesis-value">{escape(str(value or "—"))}</div>'
                f'<div class="rt-thesis-note">{escape(str(note or ""))}</div>'
                '</div>'
            )
        )

    _html(
        (
            '<div class="rt-hero rt-thesis-hero">'
            '<div class="rt-thesis-market">'
            '<div class="rt-thesis-market-label">Trade Thesis</div>'
            f'<div class="rt-thesis-market-name">{escape(str(market))}</div>'
            f'<div class="rt-thesis-market-sub">{escape(str(market_note or ""))}</div>'
            '</div>'
            + "".join(cells)
            + f'<div class="rt-thesis-summary">{escape(str(thesis or ""))}</div>'
            + '</div>'
        )
    )


def evidence_panels(
    supports: Iterable[str],
    conflicts: Iterable[str],
) -> None:
    support_items = list(supports or [])
    conflict_items = list(conflicts or [])

    if not support_items:
        support_items = ["Noch keine starke Bestätigung."]

    if not conflict_items:
        conflict_items = ["Kein zentraler Konflikt erkannt."]

    support_html = "".join(
        f'<div class="rt-evidence-item good">{escape(str(x))}</div>'
        for x in support_items
    )

    conflict_html = "".join(
        f'<div class="rt-evidence-item bad">{escape(str(x))}</div>'
        for x in conflict_items
    )

    _html(
        (
            '<div class="rt-evidence-grid">'
            '<div class="rt-panel">'
            '<div class="rt-panel-title">Unterstützt</div>'
            f'{support_html}'
            '</div>'
            '<div class="rt-panel">'
            '<div class="rt-panel-title">Konflikte</div>'
            f'{conflict_html}'
            '</div>'
            '</div>'
        )
    )


def insights(
    items: Iterable[tuple[str, str, Any]],
) -> None:
    rows = []

    for title, text, tone_value in items:
        accent = _tone(tone_value)

        rows.append(
            (
                f'<div class="rt-insight" style="--rt-accent:{accent}">'
                '<div class="rt-insight-dot">◆</div>'
                '<div>'
                f'<div class="rt-insight-title">{escape(str(title))}</div>'
                f'<div class="rt-insight-text">{escape(str(text))}</div>'
                '</div>'
                '</div>'
            )
        )

    _html(
        '<div class="rt-panel">'
        '<div class="rt-panel-title">Zusätzliche Einblicke</div>'
        + "".join(rows)
        + '</div>'
    )


def regime_path(current: str) -> None:
    states = [
        ("RECOVERY", "Recovery"),
        ("EXPANSION", "Expansion"),
        ("SLOWDOWN", "Slowdown"),
        ("CONTRACTION", "Contraction"),
    ]

    current_upper = str(current or "").upper()
    nodes = []

    for key, label in states:
        active = (
            key in current_upper
            or (
                key == "SLOWDOWN"
                and "LATE_SLOWDOWN" in current_upper
            )
        )

        nodes.append(
            (
                f'<div class="rt-node{" active" if active else ""}">'
                f'{escape(label)}'
                '</div>'
            )
        )

    _html(
        '<div class="rt-regime-path">'
        + "".join(nodes)
        + '</div>'
    )

# V3.30.4.1 · RT HERO COMPATIBILITY REPAIR
