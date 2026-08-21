from __future__ import annotations
# V3.21.0 · TRADE TICKET UX PREVIEW
# V3.21.0 legacy source contracts · NOT RENDERED
# suggested_target = base_price * (1.02 if side == "LONG" else 0.98)
# V3.20.0 · PLANNER IP SHIELD
# Technische Speicher-/Gateway-Details sind ADMIN-only.

import math
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import streamlit as st

from src.deployment_mode import REMOTE_GATEWAY, deployment_config_from_mapping
from src.ftmo_risk import risk_config_from_mapping
from src.journal_gateway_client import JournalGatewayClient, JournalGatewayError, config_from_mapping as gateway_config_from_mapping
from src.prop_gateway_compat import prop_account as remote_prop_account
from src.price_units import auto_market_reference_entry, mt5_price_to_plan, planner_digits, price_unit_note
from src.mt5_account import (
    MT5BridgeError,
    MT5ConfigError,
    MT5ConnectionError,
    MT5UnavailableError,
    config_from_mapping,
    get_mt5_snapshot,
)
from src.style import apply_style, context_strip, definition, metric_card, page_header, section_line
from src.mt5_symbols import openable_symbol_catalog, symbol_label_map
from src.prop_desk import ensure_prop_account, realized_balance
from src.trade_journal import create_trade_plan, initialize_journal, resolve_db_path
from src.trade_context import all_markets, infer_cot_context
from src.trade_snapshot import collect_trade_snapshot
from src.tradingview_widget import render_tradingview_chart


apply_style()

trader = dict(st.session_state.get("auth_trader") or {})
if not trader:
    st.error("Keine Trader-Sitzung aktiv. Bitte neu anmelden.")
    st.stop()
is_admin = str(trader.get("role", "TRADER")).upper() == "ADMIN"


def _secret_section(name: str) -> dict:
    try:
        section = st.secrets.get(name, {})
        return dict(section) if section else {}
    except Exception:
        return {}


def _finite(value, default=np.nan):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if np.isfinite(x) else default


def _money(value, currency="USD"):
    x = _finite(value)
    if not np.isfinite(x):
        return "—"
    prefix = "$" if str(currency).upper() == "USD" else f"{currency} "
    return f"{prefix}{x:,.2f}"


def _price(value, digits=5):
    x = _finite(value)
    if not np.isfinite(x):
        return "—"
    return f"{x:.{digits}f}".rstrip("0").rstrip(".")


def _symbol_row(catalog: pd.DataFrame, symbol: str) -> dict:
    if catalog is None or catalog.empty or "symbol" not in catalog.columns:
        return {}
    rows = catalog[catalog["symbol"].astype(str).str.upper() == str(symbol).upper()]
    return rows.iloc[0].to_dict() if not rows.empty else {}


def _mark_price(spec: dict) -> float:
    bid, ask, last = (_finite(spec.get(k)) for k in ("bid", "ask", "last"))
    if np.isfinite(last) and last > 0:
        return last
    if np.isfinite(bid) and np.isfinite(ask):
        return (bid + ask) / 2.0
    if np.isfinite(bid):
        return bid
    if np.isfinite(ask):
        return ask
    return np.nan


def _context_label(context: dict) -> str:
    mode = str(context.get("mode", "NONE"))
    if mode == "FX_PAIR":
        return f"FX · {context.get('base')}/{context.get('quote')}"
    if mode == "MARKET":
        market = context.get("market") or {}
        return f"{context.get('asset_class', 'Markt')} · {market.get('name', '—')}"
    return "Keine automatische COT-Zuordnung"


page_header(
    "Trading · Neuer Trade",
    "Neuer Trade",
    "Asset wählen, Setup definieren, Risiko prüfen, speichern.",
    "V3.9.0 · SIMPLE TRADE FLOW",
)

st.caption("Keine echte Orderausführung: Der Planner dokumentiert deine Idee und friert den Research-Zustand im Hintergrund ein.")




mt5_section = _secret_section("mt5")
risk_section = _secret_section("risk")
journal_section = _secret_section("journal")
deployment = deployment_config_from_mapping(_secret_section("deployment"))
is_remote = deployment.mode == REMOTE_GATEWAY
risk_cfg = risk_config_from_mapping(risk_section)
db_path = None
remote_client = None

