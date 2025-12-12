
import os
import sqlite3
import subprocess
from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any
from pathlib import Path

router = APIRouter(prefix="/api/database", tags=["Database"])

DB_PATH = os.environ.get("FILAMENTHUB_DB_PATH", "data/filamenthub.db")

# -----------------------------
# DB EDITOR ENDPOINT
# -----------------------------
@router.post("/editor")
async def execute_editor_query(request: Request):
    """Führt beliebige SQL-Befehle aus (INSERT, UPDATE, DELETE, CREATE, ALTER, DROP)"""
    data = await request.json()
    sql = data.get("sql", "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Kein SQL-Befehl übergeben")

    # Sicherheitsabfrage: Nur bestimmte Befehle zulassen
    allowed = ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP")
    if not any(sql.upper().startswith(cmd) for cmd in allowed):
        raise HTTPException(status_code=403, detail="Nur INSERT, UPDATE, DELETE, CREATE, ALTER, DROP erlaubt")

    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        conn.close()
        return {"success": True, "message": "Befehl erfolgreich ausgeführt"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query Fehler: {str(e)}")


# -----------------------------
# DATABASE INFO
# -----------------------------
@router.get("/info")
def get_database_info():
    """Gibt Informationen über die Datenbank zurück"""
    
    if not os.path.exists(DB_PATH):
        return {
            "exists": False,
            "path": DB_PATH,
            "size_mb": 0,
            "tables": []
        }
    
    # File Info
    file_size = os.path.getsize(DB_PATH)
    file_stats = os.stat(DB_PATH)
    
    # Tabellen auslesen
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "exists": True,
        "path": os.path.abspath(DB_PATH),
        "size_mb": round(file_size / 1024 / 1024, 3),
        "size_kb": round(file_size / 1024, 2),
        "tables": tables,
        "table_count": len(tables),
        "created": file_stats.st_ctime,
        "modified": file_stats.st_mtime
    }


@router.get("/tables")
def get_table_info():
    """Gibt detaillierte Informationen über alle Tabellen zurück"""
    
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Alle Tabellen
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    table_info = []
    
    for table in tables:
        # Row Count
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cursor.fetchone()[0]
        # Columns
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        # Preview Rows
        cursor.execute(f"SELECT * FROM {table} LIMIT 5")
        preview_rows = cursor.fetchall()
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
    
    conn.close()
    
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
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    stats = {}
    
    # Materials
    try:
        cursor.execute("SELECT COUNT(*) FROM material")
        stats["materials_count"] = cursor.fetchone()[0]
    except:
        stats["materials_count"] = 0
    
    # Spools
    try:
        cursor.execute("SELECT COUNT(*) FROM spool")
        stats["spools_count"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM spool WHERE is_open = 1")
        stats["spools_open"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM spool WHERE is_empty = 1")
        stats["spools_empty"] = cursor.fetchone()[0]
    except:
        stats["spools_count"] = 0
        stats["spools_open"] = 0
        stats["spools_empty"] = 0
    
    # Printers
    try:
        cursor.execute("SELECT COUNT(*) FROM printer")
        stats["printers_count"] = cursor.fetchone()[0]
    except:
        stats["printers_count"] = 0
    
    # Jobs
    try:
        cursor.execute("SELECT COUNT(*) FROM job")
        stats["jobs_count"] = cursor.fetchone()[0]
    except:
        stats["jobs_count"] = 0
    
    conn.close()
    
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
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        # Convert to dict
        result = [dict(row) for row in rows]
        
        conn.close()
        
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
