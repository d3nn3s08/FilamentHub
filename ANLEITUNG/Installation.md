# Installationsanleitung

## Voraussetzungen
- Python 3.10 oder neuer
- Git (optional, für Klonen des Repos)
- Docker (optional, für Container-Betrieb)

## Installation unter Windows
1. Repository klonen oder herunterladen
2. In das Projektverzeichnis wechseln
3. Virtuelle Umgebung erstellen:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
4. Abhängigkeiten installieren:
   ```powershell
   pip install -r requirements.txt
   ```
5. App starten:
   ```powershell
   python run.py
   ```
6. Webinterface im Browser öffnen: [http://localhost:8000](http://localhost:8000)

## Installation unter Linux
1. Repository klonen oder herunterladen
2. In das Projektverzeichnis wechseln
3. Virtuelle Umgebung erstellen:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```
5. App starten:
   ```bash
   python run.py
   ```
6. Webinterface im Browser öffnen: [http://localhost:8000](http://localhost:8000)

## Installation mit Docker
1. Docker installieren
2. Im Projektverzeichnis:
   ```bash
   docker build -t filamenthub .
   docker run -d -p 8000:8000 -v $(pwd)/data:/app/data filamenthub
   ```
3. Webinterface im Browser öffnen: [http://localhost:8000](http://localhost:8000)

## Installation auf Raspberry Pi
1. Python 3.10+ und Git installieren
2. Schritte wie bei Linux ausführen
3. Optional: Docker nutzen (siehe oben)

## Installation auf Unraid
1. Docker-Template/Stack anlegen
2. Image bauen oder aus Registry laden
3. Ports und Volumes konfigurieren (`/data` und `/logs` als persistente Volumes)
4. Container starten

## Ports und Konfiguration
- Standard-Port: 8080
- Konfigurierbar über Umgebungsvariablen oder `config.yaml`

## Troubleshooting
- Schreibrechte auf `data/` und `logs/` sicherstellen
- Bei Problemen siehe [Fehlermeldung.md](Fehlermeldung.md)

## Weiterführende Links
- [Handbuch](Handbuch.md)
- [API-Dokumentation](API.md)