try:
    if is_remote:
        gateway_cfg = gateway_config_from_mapping(_secret_section("gateway"))
        token = str(st.session_state.get("auth_gateway_token", "") or "")
        remote_client = JournalGatewayClient(gateway_cfg, token)
        with st.spinner("Broker-Symbolkatalog wird sicher vom lokalen Gateway geladen …"):
            mt5_snapshot = remote_client.planner_context()
    else:
        mt5_config = config_from_mapping(mt5_section)
        db_path = resolve_db_path(journal_section)
        initialize_journal(db_path)
        with st.spinner("MT5-Symbole und Kurskontext werden geladen …"):
            mt5_snapshot = get_mt5_snapshot(mt5_config)
except (MT5UnavailableError, MT5BridgeError, MT5ConnectionError, MT5ConfigError, JournalGatewayError, ValueError) as exc:
    st.error(str(exc))
    if is_remote:
        st.caption("Die Online-App benötigt das erreichbare HTTPS-Journal-Gateway auf deinem Mac. MT5 selbst bleibt lokal.")
    else:
        st.caption("Für den Planner muss die bestehende MT5-Read-only-Bridge laufen.")
    st.stop()

prop_account = {}
prop_balance = np.nan
try:
    trader_id = str(trader.get("trader_id", "") or "")
    if is_remote:
        prop_info = remote_prop_account(remote_client) if remote_client is not None else {}
        prop_account = dict(prop_info.get("account") or {})
        prop_balance = _finite(prop_info.get("balance"))
    elif trader_id:
        prop_account = ensure_prop_account(trader_id, db_path=db_path)
        prop_balance = realized_balance(trader_id, db_path=db_path)
except Exception:
    prop_account = {}
    prop_balance = np.nan

account = mt5_snapshot.get("account", {})
catalog = openable_symbol_catalog(mt5_snapshot.get("symbol_catalog", pd.DataFrame()))
symbols = sorted(catalog["symbol"].dropna().astype(str).unique().tolist()) if "symbol" in catalog.columns else []
labels = symbol_label_map(catalog)
if not symbols:
    st.error("Die MT5-Bridge liefert aktuell keinen nutzbaren Broker-Symbolkatalog. Bridge aktualisieren und MT5 prüfen.")
    st.stop()

currency = str(account.get("currency", "USD") or "USD")
if is_remote:
    context_strip([
        ("Trader", str(trader.get("display_name", "—"))),
        ("Modus", "ONLINE"),
        ("CFD-Katalog", str(len(symbols))),
        ("Journal", "MAC · GATEWAY"),
    ])
    st.caption("Online werden nur Broker-Symbolmetadaten geladen; Live-FTMO-Quotes, Kontostand, Positionen und Portfolio-Risk verlassen den Mac nicht.")
elif is_admin:
    context_strip([
        ("Trader", str(trader.get("display_name", "—"))),
        ("Equity", _money(account.get("equity"), currency)),
        ("MT5-CFDs", str(len(symbols))),
        ("Journal", "SQLITE · PERSISTENT"),
    ])
else:
    context_strip([
        ("Trader", str(trader.get("display_name", "—"))),
        ("Rolle", "TRADER"),
        ("MT5-CFDs", str(len(symbols))),
        ("Journal", "EIGENE TRADES"),
    ])
    st.caption("FTMO-Kontostand, offene Positionen und Portfolio-Risk des ADMIN werden in deinem Snapshot nicht gespeichert oder angezeigt.")

if is_admin:
    with st.expander("Technische Details · Speicherung", expanded=False):
        if is_remote:
            st.code("REMOTE_GATEWAY → lokale Master-SQLite auf dem Mac")
            definition(
                "Der Online-Planner schreibt den Plan per authentifiziertem HTTPS-Gateway direkt in die lokale Master-Datenbank. "
                "Der lokale Dateipfad und FTMO-Kontodaten werden nicht an die Online-App übertragen."
            )
        else:
            st.code(str(db_path))
            definition(
                "Die Datenbank liegt standardmäßig außerhalb des Download-Ordners. Dadurch bleibt das Journal bei zukünftigen Bot-Versionen erhalten. "
                "Optional kann unter [journal] db_path in secrets.toml ein anderer lokaler Pfad gesetzt werden."
            )

section_line("1 · Asset", "Instrument, Richtung und Ordertyp")

