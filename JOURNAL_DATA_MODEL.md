# Trading Journal · Data Model

## Forschungsprinzip
Jeder Trade-Plan ist ein `as-known-at-plan-time` Snapshot. Features werden zum Entscheidungszeitpunkt eingefroren und später nicht mit neueren COT-, Preis-, Saison- oder Risk-Daten überschrieben.

## 0. traders
Lokale Identitätsschicht für Multi-Trader-Research:
- trader_id
- username
- display_name
- role: ADMIN / TRADER
- active
- Passwort nur als PBKDF2-SHA256-Hash + Salt

Jeder neue Trade-Plan trägt eine stabile `trader_id`. Normale Trader sehen nur ihre eigenen Pläne; der ADMIN kann einzelne Trader oder das Gesamtkollektiv auswerten.

## 1. trade_plans
Die diskretionäre Entscheidung des Traders inklusive `trader_id`: Instrument, Richtung, S&D-Zone, Entry, Stop, Target, Timeframe, Freshness, Retests, Qualität, REAL/SIMULATION/SKIPPED und Skip-Grund.

Diese Tabelle ist immutable. Änderungen werden nicht überschrieben.

## 2. trade_snapshots
Ein vollständiges JSON des damaligen Systemzustands. Jeder Snapshot besitzt einen SHA-256-Hash. Beim Lesen wird die Integrität geprüft.

## 3. snapshot_features
Dasselbe Snapshot-Material wird zusätzlich in eine Long-Feature-Tabelle abgelegt:

`trade_id | feature_group | feature_name | value_type | numeric_value | text_value | bool_value`

Das vermeidet spätere Schema-Migrationen, wenn neue Features hinzukommen, und erleichtert Feature-Matrix-Exporte für Statistik/ML.

## 4. trade_events
Append-only Event Sourcing für spätere Entscheidungen, z. B.:
- TRADE_TAKEN
- PLAN_CANCELLED
- ENTRY_CHANGED
- STOP_CHANGED
- TARGET_CHANGED
- MANUAL_EXIT
- NOTE

Damit kann später Originalplan vs. tatsächliches Trade-Management untersucht werden.

## 5. trade_outcomes
Bewusst getrennt und veränderbar, weil Outcomes erst nach dem Plan entstehen. V3.6.1 führt sie automatisch aus MT5-CFD-Historie nach:
- lifecycle_status: PLANNED / ACTIVE / CLOSED / EXPIRED / AMBIGUOUS
- entry_triggered / entry_time
- stop_time / target_time / first_exit / exit_time
- result_r
- mae_r / mfe_r
- +1R / +2R / +3R Zeitpunkte
- holding_minutes
- direction-adjusted 1D / 3D / 5D / 10D / 20D / 40D / 60D Forward Return
- verwendeter Historien-Timeframe und Ambiguitätsgrund
- zusätzliches Outcome-JSON

### Historienprinzip
Der Outcome Tracker fragt die lokale read-only MT5-Bridge nach historischen CFD-Bars. LIMIT-Pläne verwenden primär H1; unklare Intrabar-Fälle werden mit M5 und danach M1 aufgelöst. MARKET-Pläne lösen zuerst den tatsächlichen simulierten Fill über M15 auf; liegt der Speichermoment innerhalb der M15-Bar, wird nur für den Fill M5 und nötigenfalls M1 verwendet. Bei geschlossenem Markt gilt der Open der ersten verfügbaren Bar nach dem Planzeitpunkt als Fill. Danach läuft auch MARKET wieder über H1 → M5 → M1. Bleibt selbst M1 unklar, wird `AMBIGUOUS` gespeichert und kein Ergebnis erfunden. Der Bot muss nicht 24/7 laufen; beim nächsten manuellen Sync wird die fehlende Historie rückwirkend nachgeladen.

## ML-Grundsatz
Labels/Outcomes dürfen niemals in die eingefrorenen Snapshot-Features zurückgeschrieben werden. Training muss zeitlich getrennt und später Walk-Forward/Out-of-Sample erfolgen.


## Multi-Trader Datenschutz
Der lokale FTMO-/Portfoliozustand gehört dem ADMIN. Ein normaler TRADER erhält im Planner zwar denselben brokerseitigen CFD-Katalog und dieselbe MT5-Kurshistorie für Simulationen, sein Snapshot enthält aber keine ADMIN-Balance, Equity, offenen Positionen oder Portfolio-Risk-Werte.

## Gemeinsame Outcomes
Alle Trader können über denselben lokalen MT5-History-Adapter objektiv ausgewertet werden. Die Identitäten bleiben getrennt; Auswertungen können später pro Trader oder aggregiert erfolgen.

## 6. mt5_history_bars / mt5_history_coverage
Lokaler persistenter History-Cache für den Outcome Tracker.

`mt5_history_bars` speichert deduplizierte OHLC-Bars pro `symbol + timeframe + time_utc`. `mt5_history_coverage` speichert zusätzlich bereits geprüfte halb-offene Zeiträume `[start, end)`, auch wenn MT5 darin keine Bars geliefert hat (z. B. Wochenende/Marktschließung). Dadurch werden gleiche Zeiträume nicht bei jedem Sync erneut beim MT5-Terminal angefragt.

Der reguläre Swing-Sync berücksichtigt nur `PLANNED` und `ACTIVE`. Mehrere Trades desselben Symbols teilen sich denselben Cache. LIMIT nutzt H1 als Standard. MARKET nutzt M15 nur zur Fill-Auflösung und danach ebenfalls H1; M5/M1 bleiben gezielte Auflösungs-Layer. Laufende Kerzen gelten nicht als finale Cache-Coverage.

## V3.8.0 · Prop Desk Tabellen

`prop_accounts` speichert die prospektive virtuelle Account-Konfiguration je `trader_id` (Startkapital, Default/Max Risk, Aktiv-Flag). `prop_trade_allocations` speichert pro SIMULATION-Trade die unveränderliche virtuelle Sizing-Entscheidung: Balance zum Planzeitpunkt, Risk-Budget, Lots, Tick-Werte und Sizing-Status. Realized/Floating P&L wird daraus zusammen mit `trade_outcomes` abgeleitet; die unveränderlichen Research-Snapshots werden nicht verändert.
