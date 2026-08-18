from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from src.deployment_mode import REMOTE_GATEWAY, deployment_config_from_mapping
from src.journal_gateway_client import JournalGatewayClient, JournalGatewayError, config_from_mapping as gateway_config_from_mapping
from src.mt5_account import config_from_mapping as mt5_config_from_mapping, read_bridge_quotes
from src.paper_position_management import (
    list_active_paper_positions,
    list_paper_management_events,
    manual_close_from_quotes,
    set_break_even,
)
from src.price_units import mt5_price_to_plan
from src.style import page_header, section_line
from src.trade_journal import resolve_db_path


def _secret_section(name: str) -> dict:
    try:
        return dict(st.secrets.get(name, {}) or {})
    except Exception:
        return {}


def _finite(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


page_header(
    "Trading · Simulation",
    "Positionsmanagement",
    "Offene Demo-Positionen verwalten: Break Even oder manuell schließen.",
    "V3.15.0 · PAPER POSITION MANAGEMENT",
)
st.caption(
    "Nur SIMULATION. Es wird keine MT5-Order geändert oder geschlossen. "
    "FTMO/MT5 liefert ausschließlich read-only Bid/Ask-Quotes."
)

trader = dict(st.session_state.get("auth_trader") or {})
trader_id = str(trader.get("trader_id", "") or "")
if not trader_id:
    st.error("Trader-Sitzung fehlt.")
    st.stop()

deployment = deployment_config_from_mapping(_secret_section("deployment"))
is_remote = deployment.mode == REMOTE_GATEWAY
remote_client = None
db_path = None
if is_remote:
    remote_client = JournalGatewayClient(
        gateway_config_from_mapping(_secret_section("gateway")),
        st.session_state.get("auth_gateway_token"),
    )
else:
    db_path = resolve_db_path(_secret_section("journal"))

watcher_cfg = _secret_section("execution_watcher")
max_tick_age_seconds = float(watcher_cfg.get("max_tick_age_seconds", 5.0) or 5.0)

try:
    positions = (
        remote_client.paper_positions()
        if is_remote
        else list_active_paper_positions(trader_id=trader_id, db_path=db_path)
    )
except Exception as exc:
    st.error(f"Offene Simulationen konnten nicht geladen werden: {exc}")
    st.stop()

section_line("Offene Positionen", "SIMULATION · ACTIVE")

if positions.empty:
    st.info("Keine offenen SIMULATION-Positionen vorhanden.")
else:
    display = positions.copy()
    display["Trade"] = display["trade_id"].astype(str).str[:8]
    display["Markt"] = display["cfd_symbol"].astype(str)
    display["Richtung"] = display["side"].astype(str).str.upper()
    display["Entry"] = [
        mt5_price_to_plan(symbol, value) if _finite(value) is not None else None
        for symbol, value in zip(display["cfd_symbol"], display["execution_price"])
    ]
    display["SL ursprünglich"] = pd.to_numeric(display["stop"], errors="coerce")
    display["SL aktuell"] = [
        mt5_price_to_plan(symbol, managed) if _finite(managed) is not None else original
        for symbol, managed, original in zip(
            display["cfd_symbol"], display["current_stop_mt5"], display["stop"]
        )
    ]
    display["TP"] = pd.to_numeric(display["target"], errors="coerce")
    display["Management"] = [
        "BREAK EVEN" if int(_finite(value) or 0) == 1 else "INITIAL SL"
        for value in display["break_even_active"]
    ]
    st.dataframe(
        display[["Trade", "Markt", "Richtung", "Entry", "SL ursprünglich", "SL aktuell", "TP", "Management"]],
        hide_index=True,
        width="stretch",
    )

    labels = {
        str(row["trade_id"]): f'{row["cfd_symbol"]} · {str(row["side"]).upper()} · {str(row["trade_id"])[:8]}'
        for _, row in positions.iterrows()
    }
    selected_ids = st.multiselect(
        "Positionen auswählen",
        options=list(labels),
        format_func=lambda trade_id: labels.get(trade_id, trade_id),
    )

    c1, c2, c3 = st.columns([0.30, 0.40, 0.30])
    with c1:
        be_clicked = st.button(
            "Break Even setzen",
            type="primary",
            use_container_width=True,
            disabled=not selected_ids,
        )
    with c2:
        close_confirm = st.checkbox(
            "Schließen bestätigen",
            value=False,
            help="LONG wird zum aktuellen Bid, SHORT zum aktuellen Ask geschlossen.",
        )
    with c3:
        close_clicked = st.button(
            "Position schließen",
            use_container_width=True,
            disabled=not selected_ids or not close_confirm,
        )

    if be_clicked:
        ok = 0
        for trade_id in selected_ids:
            try:
                result = (
                    remote_client.paper_break_even(trade_id)
                    if is_remote
                    else set_break_even(trade_id, actor_trader_id=trader_id, db_path=db_path)
                )
                ok += 1
                if result.get("already_active"):
                    st.info(f"{labels[trade_id]} ist bereits auf Break Even.")
            except Exception as exc:
                st.error(f"{labels.get(trade_id, trade_id)}: {exc}")
        if ok:
            st.success(f"Break Even für {ok} Position(en) verarbeitet.")
            st.rerun()

    if close_clicked:
        ok = 0
        quotes = None
        if not is_remote:
            try:
                quotes = read_bridge_quotes(
                    mt5_config_from_mapping(_secret_section("mt5")),
                    max_age_seconds=max(3, int(max_tick_age_seconds)),
                )
            except Exception as exc:
                st.error(f"MT5-Quotes konnten nicht geladen werden: {exc}")
                st.stop()
        for trade_id in selected_ids:
            try:
                if is_remote:
                    remote_client.paper_manual_close(trade_id)
                else:
                    manual_close_from_quotes(
                        trade_id,
                        actor_trader_id=trader_id,
                        quotes=quotes,
                        db_path=db_path,
                        max_tick_age_seconds=max_tick_age_seconds,
                    )
                ok += 1
            except Exception as exc:
                st.error(f"{labels.get(trade_id, trade_id)}: {exc}")
        if ok:
            st.success(f"{ok} Position(en) intern geschlossen.")
            st.rerun()

st.caption(
    "Break Even gilt erst ab dem Klick-Zeitpunkt. Frühere Bars oder Quotes können "
    "den nachträglich gesetzten Stop nicht rückwirkend auslösen. Manuelle Exits "
    "werden mit Bid/Ask, Zeitstempel und R-Multiple gespeichert."
)

with st.expander("Management-Audit", expanded=False):
    try:
        events = (
            remote_client.paper_management_events(limit=100)
            if is_remote
            else list_paper_management_events(trader_id=trader_id, limit=100, db_path=db_path)
        )
        if events.empty:
            st.caption("Noch keine Management-Aktionen.")
        else:
            cols = [
                col for col in [
                    "occurred_at_utc", "action", "symbol", "side",
                    "old_stop_mt5", "new_stop_mt5", "exit_price_mt5", "result_r",
                ] if col in events.columns
            ]
            st.dataframe(events[cols], hide_index=True, width="stretch")
    except Exception as exc:
        st.warning(f"Audit konnte nicht geladen werden: {exc}")
