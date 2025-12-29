# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

---

## [2025-12-28] - Filament-Tracking Robustheit

### Behoben
- **Bambu Lab Remain-Bug**: Filamentverbrauch wird jetzt korrekt berechnet trotz unzuverlässiger `remain`-Werte
  - Problem: Bambu Lab's MQTT-Payload sendet `remain`-Werte, die willkürlich steigen/fallen können
  - Lösung: Job-Tracking akzeptiert nur SINKENDE `remain`-Werte (tatsächlicher Verbrauch)
  - Bei steigenden Werten wird der letzte niedrige Wert beibehalten
  - Warning-Log bei erkannten Anstiegen für Debugging
  - Neuer Test `test_remain_increase_bug` validiert das Verhalten
  - Betrifft: `app/services/job_tracking_service.py:364-378`
- **Spulen-Gewicht bei Job-Finish**: Finales Spulen-Gewicht wird jetzt korrekt aktualisiert
  - Problem: Bei abgebrochenen/fehlgeschlagenen Jobs wurde das Spulen-Gewicht nicht vom Verbrauch abgezogen
  - Lösung: Job-Finish aktualisiert jetzt alle verwendeten Spulen (inkl. Multi-Spool-Jobs)
  - Betrifft: `app/services/job_tracking_service.py:492-526`
- **Job-Status-Anzeige**: Status-Badges zeigen jetzt korrekte Zustände an
  - ✓ "Abgeschlossen" (grün) nur für erfolgreich beendete Jobs
  - ⊗ "Abgebrochen" (gelb) für abgebrochene Jobs (cancelled)
  - ✗ "Fehlgeschlagen" (rot) für fehlgeschlagene Jobs (failed/error)
  - ⊘ "Gestoppt" (gelb) für gestoppte Jobs (stopped/aborted)
  - Betrifft: `frontend/static/jobs.js:219-236`
- **Job-Bearbeitung**: Verbrauchsfelder sind jetzt readonly bei MQTT-getrackten Jobs
  - Automatisch getrackte Jobs: Filament (g) und Filament (mm) sind nicht editierbar (grauer Hintergrund)
  - Manuelle Jobs (0g Verbrauch): Felder bleiben editierbar
  - Tooltip zeigt "Automatisch getrackt (nicht editierbar)" bei readonly-Feldern
  - Betrifft: `frontend/static/jobs.js:352-372`
- **Spulen-Dropdown Anzeige**: Gewicht wird jetzt korrekt angezeigt
  - Problem: Frontend suchte nach `spool.weight_current`, aber API liefert `spool.weight` (serialization_alias)
  - Lösung: Frontend verwendet jetzt `spool.weight` für Gewichtsanzeige
  - Format: "PLA Basic BLAU | 📡 RFID | 332.50g / 1000g" oder "PLA Basic FFFFFF | #5 | 500.00g / 1000g"
  - Betrifft: `frontend/static/jobs.js:131`
- **Job-Duplikation**: Intelligente Erkennung von Server-Neustarts vs. neue Drucke
  - Problem: Nach Server-Neustart war RAM leer, aber DB hatte noch "running" Jobs
  - Bei neuem MQTT-Update wurde ein NEUER Job angelegt statt den existierenden zu verwenden
  - Auch bei gleichen Dateinamen (z.B. mehrere Cali Cubes hintereinander) entstanden Duplikate
  - Lösung: **Job-Fingerprint-System** mit persistentem Snapshot (JSON-Datei)
  - Beim Job-Start wird Snapshot gespeichert: `layer_num`, `mc_percent`, `started_at`
  - Beim Job-Update wird Snapshot aktualisiert mit aktuellem Fortschritt
  - Bei MQTT "PRINTING" Event: Vergleich von aktuellem Fortschritt mit Snapshot
  - **Server-Neustart erkannt**: Fortschritt >= Snapshot → Job wird restored
  - **Neuer Druck erkannt**: Fortschritt < Snapshot → Alter Job wird als "failed" markiert, neuer Job erstellt
  - Duplikate werden automatisch bereinigt (ältester bleibt, neuere gelöscht)
  - Stale Jobs (>48h) werden automatisch als "failed" markiert
  - Snapshot wird bei Job-Ende gelöscht
  - **Hybrid-Modus**: Unterstützt Bambu Lab (`cloud_serial`) UND Klipper (`printer_id`)
  - Snapshot-Key: `cloud_serial` für Bambu Lab (hardware-gebunden), `printer_{printer_id}` für Klipper (DB-gebunden)
  - Betrifft: `app/services/job_tracking_service.py:79-159, 290-507, 624-637, 793-794`
  - Snapshot-Datei: `data/job_snapshots.json`

