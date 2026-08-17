from __future__ import annotations

import pandas as pd
import streamlit as st

from src.deployment_mode import REMOTE_GATEWAY, deployment_config_from_mapping
from src.journal_gateway_client import JournalGatewayClient, JournalGatewayError, config_from_mapping as gateway_config_from_mapping
from src.prop_gateway_compat import prop_account as remote_prop_account, update_prop_account as remote_update_prop_account
from src.style import apply_style, context_strip, metric_card, page_header, section_line
from src.prop_desk import ensure_prop_account, update_prop_account
from src.trade_journal import initialize_journal, resolve_db_path
from src.trader_auth import (
    change_own_password,
    claim_unassigned_plans,
    create_trader,
    list_traders,
    reset_trader_password,
    set_trader_active,
    unassigned_plan_count,
)

apply_style()


def _secret_section(name: str) -> dict:
    try:
        section = st.secrets.get(name, {})
        return dict(section) if section else {}
    except Exception:
        return {}


current = dict(st.session_state.get("auth_trader") or {})
if str(current.get("role", "")).upper() != "ADMIN":
    st.error("Diese Seite ist nur für ADMIN verfügbar.")
    st.stop()

deployment = deployment_config_from_mapping(_secret_section("deployment"))
is_remote = deployment.mode == REMOTE_GATEWAY
db_path = None
remote_client = None

try:
    if is_remote:
        remote_client = JournalGatewayClient(
            gateway_config_from_mapping(_secret_section("gateway")),
            str(st.session_state.get("auth_gateway_token", "") or ""),
        )
        traders = remote_client.list_traders(active_only=False)
        unassigned = 0
    else:
        db_path = resolve_db_path(_secret_section("journal"))
        initialize_journal(db_path)
        traders = list_traders(db_path=db_path)
        unassigned = unassigned_plan_count(db_path=db_path)
except (ValueError, JournalGatewayError) as exc:
    st.error(str(exc))
    st.stop()

page_header(
    "Admin · Multi-Trader",
    "Trader verwalten",
    "Getrennte Identitäten für gemeinsame Simulationen und spätere Research-Auswertung.",
    "V3.9.0 · MINIMAL UI REWORK",
)

