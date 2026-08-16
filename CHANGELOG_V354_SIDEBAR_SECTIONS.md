# V3.5.4 · Strukturierte Sidebar-Navigation

Die Navigation wurde ausschließlich auf UI-/Informationsarchitektur-Ebene neu gruppiert.
Signal-, COT-, Seasonality-, MT5- und Risk-Logik bleiben unverändert.

## Neue Sektionen

### SCHNELLÜBERBLICK
- COT Watchlist
- Risk Cockpit

### MARKT & PORTFOLIO
- COT Marktanalyse
- Forex COT Matrix
- Portfolio & Risk

### RESEARCH
- COT Research Lab
- CFTC Datenmodell

Die COT Watchlist bleibt die Default-Startseite. Die Gruppierung nutzt die native
`st.navigation`-Section-Struktur; es wurden keine eigenen Sidebar-Hacks eingeführt.
