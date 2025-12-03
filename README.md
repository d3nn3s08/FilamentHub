<p align="center">
  <img src="data/A_German-language_presentation_graphic_depicts_a_p.png" width="300" />
</p>

<h1 align="center">FilamentHub</h1>
<p align="center">Modernes, lokales Filament-Management für Bambu, Klipper & Standalone.</p>

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-0db7ed?logo=docker)
![License](https://img.shields.io/badge/Lizenz-MIT-green)
![Platform](https://img.shields.io/badge/Plattformen-Win%20%7C%20Linux%20%7C%20Unraid-blue)
![Docker Build](https://img.shields.io/github/actions/workflow/status/d3nn3s08/FilamentHub/docker-publish.yml?branch=main&label=Docker%20Build)

![Status](https://img.shields.io/badge/Status-Aktive_Entwicklung-orange)

![Bambu](https://img.shields.io/badge/Bambu-LAN%20%26%20Cloud-green)
![Klipper](https://img.shields.io/badge/Klipper-Unterstützt-purple)

> 🇺🇸 **English version:** [README.en.md](README.en.md)

---
![Status](https://img.shields.io/badge/Status-Nicht%20lauff%C3%A4hig%20aktuell-red)



## Funktionen

### Druckerverwaltung
- Übersicht aller registrierten Drucker
- Live-Status, Temperaturen, aktueller Job
- Druckhistorie, Nutzungsdaten, MQTT für Bambu (LAN)

### Filamentverwaltung
- Bestände mit Hersteller, Farbe, Material, Restmenge
- Letzte Nutzung je Drucker, Verbrauchsdaten
- Warnungen bei niedrigem Bestand (optional)

### Analyse & Statistiken
- Druckzeit pro Drucker
- Filamentverbrauch & Kostenabschätzung
- Tages-/Monatsübersichten

### Weboberfläche
- Strukturierte Navigation (Dashboard / Printer / Filament / System)
- Karten, Tabellen, Status-Badges
- Dunkles, ruhiges UI (Unraid-inspiriert)

### Datenbank & Backups
- SQLite als integrierte lokale Datenbank
- Debug/Service-Tab: Backup-Button (ZIP mit DB + Logs) → `data/backups/filamenthub_backup_<timestamp>.zip`
- DB-Wartung: VACUUM, Tabellen-Explorer, Ad-hoc-SELECT

### Debug & Wartung
- Debug Center mit System-, Service-, MQTT-, Performance- und Datenbank-Tabs
- Test-Runner (Smoke/DB/Coverage) gegen Test-DB
- Log-Management (Rotation, Anzeigen, Löschen)
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
Debug/Service-Tab öffnen (Browser auf Port 8080), dort Backup-Button testen: ZIP liegt danach unter `data/backups/`.

## Quickstart (Docker)
```bash
docker build -t filamenthub .
docker run -d -p 8080:8080 -v $(pwd)/data:/app/data filamenthub
```

---

## Lizenz
MIT License

---

## Kontakt
Entwickelt von **d3nn3s08**
