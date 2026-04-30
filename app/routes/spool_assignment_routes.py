"""
FastAPI Routes for Spool Assignment (New AMS Spool → Existing Storage Spool)

When a new spool is detected in the AMS (UUID not in DB), it gets auto-created.
This module provides:
- SSE stream to notify frontend about newly detected spools
- Merge endpoint to transfer UUID/RFID from auto-created spool to existing storage spool
- Storage spools listing for the assignment modal
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select, col
import asyncio
import json
import time
import logging

from app.database import get_session
from app.models.spool import Spool
from app.models.material import Material
from app.models.printer import Printer
from app.services.spool_number_service import assign_spool_number

logger = logging.getLogger("services")

router = APIRouter(prefix="/api/spools", tags=["spool-assignment"])

# ========================================
# Global Pub/Sub for New Spool Detection
# ========================================
connected_clients: set = set()

# Cooldown: Don't re-broadcast same tray_uuid within 60 seconds
# (war 300s/5min – zu lang: wenn Benutzer Dialog verpasst, muss er 5min warten)
_broadcast_cooldown: dict = {}
BROADCAST_COOLDOWN_SECONDS = 60


def clear_broadcast_cooldown(tray_uuid: str) -> None:
    """Löscht Cooldown für eine tray_uuid (z.B. wenn Spule gelöscht wird)."""
    _broadcast_cooldown.pop(tray_uuid, None)


async def broadcast_new_spool(spool_data: dict):
    """Broadcast new spool detection to all connected SSE clients."""
    tray_uuid = spool_data.get("tray_uuid")

    # Cooldown check
    if tray_uuid and tray_uuid in _broadcast_cooldown:
        elapsed = time.time() - _broadcast_cooldown[tray_uuid]
        if elapsed < BROADCAST_COOLDOWN_SECONDS:
            return
        else:
            del _broadcast_cooldown[tray_uuid]

    if tray_uuid:
        _broadcast_cooldown[tray_uuid] = time.time()

    logger.info(f"[SPOOL ASSIGN] Broadcasting new spool to {len(connected_clients)} clients")

    disconnected = set()
    for client_queue in connected_clients:
        try:
            client_queue.put_nowait(spool_data)
        except Exception as e:
            logger.debug(f"[SPOOL ASSIGN] Failed to send to client: {e}")
            disconnected.add(client_queue)

    for q in disconnected:
        connected_clients.discard(q)


# ========================================
# Request/Response Models
# ========================================

class MergeRequest(BaseModel):
    """Merge auto-created spool (source) into existing storage spool (target)."""
    source_spool_id: str
    target_spool_id: str


class AssignFromAmsRequest(BaseModel):
    """AMS-Erkennungsdaten für direktes Zuordnen zu bestehender Lager-Spule (ohne Auto-Spule)."""
    tray_uuid: str | None = None
    tag_uid: str | None = None
    ams_slot: int | None = None
    ams_id: str | None = None
    printer_id: str | None = None
    remain_percent: float | None = None
    tray_type: str | None = None
    tray_color: str | None = None
    weight_current: float | None = None
    weight_full: float | None = None
    weight_empty: float | None = None


class CreateFromAmsRequest(BaseModel):
    """Erstellt eine neue Spule aus AMS-Erkennungsdaten (User wählte 'Neue Spule anlegen')."""
    tray_uuid: str | None = None
    tag_uid: str | None = None
    ams_slot: int
    ams_id: str | None = None
    printer_id: str | None = None
    remain_percent: float | None = None
    tray_type: str | None = None
    tray_sub_brands: str | None = None
    tray_color: str | None = None
    weight_current: float | None = None
    weight_full: float | None = None
    weight_empty: float | None = None
    material_id: str | None = None
    vendor: str | None = None


# ========================================
# SSE Endpoint
# ========================================

@router.get("/new-detected/stream")
async def new_spool_stream():
    """
    SSE endpoint for real-time new spool detection notifications.
    Frontend connects to receive alerts when unknown spools appear in AMS.
    """
    client_queue = asyncio.Queue()
    connected_clients.add(client_queue)
    logger.info(f"[SPOOL ASSIGN SSE] Client connected. Total: {len(connected_clients)}")

    async def event_generator():
        from app.main import is_app_shutting_down
        try:
            while not is_app_shutting_down():
                try:
                    spool_data = await asyncio.wait_for(
                        client_queue.get(),
                        timeout=30.0
                    )
                    yield f"data: {json.dumps(spool_data)}\n\n"
                except asyncio.TimeoutError:
                    yield f": heartbeat\n\n"
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"[SPOOL ASSIGN SSE] Error: {e}")
                    yield f"data: {{\"error\": \"stream_error\"}}\n\n"
                    await asyncio.sleep(1)
        finally:
            connected_clients.discard(client_queue)
            logger.info(f"[SPOOL ASSIGN SSE] Client disconnected. Total: {len(connected_clients)}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ========================================
# Storage Spools (for assignment modal)
# ========================================

@router.get("/storage")
def get_storage_spools(session: Session = Depends(get_session)):
    """
    Returns all spools currently in storage (not assigned to any AMS).
    Used by the assignment modal to list available spools.

    Filterkriterien:
    - ams_slot IS NULL  → nicht in einem AMS-Slot (Hauptkriterium)
    - is_empty != True  → nicht als leer markiert (NULL wird wie False behandelt)
    - printer_id-Prüfung entfernt: Spulen können printer_id aus früherer AMS-Nutzung
      haben, sind aber trotzdem im Lager, wenn ams_slot NULL ist
    """
    stmt = select(Spool).where(
        col(Spool.ams_slot).is_(None),
        Spool.is_empty != True,  # NULL-safe: NULL gilt als "nicht leer"
        # is_active: NULL-safe, alte Datensätze ohne is_active-Flag einschließen
        (Spool.is_active == True) | col(Spool.is_active).is_(None),
    )
    spools = session.exec(stmt).all()

    result = []
    for s in spools:
        # Load material name
        material_name = None
        material_brand = None
        if s.material_id:
            mat = session.get(Material, s.material_id)
            if mat:
                material_name = mat.name
                material_brand = mat.brand

        result.append({
            "id": s.id,
            "spool_number": s.spool_number,
            "name": s.name or material_name,
            "vendor": s.vendor or material_brand,
            "color": s.color or s.tray_color,
            "material_name": material_name,
            "material_brand": material_brand,
            "weight_current": s.weight_current,
            "weight_full": s.weight_full,
            "remain_percent": s.remain_percent,
            "status": s.status,
            "tag_uid": s.tag_uid,
            "tray_uuid": s.tray_uuid,
            "label": s.label,
        })

    return result


# ========================================
# Merge Endpoint
# ========================================

@router.post("/merge")
def merge_spools(req: MergeRequest, session: Session = Depends(get_session)):
    """
    Merge an auto-created AMS spool (source) into an existing storage spool (target).

    Transfers UUID/RFID data and AMS assignment from source to target, then deletes source.
    """
    source = session.get(Spool, req.source_spool_id)
    target = session.get(Spool, req.target_spool_id)

    if not source:
        raise HTTPException(status_code=404, detail="Quell-Spule (auto-created) nicht gefunden")
    if not target:
        raise HTTPException(status_code=404, detail="Ziel-Spule (Lager) nicht gefunden")

    # Validate source has RFID/UUID data
    if not source.tag_uid and not source.tray_uuid:
        raise HTTPException(
            status_code=400,
            detail="Quell-Spule hat keine UUID/RFID-Daten zum Übertragen",
        )

    logger.info(
        f"[SPOOL MERGE] Merging source={source.id} → target={target.id} "
        f"(#{target.spool_number}, tag_uid={source.tag_uid}, tray_uuid={source.tray_uuid})"
    )

    # Transfer RFID/UUID identifiers
    target.tag_uid = source.tag_uid
    target.tray_uuid = source.tray_uuid
    target.rfid_chip_id = source.rfid_chip_id

    # Transfer AMS assignment
    target.printer_id = source.printer_id
    target.ams_slot = source.ams_slot
    target.ams_id = source.ams_id
    target.last_slot = source.ams_slot
    target.status = "Aktiv"
    target.location = None
    target.is_open = True

    # Transfer tray metadata.
    # Farbe immer aus der neu erkannten Spule übernehmen, damit die Zielspule
    # den tatsächlich eingelegten Farbwert widerspiegelt.
    if source.tray_color:
        target.tray_color = source.tray_color
    if not target.tray_type and source.tray_type:
        target.tray_type = source.tray_type
    if source.color:
        target.color = source.color

    # Transfer weight data (only if target doesn't have current weight)
    if target.weight_current is None and source.weight_current is not None:
        target.weight_current = source.weight_current
    if source.remain_percent is not None:
        target.remain_percent = source.remain_percent

    # Update timestamps
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    target.updated_at = now
    target.last_seen = now

    # Delete source (the auto-created duplicate)
    session.delete(source)
    session.add(target)
    session.commit()
    session.refresh(target)

    logger.info(
        f"[SPOOL MERGE] Success: Spule #{target.spool_number} hat jetzt "
        f"UUID={target.tray_uuid}, AMS Slot={target.ams_slot}"
    )

    # Rückwirkend weight_history-Einträge mit spool_number befüllen
    # (Druckjobs die VOR dem Merge liefen haben spool_number=None gespeichert)
    if target.tray_uuid and target.spool_number:
        try:
            from app.services.spool_number_service import backfill_weight_history_spool_number
            updated = backfill_weight_history_spool_number(
                session, target.tray_uuid, target.spool_number
            )
            if updated:
                session.commit()
                logger.info(
                    f"[SPOOL MERGE] Weight-History Backfill: {updated} Eintraege "
                    f"fuer Spule #{target.spool_number} aktualisiert"
                )
        except Exception:
            logger.exception("[SPOOL MERGE] Weight-History Backfill fehlgeschlagen (non-critical)")

    # Build response
    material_name = None
    if target.material_id:
        mat = session.get(Material, target.material_id)
        if mat:
            material_name = f"{mat.brand or ''} {mat.name or ''}".strip()

    printer_name = None
    if target.printer_id:
        printer = session.get(Printer, target.printer_id)
        if printer:
            printer_name = printer.name

    return {
        "success": True,
        "spool": {
            "id": target.id,
            "spool_number": target.spool_number,
            "name": target.name,
            "color": target.color,
            "material": material_name,
            "printer_name": printer_name,
            "ams_slot": target.ams_slot,
            "tag_uid": target.tag_uid,
            "tray_uuid": target.tray_uuid,
            "status": target.status,
        },
    }


# ========================================
# Assign from AMS (kein Auto-Spool nötig)
# ========================================

@router.post("/{spool_id}/assign-from-ams")
def assign_spool_from_ams(
    spool_id: str,
    req: AssignFromAmsRequest,
    session: Session = Depends(get_session),
):
    """
    Weist einer bestehenden Lager-Spule die AMS-Erkennungsdaten zu.
    Wird verwendet wenn im Dialog 'Zuordnen' geklickt wird und KEINE Auto-Spule
    vorher erstellt wurde (spool_id=null im Broadcast-Event).
    """
    from datetime import datetime

    spool = session.get(Spool, spool_id)
    if not spool:
        raise HTTPException(status_code=404, detail="Spule nicht gefunden")

    logger.info(
        f"[SPOOL ASSIGN] assign-from-ams: spool={spool_id[:8]} "
        f"slot={req.ams_slot} tray={req.tray_uuid[:8] if req.tray_uuid else None}"
    )

    # AMS-Erkennungsdaten auf die Spule übertragen
    if req.tray_uuid:
        spool.tray_uuid = req.tray_uuid
        spool.rfid_chip_id = req.tray_uuid
    if req.tag_uid:
        spool.tag_uid = req.tag_uid
    if req.ams_slot is not None:
        spool.ams_slot = req.ams_slot
        spool.last_slot = req.ams_slot
    if req.ams_id is not None:
        spool.ams_id = str(req.ams_id)
    if req.printer_id:
        spool.printer_id = req.printer_id
    if req.remain_percent is not None:
        spool.remain_percent = req.remain_percent
    if req.tray_type and not spool.tray_type:
        spool.tray_type = req.tray_type
    if req.tray_color:
        spool.tray_color = req.tray_color
    if req.weight_current is not None and spool.weight_current is None:
        spool.weight_current = req.weight_current
    if req.weight_full is not None and spool.weight_full is None:
        spool.weight_full = req.weight_full
    if req.weight_empty is not None and spool.weight_empty is None:
        spool.weight_empty = req.weight_empty

    now = datetime.utcnow().isoformat()
    spool.status = "Aktiv"
    spool.is_open = True
    spool.location = None
    spool.last_seen = now
    spool.updated_at = now

    session.add(spool)
    session.commit()
    session.refresh(spool)

    # Weight-History Backfill: Wenn Spule schon eine Nummer hat, UUID rückwirkend eintragen
    if spool.tray_uuid and spool.spool_number:
        try:
            from app.services.spool_number_service import backfill_weight_history_spool_number
            updated_count = backfill_weight_history_spool_number(
                session, spool.tray_uuid, spool.spool_number
            )
            if updated_count:
                session.commit()
        except Exception:
            logger.exception("[SPOOL ASSIGN] Weight-History Backfill fehlgeschlagen (non-critical)")

    # Response
    material_name = None
    if spool.material_id:
        mat = session.get(Material, spool.material_id)
        if mat:
            material_name = f"{mat.brand or ''} {mat.name or ''}".strip()

    return {
        "success": True,
        "spool": {
            "id": spool.id,
            "spool_number": spool.spool_number,
            "name": spool.name,
            "color": spool.color,
            "material": material_name,
            "ams_slot": spool.ams_slot,
            "tag_uid": spool.tag_uid,
            "tray_uuid": spool.tray_uuid,
            "status": spool.status,
        },
    }


# ========================================
# Create from AMS (User wählte "Neue Spule anlegen")
# ========================================

@router.post("/create-from-ams")
def create_spool_from_ams(
    req: CreateFromAmsRequest,
    session: Session = Depends(get_session),
):
    """
    Erstellt eine neue Spule aus den AMS-Erkennungsdaten.
    Wird aufgerufen wenn der User im Dialog 'Neue Spule anlegen' wählt.
    """
    from datetime import datetime

    # Material auflösen: wenn keine material_id übergeben, via tray_type suchen/erstellen
    mat_id = req.material_id
    if not mat_id and req.tray_type:
        try:
            from app.services.ams_sync import _ensure_material
            mat_id = _ensure_material(session, req.tray_type, req.tray_color, req.tray_sub_brands)
        except Exception as e:
            logger.warning(f"[SPOOL ASSIGN] _ensure_material fehlgeschlagen: {e}")

    if not mat_id:
        # Fallback: erstes verfügbares Material verwenden
        any_mat = session.exec(select(Material)).first()
        mat_id = any_mat.id if any_mat else None

    material = session.get(Material, mat_id) if mat_id else None

    if not mat_id:
        raise HTTPException(
            status_code=400,
            detail="Kein Material gefunden. Bitte zuerst ein Material anlegen.",
        )

    weight_full = req.weight_full
    if weight_full is None and material and material.spool_weight_full is not None:
        weight_full = material.spool_weight_full
    if weight_full is None:
        weight_full = 750

    weight_empty = req.weight_empty
    if weight_empty is None and material and material.spool_weight_empty is not None:
        weight_empty = material.spool_weight_empty
    if weight_empty is None:
        weight_empty = 20

    weight_current = req.weight_current
    if weight_current is None and req.remain_percent is not None:
        try:
            weight_current = (float(weight_full) - float(weight_empty)) * (float(req.remain_percent) / 100.0)
        except Exception:
            weight_current = None
    if weight_current is None:
        try:
            weight_current = max(0.0, float(weight_full) - float(weight_empty))
        except Exception:
            weight_current = None

    printer = session.get(Printer, req.printer_id) if req.printer_id else None
    is_bambu_printer = bool(printer and str(printer.printer_type).lower() == "bambu")

    derived_name = (
        req.tray_sub_brands
        or req.tray_type
        or (material.name if material else None)
        or "AMS Spule"
    )
    derived_vendor = (
        req.vendor
        or (material.brand if material else None)
        or ("Bambu Lab" if is_bambu_printer else None)
    )

    now = datetime.utcnow().isoformat()
    spool_data = {
        "material_id": mat_id,
        "printer_id": req.printer_id,
        "ams_id": str(req.ams_id) if req.ams_id else None,
        "ams_slot": req.ams_slot,
        "last_slot": req.ams_slot,
        "tag_uid": req.tag_uid,
        "tray_uuid": req.tray_uuid,
        "rfid_chip_id": req.tray_uuid,
        "tray_color": req.tray_color,
        "tray_type": req.tray_type,
        "remain_percent": req.remain_percent,
        "weight_current": weight_current,
        "weight_full": weight_full,
        "weight_empty": weight_empty,
        "last_seen": now,
        "first_seen": now,
        "used_count": 0,
        "status": "Aktiv",
        "is_open": True,
        "color": req.tray_color,
        "name": derived_name,
        "vendor": derived_vendor,
        "created_at": now,
        "updated_at": now,
    }

    spool = Spool(**spool_data)
    assign_spool_number(spool, session)
    session.add(spool)
    session.commit()
    session.refresh(spool)

    logger.info(
        f"[SPOOL ASSIGN] create-from-ams: neue Spule {spool.id[:8]} "
        f"für Slot {req.ams_slot} erstellt"
    )

    material_name = None
    if material:
        material_name = f"{material.brand or ''} {material.name or ''}".strip()

    return {
        "success": True,
        "spool": {
            "id": spool.id,
            "spool_number": spool.spool_number,
            "name": spool.name,
            "color": spool.color,
            "material": material_name,
            "ams_slot": spool.ams_slot,
            "tag_uid": spool.tag_uid,
            "tray_uuid": spool.tray_uuid,
            "status": spool.status,
        },
    }
