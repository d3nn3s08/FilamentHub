"""Sichere Backup-Endpoints fuer die Datenbank-Sicherung."""
import os
import logging
import shutil
import re
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from app import database as app_database

router = APIRouter(prefix="/api/database/backups", tags=["Backups"])
logger = logging.getLogger("database")

DB_PATH = getattr(app_database, "DB_PATH", os.environ.get("FILAMENTHUB_DB_PATH", "data/filamenthub.db"))
BACKUP_DIR = "data/backups"
MAX_BACKUPS = 10
MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


def _validate_backup_filename(filename: str) -> str:
    """Validates backup filename to prevent path traversal attacks."""
    if not re.match(r'^[a-zA-Z0-9_\-]+\.db$', filename):
        raise HTTPException(status_code=400, detail="Ungueltiger Dateiname")
    return os.path.join(BACKUP_DIR, filename)


def _cleanup_old_backups():
    """Removes oldest backups if more than MAX_BACKUPS exist."""
    if not os.path.exists(BACKUP_DIR):
        return
    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.endswith('.db'):
            fp = os.path.join(BACKUP_DIR, f)
            backups.append((fp, os.stat(fp).st_ctime))
    backups.sort(key=lambda x: x[1])
    while len(backups) > MAX_BACKUPS:
        oldest_path, _ = backups.pop(0)
        try:
            os.remove(oldest_path)
            logger.info("Auto-cleanup: removed old backup %s", oldest_path)
        except Exception as exc:
            logger.warning("Failed to remove old backup %s: %s", oldest_path, exc)


@router.post("/create")
def backup_database():
    """Erstellt ein Dateisystem-Backup der DB."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"filamenthub_backup_{timestamp}.db")
        shutil.copy2(DB_PATH, backup_path)
        backup_size = os.path.getsize(backup_path)
        _cleanup_old_backups()
        return {
            "success": True,
            "message": "Backup erstellt",
            "backup_path": os.path.abspath(backup_path),
            "backup_size_mb": round(backup_size / 1024 / 1024, 3),
            "timestamp": timestamp,
        }
    except Exception as exc:
        logger.error("Backup failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Backup Fehler: {str(exc)}")


@router.get("/list")
def list_backups():
    """Listet alle vorhandenen Backups auf."""
    if not os.path.exists(BACKUP_DIR):
        return {"backups": [], "count": 0}

    backups = []
    try:
        for file in os.listdir(BACKUP_DIR):
            if file.endswith('.db'):
                file_path = os.path.join(BACKUP_DIR, file)
                file_stats = os.stat(file_path)
                backups.append({
                    "filename": file,
                    "path": os.path.abspath(file_path),
                    "size_mb": round(file_stats.st_size / 1024 / 1024, 3),
                    "created": file_stats.st_ctime,
                })
        backups.sort(key=lambda x: x["created"], reverse=True)
    except Exception as exc:
        logger.error("Failed to list backups: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Fehler beim Lesen der Backups")

    return {"backups": backups, "count": len(backups)}


@router.get("/download/{filename}")
def download_backup(filename: str):
    """Liefert eine Backup-Datei als Download."""
    backup_path = _validate_backup_filename(filename)
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="Backup nicht gefunden")
    return FileResponse(
        path=backup_path,
        media_type="application/octet-stream",
        filename=filename,
    )


@router.post("/upload")
async def upload_backup(file: UploadFile = File(...)):
    """Laedt eine .db-Backup-Datei in den Backup-Ordner hoch."""
    source_name = (file.filename or "").strip()
    if not source_name.lower().endswith(".db"):
        raise HTTPException(status_code=400, detail="Nur .db-Dateien sind erlaubt")

    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stem = os.path.splitext(os.path.basename(source_name))[0]
        sanitized_stem = re.sub(r"[^a-zA-Z0-9_\-]+", "_", stem).strip("_") or "imported_backup"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{sanitized_stem}_{timestamp}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)

        size_bytes = 0
        with open(backup_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > MAX_UPLOAD_SIZE_BYTES:
                    out.close()
                    os.remove(backup_path)
                    raise HTTPException(status_code=413, detail="Datei zu gross (max. 100 MB)")
                out.write(chunk)

        if size_bytes == 0:
            os.remove(backup_path)
            raise HTTPException(status_code=400, detail="Datei ist leer")

        logger.info("Backup uploaded: %s (%s bytes)", backup_path, size_bytes)
        _cleanup_old_backups()
        return {
            "success": True,
            "message": "Backup hochgeladen",
            "filename": backup_filename,
            "backup_size_mb": round(size_bytes / 1024 / 1024, 3),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Upload failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload Fehler: {str(exc)}")
    finally:
        await file.close()


@router.post("/restore/{filename}")
def restore_backup(filename: str):
    """Stellt die Datenbank aus einem Backup wieder her."""
    backup_path = _validate_backup_filename(filename)
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="Backup nicht gefunden")

    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        safety_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_path = os.path.join(BACKUP_DIR, f"filamenthub_pre_restore_{safety_ts}.db")
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, safety_path)
            logger.info("Safety backup created at %s", safety_path)

        shutil.copy2(backup_path, DB_PATH)
        logger.info("Database restored from %s", backup_path)
        _cleanup_old_backups()
        return {
            "success": True,
            "message": "Datenbank wiederhergestellt",
            "restored_from": filename,
            "safety_backup": os.path.basename(safety_path),
        }
    except Exception as exc:
        logger.error("Restore failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Restore Fehler: {str(exc)}")


@router.delete("/delete/{filename}")
def delete_backup(filename: str):
    """Loescht ein einzelnes Backup."""
    backup_path = _validate_backup_filename(filename)
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="Backup nicht gefunden")

    try:
        os.remove(backup_path)
        logger.info("Backup deleted: %s", backup_path)
        return {"success": True, "message": f"Backup {filename} geloescht"}
    except Exception as exc:
        logger.error("Delete backup failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Loeschen fehlgeschlagen: {str(exc)}")
