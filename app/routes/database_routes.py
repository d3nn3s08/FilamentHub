import os
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.db.session import session_scope
from app.database import engine


router = APIRouter(prefix="/api/database", tags=["Database"])
logger = logging.getLogger("app")

# Default DB path; tests may override this by setting module variable
DB_PATH = "data/filamenthub.db"


class SQLEditorRequest(BaseModel):
    sql: str


@router.get("/info")
def get_database_info():
    """Gibt Basisinformationen über die Datenbank zurück."""
    exists = os.path.exists(DB_PATH)
    tables: List[str] = []
    file_stats = None
    size_mb = None

    if exists:
        try:
            file_stats = os.stat(DB_PATH)
            size_mb = round(os.path.getsize(DB_PATH) / 1024 / 1024, 3)
        except Exception as exc:
            logger.debug("Could not stat DB file: %s", exc, exc_info=True)

        try:
            with session_scope() as session:
                res = session.exec(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                )
                for row in res.all():
                    tables.append(row[0])
        except Exception as exc:
            logger.debug("Failed to list DB tables: %s", exc, exc_info=True)

    return {
        "exists": exists,
        "size_mb": size_mb,
        "tables": tables,
        "created": getattr(file_stats, "st_ctime", None),
        "modified": getattr(file_stats, "st_mtime", None),
    }


@router.get("/tables")
def get_table_info():
    """Gibt detaillierte Informationen über alle Tabellen zurück."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    table_info: List[Dict[str, Any]] = []
    try:
        with session_scope() as session:
            res = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"))
            names = [r[0] for r in res.all()]
            for table in names:
                # row count
                cnt_res = session.exec(text(f"SELECT COUNT(*) FROM {table}"))
                cnt_row = cnt_res.first()
                row_count = int(cnt_row[0]) if cnt_row else 0

                # columns
                cols_res = session.exec(text(f"PRAGMA table_info({table})"))
                columns_raw = cols_res.all()
                columns = [
                    {
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "primary_key": bool(col[5]),
                    }
                    for col in columns_raw
                ]

                # preview
                preview_res = session.exec(text(f"SELECT * FROM {table} LIMIT 5"))
                preview_rows = [tuple(r) for r in preview_res.all()]
                preview_headers = [col[1] for col in columns_raw]

                table_info.append(
                    {
                        "name": table,
                        "row_count": row_count,
                        "column_count": len(columns),
                        "columns": columns,
                        "preview": {"headers": preview_headers, "rows": preview_rows},
                    }
                )
    except Exception as exc:
        logger.error("Failed to gather table info: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Fehler beim Lesen der Tabellen")

    return {"tables": table_info}


@router.get("/stats")
def get_database_stats():
    """Gibt einfache Zählstatistiken zurück."""
    if not os.path.exists(DB_PATH):
        return {
            "materials_count": 0,
            "spools_count": 0,
            "printers_count": 0,
            "jobs_count": 0,
            "spools_open": 0,
            "spools_empty": 0,
        }

    stats: Dict[str, int] = {}
    with session_scope() as session:
        # Materials
        try:
            res = session.exec(text("SELECT COUNT(*) FROM material"))
            r = res.first()
            stats["materials_count"] = int(r[0]) if r else 0
        except Exception as exc:
            logger.debug("Failed to read material count: %s", exc, exc_info=True)
            stats["materials_count"] = 0

        # Spools
        try:
            res = session.exec(text("SELECT COUNT(*) FROM spool"))
            r = res.first()
            stats["spools_count"] = int(r[0]) if r else 0

            res = session.exec(text("SELECT COUNT(*) FROM spool WHERE is_open = 1"))
            r = res.first()
            stats["spools_open"] = int(r[0]) if r else 0

            res = session.exec(text("SELECT COUNT(*) FROM spool WHERE is_empty = 1"))
            r = res.first()
            stats["spools_empty"] = int(r[0]) if r else 0
        except Exception as exc:
            logger.debug("Failed to read spool stats: %s", exc, exc_info=True)
            stats["spools_count"] = 0
            stats["spools_open"] = 0
            stats["spools_empty"] = 0

        # Printers
        try:
            res = session.exec(text("SELECT COUNT(*) FROM printer"))
            r = res.first()
            stats["printers_count"] = int(r[0]) if r else 0
        except Exception as exc:
            logger.debug("Failed to read printers count: %s", exc, exc_info=True)
            stats["printers_count"] = 0

        # Jobs
        try:
            res = session.exec(text("SELECT COUNT(*) FROM job"))
            r = res.first()
            stats["jobs_count"] = int(r[0]) if r else 0
        except Exception as exc:
            logger.debug("Failed to read jobs count: %s", exc, exc_info=True)
            stats["jobs_count"] = 0

    return stats


@router.get("/query")
def execute_query(sql: str):
    """Führt eine SELECT-Query aus (nur Entwicklung)."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    if not sql.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=403, detail="Nur SELECT Queries erlaubt")

    try:
        with session_scope() as session:
            res = session.exec(text(sql))
            rows = res.mappings().all()
            result = [dict(r) for r in rows]
        return {"success": True, "row_count": len(result), "data": result}
    except Exception as exc:
        logger.error("Query execution failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Query Fehler: {str(exc)}")


