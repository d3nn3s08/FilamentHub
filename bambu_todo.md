# Bambu TODO

## Phase 1 - AMS/Status (Basis)
1. [x] AMS-Status abrufen (Connect)
2. [x] Slot-Infos auslesen (IDs/Status)
3. [x] Materialtyp/Farbe erkennen (aus Payload)
4. [x] Aktiven Slot erfassen
5. [x] Erweiterte AMS-Daten: Reste-Metriken (falls verfuegbar), Drybox-Status, Temperatur/Feuchtigkeit
6. [x] Mehrere AMS-Module unterstuetzen (AMS1/AMS2)

## Phase 1 - Drucker/Job-Basics
7. [x] Verbindung zu jedem Drucker herstellen
8. [x] Aktuellen Job auslesen
9. [x] Materialanforderung des Jobs erkennen

## Phase 2 - Spulen/Tracking & Zuordnung
10. [x] Spulen automatisch zuordnen (Materialname, Farbe, AMS-Slot, Hersteller)
11. [x] Verbrauch pro Spule tracken (Start-/Restgewicht, Verbrauch pro Druck, Auto-Update)
12. [ ] Historie pro Spule (letzter Einsatz, Drucker, Gesamt-Druckzeit)
13. [ ] Warnungen/Flags (fast leer, leer, nicht im AMS)
14. [x] Abgleich Job <-> AMS <-> Spule (Material-Matching)
15. [x] Automatische Zuordnung zum Druckauftrag; Vorschlag bei mehreren; Hinweis wenn keine passt; AMS-Slot verlinken
16. [x] MQTT-Anbindung

## Phase 2 - Webinterface
17. [ ] Separate Views/Seiten: Printer (inkl. AMS-Infos) und Filament (Spulenliste)
18. [x] Spulenliste: Name, Material, Farbe, letzter Einsatz, Drucker, Restmenge
19. [ ] AMS-View: Slots mit Material-Anzeige, aktiver Slot hervorgehoben, Warnungen

## Phase 3 - Erweiterte Erkennung (optional)
19. [ ] QR-Codes/RFID (NTAG etc.)
20. [ ] Visuelle Erkennung (Farberkennung ueber Kamera)

## Phase 4 - Komfort/Verbindung

- [ ] MQTT-Auto-Connect
- [ ] MQTT-Protokoll wählbar (3.1.1 vs 5.0) pro Verbindung
    - Debug-Panel: Dropdown "MQTT Version" (Default 3.1.1 f?r A1 mini, Option 5.0 f?r X1C)
    - /api/mqtt/connect akzeptiert `protocol_version` und setzt Client auf v3.1.1 oder v5
    - Optional: Auto-Default je nach Drucker-Modell
 Checkbox für Bambu-Drucker
    - Checkbox „Automatisch MQTT verbinden“ im Drucker-Bearbeiten-Dialog einbauen (Frontend)
    - Feld auto_connect in der Datenbank ergänzen
    - Beim Speichern wird das Feld gesetzt
    - Backend baut MQTT-Verbindung nur für Drucker mit auto_connect = true auf
    - Einstellung ist im Dialog sichtbar und änderbar
################################################
Alles zusammen in einem Paket:

Spulen-Dialog (Frontend):

Checkbox „Ohne RFID/Chip“ → macht „Virtuelle ID“ Pflicht.
Feld „Virtuelle ID“ + Button „ID generieren“ (kurzer Code, z. B. VSP‑1234).
Checkbox „Spule neu“ → setzt Status/used_count=0, remain=100 % bzw. Restgewicht = Gewicht_voll.
Nach erfolgreicher ID-Generierung: Button „QR/Barcode anzeigen“ (Modal mit Download/Print).
Backend:

Beim Speichern ohne RFID: virtuelle ID als eindeutigen Schlüssel speichern (z. B. in tag_uid/external_id) und als Tag-Ersatz nutzen.
Matching-Reihenfolge im AMS-Report: tag_uid (inkl. virtuelle), dann tray_uuid, dann Slot als Fallback.
„Spule neu“: used_count=0, remain_percent=100 bzw. Gewicht = weight_full, Status „Neu“.
Pending-Flow bei unbekannter Spule (keine Tag/Slot-Erkennung):

Start: Verbrauch wird getrackt, Spule ist „Unbekannt“.
Ende: Modal „Druckauftrag fertig – bitte Spule zuweisen“, Auswahl aus Spulen (inkl. virtueller). Nach Bestätigung werden Verbrauch und job_spool_usage auf die gewählte Spule verbucht (used_count/Gewicht/last_slot aktualisieren). Bei „Nein“ bleibt der Job „Zuweisung ausstehend“.
Damit haben wir virtuelle IDs, QR/Barcode, Spule-neu-Logik, sauberes Matching und den „Unbekannt → nachträglich zuweisen“-Flow. Wenn das so passt, setze ich es um.


## Recent work (2025-12-18)
- [x] Tests: API-Tests für `service_routes` ergänzt (Success/Error/Exception + Docker endpoint mocks)
- [x] Tests: `database_routes` API-tests hinzugefügt (isolated tmp sqlite DB, CRUD + error case)
- [x] Refactor: MQTT payload processing extracted to `app/services/mqtt_payload_processor.py` (keeps `on_message()` lean)
- [x] Test infra: Per-run temporary test DBs and `init_db()` flow established to avoid locking issues

## Next steps (short)
- [ ] Add lightweight unit tests for payload processing and AMS/job parsing logic (pure functions)
- [ ] Harden spool assignment edge-cases exposed by tests (unknown spools, virtual IDs)



