# FilamentHub – Gesamtanalyse & AMS-Analyse

## 1. Gesamtanalyse (Systemarchitektur, Stand Dezember 2025)

### 1.1 Grundprinzip
- Entwicklungsrahmen: Analyse → Entscheidung → Umsetzung (getrennte Modi)
- KI darf nur nach expliziter Freigabe implementieren, sonst nur analysieren

### 1.2 Architektur & Module
- Modularer Aufbau: Scanner, PrinterService, MQTT, AMS, Debug Center
- Datenflüsse: MQTT → Mapper/Service → PrinterData → UI (Websocket)
- Trennung von Runtime, Debug, Produktivlogik

### 1.3 Printer-Erkennung & Auto-Mapping
- Implizites Mapping über Serial/Topic/ID
- Mapping-Logik in PrinterService und MQTT-Auswertung
- Kein expliziter Auto-Mapper als zentrales Modul

### 1.4 Scanner Lite vs. PRO
- Scanner-Funktionen vorhanden, aber keine klare Trennung Lite/PRO
- PRO-Features teils geplant, teils noch nicht umgesetzt
- Potenzial für Redundanzen bei doppelter Scanner-Logik

### 1.5 AMS-Integration (Überblick)
- AMS-Status, Slot-Erkennung, Spool-Zuordnung vorhanden
- Multi-AMS vorbereitet, aber noch nicht voll produktiv
- AMS als Capability eines Druckers teils modelliert

### 1.6 Confidence/Trust
- Implizite Vertrauensannahmen (z. B. MQTT vorhanden → Drucker gültig)
- Explizites Confidence-Modell würde nur formalisieren

### 1.7 Datenverträge & Normalisierung
- Teils stabile Datenverträge, teils Inkonsistenzen (nested/flat)
- Refactoring und Dokumentation empfohlen

### 1.8 Debug Center
- Panels spiegeln viele reale Systemzustände
- Einige Debug-Funktionen ohne Backend-Wahrheit

### 1.9 Redundanzen & Risiken
- Potenziell doppelte Scanner-Logik
- Mehrfach-Erkennung desselben Druckers möglich
- Inkonsistenzen zwischen Scanner, PrinterService, AMS möglich

### 1.10 Gap-Analyse & Empfehlungen
- Viele Features existieren implizit, sollten konsolidiert und dokumentiert werden
- PRO-Features nur umsetzen, wenn echter Mehrwert
- Fokus auf Konsolidierung und Klarheit statt Feature-Menge

---

## 2. AMS-Analyse (Stand Dezember 2025)

### 2.1 Existenz & Vollständigkeit
  
# AMS-STRICT-ANALYSE (Dezember 2025)
## ANALYSE 1: AMS-Parser im PrinterService
1. Funktion vorhanden: Ja
2. Funktion vollständig: Nein (siehe Details)
3. Zweck der Funktion:
	- Extrahiert AMS-Daten (Slots, Status) aus Bambu-/MQTT-JSON für die Druckerverwaltung.
4. Analyse der aktuellen Logik:
	- AMS-Daten werden aus dem JSON gelesen (parse_ams, UniversalMapper).
	- Es wird meist nur ein AMS-Block (ams_0) verarbeitet; ams_1, ams_2 etc. sind vorbereitet, aber nicht voll integriert.
	- Die Logik nimmt oft implizit Single-AMS an (z. B. direkte Zuordnung zu Drucker/Slot).
	- Multi-AMS wird in Settings und Mappern erwähnt, aber die Verarbeitung ist nicht durchgängig.
	- Fehlerhafte oder unvollständige Daten werden teils abgefangen, aber nicht systematisch validiert.
5. Bewertung Single-AMS-Fähigkeit:
	- Voll funktionsfähig, produktiv im Einsatz.
6. Bewertung Multi-AMS-Fähigkeit:
	- Logisch vorbereitet, aber nicht durchgängig implementiert oder getestet.
	- Annahmen (z. B. nur ams_0) verhindern echte Multi-AMS-Nutzung.
7. Erkannte Schwächen / Risiken:
	- Multi-AMS wird nicht konsistent unterstützt.
	- Parser ist bei fehlerhaften Daten nicht robust genug (fehlende Nodes, leere Slots, inkonsistente Strukturen).
	- Risiko von Datenverlust bei mehreren AMS-Modulen.
8. Was fehlt konkret?
	- Durchgängige Verarbeitung von ams_1, ams_2 ...
	- Systematische Fehlerbehandlung und Validierung für Multi-AMS.
	- Klare Trennung/Zuordnung von AMS-Instanzen zu Druckern.
9. Testsituation:
	- Tests für Single-AMS vorhanden oder geplant.
	- Multi-AMS- und Fehlerfalltests fehlen.
