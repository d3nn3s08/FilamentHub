from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response, HTMLResponse
import subprocess
import threading
from pathlib import Path
import os
import tempfile
from uuid import uuid4
import mimetypes
import shutil


from app.routes.admin_routes import admin_required, audit, client_ip
from fastapi.templating import Jinja2Templates
from fastapi import Depends

router = APIRouter()

templates = Jinja2Templates(directory="frontend/templates")

ROOT_DIR = Path(__file__).resolve().parents[2]
_coverage_lock = threading.Lock()


@router.post("/coverage/run")
# DEV-FEATURE: Code-Coverage darf nur im Entwicklungsmodus ausgeführt werden
def run_coverage(request: Request):
    admin_required(request)
    # DEV-Mode Guard: nur erlauben, wenn FILAMENTHUB_DEV_FEATURES=="1"
    if os.environ.get("FILAMENTHUB_DEV_FEATURES") != "1":
        audit(
            "admin_coverage_blocked_production",
            {
                "ip": client_ip(request),
                "reason": "Prod block",
            },
        )
        return JSONResponse(
            {"success": False, "message": "Coverage ist ein Entwickler-Feature und im Produktivmodus deaktiviert"},
            status_code=403,
        )

    # --- Backend-Guard: pytest vorhanden? ---
    if not shutil.which("pytest"):
        audit(
            "admin_coverage_error",
            {
                "ip": client_ip(request),
                "message": "pytest nicht installiert"
            },
        )
        return JSONResponse(
            {"success": False, "message": "pytest ist nicht installiert (Coverage nicht möglich)"},
            status_code=500,
        )
    # --- Ende Guard ---

    if not _coverage_lock.acquire(blocking=False):
        return JSONResponse({"success": False, "message": "Coverage läuft bereits"}, status_code=200)
    temp_db = Path(tempfile.gettempdir()) / f"filamenthub_cov_{uuid4().hex}.db"
    try:
        cmd = ["pytest", "--cov=app", "--cov-report=html", "--ignore=Backup"]
        temp_db = Path(tempfile.gettempdir()) / f"filamenthub_cov_{uuid4().hex}.db"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT_DIR)
        env["FILAMENTHUB_DB_PATH"] = str(temp_db)
        result = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        success = result.returncode == 0
        message = "Coverage erfolgreich ausgeführt" if success else "Coverage fehlgeschlagen"
        audit(
            "admin_coverage_run",
            {
                "ip": client_ip(request),
                "success": success,
                "stdout": (result.stdout or "")[:1000],
                "stderr": (result.stderr or "")[:1000],
            },
        )
        # Wenn HTML-Report erzeugt wurde, Gesamtwert parsen und als Verlauf speichern
        try:
            index_file = ROOT_DIR / "htmlcov" / "index.html"
            if index_file.exists():
                with open(index_file, 'r', encoding='utf-8') as f:
                    html = f.read()
                import re
                m = re.search(r'Coverage report:\s*(\d+)%', html)
                overall = None
                if m:
                    overall = int(m.group(1))
                else:
                    m2 = re.search(r'coverage.*?(\d+)%', html, re.IGNORECASE)
                    if m2:
                        overall = int(m2.group(1))

                if overall is not None:
                    hist_folder = ROOT_DIR / 'data'
                    hist_folder.mkdir(parents=True, exist_ok=True)
                    hist_file = hist_folder / 'coverage_history.json'
                    import json, time
                    entry = {"ts": int(time.time()), "percent": overall}
                    try:
                        if hist_file.exists():
                            with open(hist_file, 'r', encoding='utf-8') as hf:
                                arr = json.load(hf)
                        else:
                            arr = []
                    except Exception:
                        arr = []
                    arr.append(entry)
                    arr = arr[-200:]
                    with open(hist_file, 'w', encoding='utf-8') as hf:
                        json.dump(arr, hf)
        except Exception:
            pass
        return {"success": success, "message": message}
    except subprocess.TimeoutExpired as exc:
        audit(
            "admin_coverage_timeout",
            {"ip": client_ip(request), "message": "Timeout bei Coverage", "details": str(exc)},
        )
        return {"success": False, "message": "Coverage läuft zu lange (Timeout)"}
    except Exception as exc:
        audit("admin_coverage_error", {"ip": client_ip(request), "message": str(exc)})
        return {"success": False, "message": "Coverage fehlgeschlagen"}
    finally:
        try:
            if temp_db.exists():
                temp_db.unlink()
        except Exception:
            pass
        _coverage_lock.release()


@router.get("/coverage/report")
def coverage_report(request: Request):
    """Serve the main coverage report HTML page."""
    admin_required(request)
    report_path = ROOT_DIR / "htmlcov" / "index.html"
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="Coverage noch nicht ausgeführt")
    audit("admin_coverage_report", {"ip": client_ip(request)})

    # Read and inject <base> tag to fix relative paths
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Inject <base href="/api/admin/coverage/report/"> after <head> tag
    # This makes all relative links work correctly
    content = content.replace(
        '<head>',
        '<head>\n    <base href="/api/admin/coverage/report/">'
    )

    return HTMLResponse(
        content=content,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@router.get("/coverage/history")
def coverage_history(request: Request):
    """Return stored coverage history as JSON."""
    admin_required(request)
    hist_file = ROOT_DIR / 'data' / 'coverage_history.json'
    if not hist_file.exists():
        return JSONResponse([], status_code=200)
    try:
        import json
        with open(hist_file, 'r', encoding='utf-8') as f:
            arr = json.load(f)
        return JSONResponse(arr)
    except Exception:
        return JSONResponse([], status_code=200)


@router.get("/coverage/ui")
def coverage_ui(request: Request):
    """Render a wrapper UI that shows the coverage report in an iframe and a small chart."""
    admin_required(request)
    return templates.TemplateResponse("coverage_wrapper.html", {"request": request})


@router.head("/coverage/report")
def coverage_report_head(request: Request):
    """Check if coverage report exists (used by frontend to enable/disable button)."""
    admin_required(request)
    report_path = ROOT_DIR / "htmlcov" / "index.html"
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="Coverage noch nicht ausgeführt")
    return Response(status_code=200)


@router.get("/coverage/report/{file_path:path}")
def coverage_report_file(request: Request, file_path: str):
    """Serve static files from htmlcov directory (CSS, JS, other HTML files)."""
    admin_required(request)

    # Security: prevent directory traversal
    if ".." in file_path or file_path.startswith("/"):
        raise HTTPException(status_code=403, detail="Invalid file path")

    full_path = ROOT_DIR / "htmlcov" / file_path

    if not full_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(str(full_path))
    if mime_type is None:
        mime_type = "application/octet-stream"

    return FileResponse(str(full_path), media_type=mime_type)