prefill = str(st.session_state.get("trade_plan_symbol", "") or "")
default_index = symbols.index(prefill) if prefill in symbols else 0
c1, c2, c3, c4, c5 = st.columns([1.5, 0.75, 0.95, 0.8, 0.9])
with c1:
    symbol = st.selectbox(
        "CFD-Symbol",
        symbols,
        index=default_index,
        format_func=lambda value: labels.get(value, value),
        help="Vollständiger in deinem MT5-Konto verfügbarer Brokerkatalog; nicht nur Market Watch.",
    )
with c2:
    side = st.selectbox("Richtung", ["LONG", "SHORT"])
with c3:
    plan_type = st.selectbox("Plan-Typ", ["SIMULATION", "REAL", "SKIPPED"])
with c4:
    order_type = st.selectbox("Order", ["LIMIT", "MARKET"], help="LIMIT wird erst aktiv, wenn der Entry später im MT5-Kursverlauf berührt wird.")
with c5:
    timeframe = st.selectbox("S&D Timeframe", ["4H", "Daily", "Weekly", "1H", "Andere"])

spec = _symbol_row(catalog, symbol)
mt5_mark = _mark_price(spec)
mark = mt5_price_to_plan(symbol, mt5_mark) if np.isfinite(mt5_mark) else np.nan
mt5_digits = int(_finite(spec.get("digits"), 5) if np.isfinite(_finite(spec.get("digits"), 5)) else 5)
digits = planner_digits(symbol, mt5_digits)
inferred = infer_cot_context(symbol, spec)
unit_note = price_unit_note(symbol)
if unit_note:
    st.info(unit_note)

c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("MARK", _price(mark, digits), "lokaler MT5-Kontext" if not is_remote else "online bewusst nicht übertragen")
with c2:
    metric_card("COT-ZUORDNUNG", _context_label(inferred), "automatisch erkannt")
with c3:
    if plan_type == "SIMULATION" and prop_account:
        prop_default = _finite(prop_account.get("default_risk_pct"), 0.005)
        metric_card("PROP RISK", f"{prop_default * 100:.2f}%", f"Balance {_money(prop_balance, prop_account.get('currency', 'USD'))}")
    elif is_admin:
        metric_card("TARGET RISK", f"{risk_cfg.target_trade_risk_pct * 100:.2f}%", _money(risk_cfg.initial_capital * risk_cfg.target_trade_risk_pct, currency))
    else:
        metric_card("TRADER", str(trader.get("display_name", "—")), "eigene Simulation / eigener Plan")
with c4:
    metric_card("PLAN", plan_type, "REAL / SIMULATION / SKIPPED")

section_line("Chart", "optional")
with st.expander(f"TradingView Chart · {symbol}", expanded=False):
    tv_symbol = render_tradingview_chart(symbol, timeframe=timeframe, height=570)
    st.caption(
        f"TradingView-Mapping: {symbol} → {tv_symbol}. Der Chart dient nur der visuellen Analyse. "
        "Zone/SL/TP werden in Planner-Einheiten gespeichert; Execution und spätere Outcomes werden automatisch auf FTMO/MT5-CFD-Einheiten normalisiert. "
        "Falls das Broker-Symbol nicht exakt gemappt wird, kannst du oben im TradingView-Widget das Symbol manuell wechseln."
    )

with st.expander("COT-Zuordnung manuell überschreiben", expanded=False):
    override_enabled = st.checkbox("Manuelle COT-Zuordnung verwenden", value=False)
    market_rows = all_markets()
    asset_classes = list(dict.fromkeys(row["asset_class"] for row in market_rows))
    manual_context = None
    if override_enabled:
        ac = st.selectbox("Assetklasse", asset_classes)
        candidates = [row for row in market_rows if row["asset_class"] == ac]
        names = [row["name"] for row in candidates]
        name = st.selectbox("COT-Markt", names)
        chosen = next(row for row in candidates if row["name"] == name)
        manual_context = {"mode": "MARKET", "asset_class": ac, "market": {k: v for k, v in chosen.items() if k != "asset_class"}}
        st.caption(f"Snapshot verwendet: {ac} · {name}")
    else:
        st.caption("Automatische Zuordnung bleibt aktiv. FX-Paare speichern Base- und Quote-COT getrennt.")

section_line("2 · Setup", "Zone, Entry, Stop und Target")

