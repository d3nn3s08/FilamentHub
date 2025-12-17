# 📊 FilamentHub - Asset Loading Analysis (CSS/JS Verweise)

## 1. HAUPTEINSTIEGSPUNKT: `layout.html`
**Pfad:** `app/templates/layout.html` (Basis-Template für alle Seiten)

### CSS-Verweise in layout.html:
```html
<link rel="stylesheet" href="{{ url_for('frontend_static', path='css/main.css') }}">
  → Lädt: /frontend/css/main.css (Hauptstilsheet)

<link rel="stylesheet" href="{{ url_for('static', path='debug.css') }}">
  → Lädt: /static/debug.css (Debug-spezifischer CSS)

{% block extra_styles %}{% endblock %}
  → Platzhalter für seiten-spezifische Stylesheets (wird in Kind-Templates überschrieben)
```

### JS-Verweise in layout.html:
```html
<!-- GLOBAL SCRIPTS (auf allen Seiten aktiv) -->
<script src="/frontend/js/global_notifications.js"></script>
<script src="/frontend/js/navbar.js"></script>

<!-- PAGE-SPECIFIC SCRIPTS (Bedingt geladen basierend auf active_page) -->
{% if active_page == "debug" %}
  <script src="/static/debug.js"></script>
{% endif %}

{% if active_page == "dashboard" %}
  <script src="/static/dashboard.js"></script>
{% endif %}

{% if active_page == "materials" %}
  <script src="/static/materials.js"></script>
{% endif %}

{% if active_page == "spools" %}
  <script src="/static/spools.js"></script>
{% endif %}

{% if active_page == "printers" %}
  <script src="/static/printers.js"></script>
{% endif %}

{% block scripts %}{% endblock %}
  → Platzhalter für seiten-spezifische Scripts
```

---

## 2. DEBUG SEITE: `debug.html`
**Pfad:** `app/templates/debug.html` (Debug Center)

### CSS-Verweise im `{% block extra_styles %}`:
```html
<link rel="stylesheet" href="/frontend/css/debug_tabs.css">
<link rel="stylesheet" href="/frontend/css/log_viewer.css">
<link rel="stylesheet" href="{{ url_for('static', filename='css/debug-theme.css') }}">
```

**Zugeladene Styles:**
- `/frontend/css/debug_tabs.css` - Tab Navigation Styling
- `/frontend/css/log_viewer.css` - Log Viewer UI Styling
- `/static/css/debug-theme.css` - Debug spezifisches Theme

### JS-Verweise im `{% block extra_styles %}`:
```html
<script src="/frontend/js/log_viewer_renderer.js"></script>
<script src="/frontend/js/log_viewer_controller.js"></script>
```

### JS-Verweise am Ende der Seite:
```html
<!-- Hauptinline-Scripts in <script>...</script> Blöcken -->
<!-- Zeilen 454-909: Komplexe JavaScript-Logik inline -->

<!-- Auskommentiert (aktuell nicht geladen):
<script src="/static/js/mqtt_connect.js"></script>
-->

<!-- Aktuelle externe Scripts: -->
<script src="/static/js/mqtt-connect-handler.js"></script>

<!-- Weitere Inline-Scripts in <script>...</script> Blöcken -->
```

**In layout.html wird dann zusätzlich geladen (weil active_page == "debug"):**
```html
<script src="/static/debug.js"></script>
```

---

## 3. LOGS SEITE: `logs.html`
**Pfad:** `app/templates/logs.html`

### CSS:
```html
<link rel="stylesheet" href="/static/logs.css">
```

### JS:
```html
<script src="/static/logs.js"></script>
```

---

## 4. ASSET LOADING FLOW (Übersicht)

