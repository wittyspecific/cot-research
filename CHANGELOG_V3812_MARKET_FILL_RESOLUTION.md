# V3.8.1.2 · MARKET Fill Resolution

- `MARKET`-Simulationen verwenden für den Entry nicht mehr blind den im Planner eingetragenen Referenzpreis.
- Primäre Fill-Auflösung ist `M15`. Liegt der Planzeitpunkt innerhalb der M15-Bar, wird nur für den Fill mit `M5` und danach `M1` verfeinert.
- Bei geschlossenem Markt wartet der Tracker auf die erste tatsächlich vorhandene Bar nach dem Planzeitpunkt und verwendet deren `open` als simulierten Fill.
- Bei einem Speichermoment mitten in einer M1-Bar wird der Open der nächsten vollständigen Minute verwendet; es wird keine Preisbewegung vor dem Speichern zugerechnet.
- Nach aufgelöstem MARKET-Fill läuft der Trade wieder über den normalen Swing-Pfad `H1 -> M5 -> M1`.
- Neue Derived-Outcome-Felder: `execution_price` und `fill_timeframe`; der immutable Plan-Entry bleibt unverändert erhalten.
- Der Prop Desk verwendet den tatsächlichen simulierten Fill für Floating P&L, Realized P&L und Stop-Risk. Die bei Planung eingefrorene Lotgröße bleibt unverändert.
- MT5-History-Bridge und lokaler History-Cache unterstützen jetzt `M15`.
- LIMIT-Logik bleibt unverändert H1-first.
