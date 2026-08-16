# V3.6.2.2 · Efficient MT5 History Sync

- Regulärer Outcome-Sync prüft nur noch `PLANNED`- und `ACTIVE`-Trades.
- Historische MT5-Bars werden persistent in derselben lokalen SQLite-Datenbank gecacht.
- Cache-Coverage wird auch für leere Marktzeiträume gespeichert, damit Wochenenden/Feiertage nicht wiederholt angefragt werden.
- Mehrere Trades/Trader desselben CFD-Symbols werden vor dem MT5-Abruf zusammengeführt; überlappende Zeiträume erzeugen nur eine History-Anfrage.
- Bei späteren Syncs wird nur der noch nicht gecachte Zeitbereich nachgeladen.
- H1 bleibt Primärhistorie; M5/M1 werden weiterhin ausschließlich für `AMBIGUOUS`-Pfade verwendet und ebenfalls gecacht.
- Laufende, noch nicht abgeschlossene H1-/M5-/M1-/D1-Kerzen werden nicht als finale Historie gecacht.
- Automatischer Sync beim ersten Journal-Öffnen ist standardmäßig AUS. Manueller Sync ist der empfohlene Swing-Workflow.
- Sync-UI zeigt Anzahl geprüfter offener Pläne, CFD-Symbole, echte neue MT5-Requests, geladene H1-Bars und M5/M1-Fallbacks.
- Keine Änderung an MT5-Bridge oder Trade-Berechtigungen; weiterhin read-only.
