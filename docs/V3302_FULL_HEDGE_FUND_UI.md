# V3.30.2 · Full Hedge Fund UI Migration

Dieser Release bündelt die visuelle Migration in einem einzigen Installer.

Enthalten:
- globale Hedge-Fund-Shell
- Sidebar / aktive Navigation
- Branding und Login
- Inputs / Dropdowns / Buttons / Tabs
- Forms / Expander / Panels / Metrics
- Tabellen / DataFrames
- Opportunity Scanner und eingebettete originale COT Watchlist
- Marktanalyse / Währungsstärke / Makro-Regime
- Dashboard / Legacy-Seiten über zentrale Theme-Schichten
- transparente institutionelle Plotly-Defaults
- finales Post-Render-CSS nach page.run(), damit lokales Legacy-CSS die
  Hauptoptik nicht wieder überschreibt

Nicht enthalten:
- keine Watchlist-Logik
- keine COT-/Macro-/Seasonality-/Analog-Modelle
- kein Risk / Journal / Execution

Der Modell-Audit bleibt ein separater Arbeitsblock.
