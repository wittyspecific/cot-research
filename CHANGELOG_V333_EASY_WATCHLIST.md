# V3.3.3 · Einfache Watchlist

Diese Version verändert ausschließlich die Darstellung der Watchlist.

## Ziel

Die Hauptansicht soll auch ohne Statistikkenntnisse verständlich sein.

## Neue Informationshierarchie

1. **Jetzt interessant**  
   Aktiver COT-Zyklus + Netto-Bestätigung + passende Range-Lage.

2. **Beobachten**  
   Aktiver Zyklus; genau eine der zusätzlichen Bestätigungen fehlt.

3. **Noch kein klares Bild**  
   Weitere aktive Zyklen werden eingeklappt dargestellt.

4. **Was hat sich verändert?**  
   Neue Extrem-Eintritte, Releases und ungewöhnliche Commercial-Dynamik
   liegen ebenfalls in einem Expander und dominieren die Hauptansicht nicht.

## Technische Daten

COT-Index, Commercial-/Retail-Netto-Perzentile, Range und die exakten
fehlenden Bedingungen bleiben vollständig erhalten und sind pro Markt unter
**Technische Details anzeigen** verfügbar.

## Methodik

Keine Änderung an:

- `src/watchlist.py`
- `src/analysis.py`
- `src/config.py`
- `src/cftc.py`
- `src/cftc_reports.py`
- Preis-, NC-Divergenz- oder Research-Logik
- Schwellenwerten
- Qualifikationsregeln
- Marktuniversum

Es handelt sich ausschließlich um ein UI-/Text-Update der Watchlist.