@router.post("/editor")
def execute_editor_query(payload: SQLEditorRequest):
    """Führt nicht-SELECT SQL-Befehle aus (INSERT/UPDATE/DELETE/CREATE/ALTER/DROP)."""
    sql = payload.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Kein SQL-Befehl übergeben")

    allowed = ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP")
    if not any(sql.upper().startswith(cmd) for cmd in allowed):
        raise HTTPException(status_code=403, detail="Nur INSERT, UPDATE, DELETE, CREATE, ALTER, DROP erlaubt")

    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    try:
        with session_scope() as session:
            session.exec(text(sql))
            session.commit()
        return {"success": True, "message": "Befehl erfolgreich ausgeführt"}
    except Exception as exc:
        logger.error("Editor query failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Query Fehler: {str(exc)}")


@router.post("/vacuum")
def vacuum_database():
    """Führt VACUUM aus und liefert Vorher/Nachher-Größe."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    try:
        size_before = os.path.getsize(DB_PATH)
        # VACUUM outside explicit transaction
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.exec_driver_sql("VACUUM")
        size_after = os.path.getsize(DB_PATH)
        saved_kb = round((size_before - size_after) / 1024, 2)
        return {
            "success": True,
            "message": "Datenbank optimiert",
            "size_before_mb": round(size_before / 1024 / 1024, 3),
            "size_after_mb": round(size_after / 1024 / 1024, 3),
            "saved_kb": saved_kb,
        }
    except Exception as exc:
        logger.error("VACUUM failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"VACUUM Fehler: {str(exc)}")


@router.post("/backup")
def backup_database():
    """Erstellt ein Dateisystem-Backup der DB (kopiert die Datei)."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    try:
        backup_dir = "data/backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"filamenthub_backup_{timestamp}.db")
        shutil.copy2(DB_PATH, backup_path)
        backup_size = os.path.getsize(backup_path)
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


@router.get("/backups/list")
def list_backups():
    backup_dir = "data/backups"
    if not os.path.exists(backup_dir):
        return {"backups": [], "count": 0}

    backups = []
    try:
        for file in os.listdir(backup_dir):
            if file.endswith('.db'):
                file_path = os.path.join(backup_dir, file)
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


@router.post("/migrate")
def migrate_database():
    """Führt Alembic-Migrationen (upgrade head) aus."""
    project_root = Path(__file__).resolve().parents[2]
    venv_alembic = project_root / ".venv" / "Scripts" / "alembic.exe"
    cmd = [str(venv_alembic if venv_alembic.exists() else "alembic"), "upgrade", "head"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=project_root)
        return {"success": True, "message": "Migration erfolgreich", "stdout": result.stdout, "stderr": result.stderr}
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Alembic CLI nicht gefunden")
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        if "No changes detected" in output or "Keine Änderungen erkannt" in output:
            return {"success": True, "message": "Migration übersprungen (keine Änderungen)", "stdout": exc.stdout, "stderr": exc.stderr}
        logger.error("Migration failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Migration fehlgeschlagen: {exc.stderr or exc.stdout}")


