# Migration Changelog

## 0.1 - Start der Migration (2025-12-06)
- Dateien: `app/services/printer_data.py`, `app/services/universal_mapper.py`, `services/printer_service.py`, `services/printer_mqtt_client.py`
- Aenderung: Kernmodule fuer die neue Pipeline (PrinterData, UniversalMapper, PrinterService, MQTT-Client) neu angelegt und lauffaehig gemacht.
- Roadmap-Stufe: Schritt 1 - Kernmodule pruefen & erstellen
- Legacy-Code: nicht veraendert, nur neue Dateien hinzugefuegt.
- Dateien: `app/main.py`
- Aenderung: Globalen `PrinterService` an der FastAPI-App registriert (`app.state.printer_service`) als Einstiegspunkt der neuen Pipeline.
- Roadmap-Stufe: Schritt 2 - PrinterService global einbinden
- Legacy-Code: unveraendert.
- Datum: 2025-12-06
- Dateien: `app/services/printer_data.py`
- Aenderung: PrinterData um Modellfeld, Timestamp und float-Progress erweitert; to_dict liefert kopierte Strukturen und Timestamp; progress als Optional[float].
- Roadmap-Stufe: Schritt 1 - Kernmodule finalisieren
- Legacy-Code: unveraendert.

## 0.2 - MQTT Routing Umbau (geplant)
- Datum: 2025-12-06
- Dateien: `app/routes/mqtt_routes.py`
- Aenderung: Analyse des aktuellen MQTT-Handlers; derzeit wird Serial via Topic-Split (`device/<serial>/...`) extrahiert, JSON direkt verarbeitet, `parse_ams`/`parse_job` genutzt, Job/AMS-Tracking auf rohen Feldern (`gcode_state`, `mc_percent`, `ams.trays`) basierend; kein UniversalMapper/PrinterData im Einsatz.
- Roadmap-Stufe: Schritt 3 - MQTT-Routing analysieren
- Legacy-Code: weiterhin aktiv (parse_ams, parse_job, mc_* Zugriffe, raw Payload Broadcast).
- Datum: 2025-12-06
- Dateien: `app/routes/mqtt_routes.py`
- Aenderung: MQTT-Connect setzt nun Default-Credentials (User `bblp`, TLS insecure, Port 8883) und registriert den globalen `PrinterService`; `on_message` mapped Payloads ueber `UniversalMapper` (Modell aus DB via `cloud_serial`), schreibt PrinterData in den Service und sendet im WebSocket neben Topic/Payload auch `printer` (mapped) und `raw` (Fallback).
- Roadmap-Stufe: Schritt 4 - MQTT-Routing umbauen
- Legacy-Code: parse_ams/parse_job und mc_*/raw-Pfade bleiben aktiv (Soft-Switch).
- Datum: 2025-12-06
- Dateien: `app/routes/mqtt_routes.py`
- Aenderung: WebSocket-Payload vereinheitlicht (`topic`, `payload`, `printer`, `raw`, `timestamp`, `qos`), DB-Lookup via `cloud_serial` für Modellwahl, PrinterData als Primärquelle; AMS/Job sync nutzt gemappte AMS falls vorhanden.
- Roadmap-Stufe: Schritt 4 - MQTT-Routing finalisieren
- Legacy-Code: parse_ams/parse_job weiterhin als Fallback aktiv.
- Datum: 2025-12-06
- Dateien: `app/services/universal_mapper.py`
- Aenderung: Mapper robuster gemacht (float-Progress, Safe-Floats/-Ints, modellabhängige Blöcke inkl. print_status/H2D, Layer-Clamping, keine Exceptions, Extras sauber gefüllt).
- Roadmap-Stufe: Schritt 1/4 - Kernmodule finalisieren / Mapper-Härtung
- Legacy-Code: unverändert, nur Mapping erweitert.
- Datum: 2025-12-06
- Dateien: `services/printer_mqtt_client.py`
- Aenderung: MQTT-Client mit Debug-Logging, Reconnect-Handling, sauberen Fehlermeldungen, Mapper-Update bei Modelwechsel, TLS-Login bblp/API-Key beibehalten.
- Roadmap-Stufe: Schritt 1/4 - Kernmodule finalisieren / MQTT-Eingang härten
- Legacy-Code: unverändert.
- Datum: 2025-12-06
- Dateien: `app/models/printer.py`
- Aenderung: Datenmodell um `model` (z.B. X1C, A1MINI, P1S, H2D) und `mqtt_version` (Default 311) ergänzt.
- Roadmap-Stufe: Schritt 7 - DB-Modell erweitern
- Legacy-Code: unverändert, Migration noch erforderlich.

