# V3.5.1 · FTMO Swing CFD Portfolio & Risk Engine

## Ziel

Die bestehende COT-/Seasonality-Research-Logik bleibt unverändert. V3.5.1 ergänzt eine vollständig read-only Portfolio- und Risk-Schicht für ein FTMO 2-Step Swing Konto mit 100.000 USD Initialkapital und CFD-Ausführung über MT5.

## FTMO Rule Guard

- Maximum Daily Loss: 5 % des Initialkapitals.
- Daily-Loss-Limit: Kontostand um 00:00 CE(S)T minus 5.000 USD.
- Maximum Loss: statischer 10-%-Loss-Rahmen; bei 100.000 USD liegt der Equity-Floor bei 90.000 USD.
- Equity, Floating P&L, Swaps und MT5-Kontoeffekte werden über den Live-Snapshot berücksichtigt.
- FTMO-Regelgrenzen und interne Safety-Limits sind in UI und Code strikt getrennt.

## MT5 Bridge V3.5.1

`mt5/MT5ReadOnlyBridge.mq5` exportiert zusätzlich:

- `day_start_balance`
- `daily_realized_pnl`
- aktuelle berechnete Serverzeit
- Tick Value Profit/Loss
- `cot_mt5_symbols.csv` mit den in Market Watch sichtbaren CFD-Symbolen und ihren Lot-/Tick-Spezifikationen

Die Bridge enthält weiterhin keine Order-, Close-, Modify- oder SL/TP-Logik.

## Open Stop Risk

Für jede offene Position werden getrennt berechnet:

- aktueller zusätzlicher Verlust vom aktuellen Preis bis SL
- ursprüngliches Entry→SL-Risiko
- Risiko als Anteil des 100k-Initialkapitals
- Cluster-Zuordnung

Fehlende Stops werden nicht geschätzt. Eine Position ohne SL macht den vollständigen Portfolio-Stop-Risk unbestimmt und blockiert konservativ die Pre-Trade-Freigabe.

## Interne Safety Policy

Standardwerte, ausdrücklich keine FTMO-Regeln:

- Zielrisiko je Trade: 0,50 %
- maximaler Einzeltrade: 0,75 %
- maximaler Open Stop Risk: 3,00 %
- maximaler Cluster Risk: 1,50 %
- Daily Safety Reserve: 1,00 %
- Max-Loss Safety Reserve: 2,00 %
- Weekend-/Gap-Stress: 1,5× bekannter Stop-Risk

Die Werte können auf der Portfolio-Seite verändert und optional in `[risk]` in `secrets.toml` vorbelegt werden.

## Exposure

- Cluster: Metals, Energy, Indices, FX, Crypto, Other.
- FX Currency Factor erkennt gemeinsame Währungsrichtungen, z. B. mehrere USD-Short-Komponenten.
- Factor Risk ist eine Konzentrationsansicht und wird nicht als zusätzliches Portfolio-Risiko aufsummiert.

## Pre-Trade Risk Approval

Für Market-Watch-CFDs können Richtung, Entry, Stop und gewünschtes Risiko angegeben werden. Die Engine:

1. berechnet Risiko pro 1,00 Lot aus Tick Size / Tick Value,
2. begrenzt das Budget durch FTMO-Puffer und interne Limits,
3. rundet Lots immer nach unten auf den MT5-Volume-Step,
4. liefert `APPROVED`, `REDUCED` oder `BLOCKED`,
5. sendet keine Order.

## Tests

Neue Regressionstests decken FTMO-Grenzen, Stop-Risk, Lot-Rundung, Cluster-/FX-Exposure, konservative Blocks und Read-only-Codehygiene ab.