@router.delete("/row")
def delete_row(table: str, id: str):
    """Löscht eine Zeile anhand der ID aus einer erlaubten Tabelle."""
    allowed_tables = {"material", "spool", "printer", "job"}
    if table not in allowed_tables:
        raise HTTPException(status_code=400, detail="Tabelle nicht erlaubt")

    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    try:
        with session_scope() as session:
            res = session.exec(text(f"DELETE FROM {table} WHERE id = :id"), {"id": id})
            # attempt to get affected rows; fall back to existence check
            affected = getattr(res, "rowcount", None)
            if affected is None:
                # check if row still exists
                chk = session.exec(text(f"SELECT COUNT(*) FROM {table} WHERE id = :id"), {"id": id})
                chk_row = chk.first()
                affected = 0 if (chk_row and int(chk_row[0]) > 0) else 1
            session.commit()

        if not affected:
            raise HTTPException(status_code=404, detail="Kein Eintrag mit dieser ID gefunden")

        return {"success": True, "message": f"Eintrag gelöscht ({table}, id={id})", "affected": affected}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Delete error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Delete-Fehler: {exc}")

import os
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.db.session import session_scope
from app.database import engine


router = APIRouter(prefix="/api/database", tags=["Database"])
logger = logging.getLogger("app")

# Default DB path; tests may override this by setting module variable
DB_PATH = "data/filamenthub.db"


class SQLEditorRequest(BaseModel):
    sql: str


@router.get("/info")
def get_database_info():
    """Gibt Basisinformationen über die Datenbank zurück."""
    exists = os.path.exists(DB_PATH)
    tables: List[str] = []
    file_stats = None
    size_mb = None

    if exists:
        try:
            file_stats = os.stat(DB_PATH)
            size_mb = round(os.path.getsize(DB_PATH) / 1024 / 1024, 3)
        except Exception as exc:
            logger.debug("Could not stat DB file: %s", exc, exc_info=True)

        try:
            with session_scope() as session:
                res = session.exec(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                )
                for row in res.all():
                    tables.append(row[0])
        except Exception as exc:
            logger.debug("Failed to list DB tables: %s", exc, exc_info=True)

    return {
        "exists": exists,
        "size_mb": size_mb,
        "tables": tables,
        "created": getattr(file_stats, "st_ctime", None),
        "modified": getattr(file_stats, "st_mtime", None),
    }


