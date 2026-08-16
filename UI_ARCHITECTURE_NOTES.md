
# V3.2 · UI-Architektur

## Neue Informationsarchitektur

### 1. Watchlist ist Startseite
Der wöchentliche Workflow beginnt jetzt bei der einzigen Frage, die vor der
Detailanalyse relevant ist: Welche Märkte stehen in ungewöhnlicher
Positionierung?

Die Watchlist wird nicht gerankt. Qualifizierte Märkte werden nach
Zyklusphase gegliedert:

1. NEU IM EXTREM
2. EXTREM · PERSISTENZ
3. RELEASE

Innerhalb jeder Phase bleibt die Reihenfolge alphabetisch. Themen/Komplexe
werden als Kontext in der Zeile geführt, nicht als Rankingebene.

### 2. Marktanalyse = sechs Aussagen vor den Tabs
Die frühere Kopfverdichtung wurde auf sechs Zeilen reduziert:

1. COT-Index
2. Netto-Validierung
3. Positionierungs-Velocity
4. Hedger-Zyklus
5. Spekulativer Flow · Divergenz sekundär
6. Saisonalität

Marktauflösung, CFTC-Code und Datumsangaben liegen getrennt in einer schmalen
Kontextzeile und zählen nicht als Analysestufe.

### 3. Detailwerte wandern in die Fach-Tabs
Die Tabs sind direkt auf die sechs Stufen ausgerichtet:

- 1 · COT-Index
- 2–3 · Netto & Flow
- 4 · Hedger-Zyklus
- 5 · Spec-Flow
- 6 · Saisonalität
- Historie
- Methodik

Fachbegriffe werden dort erklärt, wo sie auftreten.

### 4. Research Lab und Datenmodell sind Kontrollseiten
Aus der Marktanalyse führen sichtbare Links in beide Kontrollseiten. Der
ausgewählte Markt wird über `st.session_state["selected_market"]` weitergereicht.
Jede Unterseite besitzt einen sichtbaren Rückweg zur Watchlist.

## Methodik unverändert

Folgende Dateien wurden beim UI-Umbau byte-identisch gelassen:

- src/analysis.py
- src/cftc.py
- src/cftc_reports.py
- src/config.py
- src/markets.py
- src/prices.py
- src/publication.py
- src/report_analysis.py
- src/research_lab.py
- src/seasonality.py
- src/watchlist.py

## Auffällige methodische Stellen — NICHT geändert

1. **Legacy-Watchlist vs. V3-Datenmodell**
   Die produktive Watchlist nutzt weiterhin die Legacy-Benchmark-Logik, obwohl
   Disaggregated/TFF bereits als neue Datenbasis parallel vorhanden sind.

2. **Hit Rates ohne unbedingte Basisrate**
   `summarize_events`, `summarize_releases` und Teile des Research Labs
   berechnen Trefferquoten, aber nicht überall eine unbedingte Vergleichsrate
   des Marktes. Die Berechnung blieb unverändert; die UI zeigt diese Hit Rates
   in V3.2 deshalb nicht mehr. Die Saisonalität ist nicht betroffen, weil dort
   die Markt-Basisrate bereits berechnet und daneben angezeigt wird.

3. **26W als Produktionsfenster**
   `COT_INDEX_WEEKS = 26` bleibt unverändert, obwohl das Research Lab den
   Vergleich 26W vs. 52W erst noch empirisch entscheiden soll.

4. **Net/OI noch nicht Teil der Legacy-Watchlist**
   Die report-spezifische V3-Datenbasis berechnet Net/OI, die bestehende
   Watchlist-Qualifikation wurde jedoch nicht migriert.

5. **Continuous-Futures-Preisreihen**
   Yahoo-Continuous-Futures können Rollartefakte enthalten. Das ist besonders
   für Saisonalität relevant, kann aber auch Event-Returns beeinflussen.

6. **Historischer Publikationszeitpunkt**
   Sonderveröffentlichungen sind explizit hinterlegt. Für normale ältere
   COT-Wochen verwendet die bestehende Logik einen konservativen
   Verfügbarkeitsanker statt einer vollständigen historischen Liste exakter
   Release-Zeitpunkte.

7. **TFF-Richtungssemantik**
   Dealer, Asset Manager und Leveraged Funds werden im Research Lab nicht
   automatisch in eine erfundene bullish/bearish-Hedgerlogik gezwungen. Das
   bleibt methodisch korrekt offen.

## V3.5.4 · Strukturierte Navigation

Die Sidebar ist nun in **SCHNELLÜBERBLICK**, **MARKT & PORTFOLIO** und **RESEARCH** gegliedert. Watchlist und Risk Cockpit bilden die kompakte operative Ebene; Detailanalyse und Research sind visuell getrennt.
