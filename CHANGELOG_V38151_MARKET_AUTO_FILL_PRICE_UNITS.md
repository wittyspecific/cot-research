# V3.8.1.5.1 · MARKET Auto-Fill & Price Unit Alignment

- MARKET benötigt keinen manuell definierten Entry mehr. LONG wird am nächsten frischen MT5 Ask, SHORT am nächsten frischen MT5 Bid ausgeführt.
- Der Planner zeigt für MARKET `AUTO` statt eines editierbaren Entry-Feldes. Der alte NOT-NULL-DB-Entry bleibt nur als automatisch erzeugter, nicht ausführungsrelevanter Referenzwert kompatibel.
- XCUUSD verwendet zentral den Preisfaktor ×100 zwischen Planner-/Chart-Einheit und MT5-Einheit. Zone/SL/TP bleiben für Trader in der 6.xx-Darstellung; Live Execution, LIMIT-Trigger, History/SL/TP und Prop Desk rechnen intern in MT5-Einheiten.
- Neue MARKET-Simulationen frieren beim Plan nur Balance und USD-Risk-Budget ein. Die virtuelle Lotgröße wird erst beim tatsächlichen MT5-Fill aus Execution ↔ SL berechnet und danach unveränderlich gespeichert.
- Bestehende MARKET-Simulationen mit bereits vorhandenem Execution Price können die neue Execution-Sizing-Schicht ebenfalls nutzen; alte Plan-/Snapshot-Daten bleiben unverändert.
- Der 2-Sekunden MT5 Quote Export aus V3.8.1.5 bleibt unverändert. Keine neue EA-Kompilierung erforderlich.