@router.get("/tables")
def get_table_info():
    """Gibt detaillierte Informationen über alle Tabellen zurück."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    table_info: List[Dict[str, Any]] = []
    try:
        with session_scope() as session:
            res = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"))
            names = [r[0] for r in res.all()]
            for table in names:
                # row count
                cnt_res = session.exec(text(f"SELECT COUNT(*) FROM {table}"))
                cnt_row = cnt_res.first()
                row_count = int(cnt_row[0]) if cnt_row else 0

                # columns
                cols_res = session.exec(text(f"PRAGMA table_info({table})"))
                columns_raw = cols_res.all()
                columns = [
                    {
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "primary_key": bool(col[5]),
                    }
                    for col in columns_raw
                ]

                # preview
                preview_res = session.exec(text(f"SELECT * FROM {table} LIMIT 5"))
                preview_rows = [tuple(r) for r in preview_res.all()]
                preview_headers = [col[1] for col in columns_raw]

                table_info.append(
                    {
                        "name": table,
                        "row_count": row_count,
                        "column_count": len(columns),
                        "columns": columns,
                        "preview": {"headers": preview_headers, "rows": preview_rows},
                    }
                )
    except Exception as exc:
        logger.error("Failed to gather table info: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Fehler beim Lesen der Tabellen")

    return {"tables": table_info}


@router.get("/stats")
def get_database_stats():
    """Gibt einfache Zählstatistiken zurück."""
    if not os.path.exists(DB_PATH):
        return {
            "materials_count": 0,
            "spools_count": 0,
            "printers_count": 0,
            "jobs_count": 0,
            "spools_open": 0,
            "spools_empty": 0,
        }

    stats: Dict[str, int] = {}
    with session_scope() as session:
        # Materials
        try:
            res = session.exec(text("SELECT COUNT(*) FROM material"))
            r = res.first()
            stats["materials_count"] = int(r[0]) if r else 0
        except Exception as exc:
            logger.debug("Failed to read material count: %s", exc, exc_info=True)
            stats["materials_count"] = 0

        # Spools
        try:
            res = session.exec(text("SELECT COUNT(*) FROM spool"))
            r = res.first()
            stats["spools_count"] = int(r[0]) if r else 0

            res = session.exec(text("SELECT COUNT(*) FROM spool WHERE is_open = 1"))
            r = res.first()
            stats["spools_open"] = int(r[0]) if r else 0

            res = session.exec(text("SELECT COUNT(*) FROM spool WHERE is_empty = 1"))
            r = res.first()
            stats["spools_empty"] = int(r[0]) if r else 0
        except Exception as exc:
            logger.debug("Failed to read spool stats: %s", exc, exc_info=True)
            stats["spools_count"] = 0
            stats["spools_open"] = 0
            stats["spools_empty"] = 0

        # Printers
        try:
            res = session.exec(text("SELECT COUNT(*) FROM printer"))
            r = res.first()
            stats["printers_count"] = int(r[0]) if r else 0
        except Exception as exc:
            logger.debug("Failed to read printers count: %s", exc, exc_info=True)
            stats["printers_count"] = 0

        # Jobs
        try:
            res = session.exec(text("SELECT COUNT(*) FROM job"))
            r = res.first()
            stats["jobs_count"] = int(r[0]) if r else 0
        except Exception as exc:
            logger.debug("Failed to read jobs count: %s", exc, exc_info=True)
            stats["jobs_count"] = 0

    return stats


@router.get("/query")
def execute_query(sql: str):
    """Führt eine SELECT-Query aus (nur Entwicklung)."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    if not sql.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=403, detail="Nur SELECT Queries erlaubt")

    try:
        with session_scope() as session:
            res = session.exec(text(sql))
            rows = res.mappings().all()
            result = [dict(r) for r in rows]
        return {"success": True, "row_count": len(result), "data": result}
    except Exception as exc:
        logger.error("Query execution failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Query Fehler: {str(exc)}")