---

## [2025-12-27] - Spulen-Nummern-System & AMS-Integration

### Hinzugefügt
- **Spulen-Nummern-System**: Intelligentes Lager-System mit manueller Spulen-Nummernvergabe
  - Nummern werden nur bei manueller Spulen-Erstellung vergeben (RFID-Spulen bleiben ohne Nummer)
  - Automatisches Recycling: Freigegebene Nummern werden wiederverwendet
  - Benachrichtigungssystem bei Nummern-Freigabe
  - Job-Snapshots speichern verwendete Spulen-Nummern
  - Neues Feld `is_open` für Spulen-Status (Alembic-Migration `ba95fb93b934`)
- **Quick-Assign System**: AMS-Spulen können schnell zugewiesen werden
  - Modales Popup mit komplett überarbeitetem Design
  - Große, klare Spulen-Nummern mit Akzentfarbe
  - Farb-Badges für Spulen-Farben (visuelles Feedback)
  - RFID-Badge (🏷️) für RFID-erkannte Spulen
  - Hover-Effekte mit Animation (Border-Highlight, Lift-Effekt, Shadow)
  - Verbesserte Suchfunktion (Nummer, Name, Hersteller, Farbe)
  - Spulen-Nummern-Anzeige direkt in der AMS-Ansicht
  - Entfernen-Button für zugewiesene Spulen
- **Confirm-Unassign Modal**: Bestätigungsdialog beim Entfernen von Spulen aus AMS-Slots
  - Zeigt Spulen-Name/Nummer an
  - Abbrechen + Entfernen Buttons
- **Frontend**: Spulen-Nummern-Anzeige mit RFID-Erkennung in spools.js
- **Datenbank**: Migration-Check vor Alembic-Upgrade
  - Prüft aktuelle Revision und überspringt unnötige Upgrades
  - Besseres Logging für Migrations-Status

### Geändert
- Spulen-Nummern sind jetzt optional und werden manuell vergeben (nicht automatisch)
- **Quick-Assign Modal Design** komplett überarbeitet:
  - Moderne Optik mit größerem Layout (650px statt 500px)
  - Gewicht prominent angezeigt (1.25rem, fett)
  - Prozent-Anzeige in Akzentfarbe-2
  - Leerer-Zustand mit schöner "Keine Spulen gefunden"-Anzeige (📭)
  - Verfügbare Spulen-Anzahl als Header (🎯)
  - Bessere Lesbarkeit und Kontraste
- **MQTT-Protokoll**: H2D verwendet jetzt MQTT v5 (Premium-Modell)
  - Premium-Modelle (X1C, X1E, P1S, P1P, H2D) → MQTT v5
  - Budget-Modelle (A1, A1 Mini) → MQTT v3.1.1

### Behoben
- **Quick-Assign Modal CSS-Klasse** korrigiert (`active` → `show`)
- **AMS Online-Status**: wird nicht mehr durch manuelle Zuweisungen gesetzt
  - Online-Status wird ausschließlich über MQTT-Daten aktualisiert (korrekte Logik!)
  - Verhindert falsche "online"-Anzeige bei manuellen Slot-Zuweisungen
- Fehlende `numberDisplay`-Logik in `spools.js` hinzugefügt
- Syntax-Fehler in `mqtt_routes.py` (Zeile 879) entfernt

### Wartung
- Ungenutzte Python-Skripte und Logs im Root-Verzeichnis entfernt
- Backup-Dateien, temporäre Skripte und alte Test-Dateien bereinigt

---

## [2025-12-26] - Pro-Mode System Überarbeitung

### Hinzugefügt
- Admin-Panel: Debug-Einstellungen für Pro-Mode

### Geändert
- **Lite/Pro Mode System** komplett überarbeitet
  - JavaScript-basierte Sichtbarkeit
  - MQTT-Tab-Isolation
  - Bessere Moduserkennung

