<p align="center">
  <img src="docs/logo.png" width="280" />
</p>

<h1 align="center">FilamentHub</h1>
<p align="center">Lokale Filament-Verwaltung für Bambu, Klipper & Standalone-Drucker.</p>

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-Ready-0db7ed?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platforms-Win%20%7C%20Linux%20%7C%20Unraid-blue)
![Status](https://img.shields.io/badge/Status-Beta_v1.6-orange)

![Bambu](https://img.shields.io/badge/Bambu-LAN%20%26%20Cloud-green)
![Klipper](https://img.shields.io/badge/Klipper-Supported-purple)

> **English version:** [ANLEITUNG/README.en.md](ANLEITUNG/README.en.md)

---

## Features

### Druckerverwaltung
- Übersicht aller registrierten Drucker
- Live-Status, Temperaturen, aktueller Druckauftrag
- Druckhistorie, Verbrauchsdaten, MQTT für Bambu (LAN)

### Filamentverwaltung
- Bestand mit Hersteller, Farbe, Material, Restgewicht
- Letzter Einsatz pro Drucker, Verbrauchsdaten
- Optionale Warnungen bei niedrigem Bestand

### Statistiken & Analysen
- Druckzeit pro Drucker
- Filamentverbrauch & Kostenschätzung
- Tages-/Monatsübersichten

### Web-UI
- Strukturierte Navigation (Dashboard / Drucker / Filament / System)
- Dark UI (Unraid-inspiriert)

### Datenbank & Backups
- SQLite als integrierte lokale Datenbank
- Backup-Funktion im Debug-Tab (DB + Logs als ZIP)
- DB-Wartung: VACUUM, Tabellenansicht, ad-hoc SELECT

---

## Installation (Docker — empfohlen für NAS)

```bash
cp .env.example .env
# .env öffnen und ADMIN_PASSWORD_HASH eintragen:
# python -c "import bcrypt; print(bcrypt.hashpw(b'DEIN_PASSWORT', bcrypt.gensalt()).decode())"

docker compose up -d
```

Danach erreichbar unter: `http://YOUR_NAS_IP:8085`

---

## Installation (Python direkt)

```bash
python -m venv .venv
# Windows:
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python run.py
# Linux/Mac:
source .venv/bin/activate && pip install -r requirements.txt && python run.py
```

---

## Unterstützte Drucker

| Typ | Verbindung |
|---|---|
| Bambu Lab (X1C, P1S, A1, ...) | MQTT LAN oder Bambu Cloud |
| Klipper / Moonraker | HTTP API |
| Standalone | Manuell |

---

## Konfiguration

| Datei | Zweck |
|---|---|
| `.env` | Admin-Passwort, App-Version, Dev-Flags |
| `config.yaml` | Logging, Server-Port, Integrationsmode |

---

## Lizenz

MIT — siehe [LICENSE.md](LICENSE.md)
