# V3.8.1.1 · Currency 20/40/60T Seasonality

- Forex-Währungsübersicht um eine kompakte Spalte `Saison 20/40/60T` erweitert.
- Darstellung: `▲` bullish, `▼` bearish, `—` gemischt, `·` nicht verfügbar.
- 20 abgeschlossene Jahre; 20/40/60 Handelstage voraus.
- Richtungslogik entspricht der bestehenden Watchlist-Seasonality.
- Alle neun Währungs-Preisproxies werden in einem Batch geladen, statt je Währung eine einzelne Anfrage zu erzeugen.
- Seasonality bleibt strikt separater Kontext und verändert den COT-Score 1/4–4/4 nicht.
