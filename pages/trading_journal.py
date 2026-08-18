from __future__ import annotations
# V3.14.6 · JOURNAL ML SNAPSHOT & EXECUTION RR

import numpy as np
import pandas as pd
import streamlit as st

from src.deployment_mode import REMOTE_GATEWAY, deployment_config_from_mapping
from src.journal_gateway_client import JournalGatewayClient, JournalGatewayError, config_from_mapping as gateway_config_from_mapping
from src.mt5_account import MT5BridgeError, MT5ConfigError, MT5ConnectionError, MT5UnavailableError, config_from_mapping
from src.mt5_history import MT5HistoryError
from src.journal_execution_metrics import effective_rr, rr_source
from src.journal_strategy_view import find_strategy_logic_blocks
from src.outcome_tracker import sync_trade_outcomes
from src.price_units import mt5_price_to_plan, price_factor_to_mt5
from src.style import apply_style, context_strip, definition, metric_card, page_header, section_line
from src.trade_journal import (
    append_trade_event,
    build_feature_matrix,
    get_trade_events,
    get_trade_outcome,
    get_trade_snapshot,
    initialize_journal,
    journal_summary,
    list_trade_plans,
    resolve_db_path,
    void_trade_plan,
)
from src.trader_auth import list_traders
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


def _fmt_r(value):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{x:+.2f}R" if np.isfinite(x) else "—"


def _short_id(value: str) -> str:
    return str(value)[:8]


def _entry_display(row) -> str | float:
    if str(row.get("order_type") or "").upper() != "MARKET":
        return row.get("entry")
    execution = row.get("execution_price")
    try:
        execution = float(execution)
    except (TypeError, ValueError):
        execution = np.nan
    if np.isfinite(execution):
        display = mt5_price_to_plan(row.get("cfd_symbol"), execution)
        return f"AUTO → {display:g}" if display is not None else "AUTO"
    return "AUTO"


page_header(
    "Trading · Journal",
    "Journal",
    "Geplant, aktiv, geschlossen oder verworfen – ohne technische Details im Weg.",
    "V3.9.0 · CLEAN JOURNAL",
)

deployment = deployment_config_from_mapping(_secret_section("deployment"))
is_remote = deployment.mode == REMOTE_GATEWAY
journal_section = _secret_section("journal")
mt5_section = _secret_section("mt5")
db_path = None
remote_client = None

try:
    if is_remote:
        gateway_cfg = gateway_config_from_mapping(_secret_section("gateway"))
        remote_client = JournalGatewayClient(gateway_cfg, str(st.session_state.get("auth_gateway_token", "") or ""))
    else:
        db_path = resolve_db_path(journal_section)
        initialize_journal(db_path)
except (ValueError, JournalGatewayError) as exc:
    st.error(str(exc))
    st.stop()

trader_filter_id: str | None = str(trader.get("trader_id", ""))
trader_filter_label = str(trader.get("display_name", "Trader"))

try:
    if is_admin:
        trader_table = remote_client.list_traders(active_only=False) if is_remote else list_traders(db_path=db_path, active_only=False)
        choices = ["__ALL__"] + trader_table.get("trader_id", pd.Series(dtype=str)).astype(str).tolist()
        label_map = {"__ALL__": "Alle Trader"}
        for _, trow in trader_table.iterrows():
            label_map[str(trow["trader_id"])] = f"{trow['display_name']} · {trow['username']}"
        selected_trader = st.selectbox("Journal-Sicht", choices, format_func=lambda x: label_map.get(x, x))
        trader_filter_id = None if selected_trader == "__ALL__" else selected_trader
        trader_filter_label = label_map.get(selected_trader, "Alle Trader")

    summary = remote_client.journal_summary(trader_id=trader_filter_id) if is_remote else journal_summary(db_path=db_path, trader_id=trader_filter_id)
except JournalGatewayError as exc:
    st.error(str(exc))
    st.stop()

