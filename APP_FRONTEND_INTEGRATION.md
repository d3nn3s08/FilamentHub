# 🔗 FilamentHub - Backend (app/) ↔ Frontend (frontend/) Integration

## 🎯 ÜBERSICHT: Wie `app/` auf `frontend/` zugreift

Das Flask/FastAPI Backend in `app/` greift auf das `frontend/` Verzeichnis an **3 Stellen** zu:

### **1. STATIC FILES MOUNTING** (main.py, Zeile 138-139)
### **2. TEMPLATE RENDERING** (main.py, Zeile 140)
### **3. ROUTE HANDLERS** (Verschiedene Routes)

---

## 📌 DETAILLIERTE ANALYSE

### **1️⃣ STATIC FILES MOUNTING** (main.py)

```python
# Zeile 138-139 in app/main.py
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/frontend", StaticFiles(directory="frontend/static"), name="frontend_static")
```

**Was das bedeutet:**
- **`/static`** → Zeigt auf `app/static/` (Backend-spezifische Assets)
- **`/frontend`** → Zeigt auf `frontend/static/` (Frontend-Assets)

**Zugriff im Browser:**
```
GET /frontend/css/main.css
    ↓
Lädt: frontend/static/css/main.css

GET /frontend/js/navbar.js
    ↓
Lädt: frontend/static/js/navbar.js
```

---

### **2️⃣ TEMPLATE RENDERING** (main.py)

```python
# Zeile 140 in app/main.py
templates = Jinja2Templates(directory="frontend/templates")
```

**Was das bedeutet:**
- FastAPI/Jinja2 sucht Templates in `frontend/templates/`
- Nicht in `app/templates/`!

---

### **3️⃣ ROUTE HANDLERS** (main.py, Zeilen 178-297)

Alle Seiten-Routes laden Templates aus `frontend/templates/`:

```python
# Zeile 182-188: Dashboard
@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        'dashboard.html',           # ← frontend/templates/dashboard.html
        {
            'request': request,
            'title': 'FilamentHub - Dashboard',
            'active_page': 'dashboard'
        },
    )

# Zeile 194-200: Materialien
@app.get('/materials', response_class=HTMLResponse)
async def materials_page(request: Request):
    return templates.TemplateResponse(
        'materials.html',           # ← frontend/templates/materials.html
        { ... }
    )

# Zeile 206-212: Spulen
@app.get('/spools', response_class=HTMLResponse)
async def spools_page(request: Request):
    return templates.TemplateResponse(
        'spools.html',              # ← frontend/templates/spools.html
        { ... }
    )

# Zeile 218-224: Drucker
@app.get('/printers', response_class=HTMLResponse)
async def printers_page(request: Request):
    return templates.TemplateResponse(
        'printers.html',            # ← frontend/templates/printers.html
        { ... }
    )

# Zeile 230-236: Jobs
@app.get('/jobs', response_class=HTMLResponse)
async def jobs_page(request: Request):
    return templates.TemplateResponse(
        'jobs.html',                # ← frontend/templates/jobs.html
        { ... }
    )

# Zeile 242-248: Statistiken
@app.get('/statistics', response_class=HTMLResponse)
async def statistics_page(request: Request):
    return templates.TemplateResponse(
        'statistics.html',          # ← frontend/templates/statistics.html
        { ... }
    )

# Zeile 254-260: Settings
@app.get('/settings', response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(
        'settings.html',            # ← frontend/templates/settings.html
        { ... }
    )
```

**AUSNAHMEN (laden aus `app/templates/`):**

```python
# Zeile 266-268: Logs
@app.get('/logs', response_class=HTMLResponse)
async def logs_page(request: Request):
    logs_templates = Jinja2Templates(directory='app/templates')  # ← app/templates!
    return logs_templates.TemplateResponse('logs.html', { ... })

# Zeile 276-284: Debug
@app.get('/debug', response_class=HTMLResponse)
async def debug_page(request: Request):
    debug_templates = Jinja2Templates(directory='app/templates')  # ← app/templates!
    printers = []
    try:
        with Session(engine) as session:
            printers = session.exec(select(Printer)).all()
    except Exception:
        printers = []
    return debug_templates.TemplateResponse(
        'debug.html',
        {'request': request, 'title': 'FilamentHub Debug Center', 'active_page': 'debug', 'printers': printers},
    )

# Zeile 293-297: AMS Help
@app.get('/ams-help', response_class=HTMLResponse)
async def ams_help_page(request: Request):
    help_templates = Jinja2Templates(directory='app/templates')  # ← app/templates!
    return help_templates.TemplateResponse(
        'ams_help.html',
        {'request': request, 'title': 'AMS Helper'},
    )
```

---

### **4️⃣ WEITERE ZUGRIFFE AUS ROUTE-DATEIEN**

#### **admin_routes.py:**
```python
# Zeile 27
templates = Jinja2Templates(directory="frontend/templates")

# Laden: admin_login.html, admin_panel.html, admin_notifications.html
return templates.TemplateResponse("admin_login.html", { ... })
return templates.TemplateResponse("admin_panel.html", { ... })
return templates.TemplateResponse("admin_notifications.html", { ... })
```

#### **debug_ams_routes.py:**
```python
# Zeile 10
templates = Jinja2Templates(directory="frontend/templates")

# Laden: debug_ams.html
return templates.TemplateResponse( ... )
```

#### **debug_routes.py:**
```python
# Zeile 149-150
"templates": os.path.abspath("frontend/templates"),
"static": os.path.abspath("app/static"),
```

---

## 📊 DATENFLUSS DIAGRAMM

