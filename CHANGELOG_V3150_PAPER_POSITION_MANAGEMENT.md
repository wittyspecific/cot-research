# V3.15.0 · Paper Position Management

- Neue Seite `Trading → Positionsmanagement` für offene SIMULATION-Trades.
- Break Even verschiebt nur den internen Demo-Stop auf den tatsächlichen Execution-Fill.
- Der neue Stop gilt ab dem Klick-Zeitpunkt; es gibt keinen rückwirkenden Break-Even-Trigger.
- Der vorhandene lokale Live-Execution-Watcher prüft aktive BE-Stops mit denselben read-only MT5 Bid/Ask-Quotes.
- Manuelles Schließen: LONG = Bid, SHORT = Ask; stale Quotes werden verworfen.
- Ergebnis-R wird gegen das ursprüngliche Initialrisiko gerechnet, nicht gegen den verschobenen BE-Stop.
- Management-Aktionen werden append-only mit Zeit, altem/neuem Stop, Bid/Ask, Exit-Fill und R-Multiple protokolliert.
- Trade-Pläne und Research-Snapshots bleiben immutable.
- Keine neue MQL5-Datei, kein OrderSend, kein PositionModify, kein PositionClose.
