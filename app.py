from __future__ import annotations

import streamlit as st

from src.deployment_mode import REMOTE_GATEWAY, deployment_config_from_mapping
from src.journal_gateway_client import JournalGatewayClient, JournalGatewayError, config_from_mapping as gateway_config_from_mapping
from src.style import apply_style
from src.trade_journal import initialize_journal, resolve_db_path
from src.trader_auth import authenticate_trader, create_trader, get_trader, trader_count


st.set_page_config(
    page_title="COT Research",
    page_icon="◆",
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
        st.caption("Für die Online-Instanz müssen [deployment] mode='REMOTE_GATEWAY' sowie [gateway] base_url/shared_key in Streamlit Secrets gesetzt sein.")
        st.stop()
else:
    db_path = resolve_db_path(journal_section)
    initialize_journal(db_path)


def _login_screen_local():
    st.title("◆ COT Research")
    st.caption("V3.7.0.1 · GATEWAY JSON HOTFIX · Multi-Trader")
    if trader_count(db_path=db_path) == 0:
        st.subheader("Erstes Admin-Konto anlegen")
        st.info("Dieses Konto übernimmt automatisch alle bereits vorhandenen Journal-Trades ohne Trader-Zuordnung.")
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

    st.subheader("Trader Login")
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
    st.caption("Passwörter werden ausschließlich als PBKDF2-SHA256-Hash in der lokalen SQLite-Datenbank gespeichert.")
    st.stop()


def _login_screen_remote():
    assert remote_client is not None
    st.title("◆ COT Research")
    st.caption("V3.7.0.1 · ONLINE PLANNER · JSON-safe Gateway")
    st.subheader("Trader Login")
    st.caption("Die Anmeldung wird verschlüsselt an dein lokales Journal-Gateway weitergereicht; die Trader-Datenbank bleibt auf dem Mac.")
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
            st.caption("Prüfe, ob dein Mac und der HTTPS-Tunnel zum lokalen Journal-Gateway erreichbar sind.")
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
    mode_label = "ONLINE · GATEWAY" if is_remote else "LOCAL · MASTER"
    st.caption(f"**{mode_label}**")
    st.caption(f"Angemeldet als **{trader['display_name']}** · {trader['role']}")
    if st.button("Abmelden", use_container_width=True):
        if is_remote and remote_client is not None and st.session_state.get("auth_gateway_token"):
            try:
                remote_client.with_token(str(st.session_state["auth_gateway_token"])).logout()
            except JournalGatewayError:
                pass
        st.session_state.pop("auth_gateway_token", None)
        st.session_state.pop("auth_trader", None)
        st.session_state.pop("v361_outcome_synced", None)
        st.rerun()

# Remote deployments intentionally omit FTMO account/risk pages. All MT5 account
# information and outcome synchronization remain on the local Mac.
if is_admin:
    if not is_remote:
        pages = {
            "SCHNELLÜBERBLICK": [
                st.Page("pages/watchlist.py", title="COT Watchlist", icon=":material/view_list:", default=True),
                st.Page("pages/risk_cockpit.py", title="Risk Cockpit", icon=":material/health_and_safety:"),
            ],
            "TRADING": [
                st.Page("pages/trade_planner.py", title="Trade Planner", icon=":material/edit_note:"),
                st.Page("pages/trading_journal.py", title="Trading Journal", icon=":material/menu_book:"),
            ],
            "MARKT & PORTFOLIO": [
                st.Page("pages/marktanalyse.py", title="COT Marktanalyse", icon=":material/query_stats:"),
                st.Page("pages/forex_matrix.py", title="Forex COT Matrix", icon=":material/currency_exchange:"),
                st.Page("pages/portfolio_risk.py", title="Portfolio & Risk", icon=":material/account_balance_wallet:"),
            ],
            "RESEARCH": [
                st.Page("pages/research_lab.py", title="COT Research Lab", icon=":material/science:"),
                st.Page("pages/datenmodell.py", title="CFTC Datenmodell", icon=":material/database:"),
            ],
            "ADMIN": [
                st.Page("pages/trader_admin.py", title="Trader verwalten", icon=":material/manage_accounts:"),
            ],
        }
    else:
        pages = {
            "SCHNELLÜBERBLICK": [
                st.Page("pages/watchlist.py", title="COT Watchlist", icon=":material/view_list:", default=True),
            ],
            "TRADING": [
                st.Page("pages/trade_planner.py", title="Trade Planner", icon=":material/edit_note:"),
                st.Page("pages/trading_journal.py", title="Trading Journal", icon=":material/menu_book:"),
            ],
            "MARKTANALYSE": [
                st.Page("pages/marktanalyse.py", title="COT Marktanalyse", icon=":material/query_stats:"),
                st.Page("pages/forex_matrix.py", title="Forex COT Matrix", icon=":material/currency_exchange:"),
            ],
            "RESEARCH": [
                st.Page("pages/research_lab.py", title="COT Research Lab", icon=":material/science:"),
                st.Page("pages/datenmodell.py", title="CFTC Datenmodell", icon=":material/database:"),
            ],
            "ADMIN": [
                st.Page("pages/trader_admin.py", title="Trader verwalten", icon=":material/manage_accounts:"),
            ],
        }
else:
    pages = {
        "SCHNELLÜBERBLICK": [
            st.Page("pages/watchlist.py", title="COT Watchlist", icon=":material/view_list:", default=True),
        ],
        "TRADING": [
            st.Page("pages/trade_planner.py", title="Trade Planner", icon=":material/edit_note:"),
            st.Page("pages/trading_journal.py", title="Trading Journal", icon=":material/menu_book:"),
        ],
        "MARKTANALYSE": [
            st.Page("pages/marktanalyse.py", title="COT Marktanalyse", icon=":material/query_stats:"),
            st.Page("pages/forex_matrix.py", title="Forex COT Matrix", icon=":material/currency_exchange:"),
        ],
        "RESEARCH": [
            st.Page("pages/research_lab.py", title="COT Research Lab", icon=":material/science:"),
            st.Page("pages/datenmodell.py", title="CFTC Datenmodell", icon=":material/database:"),
        ],
    }

page = st.navigation(pages, position="sidebar")
page.run()