### Behoben
- Pro-Mode Scanner Buttons aktiviert
- CSS-Selektor für `data-mode` korrigiert
- CSS-Klassen von `debug-pro` zu `pro-mode` korrigiert
- Pro-Mode System und Fingerprint-Endpoint repariert

### Wartung
- Alte ungenutzte `debug.js` Dateien entfernt

---

## [2025-12-20] - Logging-Modul

### Hinzugefügt
- Logging-Modul mit Runtime-Konfiguration

---

## [2025-12-18] - Live-Payload UI

### Hinzugefügt
- Debug Center: In-Memory Live-State für MQTT-Nachrichten
- Live Payload UI für Echtzeit-Debugging

---

## [2025-12-17] - Datenbank & Tests

### Hinzugefügt
- Alembic-Migration: `first_seen`-Spalte zur Spool-Tabelle hinzugefügt
- JSON-Renderer für Debug Center (produktiv)

### Geändert
- Tests brechen nicht mehr ab, wenn Test-DB gesperrt ist (Logging statt Fehler)

### Entfernt
- Backup-Loader aus Debug Center entfernt

---

## [2025-12-15] - MQTT-Integration

### Hinzugefügt
- **MQTT-Tab**: Lite-Modus aktiviert (auch ohne Pro-Mode sichtbar)
- MQTT Topics-Übersicht (Counts + Last Seen) im Pro-Tab ergänzt
- MQTT Runtime-Service eingeführt (Reuse `PrinterMQTTClient`)
- MQTT Runtime API-Endpunkte (`/api/mqtt/connect`, `/api/mqtt/disconnect`, `/api/mqtt/status`)

### Geändert
- MQTT-Tab: Pro-Cards (Subscriptions, Live Messages, Health & Statistik) verwenden `.panel`/`.panel-header`/`.panel-body` Struktur
- MQTT-Tab: Card-basiertes Layout analog System Status (systemkonform)

### Behoben
- MQTT UI behandelt Validation-Fehler (HTTP 422) korrekt
- Connect-Button baut echte MQTT-Verbindung auf
- Connect-Button zuverlässig über Tab-Init gebunden
- Connect-Button nutzt panel-lokale Inputs (kein globales DOM mehr)
- Status-Badge Farben korrigiert (nicht verbunden = rot)
- Connect verwendet erkannte Drucker inkl. `api_key` aus DB

---

## [2025-12-14] - Log Viewer Pro & Logging Refactor

### Hinzugefügt
- **Log Viewer Pro**: Neuer Tab im Debug Center
  - Zeilenklick + Detailfläche auch bei einzeiligen Logs
  - Stacktrace per Zeilenklick toggelbar
  - Frontend-Filter aktiviert
  - Toolbar optisch integriert
  - API-Anbindung an neuen Renderer (automatisches Laden)

### Geändert
- **Logging-System stabil**:
  - Zentraler Log Reader + `/api/debug/logs` als einzige Quelle
  - Legacy-Endpunkte liefern Deprecation-Hinweis
  - System-Status + Debug Center lesen Logging-Level/File-Status aus Settings
  - Log Viewer ruft nur noch `/api/debug/logs`
- Message-Layout und Timestamp verbessert

### Behoben
- Prefix-Kollision behoben: `/api/debug/logs`
- Abschluss-Checks durchgeführt: Limit, Modul-Whitelist, Admin-Gate, Logging-Level, Endpoint-Konsistenz

### Entfernt
- Legacy State-Datei als ungenutzt markiert

---

## [2025-12-13] - Server Start & Debug Center

### Hinzugefügt
- **Debug Center**: Lite/Pro Trennung, stabile Tabs, ASCII-Platzhalter
- Performance Lite: CPU/RAM/Disk/Uptime Cards mit defensivem Loading
- `/api/debug/performance`: Minimale Metriken für Lite Performance Tab
- **Printer Scanner Lite**: LAN Quick Scan (read-only)
  - Port-6000 Test Button + Save-Enable Flow
  - Duplikat-Schutz (IP + Typ) und Status-Feedback beim Hinzufügen