# V3.21.1 · QUICK TRADE MODE
# V3.21.1 · V3.21.0 LEGACY TEST CONTRACTS · NOT RENDERED
# Review & Speichern
# Asset & Richtung
# value="AUTO · nächster Ask" if side == "LONG" else "AUTO · nächster Bid"
# V3.21.1 legacy UI source contracts · NOT RENDERED
# #### Schnell-Setup
# Target-Vorlage
# Target verwenden
# V3.21.1 · QUICK SETUP PRICING INIT HOTFIX
# Must execute before the compact Entry/Stop/Target controls.
base_price = float(mark) if np.isfinite(mark) and mark > 0 else 1.0
step = 10 ** (-digits) if digits > 0 else 1.0

st.markdown("### Trade Setup")
st.caption(
    "Im Schnellmodus brauchst du nur Entry, Stop, Target und Risiko. "
    "Alle zusätzlichen Journal-Felder bleiben optional."
)

q1, q2, q3, q4 = st.columns([1.0, 1.0, 1.15, 0.9])

with q1:
    if order_type == "MARKET":
        st.text_input(
            "Entry",
            value="AUTO · Ask" if side == "LONG" else "AUTO · Bid",
            disabled=True,
            help=(
                "Der tatsächliche SIMULATION-Fill kommt weiterhin aus "
                "der bestehenden MT5-Quote-Logik."
            ),
        )
        entry = None
    else:
        entry = st.number_input(
            "Entry",
            value=float(base_price),
            step=float(step),
            format=f"%.{digits}f",
        )

with q2:
    suggested_stop = base_price * (0.99 if side == "LONG" else 1.01)
    stop = st.number_input(
        "Stop",
        value=float(suggested_stop),
        step=float(step),
        format=f"%.{digits}f",
    )

with q3:
    v3211_target_mode = st.radio(
        "Target",
        ["2R", "2.5R", "3R", "MANUELL", "KEIN TP"],
        horizontal=True,
        index=0,
        key=f"v3211_target_{symbol}_{side}_{order_type}",
    )

    v3211_reference_entry = float(base_price) if entry is None else float(entry)
    v3211_risk = abs(v3211_reference_entry - float(stop))
    v3211_rr_map = {"2R": 2.0, "2.5R": 2.5, "3R": 3.0}
    use_target = v3211_target_mode != "KEIN TP"

    if not use_target:
        target = None
        st.caption("Kein festes Target")
    elif v3211_target_mode == "MANUELL":
        suggested_target = base_price * (1.02 if side == "LONG" else 0.98)
        target = st.number_input(
            "Manuelles Target",
            value=float(suggested_target),
            step=float(step),
            format=f"%.{digits}f",
            label_visibility="collapsed",
        )
    else:
        v3211_rr = float(v3211_rr_map[v3211_target_mode])
        target = (
            v3211_reference_entry + v3211_risk * v3211_rr
            if side == "LONG"
            else v3211_reference_entry - v3211_risk * v3211_rr
        )
        st.caption(f"TP · {_price(float(target), digits)}")

with q4:
    if plan_type == "SIMULATION" and prop_account:
        default_risk_pct = _finite(prop_account.get("default_risk_pct"), 0.005)
        max_risk_pct = _finite(prop_account.get("max_risk_pct"), 0.01)
    else:
        default_risk_pct = float(risk_cfg.target_trade_risk_pct)
        max_risk_pct = 0.02
    requested_risk_pct = st.number_input(
        "Gewünschtes Risiko (%)",
        min_value=0.05,
        max_value=max(0.05, float(max_risk_pct * 100.0)),
        value=min(float(default_risk_pct * 100.0), max(0.05, float(max_risk_pct * 100.0))),
        step=0.05,
        key=f"requested_risk_pct_{plan_type}",
        help="Bei SIMULATION wird daraus das unveränderliche USD-Risk-Budget des virtuellen Prop-Accounts berechnet.",
    ) / 100.0