context_strip([
    ("Sicht", trader_filter_label),
    ("Pläne", str(summary.get("plans", 0))),
    ("Simulation", str(summary.get("simulation", 0))),
    ("Closed", str(summary.get("closed", 0))),
    ("Verworfen", str(summary.get("voided", 0))),
])

m1, m2, m3, m4 = st.columns(4)
with m1:
    metric_card("GEPLANT", str(summary.get("planned", 0)), "Limit/Market noch nicht abgeschlossen")
with m2:
    metric_card("AKTIV", str(summary.get("active", 0)), "Entry bereits ausgelöst")
with m3:
    metric_card("CLOSED", str(summary.get("closed", 0)), f"Expectancy {_fmt_r(summary.get('expectancy_r'))}")
with m4:
    metric_card("EXPIRED / ?", f"{summary.get('expired', 0)} / {summary.get('ambiguous', 0)}", "nicht ausgelöst / intrabar unklar")

section_line("Execution & Outcomes", "Live Entry + History Safety-Net")

if is_remote:
    st.info(
        "Die Online-Instanz liest den aktuellen Journal-Stand vom lokalen Gateway. "
        "Der MT5-Outcome-Sync ist hier absichtlich deaktiviert: Er wird ausschließlich auf deinem Mac in der LOCAL-Instanz gestartet."
    )
else:
    def _run_outcome_sync():
        try:
            cfg = config_from_mapping(mt5_section)
            with st.spinner("MT5-Historie wird nachgeladen und Trade-Outcomes werden chronologisch ausgewertet …"):
                result = sync_trade_outcomes(
                    cfg, db_path=db_path, max_trades=250, timeout_seconds=15.0, trader_id=trader_filter_id
                )
            counts = result.get("status_counts", {})
            by_tf = result.get("bars_loaded_by_timeframe", {})
            req_tf = result.get("remote_requests_by_timeframe", {})
            st.success(
                f"{result.get('checked', 0)} offene Pläne geprüft · {result.get('symbols_checked', 0)} CFD-Symbole · "
                f"{result.get('remote_requests', 0)} neue MT5-History-Anfragen · "
                f"H1 {by_tf.get('H1', 0)} Bars / {req_tf.get('H1', 0)} Requests · "
                f"MARKET-Safety-Net M1 {req_tf.get('M1', 0)} · Exit-Fallback M5/M1"
            )
            st.caption(
                f"Status nach Sync: PLANNED {counts.get('PLANNED', 0)} · ACTIVE {counts.get('ACTIVE', 0)} · "
                f"CLOSED {counts.get('CLOSED', 0)} · EXPIRED {counts.get('EXPIRED', 0)} · "
                f"AMBIGUOUS {counts.get('AMBIGUOUS', 0)}. "
                f"Cache-only: {result.get('cache_only_requests', 0)} Anfragen konnten vollständig lokal beantwortet werden."
            )
            st.session_state[f"v370_outcome_synced_{trader_filter_id or 'ALL'}"] = True
            st.rerun()
        except (MT5ConfigError, MT5UnavailableError, MT5BridgeError, MT5ConnectionError, MT5HistoryError, ValueError) as exc:
            st.error(str(exc))
            st.caption("Der lokale Gateway-Watcher kann MARKET- und LIMIT-Entries über frische Bid/Ask-Quotes sofort aktivieren. Der History-Sync bleibt das Sicherheitsnetz: MARKET-Fills werden bei Bedarf mit M1 rekonstruiert; danach läuft das normale H1-Tracking mit M5/M1 nur bei Ambiguität.")

    auto_sync = st.toggle("Beim ersten Öffnen des Journals automatisch nachholen", value=False, help="Für Swing Trading ist manueller Sync sinnvoll. Aus: nur auf Knopfdruck synchronisieren.")
    if st.button("MT5 Outcomes jetzt synchronisieren", type="primary", use_container_width=True):
        _run_outcome_sync()
    if auto_sync and not st.session_state.get(f"v370_outcome_synced_{trader_filter_id or 'ALL'}", False) and summary.get("plans", 0) > 0:
        _run_outcome_sync()

