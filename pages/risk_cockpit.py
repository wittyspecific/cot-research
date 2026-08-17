from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.ftmo_risk import FTMORiskConfig, risk_cockpit_summary, risk_config_from_mapping
from src.mt5_account import (
    MT5BridgeError,
    MT5ConfigError,
    MT5ConnectionError,
    MT5UnavailableError,
    config_from_mapping,
    get_mt5_snapshot,
)
from src.style import apply_style, context_strip, metric_card, page_header, section_line


apply_style()


def _money(value, currency="USD"):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    if not np.isfinite(x):
        return "—"
    symbol = "$" if str(currency).upper() == "USD" else f"{currency} "
    return f"{symbol}{x:,.0f}"


def _pct(value, digits=2):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    if not np.isfinite(x):
        return "—"
    return f"{100.0 * x:.{digits}f}%"


def _secret_section(name: str) -> dict:
    try:
        section = st.secrets.get(name, {})
        return dict(section) if section else {}
    except Exception:
        return {}


def _status_action(status: str) -> tuple[str, str]:
    if status == "RED":
        return "RED · KEINE NEUEN TRADES", "Erst bestehendes Risiko reduzieren, bevor neues Risiko hinzukommt."
    if status == "YELLOW":
        return "YELLOW · NUR SELEKTIV", "Risk-Budget ist knapp. Neue Trades nur nach vollständigem Pre-Trade-Check."
    return "GREEN · RISIKO VERFÜGBAR", "Neue Trades sind grundsätzlich möglich; jeder Trade bleibt einzeln zu prüfen."


def _render_status(status: str, headline: str, detail: str):
    text = f"**{headline}** — {detail}"
    if status == "RED":
        st.error(text)
    elif status == "YELLOW":
        st.warning(text)
    else:
        st.success(text)


def _driver_note(row: pd.Series) -> str:
    util = row.get("utilization")
    remaining = row.get("remaining")
    if pd.notna(remaining) and float(remaining) < 0:
        return f"{_pct(util, 0)} des Limits · {_money(abs(float(remaining)))} über Limit"
    return f"{_pct(util, 0)} des Limits · {_money(max(float(remaining), 0.0) if pd.notna(remaining) else np.nan)} frei"


page_header(
    "Admin · Risiko",
    "Risk Cockpit",
    "Aktuelle Portfolio-Auslastung und Risikolimits auf einen Blick.",
    "V3.9.0 · RISK COCKPIT",
)

mt5_section = _secret_section("mt5")
risk_section = _secret_section("risk")
try:
    mt5_config = config_from_mapping(mt5_section)
    risk_cfg: FTMORiskConfig = risk_config_from_mapping(risk_section)
except MT5ConfigError as exc:
    st.error(str(exc))
    st.stop()

if not mt5_section and mt5_config.mode != "bridge":
    st.info("Noch keine lokale MT5-Konfiguration gefunden. Bitte zuerst Portfolio & Risk einrichten.")
    st.page_link("pages/portfolio_risk.py", label="Portfolio & Risk öffnen", icon=":material/settings:")
    st.stop()

try:
    snapshot = get_mt5_snapshot(mt5_config)
except (MT5UnavailableError, MT5BridgeError, MT5ConnectionError, MT5ConfigError) as exc:
    st.error(str(exc))
    st.page_link("pages/portfolio_risk.py", label="Verbindung prüfen", icon=":material/settings:")
    st.stop()

account = snapshot["account"]
positions = snapshot["positions"].copy()
currency = account.get("currency") or "USD"
summary = risk_cockpit_summary(account, positions, risk_cfg)
state = summary["state"]

captured = snapshot.get("captured_at")
captured_text = (
    pd.Timestamp(captured).strftime("%d.%m.%Y %H:%M:%S")
    if captured is not None and not pd.isna(captured)
    else "—"
)
context_strip(
    [
        ("Equity", _money(state["equity"], currency)),
        ("Offene Positionen", str(len(positions))),
        ("FTMO aktuell", "OK" if summary["ftmo_current_ok"] else "LIMIT"),
        ("Snapshot", captured_text),
    ]
)

headline, detail = _status_action(summary["status"])
_render_status(summary["status"], headline, detail)

m1, m2, m3, m4 = st.columns(4)
with m1:
    metric_card("DAILY BUFFER", _money(state["daily_buffer"], currency), "bis aktuelle FTMO-Daily-Grenze")
with m2:
    metric_card("MAX-LOSS BUFFER", _money(state["total_buffer"], currency), "bis $90k FTMO-Floor")
with m3:
    metric_card(
        "OPEN STOP RISK",
        _money(summary["portfolio_risk"], currency),
        f"{_pct(state['known_open_stop_risk_pct'])} · Limit {_money(summary['portfolio_limit'], currency)}",
    )
with m4:
    free = max(float(summary["portfolio_remaining"]), 0.0)
    over = max(-float(summary["portfolio_remaining"]), 0.0)
    metric_card(
        "NEUE RISK CAPACITY",
        _money(free, currency),
        f"{_money(over, currency)} über Portfolio-Limit" if over > 0 else "freies Portfolio-Stop-Risk",
    )

section_line("Die 3 größten Risikotreiber", "nur das Wesentliche")
drivers = summary["drivers"].head(3)
if drivers.empty:
    st.caption("Keine offenen Stop-Risiken vorhanden.")
else:
    cols = st.columns(len(drivers))
    for col, (_, row) in zip(cols, drivers.iterrows()):
        with col:
            metric_card(
                f"{row['label']} · {row['kind'].upper()}",
                _money(row["risk"], currency),
                _driver_note(row),
            )

section_line("Risk Capacity nach Bereich", "0 = aktuell kein neues Risiko")
clusters = summary["cluster_capacity"]
preferred = ["FX", "Energy", "Metals", "Indices", "Other", "Crypto"]
cluster_map = {str(r["cluster"]): r for _, r in clusters.iterrows()} if not clusters.empty else {}
visible = [name for name in preferred if name in cluster_map]
if not visible:
    st.caption("Keine Cluster-Risiken vorhanden.")
else:
    cols = st.columns(min(len(visible), 5))
    for i, name in enumerate(visible[:5]):
        row = cluster_map[name]
        remaining = float(row.get("remaining", 0.0))
        risk = float(row.get("stop_risk", 0.0))
        limit = float(row.get("limit", 0.0))
        with cols[i]:
            metric_card(
                name.upper(),
                _money(max(remaining, 0.0), currency),
                f"Risk {_money(risk, currency)} / {_money(limit, currency)}",
            )

# Only surface the most decision-relevant stress warning; keep detailed numbers on the full page.
if np.isfinite(summary["all_stops_daily_safety"]) and summary["all_stops_daily_safety"] < 0:
    st.error(
        f"All-Stops-Szenario liegt {_money(abs(summary['all_stops_daily_safety']), currency)} "
        "unter dem internen Daily-Sicherheitsfloor."
    )
elif np.isfinite(summary["weekend_total_safety"]) and summary["weekend_total_safety"] < 0:
    st.warning(
        f"Weekend-Stress liegt {_money(abs(summary['weekend_total_safety']), currency)} "
        "unter dem internen Max-Loss-Sicherheitsfloor."
    )

st.page_link(
    "pages/portfolio_risk.py",
    label="Alle Risk-Details & Pre-Trade-Rechner öffnen",
    icon=":material/analytics:",
    use_container_width=True,
)