with st.expander("Weitere Setup-Details (optional)", expanded=False):
    st.caption(
        "Zone, Freshness, Qualität, Retests, Gültigkeit und Notiz werden "
        "weiterhin gespeichert, müssen aber nicht jedes Mal geöffnet werden."
    )

    # Sensible display defaults only; the user remains the source of the actual S&D levels.
    base_price = float(mark) if np.isfinite(mark) and mark > 0 else 1.0
    step = 10 ** (-digits) if digits > 0 else 1.0

    p1, p2, p3 = st.columns(3)
    with p1:
        zone_type = st.selectbox("Zone", ["DEMAND", "SUPPLY", "OTHER"])
    with p2:
        freshness = st.selectbox("Freshness", ["FRESH", "1. RETEST", "2. RETEST", "3+ RETEST", "N/V"])
    with p3:
        quality = st.selectbox("Eigene Zonenqualität", ["A", "B", "C", "N/V"])

    z1, z2, z3 = st.columns(3)
    with z1:
        zone_low = st.number_input("Zone Low", value=float(base_price), step=float(step), format=f"%.{digits}f")
    with z2:
        zone_high = st.number_input("Zone High", value=float(base_price), step=float(step), format=f"%.{digits}f")
    with z3:
        retests = st.number_input("Retest-Anzahl", min_value=0, max_value=20, value=0, step=1)

    opt1, opt2 = st.columns(2)
    with opt1:
        expiry_days = st.number_input(
            "Limit gültig (Kalendertage)",
            min_value=0,
            max_value=90,
            value=0,
            step=1,
            disabled=order_type != "LIMIT",
            help="0 = kein automatisches Expiry. Der Outcome Tracker markiert eine nicht ausgelöste Limit-Idee erst nach diesem Zeitraum als EXPIRED.",
        )
    with opt2:
        skip_reason = st.selectbox(
            "Grund falls SKIPPED",
            [
                "—", "Risk blockiert", "Entry verpasst", "Zone nicht gut genug", "R:R zu niedrig",
                "News / Event", "Zu viele korrelierte Positionen", "Kein Vertrauen", "Andere Position bevorzugt", "Sonstiges",
            ],
        )

    notes = st.text_area("Notiz", placeholder="Optional: Warum gefällt dir die Zone / was ist der Kontext?")


if order_type == "LIMIT":
    risk_distance = abs(float(entry) - float(stop))
    if use_target and risk_distance > 0:
        reward = (float(target) - float(entry)) if side == "LONG" else (float(entry) - float(target))
        rr = reward / risk_distance
    else:
        rr = np.nan
else:
    risk_distance = np.nan
    rr = np.nan



# Display-only ticket. It does not alter plan, snapshot, sizing or execution.
v3210_entry_ref = float(base_price) if entry is None else float(entry)
v3210_entry_text = (
    "AUTO · MT5 Fill"
    if order_type == "MARKET"
    else _price(float(entry), digits)
)
v3210_stop_text = _price(float(stop), digits)
v3210_target_text = (
    _price(float(target), digits)
    if target is not None and np.isfinite(float(target))
    else "—"
)
v3210_rr_text = (
    f"{float(rr):.2f}R"
    if np.isfinite(rr)
    else ("nach Fill" if order_type == "MARKET" else "—")
)
v3210_risk_text = f"{float(requested_risk_pct) * 100:.2f}%"

v3210_risk_usd = np.nan
if (
    plan_type == "SIMULATION"
    and np.isfinite(_finite(prop_balance))
):
    v3210_risk_usd = float(prop_balance) * float(requested_risk_pct)

if order_type == "MARKET":
    v3210_valid = (
        float(stop) < v3210_entry_ref
        if side == "LONG"
        else float(stop) > v3210_entry_ref
    )
    v3210_status = "FILL PENDING" if v3210_valid else "CHECK STOP"
else:
    v3210_valid = (
        float(stop) < float(entry)
        if side == "LONG"
        else float(stop) > float(entry)
    )
    if use_target and target is not None:
        v3210_valid = v3210_valid and (
            float(target) > float(entry)
            if side == "LONG"
            else float(target) < float(entry)
        )
    v3210_status = "VALID" if v3210_valid else "CHECK LEVELS"

v3210_status_class = "ok" if v3210_valid else "warn"
v3210_risk_usd_text = (
    _money(
        v3210_risk_usd,
        prop_account.get("currency", "USD"),
    )
    if np.isfinite(v3210_risk_usd)
    else "—"
)