with st.expander("Datenbank & Forschungsprinzip", expanded=False):
    if is_remote:
        st.code("ONLINE → HTTPS Gateway → lokale Master-SQLite")
        definition(
            "Die Online-App besitzt keine eigene Journal-Datenbank. Plan, Snapshot, Events und Outcomes werden vom lokalen Gateway gelesen/geschrieben. "
            "MT5 und die SQLite-Masterdatei bleiben auf dem Mac."
        )
    else:
        st.code(str(db_path))
        definition(
            "Trade-Plan und Snapshot sind append-only/immutable. Entry-/SL-/TP-Änderungen werden als Events ergänzt. "
            "Die Outcome-Tabelle ist davon getrennt und darf aktualisiert werden, wenn neue Marktpreise eintreffen."
        )

with st.expander("Research / ML Feature-Matrix", expanded=False):
    if is_remote:
        st.caption("Der vollständige ML-Export bleibt lokal beim ADMIN, damit die Master-Datenbank nicht als Massendownload über das öffentliche Gateway exponiert wird.")
    else:
        matrix = build_feature_matrix(db_path=db_path, include_text=False, include_outcomes=True, trader_id=trader_filter_id)
        st.caption(
            f"{len(matrix)} gültige Trades × {len(matrix.columns)} Spalten. Verworfene Fehleinträge sind ausgeschlossen. "
            "Plan-Time-Features beginnen mit feature__; spätere Zielvariablen mit label__."
        )
        if not matrix.empty:
            csv_data = matrix.to_csv(index=False).encode("utf-8")
            st.download_button("Feature-Matrix als CSV exportieren", data=csv_data, file_name="cot_trade_feature_matrix.csv", mime="text/csv")

section_line("Trades", "REAL · SIMULATION · SKIPPED")
filter_type = st.radio("Filter", ["ALLE", "REAL", "SIMULATION", "SKIPPED"], horizontal=True)
show_voided = st.toggle("Verworfene Fehleinträge anzeigen", value=False, help="VOID-Pläne bleiben revisionssicher gespeichert, zählen aber nicht zu Statistik, Prop Desk, Outcome-Sync oder ML.")
try:
    if is_remote:
        plans = remote_client.list_trade_plans(
            limit=1000,
            plan_type=None if filter_type == "ALLE" else filter_type,
            trader_id=trader_filter_id,
        )
    else:
        plans = list_trade_plans(
            db_path=db_path,
            limit=1000,
            plan_type=None if filter_type == "ALLE" else filter_type,
            trader_id=trader_filter_id,
        )
except JournalGatewayError as exc:
    st.error(str(exc))
    st.stop()

if not plans.empty and not show_voided:
    _status_series = plans.get("lifecycle_status", pd.Series(index=plans.index, dtype=object)).fillna("PLANNED").astype(str).str.upper()
    plans = plans.loc[~_status_series.eq("VOID")].copy()

if plans.empty:
    st.info("Noch keine Trade-Pläne gespeichert.")
    st.page_link("pages/trade_planner.py", label="Ersten Trade planen", icon=":material/edit_note:")
    st.stop()

view = plans.copy()
view["created"] = pd.to_datetime(view["created_at_local"], errors="coerce").dt.strftime("%d.%m.%Y %H:%M")
view["ID"] = view["trade_id"].map(_short_id)
view["EffectiveRR"] = view.apply(effective_rr, axis=1)
view["R:R"] = view["EffectiveRR"].map(
    lambda x: f"{float(x):.2f}R" if x is not None and pd.notna(x) else "—"
)
view["Result"] = pd.to_numeric(view.get("result_r"), errors="coerce").map(_fmt_r)
view["Status"] = view.get("lifecycle_status", pd.Series(index=view.index, dtype=object)).fillna("PLANNED")
view["Trader"] = view.get("trader_display_name", pd.Series(index=view.index, dtype=object)).fillna("Legacy")
view["EntryDisplay"] = view.apply(_entry_display, axis=1)
columns = ["created", "ID"]
if is_admin and trader_filter_id is None:
    columns.append("Trader")