@router.post("/editor")
def execute_editor_query(payload: SQLEditorRequest):
    """Führt nicht-SELECT SQL-Befehle aus (INSERT/UPDATE/DELETE/CREATE/ALTER/DROP)."""
    sql = payload.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Kein SQL-Befehl übergeben")

    allowed = ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP")
    if not any(sql.upper().startswith(cmd) for cmd in allowed):
        raise HTTPException(status_code=403, detail="Nur INSERT, UPDATE, DELETE, CREATE, ALTER, DROP erlaubt")

    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    try:
        with session_scope() as session:
            session.exec(text(sql))
            session.commit()
        return {"success": True, "message": "Befehl erfolgreich ausgeführt"}
    except Exception as exc:
        logger.error("Editor query failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=400, detail=f"Query Fehler: {str(exc)}")


@router.post("/vacuum")
def vacuum_database():
    """Führt VACUUM aus und liefert Vorher/Nachher-Größe."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    try:
        size_before = os.path.getsize(DB_PATH)
        # VACUUM outside explicit transaction
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.exec_driver_sql("VACUUM")
        size_after = os.path.getsize(DB_PATH)
        saved_kb = round((size_before - size_after) / 1024, 2)
        return {
            "success": True,
            "message": "Datenbank optimiert",
            "size_before_mb": round(size_before / 1024 / 1024, 3),
            "size_after_mb": round(size_after / 1024 / 1024, 3),
            "saved_kb": saved_kb,
        }
    except Exception as exc:
        logger.error("VACUUM failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"VACUUM Fehler: {str(exc)}")


@router.post("/backup")
def backup_database():
    """Erstellt ein Dateisystem-Backup der DB (kopiert die Datei)."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    try:
        backup_dir = "data/backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"filamenthub_backup_{timestamp}.db")
        shutil.copy2(DB_PATH, backup_path)
        backup_size = os.path.getsize(backup_path)
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


@router.get("/backups/list")
def list_backups():
    backup_dir = "data/backups"
    if not os.path.exists(backup_dir):
        return {"backups": [], "count": 0}

    backups = []
    try:
        for file in os.listdir(backup_dir):
            if file.endswith('.db'):
                file_path = os.path.join(backup_dir, file)
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


@router.post("/migrate")
def migrate_database():
    """Führt Alembic-Migrationen (upgrade head) aus."""
    project_root = Path(__file__).resolve().parents[2]
    venv_alembic = project_root / ".venv" / "Scripts" / "alembic.exe"
    cmd = [str(venv_alembic if venv_alembic.exists() else "alembic"), "upgrade", "head"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=project_root)
        return {"success": True, "message": "Migration erfolgreich", "stdout": result.stdout, "stderr": result.stderr}
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Alembic CLI nicht gefunden")
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        if "No changes detected" in output or "Keine Änderungen erkannt" in output:
            return {"success": True, "message": "Migration übersprungen (keine Änderungen)", "stdout": exc.stdout, "stderr": exc.stderr}
        logger.error("Migration failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Migration fehlgeschlagen: {exc.stderr or exc.stdout}")


@router.delete("/row")
def delete_row(table: str, id: str):
    """Löscht eine Zeile anhand der ID aus einer erlaubten Tabelle."""
    allowed_tables = {"material", "spool", "printer", "job"}
    if table not in allowed_tables:
        raise HTTPException(status_code=400, detail="Tabelle nicht erlaubt")

    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    try:
        with session_scope() as session:
            res = session.exec(text(f"DELETE FROM {table} WHERE id = :id"), {"id": id})
            # attempt to get affected rows; fall back to existence check
            affected = getattr(res, "rowcount", None)
            if affected is None:
                # check if row still exists
                chk = session.exec(text(f"SELECT COUNT(*) FROM {table} WHERE id = :id"), {"id": id})
                chk_row = chk.first()
                affected = 0 if (chk_row and int(chk_row[0]) > 0) else 1
            session.commit()

        if not affected:
            raise HTTPException(status_code=404, detail="Kein Eintrag mit dieser ID gefunden")

        return {"success": True, "message": f"Eintrag gelöscht ({table}, id={id})", "affected": affected}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Delete error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Delete-Fehler: {exc}")
@router.get("/tables")
def get_table_info():
    """Gibt detaillierte Informationen über alle Tabellen zurück"""
    
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")
    
    with session_scope() as session:
        table_info = []
        for table in tables:
            # Row Count
            cnt_res = session.exec(text(f"SELECT COUNT(*) as c FROM {table}"))
            cnt_row = cnt_res.first()
            row_count = int(cnt_row[0]) if cnt_row else 0

            # Columns
            cols_res = session.exec(text(f"PRAGMA table_info({table})"))
            columns = cols_res.all()

            # Preview Rows
            preview_res = session.exec(text(f"SELECT * FROM {table} LIMIT 5"))
            preview_rows = [tuple(r) for r in preview_res.all()]

            preview_headers = [col[1] for col in columns]
            table_info.append({
                "name": table,
                "row_count": row_count,
                "column_count": len(columns),
                "columns": [
                    {
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "primary_key": bool(col[5])
                    }
                    for col in columns
                ],
                "preview": {
                    "headers": preview_headers,
                    "rows": preview_rows
                }
            })
    
    return {"tables": table_info}


@router.get("/stats")
def get_database_stats():
    """Gibt Statistiken über die Datenbank zurück"""
    
    if not os.path.exists(DB_PATH):
        return {
            "materials_count": 0,
            "spools_count": 0,
            "printers_count": 0,
            "jobs_count": 0,
            "spools_open": 0,
            "spools_empty": 0
        }
    
    with session_scope() as session:
        stats = {}

        # Materials
        try:
            res = session.exec(text("SELECT COUNT(*) FROM material"))
            r = res.first()
            stats["materials_count"] = int(r[0]) if r else 0
        except Exception as exc:
            logger.debug("Failed to read material count: %s", exc, exc_info=True)
            stats["materials_count"] = 0

        # Spools
        try:
            res = session.exec(text("SELECT COUNT(*) FROM spool"))
            r = res.first()
            stats["spools_count"] = int(r[0]) if r else 0

            res = session.exec(text("SELECT COUNT(*) FROM spool WHERE is_open = 1"))
            r = res.first()
            stats["spools_open"] = int(r[0]) if r else 0

            res = session.exec(text("SELECT COUNT(*) FROM spool WHERE is_empty = 1"))
            r = res.first()
            stats["spools_empty"] = int(r[0]) if r else 0
        except Exception as exc:
            logger.debug("Failed to read spool stats: %s", exc, exc_info=True)
            stats["spools_count"] = 0
            stats["spools_open"] = 0
            stats["spools_empty"] = 0

        # Printers
        try:
            res = session.exec(text("SELECT COUNT(*) FROM printer"))
            r = res.first()
            stats["printers_count"] = int(r[0]) if r else 0
        except Exception as exc:
            logger.debug("Failed to read printers count: %s", exc, exc_info=True)
            stats["printers_count"] = 0

        # Jobs
        try:
            res = session.exec(text("SELECT COUNT(*) FROM job"))
            r = res.first()
            stats["jobs_count"] = int(r[0]) if r else 0
        except Exception as exc:
            logger.debug("Failed to read jobs count: %s", exc, exc_info=True)
            stats["jobs_count"] = 0

    return stats


@router.get("/query")
def execute_query(sql: str):
    """Führt eine SELECT Query aus (nur für Entwicklung!)"""
    
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")
    
    # Sicherheit: Nur SELECT erlauben
    if not sql.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=403, detail="Nur SELECT Queries erlaubt")
    
    try:
        with session_scope() as session:
            res = session.exec(text(sql))
            rows = res.mappings().all()
            result = [dict(r) for r in rows]
        return {
            "success": True,
            "row_count": len(result),
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query Fehler: {str(e)}")


@router.post("/vacuum")
def vacuum_database():
    """Führt VACUUM aus (komprimiert und optimiert die Datenbank)"""
    
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")
    
    try:
        size_before = os.path.getsize(DB_PATH)
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute("VACUUM")
        conn.close()
        
        size_after = os.path.getsize(DB_PATH)
        saved_kb = round((size_before - size_after) / 1024, 2)
        
        return {
            "success": True,
            "message": "Datenbank optimiert",
            "size_before_mb": round(size_before / 1024 / 1024, 3),
            "size_after_mb": round(size_after / 1024 / 1024, 3),
            "saved_kb": saved_kb
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VACUUM Fehler: {str(e)}")


@router.post("/backup")
def backup_database():
    """Erstellt ein Backup der Datenbank"""
    
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")
    
    try:
        from datetime import datetime
        import shutil
        
        # Backup Ordner
        backup_dir = "data/backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup Dateiname mit Timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"filamenthub_backup_{timestamp}.db")
        
        # Copy
        shutil.copy2(DB_PATH, backup_path)
        
        backup_size = os.path.getsize(backup_path)
        
        return {
            "success": True,
            "message": "Backup erstellt",
            "backup_path": os.path.abspath(backup_path),
            "backup_size_mb": round(backup_size / 1024 / 1024, 3),
            "timestamp": timestamp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup Fehler: {str(e)}")


@router.get("/backups/list")
def list_backups():
    """Listet alle Backups auf"""
    
    backup_dir = "data/backups"
    
    if not os.path.exists(backup_dir):
        return {"backups": [], "count": 0}
    
    backups = []
    
    for file in os.listdir(backup_dir):
        if file.endswith('.db'):
            file_path = os.path.join(backup_dir, file)
            file_stats = os.stat(file_path)
            
            backups.append({
                "filename": file,
                "path": os.path.abspath(file_path),
                "size_mb": round(file_stats.st_size / 1024 / 1024, 3),
                "created": file_stats.st_ctime
            })
    
    # Sortiere nach Datum (neueste zuerst)
    backups.sort(key=lambda x: x["created"], reverse=True)
    
    return {"backups": backups, "count": len(backups)}


@router.post("/migrate")
def migrate_database():
    """Führt Alembic-Migrationen (upgrade head) aus."""
    project_root = Path(__file__).resolve().parents[2]
    venv_alembic = project_root / ".venv" / "Scripts" / "alembic.exe"
    cmd = [str(venv_alembic if venv_alembic.exists() else "alembic"), "upgrade", "head"]
    try:
        # Prüfe aktuelle Revision
        current_cmd = [str(venv_alembic if venv_alembic.exists() else "alembic"), "current"]
        current_result = subprocess.run(
            current_cmd,
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        current_output = (current_result.stdout or "") + (current_result.stderr or "")
        # Hole HEAD-Revision
        head_cmd = [str(venv_alembic if venv_alembic.exists() else "alembic"), "heads"]
        head_result = subprocess.run(
            head_cmd,
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        head_output = (head_result.stdout or "") + (head_result.stderr or "")
        # Extrahiere Revisionen
        import re
        current_rev = re.search(r"([0-9a-f]+) \(head\)", current_output)
        head_rev = re.search(r"([0-9a-f]+) \(head\)", head_output)
        if current_rev and head_rev and current_rev.group(1) == head_rev.group(1):
            return {
                "success": True,
                "message": "Migration übersprungen (bereits aktuell)",
                "stdout": current_output,
                "stderr": ""
            }
        # Führe Migration aus
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=project_root,
        )
        # Prüfe auf spezielle Info im Alembic-Output
        output = (result.stdout or "") + (result.stderr or "")
        if "ist bereits vorhanden" in output or "already exists" in output:
            return {
                "success": True,
                "message": "Datenbankspalte bereits vorhanden",
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        if "No changes detected" in output or "Keine Änderungen erkannt" in output:
            return {
                "success": True,
                "message": "Migration übersprungen (keine Änderungen)",
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        return {
            "success": True,
            "message": "Migration erfolgreich",
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Alembic CLI nicht gefunden (venv/.venv/Scripts/alembic.exe oder alembic im PATH nicht vorhanden)")
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        if "ist bereits vorhanden" in output or "already exists" in output:
            return {
                "success": True,
                "message": "Datenbankspalte bereits vorhanden",
                "stdout": exc.stdout,
                "stderr": exc.stderr
            }
        if "No changes detected" in output or "Keine Änderungen erkannt" in output:
            return {
                "success": True,
                "message": "Migration übersprungen (keine Änderungen)",
                "stdout": exc.stdout,
                "stderr": exc.stderr
            }
        raise HTTPException(status_code=500, detail=f"Migration fehlgeschlagen: {exc.stderr or exc.stdout}")


@router.delete("/row")
def delete_row(table: str, id: str):
    """Löscht eine Zeile anhand der ID aus einer erlaubten Tabelle."""
    allowed_tables = {"material", "spool", "printer", "job"}
    if table not in allowed_tables:
        raise HTTPException(status_code=400, detail="Tabelle nicht erlaubt")
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {table} WHERE id = ?", (id,))
        affected = cur.rowcount
        conn.commit()
        conn.close()
        if affected == 0:
            raise HTTPException(status_code=404, detail="Kein Eintrag mit dieser ID gefunden")
        return {"success": True, "message": f"Eintrag gelöscht ({table}, id={id})", "affected": affected}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete-Fehler: {e}")
