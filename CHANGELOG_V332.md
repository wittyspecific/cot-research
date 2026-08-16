# V3.3.2 · Integrationsstand

## Neu

- auditiertes Preis/COT-Matching auf Tagesbasis, letzter Schlusskurs `<=` COT-Stichtag und gleiche ISO-Woche
- `nc_divergence_legacy` als unveränderte alte Divergenzlogik
- neue robuste Spec-Flow-Divergenz in `src/nc_divergence.py`
- OI-normalisierter 4W-Flow
- robustes Preis-/Flow-z über das vorangehende 156W-Kalenderfenster, current t ausgeschlossen
- 8W-Spearman-Pfad mit 9 exakten COT-Wochenpunkten
- Divergenz-Stärke + historisches Perzentil nur gegen frühere Divergenzen im 156W-Fenster
- Managed Money als primärer Proxy für Disaggregated-Rohstoffe
- Leveraged Funds als primärer Proxy für TFF-Finanzfutures
- Long-/Short-Schenkel separat vom Divergenzflag
- Redundanzdiagnostik Legacy und modern
- Research-Vergleich Alt vs. Neu ohne Forward-Return-Auswahl
- optionaler 32-Märkte-Strukturcheck im Research Lab
- `.gitignore` für `.venv`, Cache und Secrets

## Unverändert

- Commercial COT-Index 26W / 80-20
- Netto-Validierung und Commercial-Range
- Hedger-Zyklus / Release-Logik
- Saisonalitätslogik
- Watchlist-Selektion
- TradingView-artige Plotly-Interaktion aus dem vorherigen Hotfix
