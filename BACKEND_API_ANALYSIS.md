# 🔗 FilamentHub - Backend API Aufrufe (app/ Integration)

## Übersicht: Frontend → Backend Datenflusss

Der Frontend ruft kontinuierlich Daten vom **Flask-Backend** (`app/`) über **REST API Endpoints** auf.

---

## 📡 API ENDPOINTS (nach Frontend-Seite)

### 1. **NAVBAR & SETTINGS** (layout.html)
**Datei:** `navbar.js`, `settings.js`  
**Wird aufgerufen auf:** Alle Seiten (global)

```javascript
// GET: Settings abrufen
fetch("/api/settings")

// POST: Settings speichern
fetch("/api/settings", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data)
})
```

**Zweck:** User-Einstellungen (AMS-Mode, Theme, Debug-Optionen)

---

### 2. **PRINTERS SEITE** (printers.html)
**Datei:** `printers.js`  
**Wird aufgerufen auf:** GET /printers

```javascript
// GET: Alle Drucker laden
fetch("/api/printers/")

// GET: Einzelner Drucker (ID)
fetch(`/api/printers/${id}`)

// POST: Drucker-Verbindung testen
fetch(`/api/printers/${id}/test`, { method: "POST" })

// DELETE: Drucker löschen
fetch(`/api/printers/${id}`, { method: "DELETE" })
```

**Zweck:** Drucker verwalten, testen, löschen

---

### 3. **DEBUG PAGE** (debug.html)
**Dateien:** `log_viewer_controller.js`, `debug_ams.js`, `debug_pro_log.js`  
**Wird aufgerufen auf:** GET /debug

```javascript
// GET: Log-Daten abrufen
fetch('/api/debug/logs?module=app&limit=500')
fetch('/api/debug/logs?module=app&limit=200')
fetch('/api/debug/logs?module=app&limit=1000')

// GET: AMS Debug-Informationen
fetch("/api/debug/ams")
```

**Zweck:** System-Logs und Debug-Informationen für Monitoring

---

### 4. **MQTT CONNECTION** (debug.html)
**Datei:** `mqtt-connect-handler.js` (in app/static/js/)  
**Wird aufgerufen auf:** Debug Center → MQTT Tab

```javascript
// POST: MQTT Verbindung starten
fetch('/api/mqtt/runtime/connect', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ broker, port, username, password, client_id, ... })
})

// POST: MQTT Verbindung trennen
fetch('/api/mqtt/runtime/disconnect', { method: 'POST' })

// GET: MQTT Status prüfen
fetch('/api/mqtt/runtime/status')
```

**Zweck:** MQTT-Verbindungen zu 3D-Druckern managen

---

### 5. **NOTIFICATIONS** (global)
**Dateien:** `global_notifications.js`, `admin_notifications.js`  
**Wird aufgerufen auf:** Alle Seiten + Admin Panel

```javascript
// GET: Benachrichtigungsconfig laden
fetch("/api/notifications-config")

// POST: Benachrichtigungen speichern
fetch("/api/notifications-config", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(config)
})

// POST: Benachrichtigung testen/auslösen
fetch("/api/notifications-trigger", {
  method: "POST",
  body: JSON.stringify({ notification_type, ... })
})

// WebSocket: Live-Benachrichtigungen
WebSocket: ${protocol}://${window.location.host}/api/notifications/ws
```

**Zweck:** System-Benachrichtigungen verwalten

---

## 🗂️ BACKEND STRUKTUR (app/)

Die API wird wahrscheinlich in diesen Dateien definiert:

```
app/
├── __init__.py                 ← Flask App initialisierung
├── routes/
│   ├── __init__.py
│   ├── api.py                  ← API Endpoints (settings, printers, debug, mqtt, notifications)
│   ├── debug.py                ← Debug Seite Routen
│   ├── main.py                 ← Haupt-Routen (dashboard, etc.)
│   └── mqtt.py                 ← MQTT Routen
├── models/
│   ├── printer.py              ← Drucker-Modell (DB)
│   ├── settings.py             ← Einstellungen-Modell
│   └── ...
├── services/
│   ├── mqtt_service.py         ← MQTT-Logik
│   ├── printer_service.py      ← Drucker-Verwaltung
│   └── ...
└── templates/
    ├── debug.html              ← Welche JS diese Seite lädt
    ├── printers.html
    └── ...
```

