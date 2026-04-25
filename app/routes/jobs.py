from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session, SQLModel, select, col
from typing import List, Optional, Any
from datetime import datetime
from app.database import get_session
from app.models.job import Job, JobCreate, JobRead, JobSpoolUsage
from app.models.spool import Spool
from app.models.printer import Printer
from app.models.settings import Setting
import app.services.live_state as live_state_module
from app.services.eta import calculate_eta
from app.services.eta.bambu_a_series_eta import estimate_remaining_time_from_layers
import logging

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
logger = logging.getLogger("app")

_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, max-age=0, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _set_no_cache(response: Response) -> None:
    for key, value in _NO_CACHE_HEADERS.items():
        response.headers[key] = value



def _extract_print_fields(payload: Any) -> tuple[Optional[int], Optional[int], Optional[str]]:
    print_data = payload.get("print") if isinstance(payload, dict) else None
    if not isinstance(print_data, dict):
        print_data = payload if isinstance(payload, dict) else {}

    layer_num = None
    total_layer_num = None
    product_name = None

    if isinstance(print_data, dict):
        layer_num = print_data.get("layer_current") or print_data.get("layer_num") or print_data.get("layer") or print_data.get("layer_index")
        total_layer_num = (
            print_data.get("total_layer_num")
            or print_data.get("layer_total")
            or print_data.get("layer_count")
            or print_data.get("total_layers")
        )
        product_name = print_data.get("product_name") or print_data.get("product")

    if product_name is None and isinstance(payload, dict):
        product_name = payload.get("product_name") or payload.get("product")

    try:
        layer_num = int(layer_num) if layer_num is not None else None
    except Exception:
        layer_num = None
    try:
        total_layer_num = int(total_layer_num) if total_layer_num is not None else None
    except Exception:
        total_layer_num = None

    return layer_num, total_layer_num, product_name


def _detect_a_series(printer: Printer) -> tuple[bool, str]:
    series = str(getattr(printer, "series", "UNKNOWN") or "UNKNOWN").upper().strip()
    return series == "A", series


def _compute_progress_for_job(job: Job, session: Session) -> tuple[Optional[float], bool]:
    try:
        printer = session.get(Printer, job.printer_id)
        if not printer:
            return None, False

        cloud = printer.cloud_serial
        live_entry = live_state_module.get_live_state(cloud) if cloud else None
        payload = live_entry.get("payload") if isinstance(live_entry, dict) else {}

        layer_num, total_layer_num, _ = _extract_print_fields(payload)
        is_a_series, _ = _detect_a_series(printer)
        if not is_a_series:
            return None, False

        if job.finished_at is not None:
            return 1.0, True

        if layer_num is None or total_layer_num is None or total_layer_num <= 0:
            return None, True

        progress = float(layer_num) / float(total_layer_num)
        if progress < 0.0:
            progress = 0.0
        return progress, True
    except Exception:
        logger.exception("Failed to compute progress for job_id=%s", job.id)
        return None, False


def _compute_eta_for_job(job: Job, session: Session) -> Optional[int]:
    """Try to compute ETA for a Job using printer model and live-state payload.

    Returns seconds (int) or None.
    """
    try:
        printer = session.get(Printer, job.printer_id)
        if not printer:
            return None

        # Try to get live payload by cloud_serial
        cloud = printer.cloud_serial
        live_entry = live_state_module.get_live_state(cloud) if cloud else None
        payload = None
        if isinstance(live_entry, dict):
            payload = live_entry.get("payload") or {}

        layer_num, total_layer_num, _ = _extract_print_fields(payload)
        bambu_remaining_time = None
        if isinstance(payload, dict):
            print_data = payload.get("print") or payload
            if isinstance(print_data, dict):
                bambu_remaining_time = print_data.get("remain_time_s") or print_data.get("mc_remaining_time") or print_data.get("mc_remaining_seconds") or print_data.get("remaining_time") or print_data.get("remain")

        # Coerce types
        try:
            if bambu_remaining_time is not None:
                bambu_remaining_time = int(float(bambu_remaining_time))
        except Exception:
            logger.exception("Failed to coerce remaining time for job_id=%s", job.id)
            bambu_remaining_time = None

        is_a_series, series = _detect_a_series(printer)

        if is_a_series:
            if layer_num is None or total_layer_num is None:
                eta = None
            else:
                eta = estimate_remaining_time_from_layers(
                    started_at=job.started_at,
                    layer_num=layer_num,
                    total_layer_num=total_layer_num,
                )
        else:
            eta = calculate_eta(
                printer_model=(printer.model if hasattr(printer, "model") else None),
                started_at=job.started_at,
                layer_num=layer_num,
                total_layer_num=total_layer_num,
                bambu_remaining_time=bambu_remaining_time,
            )
        if eta is not None and eta < 0:
            eta = 0
        return eta
    except Exception:
        logger.exception("Failed to compute ETA for job_id=%s", job.id)
        return None


def _coerce_dt(value: Any, now: datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            logger.exception("Failed to parse datetime string value=%s", value)
            return now
    return now


def _load_spools_for_job(job: Job, session: Session) -> None:
    """Lädt JobSpoolUsage-Einträge und fügt sie als spools[] zum Job hinzu"""
    try:
        usages = session.exec(
            select(JobSpoolUsage)
            .where(JobSpoolUsage.job_id == job.id)
            .order_by(col(JobSpoolUsage.order_index))
        ).all()
        # Konvertiere zu Dictionaries für korrekte JSON-Serialisierung
        spools_data = []
        for u in usages:
            spool = session.get(Spool, u.spool_id) if u.spool_id else None
            spools_data.append(
                {
                    "id": u.id,
                    "job_id": u.job_id,
                    "spool_id": u.spool_id,
                    "slot": u.slot,
                    "used_mm": u.used_mm,
                    "used_g": u.used_g,
                    "order_index": u.order_index,
                    "spool_number": spool.spool_number if spool else None,
                    "spool_label": spool.label if spool else None,
                    "tray_color": spool.tray_color if spool else None,
                }
            )
        object.__setattr__(job, 'spools', spools_data)
    except Exception:
        logger.exception("Failed to load spools for job_id=%s", job.id)
        object.__setattr__(job, 'spools', [])


@router.get("/", response_model=List[JobRead])
def get_all_jobs(response: Response, session: Session = Depends(get_session)):
    """Alle Druckaufträge abrufen"""
    _set_no_cache(response)
    jobs = session.exec(select(Job).order_by(col(Job.started_at).desc())).all() # type: ignore
    # Attach ETA where possible (non-blocking)
    for j in jobs:
        try:
            j.eta_seconds = _compute_eta_for_job(j, session)
        except Exception:
            logger.exception("Failed to compute ETA for job_id=%s", j.id)
            j.eta_seconds = None
        # Lade spools[] Array
        _load_spools_for_job(j, session)
    return jobs


@router.get("/active", response_model=List[JobRead])
def get_active_jobs(response: Response, session: Session = Depends(get_session)):
    """
    Liefert alle aktuell laufenden Druckjobs.
    """
    _set_no_cache(response)
    jobs = session.exec(
        select(Job)
        .where(col(Job.started_at).is_not(None))
        .where(col(Job.finished_at).is_(None))
        .order_by(col(Job.started_at).desc())
    ).all()

    for job in jobs:
        try:
            job.eta_seconds = _compute_eta_for_job(job, session)

            try:
                progress, is_a_series = _compute_progress_for_job(job, session)
                object.__setattr__(job, 'progress', progress)
                object.__setattr__(job, 'is_a_series', is_a_series)
            except Exception:
                # Fallback: ignore if attribute cannot be set on model
                pass

        except Exception:
            job.eta_seconds = None
            try:
                object.__setattr__(job, 'progress', None)
                object.__setattr__(job, 'is_a_series', None)
            except Exception:
                pass

        # Lade spools[] Array
        _load_spools_for_job(job, session)

    return jobs

@router.get("/with-usage")
def get_all_jobs_with_usage(response: Response, session: Session = Depends(get_session)):
    """Alle Jobs inkl. Spulenverbrauch (job_spool_usage) liefern"""
    _set_no_cache(response)
    jobs = session.exec(select(Job).order_by(col(Job.started_at).desc())).all()
    result = []
    for job in jobs:
        usages = session.exec(
            select(JobSpoolUsage)
            .where(JobSpoolUsage.job_id == job.id)
            .order_by(col(JobSpoolUsage.order_index))
        ).all()
        item = job.model_dump()
        # compute ETA and inject
        try:
            item["eta_seconds"] = _compute_eta_for_job(job, session)
        except Exception:
            logger.exception("Failed to compute ETA for job_id=%s", job.id)
            item["eta_seconds"] = None
        item["usages"] = [u.model_dump() for u in usages]
        result.append(item)
    return result


@router.get("/stats/summary")
def get_job_stats(response: Response, session: Session = Depends(get_session)):
    """Job-Statistiken abrufen"""
    _set_no_cache(response)
    jobs = session.exec(select(Job)).all()
    
    total_jobs = len(jobs)
    total_filament_g = sum((job.filament_used_g or 0.0) for job in jobs)
    total_filament_m = sum((job.filament_used_mm or 0.0) for job in jobs) / 1000  # mm to m

    completed_jobs = [
        job for job in jobs
        if job.finished_at is not None and (job.status or "").lower() != "pending_weight"
    ]
    active_jobs = total_jobs - len(completed_jobs)

    # Energie-Berechnung
    now = datetime.utcnow()
    default_power_kw = 0.30  # Schätzung wenn kein Wert hinterlegt
    power_exact_kwh = 0.0
    power_est_kwh = 0.0
    total_duration_h = 0.0

    # Schnellzugriff: alle Printer laden
    printers = {p.id: p for p in session.exec(select(Printer)).all()}

    for job in jobs:
        start = _coerce_dt(job.started_at, now)
        end = _coerce_dt(job.finished_at, now)
        duration_h = max((end - start).total_seconds(), 0) / 3600.0
        total_duration_h += duration_h

        printer = printers.get(job.printer_id)
        power = printer.power_consumption_kw if printer else None
        if power is not None:
            power_exact_kwh += power * duration_h
        else:
            power_est_kwh += default_power_kw * duration_h

    energy_kwh = power_exact_kwh + power_est_kwh

    # Strompreis laden
    price_setting = session.exec(select(Setting).where(Setting.key == "cost.electricity_price_kwh")).first()
    price_kwh = float(price_setting.value) if price_setting and price_setting.value else None
    energy_cost = energy_kwh * price_kwh if price_kwh is not None else None

    return {
        "total_jobs": total_jobs,
        "completed_jobs": len(completed_jobs),
        "active_jobs": active_jobs,
        "total_filament_g": round(total_filament_g, 2),
        "total_filament_m": round(total_filament_m, 2),
        "total_duration_h": round(total_duration_h, 2),
        "energy_kwh_exact": round(power_exact_kwh, 3),
        "energy_kwh_estimated": round(power_est_kwh, 3),
        "energy_kwh_total": round(energy_kwh, 3),
        "energy_cost_total": round(energy_cost, 2) if energy_cost is not None else None,
        "energy_price_kwh": price_kwh,
    }


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, response: Response, session: Session = Depends(get_session)):
    """Einzelnen Druckauftrag abrufen"""
    _set_no_cache(response)
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")
    try:
        job.eta_seconds = _compute_eta_for_job(job, session)
    except Exception:
        logger.exception("Failed to compute ETA for job_id=%s", job.id)
        job.eta_seconds = None
    # Lade spools[] Array
    _load_spools_for_job(job, session)
    return job