active = int(pd.to_numeric(traders.get("active", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not traders.empty else 0
admins = int(((traders.get("role", pd.Series(dtype=str)) == "ADMIN") & (pd.to_numeric(traders.get("active", 0), errors="coerce") == 1)).sum()) if not traders.empty else 0
context_strip([
    ("Trader", str(len(traders))),
    ("Aktiv", str(active)),
    ("Admins", str(admins)),
    ("Betrieb", "ONLINE→MAC" if is_remote else "LOCAL"),
])

if unassigned and not is_remote:
    st.warning(f"{unassigned} ältere Trade-Pläne besitzen noch keine Trader-Zuordnung.")
    if st.button("Diese Legacy-Pläne meinem Admin-Konto zuordnen", type="primary"):
        count = claim_unassigned_plans(str(current["trader_id"]), db_path=db_path)
        st.success(f"{count} Trade-Pläne wurden deinem Konto zugeordnet.")
        st.rerun()

section_line("Neuen Trader anlegen", "Passwort wird nur lokal gehasht gespeichert")
with st.form("create_trader_form"):
    c1, c2, c3 = st.columns(3)
    with c1:
        username = st.text_input("Benutzername", placeholder="z. B. max")
    with c2:
        display_name = st.text_input("Anzeigename", placeholder="z. B. Max")
    with c3:
        role = st.selectbox("Rolle", ["TRADER", "ADMIN"])
    p1, p2 = st.columns(2)
    with p1:
        password = st.text_input("Initiales Passwort", type="password")
    with p2:
        password2 = st.text_input("Passwort wiederholen", type="password")
    create = st.form_submit_button("Trader anlegen", type="primary", use_container_width=True)
if create:
    if password != password2:
        st.error("Die Passwörter stimmen nicht überein.")
    else:
        try:
            if is_remote:
                created = remote_client.create_trader(username=username, display_name=display_name, password=password, role=role)
            else:
                created = create_trader(username=username, display_name=display_name, password=password, role=role, db_path=db_path)
            st.success(f"Trader {created['display_name']} ({created['username']}) wurde angelegt.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

section_line("Trader", "Identität bleibt pro Trade erhalten")
try:
    traders = remote_client.list_traders(active_only=False) if is_remote else list_traders(db_path=db_path)
except JournalGatewayError as exc:
    st.error(str(exc))
    st.stop()

if not traders.empty:
    view = traders.copy()
    view["Status"] = view["active"].map(lambda x: "AKTIV" if bool(x) else "DEAKTIVIERT")
    view["Letzter Login"] = pd.to_datetime(view["last_login_utc"], errors="coerce", utc=True).dt.strftime("%d.%m.%Y %H:%M")
    st.dataframe(
        view[["display_name", "username", "role", "Status", "Letzter Login"]].rename(columns={
            "display_name": "Name", "username": "Benutzername", "role": "Rolle"
        }),
        use_container_width=True,
        hide_index=True,
    )

    options = traders["trader_id"].tolist()
    label_map = {row["trader_id"]: f"{row['display_name']} · {row['username']} · {row['role']}" for _, row in traders.iterrows()}
    selected = st.selectbox("Trader bearbeiten", options, format_func=lambda x: label_map.get(x, x))
    row = traders[traders["trader_id"] == selected].iloc[0]
    a1, a2 = st.columns(2)
    with a1:
        desired_active = st.checkbox("Konto aktiv", value=bool(row["active"]), key=f"active_{selected}")
        if st.button("Status speichern", key=f"save_active_{selected}"):
            try:
                if is_remote:
                    remote_client.set_trader_active(selected, desired_active)
                else:
                    set_trader_active(selected, desired_active, db_path=db_path)
                st.success("Status gespeichert.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with a2:
        new_pw = st.text_input("Neues Passwort", type="password", key=f"reset_pw_{selected}")
        if st.button("Passwort zurücksetzen", key=f"reset_btn_{selected}"):
            try:
                if is_remote:
                    remote_client.reset_trader_password(selected, new_pw)
                else:
                    reset_trader_password(selected, new_pw, db_path=db_path)
                st.success("Passwort wurde neu gesetzt.")
            except Exception as exc:
                st.error(str(exc))

    section_line("Prop Desk Konto", "virtuelles Simulationskapital und Risk-Policy")
    try:
        if is_remote:
            prop_info = remote_prop_account(remote_client, trader_id=selected)
            prop = dict(prop_info.get("account") or {})
        else:
            prop = ensure_prop_account(selected, db_path=db_path)
        pc1, pc2, pc3, pc4 = st.columns(4)
        with pc1:
            prop_start = st.number_input(
                "Startkapital (USD)", min_value=1_000.0, max_value=10_000_000.0,
                value=float(prop.get("starting_capital", 200_000.0)), step=10_000.0, key=f"prop_start_{selected}"
            )
        with pc2:
            prop_default = st.number_input(
                "Standard Risk (%)", min_value=0.05, max_value=5.0,
                value=float(prop.get("default_risk_pct", 0.005))*100.0, step=0.05, key=f"prop_default_{selected}"
            ) / 100.0
        with pc3:
            prop_max = st.number_input(
                "Max Risk / Trade (%)", min_value=0.05, max_value=5.0,
                value=float(prop.get("max_risk_pct", 0.01))*100.0, step=0.05, key=f"prop_max_{selected}"
            ) / 100.0
        with pc4:
            prop_enabled = st.checkbox("Prop Desk aktiv", value=bool(prop.get("enabled", 1)), key=f"prop_enabled_{selected}")
        if st.button("Prop Desk Einstellungen speichern", key=f"save_prop_{selected}"):
            if prop_default > prop_max:
                st.error("Standard Risk darf nicht über dem Max Risk liegen.")
            else:
                if is_remote:
                    remote_update_prop_account(
                        remote_client,
                        selected, starting_capital=prop_start, default_risk_pct=prop_default, max_risk_pct=prop_max, enabled=prop_enabled
                    )
                else:
                    update_prop_account(
                        selected, starting_capital=prop_start, default_risk_pct=prop_default, max_risk_pct=prop_max, enabled=prop_enabled, db_path=db_path
                    )
                st.success("Prop Desk Einstellungen gespeichert. Änderungen am Risk gelten nur für neue Trades.")
                st.rerun()
        st.caption("Sobald der erste Prop-Trade allokiert wurde, ist das Startkapital gesperrt. So bleiben historische Lots und USD-Risiken unveränderlich.")
    except Exception as exc:
        st.warning(f"Prop Desk Konto konnte nicht geladen werden: {exc}")

section_line("Eigenes Passwort", "ADMIN-Konto")
with st.form("own_password"):
    old_pw = st.text_input("Aktuelles Passwort", type="password")
    new_pw = st.text_input("Neues Passwort", type="password")
    new_pw2 = st.text_input("Neues Passwort wiederholen", type="password")
    change = st.form_submit_button("Eigenes Passwort ändern")
if change:
    if new_pw != new_pw2:
        st.error("Die neuen Passwörter stimmen nicht überein.")
    else:
        try:
            ok = remote_client.change_own_password(old_pw, new_pw) if is_remote else change_own_password(str(current["trader_id"]), old_pw, new_pw, db_path=db_path)
            if ok:
                st.success("Passwort geändert.")
            else:
                st.error("Aktuelles Passwort ist falsch.")
        except Exception as exc:
            st.error(str(exc))
