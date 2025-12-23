* [x] MQTT Tab: Card-Layout an System Status angepasst (UI-Struktur, keine Logik)
* [ ] MQTT Datenanbindung folgt
* [ ] MQTT Debug UI: Connect/Disconnect nutzt /api/mqtt/runtime/* (Schritt 1C)
* [ ] MQTT UI: Runtime-Status + Fehlerhandling (inkl. 422) finalisiert (Schritt 1D)
* [x] MQTT: Topics/Subscribers Übersicht (read-only) umgesetzt (Schritt 2A)
* [x] MQTT UI: Connect-Button triggert Runtime-Connect (final)
* [x] MQTT-Tab: Pro-Cards (Subscriptions, Live Messages, Health & Statistik) auf systemkonforme .panel-Struktur umgestellt (keine eigenen Card-Klassen mehr)
[x] MQTT-Tab: Overview-Grundstruktur angelegt
[x] MQTT-Tab: Card-Layout an System-Status-Card-Pattern angepasst
[x] MQTT-Tab: Lite-Modus aktiviert (auch im Lite-Modus sichtbar)
[ ] MQTT-Statusdaten später anbinden
[x] Log Viewer Pro: Einstzeilige Logs mit dezenter Detailfläche bei Klick
[x] Log Viewer Pro: Zeilenklick toggelt Stacktrace
[x] Log Viewer Pro: Message-Layout + Timestamp ergänzt
[x] Log Viewer Pro: Alter State (log_viewer_state.js) als ungenutzt markiert
[x] Log Viewer Pro: Filter (Level/Modul/Suche) aktiviert
 [x] Log Viewer Pro: Toolbar UI gestylt
- [x] Logging-Status und Level aus Settings laden (system_routes)
- [x] Log Viewer Pro nutzt /api/debug/logs (keine Alt-Routen)
- [x] Log Viewer: Filter/Modulwahl und Detailanzeige finalisieren
- [x] Port-Architektur finalisiert (Default 8085, ENV HOST/PORT Override).
- [x] Uvicorn-Start unter Windows stabilisiert
- [ ] Config Manager UI (Pro): Skeleton + JS anbinden
- [ ] Enhance performance metrics (optional), keep endpoint read-only
- [ ] Add advanced scanner (Pro): active probing, vendor detection
- [ ] Implementiere Persist-Flow 'Zum System hinzufuegen' fuer getestete Drucker
- [ ] Optional: gleiche Card-Optik fuer Pro-Scanner uebernehmen
- [ ] Frontend Save-Flow finalisieren (Status/Toast) nach Dup-Check
- [ ] Pro Mode Panels mit Inhalt fuellen (Mode-Umschalt-UI vorhanden)
- [ ] Scanner Pro: Deep Probe Logik implementieren (Pro Feature)
- [ ] Scanner Pro: Device Fingerprint Logik implementieren
- [ ] Scanner Pro: Why Warning erklaeren (diagnostic reason)
- [ ] Scanner Pro: JSON Snapshot erfassen/speichern
- [ ] Pro-Unlock/Persistenz konzipieren (aktuell Anzeige-only)
- [ ] Scanner Pro: Icons finalisieren (netzwerk, fingerprint, warnung, code)
- [ ] Scanner Pro: Disabled-State/UI-Feedback produktiv einsetzen, wenn Logik aktiv wird
- [ ] Scanner Pro: Deep Probe Endpoint + UI Flow finalisieren
- [ ] Scanner Pro: Warn-/Fehlerklassifikation erweitern (Basis umgesetzt)
- [ ] Regel: Lite-Ansicht ist final und unveraenderlich (keine UI/Logik-Aenderungen)
- [ ] Pro-Features strikt kapseln, keine Sichtbarkeit im Lite-Modus

## Debug Center Open Tasks
- Pro: MQTT Charts
- Pro: AMS Deep Inspect
- Pro: JSON Inspector polish

* [ ] MQTT: Topics/Subscribers Übersicht (read-only) umgesetzt (Schritt 2A)

# Performance Lite Panel
- [x] UX verbessert: Initial-Load sofort, Loading-State, Soft-Cache (Frontend, Debug Center)
- [ ] Optional: Konfigurierbares Polling-Intervall für Performance Panel
# FilamentHub TODO

*Hinweis*: Neue Spulen-Override-Funktion (Job → Zuordnung überschreiben) eingebaut – **Testlauf erforderlich**.

## Phase 1 - Basisfunktionen
1. [x] DB Editor Tab im UI anlegen
2. [x] Backend-Endpunkt fuer schreibende SQL-Queries
3. [x] UI mit Ergebnis-/Fehleranzeige erweitern (Editor-Output, Query-Output)

## Phase 2 - Sicherheit / Admin (rot)
4. [ ] Passwortschutz fuer kritische Funktionen (DB-Editor, Migration, Backup, Admin)
5. [ ] Separater Tab mit Passwortabfrage fuer kritische Funktionen

## Phase 3 - Deployment / Migration
6. [ ] Docker/Pi-Images: alembic.ini und alembic/ ins Image aufnehmen; Schreibrechte auf data/filamenthub.db sicherstellen
7. [ ] Start-Skripte: Vor App-Start alembic upgrade head (oder init_db()) ausfuehren
8. [ ] Releases: Alembic mit ausliefern und Migrationen automatisch ausfuehren
9. [ ] Option: Bei fehlendem Alembic Start abbrechen statt warnen

## Phase 4 - CI / Tests
10. [ ] CI-Job: alembic upgrade head gegen frische DB
11. [ ] Tests im Service-Tab mit Test-DB, init_db vor pytest
12. [ ] Coverage ueber Smoke-Tests mit Test-DB

## Navigation / Design
13. [ ] Theme-Toggle finalisieren (Persistenz, OS-Mode optional, Light/Dark Assets)
14. [ ] About-Dialog im User-Menü ausliefern (Modal statt Alert)
15. [ ] User-Menü-Dropdown überall prüfen (Outside-Click, Keyboard, mobile)
16. [ ] Dashboard-KPIs/Charts in neues Layout integrieren
17. [ ] Settings-Seite: UI/Status-Feedback für API-Fehler verfeinern

## Phase 5 - Integrationen / Services
17. [ ] Test: Drucker-DB-Eintrag und Status im Debug/Status-API pruefen
18. [ ] Optionaler Auto-Connector fuer MQTT/Moonraker

## Phase 6 - Backup
15. [x] Backup-Funktion ergaenzt (DB) mit Trigger im Debug-Tab

## Phase 7 - MQTT / Debug-Center
### Low Effort
16. [ ] Topic-Liste mit Count + letzte Zeit + Klick fuer Detail
17. [ ] Feld-Kacheln (Temperaturen, Fortschritt)
18. [ ] Nachrichten-Rate (Linienplot)

### Medium
19. [ ] Diff-Viewer mit Highlight nur Veraenderungen
20. [x] JSON-Baum mit Collapse
21. [ ] Alert-Regeln (Schwellenwerte im UI)

### Fehlerbehebung / Logging
22. [x] MQTT-Logrotation auf RotatingFileHandler umstellen (Zugriffsfehler mqtt_messages.log beheben)

### High Impact
23. [ ] Aggregationspanel + Health Monitor
24. [ ] Kompakter Topic-Explorer
25. [ ] Feld-Inspector (Live-Kacheln mit Farbstatus)
26. [ ] Nachrichten-Rate Monitor (Diagramm)
27. [ ] Diff-Viewer fuer Topic-Aenderungen
28. [ ] Alert-Regeln: Schwellenwert + Popup/Sound
29. [ ] Payload-Suche + Favoriten
30. [ ] Strukturierter JSON-Baum mit Copy-Buttons
31. [ ] Export/Snapshot Button
32. [ ] Aggregationspanel: Durchschnitt/Min/Max
33. [ ] MQTT Health Panel
34. [ ] eine anzeige welches protokoll aktiv ob 5/311/usw und schaltpahr machen
35. [ ] UniversalMapper: Tests fuer single/multi AMS (parse_ams -> ams_units) ergaenzen

- [x] Alle Layout-Strings auf Encoding-Konsistenz pruefen.
- [x] Sidebar-Hygiene abgeschlossen.

- [x] Header-Cleanup abgeschlossen.

- [ ] Performance-Tab auf neues Layout migrieren
- [ ] MQTT-Viewer moderner machen und an globales Toast-/Notification-System anbinden
- [ ] AMS-Panel und Printer-Scanner in neue Struktur ueberfuehren
- [ ] WebSocket last_ping Tracking sauber implementieren
- [ ] Optional erweitern: CPU, Memory, Requests-per-Minute Abfragen
- [ ] MQTT reconnect-Status als Icon darstellen
- [ ] WebSocket last_ping sauber im Backend erfassen, um Status reachable/idle/offline zu stabilisieren
- [ ] MQTT-Details (Host/Port/Last Error) weiter ausbauen, sobald mehr Infrastruktur steht
- [ ] Optional: WS-Client-IP/Browser im Pro-Modus anzeigen
- [ ] Optional: WS-Message-Rate anzeigen
- [ ] MQTT-Live-Daten vollstaendig anbinden (nach Broker-Setup)
- [ ] MQTT Runtime: PrinterMQTTClient als zentrale Runtime-Instanz angebunden
- [ ] MQTT Runtime API: connect/disconnect/status Endpoints (Debug)
- [x] MQTT Runtime: Connect-Endpoint validiert (Schritt 1B)
- [x] Performance-Panel Frontend (Lite) an neuen /api/performance/panel Vertrag anbinden (defensive Fallbacks)
- [ ] Performance-Panel Pro: History/Statistics, Sparklines und Recording-Felder nachziehen
- [ ] Performance-API Feld-Normalisierung klären (statistics vs stats, recording_start vs recording_since)
- [ ] Performance-Contract vereinheitlichen: nested vs flat (cpu.percent vs cpu_percent, ram.percent vs ram_percent, disk.percent vs disk_percent, optionale totals ram_total_mb/disk_total_gb)
- [ ] Optional: Role-based Debug Center Access (Lite/Pro)
- [ ] Optional: Pro-Hinweis/Badge im UI für eingeschränkte Tabs
- [ ] Runtime/Requests im Debug-Frontend an Middleware-Metriken anbinden (Req/min, Avg Response)
- [ ] Optional: WS-Client-Details im Pro-Modus anzeigen
- [x] Abschluss-Checks Log-System durchgeführt
- [x] Limit-Capping, Modul-Whitelist, Admin-Gate, Logging-Level, Endpoint-Konsistenz geprüft
- [x] Log-System als STABIL markiert
- [x] Architektur-Fix abgeschlossen
- MQTT Connect: Panel-lokale Feldbindung finalisiert
- MQTT: Connect Handler vereinheitlicht (ein Endpoint, eine Funktion)
- MQTT Status-Farblogik korrigiert (Disconnected=rot)
- MQTT Connect: Schnellauswahl priorisiert, Passwort aus DB

## Recent work (2025-12-18)
- [x] Backend: Standardisierte Test-Response-Factory (`create_test_response`) eingeführt
- [x] Tests: `tests/test_service_routes_api.py` erweitert (success, command-error, exception cases + docker/compose/up tests)
- [x] Tests: `tests/test_database_routes_api.py` neu hinzugefügt (isolated tmp sqlite DB, CRUD + error case)
- [x] Refactor: Payload-Processing aus `app/routes/mqtt_routes.py` extrahiert nach `app/services/mqtt_payload_processor.py` (no side-effects)
- [x] DB: Alembic-Migration `20231202_add_spool_usage_fields` angepasst (missing `first_seen`); `init_db()`-based test init used
- [x] Test infra: Test runs use unique temp DB paths via `FILAMENTHUB_DB_PATH` and `init_db()` before pytest
- [x] Full test-suite executed with coverage; `htmlcov/` generated

## Next steps (short)
- [ ] Increase `app/routes/service_routes.py` coverage by adding focused tests for low-coverage endpoints (suggestions: `/tests/*`, `/docker/*`, `/backup`)
- [ ] Add tests for `database_routes` edge cases (vacuum, backup, backups/list)
- [ ] Optional: Add unit-tests for `mqtt_payload_processor` mapping behavior (pure function)


## Aktuelle Prioritäten
- [ ] Smart MQTT Logging Backend gemäß `sequential-purring-dolphin.md` implementieren und testen
- [ ] Coverage-Admin-Flow (Button + Report) mehrfach prüfen + ggf. Dokumentation ergänzen
- [ ] Auto-Connect Runtime & Startup-Hook mit echten Druckern verifizieren, Fehlertoleranz dokumentieren

## Lokale Debug/Cleanup (Dringend)
- [ ] Entferne temporäre Debug-Route `/api/admin/debug_verify` und zugehörige Audit-Log-Zeilen
- [ ] Entferne zusätzliche Debug-Audit-Einträge in `app/routes/admin_routes.py`
- [ ] Server neu starten und Admin-Login verifizieren (Lucy22032021)
- [ ] Reproduce `config.yaml` overwrite und Instrumentation prüfen
- [ ] Falls nötig: `debug_routes.save_config` instrumentieren, um config.yaml-Überschreiber zu finden
