<p align="center">
  <img src="docs/logo.png" width="280" />
</p>

<h1 align="center">FilamentHub</h1>
<p align="center">Modernes, lokales Filament-Management fuer Bambu, Klipper & Standalone.</p>

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-0db7ed?logo=docker)
![License](https://img.shields.io/badge/Lizenz-MIT-green)
![Platform](https://img.shields.io/badge/Plattformen-Win%20%7C%20Linux%20%7C%20Unraid-blue)
![Status](https://img.shields.io/badge/Status-Aktive_Entwicklung-orange)

![Bambu](https://img.shields.io/badge/Bambu-LAN%20%26%20Cloud-green)
![Klipper](https://img.shields.io/badge/Klipper-Unterstuetzt-purple)

> **English version:** [README.en.md](README.en.md)

---

## Funktionen

### Druckerverwaltung
- Uebersicht aller registrierten Drucker
- Live-Status, Temperaturen, aktueller Job
- Druckhistorie, Nutzungsdaten, MQTT fuer Bambu (LAN)

### Filamentverwaltung
- Bestaende mit Hersteller, Farbe, Material, Restmenge
- Letzte Nutzung je Drucker, Verbrauchsdaten
- Warnungen bei niedrigem Bestand (optional)

### Analyse & Statistiken
- Druckzeit pro Drucker
- Filamentverbrauch & Kostenabschaetzung
- Tages-/Monatsuebersichten

### Weboberflaeche
- Strukturierte Navigation (Dashboard / Printer / Filament / System)
- Karten, Tabellen, Status-Badges
- Dunkles, ruhiges UI (Unraid-inspiriert)

### Datenbank & Backups
- SQLite als integrierte lokale Datenbank
- Debug/Service-Tab: Backup-Button (ZIP mit DB + Logs) -> `data/backups/filamenthub_backup_<timestamp>.zip`
- DB-Wartung: VACUUM, Tabellen-Explorer, Ad-hoc-SELECT

### Debug & Wartung
- Debug Center mit System-, Service-, MQTT-, Performance- und Datenbank-Tabs
- Test-Runner (Smoke/DB/Coverage) gegen Test-DB
- Log-Management (Rotation, Anzeigen, Loeschen)
- Backup (DB + Logs) auf Knopfdruck

---

## Status & Roadmap
- Ziel: stabile Release **Mai 2026**
- Roadmap: [ANLEITUNG/Roadmap.md](ANLEITUNG/Roadmap.md)
- Anleitung/Handbuch: [ANLEITUNG/Handbuch.md](ANLEITUNG/Handbuch.md)

---

## Quickstart (Dev)
```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt  # Windows
# oder: source .venv/bin/activate && pip install -r requirements.txt  # Linux/Mac
python run.py  # startet FastAPI/uvicorn, Standard-Port 8080
```
Debug/Service-Tab oeffnen (Browser auf Port 8080), dort Backup-Button testen: ZIP liegt danach unter `data/backups/`.

## Quickstart (Docker)
```bash
# Von Docker Hub (empfohlen für Nutzer)
docker pull d3nn3s08/filamenthub:latest
docker-compose up -d

# Oder selbst bauen (für Entwickler)
docker build -t filamenthub .
docker-compose up -d

# App öffnen
# http://localhost:8085
```

> **Hinweis:** Die App funktioniert vollständig ohne Admin-Zugang!
> Der Admin-Bereich ist nur für den Entwickler vorgesehen und wird auf Anfrage freigegeben.

---

## Lizenz
MIT License

---

## Kontakt
Entwickelt von **d3nn3s08**

---

## Entwickler-Feature: Coverage

Die Coverage-Funktionalität ist als reines Entwickler-Feature markiert und darf nicht im Produktivbetrieb ausgeführt werden.

Aktivierung (lokal/development):

Windows PowerShell:

```powershell
$env:FILAMENTHUB_DEV_FEATURES = "1"
```

Linux/macOS:

```bash
export FILAMENTHUB_DEV_FEATURES=1
```

Hinweis: `pytest` und `pytest-cov` müssen auf dem System installiert sein, damit die Coverage-Ausführung funktioniert.
