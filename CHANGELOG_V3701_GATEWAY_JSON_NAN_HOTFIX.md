# V3.7.0.1 · Gateway JSON NaN Hotfix

- Behebt das Online-Speichern von Trade-Plänen, wenn der Research-/Planner-Snapshot `NaN`, `Infinity`, `pd.NA` oder Numpy-Missing-Werte enthält.
- Der REMOTE_GATEWAY-Client normalisiert nicht JSON-konforme Missing-Werte rekursiv zu JSON `null`.
- Datums-/Zeit-, Pandas-, Numpy-, Mapping- und Listenwerte werden für den HTTPS-Transport deterministisch JSON-sicher gemacht.
- Keine Änderung an Trade-Logik, MT5-History-Sync, H1→M5→M1-Auflösung oder Trader-Rechten.
- Regressionstest deckt verschachtelte NaN/±Infinity/pd.NA-Werte ab.
- Teststatus: 146/146 erfolgreich.
