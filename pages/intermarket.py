from __future__ import annotations
# V3.19.5 · TRADER INTERMARKET ANALYSIS ONLY
# Legacy source contracts only; not rendered:
# V3.15.5 · EXPANDED COT INTERMARKET UNIVERSE
# Research-/Confluence-Layer · weder Watchlist-Signal noch Trade-Entscheidung

import html

import pandas as pd
import streamlit as st

from src.intermarket import (
    INTERMARKET_RELATIONSHIPS,
    evaluate_relationships,
    relationship_matrix,
)
from src.style import apply_style, context_strip, page_header, section_line
from src.watchlist import scan_classic_markets


apply_style()


def _tone(value: str) -> str:
    text = str(value or "").upper()
    if "SUPPORT" in text:
        return "support"
    if text in {"CONFLICT", "MIXED"}:
        return "conflict"
    return "neutral"


def _micro_age(label: str, age: int) -> str:
    if str(label).upper() == "NEUTRAL" or int(age) < 0:
        return ""
    return "diese Woche" if int(age) == 0 else f"vor {int(age)}W"


def _category_label(value: str) -> str:
    return {
        "CURRENCY_COMMODITY": "FX ↔ Commodity",
        "MACRO_COMMODITY": "USD ↔ Commodity",
        "COMMODITY_COMMODITY": "Commodity ↔ Commodity",
        "COMMODITY_RATES": "Commodity ↔ Rates",
        "RISK_SENTIMENT": "Risk ↔ Volatility",
    }.get(str(value), str(value))


page_header(
    "Analyse · Cross-Market",
    "Intermarket",
    "Bestätigen wirtschaftlich verbundene COT-Märkte dieselbe Richtung?",
    "V3.15.5 · EXPANDED COT INTERMARKET UNIVERSE",
)

st.caption(
    "Aktuelle Intermarket-Konfluenz aus den bestehenden COT-Signalen. "
    "Die Seite zeigt bewusst nur das Analyseergebnis; Methodik und "
    "Datenqualität liegen im Admin-Bereich."
)

with st.spinner("COT-Märkte für Intermarket werden geladen …"):
    scan = scan_classic_markets()

all_markets = scan.get("all_markets", pd.DataFrame())
if isinstance(all_markets, list):
    all_markets = pd.DataFrame(all_markets)
if all_markets is None:
    all_markets = pd.DataFrame()

results = evaluate_relationships(all_markets)

support_count = (
    int(results["overall"].astype(str).str.contains("SUPPORT").sum())
    if not results.empty
    else 0
)
conflict_count = (
    int(results["overall"].astype(str).isin(["CONFLICT", "MIXED"]).sum())
    if not results.empty
    else 0
)
available_count = (
    int(results["available"].fillna(False).sum())
    if not results.empty and "available" in results.columns
    else 0
)

context_strip(
    [
        ("Beziehungen", str(len(INTERMARKET_RELATIONSHIPS))),
        ("Daten verfügbar", f"{available_count}/{len(INTERMARKET_RELATIONSHIPS)}"),
        ("Support", str(support_count)),
        ("Konflikt / Mixed", str(conflict_count)),
    ]
)

view = st.radio(
    "Bereich",
    options=[
        "Alle",
        "FX ↔ Commodity",
        "USD ↔ Commodity",
        "Commodity ↔ Commodity",
        "Commodity ↔ Rates",
        "Risk ↔ Volatility",
    ],
    horizontal=True,
    label_visibility="collapsed",
)

if view != "Alle" and not results.empty:
    category_lookup = {
        "FX ↔ Commodity": "CURRENCY_COMMODITY",
        "USD ↔ Commodity": "MACRO_COMMODITY",
        "Commodity ↔ Commodity": "COMMODITY_COMMODITY",
        "Commodity ↔ Rates": "COMMODITY_RATES",
        "Risk ↔ Volatility": "RISK_SENTIMENT",
    }
    results = results[
        results["category"].astype(str).eq(category_lookup[view])
    ].copy()

section_line(
    "Aktuelle Intermarket-Bewertung",
    "Makro 156W + Mikro 26W · Support, Conflict oder Neutral",
)

