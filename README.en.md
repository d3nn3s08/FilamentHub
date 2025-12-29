<p align="center">
  <img src="data/A_German-language_presentation_graphic_depicts_a_p.png" width="300" />
</p>

<h1 align="center">FilamentHub</h1>
<p align="center">
Open-source dashboard for filament, printer, and system management – local, independent, and inspired by the Unraid UI.
</p>

<p align="center">

  <!-- Status -->
  <img src="https://img.shields.io/badge/Status-Active%20Development-orange" />
  <img src="https://img.shields.io/badge/Phase-Public%20Beta-yellow" />
  <img src="https://img.shields.io/badge/Release-v1.6.0--beta-blue" />

  <!-- Technology -->
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" />
  <img src="https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi" />
  <img src="https://img.shields.io/badge/Docker-Ready-0db7ed?logo=docker" />

  <!-- Platform -->
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Unraid-blue" />

  <!-- License -->
  <img src="https://img.shields.io/badge/License-MIT-green" />

  <!-- Build -->
  <img src="https://img.shields.io/github/actions/workflow/status/d3nn3s08/FilamentHub/docker-publish.yml?branch=main&label=Docker%20Build" />
  <img src="https://img.shields.io/github/v/release/d3nn3s08/FilamentHub" />

  <!-- Docker -->
  <img src="https://img.shields.io/docker/image-size/d3nn3s/filamenthub/latest" />
  <img src="https://img.shields.io/docker/pulls/d3nn3s/filamenthub" />

  <!-- Integration -->
  <img src="https://img.shields.io/badge/Bambu-LAN%20%26%20Cloud-green" />
  <img src="https://img.shields.io/badge/Klipper-Supported-purple" />

</p>

<p align="center">
----------------------------------------------------
</p>

<p align="center">
  <a href="https://www.paypal.me/Denis10" target="_blank">
    <img src="https://img.shields.io/badge/Donate%20via%20PayPal-0070ba?logo=paypal&logoColor=white" />
  </a>
</p>

<p align="center">
  <a href="https://ko-fi.com/BOB51PV6CH">
    <img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Support me on Ko-fi" />
  </a>
</p>

> 🇩🇪 **German version:** [README.md](README.md)

---

## 🚧 Project Status – Public Beta

⚠️ **FilamentHub is currently in a public beta phase (v1.6.0-beta).**

- Core features are stable and ready for active use
- Database migrations run automatically on startup
- Job and filament tracking is production-ready
- APIs, UI, and data models may still change
- **Regular database backups are strongly recommended**

This beta is intended for technically experienced users and early adopters.  
Feedback, bug reports, and suggestions are highly welcome.

---

# 🧩 Project Overview

FilamentHub originally started as a **small, local filament management tool**  
for spools, colors, remaining material, and usage tracking.

Over time, the project grew significantly.  
What began as a simple tool evolved step by step into a full  
**3D printing management dashboard**, covering much more than filament alone:

- Filament management  
- Printer monitoring  
- System diagnostics  
- MQTT integration  
- Debug and maintenance tools  
- Unraid-inspired web interface  
- Docker-based deployment  

The name stayed the same – the scope expanded.

Today, FilamentHub is in a **public beta phase**, focused on  
**stability, data integrity, and a clean technical foundation**.

---

# 🚀 Features

## **Printer Management**
- Overview of all registered printers  
- Live status, temperatures, and current job  
- Bambu LAN MQTT support  
- Print history and usage statistics  
- Stable WebSocket status with ping/pong analysis (debug view)

## **Filament Management**
- Spool management with manufacturer, color, material, and remaining amount  
- Last usage per printer  
- Consumption per job / day / month  
- Cost estimations  
- Low-stock warnings  

## **Analytics & Statistics**
- Print time per printer  
- Filament consumption over time  
- Cost analysis  
- Distribution by material, color, and machine  

## **Web Interface (Unraid-inspired)**
- Clear navigation: **Dashboard / Printer / Filament / System / Debug**  
- Cards, tables, icons, and status badges  
- Dark, calm UI  
- Responsive design for desktop and server environments  

## **Database & Backups**
- Local SQLite database (created automatically)  
- Integrated backup button  
  → creates a ZIP containing **database + logs**  
  → stored at:  
  `data/backups/filamenthub_backup_<timestamp>.zip`  
- Database tools: VACUUM, table viewer, test queries  

## **Debug & Maintenance**
- Debug center including:
  - System overview  
  - Service status  
  - Log viewer  
  - MQTT monitor with lock times, ping, last message, sparklines  
  - Test runner (DB tests, smoke tests)  
  - Log rotation and cleanup  

---

# 🖼️ Screenshots

<p align="center">
  <a href="data/screenshots/Dashboard.png">
    <img src="data/screenshots/Dashboard.png" width="320" alt="Dashboard">
  </a>
  <a href="data/screenshots/Material.png">
    <img src="data/screenshots/Material.png" width="320" alt="Material management">
  </a>
  <a href="data/screenshots/AMS_übersicht.png">
    <img src="data/screenshots/AMS_übersicht.png" width="300">
  </a>
  <a href="data/screenshots/Spulen.png">
    <img src="data/screenshots/Spulen.png" width="320" alt="Spool management">
  </a>
</p>

<p align="center">
  <sub>Dashboard · Material · Spools</sub>
</p>

<p align="center">
  <a href="data/screenshots/statistiken.png">
    <img src="data/screenshots/statistiken.png" width="300" alt="Statistics">
  </a>
  <a href="data/screenshots/statistiken_02.png">
    <img src="data/screenshots/statistiken_02.png" width="300" alt="Statistics details">
  </a>
  <a href="data/screenshots/jobs.png">
    <img src="data/screenshots/jobs.png" width="300" alt="Jobs overview">
  </a>
</p>

<p align="center">
  <sub>Statistics · Details · Jobs</sub>
</p>

<p align="center">
  <a href="data/screenshots/mini_user_menu.png">
    <img src="data/screenshots/mini_user_menu.png" width="280" alt="Mini user menu">
  </a>
</p>

<p align="center">
  <sub>UI details · User menu</sub>
</p>

---

# 📅 Status & Roadmap

- Target for stable version 1.0: **May 2026**
- Current state: **Public Beta – stable for use, actively developed**
- Roadmap: [ANLEITUNG/Roadmap.md](ANLEITUNG/Roadmap.md)
- Manual: [ANLEITUNG/Handbuch.md](ANLEITUNG/Handbuch.md)

---

# 🛠️ Quickstart (Development)

> ⚠️ Note: This setup is intended for developers and beta testers.

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt  # Windows
# or
source .venv/bin/activate && pip install -r requirements.txt  # Linux/Mac

python run.py  # Starts API + UI (Port 8085)
