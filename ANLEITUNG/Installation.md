<<<<<<< Updated upstream
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
=======
﻿# FilamentHub - Installationsanleitung

## Voraussetzungen
- **Für lokale Installation:** Python 3.10 oder neuer
- **Für Docker/Unraid:** Docker oder Docker Compose
- Git (optional, zum Klonen des Repositories)

---

## Installation mit Docker (Empfohlen)

### Docker Compose (Unraid / Linux / NAS)

**1. Dateien vorbereiten**
```bash
# Projektverzeichnis erstellen
mkdir -p /mnt/user/appdata/filamenthub
cd /mnt/user/appdata/filamenthub

# Projekt-Dateien hochladen (siehe unten)
```

**2. Erforderliche Dateien**

Alle benötigten Dateien sind bereits im Repository enthalten:
- `docker-compose.yml`
- `Dockerfile`
- `.env` (enthält Fake-Hash, muss für Admin-Zugang überschrieben werden)
- `entrypoint.sh`
- `alembic.ini`
- `config.yaml`
- `requirements.txt`
- Ordner: `app/`, `alembic/`, `frontend/`, `services/`, `utils/`

> **Hinweis für Nutzer:** Die App funktioniert sofort ohne Konfiguration!
> Der Admin-Bereich ist optional und nur für Entwickler/Administratoren.

**3. Admin-Bereich (Nur für Entwickler - überspringen für normale Nutzer)**

> **Hinweis für Nutzer:** Der Admin-Bereich ist **NICHT** für normale Benutzer!
> **Die App funktioniert vollständig ohne Admin-Zugang.** Überspringen Sie diesen Schritt.

> **Hinweis für Entwickler:** Die `.env` Datei im Repository enthält einen Fake-Hash.
> Verwenden Sie Ihre separate `.env` mit dem echten Admin-Hash auf Ihrem Server.
> **Admin-Zugang wird nur auf Anfrage beim Entwickler vergeben.**

**4. Container bauen und starten**

```bash
# Image bauen (ohne Cache für sauberen Build)
docker build --no-cache -t filamenthub .

# Mit Docker Compose starten
docker-compose up -d

# Logs anschauen
docker-compose logs -f
```

**5. Container verwalten**

```bash
# Status prüfen
docker-compose ps

# Logs anzeigen
docker-compose logs -f

# Container neu starten
docker-compose restart

# Container stoppen
docker-compose down

# Container neu bauen nach Code-Änderungen
docker-compose down
docker build --no-cache -t filamenthub .
docker-compose up -d
```

**6. Health Check**
```bash
curl http://localhost:8085/health
# Erwartete Antwort: {"status":"healthy","service":"filamenthub"}
```

**7. Zugriff**
- **Web-Interface:** `http://<server-ip>:8085`
- **Admin-Panel (Developer only):** `http://<server-ip>:8085/admin`
- **API-Docs:** `http://<server-ip>:8085/docs`

---

## Docker-Konfiguration (docker-compose.yml)

Aktuelle empfohlene Konfiguration:

```yaml
services:
  filamenthub:
    container_name: filamenthub
    image: filamenthub:latest
    restart: unless-stopped
    network_mode: host
    env_file:
      - .env
    environment:
      FILAMENTHUB_DB_PATH: /app/data/filamenthub.db
      PYTHONPATH: /app
    volumes:
      - /mnt/user/appdata/filamenthub/data:/app/data
      - /mnt/user/appdata/filamenthub/logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8085/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    entrypoint: ["./entrypoint.sh"]
```

**Wichtige Punkte:**
- `network_mode: host` - Verwendet Host-Netzwerk (keine Port-Mappings nötig)
- `env_file: - .env` - Lädt Umgebungsvariablen aus .env Datei
- Volumes für persistente Daten (`data/`) und Logs (`logs/`)
- Health Check prüft alle 30s ob die App läuft

---

## Installation lokal (Entwicklung)

### Windows

**1. Repository klonen**
```powershell
git clone https://github.com/your-repo/FilamentHub.git
cd FilamentHub
```

**2. Virtuelle Umgebung erstellen**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**3. Abhängigkeiten installieren**
```powershell
pip install -r requirements.txt
```

**4. .env Datei erstellen**
```powershell
# In PowerShell
@"
ADMIN_PASSWORD_HASH=`$2b`$12`$L5hUkHdH.NH6CeC6FiH0o.lpnNpRA3zaAho6QyerwP3ZQF19xqmmq
ADMIN_COOKIE_SECURE=false
"@ | Out-File -Encoding UTF8 .env
```

> **Hinweis:** Platzhalter-Hash! Generiere deinen eigenen Hash für den Admin-Zugang.

**5. Datenbank initialisieren**
```powershell
# Ordner erstellen
mkdir -p data, logs

