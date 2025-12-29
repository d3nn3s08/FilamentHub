# FilamentHub Server Upload Anleitung

## Methode 1: WinSCP Script (Empfohlen für Automatisierung)

### Schritt 1: Server-Daten eintragen
Öffne `upload_to_server.txt` und passe die Zeile an:

```
open sftp://DEIN_USERNAME:DEIN_PASSWORD@DEIN_SERVER:22
```

Beispiel:
```
open sftp://denis:MeinPasswort123@filamenthub.example.com:22
```

Passe auch den Zielpfad an:
```
cd /pfad/zu/filamenthub
```

Beispiel:
```
cd /home/denis/filamenthub
```

### Schritt 2: Upload starten
Doppelklick auf `upload.bat` oder führe in CMD aus:
```cmd
"C:\Program Files (x86)\WinSCP\WinSCP.com" /script=upload_to_server.txt
```

---

## Methode 2: WinSCP GUI mit Synchronisation

### Schritt 1: Verbindung einrichten
1. Öffne WinSCP
2. Erstelle eine neue Site:
   - File Protocol: SFTP
   - Host name: dein-server.de
   - Port: 22
   - Username: dein_username
   - Password: dein_password
3. Verbinden

### Schritt 2: Synchronisieren
1. Im Menü: Commands -> Synchronize
2. Local directory: `C:\Users\Denis\Desktop\FilamentHub_Projekt\FilamentHub`
3. Remote directory: `/home/filamenthub` (oder dein Pfad)
4. Direction: Local -> Remote
5. Klick auf "Options"
6. Bei "Exclude mask" einfügen:

```
__pycache__/; *.pyc; .venv/; venv/; .pytest_cache/; .git/; logs/; data/*.db; Backup/; *.bak*; tests/; htmlcov/; .coverage
```

Oder nutze den Inhalt von `winscp_exclude.txt`

7. OK -> Synchronize

---

## Methode 3: PowerShell Script (Für Profis)

### Voraussetzung
WinSCP .NET Assembly muss installiert sein.

### Nutzung
```powershell
.\upload_with_winscp.ps1 -ServerHost "dein-server.de" -Username "denis" -Password "deinpasswort" -RemotePath "/home/filamenthub"
```

**WICHTIG:** Passe den SSH Fingerprint im Script an! Den Fingerprint erhältst du beim ersten Connect mit WinSCP.

---

## Was wird hochgeladen?

### Haupt-Dateien
- `run.py` - Haupt-Anwendung
- `requirements.txt` - Python Dependencies
- `config.json`, `config.yaml` - Konfiguration
- `.env` - Umgebungsvariablen (ACHTUNG: Secrets!)
- `Dockerfile`, `docker-compose.yml` - Container Config

### Verzeichnisse
- `app/` - Flask/FastAPI Anwendung
- `services/` - Backend Services
- `utils/` - Utilities
- `frontend/` - Frontend Dateien
- `alembic/` - Datenbank Migrations
- `scripts/` - Deployment Scripts

### Scripts
- `*.sh` - Shell Scripts (entrypoint.sh, rebuild.sh, etc.)

---

## Was wird NICHT hochgeladen?

- `.venv/` - Virtual Environment
- `__pycache__/` - Python Cache
- `tests/` - Test Dateien
- `.git/` - Git Repository
- `logs/` - Log Dateien
- `data/*.db` - Lokale Datenbank
- `Backup/` - Backup Ordner
- `*.bak*` - Backup Dateien

---

## Nach dem Upload

### Auf dem Server ausführen:

```bash
# In das Verzeichnis wechseln
cd /home/filamenthub

# Shell Scripts ausführbar machen
chmod +x *.sh

# Virtual Environment erstellen
python3 -m venv .venv
source .venv/bin/activate

# Dependencies installieren
pip install -r requirements.txt

# Datenbank initialisieren (falls nötig)
python create_db.py

# Anwendung starten
python run.py

# ODER mit Docker:
docker-compose up -d --build
```

---

## Tipps

### Sicherheit
- **NIEMALS** `.env` Dateien mit echten Secrets in öffentliche Repos!
- Nutze `.env.local` für lokale Secrets
- Überschreibe auf dem Server die `.env` mit echten Produktionsdaten

### Automatisierung
Du kannst `upload.bat` in einen Scheduled Task einbinden für automatische Uploads.

### Schneller Upload
Nutze WinSCP's "Keep remote directory up to date" Feature für Live-Sync während der Entwicklung.

---

## Troubleshooting

### "Host key wasn't verified"
Bei PowerShell Script: SSH Fingerprint im Script anpassen

### "Permission denied"
- Prüfe Username/Password
- Prüfe ob SSH Key benötigt wird
- Prüfe Zielverzeichnis Berechtigungen

### Dateien werden nicht gefunden
- Prüfe ob du im richtigen Verzeichnis bist
- Nutze absolute Pfade im Script

### Upload dauert zu lange
- Nutze Exclude-Liste um unnötige Dateien auszuschließen
- Komprimiere große Dateien vorher

