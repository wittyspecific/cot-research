from __future__ import annotations
# V3.21.4 · DASHBOARD CLEANUP · TOP3 REMOVED
# V3.21.4 legacy source contracts · NOT RENDERED
# Potenzial · Top 3 Setups
# V3.21.3 · DASHBOARD TOP 3 ALIGNED
# V3.21.3 · DASHBOARD TOP 3 ALIGNED
# V3.21.3 legacy source contract · NOT RENDERED
# Trade Status
# V3.21.2 · DASHBOARD TRADER FOCUS
# V3.21.2 legacy source contracts · NOT RENDERED
# Research Pulse
# Journal öffnen
# Prop Desk öffnen

import numpy as np
import pandas as pd
import streamlit as st

from src.deployment_mode import REMOTE_GATEWAY, deployment_config_from_mapping
from src.journal_gateway_client import JournalGatewayClient, JournalGatewayError, config_from_mapping as gateway_config_from_mapping
from src.mt5_account import MT5BridgeError, MT5ConfigError, MT5ConnectionError, MT5UnavailableError, config_from_mapping, get_mt5_snapshot
from src.prop_desk import prop_desk_state
from src.prop_gateway_compat import prop_desk as remote_prop_desk
from src.style import apply_style, metric_card, page_header, section_line
from src.trade_journal import initialize_journal, list_trade_plans, resolve_db_path

apply_style()


def _secret_section(name: str) -> dict:
    try:
        section = st.secrets.get(name, {})
        return dict(section) if section else {}
    except Exception:
        return {}


def _finite(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _money(value):
    x = _finite(value)
    return "—" if not np.isfinite(x) else f"${x:,.0f}"


def _pct(value):
    x = _finite(value)
    return "—" if not np.isfinite(x) else f"{x*100:+.2f}%"


def _pct_abs(value):
    x = _finite(value)
    return "—" if not np.isfinite(x) else f"{x*100:.2f}%"


def _r(value):
    x = _finite(value)
    return "—" if not np.isfinite(x) else f"{x:+.2f}R"


# V3.21.3 · SAME ALL-ALIGNED CONTRACT AS WATCHLIST

trader = dict(st.session_state.get("auth_trader") or {})
if not trader:
    st.error("Keine Trader-Sitzung aktiv.")
    st.stop()

page_header(
    "Workspace",
    f"Hallo, {trader.get('display_name', 'Trader')}",
    "Dein aktueller Überblick – Trading zuerst, Details nur bei Bedarf.",
    "V3.9.0 · MINIMAL WORKSPACE",
)

deployment = deployment_config_from_mapping(_secret_section("deployment"))
is_remote = deployment.mode == REMOTE_GATEWAY
trader_id = str(trader.get("trader_id", ""))
state = {}
plans = pd.DataFrame()

try:
    if is_remote:
        client = JournalGatewayClient(
            gateway_config_from_mapping(_secret_section("gateway")),
            str(st.session_state.get("auth_gateway_token", "") or ""),
        )
        state = remote_prop_desk(client)
        plans = client.list_trade_plans(limit=100, trader_id=trader_id)
    else:
        db_path = resolve_db_path(_secret_section("journal"))
        initialize_journal(db_path)
        mt5_snapshot = None
        try:
            mt5_snapshot = get_mt5_snapshot(config_from_mapping(_secret_section("mt5")))
        except (MT5BridgeError, MT5ConfigError, MT5ConnectionError, MT5UnavailableError):
            mt5_snapshot = None
        state = prop_desk_state(trader_id, db_path=db_path, mt5_snapshot=mt5_snapshot)
        plans = list_trade_plans(db_path=db_path, limit=100, trader_id=trader_id)
except (JournalGatewayError, ValueError, Exception) as exc:
    st.warning(f"Trading-Übersicht aktuell nicht vollständig verfügbar: {exc}")

summary = dict(state.get("summary") or {})
cols = st.columns(4)
with cols[0]:
    metric_card("Equity", _money(summary.get("equity")), _pct(summary.get("return_pct")) + " seit Start")
with cols[1]:
    metric_card("Floating P&L", _money(summary.get("floating_pnl")), "aktive Simulationen")
with cols[2]:
    metric_card("Open Risk", _pct_abs(summary.get("open_risk_pct")), _money(summary.get("open_risk")))
with cols[3]:
    metric_card("Offene Trades", str(int(summary.get("open_positions", 0) or 0)), f"{int(summary.get('closed_trades', 0) or 0)} geschlossen")

left, right = st.columns([1.7, 1], gap="large")
with left:
    section_line("Offene Positionen", "Live Mark-to-Market, wenn MT5 verfügbar")
    open_df = pd.DataFrame(state.get("open_positions") or [])
    if open_df.empty:
        st.info("Keine aktiven Simulationen.")
    else:
        view = open_df.copy()
        view["R"] = pd.to_numeric(view.get("current_r"), errors="coerce").map(_r)
        view["P&L"] = pd.to_numeric(view.get("floating_pnl"), errors="coerce").map(_money)
        view["Risk"] = pd.to_numeric(view.get("risk_pct_at_plan"), errors="coerce").map(_pct_abs)
        st.dataframe(
            view[["symbol", "side", "entry", "R", "P&L", "Risk"]].rename(columns={
                "symbol": "Asset", "side": "Richtung", "entry": "Entry"
            }),
            use_container_width=True,
            hide_index=True,
        )

with right:
    section_line("Schnellzugriff", "")
    st.page_link("pages/trade_planner.py", label="＋ Neuen Trade planen", icon=":material/add_circle:", use_container_width=True)
    st.page_link("pages/opportunity_scanner.py", label="Opportunity Scanner öffnen", icon=":material/radar:", use_container_width=True)
    st.page_link("pages/market_analysis_hub.py", label="Marktanalyse öffnen", icon=":material/hub:", use_container_width=True)
    st.page_link("pages/currency_strength_hub.py", label="Währungsstärke öffnen", icon=":material/currency_exchange:", use_container_width=True)