st.html(
    """
    <style>
    .im-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:8px 0 18px}
    .im-card{background:#fff;border:1px solid #e6eaf0;border-radius:14px;padding:16px;box-shadow:0 1px 2px rgba(15,23,42,.03)}
    .im-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:13px}
    .im-pair{font-size:15px;font-weight:800;color:#101828}
    .im-rel{font-size:9px;font-weight:800;letter-spacing:.05em;color:#667085;text-align:right}
    .im-cat{font-size:9px;color:#98a2b3;margin-top:3px}
    .im-row{display:grid;grid-template-columns:64px 1fr 78px 1fr;gap:7px;align-items:center;padding:9px 0;border-top:1px solid #f0f2f5}
    .im-k{font-size:9px;font-weight:800;letter-spacing:.055em;color:#98a2b3;text-transform:uppercase}
    .im-v{font-size:11px;font-weight:750;color:#344054}
    .im-age{font-size:8px;color:#98a2b3;margin-top:2px}
    .im-state{display:inline-flex;align-items:center;justify-content:center;padding:6px 8px;border-radius:8px;font-size:9px;font-weight:850;white-space:nowrap}
    .im-support{background:#ecfdf3;color:#15803d;border:1px solid #d7f2df}
    .im-conflict{background:#fff1f2;color:#dc2626;border:1px solid #ffe0e3}
    .im-neutral{background:#f8fafc;color:#667085;border:1px solid #e5e7eb}
    .im-overall{margin-top:12px;display:flex;align-items:center;justify-content:space-between}
    .im-note{font-size:9px;color:#98a2b3;margin-top:8px;line-height:1.45}
    .im-regime{font-size:8px;font-weight:800;color:#b54708;background:#fffaeb;border:1px solid #fedf89;border-radius:6px;padding:3px 5px;margin-left:5px}
    @media(max-width:1000px){.im-grid{grid-template-columns:1fr}}
    </style>
    """
)

cards = []
for row in results.to_dict(orient="records"):
    left_symbol = html.escape(str(row.get("currency_symbol", "—")))
    right_name = html.escape(str(row.get("reference_market", "—")))
    category = html.escape(_category_label(str(row.get("category", ""))))
    regime = (
        '<span class="im-regime">REGIME</span>'
        if bool(row.get("regime_dependent", False))
        else ""
    )

    if not bool(row.get("available", False)):
        cards.append(
            f"""
            <div class="im-card">
              <div class="im-head">
                <div>
                  <div class="im-pair">{left_symbol} ↔ {right_name}</div>
                  <div class="im-cat">{category}</div>
                </div>
              </div>
              <div class="im-note">Daten aktuell nicht verfügbar</div>
              <div class="im-overall"><span class="im-k">GESAMT</span><span class="im-state im-neutral">NEUTRAL</span></div>
            </div>
            """
        )
        continue

    macro = str(row.get("macro_alignment", "NEUTRAL"))
    micro = str(row.get("micro_alignment", "NEUTRAL"))
    overall = str(row.get("overall", "NEUTRAL"))
    left_micro_age = _micro_age(
        str(row.get("currency_micro_label", "NEUTRAL")),
        int(row.get("currency_micro_age_weeks", -1)),
    )
    right_micro_age = _micro_age(
        str(row.get("reference_micro_label", "NEUTRAL")),
        int(row.get("reference_micro_age_weeks", -1)),
    )

    cards.append(
        f"""
        <div class="im-card">
          <div class="im-head">
            <div>
              <div class="im-pair">{left_symbol} ↔ {right_name}</div>
              <div class="im-cat">{category}</div>
            </div>
          </div>

          <div class="im-row">
            <div class="im-k">Makro</div>
            <div class="im-v">{html.escape(str(row['currency_macro_label']))}</div>
            <span class="im-state im-{_tone(macro)}">{html.escape(macro)}</span>
            <div class="im-v">{html.escape(str(row['reference_macro_label']))}</div>
          </div>

          <div class="im-row">
            <div class="im-k">Mikro</div>
            <div class="im-v">
              {html.escape(str(row['currency_micro_label']))}
              <div class="im-age">{html.escape(left_micro_age)}</div>
            </div>
            <span class="im-state im-{_tone(micro)}">{html.escape(micro)}</span>
            <div class="im-v">
              {html.escape(str(row['reference_micro_label']))}
              <div class="im-age">{html.escape(right_micro_age)}</div>
            </div>
          </div>

          <div class="im-overall">
            <span class="im-k">GESAMT</span>
            <span class="im-state im-{_tone(overall)}">{html.escape(overall)}</span>
          </div>
        </div>
        """
    )

if cards:
    st.html('<div class="im-grid">' + "".join(cards) + "</div>")
else:
    st.info("Für diesen Bereich sind aktuell keine Beziehungen ausgewählt.")
