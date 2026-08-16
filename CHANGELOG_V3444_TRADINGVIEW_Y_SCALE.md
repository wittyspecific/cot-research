# V3.4.4.4 · TradingView-like Y-Axis Scaling

## Neu

Für alle Plotly-Charts wird die Y-Achsen-Skalierung jetzt über einen zentralen,
wiederverwendbaren Renderer in `src/style.py` bereitgestellt.

### Interaktion

- Vertikales Ziehen auf der sichtbaren Y-Skala verändert ausschließlich die sichtbare Y-Range.
- Drag nach oben verkleinert die sichtbare Range und streckt den Chart vertikal.
- Drag nach unten vergrößert die sichtbare Range und staucht den Chart vertikal.
- Der Mittelpunkt der beim Drag gestarteten Y-Range bleibt konstant.
- Die Skalierung wird über eine exponentielle Drag-Kennlinie kontinuierlich berechnet.
- Updates werden mit `requestAnimationFrame` gebündelt.
- Doppelklick auf die Y-Skala stellt die automatische Y-Skalierung wieder her.

## Unverändert

- zugrunde liegende Datenreihen
- X-Achse und sichtbarer Zeitraum
- 1J / 3J / 5J / MAX
- Pan / Scroll-Zoom / Unified Hover
- COT-, Seasonality-, Divergenz- und Research-Methodik

## Implementierung

`tradingview_plotly_chart()` rendert Plotly isoliert und ergänzt eine transparente
Interaktionsfläche über der Y-Skala. Während des Ziehens wird ausschließlich
`<yaxis>.range` über `Plotly.relayout()` aktualisiert. Weder Trace-Daten noch
`xaxis.range` werden verändert.

Alle neun bestehenden Plotly-Charts in `pages/marktanalyse.py` und
`pages/research_lab.py` verwenden diesen Renderer.
