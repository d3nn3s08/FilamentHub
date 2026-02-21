from fastapi import APIRouter, HTTPException, Depends
from typing import Any, Optional
import logging

import app.services.live_state as live_state_module
from app.services.ams_normalizer import (
    calc_slot_state,
    normalize_all_live_state,
    normalize_live_state,
    normalize_device,
)
from app.services.ams_parser import parse_ams
from app.services.ams_sync import sync_ams_slots
from typing import List, Dict
from sqlmodel import Session, select
from app.database import get_session
from app.models.spool import Spool
from app.models.printer import Printer
from app.models.material import Material
from app.services.filament_weights import compute_spool_remaining
from app.services.ams_sync_state import get_ams_sync_state

router = APIRouter(prefix="/api/ams", tags=["AMS"])
logger = logging.getLogger("app")


def _compute_spool_totals(spool: Spool, material: Optional[Material]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    remaining, total, percent = compute_spool_remaining(spool, material)
    return remaining, total, percent


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _resolve_spool(session: Session, tag_uid: Optional[str], tray_uuid: Optional[str]) -> Optional[Spool]:
    if not tag_uid and not tray_uuid:
        return None

    if tag_uid and tray_uuid:
        stmt = select(Spool).where((Spool.tag_uid == tag_uid) | (Spool.tray_uuid == tray_uuid))
    elif tag_uid:
        stmt = select(Spool).where(Spool.tag_uid == tag_uid)
    else:
        stmt = select(Spool).where(Spool.tray_uuid == tray_uuid)

    spools = session.exec(stmt).all()
    if len(spools) != 1:
        return None
    return spools[0]


def _get_printer_name_map(session: Session) -> Dict[str, str]:
    printers = session.exec(select(Printer)).all()
    name_map: Dict[str, str] = {}
    for printer in printers:
        if not printer.cloud_serial:
            continue
        name_map[printer.cloud_serial] = printer.name or printer.cloud_serial
    return name_map


def _get_printer_model_map(session: Session) -> Dict[str, str]:
    """Get mapping of cloud_serial to printer model (e.g., A1MINI, X1C)
    
    First try DB, then fallback to live_state printer_name
    """
    # Try DB first
    printers = session.exec(select(Printer)).all()
    model_map: Dict[str, str] = {}
    for printer in printers:
        if not printer.cloud_serial or not printer.model:
            continue
        model_map[printer.cloud_serial] = printer.model
    
    # Fallback: Extract from live_state printer_name (e.g., "A1 Mini" -> "A1MINI")
    if not model_map:  # Only if DB didn't have data
        live = live_state_module.get_all_live_state() or {}
        for device_id, device_info in live.items():
            printer_name = device_info.get("printer_name", "")
            device_serial = device_info.get("device", device_id)
            
            if not printer_name:
                continue
                
            # Map printer names to models
            name_upper = printer_name.upper()
            if "A1" in name_upper and "MINI" in name_upper:
                model_map[device_serial] = "A1MINI"
            elif "X1C" in name_upper:
                model_map[device_serial] = "X1C"
            elif "X1E" in name_upper:
                model_map[device_serial] = "X1E"
            elif "P1P" in name_upper:
                model_map[device_serial] = "P1P"
            elif "P1S" in name_upper:
                model_map[device_serial] = "P1S"
    
    return model_map


def _get_printer_id_map(session: Session) -> Dict[str, str]:
    """Get mapping of cloud_serial to printer ID"""
    printers = session.exec(select(Printer)).all()
    id_map: Dict[str, str] = {}
    for printer in printers:
        if not printer.cloud_serial:
            continue
        id_map[printer.cloud_serial] = printer.id
    return id_map


@router.get("/")
async def list_ams(session: Session = Depends(get_session)) -> Any:
    logger.debug("Listing normalized AMS live state")
    live = live_state_module.get_all_live_state()
    printer_name_map = _get_printer_name_map(session)
    printer_model_map = _get_printer_model_map(session)
    printer_id_map = _get_printer_id_map(session)
    return normalize_live_state(
        live,
        printer_name_by_serial=printer_name_map,
        printer_model_by_serial=printer_model_map,
        printer_id_by_serial=printer_id_map,
    )


@router.get("/regular")
async def list_regular_ams(session: Session = Depends(get_session)) -> Any:
    """Get only regular AMS (not AMS Lite)"""
    logger.debug("Listing regular AMS (non-Lite)")
    live = live_state_module.get_all_live_state()
    printer_name_map = _get_printer_name_map(session)
    printer_model_map = _get_printer_model_map(session)
    printer_id_map = _get_printer_id_map(session)
    normalized = normalize_live_state(
        live,
        printer_name_by_serial=printer_name_map,
        printer_model_by_serial=printer_model_map,
        printer_id_by_serial=printer_id_map,
    )
    
    # Filter: keep only devices with regular AMS (is_ams_lite = false)
    if "devices" in normalized:
        filtered_devices = []
        for device in normalized["devices"]:
            if "ams_units" in device:
                # Keep only AMS units that are NOT lite
                regular_units = [u for u in device["ams_units"] if not u.get("is_ams_lite", False)]
                if regular_units:
                    device_copy = device.copy()
                    device_copy["ams_units"] = regular_units
                    filtered_devices.append(device_copy)
        normalized["devices"] = filtered_devices
    
    return normalized


@router.get("/lite")
async def list_ams_lite(session: Session = Depends(get_session)) -> Any:
    """Get only AMS Lite units"""
    logger.debug("Listing AMS Lite units")
    live = live_state_module.get_all_live_state()
    printer_name_map = _get_printer_name_map(session)
    printer_model_map = _get_printer_model_map(session)
    printer_id_map = _get_printer_id_map(session)
    normalized = normalize_live_state(
        live,
        printer_name_by_serial=printer_name_map,
        printer_model_by_serial=printer_model_map,
        printer_id_by_serial=printer_id_map,
    )
    
    # Filter: keep only devices with AMS Lite (is_ams_lite = true)
    if "devices" in normalized:
        filtered_devices = []
        for device in normalized["devices"]:
            if "ams_units" in device:
                # Keep only AMS Lite units
                lite_units = [u for u in device["ams_units"] if u.get("is_ams_lite", False)]
                if lite_units:
                    device_copy = device.copy()
                    device_copy["ams_units"] = lite_units
                    filtered_devices.append(device_copy)
        normalized["devices"] = filtered_devices
    
    return normalized


@router.get("/sync-status")
async def get_ams_sync_status() -> Any:
    return {"sync_state": get_ams_sync_state()}


@router.post("/sync/{printer_id}")
async def trigger_ams_sync(printer_id: str, session: Session = Depends(get_session)) -> Any:
    """Manually trigger AMS sync for a printer using data from live-state.
    
    This is useful when AMS data arrived but sync wasn't triggered automatically.
    """
    printer = session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    
    if not printer.cloud_serial:
        raise HTTPException(status_code=400, detail="Printer has no cloud_serial")
    
    # Get live-state for this printer
    live = live_state_module.get_live_state(printer.cloud_serial)
    if not live:
        raise HTTPException(status_code=400, detail="No live-state data for printer")
    
    payload = live.get("payload", {}).get("print", {})
    if not payload:
        raise HTTPException(status_code=400, detail="No print payload in live-state")
    
    # Parse AMS data from payload
    try:
        ams_data = parse_ams(payload)
    except Exception as e:
        logger.exception(f"Failed to parse AMS data for printer {printer_id}")
        raise HTTPException(status_code=500, detail=f"Failed to parse AMS: {str(e)}")
    
    if not ams_data:
        raise HTTPException(status_code=400, detail="No AMS data in payload")
    
    # Run sync
    try:
        updated = sync_ams_slots(
            [dict(unit) for unit in ams_data],
            printer_id=printer_id,
            auto_create=True
        )
        logger.info(f"[AMS SYNC] Manual sync for {printer.name}: {updated} spools updated/created")
        return {
            "success": True,
            "message": f"AMS sync completed for {printer.name}",
            "updated_count": updated,
            "ams_units": len(ams_data)
        }
    except Exception as e:
        logger.exception(f"AMS sync failed for printer {printer_id}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/overview")
async def get_ams_overview(session: Session = Depends(get_session)) -> Any:
    """UI-friendly AMS overview aggregating normalized live-state.

    - Uses only `normalize_live_state()` output
    - Filters OUT AMS Lite units (only show regular AMS)
    - DB is used only for spool enrichment
    - Always returns JSON; on error returns safe empty structure
    """
    try:
        printer_name_map = _get_printer_name_map(session)
        printer_model_map = _get_printer_model_map(session)
        normalized = normalize_all_live_state(printer_name_by_serial=printer_name_map, printer_model_by_serial=printer_model_map) or {}
        devices: List[Dict] = normalized.get("devices", [])
        
        # IMPORTANT: Filter OUT AMS Lite units - only show regular AMS
        filtered_devices = []
        for device in devices:
            if "ams_units" in device:
                # Keep only AMS units that are NOT lite
                regular_units = [u for u in device["ams_units"] if not u.get("is_ams_lite", False)]
                if regular_units:
                    device_copy = device.copy()
                    device_copy["ams_units"] = regular_units
                    filtered_devices.append(device_copy)
        devices = filtered_devices

        ams_units: List[Dict] = []
        total_slots = 0
        online_ams = 0

        printer_name = None
        printer_serial = None
        printer_online = False
        if devices:
            preferred = next((d for d in devices if d.get("ams_units")), devices[0])
            printer_serial = preferred.get("device_serial")
            printer_name = printer_name_map.get(printer_serial) if printer_serial else None
            if printer_name is None:
                printer_name = printer_serial
            printer_online = bool(preferred.get("online"))

        total_remaining_grams = 0.0

        material_cache: Dict[str, Material] = {}

        for device in devices:
            device_online = bool(device.get("online"))
            units = device.get("ams_units") or []
            for unit in units:
                ams_id = unit.get("ams_id")
                unit_printer_serial = unit.get("printer_serial") or device.get("device_serial")
                unit_printer_name = unit.get("printer_name") or unit_printer_serial
                env_temp = unit.get("temp") if unit.get("temp") is not None else None
                env_humidity = unit.get("humidity") if unit.get("humidity") is not None else None

                trays = unit.get("trays") or []
                slots = []
                for tray in trays:
                    total_slots += 1
                    tag_uid = tray.get("tag_uid")
                    tray_uuid = tray.get("tray_uuid")
                    remaining_percent = _to_float(tray.get("remain_percent"))
                    remaining_grams = _to_float(tray.get("remaining_grams"))
                    state = calc_slot_state(remaining_percent)

                    spool = _resolve_spool(session, tag_uid, tray_uuid)
                    spool_total = None
                    spool_percent = None

                    material_payload = None
                    spool_payload = None
                    if spool:
                        material_name = spool.name
                        material_vendor = spool.vendor
                        if (material_name is None or material_vendor is None) and spool.material_id:
                            material = material_cache.get(spool.material_id)
                            if material is None:
                                material = session.get(Material, spool.material_id)
                                if material:
                                    material_cache[spool.material_id] = material
                            if material:
                                if material_name is None:
                                    material_name = material.name
                                if material_vendor is None:
                                    material_vendor = material.brand
                        material = material_cache.get(spool.material_id) if spool.material_id else None
                        spool_remaining, spool_total, spool_percent = _compute_spool_totals(spool, material)
                        if spool_remaining is not None:
                            remaining_grams = spool_remaining
                        if spool_percent is not None:
                            remaining_percent = spool_percent

                        if material_name or material_vendor:
                            material_payload = {
                                "name": material_name,
                                "vendor": material_vendor,
                            }
                        spool_payload = {
                            "id": spool.id,
                            "color": spool.color or spool.tray_color,
                            "remaining_grams": remaining_grams,
                            "total_grams": spool_total,
                        }

                        # Fallback: Try to derive grams from raw tray fields if no DB spool and AMS didn't provide
                        if remaining_grams is None:
                            # normalized tray may contain remain_weight or raw remain in various units
                            possible_remain_weight = None
                            try:
                                possible_remain_weight = _to_float(tray.get("remain_weight"))
                            except Exception:
                                possible_remain_weight = None

                            if possible_remain_weight is None:
                                # sometimes AMS reports 'remain' as grams*1000 (legacy), try to detect
                                try:
                                    raw_rem = _to_float(tray.get("remain"))
                                    if raw_rem is not None:
                                        if raw_rem > 1000:
                                            possible_remain_weight = raw_rem / 1000.0
                                        elif raw_rem > 100:  # ambiguous: likely grams
                                            possible_remain_weight = raw_rem
                                except Exception:
                                    possible_remain_weight = None

                            if possible_remain_weight is not None:
                                remaining_grams = round(float(possible_remain_weight), 1)
                                spool_payload["remaining_grams"] = remaining_grams

                            # Last resort: compute from percent (less accurate due to tray_weight including spool)
                            elif remaining_percent is not None and spool_total is not None:
                                try:
                                    remaining_grams = round((float(spool_total) * float(remaining_percent) / 100.0), 1)
                                    spool_payload["remaining_grams"] = remaining_grams
                                except Exception:
                                    remaining_grams = None

                    if remaining_grams is not None:
                        total_remaining_grams += max(0.0, remaining_grams)

                    slots.append({
                        "slot": tray.get("slot"),
                        "state": state,
                        "material": material_payload,
                        "remaining": {
                            "percent": remaining_percent,
                            "grams": remaining_grams,
                        },
                        "spool": spool_payload,
                        "source": "ams",
                        "rfid": tag_uid is not None,
                    })

                if device_online:
                    online_ams += 1

                ams_units.append({
                    "printer_serial": unit_printer_serial,
                    "printer_name": unit_printer_name,
                    "ams_id": ams_id,
                    "online": device_online,
                    "environment": {
                        "temperature_c": env_temp,
                        "humidity_percent": env_humidity,
                    },
                    "slots": slots,
                })

        has_ams = len(ams_units) > 0
        return {
            "has_ams": bool(has_ams),
            "printer": {
                "online": printer_online,
                "name": printer_name,
                "serial": printer_serial,
            },
            "summary": {
                "online_ams": online_ams,
                "total_slots": total_slots,
                "total_remaining_grams": total_remaining_grams,
            },
            "ams_units": ams_units,
        }

    except Exception:
        logger.exception("Failed to build AMS overview")
        return {
            "has_ams": False,
            "printer": {
                "online": False,
                "name": None,
                "serial": None,
            },
            "summary": {"online_ams": 0, "total_slots": 0, "total_remaining_grams": 0},
            "ams_units": [],
        }


@router.get("/{device}")
async def get_ams_device(device: str) -> Any:
    logger.debug("Getting normalized AMS for device %s", device)
    st = live_state_module.get_live_state(device)
    if not st:
        raise HTTPException(status_code=404, detail="Live state not found")
    return normalize_device(st)
