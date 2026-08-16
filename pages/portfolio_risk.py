from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from src.ftmo_risk import (
    FTMORiskConfig,
    cluster_risk_table,
    ftmo_rule_state,
    fx_factor_risk_table,
    instrument_risk_table,
    portfolio_risk_status,
    pretrade_approval,
    risk_config_from_mapping,
)
from src.mt5_account import (
    MT5BridgeError,
    MT5ConfigError,
    MT5ConnectionError,
    MT5UnavailableError,
    config_from_mapping,
    get_mt5_snapshot,
    runtime_diagnostics,
)
from src.mt5_symbols import openable_symbol_catalog, symbol_label_map
from src.style import (
    apply_style,
    context_strip,
    definition,
    empty_state,
    metric_card,
    page_header,
    section_line,
)


apply_style()


def _money(value, currency="USD"):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    if not np.isfinite(x):
        return "—"
    symbol = "$" if str(currency).upper() == "USD" else f"{currency} "
    return f"{symbol}{x:,.2f}"


def _pct(value, digits=2):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    if not np.isfinite(x):
        return "—"
    return f"{100.0 * x:.{digits}f}%"


def _num(value, digits=2):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "—"
    if not np.isfinite(x):
        return "—"
    return f"{x:,.{digits}f}"


def _secret_section(name: str) -> dict:
    try:
        section = st.secrets.get(name, {})
        return dict(section) if section else {}
    except Exception:
        return {}


def _config_help():
    section_line("MT5 Verbindung einrichten", "lokale Secrets · niemals ins ZIP")
    definition(
        "Auf macOS wird die lokale MT5-Bridge verwendet. Zugangsdaten und der lokale Common/Files-Pfad "
        "bleiben ausschließlich in .streamlit/secrets.toml."
    )
    st.code(
        """[mt5]\nmode = \"bridge\"\nlogin = 123456789\npassword = \"INVESTOR_PASSWORD\"\nserver = \"FTMO-Server4\"\ntimeout_ms = 10000\nbridge_common_path = \"/Users/.../MetaQuotes/Terminal/Common/Files\"\nbridge_max_age_seconds = 15\n""",
        language="toml",
    )