columns += ["cfd_symbol", "side", "plan_type", "order_type", "Status", "timeframe", "EntryDisplay", "stop", "target", "R:R", "Result"]
st.dataframe(
    view[columns].rename(columns={
        "created": "Zeit", "cfd_symbol": "Symbol", "side": "Richtung", "plan_type": "Typ", "order_type": "Order",
        "timeframe": "TF", "EntryDisplay": "Entry", "stop": "SL", "target": "TP",
    }),
    use_container_width=True,
    hide_index=True,
)

section_line("Trade inspizieren", "Snapshot, Events und Datenintegrität")
labels = {}
for _, row in plans.iterrows():
    owner = f"{row.get('trader_display_name') or 'Legacy'} · " if is_admin and trader_filter_id is None else ""
    labels[row["trade_id"]] = f"{owner}{row['cfd_symbol']} · {row['side']} · {row['plan_type']} · {_short_id(row['trade_id'])}"
selected_id = st.selectbox("Trade", list(labels.keys()), format_func=lambda x: labels[x])
row = plans[plans["trade_id"] == selected_id].iloc[0]

c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("SYMBOL", str(row["cfd_symbol"]), str(row["side"]))
with c2:
    entry_label = _entry_display(row)
    metric_card("ENTRY / SL", f"{entry_label} / {row['stop']}", f"TP {row['target'] if pd.notna(row['target']) else '—'}")
with c3:
    _detail_rr = effective_rr(row)
    _detail_rr_label = "EXECUTION R:R" if rr_source(row) == "EXECUTION" else "PLAN R:R"
    metric_card(
        _detail_rr_label,
        f"{float(_detail_rr):.2f}R" if _detail_rr is not None and np.isfinite(float(_detail_rr)) else "—",
        "echter MARKET-Fill → SL/TP" if _detail_rr_label == "EXECUTION R:R" else str(row["timeframe"]),
    )
with c4:
    status = str(row.get("lifecycle_status") or "PLANNED") if pd.notna(row.get("lifecycle_status")) else "PLANNED"
    metric_card("OUTCOME", status, _fmt_r(row.get("result_r")))

with st.expander(f"TradingView Chart · {row['cfd_symbol']}", expanded=False):
    tv_symbol = render_tradingview_chart(str(row["cfd_symbol"]), timeframe=str(row.get("timeframe") or "4H"), height=540)
    st.caption(
        f"TradingView-Mapping: {row['cfd_symbol']} → {tv_symbol}. Visueller Referenzchart; "
        "der gespeicherte Trade und sein Outcome bleiben an die MT5-CFD-Historie gebunden."
    )

try:
    snapshot = remote_client.get_trade_snapshot(selected_id) if is_remote else get_trade_snapshot(selected_id, db_path=db_path)
    outcome = remote_client.get_trade_outcome(selected_id) if is_remote else get_trade_outcome(selected_id, db_path=db_path)
    events = remote_client.get_trade_events(selected_id) if is_remote else get_trade_events(selected_id, db_path=db_path)
except JournalGatewayError as exc:
    st.error(str(exc))
    st.stop()

research = snapshot.get("research", {}) if isinstance(snapshot, dict) else {}
risk = snapshot.get("risk", {}) if isinstance(snapshot, dict) else {}
approval = risk.get("pretrade_approval", {}) if isinstance(risk, dict) else {}

s1, s2, s3 = st.columns(3)
with s1:
    risk_label = str(approval.get("status", "—"))
    risk_note = "Status beim Speichern" if approval else "ADMIN-only / nicht gespeichert"
    metric_card("RISK STATUS", risk_label, risk_note)
with s2:
    conf = None
    if isinstance(research, dict):
        conf = ((research.get("legacy") or {}).get("confirmation_4of4") or {}).get("label")
        if conf is None:
            conf = ((research.get("pair_bias") or {}).get("display"))
    metric_card("COT SNAPSHOT", str(conf or "gespeichert"), "historischer Entscheidungszustand")
with s3:
    meta = snapshot.get("meta", {})
    metric_card("SNAPSHOT VERSION", str(meta.get("snapshot_schema_version", "1.0")), "Hash-integritätsgeprüft")

