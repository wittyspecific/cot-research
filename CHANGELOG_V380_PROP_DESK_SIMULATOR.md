# V3.8.0 · Prop Desk Simulator

## Ziel

Jeder Trader erhält ein getrenntes virtuelles Prop-Trading-Konto. Standardmäßig startet es mit 200.000 USD. Nur `SIMULATION`-Pläne wirken auf dieses Konto; `REAL` und `SKIPPED` bleiben vom virtuellen Accounting getrennt.

## Virtuelle Positionsgröße

Beim Speichern eines SIMULATION-Plans werden unveränderlich eingefroren:

- virtuelle Balance zum Planzeitpunkt
- gewünschtes Risk in %
- USD-Risk-Budget
- MT5 Tick Size / Tick Value / Volume Steps
- daraus berechnete virtuelle Lotgröße und tatsächliches modelliertes Stop-Risk

Spätere Balance-Änderungen verändern historische Lots nicht rückwirkend. Default Risk ist 0,50 %, Max Risk/Trade 1,00 %; beide Werte sind pro Trader durch ADMIN konfigurierbar. Das Startkapital ist nach der ersten Prop-Allokation gesperrt.

## Prop Desk Dashboard

Neu: `Trading → Prop Desk` für Trader und ADMIN.

Anzeige pro Trader:

- Starting Capital, Balance, Equity
- Floating und Realized P&L
- Return, Current/Max Drawdown
- Open Risk, offene und geschlossene Trades
- Win Rate, Profit Factor, Expectancy R
- Equity Curve
- virtuelle Lots und aktuelles R je ACTIVE-Position

ADMIN erhält zusätzlich ein traderübergreifendes Prop-Desk-Ranking.

## Mark-to-Market

Floating P&L wird nur für tatsächlich `ACTIVE` simulierte Positionen berechnet. Die Online-App ruft dafür das lokale Gateway auf; auf dem Mac werden die bereits vorhandenen MT5-Bridge-Quotes gelesen. Es wird dabei **keine H1/M5/M1-Historie angefordert**. LONG wird konservativ am Bid, SHORT am Ask markiert. Ohne frische Bridge-Quotes bleibt die realisierte Balance sichtbar und Floating Mark-to-Market wird nicht erfunden.

## Outcome Integration

Die bestehende manuelle Outcome-Synchronisation bleibt unverändert. Sobald ein SIMULATION-Trade durch den H1→M5→M1-Tracker `CLOSED` wird, wird sein virtuelles Realized P&L aus `result_r × eingefrorenem actual_risk` abgeleitet. Ein separater Prop-Sync ist nicht nötig.

## Legacy Simulationen

Bereits vor V3.8.0 gespeicherte SIMULATION-Pläne werden beim ersten Prop-Desk-Aufruf einmalig chronologisch allokiert, sofern der historische Snapshot genügend MT5-Symboldaten für das Sizing enthält. Die Balance wird dabei jeweils as-of Planzeitpunkt berechnet.

## Privacy / Sicherheit

Die Remote-Prop-Desk-Endpunkte übertragen keine echte FTMO-Accountnummer, FTMO-Balance, reale Positionen oder Portfolio-Risk. Nur virtuelle Prop-Account-Daten und die für ACTIVE-Simulationen abgeleiteten Mark-to-Market-Werte verlassen den lokalen Gateway.