st.html(
    f"""
    <style>
      .v3210-ticket{{
        border:1px solid #dfe5ec;
        background:#fff;
        border-radius:14px;
        margin:20px 0 22px;
        overflow:hidden;
      }}
      .v3210-ticket-head{{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        padding:14px 16px;
        border-bottom:1px solid #eef1f5;
      }}
      .v3210-kicker{{
        color:#98a2b3;
        font-size:9px;
        font-weight:800;
        letter-spacing:.07em;
        text-transform:uppercase;
      }}
      .v3210-ticket-title{{
        color:#101828;
        font-size:17px;
        font-weight:800;
        margin-top:3px;
      }}
      .v3210-status{{
        font-size:10px;
        font-weight:800;
        padding:5px 9px;
        border-radius:999px;
      }}
      .v3210-status.ok{{
        color:#15803d;
        background:#f0fdf4;
        border:1px solid #bbf7d0;
      }}
      .v3210-status.warn{{
        color:#b45309;
        background:#fffbeb;
        border:1px solid #fde68a;
      }}
      .v3210-grid{{
        display:grid;
        grid-template-columns:repeat(6,minmax(0,1fr));
      }}
      .v3210-cell{{
        padding:13px 15px;
        border-right:1px solid #eef1f5;
      }}
      .v3210-cell:last-child{{border-right:none;}}
      .v3210-label{{
        color:#98a2b3;
        font-size:9px;
        font-weight:800;
        letter-spacing:.05em;
        text-transform:uppercase;
      }}
      .v3210-value{{
        color:#101828;
        font-size:14px;
        font-weight:780;
        margin-top:4px;
      }}
      @media(max-width:1000px){{
        .v3210-grid{{grid-template-columns:repeat(3,minmax(0,1fr));}}
        .v3210-cell{{border-bottom:1px solid #eef1f5;}}
      }}
      @media(max-width:650px){{
        .v3210-grid{{grid-template-columns:repeat(2,minmax(0,1fr));}}
      }}
    </style>
    <div class="v3210-ticket">
      <div class="v3210-ticket-head">
        <div>
          <div class="v3210-kicker">Trade Ticket · Live</div>
          <div class="v3210-ticket-title">{symbol} · {side} {order_type}</div>
        </div>
        <div class="v3210-status {v3210_status_class}">{v3210_status}</div>
      </div>
      <div class="v3210-grid">
        <div class="v3210-cell">
          <div class="v3210-label">Entry</div>
          <div class="v3210-value">{v3210_entry_text}</div>
        </div>
        <div class="v3210-cell">
          <div class="v3210-label">Stop</div>
          <div class="v3210-value">{v3210_stop_text}</div>
        </div>
        <div class="v3210-cell">
          <div class="v3210-label">Target</div>
          <div class="v3210-value">{v3210_target_text}</div>
        </div>
        <div class="v3210-cell">
          <div class="v3210-label">R:R</div>
          <div class="v3210-value">{v3210_rr_text}</div>
        </div>
        <div class="v3210-cell">
          <div class="v3210-label">Risk</div>
          <div class="v3210-value">{v3210_risk_text}</div>
        </div>
        <div class="v3210-cell">
          <div class="v3210-label">Risk Budget</div>
          <div class="v3210-value">{v3210_risk_usd_text}</div>
        </div>
      </div>
    </div>
    """
)

section_line("3 · Bestätigen", "Research-Snapshot wird automatisch im Hintergrund gespeichert")
st.caption(
    "Beim Speichern werden Research, COT-Kontext, Supply-&-Demand-Plan und CFD-Symbolmetadaten eingefroren. "
    + ("FTMO-Kontostand, Positionen, Live-Quotes und Portfolio-Risk bleiben im Online-Modus lokal auf dem Mac." if is_remote else "In der lokalen ADMIN-Instanz werden zusätzlich Kontostand, offene Positionen und Risk-Desk-Zustand eingefroren.")
)