if outcome:
    section_line("Outcome", "automatisch aus MT5 CFD-Historie")
    o1, o2, o3, o4 = st.columns(4)
    with o1:
        metric_card("STATUS", str(outcome.get("lifecycle_status") or "PLANNED"), str(outcome.get("data_timeframe") or "—"))
    with o2:
        metric_card("RESULT", _fmt_r(outcome.get("result_r")), str(outcome.get("first_exit") or "offen"))
    with o3:
        metric_card("MFE", _fmt_r(outcome.get("mfe_r")), "maximal favorable")
    with o4:
        metric_card("MAE", _fmt_r(outcome.get("mae_r")), "maximal adverse")
    execution_price = outcome.get("execution_price")
    if execution_price is not None and pd.notna(execution_price):
        execution_value = float(execution_price)
        fill_tf = str(outcome.get("fill_timeframe") or outcome.get("data_timeframe") or "—")
        if str(row.get("order_type") or "").upper() == "MARKET":
            display_execution = mt5_price_to_plan(row.get("cfd_symbol"), execution_value)
            factor = price_factor_to_mt5(row.get("cfd_symbol"))
            unit_suffix = f" · MT5 {execution_value:g} (×{factor:g})" if factor != 1.0 else ""
            st.caption(
                f"MARKET Auto-Fill: {display_execution:g}{unit_suffix} · Auflösung {fill_tf}. "
                "Kein manueller Entry wird für die Ausführung verwendet; Prop Desk und Outcome verwenden ausschließlich den tatsächlichen Fill."
            )
    if str(outcome.get("lifecycle_status") or "") == "AMBIGUOUS":
        st.warning("Intrabar-Reihenfolge bleibt selbst nach M1-Auflösung unklar. Der Tracker erfindet deshalb kein SL/TP-Ergebnis.")
    fwd = []
    for days in (1, 3, 5, 10, 20, 40, 60):
        value = outcome.get(f"forward_{days}d")
        if value is not None and pd.notna(value):
            fwd.append(f"{days}T {float(value)*100:+.2f}%")
    if fwd:
        st.caption("Directional Forward Return · " + " · ".join(fwd))

_strategy_blocks = find_strategy_logic_blocks(snapshot)
with st.expander("Strategie-Snapshot · beim Trade eingefroren", expanded=False):
    if not _strategy_blocks:
        st.caption(
            "Älterer Trade: Für diesen Plan existiert noch kein versionierter V3.14.6-Strategie-Snapshot. "
            "Er wird nicht rückwirkend mit heutiger Logik beschriftet."
        )
    else:
        for _strategy_path, _logic in _strategy_blocks:
            _macro = dict(_logic.get("macro") or {})
            _micro = dict(_logic.get("micro") or {})
            _decision = dict(_logic.get("decision") or {})
            _stage = dict(_macro.get("stage") or {})
            _micro_age = _micro.get("age_weeks", "—")
            _micro_status = "frisch" if _micro.get("fresh") else f"Alter {_micro_age}W"
            _stage_text = (
                f" · Stage {_stage.get('stage')} {_stage.get('label', '')}"
                if _stage else ""
            )
            st.markdown(
                f"**{_logic.get('logic_version', '—')}** · `{_strategy_path}`  \n"
                f"**Makro:** {_macro.get('phase') or '—'} · {_macro.get('state') or '—'}{_stage_text}  \n"
                f"**Mikro:** {_micro.get('label') or '—'} · {_micro_status}  \n"
                f"**Entscheidung:** {_decision.get('bias') or '—'} · "
                f"{_decision.get('plan') or '—'} · {_decision.get('signal') or '—'}"
            )
            st.caption(
                "156W = Struktur/Release · 26W = eventbasierter 90/10 Fresh-Micro-Trigger · "
                "Seasonality = Confluence only. Rohwerte bleiben für ML im eingefrorenen Snapshot."
            )
            st.json(_logic, expanded=False)

