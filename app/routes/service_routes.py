"""
Service Control Routes
Server Management, Docker, Dependencies, Tests
"""
import os
import sys
import subprocess
import psutil
import zipfile
from datetime import datetime
import tempfile
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/services", tags=["Service Control"])


# -----------------------------
# MODELS
# -----------------------------
class CommandResult(BaseModel):
    success: bool
    message: str
    output: Optional[str] = None
    exit_code: Optional[int] = None


# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def get_project_root():
    """Gibt das Projekt-Root-Verzeichnis zurück"""
    return os.getcwd()


def get_python_executable():
    """Gibt den Python-Pfad zurück"""
    return sys.executable


def make_test_db_path() -> str:
    """Erstellt einen eindeutigen Pfad für die Test-DB im System-Temp-Ordner.

    Vermeidet Locks auf gemeinsam genutzten Volumes (z.B. SMB/NFS) indem
    temporäre DB-Dateien pro Testlauf im OS-Temp-Verzeichnis angelegt werden.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return os.path.join(tempfile.gettempdir(), f"filamenthub_test_{ts}.db")


def run_command(command: str, cwd: Optional[str] = None, shell: bool = True, env: Optional[dict] = None) -> CommandResult:
    """Führt einen Command aus und gibt das Ergebnis zurück
    
    Args:
        command: Der auszuführende Befehl
        cwd: Working directory
        shell: Shell-Modus aktivieren
        env: Optionale Umgebungsvariablen (werden mit os.environ gemerged)
    """
    try:
        # Merge custom env with system env
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=True,
            text=True,
            cwd=cwd or get_project_root(),
            env=run_env,
            timeout=60
        )
        
        return CommandResult(
            success=result.returncode == 0,
            message="Erfolgreich ausgeführt" if result.returncode == 0 else "Fehler beim Ausführen",
            output=result.stdout + result.stderr,
            exit_code=result.returncode
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            success=False,
            message="Command Timeout (>60s)",
            output="Der Befehl hat zu lange gedauert"
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Fehler: {str(e)}",
            output=None
        )


def create_test_response(status: str, message: str, details: Optional[str] = None) -> dict:
    """Erstellt standardisiertes Test-Response-Format
    
    Args:
        status: 'ok', 'fail', oder 'blocked'
        message: Menschlich lesbare Kurzmeldung
        details: Optionale technische Details
    
    Returns:
        Standardisiertes Response-Dict
    """
    response = {
        "status": status,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }
    if details:
        response["details"] = details
    return response


# -----------------------------
# PROCESS INFO
# -----------------------------
@router.get("/process/info")
def get_process_info():
    """Gibt Informationen über den aktuellen Prozess zurück"""
    process = psutil.Process()
    
    return {
        "pid": process.pid,
        "name": process.name(),
        "status": process.status(),
        "create_time": process.create_time(),
        "cpu_percent": process.cpu_percent(interval=0.1),
        "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
        "num_threads": process.num_threads(),
        "python_executable": get_python_executable(),
        "python_version": sys.version
    }


@router.get("/process/list")
def list_python_processes():
    """Listet alle Python-Prozesse auf"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
        try:
            if 'python' in proc.info['name'].lower():
                processes.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "memory_mb": round(proc.info['memory_info'].rss / 1024 / 1024, 2),
                    "cmdline": ' '.join(proc.info['cmdline'][:3]) if proc.info['cmdline'] else ''
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return {"processes": processes, "count": len(processes)}


# -----------------------------
# DEPENDENCIES
# -----------------------------
@router.post("/dependencies/install")
async def install_dependencies():
    """Installiert Dependencies aus requirements.txt"""
    python = get_python_executable()
    command = f'"{python}" -m pip install -r requirements.txt'
    
    result = run_command(command)
    return result


@router.post("/dependencies/update")
async def update_dependency(package: str):
    """Aktualisiert ein einzelnes Package"""
    python = get_python_executable()
    command = f'"{python}" -m pip install --upgrade {package}'
    
    result = run_command(command)
    return result


