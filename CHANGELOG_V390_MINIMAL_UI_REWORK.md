# V3.9.0 · Minimal UI Rework

## Ziel

Die Oberfläche wurde als klarer Research- und Trading-Workspace neu strukturiert. Die bestehende Journal-, MT5-, Gateway-, Outcome-, Risk- und Prop-Desk-Architektur bleibt erhalten. Komplexe Research-Daten werden nicht entfernt, sondern in eine deutlich ruhigere Informationshierarchie eingeordnet.

## Neue Informationsarchitektur

- **Workspace:** Dashboard
- **Research:** Watchlist, Marktanalyse, Währungsstärke
- **Trading:** Neuer Trade, Journal, Prop Desk
- **Advanced:** Research Lab, CFTC Datenmodell
- **Admin:** Traderverwaltung sowie lokale FTMO-/Portfolio-Risk-Seiten nur für Admins

## Visuelles System

- helles, minimalistisches Workspace-Theme
- weiße Karten auf sehr hellem Hintergrund
- Inter-/System-Sans-Typografie
- dezente Borders, kleine Radien und mehr Weißraum
- Grün nur für positive/bullishe Richtungsinformation, Rot nur für negative/bärische Richtung
- TradingView-Preview auf Light Theme
- zentrale Style-Tokens für UI und Plotly-Charts

## COT-Semantik · STATE ≠ SIGNAL

V3.9.0 trennt den Positionierungszustand explizit vom Richtungs-Signal:

- COT-Index im oberen Extrem = **FULL HEDGE / obere Extremzone**, noch kein bullishes Signal.
- COT-Index im unteren Extrem = **LOW HEDGE / untere Extremzone**, noch kein bärisches Signal.
- Ein bullishes Signal entsteht erst durch einen **BULLISH RELEASE** aus dem oberen Hedge-Extrem.
- Ein bärisches Signal entsteht erst durch einen **BEARISH RELEASE** aus dem unteren Extrem.

Die Semantik wird konsistent in Watchlist, Forex-Währungsprofilen, Marktanalyse und neuen Research-Snapshots verwendet. Bestehende immutable Snapshots werden nicht rückwirkend verändert.

## Watchlist

Die Watchlist ist jetzt Release-first:

- oben nur aktive directional Hedge-Releases
- separate **Full Hedge Watch** für Märkte, die noch im Extremzustand stehen
- klare Bestätigung aus Release + Commercial + Non-Commercial + Retail
- Seasonality bleibt zusätzliche Confluence und verändert den COT-Score nicht

## Dashboard

Neue kompakte Startseite mit:

- Equity
- Floating P&L
- Open Risk
- offenen Trades
- aktuellen Positionen
- Quick Actions
- Research Pulse

## Trade Planner / Journal / Prop Desk

- Trade Planner in drei klaren Schritten: Asset → Setup → Bestätigen
- TradingView standardmäßig eingeklappt
- MARKET bleibt Entry `AUTO`; Execution- und Price-Unit-Logik bleibt bestehen
- Journal und Prop Desk erhalten die neue reduzierte visuelle Hierarchie

## Technische Hinweise

- Gateway-Version: `3.9.0`
- keine Änderung am MT5-EA für dieses Update
- kein neues Datenbankschema
- keine Änderung an Live Execution Watcher, Outcome State Guard oder History-Timezone-Logik
