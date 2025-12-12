<p align="center">
  <img src="docs/logo.png" width="280" />
</p>

<h1 align="center">FilamentHub</h1>
<p align="center">Modern, local filament management for Bambu, Klipper & standalone printers.</p>

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-0db7ed?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platforms-Win%20%7C%20Linux%20%7C%20Unraid-blue)
![Status](https://img.shields.io/badge/Status-Active_Development-orange)

![Bambu](https://img.shields.io/badge/Bambu-LAN%20%26%20Cloud-green)
![Klipper](https://img.shields.io/badge/Klipper-Supported-purple)

> **German version:** [README.md](README.md)

---

## Features

### Printer Management
- Overview of all registered printers
- Live status, temperatures, current job
- Print history, usage data, MQTT for Bambu (LAN)

### Filament Management
- Stock with vendor, color, material, remaining weight
- Last usage per printer, consumption data
- Optional low-stock warnings

### Analytics & Statistics
- Print time per printer
- Filament consumption & cost estimation
- Daily/monthly overviews

### Web UI
- Structured navigation (Dashboard / Printer / Filament / System)
- Cards, tables, status badges
- Dark, calm UI (Unraid-inspired)

### Database & Backups
- SQLite as integrated local database
- Debug/Service tab: backup button (ZIP with DB + logs) -> `data/backups/filamenthub_backup_<timestamp>.zip`
- DB maintenance: VACUUM, table explorer, ad-hoc SELECT

### Debug & Maintenance
- Debug Center with System, Service, MQTT, Performance, Database tabs
- Test runner (Smoke/DB/Coverage) against test DB
- Log management (rotation, list, clear)
- Backup (DB + logs) with one click

---

## Status & Roadmap
- Target: stable release **May 2026**
- Roadmap: [ANLEITUNG/Roadmap.md](ANLEITUNG/Roadmap.md)
- Handbook: [ANLEITUNG/Handbuch.md](ANLEITUNG/Handbuch.md)

---

## Quickstart (Dev)
```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt  # Windows
# or: source .venv/bin/activate && pip install -r requirements.txt  # Linux/Mac
python run.py  # starts FastAPI/uvicorn, default port 8080
```
Open the Debug/Service tab (browser on port 8080), test the backup button: ZIP will be in `data/backups/`.

## Quickstart (Docker)
```bash
docker build -t filamenthub .
docker run -d -p 8080:8080 -v $(pwd)/data:/app/data filamenthub
```

---

## License
MIT License

---

## Contact
Built by **d3nn3s08**