### Szenario A: Benutzer navigiert zu Dashboard
```
1. Browser lädt: GET /
2. Backend rendert layout.html + dashboard.html
3. Geladene Assets:
   
   CSS:
   - /frontend/css/main.css (global, aus layout.html)
   - /static/debug.css (global, aus layout.html)
   - [weitere CSS aus dashboard.html's {% block extra_styles %}]
   
   JS (Global):
   - /frontend/js/global_notifications.js
   - /frontend/js/navbar.js
   
   JS (Page-specific, weil active_page="dashboard"):
   - /static/debug.js
   - /static/dashboard.js
```

### Szenario B: Benutzer navigiert zu Debug Center
```
1. Browser lädt: GET /debug
2. Backend rendert layout.html + debug.html
3. Geladene Assets:

   CSS:
   - /frontend/css/main.css (global)
   - /static/debug.css (global)
   - /frontend/css/debug_tabs.css (aus debug.html's extra_styles)
   - /frontend/css/log_viewer.css (aus debug.html's extra_styles)
   - /static/css/debug-theme.css (aus debug.html's extra_styles)
   
   JS (Global):
   - /frontend/js/global_notifications.js
   - /frontend/js/navbar.js
   
   JS (Page-specific, weil active_page="debug"):
   - /static/debug.js
   
   JS (aus debug.html's extra_styles block):
   - /frontend/js/log_viewer_renderer.js
   - /frontend/js/log_viewer_controller.js
   
   JS (aus {% block scripts %} in debug.html):
   - /static/js/mqtt-connect-handler.js
   - [Inline-Scripts in <script>...</script> Tags]
```

---

## 5. VERZEICHNIS STRUKTUR & MAPPING

```
/frontend/
├── css/
│   ├── main.css               ← Geladen von: layout.html (global)
│   ├── debug_tabs.css         ← Geladen von: debug.html
│   ├── debug_ams.css          ← (aktuell nicht in debug.html eingebunden)
│   ├── log_viewer.css         ← Geladen von: debug.html
│   ├── global_alerts.css      ← (aktuell nicht automatisch geladen)
│   └── printers.css           ← (seiten-spezifisch)
│
└── js/
    ├── global_notifications.js  ← Geladen von: layout.html (global)
    ├── navbar.js               ← Geladen von: layout.html (global)
    ├── log_viewer_renderer.js  ← Geladen von: debug.html
    ├── log_viewer_controller.js ← Geladen von: debug.html
    ├── log_viewer_autoload.js  ← (nicht in debug.html eingebunden)
    ├── log_viewer_state.js     ← (nicht in debug.html eingebunden)
    ├── mqtt_connect.js         ← (KOMMENTIERT in debug.html)
    └── debug_ams.js            ← (nicht in debug.html eingebunden)

/static/
├── css/
│   └── debug.css              ← Geladen von: layout.html (global)
│   └── debug-theme.css        ← Geladen von: debug.html
│
├── js/
│   ├── debug.js               ← Geladen von: layout.html (wenn active_page="debug")
│   ├── dashboard.js           ← Geladen von: layout.html (wenn active_page="dashboard")
│   ├── materials.js           ← Geladen von: layout.html (wenn active_page="materials")
│   ├── spools.js              ← Geladen von: layout.html (wenn active_page="spools")
│   ├── printers.js            ← Geladen von: layout.html (wenn active_page="printers")
│   └── mqtt-connect-handler.js ← Geladen von: debug.html
│
└── logs.css, logs.js          ← Geladen von: logs.html
```

---

## 6. DETAILLIERTER VERGLEICH: /frontend/ vs /static/

| Verzeichnis | Pfad in HTML | Funktion | Ladezeit |
|---|---|---|---|
| `/frontend/` | `/frontend/js/...` | Globale Komponenten, Utilities | **Immer geladen** |
| `/frontend/` | `/frontend/css/...` | Globale & gemeinsame Styles | **Immer geladen** |
| `/static/` | `/static/...` (direkt) | Page-spezifische Assets | **Bedingt** ({% if %}) |
| `/static/` | `{{ url_for('static', ...) }}` | Flask-basierte URL-Generierung | **Dynamisch** |

---

## 7. TEMPLATE VERERBUNG & ASSET FLOW