@router.get("/dependencies/list")
def list_dependencies():
    """Listet alle installierten Packages auf"""
    python = get_python_executable()
    command = f'"{python}" -m pip list --format=json'
    
    result = run_command(command)
    
    if result.success and result.output:
        import json
        try:
            packages = json.loads(result.output)
            return {"packages": packages, "count": len(packages)}
        except:
            return {"packages": [], "count": 0}
    
    return {"packages": [], "count": 0}


@router.get("/dependencies/outdated")
def list_outdated_dependencies():
    """Listet alle veralteten Packages auf"""
    python = get_python_executable()
    command = f'"{python}" -m pip list --outdated --format=json'
    
    result = run_command(command)
    
    if result.success and result.output:
        import json
        try:
            packages = json.loads(result.output)
            return {
                "packages": packages, 
                "count": len(packages),
                "has_updates": len(packages) > 0
            }
        except:
            return {"packages": [], "count": 0, "has_updates": False}
    
    return {"packages": [], "count": 0, "has_updates": False}


@router.post("/dependencies/update-all")
async def update_all_dependencies():
    """Aktualisiert alle Packages auf die neueste Version"""
    python = get_python_executable()
    
    # Erst outdated packages abrufen
    outdated_result = run_command(f'"{python}" -m pip list --outdated --format=json')
    
    if not outdated_result.success or not outdated_result.output:
        return CommandResult(
            success=False,
            message="Konnte veraltete Packages nicht ermitteln"
        )
    
    import json
    try:
        outdated = json.loads(outdated_result.output)
        if len(outdated) == 0:
            return CommandResult(
                success=True,
                message="Alle Packages sind bereits aktuell!"
            )
        
        # Alle outdated packages updaten
        package_names = [pkg['name'] for pkg in outdated]
        packages_str = ' '.join(package_names)
        command = f'"{python}" -m pip install --upgrade {packages_str}'
        
        result = run_command(command)
        return result
        
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"Fehler beim Update: {str(e)}"
        )


# -----------------------------
# TESTS
# -----------------------------
# Mini-Test-Status-API
# Alle Test-Endpunkte liefern ein standardisiertes Response-Format:
# {
#   "status": "ok" | "fail" | "blocked",
#   "message": "Menschlich lesbare Kurzmeldung",
#   "details": "Optionale technische Details (max 500 Zeichen)",
#   "timestamp": "ISO-8601 Zeitstempel"
# }
# 
# HTTP-Status ist IMMER 200 OK
# Status-Logik erfolgt über das JSON-Feld "status"
# -----------------------------

@router.post("/tests/run")
async def run_tests():
    """Führt pytest aus"""
    try:
        python = get_python_executable()
        command = f'"{python}" -m pytest -v'
        result = run_command(command)
        
        if result.success:
            return create_test_response(
                status="ok",
                message="Tests erfolgreich"
            )
        else:
            return create_test_response(
                status="fail",
                message="Tests fehlgeschlagen",
                details=result.output[:500] if result.output else "Keine Details verfügbar"
            )
    except Exception as e:
        return create_test_response(
            status="blocked",
            message="Tests konnten nicht ausgeführt werden",
            details=str(e)
        )


@router.post("/tests/coverage")
async def run_tests_with_coverage():
    """Führt pytest mit Coverage aus - Plattformunabhängig"""
    try:
        python = get_python_executable()
        # Use a unique test DB in the system temp directory to avoid locks
        test_db_path = make_test_db_path()
        # Umgebungsvariablen für Test-DB
        test_env = {
            "FILAMENTHUB_DB_PATH": test_db_path,
            "PYTHONPATH": os.getcwd()
        }
        
        # DB initialisieren
        init_result = run_command(
            f'"{python}" -c "from app.database import init_db; init_db()"',
            env=test_env
        )
        
        if not init_result.success:
            return create_test_response(
                status="blocked",
                message="Fehler beim Initialisieren der Test-DB",
                details=init_result.output[:500] if init_result.output else None
            )
        
        # Coverage nur über Smoke-Tests, um gelockte Prod-DB zu vermeiden
        result = run_command(
            f'"{python}" -m pytest --cov=app --cov-report=term tests/test_smoke_crud.py',
            env=test_env
        )
        
        if result.success:
            return create_test_response(
                status="ok",
                message="Coverage-Test erfolgreich"
            )
        else:
            return create_test_response(
                status="fail",
                message="Coverage-Test fehlgeschlagen",
                details=result.output[:500] if result.output else "Keine Details verfügbar"
            )
    except Exception as e:
        return create_test_response(
            status="blocked",
            message="Coverage-Test konnte nicht ausgeführt werden",
            details=str(e)
        )


