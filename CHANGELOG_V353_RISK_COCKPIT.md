# V3.5.3 · Risk Cockpit

- Neue kompakte Seite **Risk Cockpit** zusätzlich zur ausführlichen Portfolio-&-Risk-Seite.
- 5-Sekunden-Ansicht: Risk-Desk-Ampel, Equity/Snapshot-Kontext, FTMO Daily- und Max-Loss-Puffer, Open Stop Risk und freie Portfolio-Risk-Capacity.
- Zeigt nur die drei größten Risikotreiber statt aller Detailtabellen.
- Kompakte Risk-Capacity nach Cluster; negative Restbudgets werden als 0 neue Capacity dargestellt.
- All-Stops-/Weekend-Stress wird nur dann prominent eingeblendet, wenn ein interner Sicherheitsfloor verletzt wird.
- Die ausführlichen Instrument-, Cluster-, FX-Faktor- und Pre-Trade-Tabellen bleiben unverändert auf **Portfolio & Risk** verfügbar.
- Cockpit und Detailseite verwenden dieselbe `src.ftmo_risk`-Berechnungslogik; keine separate Risikomethodik.