def _risk_controls(base: FTMORiskConfig) -> FTMORiskConfig:
    with st.expander("Interne Risk-Parameter", expanded=False):
        st.caption(
            "5 % Maximum Daily Loss und 10 % Maximum Loss sind für das FTMO-2-Step-Profil fest. "
            "Die folgenden Werte sind ausschließlich interne Sicherheitslimits und keine FTMO-Regeln."
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            target = st.number_input(
                "Zielrisiko / Trade (%)", min_value=0.05, max_value=2.00,
                value=float(base.target_trade_risk_pct * 100), step=0.05,
            ) / 100.0
            max_single = st.number_input(
                "Max. Einzeltrade (%)", min_value=0.05, max_value=3.00,
                value=float(base.max_single_trade_risk_pct * 100), step=0.05,
            ) / 100.0
            max_instrument = st.number_input(
                "Max. Instrument / Idee (%)", min_value=0.05, max_value=5.00,
                value=float(base.max_instrument_risk_pct * 100), step=0.05,
            ) / 100.0
        with c2:
            max_open = st.number_input(
                "Max. Open Stop Risk (%)", min_value=0.25, max_value=10.00,
                value=float(base.max_open_risk_pct * 100), step=0.25,
            ) / 100.0
            max_cluster = st.number_input(
                "Max. Cluster Risk (%)", min_value=0.25, max_value=10.00,
                value=float(base.max_cluster_risk_pct * 100), step=0.25,
            ) / 100.0
            max_fx_factor = st.number_input(
                "Max. FX-Faktor Risk (%)", min_value=0.25, max_value=10.00,
                value=float(base.max_fx_factor_risk_pct * 100), step=0.25,
            ) / 100.0
        with c3:
            daily_reserve = st.number_input(
                "Interner Daily-Puffer (%)", min_value=0.0, max_value=5.0,
                value=float(base.daily_safety_reserve_pct * 100), step=0.25,
            ) / 100.0
            total_reserve = st.number_input(
                "Interner Max-Loss-Puffer (%)", min_value=0.0, max_value=10.0,
                value=float(base.total_safety_reserve_pct * 100), step=0.25,
            ) / 100.0
            weekend = st.number_input(
                "Weekend-/Gap-Stress Multiplikator", min_value=1.0, max_value=4.0,
                value=float(base.weekend_stress_multiplier), step=0.1,
            )

    return FTMORiskConfig(
        initial_capital=base.initial_capital,
        max_daily_loss_pct=0.05,
        max_loss_pct=0.10,
        target_trade_risk_pct=target,
        max_single_trade_risk_pct=max_single,
        max_instrument_risk_pct=max_instrument,
        max_open_risk_pct=max_open,
        max_cluster_risk_pct=max_cluster,
        max_fx_factor_risk_pct=max_fx_factor,
        daily_safety_reserve_pct=daily_reserve,
        total_safety_reserve_pct=total_reserve,
        weekend_stress_multiplier=weekend,
    )


page_header(
    "Portfolio · FTMO Risk",
    "FTMO Portfolio & Risk Engine",
    "Wie viel CFD-Risiko ist im aktuellen $100k Swing-Konto bereits offen und wie viel darf ein neuer Trade noch hinzufügen?",
    "V3.6.0.1 · FULL MT5 CFD CATALOG",
)

st.caption(
    "Read-only: Diese Seite liest MT5-Daten, berechnet Risiko und Lots, sendet aber keine Order, "
    "schließt keine Position und verändert weder Stop Loss noch Take Profit."
)

mt5_section = _secret_section("mt5")
risk_section = _secret_section("risk")
try:
    mt5_config = config_from_mapping(mt5_section)
    base_risk_cfg = risk_config_from_mapping(risk_section)
except MT5ConfigError as exc:
    st.error(str(exc))
    _config_help()
    st.stop()

risk_cfg = _risk_controls(base_risk_cfg)
runtime = runtime_diagnostics()
context_strip(
    [
        ("Profil", "FTMO 2-STEP SWING"),
        ("Initial", _money(risk_cfg.initial_capital, "USD")),
        ("MT5 Modus", mt5_config.mode.upper()),
        ("Plattform", runtime["platform"]),
    ]
)

if not mt5_section and mt5_config.mode != "bridge":
    st.info("Noch keine lokale MT5-Konfiguration gefunden.")
    _config_help()
    st.stop()

refresh_col, note_col = st.columns([0.25, 0.75])
with refresh_col:
    if st.button("MT5 & Risk aktualisieren", type="primary", use_container_width=True):
        st.rerun()
with note_col:
    st.caption("Jeder Seitenaufruf liest einen frischen Bridge-Snapshot und berechnet das Portfolio-Risiko neu.")

try:
    with st.spinner("MT5 Snapshot und FTMO Risk werden geladen …"):
        snapshot = get_mt5_snapshot(mt5_config)
except (MT5UnavailableError, MT5BridgeError, MT5ConnectionError, MT5ConfigError) as exc:
    st.error(str(exc))
    _config_help()
    st.stop()
except Exception as exc:
    st.error("Unerwarteter Fehler beim Lesen des MT5-Kontos.")
    with st.expander("Technische Details"):
        st.code(str(exc))
    st.stop()

account = snapshot["account"]
positions = snapshot["positions"].copy()
catalog = snapshot.get("symbol_catalog", pd.DataFrame()).copy()
currency = account.get("currency") or "USD"
state = ftmo_rule_state(account, positions, risk_cfg)
risk_positions = state["positions"].copy()
risk_status = portfolio_risk_status(account, positions, risk_cfg)

captured = snapshot.get("captured_at")
captured_text = (
    pd.Timestamp(captured).strftime("%d.%m.%Y %H:%M:%S")
    if captured is not None and not pd.isna(captured) else "—"
)
context_strip(
    [
        ("Quelle", snapshot.get("source", "—")),
        ("Konto", str(account.get("login") or "—")),
        ("Server", account.get("server") or "—"),
        ("Snapshot", captured_text),
    ]
)
for warning in snapshot.get("warnings", []):
    st.warning(str(warning))

if currency.upper() != "USD":
    st.warning("Das Risk-Profil ist auf ein $100.000-USD-Konto ausgelegt, MT5 meldet jedoch eine andere Kontowährung.")

section_line("FTMO Rule Guard", "offizielle 2-Step-Grenzen · Equity-basiert")
a, b, c, d = st.columns(4)
with a:
    metric_card("EQUITY", _money(state["equity"], currency), f"Balance {_money(state['balance'], currency)}")
with b:
    metric_card(
        "DAILY LOSS LIMIT",
        _money(state["daily_limit"], currency),
        "00:00 CE(S)T Balance − $5.000" if state["exact_daily_limit"] else "aktuelle Bridge benötigt",
    )
with c:
    metric_card("DAILY BUFFER", _money(state["daily_buffer"], currency), "Equity bis FTMO Daily Limit")
with d:
    metric_card("MAX LOSS FLOOR", _money(state["maximum_loss_limit"], currency), "statisch · 90 % von $100k")

x1, x2, x3, x4 = st.columns(4)
with x1:
    metric_card("TOTAL BUFFER", _money(state["total_buffer"], currency), "Equity bis $90k Floor")
with x2:
    metric_card("OPEN STOP RISK", _money(state["known_open_stop_risk"], currency), _pct(state["known_open_stop_risk_pct"]))
with x3:
    metric_card("ALL-STOPS EQUITY", _money(state["all_stops_equity"], currency), "wenn bekannte SL ohne Slippage erreicht werden")
with x4:
    metric_card(
        "WEEKEND STRESS",
        _money(state["weekend_stress_equity"], currency),
        f"{risk_cfg.weekend_stress_multiplier:.1f}× bekannter Stop-Risk",
    )

section_line("Portfolio Risk Status", "interne Risk-Desk-Ampel · keine FTMO-Regel")
status = risk_status["status"]
if status == "GREEN":
    st.success("GREEN · Portfolio liegt innerhalb der internen Risk-Policy.")
elif status == "YELLOW":
    st.warning("YELLOW · Mindestens ein Risikobudget ist zu mindestens 75 % ausgelastet.")
else:
    st.error("RED · Mindestens ein internes Risk-Limit oder ein Sicherheitsfloor ist verletzt. Neue Trades sollten blockiert bleiben.")
for reason in risk_status["reasons"]:
    st.caption(f"• {reason}")

rs1, rs2 = st.columns(2)
with rs1:
    metric_card(
        "INTERNER DAILY FLOOR",
        _money(risk_status["daily_internal_floor"], currency),
        f"FTMO Daily Limit + {_pct(risk_cfg.daily_safety_reserve_pct)} Reserve",
    )
with rs2:
    metric_card(
        "INTERNER MAX-LOSS FLOOR",
        _money(risk_status["total_internal_floor"], currency),
        f"$90k Floor + {_pct(risk_cfg.total_safety_reserve_pct)} Reserve",
    )

section_line("MT5 Account State", "operative Kontodaten")
m1, m2, m3, m4 = st.columns(4)
with m1:
    metric_card("FLOATING P&L", _money(account.get("profit"), currency), "offene Positionen")
with m2:
    metric_card("MARGIN", _money(account.get("margin"), currency), "aktuell gebunden")
with m3:
    metric_card("FREE MARGIN", _money(account.get("margin_free"), currency), f"Leverage 1:{account.get('leverage', 0)}")
with m4:
    level = float(account.get("margin_level", np.nan)) if account.get("margin_level") is not None else np.nan
    metric_card("MARGIN LEVEL", f"{level:,.1f}%" if np.isfinite(level) else "—", "MT5 AccountInfo")

if bool(account.get("trade_allowed", False)):
    st.caption("MT5-Sitzung: Trading ist im Terminal erlaubt. Der COT-Bot/Bridge-Code bleibt trotzdem read-only und enthält keine Orderfunktion.")
else:
    st.caption("MT5-Sitzung: Trading laut AccountInfo nicht erlaubt / read-only.")

if not state["exact_daily_limit"]:
    st.error(
        "Für den exakten FTMO Daily-Loss-Guard fehlen `day_start_balance` und `daily_realized_pnl`. "
        "Die aktuelle MT5ReadOnlyBridge.mq5 einmal neu kompilieren und auf den Chart legen. "
        "Bis dahin wird keine neue Position als RISK APPROVED freigegeben."
    )
else:
    st.caption(
        f"Tagesstart-Balance: {_money(state['day_start_balance'], currency)} · "
        f"heute realisiert: {_money(state['daily_realized_pnl'], currency)}"
    )

if state["missing_sl_count"]:
    st.error(
        f"{state['missing_sl_count']} offene Position(en) ohne Stop Loss. Der vollständige Portfolio-Stop-Risk ist damit nicht begrenzt; "
        "Pre-Trade Approval wird konservativ blockiert."
    )

# Internal policy view.
section_line("Interne Safety Policy", "keine FTMO-Regeln")
policy = pd.DataFrame(
    [
        ["Zielrisiko je Trade", risk_cfg.target_trade_risk_pct, risk_cfg.initial_capital * risk_cfg.target_trade_risk_pct],
        ["Max. Einzeltrade", risk_cfg.max_single_trade_risk_pct, risk_cfg.initial_capital * risk_cfg.max_single_trade_risk_pct],
        ["Max. Instrument / Idee", risk_cfg.max_instrument_risk_pct, risk_cfg.initial_capital * risk_cfg.max_instrument_risk_pct],
        ["Max. Open Stop Risk", risk_cfg.max_open_risk_pct, risk_cfg.initial_capital * risk_cfg.max_open_risk_pct],
        ["Max. Cluster Risk", risk_cfg.max_cluster_risk_pct, risk_cfg.initial_capital * risk_cfg.max_cluster_risk_pct],
        ["Max. FX-Faktor Risk", risk_cfg.max_fx_factor_risk_pct, risk_cfg.initial_capital * risk_cfg.max_fx_factor_risk_pct],
        ["Daily Safety Reserve", risk_cfg.daily_safety_reserve_pct, risk_cfg.initial_capital * risk_cfg.daily_safety_reserve_pct],
        ["Max-Loss Safety Reserve", risk_cfg.total_safety_reserve_pct, risk_cfg.initial_capital * risk_cfg.total_safety_reserve_pct],
    ],
    columns=["Limit", "Anteil", "USD"],
)
st.dataframe(policy.style.format({"Anteil": "{:.2%}", "USD": "${:,.0f}"}), use_container_width=True, hide_index=True)

section_line("Offene CFD-Positionen", f"{len(risk_positions)} Positionen · live aus MT5")
if risk_positions.empty:
    empty_state("Keine offenen Positionen", "MT5 meldet aktuell keine offenen CFD-Positionen.")
else:
    display_cols = [
        "symbol", "side", "volume", "price_open", "sl", "price_current", "profit", "swap",
        "stop_risk_current", "stop_risk_entry", "risk_pct_initial", "instrument", "cluster", "ticket",
    ]
    display = risk_positions[[c for c in display_cols if c in risk_positions.columns]].copy().rename(
        columns={
            "symbol": "Symbol", "side": "Richtung", "volume": "Lots", "price_open": "Entry",
            "sl": "Stop Loss", "price_current": "Aktuell", "profit": "Floating P&L", "swap": "Swap",
            "stop_risk_current": "Aktuell→SL Risk", "stop_risk_entry": "Entry→SL Risk",
            "risk_pct_initial": "% $100k", "instrument": "Instrument", "cluster": "Cluster", "ticket": "Ticket",
        }
    )
    st.dataframe(
        display.style.format(
            {
                "Lots": "{:.2f}", "Entry": "{:,.5f}", "Stop Loss": "{:,.5f}", "Aktuell": "{:,.5f}",
                "Floating P&L": "{:+,.2f}", "Swap": "{:+,.2f}", "Aktuell→SL Risk": "${:,.2f}",
                "Entry→SL Risk": "${:,.2f}", "% $100k": "{:.2%}",
            }, na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )

section_line("Instrument Risk", "gleiche Underlyings / mehrere Tickets werden aggregiert")
instruments = instrument_risk_table(positions, risk_cfg)
if instruments.empty:
    st.caption("Keine offenen Positionen für Instrument-Risk.")
else:
    instrument_display = instruments.rename(columns={
        "instrument": "Instrument", "symbols": "MT5 Symbol(e)", "positions": "Positionen",
        "stop_risk": "Stop Risk", "risk_pct": "% $100k", "limit": "Internes Limit", "remaining": "Restbudget",
    })
    st.dataframe(
        instrument_display.style.format({
            "Stop Risk": "${:,.2f}", "% $100k": "{:.2%}", "Internes Limit": "${:,.2f}", "Restbudget": "${:,.2f}",
        }), use_container_width=True, hide_index=True,
    )

section_line("Cluster Risk", "Stop-Risk nach ökonomischem Exposure")
clusters = cluster_risk_table(positions, risk_cfg)
if clusters.empty:
    st.caption("Keine offenen Positionen für Cluster-Risk.")
else:
    cluster_display = clusters.rename(columns={
        "cluster": "Cluster", "positions": "Positionen", "instruments": "Instrumente", "stop_risk": "Stop Risk",
        "risk_pct": "% $100k", "limit": "Internes Limit", "remaining": "Restbudget",
    })
    st.dataframe(
        cluster_display.style.format({
            "Stop Risk": "${:,.2f}", "% $100k": "{:.2%}", "Internes Limit": "${:,.2f}", "Restbudget": "${:,.2f}",
        }), use_container_width=True, hide_index=True,
    )

section_line("FX Currency Factor", "gemeinsame Währungsrichtung erkennen")
fx = fx_factor_risk_table(positions, risk_cfg)
if fx.empty:
    st.caption("Aktuell keine FX-Positionen mit bestimmbarer Stop-Risk-Faktorstruktur.")
else:
    fx_display = fx.rename(columns={
        "currency": "Währung", "direction": "Faktor", "net_factor_risk": "Net Factor Risk",
        "gross_factor_risk": "Gross Factor Risk", "net_risk_pct": "Net % $100k",
        "gross_risk_pct": "Gross % $100k", "positions": "Positionen", "symbols": "Symbole",
        "limit": "Faktor-Limit", "remaining": "Restbudget",
    })
    st.dataframe(
        fx_display.style.format({
            "Net Factor Risk": "${:+,.2f}", "Gross Factor Risk": "${:,.2f}",
            "Net % $100k": "{:.2%}", "Gross % $100k": "{:.2%}",
            "Faktor-Limit": "${:,.2f}", "Restbudget": "${:,.2f}",
        }), use_container_width=True, hide_index=True,
    )
    st.caption("Factor Risk ist eine Konzentrationsansicht; die Währungszeilen dürfen nicht zum Portfolio-Risk addiert werden.")

section_line("Pre-Trade Risk Approval", "Lot-Sizing · keine Order")
catalog = openable_symbol_catalog(catalog)
if catalog is None or catalog.empty or "symbol" not in catalog.columns:
    st.warning(
        "Noch kein nutzbarer MT5-Brokerkatalog vorhanden. Die aktualisierte Bridge exportiert alle verfügbaren CFDs, nicht nur Market Watch."
    )
else:
    catalog = catalog.copy()
    catalog["symbol"] = catalog["symbol"].astype(str)
    symbols = sorted(s for s in catalog["symbol"].dropna().unique() if s)
    labels = symbol_label_map(catalog)
    if not symbols:
        st.warning("Der MT5-Brokerkatalog enthält aktuell keine für neue Trades freigegebenen Symbole.")
    else:
        p1, p2 = st.columns([0.35, 0.65])
        with p1:
            symbol = st.selectbox(
                "CFD Symbol",
                symbols,
                format_func=lambda value: labels.get(value, value),
                help="Vollständiger Brokerkatalog aus MT5; nicht auf Market Watch beschränkt.",
            )
            side = st.radio("Richtung", ["LONG", "SHORT"], horizontal=True)
            spec = catalog[catalog["symbol"] == symbol].iloc[0].to_dict()
            bid = float(spec.get("bid", np.nan)) if pd.notna(spec.get("bid", np.nan)) else np.nan
            ask = float(spec.get("ask", np.nan)) if pd.notna(spec.get("ask", np.nan)) else np.nan
            last = float(spec.get("last", np.nan)) if pd.notna(spec.get("last", np.nan)) else np.nan
            default_entry = ask if side == "LONG" and np.isfinite(ask) and ask > 0 else bid
            if not np.isfinite(default_entry) or default_entry <= 0:
                default_entry = bid if np.isfinite(bid) and bid > 0 else last
            if not np.isfinite(default_entry) or default_entry <= 0:
                default_entry = 1.0
            digits = int(float(spec.get("digits", 5) or 5))
            point = float(spec.get("point", 0.00001) or 0.00001)
            entry = st.number_input("Geplanter Entry", min_value=0.0, value=float(default_entry), step=max(point, 1e-8), format=f"%.{min(max(digits, 1), 8)}f")
            stop = st.number_input("Stop Loss", min_value=0.0, value=0.0, step=max(point, 1e-8), format=f"%.{min(max(digits, 1), 8)}f")
            requested_pct = st.number_input(
                "Gewünschtes Risiko (%)", min_value=0.05, max_value=2.00,
                value=float(risk_cfg.target_trade_risk_pct * 100), step=0.05,
            ) / 100.0

        with p2:
            if stop <= 0:
                st.info("Stop Loss eingeben. Erst dann werden Lotgröße und Risk Approval berechnet.")
            else:
                approval = pretrade_approval(
                    account=account,
                    positions=positions,
                    cfg=risk_cfg,
                    spec=spec,
                    symbol=symbol,
                    side=side,
                    entry=entry,
                    stop=stop,
                    requested_risk_pct=requested_pct,
                )
                status = approval["status"]
                if status == "APPROVED":
                    st.success("RISK APPROVED")
                elif status == "REDUCED":
                    st.warning("RISK REDUCED")
                else:
                    st.error("RISK BLOCKED")

                r1, r2, r3, r4 = st.columns(4)
                with r1:
                    metric_card("LOTS", f"{approval['lots']:.2f}" if approval["lots"] > 0 else "—", f"Raw {_num(approval['raw_lots'], 3)}")
                with r2:
                    metric_card("ACTUAL RISK", _money(approval["actual_risk"], currency), _pct(approval["actual_risk"] / risk_cfg.initial_capital))
                with r3:
                    metric_card("INSTRUMENT", approval["instrument"], f"nach Trade {_money(approval['projected_instrument_risk'], currency)}")
                with r4:
                    metric_card("CLUSTER", approval["cluster"], f"nach Trade {_money(approval['projected_cluster_risk'], currency)}")

                q1, q2, q3 = st.columns(3)
                with q1:
                    metric_card("OPEN RISK NACH TRADE", _money(approval["projected_open_risk"], currency), _pct(approval["projected_open_risk"] / risk_cfg.initial_capital))
                with q2:
                    metric_card("ALL-STOPS EQUITY", _money(approval["projected_all_stops_equity"], currency), "bestehende + neue bekannte SL")
                with q3:
                    metric_card("RISK / 1.00 LOT", _money(approval["risk_per_lot"], currency), f"Entry {entry:g} → SL {stop:g}")

                for reason in approval["reasons"]:
                    st.caption(f"• {reason}")

                with st.expander("Approval-Limits im Detail", expanded=False):
                    caps = pd.DataFrame(
                        [(k, v) for k, v in approval["caps"].items()], columns=["Constraint", "USD Risk Budget"]
                    )
                    st.dataframe(caps.style.format({"USD Risk Budget": "${:,.2f}"}), use_container_width=True, hide_index=True)

                st.caption(
                    "Die berechnete Lotgröße ist nur eine Risikodimensionierung. Es wird keine Order an MT5 gesendet. "
                    "Slippage/Gaps können reale Verluste über den modellierten Stop-Risk hinaus erhöhen."
                )

with st.expander("CFD Symbol-Spezifikationen", expanded=False):
    if catalog is None or catalog.empty:
        st.caption("Kein Symbolkatalog verfügbar.")
    else:
        cols = [c for c in [
            "symbol", "bid", "ask", "contract_size", "tick_size", "tick_value", "tick_value_loss",
            "volume_min", "volume_max", "volume_step", "currency_base", "currency_profit", "swap_long", "swap_short",
        ] if c in catalog.columns]
        st.dataframe(catalog[cols], use_container_width=True, hide_index=True)

section_line("Methodik", "V3.5.2")
st.markdown(
    """
- **FTMO 2-Step Guard:** Maximum Daily Loss = Tagesstart-Balance um 00:00 CE(S)T minus 5 % des Initialkapitals; Maximum Loss = statischer 90%-Floor.
- **Open Stop Risk:** zusätzlicher Verlust vom aktuellen MT5-Preis bis zum gesetzten Stop Loss anhand von MT5 Tick Size, Tick Value und Lots.
- **Entry Risk:** ursprüngliches Entry→SL-Risiko wird getrennt ausgewiesen; bereits realisierte Floating-Gewinne/-Verluste werden dadurch nicht mit dem aktuellen Rest-Risiko vermischt.
- **Instrument Risk:** mehrere Tickets desselben Underlyings werden vor der Freigabe als eine gemeinsame Risikoidee aggregiert.
- **Cluster Risk:** Metals, Energy, Indices, FX, Crypto und Other werden separat begrenzt.
- **FX Factor:** misst die gerichtete Netto-Risikokonzentration je Währung; gegenläufige Trades können Faktor-Risk reduzieren.
- **Weekend Stress:** interner Gap-Stress auf den bekannten Stop-Risk; kein Garant für tatsächliche Ausführung am Stop.
- **Pre-Trade Approval:** Lotgröße wird immer nach unten auf den MT5-Volume-Step gerundet. Fehlende Stops oder fehlende Daily-Limit-Daten blockieren konservativ.
    """
)
