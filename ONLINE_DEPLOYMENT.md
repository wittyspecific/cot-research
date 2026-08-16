# Online Planner → lokale Master-SQLite → lokaler MT5 Outcome Sync

## Architektur

```text
Trader Browser
    |
    v
Online Streamlit (GitHub deploy)
    |  serverseitig HTTPS + Gateway-Key + Trader-Session
    v
HTTPS Tunnel / Reverse Proxy
    |
    v
127.0.0.1:8765 auf dem Mac
COT Journal Gateway
    |
    +--> lokale trading_journal.sqlite3
    |
    +--> nur Symbol-Metadaten aus der lokalen MT5-Bridge

Separat auf dem Mac:
LOCAL Streamlit -> manueller Outcome Sync -> MT5 Bridge -> MARKET Fill M15/M5/M1 -> H1/M5/M1 -> SQLite
```

Die Online-App besitzt keine zweite Journal-Datenbank. Wenn ein Trader auf **Speichern** klickt, bestätigt das Gateway den Plan erst, nachdem er in der lokalen Master-SQLite geschrieben wurde. Ist dein Mac/Gateway nicht erreichbar, wird der Plan nicht stillschweigend irgendwo anders gespeichert; der Trader erhält einen Fehler und muss später erneut speichern.

## Sicherheitsgrenzen

Die Online-Instanz bekommt keine MT5-Zugangsdaten, keinen lokalen SQLite-Pfad und keine FTMO-Konto-/Positionsdaten. Das Gateway entfernt Live-Bid/Ask/Last aus dem öffentlich verwendeten Broker-Katalog. Auch historische lokale ADMIN-Snapshots werden vor der Online-Ausgabe gefiltert. Der Outcome-Sync und alle MT5-History-Anfragen bleiben ausschließlich in `LOCAL`.

Das Gateway lauscht standardmäßig nur auf `127.0.0.1`. Den Port **nicht direkt am Router freigeben**. Für die Online-App wird eine HTTPS-Adresse eines Tunnels oder Reverse-Proxys benötigt, die auf `http://127.0.0.1:8765` weiterleitet.

## 1. Lokale Version vorbereiten

```bash
cd /Users/kevinbusch/Downloads/cot_research_v370_online_local_gateway_deutsch_clean
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Bestehende lokale Secrets aus V3.6.2.2 übernehmen:

```bash
cp "/Users/kevinbusch/Downloads/cot_research_v3622_efficient_mt5_sync_deutsch_clean/.streamlit/secrets.toml" "/Users/kevinbusch/Downloads/cot_research_v370_online_local_gateway_deutsch_clean/.streamlit/secrets.toml"
```

Danach in der lokalen `.streamlit/secrets.toml` ergänzen:

```toml
[deployment]
mode = "LOCAL"

[gateway]
shared_key = "EIN_LANGES_ZUFAELLIGES_SECRET"
session_hours = 12
```

Ein Secret erzeugen:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

## 2. Lokales Gateway starten

In einem eigenen Terminal:

```bash
cd /Users/kevinbusch/Downloads/cot_research_v370_online_local_gateway_deutsch_clean
source .venv/bin/activate
python3 -m gateway.journal_gateway --host 127.0.0.1 --port 8765
```

Lokaler Health-Check:

```bash
curl http://127.0.0.1:8765/v1/health
```

## 3. Lokale Master-App starten

In einem zweiten Terminal:

```bash
cd /Users/kevinbusch/Downloads/cot_research_v370_online_local_gateway_deutsch_clean
source .venv/bin/activate
python3 -m streamlit run app.py
```

Nur diese LOCAL-Instanz zeigt Risk Cockpit / Portfolio & Risk und den Button **MT5 Outcomes jetzt synchronisieren**.

## 4. Sichere HTTPS-Adresse bereitstellen

Richte einen HTTPS-Tunnel oder Reverse-Proxy ein, der von außen auf `http://127.0.0.1:8765` zeigt. Trage die resultierende `https://...`-Adresse später als `gateway.base_url` in den Online-Secrets ein.

Der Gateway-Key ist eine zweite Schutzschicht zusätzlich zu den individuellen Trader-Logins. Nutze für den Tunnel selbst ebenfalls Zugriffsschutz, wenn dein Anbieter dies unterstützt.

## 5. GitHub

Vor dem ersten Commit prüfen:

```bash
cd /Users/kevinbusch/Downloads/cot_research_v370_online_local_gateway_deutsch_clean
git status
```

Die echte `.streamlit/secrets.toml`, SQLite-Dateien, virtuelle Umgebung und Schlüsseldateien müssen durch `.gitignore` ausgeschlossen bleiben.

Neues Repository:

```bash
git init
git add .
git status
git commit -m "V3.7.0 online planner local journal gateway"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Bei einem bestehenden Repository reichen normalerweise:

```bash
git add .
git status
git commit -m "V3.7.0 online planner local journal gateway"
git push
```

## 6. Online Streamlit Secrets

In der Online-Deployment-Umgebung ausschließlich diese Art Secrets setzen:

```toml
[deployment]
mode = "REMOTE_GATEWAY"

[gateway]
base_url = "https://DEINE-GATEWAY-ADRESSE"
shared_key = "DASSELBE_SECRET_WIE_AUF_DEM_MAC"
timeout_seconds = 15
verify_tls = true
```

Keine MT5-Passwörter, keine lokale `db_path` und keine Mac-Dateipfade in die Cloud-Secrets kopieren.

## Laufender Workflow

1. Trader loggt sich online ein.
2. Login wird über HTTPS am lokalen Gateway gegen die lokale Trader-Tabelle geprüft.
3. Trader plant CFD, S&D-Zone, Entry, SL, TP usw.
4. Beim Speichern schreibt das Gateway den Plan + Snapshot direkt in die lokale SQLite.
5. Online Journal liest denselben lokalen Master-Stand über das Gateway.
6. Mittwoch/Freitag öffnet der ADMIN lokal das Journal und startet den Outcome Sync.
7. Nur PLANNED/ACTIVE-Symbole werden geprüft. LIMIT läuft H1→M5→M1; MARKET löst zuerst den Fill M15→M5→M1 und wechselt danach in denselben H1-Pfad.
8. Ergebnisse landen in derselben SQLite und sind beim nächsten Online-Journal-Aufruf sichtbar.