with st.expander("Vollständigen eingefrorenen Snapshot anzeigen", expanded=False):
    st.json(snapshot, expanded=False)

status_now = str(outcome.get("lifecycle_status") or "PLANNED").upper() if outcome else "PLANNED"
triggered_now = bool(outcome.get("entry_triggered") or 0) if outcome else False
owner_id = str(row.get("trader_id") or "")
can_void = status_now == "PLANNED" and not triggered_now and (is_admin or owner_id == str(trader.get("trader_id") or ""))

if can_void:
    with st.expander("Fehleintrag verwerfen", expanded=False):
        st.warning(
            "Nur für echte Eingabefehler, z. B. falsches Asset, falsche Richtung oder falsche Levels. "
            "Der Datensatz wird nicht gelöscht, sondern revisionssicher auf VOID gesetzt."
        )
        void_reason = st.selectbox(
            "Grund",
            ["Falsches Asset", "Falsche Richtung", "Falscher Entry / SL / TP", "Doppelter Eintrag", "Sonstiger Eingabefehler"],
            key=f"void_reason_{selected_id}",
        )
        void_details = st.text_input("Optionaler Zusatz", key=f"void_details_{selected_id}", placeholder="kurze Erklärung")
        confirm_void = st.checkbox("Ich bestätige: Der Trade wurde noch nicht ausgelöst und ist ein Fehleintrag.", key=f"void_confirm_{selected_id}")
        if st.button("Fehleintrag verwerfen", type="secondary", disabled=not confirm_void, key=f"void_button_{selected_id}"):
            reason_text = void_reason + (f" · {void_details.strip()}" if void_details.strip() else "")
            try:
                if is_remote:
                    remote_client.void_trade_plan(selected_id, reason_text)
                else:
                    void_trade_plan(
                        selected_id, reason=reason_text, actor_trader_id=str(trader.get("trader_id") or ""), db_path=db_path
                    )
                st.success("Fehleintrag wurde auf VOID gesetzt und aus Outcome-Sync, Prop Desk und ML ausgeschlossen.")
                st.rerun()
            except (JournalGatewayError, ValueError, PermissionError, KeyError) as exc:
                st.error(str(exc))
elif status_now == "VOID":
    st.info("Dieser Plan wurde als Fehleintrag verworfen (VOID). Er bleibt nur für Audit/Nachvollziehbarkeit gespeichert.")

section_line("Event-Log", "Änderungen werden angehängt, nicht überschrieben")
if not events.empty:
    ev = events[["occurred_at_local", "event_type", "source", "payload_json"]].copy()
    ev["occurred_at_local"] = pd.to_datetime(ev["occurred_at_local"], errors="coerce").dt.strftime("%d.%m.%Y %H:%M:%S")
    st.dataframe(ev.rename(columns={"occurred_at_local": "Zeit", "event_type": "Event", "source": "Quelle", "payload_json": "Payload"}), use_container_width=True, hide_index=True)

with st.expander("Manuelles Event protokollieren", expanded=False):
    event_type = st.selectbox(
        "Event",
        ["TRADE_TAKEN", "ENTRY_CHANGED", "STOP_CHANGED", "TARGET_CHANGED", "MANUAL_EXIT", "NOTE"],
    )
    payload_text = st.text_area("Details", placeholder="z. B. neuer SL, neuer Entry oder Begründung")
    if st.button("Event anhängen"):
        try:
            if is_remote:
                remote_client.append_trade_event(selected_id, event_type, {"note": payload_text})
            else:
                append_trade_event(selected_id, event_type, {"note": payload_text}, db_path=db_path)
            st.success("Event wurde append-only gespeichert.")
            st.rerun()
        except JournalGatewayError as exc:
            st.error(str(exc))

st.info(
    "Der Outcome Tracker prüft regulär nur PLANNED/ACTIVE-Pläne. Historie wird pro CFD/Timeframe lokal in SQLite gecacht und dedupliziert. "
    "Die Online-App löst keine MT5-History-Abfragen aus; der manuelle Outcome-Sync bleibt ausschließlich auf dem Mac."
)
