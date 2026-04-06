# Changelog – FilamentHub

## [1.6 Beta] – 2026-04-07

### Neu
- **G-Code Modal: Job ID Spalte** – Neue Spalte in der Dateiliste zeigt den MQTT Task-ID des passenden FilamentHub-Jobs (Fuzzy-Match per Name). Laden im Hintergrund via `/api/jobs`.
- **G-Code Modal: Resizable** – Modal kann mit der Maus an der rechten unteren Ecke größer/kleiner gezogen werden (`resize: both`, `min-width: 700px`).
- **G-Code Modal: Multicolor Breakdown** – Preview-Panel zeigt bei Mehrfarben-Drucken (2+ aktive Filamente) einen Breakdown: Filament 1: Xg / Filament 2: Yg / Gesamt: Zg. Bis zu 16 Filamente (X1C).
- **3MF Gewicht-Fix** – `_parse_gcode_header` summiert Footer-Gewichte aller Filamente als Gesamt-Gewicht. Behebt Diskrepanz bei Multicolor (Header hatte oft nur Filament 1). Funktioniert für bis zu 16 Filamente.

### Fixes
- **X1C Multicolor Gewicht** – Per-Filament Gewichte wurden nicht aus .3mf extrahiert. `_parse_gcode_header` las nur die ersten 200 Zeilen (Header) — `; filament used [g] = 4.56, 21.30, 8.90` steht aber im Footer. Footer-Scan (letzte 200 Zeilen) hinzugefügt. `_extract_metrics_from_3mf` gibt jetzt `filament_weights_g` zurück. X1C Commit-Pfad updated `JobSpoolUsage.used_g` pro Slot; `filament_weights_json` Parameter transportiert per-Spool Daten aus dry_run zurück.
- **G-Code / Manuell eingeben** – Gewicht konnte nach Verbindungsfehler nicht gespeichert werden (`gcodeFileSelect` war leer → `confirmGcodeSelection` blockierte bei `!selectedFile`). Platzhalter `manual_entry` wird jetzt gesetzt, Backend überspringt FTP-Download und nutzt `confirmed_weight` direkt.
- **Verbrauch-Anzeige "Warnung 0g"** – Wurde fälschlich angezeigt wenn Gewicht gespeichert war aber keine Spule zugewiesen. Jetzt nur noch "Warnung 0g" wenn `filament_used_g === 0`.
- **Cloud-Fallback schreibt `filament_used_g` nicht** – Bei `pending_weight` → `completed` Upgrade durch Cloud-Fallback blieb `filament_used_g = 0` in der DB. Wird jetzt mit `total_used_g` aus Cloud befüllt.
- **G-Code Bestätigung für `pending_weight` Jobs** – G-Code Button hat bei Jobs ohne Gewicht/Spule direkt auto-applied ohne Datei-Dialog. `pending_weight` zu `GCODE_CONFIRM_STATUSES` hinzugefügt → User sieht immer zuerst Datei-Vorschau vor dem Speichern.

---

## [1.6 Beta] – 2026-04-06

### Neu
- **Dashboard** – VERSION-Karte zeigt aktuelle Version + Update-Kanal (BETA/STABLE) in großer Schrift
- **Settings Modal** – Firmware-Tab mit Update-Kanal-Auswahl (Stable/Beta) und manuellem Versionscheck
- **Update-Check** – `/api/version/check?channel=` Endpoint mit 6h Cache; Beta als Standard-Kanal
- **Klipper/MMU** – CORS-freier Backend-Proxy; Happy Hare String-Action Bug behoben; Gate-Daten vollständig
- **CI** – GitHub Actions Workflow für automatischen Docker Hub Build

### Fixes
- **AMS-Flash-Bug** – AMS-Übersicht blitzte kurz beim Seitenwechsel auf; `no-ams` jetzt direkt am `<body>` gesetzt
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
