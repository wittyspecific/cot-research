from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.deployment_mode import REMOTE_GATEWAY, deployment_config_from_mapping
from src.journal_gateway_client import JournalGatewayClient, JournalGatewayError, config_from_mapping as gateway_config_from_mapping
from src.mt5_account import MT5BridgeError, MT5ConfigError, MT5ConnectionError, MT5UnavailableError, config_from_mapping, get_mt5_snapshot
from src.prop_desk import prop_desk_ranking, prop_desk_state
from src.prop_gateway_compat import prop_desk as remote_prop_desk, prop_desk_ranking as remote_prop_desk_ranking
from src.style import apply_style, context_strip, metric_card, page_header, plotly_config, section_line
from src.trade_journal import initialize_journal, resolve_db_path
from src.trader_auth import list_traders

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
    except (TypeError, ValueError):
        return default
    return x if np.isfinite(x) else default


def _money(value) -> str:
    x = _finite(value)
    return "—" if not np.isfinite(x) else f"${x:,.2f}"


def _pct(value) -> str:
    x = _finite(value)
    return "—" if not np.isfinite(x) else f"{x*100:+.2f}%"


def _pct_abs(value) -> str:
    x = _finite(value)
    return "—" if not np.isfinite(x) else f"{x*100:.2f}%"


def _r(value) -> str:
    x = _finite(value)
    return "—" if not np.isfinite(x) else f"{x:+.2f}R"


trader = dict(st.session_state.get("auth_trader") or {})
if not trader:
    st.error("Keine Trader-Sitzung aktiv. Bitte neu anmelden.")
    st.stop()
is_admin = str(trader.get("role", "TRADER")).upper() == "ADMIN"
deployment = deployment_config_from_mapping(_secret_section("deployment"))
is_remote = deployment.mode == REMOTE_GATEWAY
remote_client = None
db_path = None
mt5_snapshot = None

try:
    if is_remote:
        remote_client = JournalGatewayClient(
            gateway_config_from_mapping(_secret_section("gateway")),
            str(st.session_state.get("auth_gateway_token", "") or ""),
        )
        traders = remote_client.list_traders(active_only=True) if is_admin else pd.DataFrame([trader])
    else:
        db_path = resolve_db_path(_secret_section("journal"))
        initialize_journal(db_path)
        traders = list_traders(db_path=db_path, active_only=True) if is_admin else pd.DataFrame([trader])
        try:
            mt5_snapshot = get_mt5_snapshot(config_from_mapping(_secret_section("mt5")))
        except (MT5BridgeError, MT5ConfigError, MT5ConnectionError, MT5UnavailableError):
            mt5_snapshot = None
except (JournalGatewayError, ValueError) as exc:
    st.error(str(exc))
    st.stop()

page_header(
    "Trading · Simulation",
    "Prop Desk",
    "Virtuelles Trading-Konto pro Trader: Balance, Equity, Floating/Realized P&L, Drawdown und Performance — ohne reale Orderausführung.",
    "V3.8.0.1 · PROP DESK GATEWAY HOTFIX",
)

if is_admin and not traders.empty:
    options = traders["trader_id"].astype(str).tolist()
    labels = {str(row["trader_id"]): f"{row['display_name']} · {row['username']}" for _, row in traders.iterrows()}
    default_id = str(trader.get("trader_id", ""))
    idx = options.index(default_id) if default_id in options else 0
    selected_trader_id = st.selectbox("Prop-Account anzeigen", options, index=idx, format_func=lambda x: labels.get(x, x))
else:
    selected_trader_id = str(trader.get("trader_id", ""))

if st.button("Prop Desk aktualisieren", icon=":material/refresh:"):
    st.rerun()

try:
    if is_remote:
        state = remote_prop_desk(remote_client, trader_id=selected_trader_id if is_admin else None)
    else:
        state = prop_desk_state(selected_trader_id, db_path=db_path, mt5_snapshot=mt5_snapshot)
except (JournalGatewayError, Exception) as exc:
    st.error(f"Prop Desk konnte nicht geladen werden: {exc}")
    st.stop()

account = dict(state.get("account") or {})
summary = dict(state.get("summary") or {})
owner_name = labels.get(selected_trader_id, trader.get("display_name", "Trader")) if is_admin else str(trader.get("display_name", "Trader"))
context_strip([
    ("Trader", str(owner_name).split(" · ")[0]),
    ("Startkapital", _money(summary.get("starting_capital"))),
    ("Standard Risk", f"{_finite(account.get('default_risk_pct'), 0.005)*100:.2f}%"),
    ("Preisquelle", "MT5 BRIDGE" if state.get("price_source") == "LOCAL_MT5_BRIDGE_QUOTES" else "LETZTER OUTCOME-STAND"),
])

st.caption(
    "Nur SIMULATION-Trades wirken auf dieses virtuelle Konto. Der Prop Desk eröffnet keine echten Positionen. "
    "Floating P&L wird beim Öffnen/Aktualisieren aus den lokal verfügbaren MT5-Bridge-Quotes der tatsächlich ACTIVE-Symbole markiert; dabei wird keine H1/M5/M1-Historie angefordert."
)

section_line("Account", "virtuelle Prop-Desk-Bilanz")
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    metric_card("BALANCE", _money(summary.get("balance")), "realized")
with c2:
    metric_card("EQUITY", _money(summary.get("equity")), "inkl. floating")
with c3:
    metric_card("FLOATING", _money(summary.get("floating_pnl")), "aktive Simulationen")
with c4:
    metric_card("REALIZED", _money(summary.get("realized_pnl")), "geschlossene Simulationen")
with c5:
    metric_card("RETURN", _pct(summary.get("return_pct")), "seit Account-Start")
