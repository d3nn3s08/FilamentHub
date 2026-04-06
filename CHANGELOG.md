# Changelog – FilamentHub

## [1.6 Beta] – 2026-04-06

### Neu
- **Dashboard** – VERSION-Karte zeigt aktuelle Version + Update-Kanal (BETA/STABLE) in großer Schrift
- **Settings Modal** – Firmware-Tab mit Update-Kanal-Auswahl (Stable/Beta) und manuellem Versionscheck
- **Update-Check** – `/api/version/check?channel=` Endpoint mit 6h Cache; Beta als Standard-Kanal
- **Klipper/MMU** – CORS-freier Backend-Proxy; Happy Hare String-Action Bug behoben; Gate-Daten vollständig
- **CI** – GitHub Actions Workflow für automatischen Docker Hub Build

### Fixes
- **Backup** – Admin-Sperre entfernt, Backup/Restore/Upload jetzt ohne Login nutzbar
- **Dockerfile** – VERSION-Datei wird ins Image kopiert (behebt "0.0.0" Anzeige im Container)
- **Datenbank** – Alembic-Migrationen für fehlende Spalten: `sync_paused`, `dry_run_mode`, `cloud_mqtt_enabled`, `cloud_mqtt_connected`, `cloud_mqtt_last_message` in `bambu_cloud_config`
- **Version-URL** – GitHub-Branch für Stable-Check von `master` auf `main` korrigiert

---

## [0.1.6 Beta] – 2026-04-05

### Neu
- Update-Benachrichtigung: Version-Tab in Einstellungen + Banner bei verfügbarem Update

---

## [0.1.x] – frühere Versionen

- Initiales FilamentHub v1.6 Setup
- AMS-Frontend-Guard
- Docker-Compose und .env Konfiguration
