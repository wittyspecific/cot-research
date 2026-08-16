## V3.7.0.1 · Gateway JSON NaN Hotfix

Remote Trade-Plans normalisieren optionale `NaN`/`Infinity`/`pd.NA`-Werte vor HTTPS-JSON jetzt zu `null`, damit Research-Snapshots auch bei fehlenden Einzelmetriken zuverlässig gespeichert werden.

## V3.7.0 · Online Planner / Local Journal Gateway

Dieselbe Codebasis kann jetzt in zwei Modi laufen: `LOCAL` auf dem Mac und `REMOTE_GATEWAY` als Online-Streamlit-App. Online-Login, Trade Planner, Journal und Trader-Verwaltung sprechen über ein authentifiziertes HTTPS-Gateway direkt mit der lokalen Master-SQLite. MT5, FTMO-Kontodaten, Outcome-Sync und H1→M5→M1-Historie bleiben ausschließlich lokal. Der Remote Planner erhält nur Broker-Symbolmetadaten; Live-Bid/Ask/Last, Account, Positionen und Portfolio-Risk werden nicht in die Cloud übertragen. Einrichtung: `ONLINE_DEPLOYMENT.md`.

## V3.6.2.2 · Efficient MT5 History Sync

Der Outcome Tracker ist jetzt für einen sparsamen manuellen Swing-Workflow optimiert. Regulär werden nur `PLANNED`- und `ACTIVE`-Trades betrachtet. Benötigte CFD-Symbole und überlappende Zeiträume werden dedupliziert, historische Bars persistent in SQLite gecacht und bei späteren Syncs nur noch fehlende H1-Zeiträume aus MT5 geladen. M5/M1 bleiben reine Ambiguitäts-Fallbacks. Bereits geprüfte leere Zeiträume (z. B. Wochenende) werden ebenfalls als Coverage gespeichert. Der Auto-Sync beim Journal-Start ist standardmäßig deaktiviert.

## V3.6.2.1 · Swing Outcome Resolution Hotfix

Der Outcome Tracker arbeitet jetzt passend zum Swing-Workflow primär mit **H1-Bars**. Nur wenn die H1-OHLC-Reihenfolge für Entry/SL/TP, eine angefangene Startkerze oder ein Limit-Expiry nicht eindeutig ist, wird derselbe Trade mit **M5** erneut ausgewertet; bleibt er unklar, folgt **M1**. Wenn selbst M1 keine eindeutige Reihenfolge erlaubt, bleibt der Trade explizit `AMBIGUOUS`. Dadurch werden M5/M1-History-Anfragen auf echte Sonderfälle begrenzt. Login, Multi-Trader, Journal-Snapshots, FTMO-Risk und die lokale MT5-Bridge bleiben unverändert.


### V3.6.1 · MT5 Outcome Tracker

Gespeicherte REAL-, SIMULATION- und SKIPPED-Pläne können jetzt rückwirkend mit der echten FTMO-/MT5-CFD-Historie synchronisiert werden. LIMIT-Pläne werden erst bei Berührung des Entries aktiv; optionales Expiry, SL/TP-Reihenfolge, MAE/MFE, +1R/+2R/+3R, Haltedauer und direction-adjusted 1/3/5/10/20/40/60 Trading-Day-Returns werden getrennt vom unveränderlichen Plan-Snapshot in `trade_outcomes` gespeichert. Primär werden H1-Bars verwendet; unklare Intrabar-Fälle werden stufenweise über M5 und anschließend M1 erneut ausgewertet und bleiben bei fortbestehender Unklarheit explizit `AMBIGUOUS`. Die MT5-Bridge enthält weiterhin keinerlei Order-/Close-/Modify-Logik.

### V3.6.0.1 · Vollständiger MT5-CFD-Katalog

