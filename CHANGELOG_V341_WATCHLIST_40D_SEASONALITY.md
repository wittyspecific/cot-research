# V3.4.1 · Watchlist 20Y/40D Seasonality Confluence

Die normale COT Watchlist zeigt jetzt eine zusätzliche Spalte `Saison 40T`.

Methodik:
- 20 abgeschlossene Jahre
- 40 Handelstage Forward
- bestehende `forward_statistics()` Seasonality-Methodik
- mindestens 8 historische Jahresbeobachtungen

Status:
- ✓ UNTERSTÜTZT
- ✕ GEGENLÄUFIG
- — GEMISCHT
- — N/V

Wichtig:
Seasonality verändert den COT-Bestätigungsgrad nicht.
3/3, 2/3 und 1/3 bleiben ausschließlich COT + Commercial-Netto + Retail-Netto.

Sortierung:
1. COT-Bestätigungsgrad
2. innerhalb derselben Stufe saisonal unterstützt zuerst
3. Richtung / Marktname

Zusätzlich gibt es einen Filter:
`Nur Märkte mit saisonaler 20J/40T-Unterstützung anzeigen`.