with c6:
    metric_card("MAX DD", _pct_abs(summary.get("max_drawdown_pct")), "Equity Curve")

s1, s2, s3, s4, s5, s6 = st.columns(6)
with s1:
    metric_card("OPEN", str(int(summary.get("open_positions", 0) or 0)), "aktive Trades")
with s2:
    metric_card("OPEN RISK", _money(summary.get("open_risk")), _pct_abs(summary.get("open_risk_pct")))
with s3:
    metric_card("CLOSED", str(int(summary.get("closed_trades", 0) or 0)), "ausgewertet")
with s4:
    metric_card("WIN RATE", _pct_abs(summary.get("win_rate")), "closed trades")
with s5:
    pf = _finite(summary.get("profit_factor"))
    metric_card("PROFIT FACTOR", "∞" if np.isinf(pf) else (f"{pf:.2f}" if np.isfinite(pf) else "—"), "gross win / gross loss")
with s6:
    metric_card("EXPECTANCY", _r(summary.get("expectancy_r")), "Ø Result")

curve = pd.DataFrame(state.get("equity_curve") or [])
if not curve.empty:
    curve["time_utc"] = pd.to_datetime(curve["time_utc"], errors="coerce", utc=True)
    curve["equity"] = pd.to_numeric(curve["equity"], errors="coerce")
    curve = curve.dropna(subset=["time_utc", "equity"])
if not curve.empty:
    section_line("Equity Curve", "realisierte Trades + aktuelles Mark-to-Market")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=curve["time_utc"], y=curve["equity"], mode="lines+markers", name="Equity"))
    fig.update_layout(
        template="plotly_dark",
        height=360,
        margin=dict(l=10, r=20, t=15, b=10),
        xaxis_title=None,
        yaxis_title="USD",
        hovermode="x unified",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config=plotly_config())

section_line("Offene Positionen", "nur ACTIVE Simulationen")
open_df = pd.DataFrame(state.get("open_positions") or [])
if open_df.empty:
    st.info("Aktuell keine aktiven virtuellen Positionen.")
else:
    view = open_df.copy()
    view["Risk"] = pd.to_numeric(view["risk_usd"], errors="coerce").map(_money)
    view["Floating"] = pd.to_numeric(view["floating_pnl"], errors="coerce").map(_money)
    view["R"] = pd.to_numeric(view["current_r"], errors="coerce").map(_r)
    view["Lots"] = pd.to_numeric(view["lots"], errors="coerce").map(lambda x: f"{x:g}" if pd.notna(x) else "—")
    st.dataframe(
        view[["symbol", "side", "entry", "stop", "target", "mark", "Lots", "Risk", "Floating", "R"]].rename(columns={
            "symbol": "Symbol", "side": "Richtung", "entry": "Entry", "stop": "SL", "target": "TP", "mark": "Mark"
        }),
        use_container_width=True,
        hide_index=True,
    )
    if state.get("mark_time"):
        st.caption(f"Mark-to-Market Stand: {state.get('mark_time')}")

section_line("Geschlossene Trades", "virtuelles Account-Ledger aus Outcome × eingefrorenem USD-Risk")
closed_df = pd.DataFrame(state.get("closed_trades") or [])
if closed_df.empty:
    st.caption("Noch keine geschlossenen Prop-Desk-Simulationen.")
else:
    view = closed_df.copy()
    view["Zeit"] = pd.to_datetime(view["exit_time_utc"], errors="coerce", utc=True).dt.strftime("%d.%m.%Y %H:%M")
    view["Result"] = pd.to_numeric(view["result_r"], errors="coerce").map(_r)
    view["P&L"] = pd.to_numeric(view["realized_pnl"], errors="coerce").map(_money)
    view["Risk"] = pd.to_numeric(view["risk_usd"], errors="coerce").map(_money)
    st.dataframe(
        view[["Zeit", "symbol", "side", "Result", "P&L", "Risk", "first_exit"]].rename(columns={
            "symbol": "Symbol", "side": "Richtung", "first_exit": "Exit"
        }),
        use_container_width=True,
        hide_index=True,
    )

if is_admin:
    section_line("Prop Desk Ranking", "identische virtuelle Account-Logik je Trader")
    try:
        ranking = remote_prop_desk_ranking(remote_client) if is_remote else prop_desk_ranking(db_path=db_path, mt5_snapshot=mt5_snapshot)
    except JournalGatewayError as exc:
        ranking = pd.DataFrame()
        st.warning(str(exc))
    if not ranking.empty:
        rank = ranking.copy().sort_values("equity", ascending=False)
        rank["Equity"] = pd.to_numeric(rank["equity"], errors="coerce").map(_money)
        rank["Return"] = pd.to_numeric(rank["return_pct"], errors="coerce").map(_pct)
        rank["Max DD"] = pd.to_numeric(rank["max_drawdown_pct"], errors="coerce").map(_pct_abs)
        rank["Open Risk"] = pd.to_numeric(rank["open_risk_pct"], errors="coerce").map(_pct_abs)
        rank["Realized"] = pd.to_numeric(rank["realized_pnl"], errors="coerce").map(_money)
        st.dataframe(
            rank[["display_name", "Equity", "Return", "Max DD", "Open Risk", "open_positions", "closed_trades", "Realized"]].rename(columns={
                "display_name": "Trader", "open_positions": "Open", "closed_trades": "Closed"
            }),
            use_container_width=True,
            hide_index=True,
        )

st.info(
    "Accounting-Regel: Die virtuelle Lotgröße und das USD-Risk werden beim Speichern des SIMULATION-Plans eingefroren. "
    "Spätere Balance-Änderungen verändern alte Trades nicht rückwirkend."
)
