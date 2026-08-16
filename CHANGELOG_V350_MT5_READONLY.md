# V3.5.0 · MT5 Read-Only Integration

## Neu

- neue Seite `Portfolio & MT5`
- neuer Adapter `src/mt5_account.py`
- direkter Read-only-Zugriff über das offizielle `MetaTrader5`-Pythonmodul, wenn es in der Laufzeit verfügbar ist
- Account-Snapshot:
  - Balance
  - Equity
  - Floating P&L
  - Margin / Free Margin / Margin Level
  - Leverage
  - Kontowährung
  - MT5 Trade-Permission-Status
- offene CFD-Positionen:
  - Symbol
  - Long / Short
  - Lots
  - Entry
  - Stop Loss / Take Profit
  - aktueller Preis
  - Floating P&L
  - Swap
  - Ticket / Eröffnungszeit
- Symbol-Spezifikationen für die spätere Lot-/Risk-Berechnung
- lokale macOS-Bridge `mt5/MT5ReadOnlyBridge.mq5` als Fallback
- `.streamlit/secrets.toml.example` ohne echte Zugangsdaten

## Sicherheitsgrenze

Der Python-Adapter und die MQL5-Bridge enthalten **keine** Order-, Close-, Modify-, SL-/TP- oder sonstige Trade-Ausführungsfunktion. V3.5.0 liest ausschließlich Daten.

## Noch nicht Bestandteil

- FTMO Daily-Loss-/Maximum-Loss-Guard
- Stop-Risk und Lot-Sizing
- Cluster-/Korrelationsrisiko
- FX-Währungsexposure
- Overnight-/Weekend-Stress
- Pre-Trade Risk Approval

Diese Punkte folgen auf Basis der nun verfügbaren Live-MT5-Daten.
