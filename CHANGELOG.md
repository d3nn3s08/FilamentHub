# Changelog - FilamentHub

## [1.6 Stable] - 2026-04-18

### Neu
- **Mobile Layout** - Hauptnavigation als echtes Mobile-Drawer-Menue umgesetzt. Header, Karten und zentrale Layout-Bloecke verhalten sich auf Handy jetzt deutlich sauberer.
- **Klipper Spool-Autoerkennung** - Fuer Klipper gilt jetzt `MMU > Moonraker-Spoolman > manuell`. Happy Hare/MMU-Gate-Spulen oder aktive Moonraker-Spoolman-IDs koennen laufende Jobs automatisch an die passende FilamentHub-Spule binden, wenn ein eindeutiges Mapping existiert.
- **Spulenformular: Spoolman ID** - In der Spulenverwaltung kann jetzt eine `Spoolman ID` gepflegt werden, damit Klipper/Moonraker aktive Spulen sauber auf lokale FilamentHub-Spulen gemappt werden koennen.

### Fixes
- **AMS Lite Sichtbarkeit** - `/ams-lite` und zugehoerige Navigation werden nur noch angezeigt, wenn wirklich ein aktiver Bambu-Drucker mit AMS Lite erkannt wird.
- **MMU Sichtbarkeit** - `MMU-Klipper` Navigation und MMU-Seite werden jetzt wie AMS nur noch angezeigt, wenn mindestens ein Klipper-Drucker mit erkannter Happy Hare MMU vorhanden ist.
- **Bambu Cloud Login** - Doppelter Versand von Verifikationsmails behoben. Der Login-Flow fordert den Email-Code nicht mehr doppelt an und blockiert parallele Login-/Verify-Requests.
- **Bambu Cloud Sync-Fehler** - Token-Entschluesselungsfehler werden beim manuellen Sync jetzt gezielt erkannt und als klare Fehlermeldung statt generischem 500er an die UI zurueckgegeben.
- **Lokale Debug-Credentials** - `/api/printers/{printer_id}/credentials` liefert keinen `api_key` mehr im Klartext aus. Der Endpoint gibt nur noch Metadaten plus `has_api_key` zurueck.
- **Bambu Cloud Token-Encryption** - `FILAMENTHUB_ENCRYPTION_KEY` wird jetzt im korrekten Fernet-Format verarbeitet. Dadurch brechen Encrypt/Decrypt-Laeufe mit gesetzter Umgebungsvariable nicht mehr.
- **Dependencies** - `cryptography` zu `requirements.txt` hinzugefuegt, damit die Token-Verschluesselung auf frischen Setups nicht am Import scheitert.
- **Cloud-Konfliktaufloesung** - `WeightHistory.old_weight` wird jetzt vor dem Ueberschreiben von `spool.weight_current` erfasst. Die Historie zeigt wieder echte Alt-/Neu-Werte.
- **MQTT Runtime Auto-Connect** - Das Deaktivieren von `auto_connect` trennt nicht mehr versehentlich die Runtime-Verbindung eines anderen Druckers.
- **API-Hilfe** - `/api-help` verwendet keinen hartcodierten Entwicklerpfad mehr und laeuft dadurch auch auf anderen Installationen.

---

## [1.6 Beta] - 2026-04-07

### Neu
- **G-Code Modal: Job ID Spalte** - Neue Spalte in der Dateiliste zeigt den MQTT Task-ID des passenden FilamentHub-Jobs (Fuzzy-Match per Name). Laden im Hintergrund via `/api/jobs`.
- **G-Code Modal: Resizable** - Modal kann mit der Maus an der rechten unteren Ecke groesser/kleiner gezogen werden (`resize: both`, `min-width: 700px`).
- **G-Code Modal: Multicolor Breakdown** - Preview-Panel zeigt bei Mehrfarben-Drucken (2+ aktive Filamente) einen Breakdown: Filament 1: Xg / Filament 2: Yg / Gesamt: Zg. Bis zu 16 Filamente (X1C).
- **3MF Gewicht-Fix** - `_parse_gcode_header` summiert Footer-Gewichte aller Filamente als Gesamt-Gewicht. Behebt Diskrepanz bei Multicolor (Header hatte oft nur Filament 1). Funktioniert fuer bis zu 16 Filamente.

