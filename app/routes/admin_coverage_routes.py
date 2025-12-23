from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
import subprocess
import threading
from pathlib import Path
import os
import tempfile
from uuid import uuid4

from app.routes.admin_routes import admin_required, audit, client_ip

router = APIRouter()

ROOT_DIR = Path(__file__).resolve().parents[2]
_coverage_lock = threading.Lock()


@router.post("/coverage/run")
def run_coverage(request: Request):
    admin_required(request)
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
    admin_required(request)
    report_path = ROOT_DIR / "htmlcov" / "index.html"
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="Coverage noch nicht ausgeführt")
    audit("admin_coverage_report", {"ip": client_ip(request)})
    return FileResponse(str(report_path), media_type="text/html", filename="index.html")


@router.head("/coverage/report")
def coverage_report_head(request: Request):
    admin_required(request)
    report_path = ROOT_DIR / "htmlcov" / "index.html"
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="Coverage noch nicht ausgeführt")
    audit("admin_coverage_report", {"ip": client_ip(request)})
    return FileResponse(str(report_path), media_type="text/html", filename="index.html")