```
┌─────────────────────────────────────┐
│         Browser/Client              │
└──────────────────┬──────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │   GET /        │
         │   GET /materials
         │   GET /printers │
         │   GET /debug    │
         │   etc.          │
         └────────┬────────┘
                  │
                  ▼
    ┌─────────────────────────────┐
    │   FastAPI Backend (app/)   │
    │  app/main.py               │
    │  app/routes/*.py           │
    └──────────┬──────────────────┘
               │
         ┌─────┴─────┐
         │           │
         ▼           ▼
    ┌─────────┐  ┌──────────────────────────┐
    │ Load    │  │ Mount Static Files       │
    │Template │  │                          │
    │ from    │  │ /static → app/static/    │
    │frontend/│  │ /frontend → frontend/static/
    │template │  │                          │
    │s/       │  └──────────────────────────┘
    │         │
    │ + Jinja │
    │ Context │
    │ (active │
    │ _page)  │
    └────┬────┘
         │
         ▼
    ┌─────────────────────────────┐
    │   Rendered HTML             │
    │   + CSS Links (/frontend/)  │
    │   + JS Links (/frontend/)   │
    └──────────┬──────────────────┘
               │
               ▼
         ┌──────────────────────────┐
         │ Browser lädt Assets:     │
         │ GET /frontend/css/*.css  │
         │ GET /frontend/js/*.js    │
         └──────────────────────────┘
```

---

## 📋 ZUSAMMENFASSUNG: Was `app/` auf `frontend/` zugreift

| Komponente | Datei | Zugriff | Beschreibung |
|-----------|-------|--------|-------------|
| **Static Mount** | `app/main.py:139` | `/frontend` → `frontend/static/` | CSS, JS, Bilder |
| **Template Dir** | `app/main.py:140` | `frontend/templates/` | Dashboard, Materials, etc. |
| **Admin Routes** | `admin_routes.py:27` | `frontend/templates/` | Admin Panel Templates |
| **AMS Routes** | `debug_ams_routes.py:10` | `frontend/templates/` | Debug AMS Template |
| **Debug Routes** | `debug_routes.py:149` | `frontend/templates/` | Debug Utilities |
| **Home Route** | `app/main.py:182` | `dashboard.html` | Dashboard Template |
| **Materials Route** | `app/main.py:194` | `materials.html` | Materials Template |
| **Spools Route** | `app/main.py:206` | `spools.html` | Spools Template |
| **Printers Route** | `app/main.py:218` | `printers.html` | Printers Template |
| **Jobs Route** | `app/main.py:230` | `jobs.html` | Jobs Template |
| **Statistics Route** | `app/main.py:242` | `statistics.html` | Statistics Template |
| **Settings Route** | `app/main.py:254` | `settings.html` | Settings Template |

---

## ⚠️ TEMPLATES SPLIT (wichtig!)

```
frontend/templates/          ← Hauptvorlagen (aus app/main.py geladen)
├── dashboard.html           ✅ Geladen von app/
├── materials.html           ✅ Geladen von app/
├── spools.html             ✅ Geladen von app/
├── printers.html           ✅ Geladen von app/
├── jobs.html               ✅ Geladen von app/
├── statistics.html         ✅ Geladen von app/
├── settings.html           ✅ Geladen von app/
├── layout.html             ✅ Geladen von app/ (parent template)
├── sidebar.html            ✅ Geladen von app/ (included)
├── admin_login.html        ✅ Geladen von app/ (admin_routes.py)
├── admin_panel.html        ✅ Geladen von app/ (admin_routes.py)
├── admin_notifications.html ✅ Geladen von app/ (admin_routes.py)
└── index.html              ✅ Geladen von app/

app/templates/              ← Spezielle Debug-Templates
├── logs.html               ✅ Geladen von app/main.py (NICHT aus frontend/!)
├── debug.html              ✅ Geladen von app/main.py (NICHT aus frontend/!)
└── ams_help.html           ✅ Geladen von app/main.py (NICHT aus frontend/!)
```

---

## 🔌 API ENDPOINTS (auch in app/)

Diese sind **nicht** im `frontend/` Verzeichnis, aber werden von Frontend-JS aufgerufen:

```
Frontend JS → fetch()
    ↓
/api/settings              ← settings_router
/api/printers/             ← printers_router
/api/debug/logs            ← debug_log_routes
/api/debug/ams             ← debug_ams_router
/api/mqtt/runtime/*        ← mqtt_runtime_routes
/api/notifications-*       ← notification_router
```

---

## 📝 WICHTIGE ERKENNTNISSE

### ✅ **frontend/templates/** wird geladen für:
- Alle **Hauptseiten** (Dashboard, Materials, Printers, etc.)
- **Admin Panel**
- **Sidebar, Layout**

### ✅ **frontend/static/** wird gemountet als `/frontend/` für:
- **CSS-Dateien** (main.css, debug_tabs.css, etc.)
- **JavaScript-Dateien** (navbar.js, log_viewer_renderer.js, etc.)
- **Bilder** (X1C.png, x1c.svg)

### ❌ **app/templates/** wird DIREKT geladen für:
- `logs.html`
- `debug.html` (NICHT `frontend/templates/debug.html`)
- `ams_help.html`

### 🔗 **Wichtige Kontextvariablen** (aus app/ an Templates):
```python
{
    'request': request,
    'title': 'Page Title',
    'active_page': 'dashboard|materials|printers|etc.',
    'printers': [...] # Für debug.html
}
```

Diese Variablen werden in Templates verwendet, z.B.:
```html
<!-- layout.html -->
<body class="page" data-active-page="{{ active_page|default('dashboard') }}">
```