### Fixes
- **X1C Multicolor Gewicht** - Per-Filament Gewichte wurden nicht aus .3mf extrahiert. `_parse_gcode_header` las nur die ersten 200 Zeilen (Header) - `; filament used [g] = 4.56, 21.30, 8.90` steht aber im Footer. Footer-Scan (letzte 200 Zeilen) hinzugefuegt. `_extract_metrics_from_3mf` gibt jetzt `filament_weights_g` zurueck. X1C Commit-Pfad updated `JobSpoolUsage.used_g` pro Slot; `filament_weights_json` Parameter transportiert per-Spool Daten aus dry_run zurueck.
- **G-Code / Manuell eingeben** - Gewicht konnte nach Verbindungsfehler nicht gespeichert werden (`gcodeFileSelect` war leer -> `confirmGcodeSelection` blockierte bei `!selectedFile`). Platzhalter `manual_entry` wird jetzt gesetzt, Backend ueberspringt FTP-Download und nutzt `confirmed_weight` direkt.
- **Verbrauch-Anzeige "Warnung 0g"** - Wurde faelschlich angezeigt wenn Gewicht gespeichert war aber keine Spule zugewiesen. Jetzt nur noch "Warnung 0g" wenn `filament_used_g === 0`.
- **Cloud-Fallback schreibt `filament_used_g` nicht** - Bei `pending_weight` -> `completed` Upgrade durch Cloud-Fallback blieb `filament_used_g = 0` in der DB. Wird jetzt mit `total_used_g` aus Cloud befuellt.
- **G-Code Bestaetigung fuer `pending_weight` Jobs** - G-Code Button hat bei Jobs ohne Gewicht/Spule direkt auto-applied ohne Datei-Dialog. `pending_weight` zu `GCODE_CONFIRM_STATUSES` hinzugefuegt -> User sieht immer zuerst Datei-Vorschau vor dem Speichern.

---

## [1.6 Beta] - 2026-04-06

### Neu
- **Dashboard** - VERSION-Karte zeigt aktuelle Version + Update-Kanal (BETA/STABLE) in grosser Schrift
- **Settings Modal** - Firmware-Tab mit Update-Kanal-Auswahl (Stable/Beta) und manuellem Versionscheck
- **Update-Check** - `/api/version/check?channel=` Endpoint mit 6h Cache; Beta als Standard-Kanal
- **Klipper/MMU** - CORS-freier Backend-Proxy; Happy Hare String-Action Bug behoben; Gate-Daten vollstaendig
- **CI** - GitHub Actions Workflow fuer automatischen Docker Hub Build

### Fixes
- **AMS-Flash-Bug** - AMS-Uebersicht blitzte kurz beim Seitenwechsel auf; `no-ams` jetzt direkt am `<body>` gesetzt
- **Backup** - Admin-Sperre entfernt, Backup/Restore/Upload jetzt ohne Login nutzbar
- **Dockerfile** - VERSION-Datei wird ins Image kopiert (behebt "0.0.0" Anzeige im Container)
- **Datenbank** - Alembic-Migrationen fuer fehlende Spalten: `sync_paused`, `dry_run_mode`, `cloud_mqtt_enabled`, `cloud_mqtt_connected`, `cloud_mqtt_last_message` in `bambu_cloud_config`
- **Version-URL** - GitHub-Branch fuer Stable-Check von `master` auf `main` korrigiert

---

## [0.1.6 Beta] - 2026-04-05

### Neu
- Update-Benachrichtigung: Version-Tab in Einstellungen + Banner bei verfuegbarem Update

---

## [0.1.x] - fruehere Versionen

- Initiales FilamentHub v1.6 Setup
- AMS-Frontend-Guard
- Docker-Compose und .env Konfiguration
