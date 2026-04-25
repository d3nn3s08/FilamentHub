"""
Helper to sync AMS slot data into Spool records.
Wir können optional neue Spools anlegen, falls kein Match vorhanden ist.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select, col
import logging
import time
import threading

from app.database import engine
from app.models.spool import Spool
from app.models.material import Material
from app.models.printer import Printer
from app.routes.notification_routes import trigger_notification_sync
from app.services.ams_sync_state import (
    set_ams_sync_state,
    reset_invalid_payloads,
    note_invalid_payload,
)
from app.services.ams_weight_manager import (
    process_ams_spool_detection,
    AMSType,
)
from app.services.ams_normalizer import has_ams_lite_from_payload
import asyncio

logger = logging.getLogger("services")
_printer_service_started_at: Optional[float] = None

# Lock-Mechanismus für Bug #4: Verhindert parallele AMS-Syncs für denselben Drucker
_ams_sync_locks: Dict[str, threading.Lock] = {}  # Key = printer_id
_locks_guard = threading.Lock()  # Meta-Lock für thread-safe Dict-Zugriff


def _get_ams_sync_lock(printer_id: str) -> threading.Lock:
    """
    Holt oder erstellt Lock für einen Drucker (thread-safe).
    Verhindert parallele AMS-Syncs für denselben Drucker (Bug #4).
    """
    with _locks_guard:
        if printer_id not in _ams_sync_locks:
            _ams_sync_locks[printer_id] = threading.Lock()
        return _ams_sync_locks[printer_id]


def mark_printer_service_started(started_at: Optional[float] = None) -> None:
    global _printer_service_started_at
    _printer_service_started_at = started_at if started_at is not None else time.time()


def _bambu_start_delay_active() -> bool:
    if _printer_service_started_at is None:
        return False
    return (time.time() - _printer_service_started_at) < 5.0


def bambu_start_delay_active() -> bool:
    return _bambu_start_delay_active()

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _to_int(value: Any):
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _is_ams_lite_printer(printer: Optional[Printer]) -> bool:
    if not printer:
        return False

    candidates = [
        getattr(printer, "series", None),
        getattr(printer, "model", None),
        getattr(printer, "name", None),
    ]
    normalized = [str(value).strip().upper() for value in candidates if value]

    for value in normalized:
        if value in {"A", "A1", "A1MINI", "A1 MINI"}:
            return True

    cloud_serial = getattr(printer, "cloud_serial", None)
    if not cloud_serial:
        return False

    try:
        from app.services import live_state as live_state_module

        live_entry = live_state_module.get_live_state(cloud_serial) or {}
        payload = live_entry.get("payload") or {}
        printer_model = getattr(printer, "model", None) or getattr(printer, "name", None)
        return has_ams_lite_from_payload(payload, printer_model=printer_model)
    except Exception:
        logger.exception("[AMS SYNC] Failed AMS Lite detection for printer %s", printer.id)
        return False


def _get_default_material_id(session: Session) -> Optional[str]:
    mat = session.exec(select(Material)).first()
    return mat.id if mat else None


def _get_material_for_tray(session: Session, spool: Optional[Spool], tray_type: Optional[str], tray_sub_brands: Optional[str] = None) -> Optional[Material]:
    """
    Sucht Material für AMS-Slot. Priorisiert tray_sub_brands (z.B. "PLA Basic") vor tray_type (z.B. "PLA").
    """
    if spool and spool.material_id:
        return session.get(Material, spool.material_id)
    
    # 1. Versuche zuerst mit tray_sub_brands (spezifischer, z.B. "PLA Basic")
    if tray_sub_brands:
        material = session.exec(
            select(Material).where(Material.name == tray_sub_brands, Material.brand == "Bambu Lab")
        ).first()
        if material:
            return material
    
    # 2. Fallback auf tray_type (z.B. "PLA")
    if tray_type:
        return session.exec(
            select(Material).where(Material.name == tray_type, Material.brand == "Bambu Lab")
        ).first()
    return None


def _is_bambu_material(material: Optional[Material]) -> bool:
    return bool(material and material.is_bambu is True)


def _compute_spool_weights_from_tray(tray: Dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    """
    Compute weight_full and weight_empty for Bambu Lab spools.

    Bambu Lab standard values (Herstellerangaben):
    https://grischabock.ch/forum/thread/2091-filament-spulen-leergewicht/
    - 1kg spool: 1000g filament (Netto), Spule leer 209g
    - 0.5kg spool: 500g filament (Netto), Spule leer 209g
    - 0.25kg spool: 250g filament (Netto), Spule leer 209g

    Args:
        tray: AMS tray data containing total_len (filament length in mm)

    Returns: (weight_full, weight_empty)
        - weight_full: Netto-Filamentgewicht laut Hersteller (1000g, 500g, 250g)
        - weight_empty: Leergewicht der Kunststoffspule (209g)
    """
    # Bambu Lab standard parameters
    FILAMENT_DIAMETER_MM = 1.75
    PLA_DENSITY_G_CM3 = 1.24

    # Try to compute filament size from total_len (RFID length in mm)
    total_len = tray.get("total_len")
    if total_len is not None:
        try:
            length_mm = float(total_len)
            # Calculate filament mass from length: Mass = π × r² × length × density
            import math
            radius_mm = FILAMENT_DIAMETER_MM / 2.0
            volume_mm3 = math.pi * (radius_mm ** 2) * length_mm
            # Convert mm³ to cm³ (/1000) and multiply by density
            filament_mass_g = (volume_mm3 / 1000.0) * PLA_DENSITY_G_CM3

            # Round to nearest standard spool size (Bambu Lab: 250g, 500g, 1000g FILAMENT)
            if filament_mass_g >= 750:
                # 1kg filament spool
                return 1000.0, None
            elif filament_mass_g >= 375:
                # 0.5kg filament spool
                return 500.0, None
            else:
                # 0.25kg filament spool
                return 250.0, None
        except Exception:
            pass

    # Fallback: Standard Bambu 1kg filament spool
    return 1000.0, None


def _has_valid_ams_payload(ams_units: List[Dict[str, Any]]) -> bool:
    for ams in ams_units:
        trays = ams.get("trays") or []
        if trays:
            return True
    return False


def _ensure_material(session: Session, tray_type: Optional[str], tray_color: Optional[str], tray_sub_brands: Optional[str] = None) -> Optional[str]:
    """Findet oder legt ein Material (Bambu Lab, Name=tray_sub_brands oder tray_type) an.

    Priorisiert tray_sub_brands (z.B. "PLA Basic") vor tray_type (z.B. "PLA").
    Verwendet Fuzzy-Matching um existierende Materialien zu finden.
    """
    brand = "Bambu Lab"

    # 1. Versuche zuerst mit tray_sub_brands (spezifischer, z.B. "PLA Basic")
    if tray_sub_brands:
        existing = session.exec(
            select(Material).where(Material.name == tray_sub_brands, Material.brand == brand)
        ).first()
        if existing:
            return existing.id

    # 2. Fallback auf tray_type (z.B. "PLA")
    name = tray_type or "Unknown"

    # 2a. Exakte Suche
    existing = session.exec(
        select(Material).where(Material.name == name, Material.brand == brand)
    ).first()
    if existing:
        return existing.id

    # 2b. Fuzzy-Suche: Finde Materialien die mit tray_type beginnen
    # Beispiel: "PLA" findet "PLA Basic", "PLA Matte", "PLA+"
    fuzzy_matches = session.exec(
        select(Material).where(
            Material.name.like(f"{name}%"),  # Beginnt mit "PLA"
            Material.brand == brand
        )
    ).all()

    if fuzzy_matches:
        # Priorisierung: Kürzester Name zuerst (z.B. "PLA Basic" vor "PLA Basic Refill")
        fuzzy_matches.sort(key=lambda m: len(m.name))
        logger.info(
            f"[AMS SYNC] Fuzzy-Match für tray_type='{name}': Verwende '{fuzzy_matches[0].name}' (ID: {fuzzy_matches[0].id})"
        )
        return fuzzy_matches[0].id
    try:
        mat = Material(
            name=name,
            brand=brand,
            density=1.24,
            diameter=1.75,
            is_bambu=True,
            spool_weight_full=1000.0,
            spool_weight_empty=209.0,
        )
        session.add(mat)
        session.commit()
        session.refresh(mat)
        return mat.id
    except Exception:
        session.rollback()
        logger.exception("Failed to create material for AMS tray name=%s brand=%s", name, brand)
        return None


def release_printer_spools_to_storage(printer_id: str) -> int:
    """
    Verschiebt alle AMS-Spulen eines Druckers ins Lager.
    Wird aufgerufen wenn ein Drucker offline geht (MQTT disconnect).

    WICHTIG: tag_uid und tray_uuid bleiben erhalten, damit die Spulen
    beim nächsten Einschalten automatisch wieder erkannt werden.

    Returns: Anzahl der ins Lager verschobenen Spulen.
    """
    if not printer_id:
        return 0

    released = 0
    try:
        with Session(engine) as session:
            # Finde alle Spulen die diesem Drucker zugeordnet sind UND einen AMS-Slot haben
            ams_spools = session.exec(
                select(Spool).where(
                    Spool.printer_id == printer_id,
                    col(Spool.ams_slot).is_not(None)
                )
            ).all()

            if not ams_spools:
                logger.info(f"[AMS OFFLINE] Drucker {printer_id} hat keine AMS-Spulen zum Freigeben")
                return 0

            for spool in ams_spools:
                logger.info(
                    f"[AMS OFFLINE] Spule {spool.id} (#{spool.spool_number}, Slot {spool.ams_slot}) "
                    f"→ Lager (Drucker {printer_id} offline)"
                )
                # last_slot speichern für Wiedererkennung bei non-RFID Spulen
                spool.last_slot = spool.ams_slot
                spool.ams_slot = None
                spool.ams_id = None
                # ams_source als Marker: "offline_release:<printer_id>" für Wiederzuordnung
                spool.ams_source = f"offline_release:{printer_id}"
                spool.printer_id = None
                spool.location = "storage"
                spool.status = "Verfügbar"
                spool.is_open = False
                spool.last_seen = _now_iso()
                spool.updated_at = _now_iso()
                # WICHTIG: tag_uid und tray_uuid NICHT löschen!
                # Damit wird die Spule beim nächsten Einschalten automatisch wieder erkannt
                session.add(spool)
                released += 1

            session.commit()
            logger.info(f"[AMS OFFLINE] {released} Spulen ins Lager verschoben (Drucker {printer_id})")

    except Exception:
        logger.exception(f"[AMS OFFLINE] Fehler beim Freigeben der Spulen für Drucker {printer_id}")

    return released


def check_and_release_offline_printers() -> int:
    """
    Prüft alle Drucker ob sie offline sind. Wenn ja, werden deren AMS-Spulen
    ins Lager verschoben.

    Nutzt PrinterService.get_status() um den Online-Status zu ermitteln.
    Wird beim Laden der Spulen-Seite aufgerufen.

    Returns: Gesamtanzahl der freigegebenen Spulen.
    """
    total_released = 0
    try:
        from services.printer_service import get_printer_service
        printer_service = get_printer_service()
    except RuntimeError:
        # PrinterService nicht initialisiert (Startup)
        return 0

    try:
        with Session(engine) as session:
            # Finde alle Drucker-IDs die AMS-Spulen haben
            from sqlmodel import distinct
            printer_ids_with_ams = session.exec(
                select(Spool.printer_id).where(
                    col(Spool.printer_id).is_not(None),
                    col(Spool.ams_slot).is_not(None),
                )
            ).all()

            # Deduplizieren
            unique_printer_ids = set(pid for pid in printer_ids_with_ams if pid)

            if not unique_printer_ids:
                return 0

            for printer_id in unique_printer_ids:
                # Lade Printer für cloud_serial
                printer = session.get(Printer, printer_id)
                if not printer or not printer.cloud_serial:
                    continue

                # Prüfe Online-Status
                status = printer_service.get_status(printer.cloud_serial)
                is_connected = bool(status.get("connected", False))

                if not is_connected:
                    logger.info(
                        f"[AMS OFFLINE CHECK] Drucker '{printer.name}' ({printer.id}) "
                        f"ist offline - Spulen werden ins Lager verschoben"
                    )
                    released = release_printer_spools_to_storage(printer_id)
                    total_released += released

    except Exception:
        logger.exception("[AMS OFFLINE CHECK] Fehler beim Prüfen der Offline-Drucker")

    return total_released


def sync_ams_slots(ams_units: List[Dict[str, Any]], printer_id: Optional[str] = None, auto_create: bool = False, default_material_id: Optional[str] = None) -> int:
    """
    Update existing Spool entries based on AMS slot data.
    Matching priority: tag_uid -> tray_uuid -> ams_slot.
    Optional: create new Spools if auto_create=True and eine Material-ID verfügbar ist.
    Returns number of updated records.
    """
    # FIX Bug #4: Lock auf Drucker-Ebene (verhindert parallele AMS-Syncs)
    if printer_id:
        sync_lock = _get_ams_sync_lock(printer_id)
        with sync_lock:
            return _sync_ams_slots_locked(ams_units, printer_id, auto_create, default_material_id)
    else:
        # Fallback: Kein printer_id → Kein Lock (sollte nicht vorkommen)
        logger.warning("[AMS SYNC] No printer_id provided - skipping lock!")
        return _sync_ams_slots_locked(ams_units, printer_id, auto_create, default_material_id)


def _sync_ams_slots_locked(ams_units: List[Dict[str, Any]], printer_id: Optional[str] = None, auto_create: bool = False, default_material_id: Optional[str] = None) -> int:
    """
    Interne Methode - läuft unter Drucker-Lock.
    Update existing Spool entries based on AMS slot data.
    Matching priority: tag_uid -> tray_uuid -> ams_slot.
    Optional: create new Spools if auto_create=True and eine Material-ID verfügbar ist.
    Returns number of updated records.
    """
    updated = 0
    if not ams_units:
        with Session(engine) as session:
            if _bambu_start_delay_active():
                set_ams_sync_state("pending")
                return updated
            existing_ams_spools = session.exec(
                select(Spool).where(
                    Spool.printer_id == printer_id,
                    col(Spool.ams_slot).is_not(None)
                )
            ).first()
            if existing_ams_spools:
                set_ams_sync_state("error")
                try:
                    printer = session.get(Printer, printer_id) if printer_id else None
                    printer_name = printer.name if printer else (printer_id or "Unbekannt")
                    trigger_notification_sync(
                        "ams_error",
                        printer_name=printer_name
                    )
                except Exception:
                    logger.exception("Failed to trigger ams_error notification for printer_id=%s", printer_id)
            else:
                set_ams_sync_state("pending")
        return updated

    with Session(engine) as session:
        if not _has_valid_ams_payload(ams_units):
            note_invalid_payload()
            return updated

        set_ams_sync_state("syncing")
        reset_invalid_payloads()
        material_id = default_material_id if auto_create else None

        # Setting: Soll bei unbekannter Spule still angelegt werden (true) oder immer Dialog (false)?
        from app.routes.settings_routes import get_setting
        _auto_create_setting = get_setting(session, "ams_spool_auto_create", "true")
        _silent_auto_create_allowed = str(_auto_create_setting).lower() in ("1", "true", "yes", "on")

        for ams in ams_units:
            # === EXTRACT AMS ID (required for matching) ===
            ams_id = _to_int(ams.get("id")) or 0
            
            # === NOTIFICATION: AMS Luftfeuchtigkeit prüfen ===
            humidity = ams.get("humidity")
            if humidity is not None:
                try:
                    humidity_val = int(humidity)
                    if humidity_val > 60:
                        # Lade Printer-Name für Kontext
                        printer_name = "Unbekannt"
                        if printer_id:
                            printer = session.get(Printer, printer_id)
                            printer_name = printer.name if printer else printer_id

                        trigger_notification_sync(
                            "ams_humidity_high",
                            humidity=humidity_val,
                            printer_name=printer_name
                        )
                except (ValueError, TypeError):
                    logger.exception("Failed to parse AMS humidity value: %s", humidity)

            trays = ams.get("trays") or []
            for tray in trays:
                tag_uid = tray.get("tag_uid") or tray.get("tag")
                tray_uuid = tray.get("tray_uuid")
                tray_state = tray.get("state")  # state 11 = OK, andere = Fehler
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
                                logger.exception("Failed to parse AMS slot from tray_id_name %s", name_hint)
                                ams_slot = None
                remain = tray.get("remain") or tray.get("remain_percent")
                remain_percent = float(remain) if remain is not None else None
                remain_weight = tray.get("remain_weight") or tray.get("remain_weight_g")
                try:
                    remain_weight = float(remain_weight) if remain_weight is not None else None
                except Exception:
                    remain_weight = None
                tray_type = tray.get("tray_type") or tray.get("material")
                tray_sub_brands = tray.get("tray_sub_brands")  # z.B. "PLA Basic" - spezifischer als tray_type
                tray_color = tray.get("tray_color") or tray.get("color")
                weight_full = None
                weight_empty = None
                weight_current = None

                # === UNLOAD-LOGIK: Leerer Slot → Spule ins Lager verschieben ===
                if not tag_uid and not tray_uuid and ams_slot is not None:
                    # Slot ist leer, prüfe ob Spule mit diesem Slot existiert
                    unload_stmt = select(Spool).where(
                        Spool.printer_id == printer_id,
                        Spool.ams_slot == ams_slot,
                        Spool.ams_id == str(ams_id)
                    )
                    unloaded_spool = session.exec(unload_stmt).first()
                    if unloaded_spool:
                        # Spule wurde entladen → ins Lager verschieben
                        # WICHTIG: tag_uid und tray_uuid NICHT löschen!
                        # Diese sind permanente Spulen-Identifikatoren und müssen erhalten bleiben,
                        # damit die Spule beim Einlegen in ein anderes AMS (z.B. AMS Lite) wieder erkannt wird.
                        logger.info(f"[AMS SYNC] Unloading spool {unloaded_spool.id} from slot {ams_slot}")
                        unloaded_spool.ams_slot = None
                        unloaded_spool.ams_id = None
                        unloaded_spool.location = "storage"
                        unloaded_spool.status = "Verfügbar"
                        unloaded_spool.is_open = False
                        unloaded_spool.last_seen = _now_iso()
                        session.add(unloaded_spool)
                        updated += 1
                    continue  # Leere Slots überspringen

                # === SPOOL MATCHING mit Multi-Printer Isolation ===
                # Priorität 1: RFID Tags sind global eindeutig (erlaubt Drucker-Wechsel)
                # Priorität 2: Tray UUIDs sind global eindeutig (erlaubt Drucker-Wechsel)
                # Priorität 3: RFID Chip ID (legacy field) als Fallback für alte Spulen
                # Priorität 4: AMS Slots sind lokal eindeutig (NUR innerhalb eines Druckers)
                stmt = select(Spool)
                if tag_uid:
                    # RFID Tag ist global eindeutig → kein printer_id Check
                    # Erlaubt Spulen-Migration zwischen Druckern
                    stmt = stmt.where(Spool.tag_uid == tag_uid)
                elif tray_uuid:
                    # Tray UUID ist global eindeutig → kein printer_id Check
                    # FIX Bug #10: Prüfe AUCH rfid_chip_id für alte Spulen ohne tray_uuid
                    stmt = stmt.where(
                        (Spool.tray_uuid == tray_uuid) | (Spool.rfid_chip_id == tray_uuid)
                    )
                elif ams_slot is not None and printer_id:
                    # AMS Slot ist NUR lokal eindeutig → MUSS printer_id prüfen
                    stmt = stmt.where(
                        Spool.ams_slot == ams_slot,
                        Spool.printer_id == printer_id,
                        Spool.ams_id == str(ams_id)
                    )
                else:
                    # Kein valides Matching möglich
                    continue

                # Fallback für non-RFID Spulen nach Offline-Release:
                # Wenn kein Match gefunden wird, suche im Lager nach Spulen die
                # wegen Offline von genau diesem Drucker entladen wurden (gleicher Slot)
                matches = session.exec(stmt).all()
                if not matches and not tag_uid and not tray_uuid and ams_slot is not None and printer_id:
                    offline_marker = f"offline_release:{printer_id}"
                    offline_stmt = select(Spool).where(
                        Spool.last_slot == ams_slot,
                        Spool.ams_source == offline_marker,
                        Spool.printer_id.is_(None),  # Im Lager (kein Drucker zugeordnet)
                    )
                    offline_matches = session.exec(offline_stmt).all()
                    if offline_matches:
                        matches = offline_matches
                        logger.info(
                            f"[AMS SYNC] Offline-Wiedererkennung: Spule {offline_matches[0].id} "
                            f"(last_slot={ams_slot}) → zurück zu Drucker {printer_id}"
                        )

                # Bei tray_uuid Matching mit rfid_chip_id Fallback können mehrere Spulen matchen
                # Priorisiere: tray_uuid > rfid_chip_id (neuere Spulen zuerst)
                if matches:
                    # Wenn mehrere Matches: Bevorzuge Spule mit tray_uuid (nicht nur rfid_chip_id)
                    spool = next((s for s in matches if s.tray_uuid == tray_uuid), None) if tray_uuid else None
                    if not spool:
                        # Fallback: Nimm erste Match (älteste Spule mit rfid_chip_id)
                        spool = matches[0]
                        if len(matches) > 1 and tray_uuid:
                            logger.warning(
                                f"[AMS SYNC] Multiple spools found for tray_uuid={tray_uuid}, "
                                f"using oldest (rfid_chip_id match): spool_id={spool.id}"
                            )
                else:
                    spool = None
                if not spool:
                    if not auto_create:
                        continue
                    mat_id = material_id or _ensure_material(session, tray_type, tray_color, tray_sub_brands)
                    if not mat_id:
                        continue

                    material = session.get(Material, mat_id)
                    is_bambu = _is_bambu_material(material)

                    if is_bambu and _bambu_start_delay_active():
                        logger.info("AMS auto-create delayed for Bambu material (slot=%s)", ams_slot)
                        continue

                    if material and material.spool_weight_full is not None:
                        weight_full = material.spool_weight_full
                    if material and material.spool_weight_empty is not None:
                        weight_empty = material.spool_weight_empty

                    if not is_bambu and (weight_full is None or weight_empty is None):
                        tray_full, tray_empty = _compute_spool_weights_from_tray(tray)
                        if weight_full is None:
                            weight_full = tray_full
                        if weight_empty is None:
                            weight_empty = tray_empty

                    if is_bambu:
                        if remain_weight is not None:
                            weight_current = remain_weight
                        elif remain_percent is not None and weight_full is not None and weight_empty is not None:
                            weight_current = (weight_full - weight_empty) * (remain_percent / 100.0)
                        elif weight_full is not None and weight_empty is not None:
                            # Fallback: Wenn keine Verbrauchsinformation, nehme an die Spule ist voll (neu geladen)
                            weight_current = weight_full - weight_empty
                        else:
                            weight_current = None
                    else:
                        # Non-Bambu: Speichere NETTO-Gewicht (nur Filament, ohne Spule)
                        # Konsistent mit manuellen Spulen (spools.py:88)
                        if remain_percent is not None and weight_full is not None and weight_empty is not None:
                            weight_current = (remain_percent / 100.0) * (weight_full - weight_empty)

                    now = _now_iso()
                    spool_data = {
                        "material_id": mat_id,
                        "printer_id": printer_id,
                        "ams_id": str(ams_id),  # Store AMS unit ID for multi-AMS support
                        "ams_slot": ams_slot,
                        "last_slot": ams_slot,
                        "tag_uid": tag_uid,
                        "tray_uuid": tray_uuid,
                        "rfid_chip_id": tray_uuid,  # WICHTIG: Speichere RFID/UUID als eindeutige Spulen-ID
                        "tray_color": tray_color,
                        "tray_type": tray_type,
                        "remain_percent": remain_percent,
                        "weight_current": weight_current,
                        "last_seen": now,
                        "first_seen": now,
                        "used_count": 0,
                        "label": None,  # Kein auto-Label; AMS-Slot-Info steht in eigener Spalte
                        "status": "Aktiv",  # Neue Spulen im AMS sind "Aktiv"
                        "is_open": True,  # Spulen im AMS sind geoeffnet
                        # MQTT-Daten in Spulen-Felder mappen
                        "color": tray_color,
                        "name": tray_type,
                        "vendor": "Bambu Lab" if is_bambu else tray.get("tray_sub_brands"),
                    }
                    if weight_full is not None:
                        spool_data["weight_full"] = weight_full
                    if weight_empty is not None:
                        spool_data["weight_empty"] = weight_empty

                    # Entscheide ZUERST ob Lager-Spulen existieren, dann handeln:
                    # - Leeres System → Auto-Spule still anlegen (Ersteinrichtung)
                    # - Spulen vorhanden → NUR Dialog zeigen, KEINE Auto-Spule erstellen
                    try:
                        from sqlmodel import func as _func
                        storage_spool_count = session.exec(
                            select(_func.count(Spool.id)).where(
                                col(Spool.ams_slot).is_(None),
                                Spool.is_empty != True,
                            )
                        ).one()
                    except Exception:
                        storage_spool_count = 0

                    # Entscheidung: still anlegen ODER Dialog zeigen
                    # - _silent_auto_create_allowed=True (Standard): wie bisher, leeres System = still anlegen
                    # - _silent_auto_create_allowed=False (Einstellung): immer Dialog, egal ob Lager leer
                    if _silent_auto_create_allowed and storage_spool_count == 0:
                        # Leeres System + Auto-Create erlaubt → still anlegen
                        now = datetime.utcnow().isoformat()
                        spool_data["created_at"] = now
                        spool_data["updated_at"] = now
                        spool = Spool(**spool_data)
                        session.add(spool)
                        session.flush()
                        updated += 1
                        logger.info(
                            f"[AMS SYNC] Leeres System – Auto-Spule fuer Slot {ams_slot} "
                            f"still angelegt (kein Dialog)"
                        )
                    else:
                        # Dialog zeigen: entweder Lager-Spulen vorhanden ODER Auto-Create deaktiviert
                        printer_name = None
                        if printer_id:
                            _printer = session.get(Printer, printer_id)
                            printer_name = _printer.name if _printer else None

                        broadcast_data = {
                            "type": "new_spool_detected",
                            "spool_id": None,  # Keine Auto-Spule erstellt
                            "tag_uid": tag_uid,
                            "tray_uuid": tray_uuid,
                            "tray_type": tray_type,
                            "tray_sub_brands": tray_sub_brands,
                            "tray_color": tray_color,
                            "ams_slot": ams_slot,
                            "ams_id": str(ams_id) if ams_id is not None else None,
                            "printer_id": printer_id,
                            "printer_name": printer_name,
                            "remain_percent": remain_percent,
                            # Gewichtsdaten für "Neue Spule anlegen"-Option im Dialog
                            "weight_current": weight_current,
                            "weight_full": weight_full,
                            "weight_empty": weight_empty,
                            "material_id": mat_id,
                            "vendor": "Bambu Lab" if is_bambu else tray.get("tray_sub_brands"),
                        }

                        reason = "Auto-Create deaktiviert" if not _silent_auto_create_allowed else f"{storage_spool_count} Lager-Spulen vorhanden"
                        logger.info(
                            f"[AMS SYNC] {reason} – "
                            f"Dialog fuer Slot {ams_slot} (tray={tray_uuid[:8] if tray_uuid else None}), "
                            f"keine Auto-Spule erstellt"
                        )

                        from app.routes.spool_assignment_routes import broadcast_new_spool
                        try:
                            loop = asyncio.get_running_loop()
                            asyncio.create_task(broadcast_new_spool(broadcast_data))
                        except RuntimeError:
                            try:
                                from app.main import app
                                main_loop = getattr(app.state, 'event_loop', None)
                                if main_loop and main_loop.is_running():
                                    asyncio.run_coroutine_threadsafe(
                                        broadcast_new_spool(broadcast_data), main_loop
                                    )
                                else:
                                    new_loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(new_loop)
                                    try:
                                        new_loop.run_until_complete(broadcast_new_spool(broadcast_data))
                                    finally:
                                        new_loop.close()
                                        asyncio.set_event_loop(None)
                            except Exception as loop_err:
                                logger.debug(f"[AMS SYNC] Could not broadcast: {loop_err}")

                    continue

                # Update bestehender Spule
                material = _get_material_for_tray(session, spool, tray_type, tray_sub_brands)
                is_bambu = _is_bambu_material(material)
                
                # WICHTIG: Wenn Spule via RFID gematched wurde, printer_id aktualisieren
                # (Erlaubt Spulen-Migration zwischen Druckern)
                if spool.printer_id != printer_id:
                    logger.info(f"[AMS SYNC] Spule {spool.id} wechselt Drucker: {spool.printer_id} → {printer_id}")
                    spool.printer_id = printer_id

                # Offline-Release-Marker bereinigen (Spule ist wieder im AMS)
                if spool.ams_source and spool.ams_source.startswith("offline_release:"):
                    logger.info(f"[AMS SYNC] Spule {spool.id} wieder im AMS nach Offline-Release")
                    spool.ams_source = None

                spool.ams_id = str(ams_id)  # Always update AMS ID
                spool.ams_slot = ams_slot
                spool.last_slot = ams_slot

                # FIX Bug #10: Update RFID-Felder wenn vorhanden (migriert alte rfid_chip_id zu tray_uuid)
                if tag_uid:
                    spool.tag_uid = tag_uid
                if tray_uuid:
                    spool.tray_uuid = tray_uuid
                    spool.rfid_chip_id = tray_uuid  # Sync: beide Felder halten
                    if not spool.tag_uid:
                        # Legacy: Falls tag_uid fehlt aber tray_uuid vorhanden, nutze tray_uuid als tag_uid
                        logger.debug(f"[AMS SYNC] Migrating tray_uuid to tag_uid for spool {spool.id}")

                spool.tray_color = tray_color or spool.tray_color
                spool.tray_type = tray_type or spool.tray_type

                # Set weight_full and weight_empty if missing (backfill for existing spools)
                if is_bambu:
                    if material and material.spool_weight_full is not None:
                        spool.weight_full = material.spool_weight_full
                    if material and material.spool_weight_empty is not None:
                        spool.weight_empty = material.spool_weight_empty
                else:
                    if weight_full is None or weight_empty is None:
                        tray_full, tray_empty = _compute_spool_weights_from_tray(tray)
                        weight_full = weight_full if weight_full is not None else tray_full
                        weight_empty = weight_empty if weight_empty is not None else tray_empty
                    if spool.weight_full is None and weight_full is not None:
                        spool.weight_full = weight_full
                    if spool.weight_empty is None and weight_empty is not None:
                        spool.weight_empty = weight_empty

                # Status aktualisieren: Wenn Spule im AMS ist, auf "Aktiv" setzen
                # Some test doubles (DummySpool) may not have `is_empty` attribute,
                # so use getattr with a sensible default.
                if not getattr(spool, "is_empty", False):
                    spool.status = "Aktiv"
                    spool.is_open = True
                # Neue Rolle erkennen: Remain steigt deutlich an
                if remain_percent is not None and spool.remain_percent is not None and remain_percent > spool.remain_percent + 5:
                    spool.used_count = 0
                    spool.first_seen = _now_iso()

                # Prüfe ob Spule leer geworden ist (vorher > 0, jetzt <= 0)
                old_remain = spool.remain_percent if spool.remain_percent is not None else 0
                if old_remain > 0 and remain_percent is not None and remain_percent <= 0:
                    # Spule ist leer geworden - Notification triggern
                    try:
                        printer = session.get(Printer, printer_id)
                        printer_name = printer.name if printer else printer_id
                        spool_label = spool.label or f"Spule #{spool.id}"
                        trigger_notification_sync(
                            "filament_empty",
                            printer_name=printer_name,
                            spool_label=spool_label
                        )
                    except Exception:
                        logger.exception("Failed to trigger filament_empty notification for spool_id=%s", spool.id)

                if remain_percent is not None:
                    spool.remain_percent = remain_percent

                # Prüfe auf AMS Tray Fehler (state != 11 = Fehler)
                if tray_state is not None and tray_state != 11:
                    try:
                        printer = session.get(Printer, printer_id)
                        printer_name = printer.name if printer else printer_id
                        slot_info = f"Slot {ams_slot}" if ams_slot is not None else "Unbekannter Slot"
                        trigger_notification_sync(
                            "ams_tray_error",
                            printer_name=printer_name,
                            slot=slot_info,
                            state=tray_state
                        )
                    except Exception:
                        logger.exception("Failed to trigger ams_tray_error notification for spool_id=%s", spool.id)

                # KRITISCH: weight_current darf NICHT überschrieben werden, wenn:
                # 1. Spule wird gerade in einem Job verwendet (active_job=True)
                # 2. Job wurde kürzlich beendet und hat Gewicht abgezogen
                #
                # Problem: AMS sendet MQTT-Updates alle 2-3 Sekunden mit remain_percent.
                # Wenn Job-Tracking gerade Gewicht abgezogen hat, würde AMS-Sync das
                # sofort wieder überschreiben mit der alten remain_percent-Berechnung!
                #
                # Lösung: Überschreibe weight_current NUR wenn Spule NICHT in aktivem Job
                should_update_weight = not getattr(spool, 'active_job', False)

                if should_update_weight:
                    if is_bambu:
                        if remain_weight is not None:
                            weight_current = remain_weight
                        elif remain_percent is not None and spool.weight_full is not None and spool.weight_empty is not None:
                            try:
                                wf = float(spool.weight_full)
                                we = float(spool.weight_empty)
                                weight_current = (wf - we) * (remain_percent / 100.0)
                            except Exception:
                                logger.exception("Failed to compute Bambu spool weight for spool_id=%s", spool.id)
                                weight_current = None
                        elif weight_current is None and spool.weight_full is not None and spool.weight_empty is not None:
                            # Fallback: Wenn keine Verbrauchsinformation, nehme an die Spule ist voll
                            try:
                                wf = float(spool.weight_full)
                                we = float(spool.weight_empty)
                                weight_current = wf - we
                            except Exception:
                                logger.exception("Failed to compute fallback weight for spool_id=%s", spool.id)
                                weight_current = None
                    else:
                        # Non-Bambu: Speichere NETTO-Gewicht (nur Filament, ohne Spule)
                        # Konsistent mit manuellen Spulen (spools.py:88)
                        if weight_current is None and remain_percent is not None and spool.weight_full is not None and spool.weight_empty is not None:
                            try:
                                wf = float(spool.weight_full)
                                we = float(spool.weight_empty)
                                weight_current = (remain_percent / 100.0) * (wf - we)
                            except Exception:
                                logger.exception("Failed to compute spool weight for spool_id=%s", spool.id)
                                weight_current = None
                        elif weight_current is None and spool.weight_full is not None and spool.weight_empty is not None:
                            # Fallback: Wenn keine Verbrauchsinformation, nehme an die Spule ist voll
                            try:
                                wf = float(spool.weight_full)
                                we = float(spool.weight_empty)
                                weight_current = wf - we
                            except Exception:
                                logger.exception("Failed to compute fallback weight for non-Bambu spool_id=%s", spool.id)
                                weight_current = None

                    # ========================================
                    # WEIGHT MANAGER INTEGRATION
                    # AMS-Type-basierte Gewichts-Verwaltung
                    # ========================================
                    weight_conflict_detected = False

                    if weight_current is not None and spool.tray_uuid:
                        # Determine AMS type from printer model
                        printer = session.get(Printer, printer_id) if printer_id else None
                        ams_type = AMSType.AMS_LITE if _is_ams_lite_printer(printer) else AMSType.AMS_FULL

                        # Prepare MQTT data for weight manager
                        mqtt_data_for_manager = {
                            'tray_now': {
                                'remain': weight_current
                            }
                        }

                        # Process AMS spool detection
                        try:
                            weight_result = process_ams_spool_detection(
                                spool_uuid=spool.tray_uuid,
                                ams_type=ams_type,
                                mqtt_data=mqtt_data_for_manager,
                                session=session
                            )

                            # If conflict detected, broadcast to frontend
                            if weight_result.get('conflict'):
                                weight_conflict_detected = True
                                logger.warning(
                                    f"[WEIGHT CONFLICT] Spool #{spool.spool_number} (UUID: {spool.tray_uuid}): "
                                    f"Cloud={weight_result['cloud_weight']}g vs DB={weight_result['db_weight']}g "
                                    f"(Diff: {weight_result['difference']}g) - User intervention needed!"
                                )

                                # Broadcast conflict event to frontend
                                # FIX Bug #9: Robuster Event-Loop-Handling für Thread-Kontext
                                try:
                                    from app.routes.weight_management_routes import broadcast_weight_conflict

                                    # Get material name for display
                                    material_name = "Unbekannt"
                                    # Spool hat kein direktes material Attribut, lade es über material_id
                                    if spool.material_id:
                                        try:
                                            material = session.get(Material, spool.material_id)
                                            if material:
                                                material_name = f"{material.brand or ''} {material.name or ''}".strip()
                                        except Exception as mat_err:
                                            logger.warning(f"[WEIGHT CONFLICT] Could not load material: {mat_err}")
                                    if material_name == "Unbekannt" and spool.vendor:
                                        material_name = f"{spool.vendor} {spool.color or ''}".strip()

                                    conflict_data = {
                                        "type": "weight_conflict",
                                        "spool_number": spool.spool_number,
                                        "spool_uuid": spool.tray_uuid,
                                        "spool_id": spool.id,
                                        "spool_color": spool.color,
                                        "material_name": material_name,
                                        "cloud_weight": weight_result['cloud_weight'],
                                        "db_weight": weight_result['db_weight'],
                                        "difference": weight_result['difference'],
                                        "ams_type": ams_type.value,
                                        "recommendation": weight_result.get('recommendation', 'use_db')
                                    }

                                    # Try to get running loop first
                                    try:
                                        loop = asyncio.get_running_loop()
                                        # We're in an async context, use create_task
                                        asyncio.create_task(broadcast_weight_conflict(conflict_data))
                                        logger.info(f"[WEIGHT CONFLICT] Event scheduled via create_task for spool #{spool.spool_number}")
                                    except RuntimeError:
                                        # No running loop - we're in a thread (MQTT worker)
                                        # Get the main event loop from app and schedule there
                                        try:
                                            # Import main app loop
                                            from app.main import app
                                            main_loop = getattr(app.state, 'event_loop', None)

                                            if main_loop and main_loop.is_running():
                                                asyncio.run_coroutine_threadsafe(
                                                    broadcast_weight_conflict(conflict_data),
                                                    main_loop
                                                )
                                                logger.info(f"[WEIGHT CONFLICT] Event scheduled via run_coroutine_threadsafe for spool #{spool.spool_number}")
                                            else:
                                                # Fallback: Create new event loop and run
                                                new_loop = asyncio.new_event_loop()
                                                asyncio.set_event_loop(new_loop)
                                                try:
                                                    new_loop.run_until_complete(broadcast_weight_conflict(conflict_data))
                                                    logger.info(f"[WEIGHT CONFLICT] Event broadcasted via new loop for spool #{spool.spool_number}")
                                                finally:
                                                    new_loop.close()
                                                    asyncio.set_event_loop(None)
                                        except Exception as loop_error:
                                            logger.error(f"[WEIGHT CONFLICT] Failed to find event loop: {loop_error}")
                                except Exception as broadcast_error:
                                    logger.error(f"[WEIGHT CONFLICT] Failed to broadcast event: {broadcast_error}")
                            else:
                                # No conflict - use weight from manager
                                if 'weight' in weight_result:
                                    weight_current = weight_result['weight']
                                    logger.debug(
                                        f"[WEIGHT MANAGER] Spool #{spool.spool_number}: Using {weight_result['source']} "
                                        f"weight ({weight_current}g) from {ams_type.value}"
                                    )
                        except Exception as e:
                            logger.exception(f"[WEIGHT MANAGER] Error processing spool {spool.tray_uuid}: {e}")
                            # Fall back to original weight_current calculation

                    if weight_conflict_detected:
                        logger.info(
                            f"[AMS SYNC] Skip weight update for spool {spool.id}: "
                            "conflict pending user resolution"
                        )
                    elif weight_current is not None:
                        # KRITISCH: Prüfe ob AMS-Wert niedriger als DB-Wert ist
                        # Problem: AMS Lite kann RFID nur LESEN, nicht SCHREIBEN
                        # Wenn Spule von AMS Lite → Regular AMS wandert, hat RFID veraltete Daten!
                        #
                        # Beispiel:
                        # 1. AMS Lite: Spule 791g, Job verbraucht 10g → DB: 781g
                        # 2. RFID Chip: IMMER NOCH 79% (AMS Lite kann nicht schreiben!)
                        # 3. User steckt Spule in Regular AMS
                        # 4. Regular AMS liest RFID: 79% (alt!) → berechnet 624g
                        # 5. OHNE Check: Überschreibt 781g → 624g ❌❌❌
                        #
                        # Lösung: Überschreibe nur wenn AMS-Wert >= DB-Wert
                        if spool.weight_current is not None and weight_current < spool.weight_current:
                            # AMS-Wert ist NIEDRIGER → RFID-Daten sind veraltet!
                            logger.info(
                                f"[AMS SYNC] SKIP weight update for spool {spool.id}: "
                                f"AMS-Wert ({weight_current:.1f}g) < DB-Wert ({spool.weight_current:.1f}g) "
                                f"- RFID wahrscheinlich veraltet (AMS Lite kann nicht schreiben)"
                            )
                        else:
                            # OK: AMS-Wert ist höher/gleich → Update erlaubt
                            spool.weight_current = weight_current
                else:
                    logger.debug(f"[AMS SYNC] Skipping weight update for spool {spool.id} (active_job=True)")
                if not spool.first_seen:
                    spool.first_seen = _now_iso()
                spool.last_seen = _now_iso()
                spool.updated_at = _now_iso()  # Update timestamp on every AMS sync
                # Kein auto-Label mehr setzen; AMS-Slot-Info steht in eigener Spalte
                session.add(spool)
                updated += 1
        try:
            session.commit()
        except Exception:
            session.rollback()
            set_ams_sync_state("error")
            raise
        set_ams_sync_state("ok")
    return updated