if st.button("Trade speichern", type="primary", use_container_width=True):
    plan = {
        "plan_type": plan_type,
        "order_type": order_type,
        "expiry_at_utc": (datetime.now(timezone.utc) + timedelta(days=int(expiry_days))).isoformat() if order_type == "LIMIT" and int(expiry_days) > 0 else None,
        "skip_reason": "" if skip_reason == "—" else skip_reason,
        "asset_class": (manual_context or inferred).get("asset_class", "FX" if (manual_context or inferred).get("mode") == "FX_PAIR" else ""),
        "market_name": ((manual_context or inferred).get("market") or {}).get("name", f"{inferred.get('base', '')}{inferred.get('quote', '')}" if inferred.get("mode") == "FX_PAIR" else ""),
        "cot_symbol": ((manual_context or inferred).get("market") or {}).get("symbol", ""),
        "cftc_code": "",
        "cfd_symbol": symbol,
        "side": side,
        "zone_type": zone_type,
        "timeframe": timeframe,
        "zone_low": zone_low,
        "zone_high": zone_high,
        "entry": entry,
        "stop": stop,
        "target": target if use_target else None,
        "requested_risk_pct": requested_risk_pct,
        "zone_freshness": freshness,
        "retest_count": int(retests),
        "quality_grade": quality,
        "notes": notes,
    }
    if order_type == "MARKET":
        # The UI intentionally has no manual MARKET entry. Some legacy snapshot/schema
        # paths still require a finite numeric value, so provide an immutable zone-mid
        # reference for compatibility only. Execution ignores it and uses live Ask/Bid.
        plan["entry"] = auto_market_reference_entry(plan)
        plan["market_entry_auto"] = True
    try:
        with st.spinner("Research- und Risk-Snapshot wird eingefroren …"):
            payload = collect_trade_snapshot(
                plan=plan,
                mt5_snapshot=mt5_snapshot,
                risk_cfg=risk_cfg,
                context_override=manual_context,
                include_private_risk=is_admin and not is_remote,
            )
            research = payload.get("research") or {}
            if isinstance(research, dict):
                plan["cftc_code"] = str(research.get("cftc_code", "") or "")
            if is_remote:
                if remote_client is None:
                    raise JournalGatewayError("Gateway-Client ist nicht initialisiert.")
                saved = remote_client.create_trade_plan(plan, payload)
            else:
                saved = create_trade_plan(
                    plan=plan,
                    snapshot_payload=payload,
                    trader_id=str(trader.get("trader_id", "")) or None,
                    db_path=db_path,
                )
        st.success(
            f"Gespeichert · {trader.get('display_name', 'Trader')} · {symbol} {side} · {plan_type} · {saved['feature_count']} Snapshot-Features · ID {saved['trade_id'][:8]}…"
        )
        prop_allocation = dict(saved.get("prop_allocation") or {})
        if plan_type == "SIMULATION":
            if prop_allocation and prop_allocation.get("sizing_status") == "SIZED":
                st.info(
                    f"Prop Desk: {float(prop_allocation.get('lots', 0) or 0):g} virtuelle Lots · "
                    f"{_money(prop_allocation.get('actual_risk'), prop_account.get('currency', 'USD'))} initiales Risiko · "
                    f"Balance beim Plan {_money(prop_allocation.get('balance_at_plan'), prop_account.get('currency', 'USD'))}."
                )
            elif prop_allocation and prop_allocation.get("sizing_status") == "PENDING_FILL":
                st.info(
                    f"Prop Desk: Risk-Budget {_money(prop_allocation.get('risk_budget'), prop_account.get('currency', 'USD'))} eingefroren. "
                    "Virtuelle Lots werden automatisch mit dem tatsächlichen MARKET-Fill berechnet."
                )
            elif prop_allocation:
                st.warning(f"Prop-Desk Positionsgröße nicht verfügbar: {prop_allocation.get('sizing_reason') or prop_allocation.get('sizing_status')}")
            elif saved.get("prop_allocation_error"):
                st.warning("Plan gespeichert, aber Prop-Allokation fehlgeschlagen: " + str(saved.get("prop_allocation_error")))

        risk = payload.get("risk", {}).get("pretrade_approval", {})
        if is_admin and not is_remote and risk:
            status = str(risk.get("status", "—"))
            lots = _finite(risk.get("lots"), 0.0)
            actual = _finite(risk.get("actual_risk"), 0.0)
            st.info(f"Risk Snapshot: {status} · {lots:g} Lots · {_money(actual, currency)} modelliertes initiales Risiko")
        if payload.get("errors"):
            st.warning("Snapshot wurde gespeichert, aber einzelne Datenquellen waren unvollständig: " + " | ".join(map(str, payload["errors"])))
        st.page_link("pages/trading_journal.py", label="Im Trading Journal öffnen", icon=":material/menu_book:")
    except Exception as exc:
        st.error(f"Trade-Plan konnte nicht gespeichert werden: {exc}")
