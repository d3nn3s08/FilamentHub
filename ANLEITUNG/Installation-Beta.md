# 🧪 Installation – FilamentHub Public Beta

Diese Anleitung beschreibt **ausschließlich die Installation der Public Beta** von FilamentHub.  
Sie richtet sich an **technisch versierte Nutzer und Early Adopter**.

⚠️ **Wichtiger Hinweis**  
Dies ist eine **Beta-Version**. APIs, Datenmodelle und UI können sich ändern.  
Die Beta ist **nicht** für produktionskritische Systeme gedacht.

---

## 🎯 Ziel der Beta

- Testen der aktuellen Stabilitäts- und Architekturänderungen
- Validierung von:
  - automatischen Datenbank-Migrationen
  - Job- & Filament-Tracking
  - Server-Restart-Resilienz
- Feedback sammeln, bevor ein Stable-Release erfolgt

---

## 📦 Voraussetzungen

**Pflicht**
- Docker
- Docker Compose (v2)
- Git

**Empfohlen**
- Linux / Unraid / Raspberry Pi OS
- Grundkenntnisse Docker & CLI

---

## 📁 Empfohlene Verzeichnisstruktur

Die Beta sollte **immer getrennt** von einer stabilen Installation laufen.

```text
/opt/filamenthub/
└── beta/
    ├── docker-compose.yml
    ├── .env
    ├── data/
    └── logs/
```

➡️ **Nie Stable- und Beta-Daten mischen.**

---

## 🚀 Installation (Docker Compose – empfohlen)

### 1️⃣ Repository klonen und auf Beta wechseln

```bash
git clone https://github.com/d3nn3s08/FilamentHub.git
cd FilamentHub
git checkout beta
git pull
```

### 3️⃣ Docker Image bauen

```bash
docker build -t filamenthub:beta .
```

💡 Auf Raspberry Pi kann der Build **10–30 Minuten** dauern  
(ARM-Architektur + native Python-Wheels).

---

## 🔧 WICHTIG: `docker-compose.yml` für die Beta anpassen (Pflicht!)

⚠️ **Die mitgelieferte `docker-compose.yml` ist häufig auf eine bestehende Stable-Installation angepasst.**  
👉 **Für die Beta MUSS sie geprüft und ggf. angepasst werden**, sonst startet der Container nicht oder überschreibt bestehende Daten.

---

### ✅ Zwingend zu prüfen und anzupassen

#### 1️⃣ Image-Name
Wenn du das Beta-Image lokal gebaut hast:

```bash
docker build -t filamenthub:beta .
```

muss in der `docker-compose.yml` stehen:

```yaml
image: filamenthub:beta
```

❌ **Nicht**
```yaml
image: filamenthub:latest
```

---

#### 2️⃣ Container-Name (eindeutig!)
Der Container-Name darf **nicht** mit einer bestehenden Instanz kollidieren.

```yaml
container_name: filamenthub-beta
```

---

#### 3️⃣ Volumes strikt trennen
Die Beta darf **niemals** die Daten einer Stable-Version verwenden.

**Lokal / Raspberry Pi**
```yaml
volumes:
  - ./data:/app/data
  - ./logs:/app/logs
```

**Unraid**
```yaml
volumes:
  - /mnt/user/appdata/filamenthub-beta/data:/app/data
  - /mnt/user/appdata/filamenthub-beta/logs:/app/logs
```

❌ **Nicht**
```yaml
/mnt/user/appdata/filamenthub/data:/app/data
```

---

#### 4️⃣ Netzwerk & Port
- Läuft die Beta **auf einem eigenen Host** (z. B. Raspberry Pi):
  ```yaml
  network_mode: host
  ```
  → Port `8085` kann gleich bleiben

- Läuft Stable **und** Beta auf **demselben Host**:
  - `network_mode: host` **nicht verwenden**
  - explizite Ports setzen, z. B.:
    ```yaml
    ports:
      - "8086:8085"
    ```

---

### ✅ Minimal-Beispiel (beta-tauglich)

```yaml
services:
  filamenthub:
    container_name: filamenthub-beta
    image: filamenthub:beta
    restart: unless-stopped
    network_mode: host

    env_file:
      - .env

    environment:
      FILAMENTHUB_DB_PATH: /app/data/filamenthub.db
      PYTHONPATH: /app

    volumes:
      - ./data:/app/data
      - ./logs:/app/logs

    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8085/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

    entrypoint: ["./entrypoint.sh"]
```

---

### 🔁 Nach Änderungen an der `docker-compose.yml`

```bash
docker compose down
docker compose up -d
```

---

## 📊 Logs & Start prüfen

```bash
docker compose logs -f
```

Ein erfolgreicher Start zeigt u. a.:

- Initialisierung der Datenbank
- Alembic Migrationen (`upgrade head`)
- `Application startup complete`
- `Uvicorn running on 0.0.0.0:8085`

---

## 🌐 Weboberfläche

```
http://<HOST-IP>:8085
```

Beispiel:
```
http://192.168.178.20:8085
```

---

## 🧪 Empfohlene Tests

- Admin-Login testen
- Container neu starten → Login erneut testen
- DB-Persistenz prüfen
- Healthcheck:
  ```
  http://<HOST-IP>:8085/health
  ```

---

## 🧯 Troubleshooting


### Container startet nicht
- Image-Name (`filamenthub:beta`) prüfen
- Volumes prüfen
- Container-Name eindeutig setzen
- Logs prüfen:
  ```bash
  docker compose logs -f
  ```

---

## ⚠️ Wichtige Beta-Hinweise

- Keine Garantie für Datenkompatibilität zu späteren Versionen
- Backups der `data/` dringend empfohlen
- Feedback & Issues sind ausdrücklich erwünscht

👉 GitHub Issues:  
https://github.com/d3nn3s08/FilamentHub/issues

---

## 🧭 Nächste Schritte

- Beta intensiv testen
- Feedback geben
- Vorbereitung auf Stable-Release

Danke fürs Testen der **FilamentHub Public Beta** 🚀
