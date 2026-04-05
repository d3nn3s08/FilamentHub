"""
Performance Monitoring Routes
Historische System-Performance Daten
"""
from fastapi import APIRouter
from typing import List, Dict
from datetime import datetime
import psutil
from collections import deque
from fastapi import HTTPException

router = APIRouter(prefix="/api/performance", tags=["Performance"])

# === IN-MEMORY STORAGE ===
# Speichert die letzten 720 Datenpunkte (1 Stunde bei 5s Intervall)
MAX_HISTORY = 720
performance_history: deque = deque(maxlen=MAX_HISTORY)
recording_start = datetime.now()

# === DATA COLLECTION ===
def collect_performance_data():
    """Sammelt aktuelle Performance-Daten"""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    data_point = {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": round(cpu_percent, 1),
        "ram_percent": round(memory.percent, 1),
        "ram_used_mb": round(memory.used / 1024 / 1024, 1),
        "disk_percent": round(disk.percent, 1),
        "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 1)
    }
    
    performance_history.append(data_point)
    
    # Check for alerts
    alerts = []
    if cpu_percent > 90:
        alerts.append({
            "level": "critical",
            "message": f"CPU Usage kritisch: {cpu_percent}%",
            "timestamp": data_point["timestamp"]
        })
    elif cpu_percent > 75:
        alerts.append({
            "level": "warning",
            "message": f"CPU Usage hoch: {cpu_percent}%",
            "timestamp": data_point["timestamp"]
        })
    
    if memory.percent > 90:
        alerts.append({
            "level": "critical",
            "message": f"RAM Usage kritisch: {memory.percent}%",
            "timestamp": data_point["timestamp"]
        })
    elif memory.percent > 75:
        alerts.append({
            "level": "warning",
            "message": f"RAM Usage hoch: {memory.percent}%",
            "timestamp": data_point["timestamp"]
        })
    
    return data_point, alerts

# === ENDPOINTS ===
@router.get("/current")
def get_current_performance():
    """Gibt aktuelle Performance-Daten zurück"""
    data_point, alerts = collect_performance_data()
    return {
        "current": data_point,
        "alerts": alerts
    }

@router.get("/history")
def get_performance_history(limit: int = 60):
    """Gibt Performance-Historie zurück (Standard: letzte 60 Punkte = 5 Minuten)"""
    history_list = list(performance_history)
    
    # Limit anwenden
    if limit > 0:
        history_list = history_list[-limit:]
    
    # Statistiken berechnen
    if len(history_list) > 0:
        cpu_values = [p["cpu_percent"] for p in history_list]
        ram_values = [p["ram_percent"] for p in history_list]
        
        stats = {
            "avg_cpu": round(sum(cpu_values) / len(cpu_values), 1),
            "max_cpu": round(max(cpu_values), 1),
            "min_cpu": round(min(cpu_values), 1),
            "avg_ram": round(sum(ram_values) / len(ram_values), 1),
            "max_ram": round(max(ram_values), 1),
            "min_ram": round(min(ram_values), 1),
            "data_points": len(history_list)
        }
    else:
        stats = {
            "avg_cpu": 0,
            "max_cpu": 0,
            "min_cpu": 0,
            "avg_ram": 0,
            "max_ram": 0,
            "min_ram": 0,
            "data_points": 0
        }
    
    return {
        "history": history_list,
        "stats": stats,
        "recording_since": recording_start.isoformat(),
        "total_data_points": len(performance_history)
    }

@router.post("/clear")
def clear_performance_history():
    """Löscht die Performance-Historie"""
    global recording_start
    performance_history.clear()
    recording_start = datetime.now()
    
    return {
        "success": True,
        "message": "Performance-Historie gelöscht",
        "recording_since": recording_start.isoformat()
    }

@router.get("/export")
def export_performance_data():
    """Exportiert alle Performance-Daten als JSON"""
    return {
        "recording_since": recording_start.isoformat(),
        "total_data_points": len(performance_history),
        "data": list(performance_history)
    }


@router.get("/panel")
def performance_panel(limit: int = 12):
    """
    Liefert einen defensiven Datensatz für das Performance-Panel.
    Rückgabe ist stabil und abwärtskompatibel; Felder sind optional nutzbar.
    """
    try:
        current, alerts = collect_performance_data()
    except Exception as exc:  # pragma: no cover - defensive fallback
        # Fallback bei psutil-/IO-Fehlern
        current = {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": None,
            "ram_percent": None,
            "ram_used_mb": None,
            "disk_percent": None,
            "disk_used_gb": None,
        }
        alerts = [{"level": "error", "message": f"Performance read failed: {exc}", "timestamp": current["timestamp"]}]

    # Historie defensiv aufbereiten
    history_list = list(performance_history)
    if limit > 0:
        history_list = history_list[-limit:]

    if history_list:
        cpu_values = [p.get("cpu_percent") or 0 for p in history_list]
        ram_values = [p.get("ram_percent") or 0 for p in history_list]
        stats = {
            "avg_cpu": round(sum(cpu_values) / len(cpu_values), 1),
            "max_cpu": round(max(cpu_values), 1),
            "min_cpu": round(min(cpu_values), 1),
            "avg_ram": round(sum(ram_values) / len(ram_values), 1),
            "max_ram": round(max(ram_values), 1),
            "min_ram": round(min(ram_values), 1),
            "data_points": len(history_list),
        }
    else:
        stats = {
            "avg_cpu": None,
            "max_cpu": None,
            "min_cpu": None,
            "avg_ram": None,
            "max_ram": None,
            "min_ram": None,
            "data_points": 0,
        }

    return {
        "schema_version": 1,
        "timestamp": datetime.now().isoformat(),
        "current": current,
        "alerts": alerts,
        "history": {
            "items": history_list,
            "stats": stats,
            "total": len(performance_history),
            "recording_since": recording_start.isoformat(),
        },
        "meta": {
            "interval_hint_seconds": 5,
            "limit": limit,
        },
    }
