# Installationsanleitung

## Voraussetzungen
- Python 3.10 oder neuer
- Git (optional, für Klonen des Repos)
- Docker (optional, für Container-Betrieb)

## Schnelles Setup (Init-Skripte)
- Windows: `powershell -ExecutionPolicy Bypass -File scripts/init_env.ps1`
- Linux/Pi: `chmod +x scripts/init_env.sh && ./scripts/init_env.sh`
Ergebnis: `.venv`, installierte Dependencies, Ordner `data/logs/data/backups`, Alembic-Migrationen (`upgrade head`) ausgeführt. Standard-DB-Pfad: `data/filamenthub.db`.

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
6. Webinterface im Browser öffnen: [http://localhost:8080](http://localhost:8080)

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
6. Webinterface im Browser öffnen: [http://localhost:8080](http://localhost:8080)

## Installation mit Docker
1. Docker installieren
2. Im Projektverzeichnis:
   ```bash
   docker build -t filamenthub .
   docker run -d -p 8080:8080 -v $(pwd)/data:/app/data filamenthub
   ```
3. Webinterface im Browser öffnen: [http://localhost:8080](http://localhost:8080)

## Installation auf Raspberry Pi
1. Python 3.10+ und Git installieren
2. Schritte wie bei Linux ausführen
3. Optional: Docker nutzen (siehe oben)

## Migrationen (Alembic)
- Lokal (Windows):
  ```powershell
  .venv\Scripts\Activate.ps1
  alembic upgrade head
  ```
- Lokal (Linux/Pi):
  ```bash
  source .venv/bin/activate
  alembic upgrade head
  ```
- Docker:
  ```bash
  docker run --rm -v $(pwd)/data:/app/data filamenthub alembic upgrade head
  ```
Hinweis: `alembic.ini` und `alembic/` müssen im Image/Arbeitsverzeichnis vorhanden sein; DB-Pfad standardmäßig `data/filamenthub.db`.

## Installation auf Unraid
1. Docker-Template/Stack anlegen
2. Image bauen oder aus Registry laden
3. Ports und Volumes konfigurieren (`/data` und `/logs` als persistente Volumes)
4. Container starten

### Beispiel für Unraid/Docker Compose

Falls du mehrere Dienste nutzen willst, kannst du eine `docker-compose.yml` verwenden:

```yaml
version: '3'
services:
  filamenthub:
    build: .
    container_name: filamenthub
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - FILAMENTHUB_DB_PATH=/app/data/filamenthub.db
    restart: unless-stopped
```

Die Datei `entrypoint.sh` muss im Image vorhanden sein und startet FilamentHub automatisch.

## Ports und Konfiguration
- Standard-Port: 8080
- Konfigurierbar über Umgebungsvariablen oder `config.yaml`

## Troubleshooting
- Schreibrechte auf `data/` und `logs/` sicherstellen
- Bei Problemen siehe [Fehlermeldung.md](Fehlermeldung.md)

## Weiterführende Links
- [Handbuch](Handbuch.md)
- [API-Dokumentation](API.md)
