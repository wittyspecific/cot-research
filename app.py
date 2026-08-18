from __future__ import annotations

import streamlit as st

from src.deployment_mode import REMOTE_GATEWAY, deployment_config_from_mapping
from src.journal_gateway_client import JournalGatewayClient, JournalGatewayError, config_from_mapping as gateway_config_from_mapping
from src.style import apply_style
from src.trade_journal import initialize_journal, resolve_db_path
from src.trader_auth import authenticate_trader, create_trader, get_trader, trader_count

APP_VERSION = "3.10.0"

st.set_page_config(
    page_title="COT Research",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_style()


def _secret_section(name: str) -> dict:
    try:
        section = st.secrets.get(name, {})
        return dict(section) if section else {}
    except Exception:
        return {}


deployment = deployment_config_from_mapping(_secret_section("deployment"))
is_remote = deployment.mode == REMOTE_GATEWAY
journal_section = _secret_section("journal")
db_path = None
remote_client: JournalGatewayClient | None = None

if is_remote:
    try:
        gateway_cfg = gateway_config_from_mapping(_secret_section("gateway"))
        remote_client = JournalGatewayClient(gateway_cfg, st.session_state.get("auth_gateway_token"))
    except ValueError as exc:
        st.error(str(exc))
        st.caption("Für ONLINE müssen Deployment und Gateway in Streamlit Secrets konfiguriert sein.")
        st.stop()
else:
    db_path = resolve_db_path(journal_section)
    initialize_journal(db_path)


def _login_shell(subtitle: str):
    left, center, right = st.columns([1, 1.15, 1])
    with center:
        st.markdown("<div style='height:6vh'></div>", unsafe_allow_html=True)
        st.markdown("### 📊 COT Research")
        st.caption(subtitle)
        return center


def _login_screen_local():
    _login_shell(f"V{APP_VERSION} · Research & Trading Workspace")
    left, center, right = st.columns([1, 1.15, 1])
    with center:
        if trader_count(db_path=db_path) == 0:
            st.subheader("Admin-Konto anlegen")
            with st.form("bootstrap_admin"):
                username = st.text_input("Benutzername", value="admin")
                display_name = st.text_input("Anzeigename", value="Admin")
                password = st.text_input("Passwort", type="password")
                password2 = st.text_input("Passwort wiederholen", type="password")
                submitted = st.form_submit_button("Admin anlegen", type="primary", use_container_width=True)
            if submitted:
                if password != password2:
                    st.error("Die Passwörter stimmen nicht überein.")
                    st.stop()
                try:
                    trader = create_trader(
                        username=username,
                        display_name=display_name,
                        password=password,
                        role="ADMIN",
                        claim_legacy_trades=True,
                        db_path=db_path,
                    )
                    st.session_state["auth_trader"] = trader
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            st.stop()

        st.subheader("Anmelden")
        with st.form("trader_login"):
            username = st.text_input("Benutzername")
            password = st.text_input("Passwort", type="password")
            submitted = st.form_submit_button("Anmelden", type="primary", use_container_width=True)
        if submitted:
            try:
                trader = authenticate_trader(username, password, db_path=db_path)
            except Exception:
                trader = None
            if trader is None:
                st.error("Login fehlgeschlagen oder Konto deaktiviert.")
            else:
                st.session_state["auth_trader"] = trader
                st.rerun()
        st.stop()


def _login_screen_remote():
    assert remote_client is not None
    _login_shell(f"V{APP_VERSION} · Online Workspace")
    left, center, right = st.columns([1, 1.15, 1])
    with center:
        st.subheader("Anmelden")
        st.caption("Trader-Datenbank und MT5 bleiben auf dem lokalen Gateway.")
        with st.form("trader_login_remote"):
            username = st.text_input("Benutzername")
            password = st.text_input("Passwort", type="password")
            submitted = st.form_submit_button("Anmelden", type="primary", use_container_width=True)
        if submitted:
            try:
                result = remote_client.login(username, password)
                token = str(result.get("token", "") or "")
                trader = dict(result.get("trader") or {})
                if not token or not trader:
                    raise JournalGatewayError("Gateway hat keine gültige Sitzung zurückgegeben.")
                st.session_state["auth_gateway_token"] = token
                st.session_state["auth_trader"] = trader
                st.rerun()
            except JournalGatewayError as exc:
                st.error(str(exc))
                st.caption("Prüfe Gateway und HTTPS-Tunnel auf deinem Mac.")
        st.stop()


trader = dict(st.session_state.get("auth_trader") or {})
if is_remote:
    if trader and st.session_state.get("auth_gateway_token"):
        try:
            assert remote_client is not None
            remote_client = remote_client.with_token(str(st.session_state["auth_gateway_token"]))
            trader = remote_client.me()
            st.session_state["auth_trader"] = trader
        except JournalGatewayError:
            st.session_state.pop("auth_gateway_token", None)
            st.session_state.pop("auth_trader", None)
            trader = {}
    if not trader:
        _login_screen_remote()
else:
    if trader:
        current = get_trader(str(trader.get("trader_id", "")), db_path=db_path)
        if not current or not current.get("active"):
            st.session_state.pop("auth_trader", None)
            trader = {}
        else:
            trader = current
            st.session_state["auth_trader"] = trader
    if not trader:
        _login_screen_local()

is_admin = str(trader.get("role", "TRADER")).upper() == "ADMIN"

with st.sidebar:
    st.html(
        '<div class="cot-brand"><div class="cot-brand-row">'
        '<div class="cot-logo">▥</div><div><div class="cot-brand-title">COT Research</div>'
        '<div class="cot-brand-sub">Trading & Analytics</div></div></div></div>'
    )
    mode_label = "ONLINE · GATEWAY" if is_remote else "LOCAL · MASTER"
    st.html(
        '<div class="cot-user-card">'
        f'<div class="cot-user-name">{trader["display_name"]}</div>'
        f'<div class="cot-user-meta">{trader["role"]} · {mode_label}</div>'
        '</div>'
    )
    if st.button("Abmelden", icon=":material/logout:", use_container_width=True):
        if is_remote and remote_client is not None and st.session_state.get("auth_gateway_token"):
            try:
                remote_client.with_token(str(st.session_state["auth_gateway_token"])).logout()
            except JournalGatewayError:
                pass
        st.session_state.pop("auth_gateway_token", None)
        st.session_state.pop("auth_trader", None)
        st.session_state.pop("v361_outcome_synced", None)
        st.rerun()

# V3.10.0: divide-and-conquer positioning regime is the primary research workflow.
# V3.15.0 · PAPER POSITION MANAGEMENT
pages: dict[str, list] = {
    "WORKSPACE": [
        st.Page("pages/dashboard.py", title="Dashboard", icon=":material/home:", default=True),
    ],
    "RESEARCH": [
        st.Page("pages/watchlist.py", title="Watchlist", icon=":material/radar:"),
        st.Page("pages/marktanalyse.py", title="Marktanalyse", icon=":material/query_stats:"),
        st.Page("pages/forex_matrix.py", title="Währungsstärke", icon=":material/currency_exchange:"),
    ],
    "TRADING": [
        st.Page("pages/trade_planner.py", title="Neuer Trade", icon=":material/add_circle:"),
        st.Page("pages/positionsmanagement.py", title="Positionsmanagement", icon=":material/tune:"),
        st.Page("pages/trading_journal.py", title="Journal", icon=":material/menu_book:"),
        st.Page("pages/prop_desk.py", title="Prop Desk", icon=":material/monitoring:"),
    ],
    "ADVANCED": [
        st.Page("pages/research_lab.py", title="Research Lab", icon=":material/science:"),
        st.Page("pages/datenmodell.py", title="CFTC Datenmodell", icon=":material/database:"),
    ],
}

if is_admin and not is_remote:
    pages["ADVANCED"].extend([
        st.Page("pages/risk_cockpit.py", title="FTMO Risk", icon=":material/health_and_safety:"),
        st.Page("pages/portfolio_risk.py", title="Portfolio Risk", icon=":material/account_balance_wallet:"),
    ])
if is_admin:
    pages["ADMIN"] = [
        st.Page("pages/trader_admin.py", title="Trader verwalten", icon=":material/manage_accounts:"),
    ]

page = st.navigation(pages, position="sidebar")
page.run()
