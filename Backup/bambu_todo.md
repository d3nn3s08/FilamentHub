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