def _test_command(py_args: str) -> CommandResult:
    """
    Führt Tests gegen eine eigene Test-DB aus, damit die laufende Prod-DB nicht gelockt wird.
    Plattformunabhängig: Funktioniert auf Windows, Linux (Unraid), Raspberry Pi.
    """
    python = get_python_executable()
    # Use unique temp DB path to prevent collisions/locks
    test_db_path = make_test_db_path()

    # Umgebungsvariablen für Test-DB
    test_env = {
        "FILAMENTHUB_DB_PATH": test_db_path,
        "PYTHONPATH": os.getcwd()
    }
    
    # DB initialisieren
    init_result = run_command(
        f'"{python}" -c "from app.database import init_db; init_db()"',
        env=test_env
    )
    
    if not init_result.success:
        return CommandResult(
            success=False,
            message="Fehler beim Initialisieren der Test-DB",
            output=init_result.output
        )
    
    # Tests ausführen
    return run_command(
        f'"{python}" -m pytest {py_args}',
        env=test_env
    )


@router.post("/tests/smoke")
async def run_smoke_tests():
    """Smoke-CRUD-Tests gegen Test-DB - Plattformunabhängig"""
    try:
        result = _test_command("tests/test_smoke_crud.py -q")
        
        if result.success:
            return create_test_response(
                status="ok",
                message="Smoke CRUD Test erfolgreich"
            )
        else:
            return create_test_response(
                status="fail",
                message="Smoke CRUD Test fehlgeschlagen",
                details=result.output[:500] if result.output else "Keine Details verfügbar"
            )
    except Exception as e:
        return create_test_response(
            status="blocked",
            message="Test konnte nicht ausgeführt werden",
            details=str(e)
        )


@router.post("/tests/db")
async def run_db_tests():
    """DB-CRUD-Testskript gegen Test-DB (kein pytest-Wrapper) - Plattformunabhängig"""
    try:
        python = get_python_executable()
        test_db_path = make_test_db_path()
        # Umgebungsvariablen für Test-DB
        test_env = {
            "FILAMENTHUB_DB_PATH": test_db_path,
            "PYTHONPATH": os.getcwd()
        }
        
        # DB initialisieren
        init_result = run_command(
            f'"{python}" -c "from app.database import init_db; init_db()"',
            env=test_env
        )
        
        if not init_result.success:
            return create_test_response(
                status="blocked",
                message="Fehler beim Initialisieren der Test-DB",
                details=init_result.output[:500] if init_result.output else None
            )
        
        # Test-Skript ausführen
        result = run_command(
            f'"{python}" tests/test_db_crud.py',
            env=test_env
        )
        
        if result.success:
            return create_test_response(
                status="ok",
                message="DB CRUD Test erfolgreich"
            )
        else:
            return create_test_response(
                status="fail",
                message="DB CRUD Test fehlgeschlagen",
                details=result.output[:500] if result.output else "Keine Details verfügbar"
            )
    except Exception as e:
        return create_test_response(
            status="blocked",
            message="Test konnte nicht ausgeführt werden",
            details=str(e)
        )


@router.post("/tests/all")
async def run_all_tests():
    """Alle Tests gegen Test-DB"""
    try:
        result = _test_command("-q")
        
        if result.success:
            return create_test_response(
                status="ok",
                message="Alle Tests erfolgreich"
            )
        else:
            return create_test_response(
                status="fail",
                message="Einige Tests fehlgeschlagen",
                details=result.output[:500] if result.output else "Keine Details verfügbar"
            )
    except Exception as e:
        return create_test_response(
            status="blocked",
            message="Tests konnten nicht ausgeführt werden",
            details=str(e)
        )


