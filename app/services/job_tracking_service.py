"""
Job Tracking Service - Zentrale Verwaltung für Job-Tracking und Filament-Verbrauch

Verwaltet:
- Aktive Jobs pro Drucker (RAM-basiert)
- Job-Status-Übergänge (IDLE -> RUNNING -> FINISH)
- Filament-Verbrauch Berechnung
- Spulen-Gewicht Updates
- Multi-Spool Job Tracking

Wird genutzt von:
- mqtt_runtime.py (Live MQTT Messages)
- mqtt_routes.py (HTTP API Fallback)
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlmodel import Session, select
import logging

from app.models.job import Job
from app.models.spool import Spool
from app.models.printer import Printer
from app.database import engine
from app.routes.notification_routes import trigger_notification_sync


class JobTrackingService:
    """Singleton Service für Job-Tracking und Verbrauch-Berechnung"""

    def __init__(self):
        self.active_jobs: Dict[str, Dict[str, Any]] = {}  # cloud_serial -> job_info
        self.last_gstate: Dict[str, str] = {}  # cloud_serial -> last_state
        self.logger = logging.getLogger("job_tracking")

    def _calc_usage(
        self,
        spool: Optional[Spool],
        start_remain: Optional[float],
        end_remain: Optional[float],
        start_total_len: Optional[int]
    ) -> tuple[float, float]:
        """
        Berechnet Verbrauch in mm und g

        Args:
            spool: Spulen-Objekt (für Gewichtsberechnung)
            start_remain: Start-Restmenge in %
            end_remain: End-Restmenge in %
            start_total_len: Totale Länge in mm

        Returns:
            (used_mm, used_g)
        """
        if start_remain is None or end_remain is None:
            return 0.0, 0.0

        used_percent = max(0.0, float(start_remain) - float(end_remain))

        # Länge in mm
        used_mm = (used_percent / 100.0) * float(start_total_len) if start_total_len else 0.0

        # Gewicht in g
        used_g = 0.0
        if spool and spool.weight_full is not None and spool.weight_empty is not None:
            used_g = (used_percent / 100.0) * (float(spool.weight_full) - float(spool.weight_empty))

        return used_mm, used_g

    def _find_tray(self, ams_units: List[Dict[str, Any]], slot: Optional[int]) -> Optional[Dict[str, Any]]:
        """Findet Tray-Info für einen bestimmten Slot"""
        if slot is None:
            return None

        for unit in ams_units or []:
            trays = unit.get("trays") or []
            for tray in trays:
                tid = tray.get("tray_id") if isinstance(tray, dict) else None
                tid = tid if tid is not None else (tray.get("id") if isinstance(tray, dict) else None)
                if tid is not None and int(tid) == int(slot):
                    return tray
        return None

    def _finalize_current(
        self,
        session: Session,
        info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Berechnet finalen Verbrauch für aktuellen Slot

        Returns:
            {"spool_id": str, "slot": int, "used_mm": float, "used_g": float}
        """
        if info.get("slot") is None:
            return None

        spool = session.get(Spool, info.get("spool_id")) if info.get("spool_id") else None

        used_mm, used_g = self._calc_usage(
            spool,
            info.get("start_remain"),
            info.get("last_remain"),
            info.get("start_total_len")
        )

        return {
            "spool_id": info.get("spool_id"),
            "slot": info.get("slot"),
            "used_mm": used_mm,
            "used_g": used_g
        }

    def process_message(
        self,
        cloud_serial: str,
        parsed_payload: Dict[str, Any],
        printer_id: Optional[str],
        ams_data: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Hauptfunktion: Verarbeitet eine MQTT Message für Job-Tracking

        Args:
            cloud_serial: Drucker Serial (eindeutige ID)
            parsed_payload: Geparste MQTT Payload
            printer_id: Drucker-ID aus Datenbank
            ams_data: Geparste AMS-Daten (optional)

        Returns:
            Job-Info dict oder None
        """
        if not cloud_serial or not printer_id:
            return None

        # Aktuellen Status extrahieren
        current_gstate = (
            parsed_payload.get("print", {}).get("gcode_state") or
            parsed_payload.get("gcode_state") or
            ""
        ).upper()

        # Vorherigen Status merken
        prev_gstate = self.last_gstate.get(cloud_serial)
        self.last_gstate[cloud_serial] = current_gstate

        # Hat dieser Drucker einen aktiven Job?
        has_active_job = cloud_serial in self.active_jobs

        # State-Mapping für Bambu Lab Drucker
        PRINT_STATES = {
            "PRINTING", "RUNNING",
            "PURGING", "CHANGING_FILAMENT", "CALIBRATING"  # Zählt als aktiver Druck
        }
        COMPLETED_STATES = {"FINISH", "FINISHED", "COMPLETED", "COMPLETE"}
        FAILED_STATES = {"FAILED", "ERROR", "EXCEPTION"}
        ABORTED_STATES = {"ABORT", "ABORTED", "STOPPED", "CANCELLED", "CANCELED"}

        # ===================================================================
        # JOB START
        # ===================================================================
        if not has_active_job and current_gstate in PRINT_STATES:
            return self._handle_job_start(
                cloud_serial,
                parsed_payload,
                printer_id,
                ams_data
            )

        # ===================================================================
        # JOB RUNNING (Update)
        # ===================================================================
        if has_active_job and current_gstate in PRINT_STATES:
            return self._handle_job_update(
                cloud_serial,
                parsed_payload,
                ams_data
            )

        # ===================================================================
        # JOB FINISH
        # ===================================================================
        if has_active_job and (
            current_gstate in COMPLETED_STATES or
            current_gstate in FAILED_STATES or
            current_gstate in ABORTED_STATES
        ):
            return self._handle_job_finish(
                cloud_serial,
                parsed_payload,
                ams_data,
                current_gstate,
                COMPLETED_STATES,
                FAILED_STATES,
                ABORTED_STATES
            )

        return None

    def _handle_job_start(
        self,
        cloud_serial: str,
        parsed_payload: Dict[str, Any],
        printer_id: str,
        ams_data: Optional[List[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """Erstellt einen neuen Job"""
        try:
            with Session(engine) as session:
                # Job-Name extrahieren
                job_name = (
                    parsed_payload.get("print", {}).get("subtask_name") or
                    parsed_payload.get("print", {}).get("gcode_file") or
                    parsed_payload.get("subtask_name") or
                    parsed_payload.get("gcode_file") or
                    parsed_payload.get("file") or
                    "Unnamed Job"
                )

                # Aktiven Slot finden
                active_slot = None
                ams_block = parsed_payload.get("print", {}).get("ams") or {}
                tray_now = ams_block.get("tray_now")
                tray_tar = ams_block.get("tray_tar")

                if tray_tar is not None and tray_tar != 255:
                    active_slot = int(tray_tar)
                elif tray_now is not None and tray_now != 255:
                    active_slot = int(tray_now)

                # Spule finden (via ams_slot)
                spool = None
                if active_slot is not None:
                    spool = session.exec(
                        select(Spool)
                        .where(Spool.printer_id == printer_id)
                        .where(Spool.ams_slot == active_slot)
                    ).first()

                # Job erstellen
                new_job = Job(
                    printer_id=printer_id,
                    spool_id=spool.id if spool else None,
                    name=job_name,
                    started_at=datetime.utcnow(),
                    filament_used_mm=0,
                    filament_used_g=0,
                    status="running"
                )

                session.add(new_job)
                session.commit()
                session.refresh(new_job)

                # Spulen-Status aktualisieren (für ALLE Spulen, nicht nur mit spool_number)
                if spool and not spool.is_empty:
                    if spool.status != "Aktiv":
                        spool.status = "Aktiv"
                        spool.is_open = True
                        session.add(spool)
                        session.commit()

                # === NOTIFICATION: Job ohne Spule gestartet ===
                if not spool:
                    printer = session.get(Printer, printer_id)
                    printer_name = printer.name if printer else "Unbekannt"
                    trigger_notification_sync(
                        "job_no_spool",
                        job_name=new_job.name,
                        printer_name=printer_name
                    )

                # Job-Info in RAM speichern
                tray_info = self._find_tray(ams_data or [], active_slot) if active_slot is not None else None
                start_remain = tray_info.get("remain") if tray_info else None
                total_len = tray_info.get("total_len") if tray_info else None

                self.active_jobs[cloud_serial] = {
                    "job_id": new_job.id,
                    "printer_id": printer_id,
                    "slot": active_slot,
                    "spool_id": spool.id if spool else None,
                    "start_remain": start_remain,
                    "last_remain": start_remain,
                    "start_total_len": total_len,
                    "usages": []
                }

                self.logger.info(
                    f"[JOB START] printer={printer_id} job={new_job.id} "
                    f"name={new_job.name} slot={active_slot}"
                )

                return {"job_id": new_job.id, "status": "started"}

        except Exception as e:
            self.logger.error(f"[JOB START] Failed: {e}", exc_info=True)
            return None

    def _handle_job_update(
        self,
        cloud_serial: str,
        parsed_payload: Dict[str, Any],
        ams_data: Optional[List[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """Aktualisiert laufenden Job (Slot-Wechsel, Verbrauch)"""
        job_info = self.active_jobs.get(cloud_serial)
        if not job_info:
            return None

        try:
            with Session(engine) as session:
                job = session.get(Job, job_info.get("job_id"))
                if not job:
                    # Job in DB nicht gefunden - cleanup
                    del self.active_jobs[cloud_serial]
                    return None

                # Aktuellen Slot prüfen
                ams_block = parsed_payload.get("print", {}).get("ams") or {}
                current_slot = ams_block.get("tray_tar")
                if current_slot == 255:
                    current_slot = ams_block.get("tray_now")
                if current_slot == 255:
                    current_slot = None

                # Slot-Wechsel erkennen
                if current_slot is not None and job_info.get("slot") != current_slot:
                    # Finalize old slot
                    usage = self._finalize_current(session, job_info)
                    if usage:
                        job_info.setdefault("usages", []).append(usage)

                    # Start new slot
                    tray_new = self._find_tray(ams_data or [], current_slot)
                    spool_new = session.exec(
                        select(Spool)
                        .where(Spool.printer_id == job_info.get("printer_id"))
                        .where(Spool.ams_slot == current_slot)
                    ).first()

                    job_info.update({
                        "slot": current_slot,
                        "spool_id": spool_new.id if spool_new else None,
                        "start_remain": tray_new.get("remain") if tray_new else None,
                        "last_remain": tray_new.get("remain") if tray_new else None,
                        "start_total_len": tray_new.get("total_len") if tray_new else None
                    })

                    if spool_new and not job.spool_id:
                        job.spool_id = spool_new.id

                # Update last_remain + Spulen-Gewicht
                current_tray = self._find_tray(ams_data or [], job_info.get("slot"))
                if current_tray:
                    job_info["last_remain"] = current_tray.get("remain")

                    # Spulen-Gewicht live aktualisieren
                    spool_id = job_info.get("spool_id")
                    if spool_id:
                        spool = session.get(Spool, spool_id)
                        if spool:
                            used_mm, used_g = self._calc_usage(
                                spool,
                                job_info.get("start_remain"),
                                job_info.get("last_remain"),
                                job_info.get("start_total_len")
                            )

                            if used_g > 0 and spool.weight_full is not None:
                                spool.weight_current = float(spool.weight_full) - used_g
                                session.add(spool)

                # Job-Verbrauch aktualisieren
                total_used_mm = sum(u.get("used_mm", 0) for u in job_info.get("usages", []))
                total_used_g = sum(u.get("used_g", 0) for u in job_info.get("usages", []))

                # Aktueller Slot-Verbrauch (noch nicht finalized)
                if job_info.get("spool_id"):
                    sp = session.get(Spool, job_info.get("spool_id"))
                    current_mm, current_g = self._calc_usage(
                        sp,
                        job_info.get("start_remain"),
                        job_info.get("last_remain"),
                        job_info.get("start_total_len")
                    )
                    total_used_mm += current_mm
                    total_used_g += current_g

                job.filament_used_mm = total_used_mm
                job.filament_used_g = total_used_g

                session.add(job)
                session.commit()

                return {"job_id": job.id, "status": "updated", "used_g": total_used_g}

        except Exception as e:
            self.logger.error(f"[JOB UPDATE] Failed: {e}", exc_info=True)
            return None

    def _handle_job_finish(
        self,
        cloud_serial: str,
        parsed_payload: Dict[str, Any],
        ams_data: Optional[List[Dict[str, Any]]],
        current_gstate: str,
        completed_states: set,
        failed_states: set,
        aborted_states: set
    ) -> Optional[Dict[str, Any]]:
        """Beendet aktiven Job"""
        job_info = self.active_jobs.get(cloud_serial)
        if not job_info:
            return None

        try:
            with Session(engine) as session:
                job = session.get(Job, job_info.get("job_id"))
                if not job:
                    del self.active_jobs[cloud_serial]
                    return None

                # Finalize letzten Slot
                final_tray = self._find_tray(ams_data or [], job_info.get("slot"))
                if final_tray:
                    job_info["last_remain"] = final_tray.get("remain")

                usage = self._finalize_current(session, job_info)
                if usage:
                    job_info.setdefault("usages", []).append(usage)

                # Gesamt-Verbrauch
                total_used_mm = sum(u.get("used_mm", 0) for u in job_info.get("usages", []))
                total_used_g = sum(u.get("used_g", 0) for u in job_info.get("usages", []))

                job.filament_used_mm = total_used_mm
                job.filament_used_g = total_used_g
                job.finished_at = datetime.utcnow()

                # Status-Mapping: Bambu gcode_state → Job Status
                if current_gstate in completed_states:
                    job.status = "completed"
                elif current_gstate in aborted_states:
                    # ABORT, ABORTED, STOPPED, CANCELLED, CANCELED → aborted
                    if current_gstate in {"CANCELLED", "CANCELED"}:
                        job.status = "cancelled"
                    elif current_gstate in {"ABORT", "ABORTED"}:
                        job.status = "aborted"
                    else:  # STOPPED
                        job.status = "stopped"
                elif current_gstate in failed_states:
                    # FAILED, ERROR, EXCEPTION → failed/error/exception
                    if current_gstate == "EXCEPTION":
                        job.status = "exception"
                    elif current_gstate == "ERROR":
                        job.status = "error"
                    else:
                        job.status = "failed"
                else:
                    # Fallback
                    job.status = "failed"

                # Spool ID setzen (falls noch nicht gesetzt)
                if not job.spool_id and job_info.get("usages"):
                    first_spool = next((u.get("spool_id") for u in job_info["usages"] if u.get("spool_id")), None)
                    if first_spool:
                        job.spool_id = first_spool

                session.add(job)
                session.commit()
                session.refresh(job)

                self.logger.info(
                    f"[JOB FINISH] job={job.id} status={job.status} "
                    f"used_mm={total_used_mm:.1f} used_g={total_used_g:.1f}"
                )

                # Lade Printer für Notification-Kontext
                printer = session.get(Printer, job.printer_id)
                printer_name = printer.name if printer else "Unbekannt"

                # === NOTIFICATIONS TRIGGERN ===
                # 1. Job failed (FAILED/ERROR/EXCEPTION)
                if job.status in ["failed", "error", "exception"]:
                    trigger_notification_sync(
                        "job_failed",
                        job_name=job.name,
                        printer_name=printer_name,
                        status=job.status.upper()
                    )

                # 2. Job aborted (ABORTED/STOPPED/CANCELLED)
                if job.status in ["aborted", "stopped", "cancelled"]:
                    trigger_notification_sync(
                        "job_aborted",
                        job_name=job.name,
                        printer_name=printer_name,
                        status=job.status.upper()
                    )

                # 3. Job ohne Tracking (kein Verbrauch oder keine Spule)
                if not job.spool_id or total_used_g == 0:
                    trigger_notification_sync(
                        "job_no_tracking",
                        job_name=job.name,
                        printer_name=printer_name
                    )

                # Cleanup RAM
                del self.active_jobs[cloud_serial]

                return {"job_id": job.id, "status": job.status, "used_g": total_used_g}

        except Exception as e:
            self.logger.error(f"[JOB FINISH] Failed: {e}", exc_info=True)
            # Cleanup auch bei Fehler
            if cloud_serial in self.active_jobs:
                del self.active_jobs[cloud_serial]
            return None


# Singleton Instance
job_tracking_service = JobTrackingService()
