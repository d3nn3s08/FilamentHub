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

from typing import Dict, Any, Optional, List, cast
from datetime import datetime
from sqlmodel import Session, select
import logging
import json
from pathlib import Path
import tempfile
import os
import threading
from json import JSONDecodeError

from app.models.job import Job
from app.models.spool import Spool
from app.models.printer import Printer
from app.database import engine
from app.routes.notification_routes import trigger_notification_sync


_snapshot_lock = threading.Lock()


class JobTrackingService:
    """Singleton Service für Job-Tracking und Verbrauch-Berechnung"""

    def __init__(self):
        self.active_jobs: Dict[str, Dict[str, Any]] = {}  # cloud_serial -> job_info
        self.last_gstate: Dict[str, str] = {}  # cloud_serial -> last_state
        self.logger = logging.getLogger("job_tracking")
        self.snapshots_file = Path("data/job_snapshots.json")  # Persistente Job-Fingerprints


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

        # FIX: Bambu Lab's "remain" ist EXTREM unzuverlässig und kann sogar steigen!
        # Wir ignorieren Anstiege (bleiben beim letzten Wert)
        # Dies ist eine defensive Strategie, um negative Verbräuche zu vermeiden
        used_percent = max(0.0, float(start_remain) - float(end_remain))

        # Wenn remain GESTIEGEN ist (end_remain > start_remain), ist used_percent = 0
        # Das ist technisch korrekt, aber wir verlieren Tracking-Genauigkeit

        # Länge in mm
        used_mm = (used_percent / 100.0) * float(start_total_len) if start_total_len else 0.0

        # Gewicht in g
        used_g = 0.0
        if spool and spool.weight_full is not None and spool.weight_empty is not None:
            used_g = (used_percent / 100.0) * (float(spool.weight_full) - float(spool.weight_empty))

        return used_mm, used_g

    def _get_snapshot_key(self, cloud_serial: str, printer_id: Optional[str]) -> str:
        """
        Bestimmt den Snapshot-Key basierend auf Drucker-Typ.

        - Bambu Lab (hat cloud_serial): Verwende cloud_serial (hardware-gebunden)
        - Klipper (kein cloud_serial): Verwende printer_id (DB-gebunden)
        """
        if cloud_serial:
            return cloud_serial
        if printer_id:
            return f"printer_{printer_id}"
        return "printer_unknown"

    def _save_snapshot(self, cloud_serial: str, printer_id: Optional[str], job_id: str, job_name: str,
                       slot: int, layer_num: int, mc_percent: int, started_at: datetime,
                       filament_start_mm: Optional[float] = None,
                       filament_started: bool = False,
                       using_fallback: bool = False,
                       fallback_warned: bool = False):
        """Speichert Job-Snapshot in JSON-Datei für Server-Neustart-Recovery"""
        snapshot_key = self._get_snapshot_key(cloud_serial, printer_id)

        # Neuer Snapshot
        snapshot_data = {
            "cloud_serial": cloud_serial,
            "printer_id": printer_id,
            "job_id": job_id,
            "job_name": job_name,
            "started_at": started_at.isoformat(),
            "slot": slot,
            "layer_num": layer_num,
            "mc_percent": mc_percent,
            "filament_started": filament_started,
            "using_fallback": using_fallback,
            "fallback_warned": fallback_warned,
        }

        if filament_start_mm is not None:
            snapshot_data["filament_start_mm"] = filament_start_mm

        # Ensure parent dir exists
        try:
            self.snapshots_file.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.logger.exception("[SNAPSHOT] Failed to create snapshot directory %s", self.snapshots_file.parent)
            return

        # Atomarer write: schreibe in tempfile, fsync, replace
        tmp_path = None
        try:
            with _snapshot_lock:
                snapshots = {}
                if self.snapshots_file.exists():
                    try:
                        with open(self.snapshots_file, 'r', encoding='utf-8') as f:
                            snapshots = json.load(f)
                    except JSONDecodeError:
                        self.logger.error("[SNAPSHOT] Corrupt snapshot file %s - discarding", self.snapshots_file, exc_info=True)
                        snapshots = {}
                    except OSError:
                        self.logger.exception("[SNAPSHOT] Failed to read snapshot file %s", self.snapshots_file)
                        snapshots = {}

                snapshots[snapshot_key] = snapshot_data

                dirpath = str(self.snapshots_file.parent)
                tf = tempfile.NamedTemporaryFile(mode='w', dir=dirpath, delete=False, encoding='utf-8')
                tmp_path = tf.name
                try:
                    json.dump(snapshots, tf, ensure_ascii=False, indent=2)
                    tf.flush()
                    os.fsync(tf.fileno())
                finally:
                    tf.close()

                os.replace(tmp_path, str(self.snapshots_file))

            self.logger.debug("[SNAPSHOT] Saved for key=%s job=%s", snapshot_key, job_id)

        except Exception:
            self.logger.exception("[SNAPSHOT] Failed to save snapshot for key=%s", snapshot_key)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _load_snapshot(self, cloud_serial: str, printer_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Lädt Job-Snapshot für einen Drucker"""
        snapshot_key = self._get_snapshot_key(cloud_serial, printer_id)

        if not self.snapshots_file.exists():
            return None

        try:
            with open(self.snapshots_file, 'r', encoding='utf-8') as f:
                snapshots = json.load(f)
        except JSONDecodeError:
            self.logger.error("[SNAPSHOT] Corrupt snapshot file %s - discarding", self.snapshots_file, exc_info=True)
            return None
        except OSError:
            self.logger.exception("[SNAPSHOT] Failed to read snapshot file %s", self.snapshots_file)
            return None

        return snapshots.get(snapshot_key)

    def _delete_snapshot(self, cloud_serial: str, printer_id: Optional[str]):
        """Löscht Job-Snapshot nach Job-Ende"""
        snapshot_key = self._get_snapshot_key(cloud_serial, printer_id)

        if not self.snapshots_file.exists():
            return

        tmp_path = None
        try:
            with _snapshot_lock:
                try:
                    with open(self.snapshots_file, 'r', encoding='utf-8') as f:
                        snapshots = json.load(f)
                except JSONDecodeError:
                    self.logger.error("[SNAPSHOT] Corrupt snapshot file %s - discarding", self.snapshots_file, exc_info=True)
                    return
                except OSError:
                    self.logger.exception("[SNAPSHOT] Failed to read snapshot file %s", self.snapshots_file)
                    return

                if snapshot_key in snapshots:
                    del snapshots[snapshot_key]

                    dirpath = str(self.snapshots_file.parent)
                    tf = tempfile.NamedTemporaryFile(mode='w', dir=dirpath, delete=False, encoding='utf-8')
                    tmp_path = tf.name
                    try:
                        json.dump(snapshots, tf, ensure_ascii=False, indent=2)
                        tf.flush()
                        os.fsync(tf.fileno())
                    finally:
                        tf.close()

                    os.replace(tmp_path, str(self.snapshots_file))
                    self.logger.debug("[SNAPSHOT] Deleted for key=%s", snapshot_key)

        except Exception:
            self.logger.exception("[SNAPSHOT] Failed to delete snapshot for key=%s", snapshot_key)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

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

    def _extract_filament_used_mm(self, parsed_payload: Dict[str, Any]) -> Optional[float]:
        """
        Extrahiert print.filament_used_mm aus verschiedenen möglichen Pfaden.

        Args:
            parsed_payload: Geparste MQTT Payload

        Returns:
            Filament-verbrauch in mm oder None falls nicht vorhanden
        """
        # Primärquelle: print.filament_used_mm
        print_block = parsed_payload.get("print", {})
        if isinstance(print_block, dict):
            filament_used = print_block.get("filament_used_mm")
            if filament_used is not None:
                try:
                    value = float(filament_used)
                    self.logger.debug(
                        "[FILAMENT] Extracted filament_used_mm=%s from print.filament_used_mm",
                        value,
                    )
                    return value
                except (ValueError, TypeError):
                    pass

            # Alternative: print.3D.filament_used_mm
            three_d = print_block.get("3D", {})
            if isinstance(three_d, dict):
                filament_used = three_d.get("filament_used_mm")
                if filament_used is not None:
                    try:
                        value = float(filament_used)
                        self.logger.debug(
                            "[FILAMENT] Extracted filament_used_mm=%s from print.3D.filament_used_mm",
                            value,
                        )
                        return value
                    except (ValueError, TypeError):
                        pass

        # Fallback: Root-level
        filament_used = parsed_payload.get("filament_used_mm")
        if filament_used is not None:
            try:
                value = float(filament_used)
                self.logger.debug(
                    "[FILAMENT] Extracted filament_used_mm=%s from filament_used_mm",
                    value,
                )
                return value
            except (ValueError, TypeError):
                pass

        return None

    def _calculate_filament_from_remain(self, tray_info: Dict[str, Any]) -> Optional[float]:
        """
        Berechnet absoluten Filament-Verbrauch aus remain und total_len (Fallback).

        Args:
            tray_info: Tray-Info Dict mit remain und total_len

        Returns:
            Berechneter Filament-verbrauch in mm oder None falls total_len fehlt
        """
        if not tray_info:
            return None

        total_len = tray_info.get("total_len")
        if total_len is None:
            self.logger.error("[FILAMENT] Fallback unavailable: missing total_len")
            return None

        try:
            total_len_mm = float(total_len)
        except (ValueError, TypeError):
            return None

        remain = tray_info.get("remain")
        if remain is None:
            return None

        try:
            remain_percent = float(remain)
        except (ValueError, TypeError):
            return None

        # Berechne: total_len_mm * (1 - remain_percent / 100)
        filament_used_mm = total_len_mm * (1 - remain_percent / 100.0)
        return max(0.0, filament_used_mm)  # Keine negativen Werte

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
        """Erstellt einen neuen Job oder restored existierenden nach Server-Neustart"""
        try:
            with Session(engine) as session:
                from datetime import datetime, timedelta

                # Extrahiere Job-Informationen aus MQTT-Payload
                job_name = (
                    parsed_payload.get("print", {}).get("subtask_name") or
                    parsed_payload.get("print", {}).get("gcode_file") or
                    parsed_payload.get("subtask_name") or
                    parsed_payload.get("gcode_file") or
                    parsed_payload.get("file") or
                    "Unnamed Job"
                )

                # Aktuelle Layer/Fortschritt aus MQTT
                current_layer = parsed_payload.get("print", {}).get("layer_num") or 0
                current_percent = parsed_payload.get("print", {}).get("mc_percent") or 0

                # Aktiven Slot finden
                active_slot = None
                ams_block = parsed_payload.get("print", {}).get("ams") or {}
                tray_now = ams_block.get("tray_now")
                tray_tar = ams_block.get("tray_tar")

                if tray_tar is not None and tray_tar != 255:
                    active_slot = int(tray_tar)
                elif tray_now is not None and tray_now != 255:
                    active_slot = int(tray_now)

                # === SNAPSHOT-BASIERTE ERKENNUNG: Server-Neustart vs. Neuer Job ===
                snapshot = self._load_snapshot(cloud_serial, printer_id)
                existing_jobs = session.exec(
                    select(Job)
                    .where(Job.printer_id == printer_id)
                    .where(Job.status == "running")
                    .order_by(cast(Any, Job.started_at))
                ).all()

                # CLEANUP: Duplikate löschen (behalte ältesten)
                if len(existing_jobs) > 1:
                    self.logger.warning(
                        f"[JOB START] Found {len(existing_jobs)} duplicate running jobs. "
                        f"Cleaning up duplicates."
                    )
                    for dup in existing_jobs[1:]:
                        self.logger.info(f"[JOB START] Deleting duplicate job={dup.id}")
                        session.delete(dup)
                    session.commit()
                    existing_jobs = [existing_jobs[0]]

                existing_job = existing_jobs[0] if existing_jobs else None

                # Prüfe ob existing Job wiederhergestellt werden soll
                should_restore = False
                if existing_job and snapshot:
                    # Validierung: Ist das der gleiche Druck?
                    job_age = datetime.utcnow() - existing_job.started_at

                    # Check 1: Job zu alt (>48h) → stale
                    if job_age > timedelta(hours=48):
                        self.logger.warning(
                            f"[JOB START] Stale job (age={job_age.total_seconds()/3600:.1f}h). "
                            f"Marking as failed."
                        )
                        existing_job.status = "failed"
                        existing_job.finished_at = datetime.utcnow()
                        session.add(existing_job)
                        session.commit()
                        self._delete_snapshot(cloud_serial, printer_id)
                        existing_job = None

                    # Check 2: Fortschritt gemacht? (Layer/Percent gestiegen)
                    elif (current_layer >= snapshot.get("layer_num", 0) and
                          current_percent >= snapshot.get("mc_percent", 0)):
                        # Fortschritt passt → gleicher Druck, Server-Neustart!
                        should_restore = True
                        self.logger.info(
                            f"[JOB START] Detected server restart. "
                            f"Restoring job={existing_job.id} "
                            f"(layer: {snapshot.get('layer_num')}→{current_layer}, "
                            f"progress: {snapshot.get('mc_percent')}%→{current_percent}%)"
                        )

                    else:
                        # Fortschritt NICHT gestiegen → neuer Druck!
                        self.logger.warning(
                            f"[JOB START] Progress mismatch (new print detected). "
                            f"Marking old job as failed. "
                            f"(layer: {current_layer} vs snapshot {snapshot.get('layer_num')}, "
                            f"percent: {current_percent}% vs snapshot {snapshot.get('mc_percent')}%)"
                        )
                        existing_job.status = "failed"
                        existing_job.finished_at = datetime.utcnow()
                        session.add(existing_job)
                        session.commit()
                        self._delete_snapshot(cloud_serial, printer_id)
                        existing_job = None

                elif existing_job and not snapshot:
                    # Job existiert aber kein Snapshot → vermutlich alter stale Job
                    self.logger.warning(
                        f"[JOB START] Found running job without snapshot. Marking as failed."
                    )
                    existing_job.status = "failed"
                    existing_job.finished_at = datetime.utcnow()
                    session.add(existing_job)
                    session.commit()
                    existing_job = None

                # === JOB RESTORE (nach Server-Neustart) ===
                if should_restore and existing_job:
                    # Tray-Info für remain-Tracking
                    tray_info = self._find_tray(ams_data or [], active_slot) if active_slot is not None else None
                    start_remain = tray_info.get("remain") if tray_info else None
                    total_len = tray_info.get("total_len") if tray_info else None

                    # Job in RAM wiederherstellen
                    # Lade filament_start_mm und filament_started aus Snapshot
                    assert snapshot is not None
                    filament_start_mm = snapshot.get("filament_start_mm")
                    filament_started = snapshot.get("filament_started", False)
                    using_fallback = snapshot.get("using_fallback", False)
                    fallback_warned = snapshot.get("fallback_warned", False)

                    # Wenn filament_start_mm vorhanden, setze filament_started = True
                    if filament_start_mm is not None:
                        filament_started = True

                    self.active_jobs[cloud_serial] = {
                        "job_id": existing_job.id,
                        "printer_id": printer_id,
                        "slot": active_slot,
                        "spool_id": existing_job.spool_id,
                        "start_remain": start_remain,
                        "last_remain": start_remain,
                        "start_total_len": total_len,
                        "usages": [],
                        "filament_start_mm": filament_start_mm,
                        "filament_started": filament_started,
                        "using_fallback": using_fallback,
                        "fallback_warned": fallback_warned,
                    }

                    return {"job_id": existing_job.id, "status": "restored"}

                # === NEUER JOB ERSTELLEN ===

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

                # WICHTIG: filament_start_mm wird NICHT beim Job-Start gesetzt
                # Es wird erst bei layer_num >= 1 gesetzt (in _handle_job_update)
                self.active_jobs[cloud_serial] = {
                    "job_id": new_job.id,
                    "printer_id": printer_id,
                    "slot": active_slot,
                    "spool_id": spool.id if spool else None,
                    "start_remain": start_remain,
                    "last_remain": start_remain,
                    "start_total_len": total_len,
                    "usages": [],
                    "filament_start_mm": None,  # Wird bei layer_num >= 1 gesetzt
                    "filament_started": False,  # Guard-Flag gegen doppelte Events
                    "using_fallback": False,  # Flag für Fallback-Modus
                    "fallback_warned": False  # Flag für einmalige Warnung
                }

                # === SNAPSHOT SPEICHERN (für Server-Neustart-Recovery) ===
                self._save_snapshot(
                    cloud_serial=cloud_serial,
                    printer_id=printer_id,
                    job_id=new_job.id,
                    job_name=job_name,
                    slot=active_slot or 0,
                    layer_num=current_layer,
                    mc_percent=current_percent,
                    started_at=new_job.started_at
                )

                self.logger.info(
                    f"[JOB START] printer={printer_id} job={new_job.id} "
                    f"name={new_job.name} slot={active_slot} "
                    f"(snapshot saved: layer={current_layer}, progress={current_percent}%)"
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

                # Initialize usage accumulators to avoid UnboundLocalError
                total_used_mm = 0.0
                total_used_g = 0.0

                # Aktuelle Layer-Nummer prüfen
                current_layer = parsed_payload.get("print", {}).get("layer_num") or 0

                # === LAYER-BASIERTER FILAMENT-START ===
                # Filament-Tracking startet erst bei layer_num >= 1
                if current_layer >= 1 and not job_info.get("filament_started"):
                    # Guard-Flag setzen (einmalig)
                    job_info["filament_started"] = True

                    # Extrahiere Primärquelle
                    current_filament = self._extract_filament_used_mm(parsed_payload)

                    if current_filament is not None:
                        # Primärquelle verfügbar
                        job_info["filament_start_mm"] = current_filament
                        job.filament_start_mm = current_filament
                        job_info["using_fallback"] = False

                        self.logger.info(
                            f"[FILAMENT START] Tracking started at layer={current_layer}, "
                            f"start_mm={current_filament:.1f} (primary source) for job={job.id}"
                        )
                    else:
                        # Fallback: Berechne aus remain und total_len
                        current_tray = self._find_tray(ams_data or [], job_info.get("slot"))
                        if current_tray and current_tray.get("total_len") is not None:
                            filament_start = self._calculate_filament_from_remain(current_tray)
                            if filament_start is not None:
                                job_info["filament_start_mm"] = filament_start
                                job.filament_start_mm = filament_start
                                job_info["using_fallback"] = True

                                # Warnung einmalig
                                if not job_info.get("fallback_warned"):
                                    self.logger.warning(
                                        "[FILAMENT] Using fallback calculation for job=%s",
                                        job.id,
                                    )
                                    job_info["fallback_warned"] = True

                                self.logger.info(
                                    f"[FILAMENT START] Tracking started at layer={current_layer}, "
                                    f"start_mm={filament_start:.1f} (fallback) for job={job.id}"
                                )
                            else:
                                self.logger.error(
                                    f"[FILAMENT START] Failed to calculate fallback for job={job.id}: "
                                    f"invalid remain or total_len"
                                )
                        else:
                            # Sauber abbrechen + Fehler loggen
                            self.logger.error(
                                f"[FILAMENT START] Cannot start tracking for job={job.id}: "
                                f"no filament_used_mm and no total_len"
                            )
                            job_info["filament_start_mm"] = None

                    # Snapshot + DB synchron
                    if job_info.get("filament_start_mm") is not None:
                        self._save_snapshot(
                            cloud_serial=cloud_serial,
                            printer_id=job_info.get("printer_id"),
                            job_id=job.id,
                            job_name=job.name,
                            slot=job_info.get("slot") or 0,
                            layer_num=current_layer,
                            mc_percent=parsed_payload.get("print", {}).get("mc_percent") or 0,
                            started_at=job.started_at,
                            filament_start_mm=job_info.get("filament_start_mm"),
                            filament_started=True,
                            using_fallback=job_info.get("using_fallback", False),
                            fallback_warned=job_info.get("fallback_warned", False),
                        )
                        session.add(job)
                        session.commit()

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
                    current_remain = current_tray.get("remain")

                    # FIX: Bambu Lab's "remain" kann willkürlich steigen/fallen
                    # Wir akzeptieren nur SINKENDE Werte (Filamentverbrauch)
                    # Bei steigenden Werten behalten wir den letzten niedrigen Wert
                    if current_remain is not None:
                        last_remain = job_info.get("last_remain")
                        if last_remain is None or current_remain <= last_remain:
                            # Remain ist gesunken (normaler Verbrauch) oder erster Wert
                            job_info["last_remain"] = current_remain
                        else:
                            # remain ist GESTIEGEN - Bambu Lab Bug!
                            self.logger.warning(
                                f"[JOB UPDATE] Remain INCREASED: {last_remain}% -> {current_remain}% "
                                f"(slot={job_info.get('slot')}, printer={cloud_serial}). "
                                f"Ignoring increase, keeping last value."
                            )

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
                                spool.weight_current = float(spool.weight_full) - float(used_g)
                                session.add(spool)

                # === FILAMENT-BERECHNUNG (NEUE LOGIK) ===
                # Verwende Delta-Methode ab layer_num >= 1
                start_mm_raw = job_info.get("filament_start_mm")
                start_mm = None
                if start_mm_raw is not None:
                    try:
                        start_mm = float(start_mm_raw)
                    except (TypeError, ValueError):
                        start_mm = None

                if start_mm is not None:
                    # Filament-Tracking ist aktiv (layer_num >= 1 erreicht)
                    current_filament = self._extract_filament_used_mm(parsed_payload)

                    if current_filament is not None:
                        # Primärquelle verfügbar
                        if current_filament < start_mm:
                            self.logger.warning(
                                "[FILAMENT] Current filament_used_mm (%s) is less than start_mm (%s) for job=%s",
                                current_filament,
                                start_mm,
                                job.id,
                            )
                        else:
                            job_filament_used_mm = current_filament - start_mm

                            # Wechsel von Fallback zu Primärquelle?
                            if job_info.get("using_fallback"):
                                self.logger.info(
                                    f"[FILAMENT] Switched from fallback to primary source for job={job.id}"
                                )
                                job_info["using_fallback"] = False

                            # Gewicht berechnen (für Kompatibilität)
                            # Verwende weiterhin remain-Methode für Gewicht, da wir keine absolute Gewichtsquelle haben
                            total_used_g = sum(u.get("used_g", 0) for u in job_info.get("usages", []))
                            if job_info.get("spool_id"):
                                sp = session.get(Spool, job_info.get("spool_id"))
                                if sp:
                                    _, current_g = self._calc_usage(
                                        sp,
                                        job_info.get("start_remain"),
                                        job_info.get("last_remain"),
                                        job_info.get("start_total_len")
                                    )
                                    total_used_g += current_g

                            job.filament_used_mm = max(0.0, job_filament_used_mm)
                            job.filament_used_g = total_used_g
                    else:
                        # Primärquelle nicht verfügbar, aber Fallback aktiv?
                        if job_info.get("using_fallback"):
                            # Fallback: Berechne weiterhin aus remain-Delta
                            if job_info.get("start_total_len") is None:
                                self.logger.error(
                                    "[FILAMENT] Fallback delta unavailable: missing total_len for job=%s",
                                    job.id,
                                )
                                # Keine Quelle verfÜgbar, behalte letzten Wert
                                pass
                            else:
                                total_used_mm = sum(u.get("used_mm", 0) for u in job_info.get("usages", []))
                                total_used_g = sum(u.get("used_g", 0) for u in job_info.get("usages", []))

                                if job_info.get("spool_id"):
                                    sp = session.get(Spool, job_info.get("spool_id"))
                                    if sp:
                                        current_mm, current_g = self._calc_usage(
                                            sp,
                                            job_info.get("start_remain"),
                                            job_info.get("last_remain"),
                                            job_info.get("start_total_len")
                                        )
                                        total_used_mm += current_mm
                                        total_used_g += current_g

                                job.filament_used_mm = max(0.0, total_used_mm)
                                job.filament_used_g = total_used_g
                        else:
                            # Keine Quelle verfügbar, behalte letzten Wert
                            pass
                else:
                    # Filament-Tracking noch nicht gestartet (layer_num < 1)
                    # Setze Verbrauch auf 0
                    job.filament_used_mm = 0.0
                    job.filament_used_g = 0.0

                session.add(job)

                # === SNAPSHOT AKTUALISIEREN (Layer/Progress) ===
                current_layer = parsed_payload.get("print", {}).get("layer_num") or 0
                current_percent = parsed_payload.get("print", {}).get("mc_percent") or 0
                if current_layer > 0 or current_percent > 0:
                    self._save_snapshot(
                        cloud_serial=cloud_serial,
                        printer_id=job_info.get("printer_id"),
                        job_id=job.id,
                        job_name=job.name,
                        slot=job_info.get("slot") or 0,
                        layer_num=current_layer,
                        mc_percent=current_percent,
                        started_at=job.started_at,
                        filament_start_mm=job_info.get("filament_start_mm"),
                        filament_started=job_info.get("filament_started", False),
                        using_fallback=job_info.get("using_fallback", False),
                        fallback_warned=job_info.get("fallback_warned", False),
                    )
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

                # Initialize accumulators to ensure defined values in all code paths
                total_used_mm = 0.0
                total_used_g = 0.0
                final_used_mm = 0.0

                # Finalize letzten Slot
                final_tray = self._find_tray(ams_data or [], job_info.get("slot"))
                if final_tray:
                    job_info["last_remain"] = final_tray.get("remain")

                usage = self._finalize_current(session, job_info)
                if usage:
                    job_info.setdefault("usages", []).append(usage)

                # === FINALE FILAMENT-BERECHNUNG (NEUE LOGIK) ===
                if job_info.get("filament_start_mm") is not None:
                    # Filament-Tracking war aktiv
                    final_filament = self._extract_filament_used_mm(parsed_payload)

                    if final_filament is not None:
                        # Primärquelle verfügbar
                        try:
                            start_mm = float(job_info["filament_start_mm"])
                        except (TypeError, ValueError):
                            start_mm = None
                        if start_mm is None:
                            self.logger.error(
                                "[FILAMENT] Invalid filament_start_mm for job=%s; cannot finalize from primary source",
                                job.id,
                            )
                        elif final_filament < start_mm:
                            self.logger.warning(
                                "[FILAMENT] Final filament_used_mm (%s) is less than start_mm (%s) for job=%s",
                                final_filament,
                                start_mm,
                                job.id,
                            )
                        else:
                            final_used_mm = final_filament - start_mm
                    else:
                        # Fallback: Berechne aus finalem remain-Delta
                        if job_info.get("start_total_len") is None:
                            self.logger.error(
                                "[FILAMENT] Fallback finalize unavailable: missing total_len for job=%s",
                                job.id,
                            )
                        else:
                            total_used_mm = sum(u.get("used_mm", 0) for u in job_info.get("usages", []))
                            if job_info.get("spool_id"):
                                sp = session.get(Spool, job_info.get("spool_id"))
                                if sp:
                                    current_mm, _ = self._calc_usage(
                                        sp,
                                        job_info.get("start_remain"),
                                        job_info.get("last_remain"),
                                        job_info.get("start_total_len")
                                    )
                                    total_used_mm += current_mm
                            final_used_mm = total_used_mm
                else:
                    # Filament-Tracking nie gestartet (layer_num < 1 während gesamten Jobs)
                    # Berechne Verbrauch aus finalisierten Usages (remain-delta)
                    total_used_mm = sum(u.get("used_mm", 0) for u in job_info.get("usages", []))
                    if job_info.get("spool_id"):
                        sp = session.get(Spool, job_info.get("spool_id"))
                        if sp:
                            # Wenn _finalize_current bereits ein Usage-Entry für den aktuellen
                            # Slot erstellt hat (variable `usage`), dann ist der aktuelle
                            # Verbrauch bereits in `job_info['usages']` enthalten und
                            # darf nicht erneut addiert werden.
                            if not usage:
                                current_mm, _ = self._calc_usage(
                                    sp,
                                    job_info.get("start_remain"),
                                    job_info.get("last_remain"),
                                    job_info.get("start_total_len")
                                )
                                total_used_mm += current_mm
                    final_used_mm = total_used_mm

                # Gewicht berechnen (für Kompatibilität)
                total_used_g = sum(u.get("used_g", 0) for u in job_info.get("usages", []))
                if job_info.get("spool_id"):
                    sp = session.get(Spool, job_info.get("spool_id"))
                    if sp:
                        # Wenn `usage` existiert, wurde der aktuelle Slot bereits
                        # finalisiert und ist in `usages` enthalten; vermeide Duplikate.
                        if not usage:
                            _, current_g = self._calc_usage(
                                sp,
                                job_info.get("start_remain"),
                                job_info.get("last_remain"),
                                job_info.get("start_total_len")
                            )
                            total_used_g += current_g

                job.filament_used_mm = max(0.0, final_used_mm)
                job.filament_used_g = total_used_g
                # Ensure variables used in logging are set
                total_used_mm = final_used_mm
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

                # WICHTIG: Finales Spulen-Gewicht aktualisieren!
                # Bei abgebrochenen/fehlgeschlagenen Jobs wird das Gewicht sonst nicht gesetzt

                # Alle verwendeten Spulen aktualisieren
                updated_spools = set()

                # 1. Multi-Spool: Finalisierte Slots
                for usage in job_info.get("usages", []):
                    spool_id = usage.get("spool_id")
                    if spool_id and spool_id not in updated_spools:
                        spool = session.get(Spool, spool_id)
                        if spool and spool.weight_current is not None:
                            used_g = usage.get("used_g", 0)
                            # Vom aktuellen Gewicht abziehen, nicht von weight_full!
                            new_weight = max(0, float(spool.weight_current) - used_g)
                            spool.weight_current = new_weight
                            session.add(spool)
                            updated_spools.add(spool_id)

                # 2. Aktueller Slot (falls nicht bereits in usages)
                current_spool_id = job_info.get("spool_id")
                if current_spool_id and current_spool_id not in updated_spools:
                    spool = session.get(Spool, current_spool_id)
                    if spool and spool.weight_current is not None:
                        # Berechne Verbrauch für aktuellen Slot
                        used_mm, used_g = self._calc_usage(
                            spool,
                            job_info.get("start_remain"),
                            job_info.get("last_remain"),
                            job_info.get("start_total_len")
                        )
                        if used_g > 0:
                            new_weight = max(0, float(spool.weight_current) - used_g)
                            spool.weight_current = new_weight
                            session.add(spool)

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

                # === SNAPSHOT LÖSCHEN (Job ist fertig) ===
                self._delete_snapshot(cloud_serial, job_info.get("printer_id"))

                return {"job_id": job.id, "status": job.status, "used_g": total_used_g}

        except Exception as e:
            self.logger.error(f"[JOB FINISH] Failed: {e}", exc_info=True)
            # Cleanup auch bei Fehler
            if cloud_serial in self.active_jobs:
                del self.active_jobs[cloud_serial]
            return None


# Singleton Instance
job_tracking_service = JobTrackingService()