## 0.3 - UI/JobParser (geplant)
- Datum: 2025-12-06
- Dateien: `app/static/debug.js`, `app/services/job_parser.py`, `app/templates/ams_help.html`
- Aenderung: Analyse - UI/Parser nutzen aktuell rohes JSON (mc_print.stage, mc_percent, gcode_state, layer_num, remain_time, AMS/tray Felder). Ziel: primaer `message.printer.*` (state, progress, layer.current/total, temperature.nozzle/bed/chamber, job.time_remaining) verwenden, alte Pfade als Fallback behalten.
- Roadmap-Stufe: Schritt 5 - UI/JobParser pruefen (geplant)
- Legacy-Code: unveraendert, noch vollstaendig aktiv.
- Datum: 2025-12-06
- Dateien: `app/static/debug.js`
- Aenderung: UI-Compatibility Layer ergänzt – bevorzugt `message.printer` (state/progress/temp/layer/job) und faellt auf raw JSON zurück; PrinterData wird im Inspector mitgespeichert.
- Roadmap-Stufe: Schritt 5 - UI/JobParser umstellen (kompatibel, Legacy-Fallback aktiv)
- Legacy-Code: mc_*/print.* Fallbacks bleiben erhalten.
- Datum: 2025-12-06
- Dateien: `services/printer_service.py`
- Aenderung: Typisierung und last_update für PrinterData-Cache ergänzt, unbekannte Drucker werden geloggt und registriert, get_all liefert konsistente Datenstrukturen.
- Roadmap-Stufe: Schritt 3 - PrinterService finalisieren
- Legacy-Code: unverändert.

## 0.4 - Legacy Removal (geplant)
- Datum: 2025-12-06
- Dateien: `app/routes/mqtt_routes.py`, `app/services/ams_parser.py`, `app/services/job_parser.py`, `app/static/debug.js`
- Aenderung: Kennzeichnung - Legacy-Pfade (parse_ams, parse_job, mc_* und print.* Direktzugriffe, raw Payload-Broadcast) bleiben bewusst bestehen und werden erst nach stabiler PrinterData-Umstellung entfernt.
- Roadmap-Stufe: Schritt 6 - Legacy-Code entfernen (geplant)
- Legacy-Code: weiterhin aktiv, kein Entfernen in diesem Schritt.
- Datum: 2025-12-06
- Dateien: `alembic/versions/20251206_182015_add_printer_model_and_mqtt_version.py`, `app/models/printer.py`
- Aenderung: Neue Spalten `model` (String(32), Default X1C) und `mqtt_version` (String(8), Default 311) für Printer angelegt, Defaults nach Migration entfernt; Modelle in SQLModel mit max_length ergänzt. Alembic upgrade ausgeführt.
- Roadmap-Stufe: Schritt 7 - DB-Modell erweitern
- Legacy-Code: unverändert.
- Datum: 2025-12-06
- Dateien: `app/services/universal_mapper.py`
- Aenderung: Modell-Abdeckung erweitert (X1/P1/A1/H2D), robuste Fallbacks und H2D-Kühl-/Materialfelder integriert; keine Exceptions mehr.
- Roadmap-Stufe: Schritt 4 - Modellintegration (A1/P1/H2D)
- Legacy-Code: unverändert.
- Datum: 2025-12-06
- Dateien: `app/services/job_parser.py`
- Aenderung: Job-Parser nutzt vorrangig PrinterData (`message.printer`) und faellt nur bei Bedarf auf Roh-Report zurück.
- Roadmap-Stufe: Schritt 5 - UI/JobParser (Migration)
- Legacy-Code: Fallback erhalten.

## 0.5 - MQTT Auto Protocol Detection (geplant)
- Datum: 2025-12-06
- Dateien: `services/mqtt_protocol_detector.py`
- Aenderung: Neuer Service zur automatischen MQTT-Protokollerkennung (v5/311/31) mit TLS+Auth-Test und Nachrichtenerhalt-Validierung.
- Roadmap-Stufe: Zusatzkommando – MQTT Auto-Protokollerkennung
- Legacy-Code: keine Änderungen, nur Erweiterung.

## 0.6 - UniversalMapper Full Integration (Bambu + Klipper)
- Datum: 2025-12-06
- Dateien: `app/services/universal_mapper.py`, `app/services/printer_data.py`, `services/printer_service.py`, `services/printer_mqtt_client.py`, `app/services/job_parser.py`, `app/routes/mqtt_routes.py`
- Aenderung: UniversalMapper komplett ersetzt (Bambu X1/P1/A1/H2D + Klipper/Moonraker, Auto-Modell-Erkennung, safe int/float, Layer-Clamp, Fans/Lights/AMS/Job/Error Mapping, no-exception); PrinterData/Service/Client kompatibel; Job-Parser priorisiert PrinterData; MQTT-Routing bleibt kompatibel; UI Fallbacks aktiviert.
- Dateien: `tests/test_mapper_x1c_idle.py`, `tests/test_mapper_klipper.py`, `tests/test_mapper_generic.py`
- Aenderung: Unit-Tests für Bambu-Fixture, Klipper-Dummy und generischen Fallback hinzugefügt.
- Roadmap-Stufe: 1/2/3/4/5 – Kernmodule finalisieren, Bambu/Klipper Integration, UI/JobParser Kompatibilität
- Legacy-Code: Fallbacks bleiben aktiv; parse_ams/parse_job nicht entfernt.
