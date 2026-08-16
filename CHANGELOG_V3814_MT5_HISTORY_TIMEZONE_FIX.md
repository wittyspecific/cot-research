# V3.8.1.4 · MT5 History Timezone Fix

- Bridge history protocol keeps Python/SQLite timestamps in UTC and converts request boundaries to the MetaTrader trade-server clock before `CopyRates()`.
- Returned MQL5 bar timestamps are converted back from server time to UTC before the CSV response is written.
- FTMO's documented MetaTrader platform timezone (GMT+2 with US-DST switch to GMT+3) is handled historically, including backfills across March/November.
- Non-FTMO-style server offsets fall back to the measured terminal server-vs-GMT offset.
- The local MT5 history cache is invalidated once on first bridge sync because older cached bars/coverage used the previous time basis. Journal plans, snapshots, users, events and Prop Desk accounts are not deleted.
- MARKET M15 → M5 → M1 fill logic and LIMIT H1 → M5 → M1 logic remain unchanged.
