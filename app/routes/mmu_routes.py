"""
MMU API Routes — Happy Hare Integration
========================================
Endpunkte:

  GET  /api/mmu/{printer_id}/status
       → Aktueller MMU Live-Status (aus live_state)
         Gibt zurück: enabled, is_homed, tool, gate, action, filament_pos,
                      num_gates, gates (mit Spool-Mapping)

  GET  /api/mmu/{printer_id}/gates
       → Alle Gates mit Spool-Mapping (gekürzte Ansicht)

  POST /api/mmu/{printer_id}/gates/{gate}/assign
       → Spool einem Gate zuweisen
         Body: {"spool_id": "uuid"}

  DELETE /api/mmu/{printer_id}/gates/{gate}/assign
       → Spool-Zuweisung für einen Gate aufheben

  GET  /api/mmu/printers
       → Alle Klipper-Drucker bei denen MMU erkannt wurde
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import engine
from app.models.printer import Printer
from services.mmu_service import get_mmu_service

logger = logging.getLogger("mmu_routes")

router = APIRouter(prefix="/api/mmu", tags=["mmu"])


# ---------------------------------------------------------------------------
# Request-Schemas
# ---------------------------------------------------------------------------
class AssignSpoolRequest(BaseModel):
    spool_id: str


class GcodeRequest(BaseModel):
    script: str


# ---------------------------------------------------------------------------
# Hilfsfunktion: Drucker aus DB laden
# ---------------------------------------------------------------------------
def _get_printer_or_404(printer_id: str) -> Printer:
    with Session(engine) as session:
        printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail=f"Drucker '{printer_id}' nicht gefunden")
    if printer.printer_type != "klipper":
        raise HTTPException(status_code=400, detail="MMU wird nur für Klipper-Drucker unterstützt")
    return printer


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/printers")
def get_mmu_printers():
    """
    Gibt alle Klipper-Drucker zurück bei denen Happy Hare erkannt wurde.
    Nützlich für das Frontend um die MMU-Übersicht zu befüllen.
    """
    mmu_svc = get_mmu_service()

    with Session(engine) as session:
        klipper_printers = session.exec(
            select(Printer).where(Printer.printer_type == "klipper")
        ).all()

    result = []
    for p in klipper_printers:
        mmu_detected = mmu_svc.is_mmu_present(str(p.id))
        live = mmu_svc.get_mmu_live_state(str(p.id))
        result.append({
            "printer_id":   str(p.id),
            "printer_name": p.name,
            "has_mmu":      p.has_mmu or (mmu_detected is True),
            "mmu_detected": mmu_detected,   # None = noch nicht geprüft
            "mmu_type":     p.mmu_type,
            "mmu_gate_count": live.get("num_gates") if live else p.mmu_gate_count,
            "mmu_enabled":  live.get("enabled") if live else None,
        })

    return {"printers": result}


@router.get("/{printer_id}/status")
def get_mmu_status(printer_id: str):
    """
    Gibt den vollständigen MMU Live-Status für einen Drucker zurück.
    Kommt direkt aus dem live_state (Moonraker-Daten, 1s Polling).
    """
    _get_printer_or_404(printer_id)  # Existenz + Typ prüfen

    mmu_svc = get_mmu_service()
    live = mmu_svc.get_mmu_live_state(printer_id)

    if live is None:
        # Noch kein Polling-Ergebnis oder kein MMU
        detected = mmu_svc.is_mmu_present(printer_id)
        if detected is False:
            raise HTTPException(
                status_code=404,
                detail="Kein Happy Hare MMU auf diesem Drucker erkannt"
            )
        return {
            "status":  "pending",
            "message": "MMU-Erkennung läuft noch. Bitte kurz warten.",
        }

    return live


@router.get("/{printer_id}/gates")
def get_mmu_gates(printer_id: str):
    """
    Gibt alle MMU Gates mit ihrem aktuellen Status und Spool-Mapping zurück.
    Weniger Daten als /status — nur Gate-relevante Infos.
    """
    _get_printer_or_404(printer_id)

    mmu_svc = get_mmu_service()
    live = mmu_svc.get_mmu_live_state(printer_id)

    if live is None:
        raise HTTPException(status_code=503, detail="Keine MMU-Daten verfügbar. Ist der Drucker online?")

    return {
        "printer_id":  printer_id,
        "num_gates":   live.get("num_gates", 0),
        "active_gate": live.get("gate", -1),
        "active_tool": live.get("tool", -1),
        "action":      live.get("action_label", "unknown"),
        "gates":       live.get("gates", []),
    }


@router.post("/{printer_id}/gates/{gate}/assign")
def assign_spool_to_gate(printer_id: str, gate: int, body: AssignSpoolRequest):
    """
    Weist einer Spule einen MMU-Gate zu.
    Setzt auf der Spule: printer_id, printer_slot=gate, assigned=True
    """
    _get_printer_or_404(printer_id)

    mmu_svc = get_mmu_service()
    ok = mmu_svc.assign_spool_to_gate(printer_id, gate, body.spool_id)

    if not ok:
        raise HTTPException(status_code=400, detail=f"Zuweisung fehlgeschlagen. Spool-ID: {body.spool_id}")

    logger.info("[MMU API] Spool %s → Gate %d (Drucker %s)", body.spool_id, gate, printer_id)
    return {
        "success":    True,
        "printer_id": printer_id,
        "gate":       gate,
        "spool_id":   body.spool_id,
    }


@router.post("/{printer_id}/gcode")
async def send_mmu_gcode(printer_id: str, body: GcodeRequest):
    """
    Proxy: Sendet einen GCode-Befehl über FilamentHub an Moonraker.
    Kein direkter Browser→Moonraker Zugriff nötig (kein CORS-Problem).
    """
    printer = _get_printer_or_404(printer_id)
    base_url = f"http://{printer.ip_address}:{printer.port or 7125}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/printer/gcode/script",
                json={"script": body.script},
                timeout=5.0,
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Moonraker: HTTP {resp.status_code}")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Moonraker nicht erreichbar: {exc}")


@router.delete("/{printer_id}/gates/{gate}/assign")
def unassign_gate(printer_id: str, gate: int):
    """
    Hebt die Spool-Zuweisung für einen Gate auf.
    """
    _get_printer_or_404(printer_id)

    mmu_svc = get_mmu_service()
    ok = mmu_svc.unassign_gate(printer_id, gate)

    if not ok:
        raise HTTPException(status_code=400, detail=f"Aufheben der Zuweisung fehlgeschlagen für Gate {gate}")

    logger.info("[MMU API] Gate %d (Drucker %s) Zuweisung aufgehoben", gate, printer_id)
    return {
        "success":    True,
        "printer_id": printer_id,
        "gate":       gate,
    }
