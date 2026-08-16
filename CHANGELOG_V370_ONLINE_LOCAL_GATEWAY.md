# V3.7.0 · Online Planner / Local Journal Gateway

- Zwei Betriebsarten aus derselben Codebasis: `LOCAL` und `REMOTE_GATEWAY`.
- Online-Login authentifiziert gegen die lokale Trader-Tabelle; Passworthashes bleiben auf dem Mac.
- Online geplante Trades werden synchron über das authentifizierte HTTPS-Gateway direkt in die lokale Master-SQLite geschrieben.
- Remote-User sehen nur ihre eigenen Trades; ADMIN kann Trader verwalten und die gemeinsame Journal-Sicht verwenden.
- MT5 Outcome Sync bleibt ausschließlich lokal. Die Online-App löst keine History-Abfragen aus.
- Online Planner erhält nur Broker-Symbolmetadaten. Live-Bid/Ask/Last, FTMO-Kontostand, offene Positionen und Portfolio-Risk werden nicht übertragen.
- Historische Snapshots werden vor Remote-Ausgabe serverseitig gefiltert; private Account-/Portfolio-/Risk-Felder verlassen den Mac nicht.
- Gateway-Sessions sind zufällige, lokal gehashte Bearer-Tokens mit Ablaufzeit.
- Gateway bindet standardmäßig nur an `127.0.0.1:8765`; Internetzugriff soll ausschließlich über HTTPS-Tunnel/Reverse-Proxy erfolgen.
- Remote-Ingest wird append-only als `REMOTE_GATEWAY_INGEST` im Event-Log protokolliert.
- Bestehende H1→M5→M1 Outcome-Logik und effizienter SQLite-History-Cache bleiben unverändert.
