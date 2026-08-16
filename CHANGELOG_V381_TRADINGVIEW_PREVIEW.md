# V3.8.1 · TradingView Preview

## Neu

- offizielles TradingView Advanced Chart Widget im **Trade Planner**
- TradingView-Chart beim **inspizierten Trade im Trading Journal**
- automatische Best-Effort-Zuordnung häufiger Broker-CFDs zu TradingView-Symbolen
- FX-Paare werden z. B. als `FX_IDC:EURUSD` geöffnet
- bekannte Rohstoffe/Indizes werden auf passende TradingView-Symbole gemappt
- Symbolwechsel und TradingView-Zeichenwerkzeuge bleiben im Widget verfügbar

## Sicherheits-/Datenprinzip

TradingView ist ausschließlich eine visuelle Analyseoberfläche. Der Trade-Plan speichert weiterhin die eingegebenen CFD-Level und der Outcome Tracker verwendet weiterhin ausschließlich die lokale MT5-CFD-Historie (H1 → M5 → M1). TradingView-Daten werden nicht in Outcomes oder Prop-Desk-P&L eingemischt.

## Deployment

Keine neue Secret-Variable und keine Gateway-/MT5-Bridge-Änderung erforderlich. Nach Git-Push genügt das automatische Streamlit-Cloud-Redeploy.
