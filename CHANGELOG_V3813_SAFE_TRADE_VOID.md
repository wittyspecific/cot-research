# V3.8.1.3 · Safe Trade Void

- Neuer Journal-Workflow **Fehleintrag verwerfen** statt physischem Löschen.
- Nur `PLANNED` + `entry_triggered=0`; Trader nur eigene Trades, ADMIN alle.
- Lifecycle wird `VOID`, Originalplan/Snapshot bleiben immutable.
- Append-only Audit-Event `PLAN_VOIDED` mit Grund und Actor.
- VOID wird aus Outcome-Sync, Prop Desk, Kennzahlen und ML-Feature-Matrix ausgeschlossen.
- Online-Gateway erhält authentifizierten `POST /v1/trades/{trade_id}/void` Endpoint.