# -----------------------------
# DOCKER
# -----------------------------
@router.get("/docker/status")
def docker_status():
    """Prüft ob Docker verfügbar ist"""
    result = run_command("docker --version")
    
    if result.success:
        compose_result = run_command("docker compose version")
        return {
            "available": True,
            "docker_version": result.output.strip() if result.output else "Unknown",
            "compose_available": compose_result.success,
            "compose_version": compose_result.output.strip() if compose_result.success and compose_result.output else None
        }
    
    return {
        "available": False,
        "docker_version": None,
        "compose_available": False,
        "compose_version": None
    }


@router.post("/docker/compose/up")
async def docker_compose_up():
    """Startet Docker Compose"""
    result = run_command("docker compose up -d")
    return result


@router.post("/docker/compose/down")
async def docker_compose_down():
    """Stoppt Docker Compose"""
    result = run_command("docker compose down")
    return result


@router.get("/docker/compose/ps")
def docker_compose_ps():
    """Zeigt laufende Container"""
    result = run_command("docker compose ps --format json")
    return {"output": result.output, "success": result.success}


# -----------------------------
# FILE OPERATIONS
# -----------------------------
@router.get("/logs/list")
def list_log_files():
    """Listet alle Log-Dateien auf"""
    return {"deprecated": True, "use": "/api/debug/logs"}

@router.post("/logs/clear/{module}")
async def clear_module_logs(module: str):
    """Loescht alle Logs eines Moduls"""
    return {"deprecated": True, "use": "/api/debug/logs"}

# -----------------------------
# BACKUP
# -----------------------------
@router.post("/backup")
async def create_backup():
    """
    Erstellt ein kombiniertes Backup (SQLite-DB + Logfiles) als ZIP im Verzeichnis data/backups.
    """
    backup_root = "data/backups"
    os.makedirs(backup_root, exist_ok=True)

    db_path = os.environ.get("FILAMENTHUB_DB_PATH", "data/filamenthub.db")
    logs_root = "logs"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(backup_root, f"filamenthub_backup_{timestamp}.zip")

    files_added = 0
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
        if os.path.exists(db_path):
            zipf.write(db_path, arcname="database/filamenthub.db")
            files_added += 1

        if os.path.exists(logs_root):
            for root, _, files in os.walk(logs_root):
                for file in files:
                    if file.endswith(".log"):
                        file_path = os.path.join(root, file)
                        arcname = os.path.join("logs", os.path.relpath(file_path, logs_root))
                        zipf.write(file_path, arcname=arcname)
                        files_added += 1

    if files_added == 0:
        try:
            os.remove(zip_path)
        except OSError:
            pass
        raise HTTPException(status_code=404, detail="Weder Datenbank noch Logfiles gefunden")

    size_mb = round(os.path.getsize(zip_path) / 1024 / 1024, 3)
    return {
        "success": True,
        "message": "Backup (DB + Logs) erstellt",
        "backup_path": os.path.abspath(zip_path),
        "backup_size_mb": size_mb,
        "files_added": files_added,
        "timestamp": timestamp
    }


# -----------------------------
# SERVER CONTROL
# -----------------------------
@router.post("/server/restart")
async def restart_server():
    """
    Triggert einen Server-Neustart
    HINWEIS: Funktioniert nur mit uvicorn reload=True
    """
    return {
        "success": True,
        "message": "Server-Neustart wird durch File-Änderung getriggert",
        "note": "Bei reload=True wird automatisch neugestartet"
    }


@router.get("/server/stats")
def get_server_stats():
    """Gibt Server-Statistiken zurück"""
    import time
    from datetime import datetime
    from app.routes.system_routes import START_TIME
    
    uptime = time.time() - START_TIME
    process = psutil.Process()
    
    # Network connections (wie viele aktive Verbindungen)
    try:
        connections = len(process.connections())
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        connections = 0
    
    # Hostname ermitteln
    try:
        import socket
        hostname = socket.gethostname()
    except:
        hostname = "Unknown"
    
    return {
        "start_time": datetime.fromtimestamp(START_TIME).strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_seconds": round(uptime, 2),
        "uptime_formatted": format_uptime(uptime),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": sys.platform,
        "hostname": hostname,
        "port": 8080,  # aus config laden später
        "active_connections": connections,
        "threads": process.num_threads(),
        "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2)
    }


def format_uptime(seconds: float) -> str:
    """Formatiert Uptime in lesbares Format"""
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)