---

## 📊 DATENFLUSS BEISPIEL

### Szenario: Benutzer öffnet Printers-Seite

```
1. Browser: GET /printers
   ↓
2. Flask Backend: Rendert templates/printers.html + layout.html
   ↓
3. JavaScript lädt: printers.js (weil active_page="printers")
   ↓
4. printers.js führt aus:
   fetch("/api/printers/")
   ↓
5. Backend: GET /api/printers/ → Abfrage in Datenbank
   ↓
6. Rückgabe: JSON Array mit Drucker-Objekten
   ↓
7. printers.js: Rendert Drucker in UI
```

---

## 🔍 ALLE API ENDPOINTS (ZUSAMMENFASSUNG)

| Endpoint | Method | Datei | Zweck |
|----------|--------|-------|-------|
| `/api/settings` | GET | navbar.js | Einstellungen laden |
| `/api/settings` | POST | settings.js | Einstellungen speichern |
| `/api/printers/` | GET | printers.js | Alle Drucker laden |
| `/api/printers/{id}` | GET | printers.js | Drucker-Details |
| `/api/printers/{id}/test` | POST | printers.js | Verbindung testen |
| `/api/printers/{id}` | DELETE | printers.js | Drucker löschen |
| `/api/debug/logs` | GET | log_viewer_controller.js | Logs abrufen |
| `/api/debug/ams` | GET | debug_ams.js | AMS-Debug-Info |
| `/api/mqtt/runtime/connect` | POST | mqtt-connect-handler.js | MQTT verbinden |
| `/api/mqtt/runtime/disconnect` | POST | mqtt-connect-handler.js | MQTT trennen |
| `/api/mqtt/runtime/status` | GET | mqtt-connect-handler.js | MQTT-Status |
| `/api/notifications-config` | GET | global_notifications.js | Benachrichtigungen laden |
| `/api/notifications-config` | POST | admin_notifications.js | Benachrichtigungen speichern |
| `/api/notifications-trigger` | POST | admin_notifications.js | Benachrichtigung testen |
| `/api/notifications/ws` | WebSocket | global_notifications.js | Live-Benachrichtigungen |

---

## 🚀 WEITERE MÖGLICHE ENDPOINTS (nicht sichtbar)

Diese könnten auch existieren, sind aber in den analysierten JS-Dateien nicht visible:

- `/api/materials/` - Material-Verwaltung
- `/api/spools/` - Spulen-Verwaltung
- `/api/jobs/` - Job-Verwaltung
- `/api/statistics/` - Statistiken
- `/api/ams/` - AMS-Verwaltung
- `/api/health/` - System-Health Check

---

## 📝 WICHTIGE ERKENNTNISSE

### ✅ Aktiv geladen:
- **Settings API** - auf ALLEN Seiten
- **Printers API** - auf Printers-Seite
- **Debug API** - auf Debug-Seite
- **MQTT API** - auf Debug/MQTT-Tab
- **Notifications API** - global + WebSocket

### ❌ Nicht direkt sichtbar in JS:
- `materials.js` - enthält nur Placeholder-Kommentar, keine echten API-Aufrufe
- `jobs.js` - keine sichtbaren API-Aufrufe im analysierten Code
- `dashboard.js` - nur Kommentar für zukünftige Logik
- `spools.js` - keine sichtbaren API-Aufrufe

---

## 🔗 VERKNÜPFUNG Frontend ↔ Backend

```
Frontend (JS/CSS/HTML)
    ↓
    fetch("/api/...") oder WebSocket
    ↓
Backend (Flask, app/)
    ├── routes/api.py
    ├── services/*.py
    └── models/*.py (Datenbank-Abfragen)
    ↓
    Rückgabe: JSON / Daten
    ↓
Frontend (JS rendert DOM)
```

---

## 📄 EINGEBUNDENE EXTERNE JS-DATEIEN

Diese JS-Dateien werden **nicht** im analysierten Code gefunden, könnten aber existieren:

```
/app/static/js/
├── debug.js             ← Wird geladen wenn active_page="debug"
├── mqtt-connect-handler.js ← Laden in debug.html
├── mqtt_connect.js      ← KOMMENTIERT in debug.html
└── dashboard.js         ← Wird geladen wenn active_page="dashboard"
```