- Debug Center / Printer Scanner Pro: Anzeige-Cards (Platzhalter, deutsch)
- Pro-Unlock persistent (Schloss im Toggle, Modal, Setting `debug_center_pro_unlocked`)
- Netzwerk-Info via `/api/debug/network`
- Log Viewer Lite: Level-/Textfilter, manueller/periodischer Refresh

### Geändert
- **Server-Port-Handling** vereinheitlicht (Default 8085 aus `config.yaml`, ENV `HOST`/`PORT` Override)
- Performance Lite UX verbessert: Initial-Load sofort, Loading-State, Soft-Cache
  - Werte erscheinen sofort oder nach <1s, keine leeren Blöcke, defensive Fehlerbehandlung
  - Flat/nested `current_*` Fallbacks
- Runtime/Network/WebSocket Status defensiv, Runtime idle mit "-" in Lite
- Printer Scanner Lite modernisiert (Cards, Badges, Buttons)

### Behoben
- `run.py` gibt Hinweis bei belegtem Port und erlaubt `PORT`-Override, damit Uvicorn nicht still beendet
- Uvicorn reload unter Windows aus `run.py` entfernt (stabiler Serverstart)

---

## [2025-12-10] - Globales Layout & Settings

### Hinzugefügt
- **Globales Layout** mit Mini-User-Menü (Avatar, Local User, About, Settings, Theme Toggle) auf allen Seiten
- **Light-Theme-Variante** via CSS-Variablen, umschaltbar über Theme Toggle (Persistenz in `localStorage`)
- Dropdown-/Accessibility-Logik in `frontend/static/js/navbar.js` (Outside-Click, Enter/Space, Escape)
- **Settings-API** (`/api/settings`) mit Defaults (`ams_mode`, `debug_ws_logging`) und UI-Bindung
- Settings-Seite zeigt AMS-Mode und WS-Logging-Optionen
- `UniversalMapper` nutzt `parse_ams` und beachtet `ams_mode` (single/multi), gibt AMS-Units über `ams_units` aus
- Debug Center: Performance Panel (Lite) mit defensivem Polling gegen `/api/performance/panel`

### Geändert
- Navigation-Highlighting verbessert (aktive Seite robust markiert)
- Header um User-Menü-Zone ergänzt, Buttons rechtsbündig kombiniert

---

## [2025-12-02] - AMS Helper & Job-Namen

### Hinzugefügt
- Debug/DB-Editor: Nützliche-Links-Karte mit Standardlinks (Debug, AMS Helper, Logs, API) und Button für eigene Links
- Doku: Neuer Eintrag `ANLEITUNG/AMS-Live-Tracking.md`; Handbuch-Inhaltsverzeichnis entsprechend verlinkt

### Geändert
- AMS Helper repariert (Encoding/Syntax), zeigt nun Total, Verbraucht und Rest in Metern je Slot
- Job-Namen werden aus `subtask_name` (oder G-Code-Dateiname ohne Pfad) abgeleitet statt immer "Unnamed Job"
- AMS-Sync/Spools: Live-Update von `remain_percent`/`weight_current` aus Reports verbessert

### Behoben
- Debug-Link zeigt auf `http://localhost:8080/debug`

---

## [2025-11-27] - Integration Modes & Tests

### Phase 1 – Backend/DB
- `integrations.mode` in `config.yaml` (bambu/klipper/dual/standalone)
- Mode-Setter-API `/api/system/mode`
- Printer-Modell um `active` ergänzt
- Alembic-Migration `4e2c1c9d8b3e_add_active_to_printer.py`
- Spool-Update erlaubt Materialwechsel (`material_id` optional)
- System-Status liefert aktive Drucker pro Typ (`bambu_active`, `klipper_active`)

### Phase 2 – UI/Debug
- Debug-UI: Mode-Badge farblich, Mode-Dropdown + Set-Button, Anzeige aktivierter Bambu/Klipper-Drucker
- Scanner-Tab aufgeräumt (Config-Generator entfernt, Hinweise angepasst)
- Tests-Sektion: getrennte Buttons (Smoke, DB, Alle, Coverage) mit Statusfarbe

