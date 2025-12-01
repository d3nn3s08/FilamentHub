# Release/Deployment

## Docker-Image
- Im Projektverzeichnis:
  ```bash
  docker build -t filamenthub .
  docker run -d -p 8000:8000 -v $(pwd)/data:/app/data filamenthub
  ```
- Volumes für Datenbank und Logs konfigurieren

## ZIP-Installer
- Projekt als ZIP bereitstellen
- Anleitung für Entpacken und Start (siehe Installation)

## Unraid-Template
- Docker-Stack/Template anlegen
- Ports und Volumes konfigurieren
- Image aus Registry oder lokal bauen

## Deployment-Checkliste
- Schreibrechte auf `data/` und `logs/` prüfen
- Migrationen beim Start ausführen (`alembic upgrade head`)
- Backup-Button im Debug/Service-Tab testen (legt ZIP mit DB+Logs in `data/backups`)
- Webinterface Smoke-Test (CRUD) durchlaufen
- Beispiel-Daten eintragen

## Hinweise
- Nach jedem Release: Backup und Testlauf durchführen
- Windows-Startskripte (`Start_FilamentHub.bat`/`menu_pro_v3.ps1`) sind nur für lokale Entwicklung; in Docker/Pi nicht erforderlich
