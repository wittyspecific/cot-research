# V3.6.2.1 · H1 Outcome Resolution

- Outcome Tracker: H1 ist jetzt der primäre Swing-Timeframe.
- M5 wird nur für H1-ambiguous Trades nachgeladen.
- M1 wird nur nachgeladen, wenn M5 weiterhin ambiguous ist.
- Teilkerze beim Plan-Start wird nicht rückwirkend als sicherer Entry interpretiert.
- Limit-Expiry innerhalb einer H1/M5-Kerze wird bei Entry-Berührung verfeinert statt geraten.
- Bleibt die Reihenfolge selbst auf M1 unklar, bleibt der Status `AMBIGUOUS`.
- Keine Änderung an Login, Multi-Trader-Rechten, SQLite-Journal, FTMO-Risk oder Order-Berechtigungen.
- Bestehende V3.6.1/3.6.2 MT5-Bridge unterstützt H1 bereits; kein Bridge-Update erforderlich.