### Phase 3 – Tests
- Service-Routen für Tests nutzen Test-DB (`FILAMENTHUB_DB_PATH=data/test.db`)
- Tests löschen Test-DB vor Lauf, setzen `PYTHONPATH` und rufen `init_db()`
- Coverage läuft gegen Smoke-Tests mit Test-DB
- `test_db_crud.py` nutzt ENV-DB-Pfad und bricht sauber ab, wenn gelockt

### Phase 9 – Deployment
- **Dockerfile** nutzt neues `entrypoint.sh`:
  - Alembic-Migrationen vor Start
  - `PYTHONPATH=/app`
  - `FILAMENTHUB_DB_PATH=/app/data/filamenthub.db`
  - Legt Logs/Data an
- `entrypoint.sh` hinzugefügt (Migration + Start von `run.py`)

---

## [2025-11-27] - Datenbank & API-Grundlagen

### Hinzugefügt
- Datenbank: SQLite mit Foreign-Key-Constraints aktiviert
- Material-, Spool-, Printer- und Job-Modelle mit SQLModel und Pydantic V2
- Alembic für Migrationen eingerichtet
- API-CRUD-Endpunkte für Material und Spool
- FastAPI Backend mit automatischer DB-Initialisierung und Routing
- Automatisierte Smoke-Tests für Material und Spool (CRUD: create, get, list, update, delete)
- Projektstruktur nach Best Practices: `app/`, `models/`, `routes/`, `services/`, `frontend/`, `data/`, `docs/`
- Minimal-Dashboard als HTML-Template

### Geändert
- Testdaten eindeutig gemacht, Duplikatfehler behoben
- Testdateien in das Verzeichnis `TEST_PY_datem` verschoben

### Behoben
- Alle CRUD-Tests erfolgreich durchgelaufen

---

## [2025-11-15] - Debug Center & Logging

### Hinzugefügt
- **Debug Center**: Routen `/debug` und `/logs` für Fehleranalyse und Systemdiagnose
- Debug- und Log-Templates (`debug.html`, `logs.html`)
- Logging-Konfiguration aus `config.yaml` und `RotatingFileHandler` für Logfiles
- Websocket-Streaming für Live-Logs (`/ws/logs/{module}`)
- Debug-JS und CSS für UI-Fehleranalyse und Loganzeige
- `CONTRIBUTING.md` und `CODE_OF_CONDUCT.md` ergänzt
- Roadmap und Features in `README.md` dokumentiert
- MIT-Lizenz hinzugefügt
- `/api/debug/system_status` Endpoint
- Backend-Checks für DB / API / MQTT / WS
- Frontend-Polling + UI Status-Panel
- Performance: Neuer defensiver Panel-Endpoint (`/api/performance/panel`)
- Runtime-Monitoring: HTTP-Middleware für Requests/Responsezeiten (Rolling 60s)
- Debug Center Lite/Pro Mode mit dynamischer Tab-Sichtbarkeit und Settings-Persistenz
- Debug Center / Printer Scanner: Deep Probe (Pro) Button→Backend→Ergebnisanzeige

### Geändert
- Debug Center aus Sidebar entfernt; Zugänge über User-Menü reorganisiert
- Debug/API-Header-Shortcuts entfernt; Navigation gestrafft
- Debug Center: Neues System-Panel mit Lite/Pro Modus, modernem Layout und stabiler `/api/system/status`-Anbindung
- Debug Center: System-Status-Tab finalisiert (Lite/Pro), stabile Defaults, Backend-Status
- Debug Center: Backend-/Service-Status verfeinert (API/DB/MQTT/WebSocket mit detaillierten Zuständen und Tooltips)
- Debug Center: WebSocket-Status semantisch korrigiert und Client-Tracking ergänzt (connected/listening/idle/offline)
- Debug Center / Printer Scanner: Pro-Icons und Disabled-State optimiert (Anzeige-only)

### Behoben
- Encoding-Fix: Version-Label bereinigt (UTF-8)
- UTF-8 Normalisierung, UI-Encoding repariert
- `mqtt_routes.py`: SyntaxError, SQLAlchemy `where()`-Fehler, WebSocket `finally`-Block repariert
- `job.py`: `__tablename__` statisch gesetzt
- `mqtt_routes.py`: `where()`-Klausel auf Column-Expression gebracht
- WebSocket-Status semantisch korrigiert (offline ≠ kein Client)