@router.post("/", response_model=JobRead)
def create_job(job: JobCreate, session: Session = Depends(get_session)):
    """Neuen Druckauftrag anlegen"""
    db_job = Job.model_validate(job)
    printer = session.get(Printer, db_job.printer_id) if db_job.printer_id else None
    is_klipper = bool(printer and (printer.printer_type or "").lower() == "klipper")
    if is_klipper and (db_job.status or "").lower() == "completed" and float(db_job.filament_used_g or 0.0) <= 0:
        db_job.status = "pending_weight"

    # Wenn Spule zugewiesen und Verbrauch vorhanden: Von Spule abziehen
    if db_job.spool_id and db_job.filament_used_g and db_job.filament_used_g > 0:
        spool = session.get(Spool, db_job.spool_id)
        if spool:
            # Gewicht abziehen
            if spool.weight_current is not None:
                old_weight = float(spool.weight_current or 0)
                new_weight = max(0, float(spool.weight_current) - float(db_job.filament_used_g))
                spool.weight_current = new_weight

                # Prozentsatz neu berechnen
                if spool.weight_full and spool.weight_empty:
                    weight_range = float(spool.weight_full) - float(spool.weight_empty)
                    if weight_range > 0:
                        spool.remain_percent = ((new_weight - float(spool.weight_empty)) / weight_range) * 100
                        spool.remain_percent = max(0, min(100, spool.remain_percent))  # Clamp auf 0-100

                # Spule als "leer" markieren wenn unter 50g
                if new_weight < 50:
                    spool.is_empty = True

                # Create WeightHistory entry only if the job is already finished/abgeschlossen
                if db_job.finished_at or (getattr(db_job, 'status', None) or '').lower() == 'completed':
                    try:
                        from app.models.weight_history import WeightHistory
                        history = WeightHistory(
                            spool_uuid=spool.tray_uuid or spool.id,
                            spool_number=spool.spool_number,
                            old_weight=old_weight,
                            new_weight=new_weight,
                            source='filamenthub_manual',
                            change_reason='job_created',
                            user='System'
                        )
                        session.add(history)
                    except Exception:
                        # best effort: do not fail job creation if history fails
                        pass

                session.add(spool)

    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    try:
        db_job.eta_seconds = _compute_eta_for_job(db_job, session)
    except Exception:
        logger.exception("Failed to compute ETA for job_id=%s", db_job.id)
        db_job.eta_seconds = None
    return db_job


