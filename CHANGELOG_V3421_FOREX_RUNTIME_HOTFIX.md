# V3.4.2.1 · Forex Runtime Hotfix

Behoben:
`NameError: name 'load_currency_usd_values' is not defined`

Ursache:
Beim Refactoring der Forex-Seasonality von einem einzelnen 40T-Horizont
auf 20/40/60T wurden zwei weiterhin benötigte Runtime-Hilfsfunktionen
versehentlich aus `src/fx_relative.py` entfernt:

- `load_currency_usd_values()`
- `synthesize_pair_prices()`

Beide Funktionen sind wiederhergestellt.

Keine Änderung an:
- COT-Logik
- 1/3–3/3 Bestätigung
- 20/40/60T Seasonality-Methodik
- 51-Märkte-Universum
- Forex Relative Strength
