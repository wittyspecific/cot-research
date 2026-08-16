# Speculativer Flow & Divergenz · V3.3.2

## Zweck

Die bisherige Legacy-NC-Divergenz bleibt als `nc_divergence_legacy` erhalten. Die neue Produktionsdarstellung von Stufe 5 verwendet stattdessen einen robusten, OI-normalisierten spekulativen Flow und behandelt die Divergenz als separaten Zustand relativ zum Preis.

Primärer Spekulations-Proxy:

- Rohstoffe / Disaggregated: **Managed Money**
- Währungen und Indizes / TFF: **Leveraged Funds**
- Legacy Non-Commercial: nur Vergleich / Fallback

Managed Money bzw. Leveraged Funds werden nicht als mathematisch identischer Ersatz für Legacy Non-Commercial interpretiert. Die modernen Reportstrukturen trennen weitere Gruppen explizit.

## 0. Preis-/COT-Ausrichtung

`load_prices()` lädt Tagesdaten und aggregiert **nicht** auf Freitagsschluss. Für jeden COT-Stichtag wird mit `align_prices_to_cot()` der letzte verfügbare Tages-Schlusskurs mit

`price_date <= report_date`

ausgewählt. Zusätzlich muss der Schlusskurs in derselben ISO-Kalenderwoche wie der COT-Stichtag liegen. Das genaue Preisdatum wird als `cot_price_date` gespeichert und mit `cot_price_alignment_ok` auditierbar gemacht.

Ein Preis nach dem COT-Stichtag ist unzulässig. Fehlt ein Preis in derselben COT-Woche, wird die Beobachtung für die Divergenzberechnung ungültig statt auf einen späteren oder stillschweigend verschobenen Schlusskurs auszuweichen.

## 1. Neue Divergenz

### Preis

Vier-Wochen-Logrendite, exakt Dienstag/COT-Woche zu Dienstag/COT-Woche:

`r_4w = log(price_t / price_t-4W)`

Robuste Standardisierung:

`z_price = (r_4w - Median(history)) / (IQR(history) / 1.349)`

Die Referenz verwendet das exakte vorangehende **156-Kalenderwochen-Fenster** `[t-156W, t)`. Fehlende Reportwochen werden darin nicht interpoliert; vorhandene gültige Beobachtungen innerhalb dieses Fensters werden verwendet. Der aktuelle Wert `t` ist nie Bestandteil seiner eigenen Referenzverteilung.

### Flow

`spec_net_oi = (Long - Short) / OpenInterest`

`d_flow_4w = spec_net_oi_t - spec_net_oi_t-4W`

`z_flow` wird mit derselben prior-only Median/IQR-Methodik über das exakte vorangehende 156-Kalenderwochen-Fenster standardisiert.

### Pfad

`rho` ist die Spearman-Rangkorrelation zwischen Preis und `spec_net_oi` über acht Wochen, also neun exakte wöchentliche Punkte. Fehlt eine COT-Woche in diesem Pfad, wird `rho` nicht berechnet; es wird nicht interpoliert.

### Klassifikation

Bullisch:

- `z_price <= -1.0`
- `z_flow >= +1.0`
- `rho < 0`

Bärisch: Vorzeichen gespiegelt.

Die Schwelle `1.0` ist eine feste methodische Setzung und **kein optimierter Wert**.

### Stärke

`divergence_strength = min(|z_price|, |z_flow|) * |rho|`

Zusätzlich wird das Perzentil dieser Stärke gegenüber **früheren Divergenz-Stärken innerhalb der vorangehenden 156 Kalenderwochen** desselben Marktes ausgewiesen. Die Referenzfallzahl wird mit ausgegeben. Diese Größe wird nicht mit anderen Ebenen zu einem Gesamtscore aggregiert.

## 2. Long-/Short-Schenkel

Die vorhandene Zerlegung bleibt separat erhalten:

- BULLISH · ACTIVE LONG BUILD
- BULLISH · SHORT COVERING
- BULLISH · NET BUILD
- BEARISH · ACTIVE SHORT BUILD
- BEARISH · MIXED DISTRIBUTION
- LONG LIQUIDATION / PROFIT TAKING
- BEARISH · NET REDUCTION

Die bisherigen Gross-Normalisierungen und Schenkel-Schwellen bleiben bestehen. Der Schenkelbefund beschreibt **wie** der Flow zustande kommt und ist nicht Teil des Divergenz-Flags oder der Divergenz-Stärke.

## 3. Redundanzprüfung

Für Legacy wird Commercial Δ4W gegen Non-Commercial Δ4W geprüft. Für moderne Reports werden verglichen:

- Disaggregated: Producer / Merchant vs. Managed Money
- TFF: Dealer / Intermediary vs. Leveraged Funds

Ausgegeben werden je Markt:

- Pearson-Korrelation raw Δ4W
- Pearson-Korrelation Net/OI Δ4W
- durch Hedger-Flow erklärte Varianz des spekulativen Flows
- Restvarianz
- R², mit dem NonReportable die Restdifferenz des betrachteten Paares erklärt

Interpretation:

- `|r| > 0.85`: weitgehend redundant; nicht als unabhängige Bestätigung zählen
- `|r| < 0.60`: zusätzlicher Informationsanteil strukturell plausibel
- dazwischen: teilweise gekoppelt

Diese Diagnose ist eine Strukturprüfung, kein Trading-Score.

## 4. Alt vs. neu

Im Research Lab werden auf derselben Legacy-Datenbasis verglichen:

- Zahl alter Divergenzepisoden
- Zahl neuer robuster Divergenzepisoden
- Überschneidung der Ereigniswochen
- Signale pro Jahr

Zusätzlich kann ein 51-Märkte-Strukturcheck gestartet werden. Dieser vergleicht die Signalhäufigkeit je Markt mit einer marktinternen 4W-Volatilitätskennzahl und zeigt die jährliche Signalzahl über das gesamte Universum.

Es werden in diesem Schritt **keine Forward-Returns** zur Auswahl der Definition verwendet. Die Entscheidung soll strukturell erfolgen: gleichmäßigere Verteilung, geringere Volatilitätsabhängigkeit, keine offensichtliche Zeitdrift und transparente Redundanz.

## 5. Fehlende COT-Wochen

Vier- und Acht-Wochen-Fenster werden anhand exakter Kalenderwochen-Lags aufgebaut. Ein fehlender Report macht das betreffende Fenster ungültig; `shift(4)` wird nicht als Ersatz für ein echtes 4W-Fenster verwendet.

Für die 156W-Referenz werden fehlende Messwerte nicht interpoliert. Es werden nur gültige, bereits bekannte Beobachtungen innerhalb des exakten Zeitfensters `[t-156W, t)` verwendet.