```
layout.html (Basis-Template)
├── Lädt: main.css, debug.css, global_notifications.js, navbar.js
├── {% block extra_styles %} (wird in Kind-Templates überschrieben)
├── {% block content %} (wird in Kind-Templates überschrieben)
├── Konditionale Page-specific Scripts ({% if active_page == ... %})
├── {% block scripts %} (wird in Kind-Templates überschrieben)
└── {% block extra_scripts %} (wird in Kind-Templates überschrieben)

    ↓ Wird erweitert durch:

debug.html (Kind-Template)
├── {% block extra_styles %} → Lädt: debug_tabs.css, log_viewer.css, debug-theme.css
├── {% block content %} → HTML/Inline-Styles für Debug-UI
├── {% block scripts %} → Lädt: log_viewer_renderer.js, log_viewer_controller.js, mqtt-connect-handler.js
└── Inline-JavaScript (direkt in <script>...</script> Tags)
```

---

## 8. AKTUELLE ASSET PROBLEME/NOTIZEN

### ❌ Nicht geladen, aber existiert:
- `/frontend/js/log_viewer_autoload.js` - Existiert, aber wird nicht eingebunden
- `/frontend/js/log_viewer_state.js` - Existiert, aber wird nicht eingebunden
- `/frontend/js/debug_ams.js` - Existiert, aber wird nicht eingebunden
- `/frontend/css/debug_ams.css` - Existiert, aber wird nicht eingebunden
- `/frontend/css/global_alerts.css` - Existiert, aber wird nicht eingebunden

### ⚠️ Kommentiert/Deaktiviert:
```html
<!-- In debug.html, Zeile ~2026: -->
<!-- <script src="/static/js/mqtt_connect.js"></script> -->
→ Wird nicht geladen, stattdessen mqtt-connect-handler.js
```

### ✅ Effektiv geladen für Debug-Seite:
```
Global (layout.html):
- main.css
- debug.css
- global_notifications.js
- navbar.js
- debug.js (page-specific)

Debug-spezifisch (debug.html):
- debug_tabs.css
- log_viewer.css
- debug-theme.css
- log_viewer_renderer.js
- log_viewer_controller.js
- mqtt-connect-handler.js
- Mehrere Inline-Scripts
```

---

## 9. URL_FOR() vs. DIREKTE PFADE

### Flask-Funktion `url_for()`:
```html
<!-- Generiert dynamische URLs basierend auf Flask-Konfiguration -->
{{ url_for('frontend_static', path='css/main.css') }}
  → Generiert: /frontend/css/main.css

{{ url_for('static', filename='css/debug-theme.css') }}
  → Generiert: /static/css/debug-theme.css

{{ url_for('static', path='debug.css') }}
  → Generiert: /static/debug.css
```

### Direkte Pfade:
```html
<!-- Hart-codierte Pfade (nicht flexibel) -->
<script src="/frontend/js/log_viewer_renderer.js"></script>
<link rel="stylesheet" href="/frontend/css/debug_tabs.css">
<script src="/static/debug.js"></script>
```

**Empfehlung:** `url_for()` verwenden für Portabilität und Konfigurierbarkeit.

---

## 10. ZUSAMMENFASSUNG FÜR ENTWICKLER

| Aktion | Wo hinzufügen? | Welche Datei? |
|---|---|---|
| **Globales CSS** | `layout.html` `<head>` Block | `/frontend/css/*.css` |
| **Globales JS** | `layout.html` `<script>` am Ende | `/frontend/js/*.js` |
| **Debug-spezifisches CSS** | `debug.html` `{% block extra_styles %}` | `/frontend/css/debug_*.css` |
| **Debug-spezifisches JS** | `debug.html` `{% block scripts %}` | `/static/js/*.js` |
| **Seiten-spezifisches CSS** | `dashboard.html` (etc.) `{% block extra_styles %}` | `/static/css/*.css` |
| **Seiten-spezifisches JS** | `layout.html` Konditionale | `/static/*.js` |

