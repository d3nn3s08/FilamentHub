## 2025-12-14 (Logging Refactor)
- Logging: zentraler Log Reader + /api/debug/logs als einzige Quelle, Legacy-Endpunkte liefern Deprecation-Hinweis.
- Systemstatus + Debug Center lesen Logging-Level/File-Status aus Settings; Log Viewer ruft nur noch /api/debug/logs.

## 2025-12-14
- Debug Center: neuer Pro-Tab "Log Viewer" (Placeholder)

## 2025-12-14
- Pro Config Manager � Backend Keys & Defaults vorbereitet

## 2025-12-13 (Server Start)
- Fix: run.py gibt Hinweis bei belegtem Port und erlaubt PORT-Override, damit Uvicorn nicht still beendet.
- Server-Port-Handling vereinheitlicht (Default 8085 aus config.yaml, ENV HOST/PORT Override).
- Fix: Uvicorn reload unter Windows aus run.py entfernt (stabiler Serverstart)
- Debug(Lite): Performance tab cards (CPU/RAM/Disk/Uptime) with defensive loading
- Add: /api/debug/performance (minimal metrics for Lite Performance tab)
- Debug(Lite): Printer Scanner restored (LAN quick scan, read-only)
- Printer Scanner Lite: Port-6000 Test Button + Save-Enable Flow
- UI polish: Printer Scanner Lite modernisiert (Cards, Badges, Buttons)
- Lite Printer Save: Duplikat-Schutz (IP + Typ) und Status-Feedback beim Hinzufuegen
- Debug Center: Lite/Pro Umschalt-Button mit persistiertem Modus
- Debug Center / Printer Scanner: Scanner Pro � Anzeige-Cards (Platzhalter, deutsch)

## 2025-12-13 (Rebuild)
### Changed
- Performance Lite UX verbessert: Initial-Load sofort, Loading-State, Soft-Cache (Werte erscheinen sofort oder nach <1s, keine leeren Blöcke, defensive Fehlerbehandlung).
- Debug Center neu aufgebaut (Lite/Pro Trennung, stabile Tabs, ASCII-Platzhalter).
- Pro-Unlock persistent (Schloss im Toggle, Modal, Setting debug_center_pro_unlocked).
- Runtime/Network/WebSocket Status defensiv, Runtime idle mit "-" in Lite.
- Performance Lite: Sofort-Load, Loading-State, Soft-Cache, flat/nested current_* Fallbacks.
- Netzwerk-Info via /api/debug/network, Printer-Scanner Lite Quick Scan mit Icons/Statusbadges.
- Log Viewer Lite: Level-/Textfilter, manueller/periodischer Refresh.
# Changelog

## 2025-12-10
### Added
- Globales Layout mit Mini-User-Menü (Avatar, Local User, About, Settings, Theme Toggle) auf allen Seiten.
- Light-Theme-Variante via CSS-Variablen, umschaltbar über Theme Toggle (Persistenz in localStorage).
- Dropdown-/Accessibility-Logik in `frontend/static/js/navbar.js` (Outside-Click, Enter/Space, Escape).
- Settings-API (`/api/settings`) mit Defaults (ams_mode, debug_ws_logging) und UI-Bindung im Mini-Menü und auf der Settings-Seite.
- Settings-Seite zeigt AMS-Mode und WS-Logging-Optionen und synchronisiert mit der API.
- UniversalMapper nutzt `parse_ams` und beachtet `ams_mode` (single/multi), gibt AMS-Units über `ams_units` aus.
- Debug Center: Performance Panel (Lite) mit defensivem Polling gegen `/api/performance/panel (flache current_* Felder unterst?tzt)` (CPU/RAM/Disk/Uptime).

### Changed
- Navigation-Highlighting verbessert (aktive Seite robust markiert).
- Header um User-Menü-Zone ergänzt, Buttons rechtsbündig kombiniert.

## 2025-12-02
- AMS Helper repariert (Encoding/Syntax), zeigt nun Total, Verbraucht und Rest in Metern je Slot.
- Job-Namen werden aus `subtask_name` (oder G-Code-Dateiname ohne Pfad) abgeleitet statt immer "Unnamed Job".
- Debug/DB-Editor: Nuetzliche-Links-Karte mit Standardlinks (Debug, AMS Helper, Logs, API) und Button fuer eigene Links; Debug-Link zeigt auf http://localhost:8080/debug.
- Doku: Neuer Eintrag ANLEITUNG/AMS-Live-Tracking.md; Handbuch-Inhaltsverzeichnis entsprechend verlinkt.
- AMS-Sync/Spools: Live-Update von remain_percent/weight_current aus Reports verbessert.

## 2025-11-27 (Update)
### Phase 1 – Backend/DB
- `integrations.mode` in `config.yaml` (bambu/klipper/dual/standalone); Mode-Setter-API `/api/system/mode`.
- Printer-Modell um `active` ergänzt; Alembic-Migration `4e2c1c9d8b3e_add_active_to_printer.py`.
- Spool-Update erlaubt Materialwechsel (`material_id` optional).
- System-Status liefert aktive Drucker pro Typ (`bambu_active`, `klipper_active`).

