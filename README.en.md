<p align="center">
  <img src="docs/logo.png" width="180" />
</p>

# FilamentHub  
Modern Filament Management for Bambu, Klipper & Standalone Printers

FilamentHub is a fully local, open-source filament and spool management system.  
It helps you track materials, remaining filament, AMS slots, printer usage and print jobs –  
with or without Bambu Cloud, and fully compatible with both **Bambu LAN Mode** and **Klipper (Moonraker)**.

> 🇩🇪 **German version available:**  
> 👉 [README.de.md](README.de.md)

---

## 🔖 Badges

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-ready-0db7ed?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Project-Active-success)
![Platform](https://img.shields.io/badge/Platforms-Win%20%7C%20Linux%20%7C%20Unraid-blue)

---

## 🚀 Features (Current)

### ✔ Backend (FastAPI)
- Fully structured REST API
- Auto documentation: `/docs`
- `sqlite` + SQLModel ORM
- CRUD for:
  - Materials
  - Spools
- Automatic DB creation

### ✔ UI (Prototype)
- Minimal dark dashboard
- Will evolve into a full UI

### ✔ Docker
- Fully containerized  
- Works on **Unraid, Raspberry Pi, Linux, Windows**

### ✔ Integration Ready
- Bambu LAN (MQTT)
- Klipper (Moonraker)
- Manual Mode (for offline users)

---

## 🧠 Architecture Overview