@router.patch("/{job_id}")
def patch_job(job_id: str, payload: dict, session: Session = Depends(get_session)):
    """
    Partielles Update eines Jobs (für Cloud-Daten-Ergänzung).
    Unterstützt: started_at, finished_at, status, filament_used_g, filament_used_mm
    """
    db_job = session.get(Job, job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")

    # Erlaubte Felder für partielles Update
    # display_name: User kann frei ändern (für Anzeige)
    # name: Original aus MQTT (für Matching) - sollte nicht manuell geändert werden
    allowed_fields = ['started_at', 'finished_at', 'status', 'filament_used_g', 'filament_used_mm', 'name', 'display_name']

    # Merke alte Werte
    old_used_g = db_job.filament_used_g or 0
    old_spool_id = db_job.spool_id
    old_finished = bool(db_job.finished_at)

    for key, value in payload.items():
        if key in allowed_fields and value is not None:
            setattr(db_job, key, value)

    printer = session.get(Printer, db_job.printer_id) if db_job.printer_id else None
    is_klipper = bool(printer and (printer.printer_type or "").lower() == "klipper")
    if is_klipper and (db_job.status or "").lower() == "completed" and float(db_job.filament_used_g or 0.0) <= 0:
        db_job.status = "pending_weight"

    # Entscheide ob der Job jetzt als abgeschlossen gilt (entweder bereits oder via Patch)
    will_be_finished = bool(db_job.finished_at) or (payload.get('status') and str(payload.get('status')).lower() == 'completed') or ('finished_at' in payload and payload.get('finished_at'))

    # Falls Verbrauch gesetzt wurde und Job als abgeschlossen gilt => Spule anpassen + History erzeugen
    try:
        if 'filament_used_g' in payload and db_job.spool_id and will_be_finished:
            new_used = float(db_job.filament_used_g or 0)
            # Fall A: Spule wurde gewechselt
            if db_job.spool_id and db_job.spool_id != old_spool_id and new_used > 0:
                spool = session.get(Spool, db_job.spool_id)
                if spool and spool.weight_current is not None:
                    old_weight = float(spool.weight_current or 0)
                    new_weight = max(0, float(spool.weight_current) - float(new_used))
                    spool.weight_current = new_weight
                    if spool.weight_full and spool.weight_empty:
                        weight_range = float(spool.weight_full) - float(spool.weight_empty)
                        if weight_range > 0:
                            spool.remain_percent = ((new_weight - float(spool.weight_empty)) / weight_range) * 100
                            spool.remain_percent = max(0, min(100, spool.remain_percent))
                    if new_weight < 50:
                        spool.is_empty = True
                    try:
                        from app.models.weight_history import WeightHistory
                        history = WeightHistory(
                            spool_uuid=spool.tray_uuid or spool.id,
                            spool_number=spool.spool_number,
                            old_weight=old_weight,
                            new_weight=new_weight,
                            source='filamenthub_manual',
                            change_reason='job_patch',
                            user='System'
                        )
                        session.add(history)
                    except Exception:
                        pass
                    session.add(spool)
            # Fall B: gleiche Spule, Verbrauch hat sich geändert
            elif db_job.spool_id and db_job.spool_id == old_spool_id and new_used != old_used_g:
                spool = session.get(Spool, db_job.spool_id)
                if spool and spool.weight_current is not None:
                    diff = new_used - old_used_g
                    old_weight = float(spool.weight_current or 0)
                    new_weight = max(0, old_weight - diff)
                    spool.weight_current = new_weight
                    if spool.weight_full and spool.weight_empty:
                        weight_range = float(spool.weight_full) - float(spool.weight_empty)
                        if weight_range > 0:
                            spool.remain_percent = ((new_weight - float(spool.weight_empty)) / weight_range) * 100
                            spool.remain_percent = max(0, min(100, spool.remain_percent))
                    if new_weight < 50:
                        spool.is_empty = True
                    try:
                        from app.models.weight_history import WeightHistory
                        history = WeightHistory(
                            spool_uuid=spool.tray_uuid or spool.id,
                            spool_number=spool.spool_number,
                            old_weight=old_weight,
                            new_weight=new_weight,
                            source='filamenthub_manual',
                            change_reason='job_patch',
                            user='System'
                        )
                        session.add(history)
                    except Exception:
                        pass
                    session.add(spool)
    except Exception:
        # Best-effort: Fehler beim Anlegen der History sollen Patch nicht verhindern
        pass

    session.add(db_job)
    session.commit()
    session.refresh(db_job)

    return {"success": True, "job_id": job_id}


@router.post("/{job_id}/force-complete")
def force_complete_job(job_id: str, session: Session = Depends(get_session)):
    """
    Markiert einen hängengebliebenen 'running'-Job als abgeschlossen.
    Wird genutzt wenn der Drucker den FINISH-State nicht gesendet hat (z.B. A1 Mini nach Neustart).
    """
    db_job = session.get(Job, job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")

    if db_job.status != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Job hat Status '{db_job.status}' – nur 'running'-Jobs können force-completed werden"
        )

    db_job.status = "completed"
    db_job.finished_at = datetime.utcnow()
    session.add(db_job)
    session.commit()

    return {"success": True, "job_id": job_id, "new_status": "completed"}


@router.put("/{job_id}", response_model=JobRead)
def update_job(job_id: str, job: JobCreate, session: Session = Depends(get_session)):
    """Druckauftrag aktualisieren"""
    db_job = session.get(Job, job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")

    # Merke alte Werte für Differenz-Berechnung
    old_spool_id = db_job.spool_id
    old_used_g = db_job.filament_used_g or 0

    job_data = job.model_dump(exclude_unset=True)
    for key, value in job_data.items():
        setattr(db_job, key, value)

    # Wenn Spule oder Verbrauch geändert wurde: Gewicht anpassen
    new_spool_id = db_job.spool_id
    new_used_g = db_job.filament_used_g or 0

    # Fall 1: Spule wurde geändert oder hinzugefügt
    if new_spool_id and new_spool_id != old_spool_id and new_used_g > 0:
        spool = session.get(Spool, new_spool_id)
        if spool:
            # Ganzen Verbrauch abziehen
            if spool.weight_current is not None:
                    old_weight = float(spool.weight_current or 0)
                    new_weight = max(0, float(spool.weight_current) - float(new_used_g))
                    spool.weight_current = new_weight

                    # Prozentsatz neu berechnen
                    if spool.weight_full and spool.weight_empty:
                        weight_range = float(spool.weight_full) - float(spool.weight_empty)
                        if weight_range > 0:
                            spool.remain_percent = ((new_weight - float(spool.weight_empty)) / weight_range) * 100
                            spool.remain_percent = max(0, min(100, spool.remain_percent))

                    if new_weight < 50:
                        spool.is_empty = True

                    # Create history entry
                    try:
                        from app.models.weight_history import WeightHistory
                        history = WeightHistory(
                            spool_uuid=spool.tray_uuid or spool.id,
                            spool_number=spool.spool_number,
                            old_weight=old_weight,
                            new_weight=new_weight,
                            source='filamenthub_manual',
                            change_reason='job_updated',
                            user='System'
                        )
                        session.add(history)
                    except Exception:
                        pass

                    session.add(spool)

    # Fall 2: Gleiche Spule, aber Verbrauch hat sich geändert
    elif new_spool_id and new_spool_id == old_spool_id and new_used_g != old_used_g:
        spool = session.get(Spool, new_spool_id)
        if spool and spool.weight_current is not None:
            # Differenz berechnen und anpassen
            diff_g = new_used_g - old_used_g
            old_weight = float(spool.weight_current or 0)
            new_weight = max(0, float(spool.weight_current) - diff_g)
            spool.weight_current = new_weight

            # Prozentsatz neu berechnen
            if spool.weight_full and spool.weight_empty:
                weight_range = float(spool.weight_full) - float(spool.weight_empty)
                if weight_range > 0:
                    spool.remain_percent = ((new_weight - float(spool.weight_empty)) / weight_range) * 100
                    spool.remain_percent = max(0, min(100, spool.remain_percent))

            if new_weight < 50:
                spool.is_empty = True

            # Create history entry for the diff
            try:
                from app.models.weight_history import WeightHistory
                history = WeightHistory(
                    spool_uuid=spool.tray_uuid or spool.id,
                    spool_number=spool.spool_number,
                    old_weight=old_weight,
                    new_weight=new_weight,
                    source='filamenthub_manual',
                    change_reason='job_updated',
                    user='System'
                )
                session.add(history)
            except Exception:
                pass

            session.add(spool)

    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    try:
        db_job.eta_seconds = _compute_eta_for_job(db_job, session)
    except Exception:
        logger.exception("Failed to compute ETA for job_id=%s", db_job.id)
        db_job.eta_seconds = None
    return db_job


class JobSpoolUpdate(SQLModel):
    spool_id: Optional[str] = None


class JobManualUsageUpdate(SQLModel):
    """Model für manuelle Verbrauchseingabe bei Jobs ohne AMS"""
    spool_id: Optional[str] = None  # Spule zuordnen (Pflicht!)
    used_g: Optional[float] = None   # Verbrauch in Gramm
    used_mm: Optional[float] = None  # Verbrauch in Millimetern


@router.patch("/{job_id}/spool", response_model=JobRead)
def override_job_spool(job_id: str, payload: JobSpoolUpdate, session: Session = Depends(get_session)):
    """
    Spulen-Zuordnung eines Jobs überschreiben (oder entfernen).
    spool_id None entfernt die Zuordnung.
    """
    db_job = session.get(Job, job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")

    if payload.spool_id:
        spool = session.get(Spool, payload.spool_id)
        if not spool:
            raise HTTPException(status_code=400, detail="Spule nicht gefunden")

        # Status auf "Aktiv" setzen bei manueller Zuweisung (wenn nicht leer)
        if not spool.is_empty and spool.status != "Aktiv":
            spool.status = "Aktiv"
            spool.is_open = True
            session.add(spool)

    db_job.spool_id = payload.spool_id
    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    try:
        db_job.eta_seconds = _compute_eta_for_job(db_job, session)
    except Exception:
        logger.exception("Failed to compute ETA for job_id=%s", db_job.id)
        db_job.eta_seconds = None
    return db_job


@router.patch("/{job_id}/manual-usage", response_model=JobRead)
def update_manual_usage(job_id: str, payload: JobManualUsageUpdate, session: Session = Depends(get_session)):
    """
    Manuelle Verbrauchseingabe für Jobs ohne AMS-Tracking.
    Spule muss zugeordnet werden (Pflicht), dann wird Verbrauch von Spule abgezogen.
    """
    db_job = session.get(Job, job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")

    # Spule ist Pflicht!
    if not payload.spool_id:
        raise HTTPException(status_code=400, detail="Spule muss zugeordnet werden")

    spool = session.get(Spool, payload.spool_id)
    if not spool:
        raise HTTPException(status_code=400, detail="Spule nicht gefunden")

    # Spule zuordnen
    db_job.spool_id = payload.spool_id

    # Status auf "Aktiv" setzen bei manueller Zuweisung (wenn nicht leer)
    if not spool.is_empty and spool.status != "Aktiv":
        spool.status = "Aktiv"
        spool.is_open = True

    # Verbrauch setzen (mindestens einer muss angegeben sein)
    if payload.used_g is None and payload.used_mm is None:
        raise HTTPException(status_code=400, detail="Verbrauch (used_g oder used_mm) muss angegeben werden")

    if payload.used_mm is not None:
        db_job.filament_used_mm = payload.used_mm
    if payload.used_g is not None:
        db_job.filament_used_g = payload.used_g

    # Von Spule abziehen (wenn Gewicht vorhanden)
    if payload.used_g and spool.weight_current is not None:
        new_weight = max(0, float(spool.weight_current) - float(payload.used_g))
        spool.weight_current = new_weight

        # Spule als "leer" markieren wenn unter 50g
        if new_weight < 50:
            spool.is_empty = True

    session.add(spool)

    session.add(db_job)
    session.commit()
    session.refresh(db_job)
    try:
        db_job.eta_seconds = _compute_eta_for_job(db_job, session)
    except Exception:
        logger.exception("Failed to compute ETA for job_id=%s", db_job.id)
        db_job.eta_seconds = None
    return db_job


@router.post("/{job_id}/cloud-usage")
def add_cloud_usage(job_id: str, payload: dict, session: Session = Depends(get_session)):
    """
    Multi-Spool Verbrauch aus Cloud-Daten hinzufügen.

    Payload:
    {
        "usages": [
            {"spool_id": "...", "used_g": 8.22, "slot": 0},
            {"spool_id": "...", "used_g": 0.48, "slot": 3}
        ],
        "source": "bambu_cloud"
    }
    """
    from app.models.weight_history import WeightHistory

    db_job = session.get(Job, job_id)
    if not db_job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")

    usages = payload.get("usages", [])
    if not usages:
        raise HTTPException(status_code=400, detail="Keine Verbrauchsdaten angegeben")

    source = payload.get("source", "manual")
    total_weight = 0
    created_usages = []

    for idx, usage_data in enumerate(usages):
        spool_id = usage_data.get("spool_id")
        used_g = float(usage_data.get("used_g", 0) or 0)
        slot = usage_data.get("slot")

        if not spool_id or used_g <= 0:
            continue

        spool = session.get(Spool, spool_id)
        if not spool:
            continue

        # 1. JobSpoolUsage erstellen
        spool_usage = JobSpoolUsage(
            job_id=job_id,
            spool_id=spool_id,
            slot=slot,
            used_g=used_g,
            used_mm=0,  # TODO: Berechnen wenn nötig
            order_index=idx
        )
        session.add(spool_usage)
        created_usages.append(spool_usage)

        # 2. Gewicht von Spule abziehen
        old_weight = float(spool.weight_current or 0)
        new_weight = max(0, old_weight - used_g)
        spool.weight_current = new_weight

        # 3. Weight History erstellen (nur wenn spool tray_uuid hat)
        if spool.tray_uuid:
            history = WeightHistory(
                spool_uuid=spool.tray_uuid,
                spool_number=spool.spool_number,
                old_weight=old_weight,
                new_weight=new_weight,
                change_reason=f"Cloud-Import: {db_job.name}",
                source=source,
                user="System"
            )
            session.add(history)

        # 4. Spule-Status aktualisieren
        if new_weight < 50:
            spool.is_empty = True

        session.add(spool)
        total_weight += used_g

    # 5. Job-Gesamtgewicht aktualisieren
    db_job.filament_used_g = total_weight

    # 6. Erste Spule als "primäre" setzen (für Kompatibilität)
    if created_usages and created_usages[0].spool_id:
        db_job.spool_id = created_usages[0].spool_id

    session.add(db_job)
    session.commit()

    return {
        "success": True,
        "job_id": job_id,
        "usages_created": len(created_usages),
        "total_weight_g": total_weight
    }


@router.post("/{job_id}/refresh-weight-gcode")
def refresh_weight_from_gcode(
    job_id: str,
    gcode_filename: Optional[str] = None,
    dry_run: bool = False,
    confirmed_weight: Optional[float] = None,
    filament_weights_json: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """
    Lädt G-Code vom Drucker und aktualisiert Filament-Gewicht nachträglich
    
    Args:
        job_id: Job ID
        gcode_filename: Optional - Spezifischer Dateiname falls mehrere Matches
        
    Returns:
        Success: {success: true, weight: float, filename: str}
        Multiple matches: {success: false, multiple_matches: true, files: List[str]}
        Error: {success: false, error: str}
    """
    from app.services.gcode_ftp_service import get_gcode_ftp_service
    
    # Job laden
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    
    # Drucker laden
    printer = session.get(Printer, job.printer_id) if job.printer_id else None
    if not printer:
        raise HTTPException(status_code=400, detail="Kein Drucker für diesen Job gefunden")
    
    # Klipper-Drucker erkennen
    is_klipper = bool(printer and (printer.printer_type or "").lower() == "klipper")

    # Prüfe ob Drucker FTP-Zugang hat (Klipper braucht kein api_key)
    if not is_klipper and (not printer.ip_address or not printer.api_key):
        raise HTTPException(
            status_code=400,
            detail="Drucker hat keine IP-Adresse oder API-Key konfiguriert"
        )

    # -----------------------------------------------------------------------
    # [BETA] Klipper-Support: Moonraker HTTP statt FTPS
    # -----------------------------------------------------------------------
    if is_klipper:
        import httpx as _httpx
        import math as _math

        if not printer.ip_address:
            raise HTTPException(status_code=400, detail="Klipper-Drucker hat keine IP-Adresse")

        base_url = f"http://{printer.ip_address}:{printer.port or 7125}"

        def _klipper_enrich(file_list: list, hc, limit: int = 20) -> list:
            """Reichert Klipper-Dateiliste mit Gewicht + Länge aus Moonraker-Metadaten an."""
            enriched = []
            for _fi in file_list[:limit]:
                item = dict(_fi)
                try:
                    _rm = hc.get(f"{base_url}/server/files/metadata", params={"filename": _fi["name"]}, timeout=5.0)
                    if _rm.status_code == 200:
                        _m = _rm.json().get("result", {})
                        if _m.get("filament_weight_total") and float(_m["filament_weight_total"]) > 0:
                            item["weight_g"] = round(float(_m["filament_weight_total"]), 2)
                        elif _m.get("filament_total") and float(_m["filament_total"]) > 0:
                            _mm2 = float(_m["filament_total"])
                            _r2 = 0.0875
                            item["weight_g"] = round(_mm2 * (_math.pi * _r2 ** 2 * 0.1) * 1.24, 2)
                        if _m.get("filament_total") and float(_m["filament_total"]) > 0:
                            item["length_mm"] = round(float(_m["filament_total"]), 1)
                except Exception:
                    pass
                enriched.append(item)
            return enriched

        try:
            with _httpx.Client(timeout=10.0) as _hc:
                # 1. Dateiliste holen (falls kein Dateiname angegeben)
                _klipper_filename = gcode_filename
                if not _klipper_filename:
                    _lr = _hc.get(f"{base_url}/server/files/list", params={"root": "gcodes"})
                    _lr.raise_for_status()
                    _all_files = _lr.json().get("result", [])
                    _gcode_files = [
                        {
                            "name": str(f.get("path") or f.get("filename") or ""),
                            "size": f.get("size", 0),
                            "modified": f.get("modified", 0),
                            "weight_g": None,
                            "length_mm": None,
                        }
                        for f in _all_files
                        if str(f.get("path") or f.get("filename") or "").lower().endswith(".gcode")
                    ]

                    if not _gcode_files:
                        return {"success": False, "error": "Keine G-Code Dateien auf dem Drucker gefunden"}

                    # Fuzzy-Match: Job-Name mit Dateinamen abgleichen
                    _jn = (job.name or "").lower().replace(" ", "").replace("_", "").replace("-", "").replace(".gcode", "")
                    _matches = []
                    for _f in _gcode_files:
                        _fn = _f["name"].lower().replace(" ", "").replace("_", "").replace("-", "").replace(".gcode", "")
                        if len(_jn) >= 3 and _jn in _fn:
                            _matches.append(_f)
                        elif len(_fn) >= 3 and _fn in _jn:
                            _matches.append(_f)

                    if len(_matches) == 0:
                        # Kein Match → alle Dateien zeigen (mit Metadaten, max 20)
                        return {
                            "success": False,
                            "no_match": True,
                            "available_files": _klipper_enrich(_gcode_files, _hc, limit=20),
                            "message": f"Keine passende Datei für '{job.name}' gefunden",
                        }
                    elif len(_matches) > 1:
                        # Mehrere Treffer → alle Treffer mit Metadaten anzeigen
                        return {
                            "success": False,
                            "multiple_matches": True,
                            "files": _klipper_enrich(_matches, _hc, limit=20),
                            "message": f"Mehrere Dateien gefunden für '{job.name}'",
                        }
                    else:
                        _klipper_filename = _matches[0]["name"]

                # 2. Moonraker-Metadaten für diese Datei holen
                _mr = _hc.get(f"{base_url}/server/files/metadata", params={"filename": _klipper_filename})
                _mr.raise_for_status()
                _meta = _mr.json().get("result", {})

                # 3. Gewicht extrahieren
                _w = None
                # Direktes Gewicht in Gramm (slicer hat es gesetzt)
                if _meta.get("filament_weight_total") and float(_meta["filament_weight_total"]) > 0:
                    _w = float(_meta["filament_weight_total"])
                # Fallback: filament_total in mm → Gramm umrechnen
                elif _meta.get("filament_total") and float(_meta["filament_total"]) > 0:
                    _mm = float(_meta["filament_total"])
                    _density = 1.24  # PLA-Standard g/cm³
                    if job.spool_id:
                        _sp = session.get(Spool, job.spool_id)
                        if _sp and _sp.material_id:
                            try:
                                from app.models.material import Material as _Mat
                                _mat = session.get(_Mat, _sp.material_id)
                                if _mat and _mat.density and float(_mat.density) > 0:
                                    _density = float(_mat.density)
                            except Exception:
                                pass
                    _r_cm = 0.0875  # 1.75mm Filament-Radius in cm
                    _w = _mm * (_math.pi * _r_cm ** 2 * 0.1) * _density

                if _w is None or _w <= 0:
                    return {
                        "success": False,
                        "error": f"Kein Gewicht in '{_klipper_filename}' gefunden "
                                 f"(filament_total={_meta.get('filament_total')}, "
                                 f"filament_weight_total={_meta.get('filament_weight_total')})",
                    }

                _w = round(_w, 2)

                # Dry-run: Vorschau zurückgeben ohne zu speichern
                if dry_run:
                    _dur = None
                    if job.started_at and job.finished_at:
                        _dur = int((job.finished_at - job.started_at).total_seconds() / 60)
                    return {
                        "needs_confirmation": True,
                        "weight": _w,
                        "filename": _klipper_filename,
                        "job_name": job.name,
                        "duration_min": _dur,
                    }

        except _httpx.RequestError as _e:
            return {"success": False, "error": f"Moonraker nicht erreichbar ({base_url}): {_e}"}
        except Exception as _e:
            logger.error(f"[KLIPPER GCODE REFRESH] Fehler für job={job_id}: {_e}", exc_info=True)
            return {"success": False, "error": f"Fehler beim Klipper G-Code Download: {_e}"}

        # Gewicht in DB schreiben (identisch zum Bambu-Pfad)
        _old_w = float(job.filament_used_g or 0)
        _diff_w = _w - _old_w
        job.filament_used_g = _w
        if (job.status or "").lower() in ("pending_weight",) and _w > 0 and job.finished_at is not None:
            job.status = "completed"

        if job.spool_id and _diff_w != 0:
            _spool_k = session.get(Spool, job.spool_id)
            if _spool_k and _spool_k.weight_current is not None:
                _old_sw = float(_spool_k.weight_current or 0)
                _new_sw = max(0.0, _old_sw - _diff_w)
                _spool_k.weight_current = _new_sw
                if _spool_k.weight_full and _spool_k.weight_empty:
                    _wr = float(_spool_k.weight_full) - float(_spool_k.weight_empty)
                    if _wr > 0:
                        _spool_k.remain_percent = max(0, min(100, (_new_sw - float(_spool_k.weight_empty)) / _wr * 100))
                try:
                    from app.models.weight_history import WeightHistory as _WH
                    session.add(_WH(
                        spool_uuid=_spool_k.tray_uuid or _spool_k.id,
                        spool_number=_spool_k.spool_number,
                        old_weight=_old_sw,
                        new_weight=_new_sw,
                        source="print_consumed",
                        change_reason="klipper_gcode_weight_refresh",
                        user="System",
                    ))
                except Exception:
                    pass
                session.add(_spool_k)

        session.add(job)
        session.commit()
        logger.info(f"[KLIPPER GCODE REFRESH] ✅ job={job_id} {_old_w:.1f}g → {_w:.1f}g ({_klipper_filename})")
        return {
            "success": True,
            "weight": _w,
            "filename": _klipper_filename,
            "weight_diff": _diff_w,
            "message": f"Gewicht aktualisiert: {_w:.1f}g aus {_klipper_filename}",
        }
    # -----------------------------------------------------------------------
    # Ende Klipper-Pfad — ab hier nur noch Bambu/FTPS
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # X1C: FTPS-First, Bambu Cloud nur als Fallback bei FTPS-Fehler
    # -----------------------------------------------------------------------
    is_x1c = (printer.model or "").upper() in ("X1C", "X1") or (printer.series or "").upper() == "X"

    if is_x1c and not is_klipper:
        from app.services.gcode_ftp_service import SimpleFTPS as _SimpleFTPS_X1C
        from app.services.gcode_ftp_service import FTPLibFTPS as _FTPLibFTPS_X1C

        _x1c_weight: Optional[float] = None
        _x1c_weights_list: Optional[list] = None
        _x1c_filename: str = gcode_filename or f"[X1C] {job.name}"
        _x1c_conn_method = "ftps"

        # --- confirmed_weight: direkt uebernehmen ohne FTPS/Cloud ---
        if confirmed_weight is not None:
            _x1c_weight = round(float(confirmed_weight), 2)
        else:
            # ----------------------------------------------------------
            # SCHRITT 1a: SimpleFTPS-Direktverbindung zum X1C
            # Kurzer Timeout (10s) für schnelles Fail-Fast
            # ----------------------------------------------------------
            _ftps_x1c_error = None
            _ftps_x1c_files: list = []
            try:
                _ftps_x1c = _SimpleFTPS_X1C(timeout=10)
                _ftps_x1c.connect(printer.ip_address, 990, retries=1)
                _ftps_x1c.login("bblp", printer.api_key)
                _ftps_x1c.cwd("/cache")
                _ftps_x1c_files = _ftps_x1c.list_dir(with_metadata=True)
                _ftps_x1c.quit()
                logger.info(f"[X1C FTPS] SimpleFTPS OK: {len(_ftps_x1c_files)} Dateien in /cache")
            except Exception as _ftps_e:
                _ftps_x1c_error = str(_ftps_e)
                logger.warning(f"[X1C FTPS] SimpleFTPS fehlgeschlagen ({printer.ip_address}:990): {_ftps_e}")

            # ----------------------------------------------------------
            # SCHRITT 1b: FTPLibFTPS als zweiten FTPS-Versuch
            # ----------------------------------------------------------
            if _ftps_x1c_error:
                try:
                    logger.info(f"[X1C FTPS] Versuche FTPLibFTPS Fallback fuer {printer.ip_address}:990")
                    _ftps_lib_x1c = _FTPLibFTPS_X1C(timeout=10)
                    _ftps_lib_x1c.connect(printer.ip_address, 990)
                    _ftps_lib_x1c.login("bblp", printer.api_key)
                    _ftps_lib_x1c.cwd("/cache")
                    _ftps_x1c_files = _ftps_lib_x1c.list_dir(with_metadata=True)
                    _ftps_lib_x1c.quit()
                    _ftps_x1c_error = None  # Erfolg!
                    _x1c_conn_method = "ftps_ftplib"
                    logger.info(f"[X1C FTPS] FTPLibFTPS OK: {len(_ftps_x1c_files)} Dateien in /cache")
                except Exception as _ftps_lib_e:
                    _ftps_x1c_error = f"SimpleFTPS: {_ftps_x1c_error} | FTPLibFTPS: {_ftps_lib_e}"
                    logger.warning(f"[X1C FTPS] FTPLibFTPS auch fehlgeschlagen: {_ftps_lib_e}")

            if not _ftps_x1c_error:
                # ----------------------------------------------------------
                # FTPS OK: .3mf Dateien filtern (X1C-spezifisch) + Job-Match
                # ----------------------------------------------------------
                _x1c_3mf_files = [f for f in _ftps_x1c_files if f["name"].lower().endswith(".3mf")]

                if not gcode_filename:
                    # Kein Dateiname vorgegeben → Job-Namen-Match
                    if not _x1c_3mf_files:
                        return {
                            "success": False,
                            "connection_method": "ftps",
                            "error": "Keine .3mf Dateien im X1C Cache (/cache) gefunden",
                        }

                    _x1c_job_norm = (
                        (job.name or "").lower()
                        .replace(" ", "").replace("_", "").replace("-", "").replace(".3mf", "")
                    )

                    _x1c_ftps_matches = []
                    for _finfo in _x1c_3mf_files:
                        _fn_n = (
                            _finfo["name"].lower()
                            .replace(" ", "").replace("_", "").replace("-", "").replace(".3mf", "")
                        )
                        if len(_x1c_job_norm) >= 3 and _x1c_job_norm in _fn_n:
                            _x1c_ftps_matches.append(_finfo)
                        elif len(_fn_n) >= 3 and _fn_n in _x1c_job_norm:
                            _x1c_ftps_matches.append(_finfo)

                    def _x1c_file_obj(f: dict) -> dict:
                        _ext = f["name"].rsplit(".", 1)[-1].lower() if "." in f["name"] else ""
                        return {
                            "name": f["name"],
                            "extension": _ext,
                            "mtime_str": f.get("mtime_str") or "",
                            "size_kb": round((f.get("size") or 0) / 1024, 1),
                            "weight_g": None,
                        }

                    if len(_x1c_ftps_matches) == 0:
                        _dur_nm = None
                        if job.started_at and job.finished_at:
                            _dur_nm = int((job.finished_at - job.started_at).total_seconds() / 60)
                        return {
                            "success": False,
                            "no_match": True,
                            "available_files": [_x1c_file_obj(f) for f in _x1c_3mf_files],
                            "connection_method": "ftps",
                            "job_name": job.name,
                            "duration_min": _dur_nm,
                            "message": f"Keine passende Datei fuer '{job.name}' gefunden",
                        }
                    elif len(_x1c_ftps_matches) > 1:
                        return {
                            "success": False,
                            "multiple_matches": True,
                            "files": [_x1c_file_obj(f) for f in _x1c_ftps_matches],
                            "connection_method": "ftps",
                            "message": f"Mehrere Dateien gefunden fuer '{job.name}'",
                        }
                    else:
                        gcode_filename = _x1c_ftps_matches[0]["name"]
                        _x1c_filename = gcode_filename

                # Gewicht aus .3mf via FTPS extrahieren
                try:
                    _ftp_svc_x1c = get_gcode_ftp_service()
                    _w_result_x1c = _ftp_svc_x1c.download_gcode_metrics(
                        printer_ip=printer.ip_address,
                        api_key=printer.api_key,
                        task_id=job.task_id or job_id,
                        gcode_filename=gcode_filename,
                    )
                    if _w_result_x1c:
                        _x1c_w_val = _w_result_x1c.get("weight_g")
                        if _x1c_w_val and float(_x1c_w_val) > 0:
                            _x1c_weight = round(float(_x1c_w_val), 2)
                        _wl = _w_result_x1c.get("filament_weights_g")
                        if _wl:
                            _x1c_weights_list = _wl
                except Exception as _we:
                    logger.warning(f"[X1C FTPS WEIGHT] Extraktion fehlgeschlagen: {_we}")

            else:
                # ----------------------------------------------------------
                # SCHRITT 2: FTPS fehlgeschlagen → Cloud-Fallback fuer Gewicht
                # ----------------------------------------------------------
                _x1c_conn_method = "cloud_fallback"
                import httpx as _httpx_x1c
                from sqlmodel import select as _select_x1c
                from app.models.bambu_cloud_config import BambuCloudConfig as _BCC
                from app.services.token_encryption import decrypt_token as _dt

                _cloud_cfg = session.exec(_select_x1c(_BCC)).first()
                if not _cloud_cfg or not _cloud_cfg.access_token_encrypted:
                    return {
                        "success": False,
                        "connection_error": True,
                        "error_message": f"Verbindung zu {printer.name} ({printer.ip_address}:990) fehlgeschlagen",
                        "error_detail": _ftps_x1c_error,
                        "printer_ip": printer.ip_address or "",
                        "printer_model": printer.model or "",
                        "connection_method": "ftps_failed_no_cloud",
                    }

                _access_token = _dt(_cloud_cfg.access_token_encrypted)
                _region = _cloud_cfg.region or "eu"
                _base_url = {
                    "eu": "https://api.bambulab.com",
                    "us": "https://api.bambulab.com",
                    "cn": "https://api.bambulab.cn",
                }.get(_region, "https://api.bambulab.com")

                _job_start_x1c = None
                if job.started_at:
                    if isinstance(job.started_at, str):
                        try:
                            _job_start_x1c = datetime.fromisoformat(job.started_at.replace('Z', '+00:00'))
                        except Exception:
                            pass
                    else:
                        _job_start_x1c = job.started_at

                _printer_serial_x1c = printer.cloud_serial or printer.bambu_device_id or ""
                _printer_name_x1c = printer.name or ""

                try:
                    with _httpx_x1c.Client(timeout=20.0) as _hc:
                        _resp = _hc.get(
                            f"{_base_url}/v1/user-service/my/tasks",
                            params={"limit": 50},
                            headers={
                                "Authorization": f"Bearer {_access_token}",
                                "Content-Type": "application/json",
                                "User-Agent": "bambu_network_agent/01.09.05.01",
                                "X-BBL-Client-Name": "OrcaSlicer",
                                "X-BBL-Client-Type": "slicer",
                                "X-BBL-Client-Version": "01.09.05.01",
                            }
                        )
                    if _resp.status_code == 401:
                        return {
                            "success": False,
                            "connection_error": True,
                            "error_message": "FTPS fehlgeschlagen — Cloud-Token ungueltig (HTTP 401)",
                            "error_detail": f"FTPS: {_ftps_x1c_error}",
                            "printer_model": printer.model or "",
                            "connection_method": "ftps_failed_cloud_error",
                        }
                    if _resp.status_code >= 400:
                        return {
                            "success": False,
                            "connection_error": True,
                            "error_message": f"FTPS fehlgeschlagen — Cloud API Fehler (HTTP {_resp.status_code})",
                            "error_detail": _ftps_x1c_error,
                            "printer_model": printer.model or "",
                            "connection_method": "ftps_failed_cloud_error",
                        }
                    _cloud_data = _resp.json()
                except Exception as _exc:
                    return {
                        "success": False,
                        "connection_error": True,
                        "error_message": f"Verbindung fehlgeschlagen — FTPS und Cloud nicht erreichbar",
                        "error_detail": f"FTPS: {_ftps_x1c_error} | Cloud: {_exc}",
                        "printer_model": printer.model or "",
                        "connection_method": "ftps_failed_cloud_error",
                    }

                # Task-Liste extrahieren
                if isinstance(_cloud_data, list):
                    _task_list = _cloud_data
                elif isinstance(_cloud_data, dict):
                    _task_list = _cloud_data.get("tasks") or _cloud_data.get("hits") or []
                    if isinstance(_task_list, dict):
                        _task_list = _task_list.get("hits", [])
                else:
                    _task_list = []

                logger.info(f"[X1C CLOUD FALLBACK] {len(_task_list)} Tasks, suche '{job.name}'")

                # Auto-Match (nur Gewicht, keine Task-Liste zurueckgeben)
                _job_name_lc = (job.name or "").lower()
                for _t in _task_list:
                    _tt = (_t.get("title") or "").lower()
                    _name_ok = _tt == _job_name_lc or _tt in _job_name_lc or _job_name_lc in _tt
                    if not _name_ok:
                        continue
                    _dev_id = _t.get("deviceId") or _t.get("device_id") or ""
                    _dev_name = _t.get("deviceName") or _t.get("device_name") or ""
                    _dev_ok = bool(_dev_id and _printer_serial_x1c and _dev_id == _printer_serial_x1c)
                    if not _dev_ok and _dev_name and _printer_name_x1c:
                        _dev_ok = (
                            _dev_name.lower() == _printer_name_x1c.lower()
                            or _dev_name.lower() in _printer_name_x1c.lower()
                            or _printer_name_x1c.lower() in _dev_name.lower()
                        )
                    _t_start_str = _t.get("startTime") or _t.get("start_time") or ""
                    _time_ok = False
                    if _t_start_str and _job_start_x1c:
                        try:
                            _ts = datetime.fromisoformat(_t_start_str.replace('Z', ''))
                            _jsc = _job_start_x1c.replace(tzinfo=None) if (hasattr(_job_start_x1c, 'tzinfo') and _job_start_x1c.tzinfo) else _job_start_x1c
                            _time_ok = abs((_ts - _jsc).total_seconds()) < 86400
                        except Exception:
                            pass
                    if _name_ok and (_dev_ok or _time_ok):
                        _w_total = 0.0
                        _ams = _t.get("amsDetailMapping") or _t.get("ams_mapping") or []
                        if _ams:
                            _w_total = sum(float(m.get("weight", 0) or 0) for m in _ams)
                        if _w_total <= 0:
                            _w_total = float(_t.get("weight", 0) or 0)
                        if _w_total > 0:
                            _x1c_weight = _w_total
                            _x1c_filename = f"[Cloud] {_t.get('title', job.name)}"
                            logger.info(f"[X1C CLOUD FALLBACK] Match: '{_t.get('title')}' => {_w_total:.1f}g")
                        break

                if _x1c_weight is None or _x1c_weight <= 0:
                    _dur_nomatch = None
                    if job.started_at and job.finished_at:
                        _dur_nomatch = int((job.finished_at - job.started_at).total_seconds() / 60)
                    return {
                        "success": False,
                        "needs_manual": True,
                        "connection_error": True,
                        "error_message": f"FTPS fehlgeschlagen — Cloud: kein passender Job fuer '{job.name}' gefunden",
                        "error_detail": f"FTPS: {_ftps_x1c_error}",
                        "connection_method": "ftps_failed_cloud_no_match",
                        "job_name": job.name,
                        "duration_min": _dur_nomatch,
                    }

        if _x1c_weight is None or _x1c_weight <= 0:
            return {
                "success": False,
                "error": f"Kein Gewicht gefunden fuer {_x1c_filename} — bitte manuell eingeben",
            }

        if dry_run:
            _dur_x1c = None
            if job.started_at and job.finished_at:
                _dur_x1c = int((job.finished_at - job.started_at).total_seconds() / 60)
            return {
                "needs_confirmation": True,
                "weight": round(_x1c_weight, 2),
                "filename": _x1c_filename,
                "job_name": job.name,
                "duration_min": _dur_x1c,
                "connection_method": _x1c_conn_method,
                "filament_weights_g": _x1c_weights_list,
            }

        _x1c_old_w = job.filament_used_g or 0
        _x1c_diff = _x1c_weight - _x1c_old_w
        job.filament_used_g = _x1c_weight
        if (job.status or "").lower() == "pending_weight" and _x1c_weight > 0 and job.finished_at is not None:
            job.status = "completed"
        # Per-Spool Gewichte: aus Frontend-Bestätigung (filament_weights_json) oder FTPS-Download
        _per_spool_w: Optional[list] = None
        if filament_weights_json:
            try:
                import json as _json_mod
                _per_spool_w = _json_mod.loads(filament_weights_json)
            except Exception:
                pass
        if not _per_spool_w and _x1c_weights_list:
            _per_spool_w = _x1c_weights_list

        if _per_spool_w:
            # Multicolor: Jede Spule einzeln aktualisieren via JobSpoolUsage
            from sqlmodel import select as _sel_su
            from app.models.job import JobSpoolUsage as _JSU
            _usages = session.exec(_sel_su(_JSU).where(_JSU.job_id == job_id)).all()
            _usages_by_slot = {u.slot: u for u in _usages if u.slot is not None}
            for _slot_i, _sw in enumerate(_per_spool_w):
                _u = _usages_by_slot.get(_slot_i)
                if not _u:
                    continue
                _u.used_g = round(float(_sw), 2)
                session.add(_u)
                if _u.spool_id and float(_sw) > 0:
                    _u_spool = session.get(Spool, _u.spool_id)
                    if _u_spool and _u_spool.weight_current is not None:
                        _u_sw_old = float(_u_spool.weight_current)
                        _u_sw_new = max(0.0, _u_sw_old - float(_sw))
                        _u_spool.weight_current = _u_sw_new
                        if _u_spool.weight_full and _u_spool.weight_empty:
                            _u_wr = float(_u_spool.weight_full) - float(_u_spool.weight_empty)
                            if _u_wr > 0:
                                _u_spool.remain_percent = max(0, min(100, (
                                    _u_sw_new - float(_u_spool.weight_empty)) / _u_wr * 100))
                        try:
                            from app.models.weight_history import WeightHistory as _WH_ms
                            session.add(_WH_ms(
                                spool_uuid=_u_spool.tray_uuid or _u_spool.id,
                                spool_number=_u_spool.spool_number,
                                old_weight=_u_sw_old,
                                new_weight=_u_sw_new,
                                source="print_consumed",
                                change_reason="x1c_weight_refresh_multispool",
                                user="System",
                            ))
                        except Exception:
                            pass
                        session.add(_u_spool)
            logger.info(f"[X1C WEIGHT] Multi-Spool: {len(_per_spool_w)} Filamente → {_per_spool_w}")
        elif job.spool_id and _x1c_diff != 0:
            # Einzelspule: klassische Logik
            _x1c_spool = session.get(Spool, job.spool_id)
            if _x1c_spool and _x1c_spool.weight_current is not None:
                _x1c_sw_old = float(_x1c_spool.weight_current or 0)
                _x1c_sw_new = max(0, float(_x1c_spool.weight_current) - _x1c_diff)
                _x1c_spool.weight_current = _x1c_sw_new
                if _x1c_spool.weight_full and _x1c_spool.weight_empty:
                    _wr = float(_x1c_spool.weight_full) - float(_x1c_spool.weight_empty)
                    if _wr > 0:
                        _x1c_spool.remain_percent = max(0, min(100, (
                            (_x1c_sw_new - float(_x1c_spool.weight_empty)) / _wr
                        ) * 100))
                try:
                    from app.models.weight_history import WeightHistory as _WH2
                    session.add(_WH2(
                        spool_uuid=_x1c_spool.tray_uuid or _x1c_spool.id,
                        spool_number=_x1c_spool.spool_number,
                        old_weight=_x1c_sw_old,
                        new_weight=_x1c_sw_new,
                        source="print_consumed",
                        change_reason="x1c_weight_refresh",
                        user="System",
                    ))
                except Exception:
                    pass
                session.add(_x1c_spool)
        session.add(job)
        session.commit()
        logger.info(f"[X1C WEIGHT] job={job_id} {_x1c_old_w:.1f}g => {_x1c_weight:.1f}g via {_x1c_conn_method}")
        return {
            "success": True,
            "weight": _x1c_weight,
            "filename": _x1c_filename,
            "weight_diff": _x1c_diff,
            "connection_method": _x1c_conn_method,
            "message": f"Gewicht aktualisiert: {_x1c_weight:.1f}g ({_x1c_conn_method})"
        }

    # -----------------------------------------------------------------------
    # Bambu FTPS-Pfad (A1 Mini, A1, P-Series)
    # -----------------------------------------------------------------------
    try:
        ftp_service = get_gcode_ftp_service()

        def _enrich_files_with_weight(files: list[dict]) -> list[dict]:
            """
            Erweitert Dateiliste um `weight_g` (falls aus Datei extrahierbar).
            Wird nur fuer Dateiauswahl-Dialog genutzt.
            """
            enriched: list[dict] = []
            weight_cache: dict[str, Optional[dict]] = {}
            task_id_for_lookup = job.task_id or job_id

            for file_info in files:
                filename = file_info.get("name")
                item = dict(file_info)
                item["weight_g"] = None
                item["length_mm"] = None

                if filename:
                    if filename not in weight_cache:
                        try:
                            metrics = ftp_service.download_gcode_metrics(
                                printer_ip=printer.ip_address,
                                api_key=printer.api_key,
                                task_id=task_id_for_lookup,
                                gcode_filename=filename
                            )
                            weight_cache[filename] = metrics
                        except Exception:
                            weight_cache[filename] = None
                    metrics_val = weight_cache.get(filename) or {}
                    weight_val = metrics_val.get("weight_g")
                    length_val = metrics_val.get("length_mm")
                    if weight_val and weight_val > 0:
                        item["weight_g"] = round(float(weight_val), 2)
                    if length_val and length_val > 0:
                        item["length_mm"] = round(float(length_val), 1)

                enriched.append(item)

            return enriched
        
        _all_gcode_files = None  # Wird für dry_run Response genutzt

        # Falls kein spezifischer Dateiname gegeben: Suche nach passenden Files
        if not gcode_filename:
            # Liste alle G-Code Files im Cache auf
            from app.services.gcode_ftp_service import SimpleFTPS

            # FTPS-Verbindung zum Bambu-Drucker
            ftps = SimpleFTPS(timeout=60)
            ftps.connect(printer.ip_address, 990, retries=3)
            ftps.login("bblp", printer.api_key)
            ftps.cwd("/cache")

            file_list = ftps.list_dir(with_metadata=True)  # Mit Timestamps!
            ftps.quit()

            # A1/A1 Mini: nur .gcode Dateien (X1C wird oben separat behandelt)
            gcode_files = [
                f for f in file_list
                if f["name"].lower().endswith(".gcode")
            ]

            if not gcode_files:
                return {
                    "success": False,
                    "connection_method": "ftps",
                    "error": "Keine .gcode Dateien im Drucker-Cache (/cache) gefunden"
                }

            def _build_file_obj(f: dict) -> dict:
                _ext = f["name"].rsplit(".", 1)[-1].lower() if "." in f["name"] else ""
                return {
                    "name": f["name"],
                    "extension": _ext,
                    "mtime_str": f.get("mtime_str") or "",
                    "size_kb": round((f.get("size") or 0) / 1024, 1),
                    "weight_g": None,  # Wird beim Klick geladen
                }

            # Versuche Job-Namen mit Dateien zu matchen
            job_name_normalized = (
                job.name.lower()
                .replace(" ", "")
                .replace("_", "")
                .replace("-", "")
            )
            # Entferne .gcode falls Jobname sie enthält
            job_name_normalized = job_name_normalized.replace(".gcode", "")

            matches = []
            for file_info in gcode_files:
                filename = file_info["name"]
                filename_normalized = (
                    filename.lower()
                    .replace(" ", "")
                    .replace("_", "")
                    .replace("-", "")
                    .replace(".gcode", "")
                )

                # Substring-Match (mindestens 3 Zeichen)
                if len(job_name_normalized) >= 3 and job_name_normalized in filename_normalized:
                    matches.append(file_info)
                elif len(filename_normalized) >= 3 and filename_normalized in job_name_normalized:
                    matches.append(file_info)

            if len(matches) == 0:
                # Kein Match: Gib alle verfügbaren Dateien zurück (Gewicht lädt beim Klick)
                return {
                    "success": False,
                    "no_match": True,
                    "available_files": [_build_file_obj(f) for f in gcode_files],
                    "connection_method": "ftps",
                    "message": f"Keine passende Datei fuer '{job.name}' gefunden"
                }
            elif len(matches) > 1:
                # Mehrere Matches: User muss wählen
                return {
                    "success": False,
                    "multiple_matches": True,
                    "files": [_build_file_obj(f) for f in matches],
                    "connection_method": "ftps",
                    "message": f"Mehrere Dateien gefunden fuer '{job.name}'"
                }
            else:
                # Genau 1 Match: Verwenden — alle Dateien für dry_run merken
                gcode_filename = matches[0]["name"]
                _all_gcode_files = gcode_files  # Komplette Liste für dry_run Response
        
        # Download G-Code und extrahiere Gewicht
        logger.info(
            f"[MANUAL GCODE REFRESH] Downloading {gcode_filename} "
            f"for job={job_id} ({job.name})"
        )
        
        # Bei confirmed_weight FTP-Download überspringen
        if confirmed_weight is not None:
            weight = round(float(confirmed_weight), 2)
        else:
            weight = ftp_service.download_gcode_weight(
                printer_ip=printer.ip_address,
                api_key=printer.api_key,
                task_id=job.task_id or job_id,  # Fallback zu job_id für Logging
                gcode_filename=gcode_filename
            )

            if weight is None or weight <= 0:
                return {
                    "success": False,
                    "error": f"Kein Gewicht in {gcode_filename} gefunden"
                }

        # Dry-run: Vorschau zurückgeben ohne zu speichern
        if dry_run:
            _dur = None
            if job.started_at and job.finished_at:
                _dur = int((job.finished_at - job.started_at).total_seconds() / 60)
            resp: dict = {
                "needs_confirmation": True,
                "weight": round(weight, 2),
                "filename": gcode_filename,
                "job_name": job.name,
                "duration_min": _dur,
            }
            # Alle verfügbaren Dateien mitschicken damit User wechseln kann
            if _all_gcode_files:
                resp["available_files"] = _all_gcode_files
            return resp

        # Update Job Gewicht
        old_weight = job.filament_used_g or 0
        weight_diff = weight - old_weight
        
        job.filament_used_g = weight
        if (job.status or "").lower() == "pending_weight" and weight > 0 and job.finished_at is not None:
            job.status = "completed"
        
        # Update Spule falls vorhanden
        if job.spool_id and weight_diff != 0:
            spool = session.get(Spool, job.spool_id)
            if spool and spool.weight_current is not None:
                old_weight = float(spool.weight_current or 0)
                new_weight = max(0, float(spool.weight_current) - weight_diff)
                spool.weight_current = new_weight
                
                # Prozentsatz neu berechnen
                if spool.weight_full and spool.weight_empty:
                    weight_range = float(spool.weight_full) - float(spool.weight_empty)
                    if weight_range > 0:
                        spool.remain_percent = ((new_weight - float(spool.weight_empty)) / weight_range) * 100
                        spool.remain_percent = max(0, min(100, spool.remain_percent))
                
                # Create WeightHistory for gcode refresh (print consumption)
                try:
                    from app.models.weight_history import WeightHistory
                    history = WeightHistory(
                        spool_uuid=spool.tray_uuid or spool.id,
                        spool_number=spool.spool_number,
                        old_weight=old_weight,
                        new_weight=new_weight,
                        source='print_consumed',
                        change_reason='gcode_weight_refresh',
                        user='System'
                    )
                    session.add(history)
                except Exception:
                    logger.exception("[MANUAL GCODE REFRESH] WeightHistory create failed for spool_id=%s", spool.id)

                session.add(spool)
        
        session.add(job)
        session.commit()
        
        logger.info(
            f"[MANUAL GCODE REFRESH] ✅ Updated job={job_id} weight: "
            f"{old_weight:.1f}g → {weight:.1f}g (diff={weight_diff:+.1f}g) from {gcode_filename}"
        )
        
        return {
            "success": True,
            "weight": weight,
            "filename": gcode_filename,
            "weight_diff": weight_diff,
            "message": f"Gewicht aktualisiert: {weight:.1f}g aus {gcode_filename}"
        }
        
    except Exception as e:
        logger.error(
            f"[MANUAL GCODE REFRESH] Error for job={job_id}: {e}",
            exc_info=True
        )
        _err_str = str(e)
        # Erkennbare Verbindungsfehler als connection_error markieren
        _is_conn_err = any(kw in _err_str.lower() for kw in [
            "connection", "refused", "timeout", "timed out", "ssl", "ftps",
            "errno", "port", "network", "unreachable", "reset by peer",
        ])
        if _is_conn_err:
            return {
                "success": False,
                "connection_error": True,
                "error_message": f"Verbindung zu {printer.name} ({printer.ip_address}:990) fehlgeschlagen",
                "error_detail": _err_str,
                "printer_ip": printer.ip_address or "",
                "printer_model": printer.model or "",
                "connection_method": "ftps_failed",
            }
        return {
            "success": False,
            "error": f"Fehler beim G-Code Download: {_err_str}"
        }


@router.delete("/{job_id}")
def delete_job(job_id: str, session: Session = Depends(get_session)):
    """Druckauftrag löschen"""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Druckauftrag nicht gefunden")
    
    has_spool_usage = session.exec(
        select(JobSpoolUsage.id).where(JobSpoolUsage.job_id == job_id)
    ).first()
    if has_spool_usage:
        raise HTTPException(
            status_code=409,
            detail="Job kann nicht gelöscht werden, weil Verbrauchshistorie vorhanden ist",
        )
    session.delete(job)
    session.commit()
    return {"success": True, "message": "Druckauftrag gelöscht"}