# Migrationen ausführen
alembic upgrade head
```

**6. App starten**
```powershell
python run.py
```

**7. Webinterface öffnen**
- http://localhost:8085

### Linux / Raspberry Pi

**1. Repository klonen**
```bash
git clone https://github.com/your-repo/FilamentHub.git
cd FilamentHub
```

**2. Virtuelle Umgebung erstellen**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**3. Abhängigkeiten installieren**
```bash
pip install -r requirements.txt
```

**4. .env Datei erstellen**
```bash
cat > .env << 'EOF'
ADMIN_PASSWORD_HASH=$2b$12$L5hUkHdH.NH6CeC6FiH0o.lpnNpRA3zaAho6QyerwP3ZQF19xqmmq
ADMIN_COOKIE_SECURE=false
EOF
```

> **Hinweis:** Platzhalter-Hash! Generiere deinen eigenen Hash für den Admin-Zugang.

**5. Datenbank initialisieren**
```bash
# Ordner erstellen
mkdir -p data logs

# Migrationen ausführen
alembic upgrade head
```

**6. App starten**
```bash
python run.py
```

**7. Webinterface öffnen**
- http://localhost:8085

---

## Datenbank-Migrationen (Alembic)

FilamentHub nutzt Alembic für Datenbank-Schema-Updates.

### Lokale Installation

**Windows:**
```powershell
.venv\Scripts\Activate.ps1
alembic upgrade head
```

**Linux/Pi:**
```bash
source .venv/bin/activate
alembic upgrade head
```

### Docker

Migrationen werden automatisch beim Container-Start ausgeführt durch `entrypoint.sh`.

**Manuelle Migration im laufenden Container:**
```bash
docker exec -it filamenthub alembic upgrade head
```

**Migration mit temporärem Container:**
```bash
docker run --rm \
  -v /mnt/user/appdata/filamenthub/data:/app/data \
  filamenthub \
  alembic upgrade head
```

### Bestehende Datenbank stampen

Falls du eine existierende Datenbank hast (ohne Alembic-Versionierung):

```bash
# Im Container
docker exec -it filamenthub alembic stamp head

# Oder lokal
alembic stamp head
```

---
>>>>>>> Stashed changes

## Ports und Konfiguration
- Standard-Port: 8080
- Konfigurierbar über Umgebungsvariablen oder `config.yaml`

## Troubleshooting
<<<<<<< Updated upstream
- Schreibrechte auf `data/` und `logs/` sicherstellen
- Bei Problemen siehe [Fehlermeldung.md](Fehlermeldung.md)
=======

### Container startet nicht

**1. Logs prüfen:**
```bash
docker logs filamenthub
# oder
docker-compose logs
```

**2. Häufige Probleme:**

**Problem:** `ADMIN_PASSWORD_HASH must be set in environment`
- **Lösung:** `.env` Datei fehlt oder ist nicht korrekt
- Erstelle `.env` mit `ADMIN_PASSWORD_HASH=...`

**Problem:** `table material already exists`
- **Lösung:** Bestehende Datenbank ohne Alembic-Versionierung
- Lösung 1: Datenbank löschen `rm data/filamenthub.db`
- Lösung 2: Datenbank stampen `docker exec -it filamenthub alembic stamp head`

**Problem:** `slice bounds out of range` (Docker Compose Panic)
- **Lösung:** Docker Compose Bug - verwende `docker build` + `docker run` statt `docker-compose build`

**Problem:** Port 8085 already in use
- **Lösung:** Anderen Container/Prozess stoppen oder Port in `config.yaml` ändern

### Schreibrechte

**Linux/Unraid:**
```bash
# Verzeichnisse erstellen und Rechte setzen
mkdir -p /mnt/user/appdata/filamenthub/data
mkdir -p /mnt/user/appdata/filamenthub/logs
chmod 777 /mnt/user/appdata/filamenthub/data
chmod 777 /mnt/user/appdata/filamenthub/logs
```

### Datenbank zurücksetzen

**WARNUNG: Alle Daten gehen verloren!**

```bash
# Container stoppen
docker-compose down

# Backup erstellen
cp data/filamenthub.db data/filamenthub.db.backup

# Datenbank löschen
rm data/filamenthub.db

# Neu starten
docker-compose up -d
```

### Admin-Passwort vergessen (Developer/Advanced)

> **Hinweis:** Nur für Entwickler/Administratoren relevant.

**Neues Passwort generieren:**

```bash
# Python BCrypt installieren (falls nicht vorhanden)
pip install bcrypt

# Neuen Hash generieren
python3 -c "import bcrypt; pw = input('Neues Passwort: ').encode(); print('ADMIN_PASSWORD_HASH=' + bcrypt.hashpw(pw, bcrypt.gensalt()).decode())"

# Hash in .env Datei eintragen
# Container neu starten
docker-compose restart
```

---
>>>>>>> Stashed changes

## Weiterführende Links
- [Handbuch](Handbuch.md)
- [API-Dokumentation](API.md)
<<<<<<< Updated upstream
=======
- [Fehlerbehebung](Fehlermeldung.md)
- [GitHub Issues](https://github.com/your-repo/FilamentHub/issues)

---

**Letzte Aktualisierung:** 2025-12-25
**Version:** 0.1.0

>>>>>>> Stashed changes