10. Empfehlung (konzeptionell):
	- Parser auf echte Multi-AMS-Fähigkeit und Fehlerrobustheit erweitern.
	- Systematische Tests für Multi-AMS und fehlerhafte Daten ergänzen.
---
## ANALYSE 2: Mapper + Modelle
1. Funktion vorhanden: Ja (Mapper und Modelle existieren)
2. Funktion vollständig: Nein (Multi-AMS nicht voll integriert)
3. Zweck der Funktion:
	- Mappen von AMS- und Slot-Daten auf interne Datenmodelle (Spool, Slot, ggf. AMS-Instanz).
4. Analyse der aktuellen Logik:
	- Slot-Daten werden gemappt, meist auf Basis von ams_0.
	- AMS-Hierarchie ist angedeutet (ams_0, ams_1), aber nicht durchgängig im Modell abgebildet.
	- AMS-ID als explizites Feld im Modell fehlt oder wird nicht überall genutzt.
	- Daten werden bei mehreren AMS-Modulen potenziell überschrieben, nicht zusammengeführt.
	- Modell ist für Single-AMS ausgelegt, Multi-AMS nur teilweise vorbereitet.
5. Bewertung Single-AMS-Fähigkeit:
	- Ja, stabil und produktiv.
6. Bewertung Multi-AMS-Fähigkeit:
	- Strukturell möglich, aber nicht ohne Anpassungen.
	- Erweiterung auf Multi-AMS erfordert Modell- und Mapping-Refactor.
7. Erkannte Schwächen / Risiken:
	- Keine eindeutige AMS-ID im Modell → Zuordnungsprobleme bei Multi-AMS.
	- Risiko von Datenverlust/Überschreibung bei mehreren AMS-Modulen.
	- Slot-Zuordnung nicht eindeutig, falls mehrere AMS vorhanden.
8. Was fehlt konkret?
	- Explizite AMS-ID im Modell.
	- Zusammenführung statt Überschreibung von Slot-Daten.
	- Durchgängige Multi-AMS-Unterstützung in Mapper und Modellen.
9. Testsituation:
	- Mapper- und Modelltests für Single-AMS vorhanden oder geplant.
	- Multi-AMS- und Edge-Case-Tests fehlen.
10. Empfehlung (konzeptionell):
	- Modell und Mapper auf explizite Multi-AMS-Fähigkeit umbauen (AMS-ID, Slot-Relation).
	- Tests für Multi-AMS und Slot-Zuordnung ergänzen.
---
**Hinweis:**
Diese Analyse erfolgte strikt read-only und ohne jegliche Codeänderung. Empfehlungen sind rein konzeptionell und dienen der Klarheit für die weitere Entwicklung.

### 2.2 Logische Korrektheit
- Single-AMS produktiv, Multi-AMS vorbereitet, aber noch nicht voll getestet
- Mapping über Materialname, Farbe, Slot, Hersteller
- Fehlerfälle teils behandelt, aber nicht systematisch dokumentiert

### 2.3 Testabdeckung
- Tests für UniversalMapper/AMS in TODO, aber noch nicht vollständig
- Keine Hinweise auf Edge-Case- oder Multi-AMS-Tests

### 2.4 Bewertung
| Bereich                | Existiert (IST)                | Fehlt / Lücke                        |
|------------------------|-------------------------------|--------------------------------------|
| AMS-Status/Slot-Infos  | Ja, Backend & Doku            | -                                    |
| Single-AMS             | Ja, produktiv                 | -                                    |
| Multi-AMS              | Logisch vorbereitet           | Volle Testabdeckung, produktive Nutzung |
| AMS-Mapping            | Ja, Slot/Spool-Zuordnung      | Edge-Case-Handling, Mapping-Tests    |
| Fehlerfälle            | Teilweise behandelt           | Systematische Fehlerfall-Tests       |
| Testabdeckung          | Grundlegend, TODO für Mapper  | Edge/Multi-AMS, Fallback, Fehlerdaten|

### 2.5 Empfehlungen
- Fokus auf systematische Tests für Multi-AMS, Fehlerfälle und Mapping-Logik
- Dokumentation der aktuellen Fehlerbehandlung und Fallbacks
- Keine neuen Features, bevor Multi-AMS-Logik und Tests abgeschlossen sind

---

**Fazit:**
FilamentHub ist modular und AMS ist als Kernfunktion verankert. Single-AMS funktioniert, Multi-AMS ist vorbereitet, aber noch nicht voll abgesichert. Die größte Lücke besteht in der Testabdeckung und der systematischen Fehlerfallbehandlung. Konsolidierung und Dokumentation sind wichtiger als neue Features.