### Phase 2 – UI/Debug
- Debug-UI: Mode-Badge farblich, Mode-Dropdown + Set-Button, Anzeige aktivierter Bambu/Klipper-Drucker.
- Scanner-Tab aufgeräumt (Config-Generator entfernt, Hinweise angepasst).
- Tests-Sektion: getrennte Buttons (Smoke, DB, Alle, Coverage) mit Statusfarbe.

### Phase 3 – Tests
- Service-Routen für Tests nutzen Test-DB (`FILAMENTHUB_DB_PATH=data/test.db`), löschen sie vor dem Lauf, setzen `PYTHONPATH` und rufen `init_db()`.
- Coverage läuft gegen Smoke-Tests mit Test-DB.
- `test_db_crud.py` nutzt ENV-DB-Pfad und bricht sauber ab, wenn gelockt.

### Phase 9 – Deployment
- Dockerfile nutzt neues `entrypoint.sh`: Alembic-Migrationen vor Start, `PYTHONPATH=/app`, `FILAMENTHUB_DB_PATH=/app/data/filamenthub.db`, legt Logs/Data an.
- `entrypoint.sh` hinzugefügt (Migration + Start von `run.py`).

## 2025-11-27
- Datenbank weiterhin SQLite, Foreign-Key-Constraints aktiviert
- Material-, Spool-, Printer- und Job-Modelle mit SQLModel und Pydantic V2 erstellt und erweitert
- Alembic für spätere Migrationen eingerichtet
- API-CRUD-Endpunkte für Material und Spool implementiert und auf neue Schemas umgestellt
- FastAPI Backend mit automatischer DB-Initialisierung und Routing
- Automatisierte Smoke-Tests für Material und Spool (CRUD: create, get, list, update, delete) mit FastAPI TestClient
- Testdaten eindeutig gemacht, Duplikatfehler behoben
- Testdateien in das Verzeichnis `TEST_PY_datem` verschoben
- Alle CRUD-Tests erfolgreich durchgelaufen
- Projektstruktur nach Best Practices: app/, models/, routes/, services/, frontend/, data/, docs/
- Minimal-Dashboard als HTML-Template integriert

## 2025-11-15
- Debugcenter: Routen `/debug` und `/logs` für Fehleranalyse und Systemdiagnose
- Debug- und Log-Templates (`debug.html`, `logs.html`) integriert
- Logging-Konfiguration aus `config.yaml` und RotatingFileHandler für Logfiles
- Websocket-Streaming für Live-Logs (`/ws/logs/{module}`) implementiert
- Debug-JS und CSS für UI-Fehleranalyse und Loganzeige
- CONTRIBUTING.md und CODE_OF_CONDUCT.md ergänzt
- Roadmap und Features in README.md dokumentiert
- MIT-Lizenz hinzugefügt

- Encoding-Fix: Version-Label bereinigt (UTF-8).
- UTF-8 Normalisierung, UI-Encoding repariert.
- Debug Center aus Sidebar entfernt; Zugaenge ueber User-Menue reorganisiert.
- Debug/API-Header-Shortcuts entfernt; Navigation gestrafft.
- Debug Center: neues System-Panel mit Lite/Pro Modus, modernem Layout und stabiler /api/system/status-Anbindung.
- Added /api/debug/system_status endpoint.
- Added backend checks for DB / API / MQTT / WS.
- Added frontend polling + UI Status-Panel.
- Debug Center: System-Status-Tab finalisiert (Lite/Pro), stabile Defaults, Backend-Status.
- Debug Center: Backend-/Service-Status verfeinert (API/DB/MQTT/WebSocket mit detaillierten Zuständen und Tooltips).
- Debug Center: WebSocket-Status semantisch korrigiert und Client-Tracking ergänzt (connected/listening/idle/offline).
- Fix: mqtt_routes.py – SyntaxError, SQLAlchemy where()-Fehler, WebSocket finally-Block repariert.
- Performance: Neuer defensiver Panel-Endpoint (/api/performance/panel) mit stabilem JSON-Vertrag und Erweiterbarkeit.
- Runtime-Monitoring: HTTP-Middleware für Requests/Responsezeiten (Rolling 60s) und System-Status-Expose in /api/debug/system_status.
- Fix: job.py __tablename__ statisch gesetzt; mqtt_routes.py where()-Klausel auf Column-Expression gebracht.
- WebSocket-Status semantisch korrigiert (offline ≠ kein Client).

- Added: Debug Center Lite/Pro Mode mit dynamischer Tab-Sichtbarkeit und Settings-Persistenz.
- Debug Center / Printer Scanner: Pro-Icons und Disabled-State optimiert (Anzeige-only)
- Debug Center / Printer Scanner: Pro-Icons und Disabled-State optimiert (Anzeige-only)
- Debug Center / Printer Scanner: Deep Probe (Pro) Button->Backend->Ergebnisanzeige