Trade Planner und Portfolio & Risk beziehen die handelbaren CFD-Symbole jetzt aus dem vollständigen brokerseitigen MT5-Katalog und nicht mehr nur aus Market Watch. Ausgeblendete, aber für neue Trades freigegebene Symbole bleiben damit planbar. Die MT5-Bridge exportiert Description, Pfad, Trade Mode und Market-Watch-Status; der Symbolkatalog wird getrennt vom schnellen Account-/Positions-Heartbeat aktualisiert.


# COT Marktanalyse — COT Watchlist V2.7

Diese Version stellt die Benutzeroberfläche vollständig auf Deutsch um. Die
internen Variablennamen bleiben aus Gründen der Code-Stabilität unverändert.

## Marktuniversum

- Währungen
- Energie
- Metalle
- Getreide
- Vieh
- Soft Commodities
- Indizes

## Schnellübersicht

Der Kopfbereich beantwortet sechs Fragen:

1. Wurde der richtige CFTC-Kontrakt aufgelöst?
2. In welcher Phase befindet sich der Hedger-Zyklus?
3. Ist das Commercial-Extrem durch die tatsächliche Netto-Positionierung bestätigt?
4. Wie dynamisch verändert sich die Commercial-Positionierung?
5. Wo liegen Non-Commercials auf Level- und Flow-Ebene?
6. Liegt eine Non-Commercial-Divergenz vor?

## Analysebereiche

- Übersicht
- Positionierung
- Hedger-Zyklus
- NC-Divergenz
- Historische Auswertung
- Methodik

## Start im Terminal

