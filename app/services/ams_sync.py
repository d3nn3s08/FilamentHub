"""
Helper to sync AMS slot data into Spool records.
Wir können optional neue Spools anlegen, falls kein Match vorhanden ist.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select

from app.database import engine
from app.models.spool import Spool
from app.models.material import Material
from app.routes.notification_routes import trigger_notification_sync


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _to_int(value: Any):
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _get_default_material_id(session: Session) -> Optional[str]:
    mat = session.exec(select(Material)).first()
    return mat.id if mat else None


def _ensure_material(session: Session, tray_type: Optional[str], tray_color: Optional[str]) -> Optional[str]:
    """Findet oder legt ein Material (Bambu Lab, Name=tray_type) an."""
    name = tray_type or "Unknown"
    brand = "Bambu Lab"
    existing = session.exec(
        select(Material).where(Material.name == name, Material.brand == brand)
    ).first()
    if existing:
        return existing.id
    try:
        mat = Material(
            name=name,
            brand=brand,
            color=f"#{tray_color[:6]}" if tray_color else None,
            density=1.24,
            diameter=1.75,
        )
        session.add(mat)
        session.commit()
        session.refresh(mat)
        return mat.id
    except Exception:
        session.rollback()
        return None


def sync_ams_slots(ams_units: List[Dict[str, Any]], printer_id: Optional[str] = None, auto_create: bool = False, default_material_id: Optional[str] = None) -> int:
    """
    Update existing Spool entries based on AMS slot data.
    Matching priority: tag_uid -> tray_uuid -> ams_slot.
    Optional: create new Spools if auto_create=True and eine Material-ID verfügbar ist.
    Returns number of updated records.
    """
    updated = 0
    if not ams_units:
        return updated

    with Session(engine) as session:
        material_id = default_material_id if auto_create else None
        for ams in ams_units:
            # === NOTIFICATION: AMS Luftfeuchtigkeit prüfen ===
            humidity = ams.get("humidity")
            if humidity is not None:
                try:
                    humidity_val = int(humidity)
                    if humidity_val > 60:
                        # Lade Printer-Name für Kontext
                        printer_name = "Unbekannt"
                        if printer_id:
                            from app.models.printer import Printer
                            printer = session.get(Printer, printer_id)
                            printer_name = printer.name if printer else printer_id

                        trigger_notification_sync(
                            "ams_humidity_high",
                            humidity=humidity_val,
                            printer_name=printer_name
                        )
                except (ValueError, TypeError):
                    pass

            trays = ams.get("trays") or []
            for tray in trays:
                tag_uid = tray.get("tag_uid") or tray.get("tag")
                tray_uuid = tray.get("tray_uuid")
                # slot robust auslesen, ohne 0 zu verwerfen
                raw_slot = tray.get("tray_id")
                if raw_slot is None:
                    raw_slot = tray.get("id")
                if raw_slot is None:
                    raw_slot = tray.get("slot") or tray.get("tray")
                ams_slot = _to_int(raw_slot)
                if ams_slot is None:
                    # Versuche aus tray_id_name wie "A00-K0" die Slot-Nummer (letzte Ziffer) zu ziehen
                    name_hint = tray.get("tray_id_name") or tray.get("name")
                    if name_hint and isinstance(name_hint, str):
                        digits = "".join(filter(str.isdigit, name_hint))
                        if digits:
                            try:
                                ams_slot = int(digits[-1])
                            except Exception:
                                ams_slot = None
                remain = tray.get("remain") or tray.get("remain_percent")
                remain_percent = float(remain) if remain is not None else 0.0
                tray_type = tray.get("tray_type") or tray.get("material")
                tray_color = tray.get("tray_color") or tray.get("color")
                weight_current = None
                # einfache Ableitung des aktuellen Gewichts, falls vorhanden
                if remain_percent is not None and tray.get("weight_full") and tray.get("weight_empty"):
                    try:
                        wf = float(tray.get("weight_full"))
                        we = float(tray.get("weight_empty"))
                        weight_current = we + (remain_percent / 100.0) * (wf - we)
                    except Exception:
                        weight_current = None

                stmt = select(Spool)
                if tag_uid:
                    stmt = stmt.where(Spool.tag_uid == tag_uid)
                elif tray_uuid:
                    stmt = stmt.where(Spool.tray_uuid == tray_uuid)
                elif ams_slot is not None:
                    stmt = stmt.where(Spool.ams_slot == ams_slot)
                else:
                    continue

                spool = session.exec(stmt).first()
                if not spool:
                    if not auto_create:
                        continue
                    mat_id = material_id or _ensure_material(session, tray_type, tray_color)
                    if not mat_id:
                        continue
                    now = _now_iso()
                    spool = Spool(
                        material_id=mat_id,
                        printer_id=printer_id,
                        ams_slot=ams_slot,
                        last_slot=ams_slot,
                        tag_uid=tag_uid,
                        tray_uuid=tray_uuid,
                        tray_color=tray_color,
                        tray_type=tray_type,
                        remain_percent=remain_percent,
                        weight_current=weight_current,
                        last_seen=now,
                        first_seen=now,
                        used_count=0,
                        label=f"AMS Slot {ams_slot}" if ams_slot is not None else None,
                    )
                    session.add(spool)
                    updated += 1
                    continue

                # Update bestehender Spule
                spool.ams_slot = ams_slot
                spool.last_slot = ams_slot
                spool.tag_uid = tag_uid or spool.tag_uid
                spool.tray_uuid = tray_uuid or spool.tray_uuid
                spool.tray_color = tray_color or spool.tray_color
                spool.tray_type = tray_type or spool.tray_type
                # Neue Rolle erkennen: Remain steigt deutlich an
                if remain_percent is not None and spool.remain_percent is not None and remain_percent > spool.remain_percent + 5:
                    spool.used_count = 0
                    spool.first_seen = _now_iso()
                spool.remain_percent = remain_percent
                if weight_current is None and remain_percent is not None and spool.weight_full is not None and spool.weight_empty is not None:
                    try:
                        wf = float(spool.weight_full)
                        we = float(spool.weight_empty)
                        weight_current = we + (remain_percent / 100.0) * (wf - we)
                    except Exception:
                        weight_current = None
                if weight_current is not None:
                    spool.weight_current = weight_current
                if not spool.first_seen:
                    spool.first_seen = _now_iso()
                spool.last_seen = _now_iso()
                if ams_slot is not None and not spool.label:
                    spool.label = f"AMS Slot {ams_slot}"
                session.add(spool)
                updated += 1
        session.commit()
    return updated