```bash
cd /Users/kevinbusch/Downloads/cot_classic_rebuild_v25_de
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Für spätere Starts:

```bash
cd /Users/kevinbusch/Downloads/cot_classic_rebuild_v25_de
source .venv/bin/activate
python3 -m streamlit run app.py
```


## V2.6 — Saisonalität

Die saisonale Logik wurde aus dem bereitgestellten TradingView-Modell adaptiert.

### Saisonkurve

- historische Fenster: 5 / 10 / 15 / 20 / 30 Jahre
- Standard-Ausreißerfilter: IQR-Faktor 2,75
- tägliche historische Renditen werden nach ihrer Handelsposition im Jahr ausgerichtet
- Ausreißer werden für die Kurvenbildung begrenzt
- die durchschnittlichen Tagesbewegungen werden kumulativ aufgezinst

### Forward-Statistik

Für den aktuellen Handelstag im Jahr werden reale historische Forward-Renditen
berechnet:

- 10 Handelstage ≈ 2 Wochen
- 20 Handelstage ≈ 4 Wochen
- 40 Handelstage ≈ 8 Wochen
- 60 Handelstage ≈ 12 Wochen

Ausgegeben werden Stichprobe, Positiv-Quote, Median, Mittelwert,
Standardabweichung, schlechtestes und bestes historisches Jahr.

Die Forward-Statistik verwendet bewusst die tatsächlich realisierten Renditen
ohne Winsorisierung. Der IQR-Filter wird ausschließlich für die geglättete
saisonale Tendenzkurve verwendet.


## V2.7 — COT-Watchlist

Die App bleibt eine Ein-Markt-Detailanalyse, erhält aber einen vorgeschalteten
CFTC-Scan über das gesamte klassische Marktuniversum. Die Watchlist lädt keine
Preisdaten und verwendet daher ausschließlich die COT-Stufen 1–4.

### Gruppen

- Neu betreten: Hedger-Extremdauer = 1 Woche
- Release: aktuelle bzw. noch aktive Hedger-Release-Phase
- Im Extrem: persistierende Extremphase ab Woche 2
- Auffällige Geschwindigkeit ohne Extrem: Commercial-Δ4W im >=90. oder <=10. Perzentil

Es wird ausdrücklich nicht gerankt. Innerhalb jeder Gruppe werden die Märkte
alphabetisch dargestellt. Die Watchlist ist eine Zustands- und
Veränderungsbeschreibung für die anschließende Chartanalyse, keine Setupliste.

Ein Klick auf eine Tabellenzeile übernimmt den Markt in die Einzelauswahl.
NC-Divergenz und Saisonalität werden erst dort geladen, sodass der Watchlist-Scan
keine Volluniversums-yfinance-Abfragen erzeugt.


## V2.8 — statistisch kalibrierte Saisonalität

Die frühere Bezeichnung `BULLISCH/BÄRISCH · ROBUST` wurde entfernt.

### Feste Evidenzstruktur

- Primärhorizont: 10 Handelstage
- Historienfenster: immer 5 / 10 / 15 / 20 / 30 Jahre
- 30 Jahre dienen als langfristige Referenz
- 20 / 40 / 60 Handelstage sind verschachtelte Zoomstufen und keine
  unabhängigen Bestätigungen

### Marktinterne Basisrate

Für jeden Forward-Horizont wird die positive Renditewahrscheinlichkeit über
alle möglichen Kalenderphasen desselben Marktes berechnet. Die saisonale
Positiv-Quote wird gegen diese Basisrate gestellt.

Ausgegeben werden:

- positive Jahre / Stichprobe
- Positiv-Quote
- 95%-Wilson-Konfidenzintervall
- Markt-Basisrate
- Abstand zur Basisrate in Prozentpunkten
- exakter zweiseitiger Binomial-p-Wert
- Median, Mittelwert und Streuung

Der p-Wert wird bewusst nicht als Signifikanz- oder Qualitätssiegel verwendet.
Die marktinterne Basisrate beruht auf überlappenden Forward-Renditen und ist
daher ein explorativer Vergleichsmaßstab.

### Continuous-Futures-Warnung

Yahoo-Continuous-Futures können kalendergebundene Rollsprünge enthalten.
Da diese Sprünge jedes Jahr zu ähnlichen Zeitpunkten auftreten können, stellen
sie für Saisonalitätsanalysen einen systematischen Bias dar. Die aktuelle
Preisreihe ist deshalb als Research-Proxy zu verstehen. Eine rollbereinigte
Futures-Reihe ist für spätere Produktionsentscheidungen vorzuziehen.


## V2.9 — Bedingungs-Watchlist

Die Marktübersicht ist bewusst keine Top-5-Rangliste.

### Hauptbedingungen

Ein Markt erscheint nur dann in der qualifizierten Liste, wenn gleichzeitig:

1. Hedger-Zyklus = `EXTREME` oder `RELEASE`
2. Netto-Validierung = `CONFIRMED`
3. Commercial-Netto = richtungskorrektes `AT / NEAR RANGE HIGH/LOW`

Die Listenlänge ist ein Ergebnis. Eine leere Woche ist zulässig.

### Themen / Komplexe

Bestimmte korrelierte Kontrakte werden als ein Thema gezählt:

- Sojakomplex: ZS / ZM / ZL
- Getreide: ZC / ZW
- Rohölkomplex: CL / RB / HO
- Edelmetalle: GC / SI
- Rindfleisch: LE / GF
- Aktienindizes: ES / NQ / YM / RTY
- USD-Währungsfaktor: EUR / GBP / JPY / CHF / CAD / AUD / NZD

Andere Märkte bilden standardmäßig ein eigenes Thema.

### Rohstoffe vs. Finanzwerte

Rohstoffe und Finanzwerte werden getrennt ausgewiesen. Die Legacy-Commercial-
Kategorie bei Finanzfutures wird nicht mit derselben physischen Hedger-Geschichte
wie bei Rohstoffen beschrieben.

### Knapp verfehlt

`Knapp verfehlt` bedeutet logisch: aktiver Zyklus und genau eine der beiden
zusätzlichen Bestätigungen (Netto oder Range) ist erfüllt. Es gibt keinen
Distanzscore und keine Rangfolge.

Die sekundäre Veränderungsansicht aus V2.7 bleibt erhalten.


## V2.10 — feste Methodik

Die produktiven Analyseparameter wurden in `src/config.py` zentralisiert und
aus dem normalen Sidebar-Workflow entfernt.

Fest eingestellt:

- COT-Index: 26 Wochen
- Index-Extremgrenzen: 80 / 20
- Netto-Historie: 156 Wochen
- Netto-Perzentil-Grenzen: 80 / 20
- Commercial-Extrem-Range: 26 Wochen
- NC-Divergenz: 4 Wochen
- bestätigende NC-Netto-Wochen: 3
- Mindest-Preisbewegung: 1,00 %
- Mindest-NC-Netto-Veränderung / Brutto: 1,00 %
- Mindestveränderung aktiver Schenkel / Brutto: 0,50 %
- Mindestanteil aktiver Aufbau: 0,55
- historische COT-Horizonte: 4 und 8 Wochen
- saisonaler IQR-Faktor: 2,75

Die normale Analyse verwendet ausschließlich diese Werte.

Ein ausklappbarer Sensitivitätsbereich ist vorhanden, aber standardmäßig
deaktiviert. Erst nach bewusster Aktivierung des Sensitivitätsmodus können
Parameter für Forschungszwecke vorübergehend verändert werden. Diese Änderungen
gelten nur für die aktuelle Streamlit-Sitzung und verändern `src/config.py` nicht.

Die Auswahl der sichtbaren Saisonkurven ist weiterhin frei, da sie nur die
Darstellung verändert und nicht die statistische Methodik.


## V2.11 — getrennte Seiten

Die Einzelmarktanalyse und die marktübergreifende Watchlist sind jetzt zwei
eigenständige Streamlit-Seiten.

### COT Marktanalyse

Nur die Detailanalyse des aktuell gewählten Einzelmarkts:

- Übersicht
- Positionierung
- Hedger-Zyklus
- NC-Divergenz
- Saisonalität
- historische Auswertung
- Methodik

Die Watchlist erscheint hier nicht mehr als Tab.

### COT Watchlist

Eigene Seite mit dem Scan über das klassische COT-Universum:

- qualifizierte Kandidaten
- Rohstoffe / Finanzwerte getrennt
- Themen / Komplexe
- knapp verfehlt
- weitere aktive Zyklen
- aktuelle Veränderungen

Der Scan verwendet nur CFTC-Daten. Preisbasierte Analysen werden erst auf der
Detailseite geladen.

Ein Klick auf eine auswählbare Watchlist-Zeile übergibt den Markt per
`st.session_state` und öffnet direkt `COT Marktanalyse`.

### Navigation

Die App verwendet `st.navigation` / `st.Page` aus Streamlit >= 1.40. Beide
Seiten erscheinen sauber getrennt in der linken Navigation.

Start weiterhin unverändert mit:

```bash
python3 -m streamlit run app.py
```


## V3.0 — Data Foundation

Die funktionierende V2.11-Logik wird nicht überschrieben. V3.0 baut die neue
CFTC-Datenbasis parallel auf.

### Report-Typen

- Rohstoffe: Disaggregated Futures Only (`72hh-3qpy`)
- Währungen / Indizes: TFF Futures Only (`gpe5-46if`)
- Legacy Futures Only (`6dca-aqww`) bleibt Benchmark

### Raw Net + Net/OI

Für jede report-spezifische Tradergruppe werden parallel berechnet:

- Raw Net = Long - Short
- Raw-Net-Perzentil über 156 Wochen
- Net/OI = (Long - Short) / Open Interest
- Net/OI-Perzentil über 156 Wochen
- 26W COT-Index
- Raw-Net Δ4W
- Net/OI Δ4W

Raw Net wird nicht ersetzt. Net/OI ist in V3.0 noch keine neue Pflichtregel.

### Kategorien

Disaggregated:
- Producer / Merchant
- Managed Money
- Swap Dealer
- Other Reportables
- Nonreportable

TFF:
- Dealer / Intermediary
- Asset Manager / Institutional
- Leveraged Funds
- Other Reportables
- Nonreportable

### Publikationslag

Historische Forward-Tests starten nicht mehr am COT-Positionsdatum.
Dokumentierte Sonderveröffentlichungen aus 2023 und 2025 werden mit ihren
tatsächlichen CFTC-Publikationsdaten behandelt. Für gewöhnliche ältere Wochen
wird ein konservativer Verfügbarkeitsanker genutzt.

### Neue Seite

`CFTC Datenmodell · V3` zeigt Disaggregated/TFF und Legacy parallel.

Die Watchlist bleibt in V3.0 absichtlich Legacy-basiert, bis die neue Datenbasis
plausibilisiert und neu kalibriert wurde.


## V3.1 — COT Research Lab

Neue eigenständige Research-Seite. Sie verändert die Produktions-Watchlist
nicht automatisch.

### 26W vs. 52W

Für die ausgewählte report-spezifische Positionierungsreihe werden berechnet:

- extreme Wochen 26W / 52W
- P(52W extrem | 26W extrem)
- P(26W extrem | 52W extrem)
- Richtungsübereinstimmung, wenn beide extrem sind
- unabhängige Extrem-Episoden
- Median der Episodendauer
- obere / untere Episoden
- Releases
- 4W / 8W Forward-Renditen nach neuem Extrem
- 4W / 8W Forward-Renditen nach Release

Consecutive Extreme Weeks werden als eine Episode behandelt.

### Release Decay

Für 26W und 52W wird jeder historische Release mit verzögerten Einstiegen
ausgewertet:

- W0
- W1
- W2
- W3
- W4

Je Einstieg werden 4W und 8W gemessen.

Für Producer/Merchant werden zusätzlich richtungsbereinigte Hit Rate,
Median und Mittelwert ausgegeben. Bei TFF-Gruppen wird keine künstliche
bullish/bearish-Konvention erzwungen.

### Nullmodell

Implementiert ist ein per-market Circular Time Shift:

- Event-Abstände und Cluster bleiben erhalten
- Event-Richtungen bleiben erhalten
- der komplette Eventplan wird zirkulär gegen die Preisreihe verschoben
- damit wird die originale zeitliche Verbindung zu Forward-Renditen zerstört

Ausgabe:

- beobachtete Hit Rate
- Median der Null-Hit-Rate
- 95%-Nullbereich
- empirischer p-Wert
- beobachtete richtungsbereinigte Median-Rendite
- 95%-Nullbereich der Median-Rendite

Das ist bewusst noch kein vollständiger family-wise Multiple-Testing-Test
über den gesamten Watchlist-Prozess.

### Richtungsannahmen

Directional Research wird in V3.1 nur automatisch für
`Disaggregated -> Producer/Merchant` aktiviert:

- oberes Producer-Extrem = bullish
- unteres Producer-Extrem = bearish

Für TFF Dealer, Asset Manager und Leveraged Funds werden keine neuen
Produktionsregeln erfunden. Dort bleiben 26W/52W-Struktur und rohe
Upper-/Lower-Forward-Statistiken verfügbar.


## V3.2 — UI Architecture

Reines UI-/Informationsarchitektur-Release:

- Watchlist ist Standardseite
- Watchlist nach Zyklusphase statt Rangfolge
- `selected_market` verbindet Watchlist, Marktanalyse, Research Lab und Datenmodell
- sichtbarer Rückweg zur Watchlist auf allen Unterseiten
- Marktanalyse-Kopf auf sechs Research-Aussagen reduziert
- Fachdefinitionen direkt an den jeweiligen Tabs
- tiefblau-institutionelles Terminal-Theme ohne Verläufe, Schatten oder Rundungen
- Trefferquoten ohne vorhandene unbedingte Basisrate werden in der UI nicht angezeigt
- sämtliche Analyse- und Config-Dateien bleiben unverändert

Details: `UI_ARCHITECTURE_NOTES.md`.


## V3.3 — UI Repair

Reines Darstellungs-Release auf Basis von V3.2.

Behoben:

- HTML-Komponenten werden über `st.html()` statt über den Markdown-Parser
  gerendert. Dadurch erscheinen `context-strip`, Header, Stage Summary,
  Definitionen und Kennzahlen nicht mehr als sichtbarer HTML-Code.
- Die Watchlist verwendet keine riesigen Volltext-Buttons mehr.
- Jede Watchlist-Zeile besitzt feste Research-Spalten:
  Markt, Zyklus, COT 26W, Commercial-Netto-Perzentil, Retail-Netto-Perzentil,
  Validierung und Range.
- Nur der Marktname ist ein kompakter Button zum Öffnen der Detailanalyse.
- Sekundäre Veränderungszeilen wurden ebenfalls in feste Spalten aufgeteilt.
- Typografie wurde leicht vergrößert und die maximale Inhaltsbreite reduziert.

Keine Analyse- oder Config-Datei wurde verändert.


## V3.3.1 — UI Hotfix

Behoben wurde ein Laufzeitfehler in `src/style.py`.

Die in V3.3 ergänzten CSS-Regeln lagen innerhalb eines Python-f-Strings.
Einige CSS-Klammern waren nicht als `{{` / `}}` escaped. Dadurch versuchte
Python CSS-Eigenschaften wie `height` als Python-Ausdruck auszuwerten.

V3.3.1 escaped diese CSS-Klammern korrekt.

Zusätzlich zum Syntaxcheck wird `apply_style()` nun in der Build-Prüfung
tatsächlich ausgeführt, damit f-string/CSS-Laufzeitfehler erkannt werden.

Keine Analyse- oder Config-Logik wurde verändert.


## Readable Web Design

Diese Variante ändert ausschließlich die Darstellung:

- hellere dunkle Flächen
- höherer Textkontrast
- größere Fließ- und Tabellen-Schrift
- mehr vertikaler Abstand
- besser sichtbare Buttons, Tabs, Eingabefelder und Panels
- Streamlit-Theme für konsistente Darstellung auf Community Cloud

Analyse, Inhalte, Navigation und Methodik bleiben unverändert.


## TradingView-like Plotly Interaction

Reines Chart-UX-Update:

- Zeitreihen starten standardmäßig im 3-Jahres-Fenster
- 1J / 3J / 5J / MAX für Datumsachsen
- Mausrad-Zoom
- Drag-to-Pan als Standard
- X- und Y-Achse frei zoombar
- Doppelklick = Reset + Autoscale
- Crosshair / Unified Hover
- reduzierte Plotly-Modebar
- Zoom-Zustand bleibt bei Streamlit-Reruns über `uirevision` stabil

Daten, Berechnungen, Schwellen, Texte und Navigation wurden nicht verändert.


## TradingView Chart Hotfix

Behoben wurden zwei falsche Variablennamen im reinen Chart-UX-Wrapper:

- Hedger-Zyklus: `cycle_history["report_date"]` -> `cot["report_date"]`
- Commercial-Netto-Range: `range_tail["report_date"]` -> `cot["report_date"]`

Beide Charts verwenden bereits `cot` als Datenquelle. Analyse und Daten bleiben unverändert.

## V3.3.2 · Speculativer Flow & robuste Divergenz

Stufe 5 wurde methodisch überarbeitet, ohne die Legacy-Definition zu löschen.

- Preis-/COT-Ausrichtung wird explizit auf Tages-Schlusskurs `<=` COT-Dienstag auditiert.
- Keine Freitag-Wochenaggregation für die Divergenz.
- Neue 4W-Preis- und 4W-Flow-Komponenten werden robust mit Median / `IQR / 1.349` standardisiert.
- Net Position wird für den neuen Flow durch Open Interest normalisiert.
- 8W-Spearman-Pfad mit 9 exakten COT-Wochenpunkten.
- Kein Look-ahead: die aktuelle Beobachtung ist nicht Teil ihres eigenen vorangehenden 156-Kalenderwochen-Fensters.
- Fehlende COT-Wochen werden nicht interpoliert und nicht durch positionsbasiertes `shift(4)` kaschiert.
- Primärer moderner Spekulations-Proxy: Managed Money (Disaggregated) bzw. Leveraged Funds (TFF).
- Legacy-NC bleibt als `nc_divergence_legacy` parallel verfügbar.
- Long-/Short-Schenkel bleiben separat sichtbar.
- Research Lab: Redundanz Legacy vs. modern, Alt-vs.-Neu, Zeitdrift sowie optionaler 51-Märkte-Strukturcheck.
- Keine Forward-Return-Optimierung der neuen Divergenzdefinition.

Details: `NC_DIVERGENZ_METHODIK.md`.


## V3.3.3 · Einfache Watchlist

Die Watchlist wurde für Nutzer ohne Statistik-Hintergrund neu strukturiert.
Die Berechnungs- und Qualifikationslogik bleibt unverändert. Technische
Kennzahlen sind weiterhin pro Markt über „Technische Details anzeigen“
erreichbar.


## V3.3.4 · Minimal COT Ranking

Alternative einfache Watchlist: aktuelle COT-Extreme werden nach der Anzahl
der transparenten Bestätigungen COT / Commercial-Netto / Retail-Netto in
Rang 1 bis 3 gruppiert. Es gibt keinen versteckten Score. Range, Flow,
Divergenz und Saisonalität bleiben Detailinformationen.


## V3.3.5 · Clickable Ranking

Die Marktnamen in der Ranking-Watchlist sind direkt anklickbar. Ein Klick
öffnet die bestehende COT Marktanalyse mit dem ausgewählten Asset.
Ranking- und Analyselogik bleiben unverändert.


## V3.3.6 · Simple Watchlist

Die sichtbare Rang-Spalte wurde entfernt. Die Watchlist bleibt intern nach
3/3, 2/3 und 1/3 Bestätigungen sortiert, zeigt aber keinen künstlichen Rang
mehr. Marktnamen bleiben direkt anklickbar.


## V3.3.7 · Expanded Universe

Das Marktuniversum wurde von 32 auf 36 Märkte erweitert:

- Mexican Peso · MXN · CME · Yahoo `6M=F`
- U.S. Dollar Index · USD · ICE Futures U.S. · Preisproxy Yahoo `DX-Y.NYB`
- Bitcoin · BTC · CME · Yahoo `BTC=F`
- Ether · ETH · CME · Yahoo `ETH=F`

Bitcoin und Ether bilden die neue Assetklasse `Cryptocurrencies`.
Für die moderne CFTC-Auswertung werden sie als Financial Futures behandelt
(TFF / Leveraged Funds); falls diese moderne Serie nicht aufgelöst werden
kann, bleibt der vorhandene Legacy-Non-Commercial-Fallback aktiv.

Die bestehende COT-Watchlist- und Analyseberechnung bleibt unverändert.


## V3.3.8 · Full-width Positioning Comparison

Der COT-Index-Chart in der Marktanalyse ist jetzt vollbreit und gleich hoch
wie der langfristige Netto-Perzentil-Chart. Die rechte Statusbox wurde
entfernt, damit beide Zeitreihen direkt untereinander visuell verglichen
werden können.


## V3.3.9 · Full 51-Market Universe

15 weitere Märkte wurden ergänzt:

- Orange Juice · OJ
- VIX Futures · VIX
- U.S. Treasury 2Y · ZT
- U.S. Treasury 5Y · ZF
- U.S. Treasury 10Y · ZN
- U.S. Treasury Bond 30Y · ZB
- Ultra U.S. Treasury Bond · UB
- Wheat HRW · KE
- Wheat Hard Red Spring · MWE
- Rough Rice · ZR
- Lumber · LBR
- Brazilian Real · BRL
- South African Rand · ZAR
- Brent Crude Oil · BZ
- Canola · RS

Gesamtuniversum: 51 Märkte.

Für alle 15 neuen CFTC-Märkte ist der offizielle Contract Market Code
hinterlegt. Die Resolver verwenden diesen exakten Code vor der Namenssuche.

Brent `LAST DAY` wird gezielt erlaubt, ohne den allgemeinen Schutz gegen
unerwünschte Last-Day-/Micro-/Spread-Serien aufzuheben.

HRSpring und Canola werden ohne erzwungenen Yahoo-Continuous-Ticker geführt;
ihre COT-Analyse ist vollständig verfügbar. Beim VIX dient `^VIX` nur als
Preisproxy, während die Positionierungsdaten aus VIX Futures stammen.


## V3.4.0 · Forex COT Matrix

Separate Forex-Seite mit 55 Crosses aus 11 COT-Währungen.

Der Pair-Bias basiert ausschließlich auf der relativen 1/3–3/3-COT-Stärke.
Zusätzlich wird für jedes tatsächliche Base/Quote-Paar separat die
Saisonalität der letzten 20 abgeschlossenen Jahre für die kommenden
40 Handelstage berechnet.

Die Seasonality bestätigt oder widerspricht dem COT-Bias, verändert ihn
aber nicht.


## V3.4.1 · Normal-Asset Watchlist + 40T Seasonality

Die normale COT Watchlist zeigt nun zusätzlich die 20J/40T-Saisonalität.
Sie wird als separate Confluence dargestellt und verändert die 1/3–3/3
Positionierungsbestätigung nicht.

Innerhalb derselben COT-Stufe werden saisonal unterstützte Märkte zuerst
angezeigt. Ein optionaler Filter zeigt nur unterstützte Setups.


## V3.4.2 · 20/40/60T Seasonality

Normale Watchlist und Forex COT Matrix zeigen nun parallel die saisonale Unterstützung über 20, 40 und 60 Handelstage auf Basis der letzten 20 abgeschlossenen Jahre. Die Horizonte dienen als Persistenz-/Timing-Kontext und nicht als automatische Exit-Regel.


## V3.4.4 · Non-Commercial Netto-Perzentil

Watchlist und Forex Scanner verwenden nun zusätzlich das Legacy
Non-Commercial Netto-Perzentil als vierte Positionierungsbedingung.

Bullish bestätigt NC, wenn sein langfristiges Netto-Perzentil <=20 liegt.
Bearish bestätigt NC, wenn es >=80 liegt.

Die Anzeige wird damit 1/4 bis 4/4. Seasonality bleibt separat.
Commercial und Legacy NC sind nicht vollständig unabhängige Gruppen;
4/4 bezeichnet deshalb ein geschlossenes Positionierungsbild, keinen
statistisch unabhängigen Vierfach-Score.


## V3.4.4.4 · TradingView-like Y-Axis Scaling

Alle Plotly-Charts verwenden jetzt einen zentralen Chart-Renderer mit einer
TradingView-ähnlichen Y-Skalen-Interaktion. Durch vertikales Ziehen auf der
Y-Achse wird ausschließlich die sichtbare Y-Range gestreckt oder gestaucht;
Daten und X-Zeitraum bleiben unverändert. Der Mittelpunkt der beim Drag
sichtbaren Range bleibt stabil. Die Interaktion arbeitet mit
`requestAnimationFrame` und `Plotly.relayout()` und ist für sämtliche Charts
wiederverwendbar.


## V3.6.2 · Multi-Trader Foundation

Der Trade Planner und das Trading Journal unterstützen jetzt getrennte Trader-Identitäten. Beim ersten Start wird lokal ein ADMIN-Konto angelegt; vorhandene Legacy-Pläne ohne Owner können einmalig diesem Admin zugeordnet werden. Weitere Trader werden über `Trader verwalten` angelegt.

Normale TRADER können Watchlist, Trade Planner, eigenes Trading Journal, Marktanalyse und Research verwenden. Risk Cockpit, Portfolio & Risk und FTMO-Kontodetails bleiben ADMIN-only. Alle Simulationen verwenden weiterhin dieselbe lokale read-only MT5-Kurshistorie für den Outcome Tracker.

Die Passwörter werden nicht im Klartext gespeichert, sondern als PBKDF2-SHA256-Hash mit individuellem Salt in derselben persistenten lokalen SQLite-Datenbank. Die Trader-ID wird als Metadatum gespeichert und nicht automatisch als ML-Feature behandelt.
