"""
Job Tracking Service - Zentrale Verwaltung fÃ¼r Job-Tracking und Filament-Verbrauch

Verwaltet:
- Aktive Jobs pro Drucker (RAM-basiert)
- Job-Status-ÃœbergÃ¤nge (IDLE -> RUNNING -> FINISH)
- Filament-Verbrauch Berechnung
- Spulen-Gewicht Updates
- Multi-Spool Job Tracking

Wird genutzt von:
- mqtt_runtime.py (Live MQTT Messages)
- mqtt_routes.py (HTTP API Fallback)
"""

from typing import Dict, Any, Optional, List, cast
from datetime import datetime
from sqlmodel import Session, select, col
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
from app.models.material import Material
from app.database import engine
from app.routes.notification_routes import trigger_notification_sync
from app.services.eta.bambu_a_series_eta import estimate_remaining_time_from_layers
from app.services.spool_helpers import is_external_tray, get_external_tray_id


_snapshot_lock = threading.Lock()


class JobTrackingService:
    """Singleton Service fÃ¼r Job-Tracking und Verbrauch-Berechnung"""

    def __init__(self):
        self.active_jobs: Dict[str, Dict[str, Any]] = {}  # cloud_serial -> job_info
        self.last_gstate: Dict[str, str] = {}  # cloud_serial -> last_state
        self.logger = logging.getLogger("services")
        self.snapshots_file = Path("data/job_snapshots.json")  # Persistente Job-Fingerprints
        self.binding_warning_layer_threshold = 10
        self._job_finish_cooldown: Dict[str, float] = {}  # cloud_serial -> timestamp nach Job-Ende
        self._JOB_FINISH_COOLDOWN_SECS = 120  # 2 Minuten Sperrzeit nach Job-Ende

    def _extract_job_name(self, parsed_payload: Dict[str, Any]) -> Optional[str]:
        """Extrahiert Jobnamen aus MQTT-Payload oder None."""
        name = (
            parsed_payload.get("print", {}).get("subtask_name") or
            parsed_payload.get("print", {}).get("gcode_file") or
            parsed_payload.get("subtask_name") or
            parsed_payload.get("gcode_file") or
            parsed_payload.get("file")
        )
        if not name:
            return None
        name_str = str(name).strip()
        return name_str if name_str and name_str != "Unnamed Job" else None

    def _get_or_prefetch_gcode_weight(
        self,
        session: Session,
        job: Job,
        job_info: Dict[str, Any],
        parsed_payload: Dict[str, Any],
        printer: Optional[Printer],
    ) -> Optional[float]:
        """
        Holt einmalig das erwartete Job-Gewicht aus dem G-Code (falls verfuegbar).
        Ergebnis wird in job_info gecached und fuer Live-Schaetzung genutzt.
        """
        cached = job_info.get("prefetched_gcode_weight")
        if isinstance(cached, (int, float)) and float(cached) > 0:
            return float(cached)

        if job_info.get("prefetched_weight_attempted"):
            return None
        job_info["prefetched_weight_attempted"] = True

        if not printer or not printer.ip_address or not printer.api_key:
            return None

        task_id = job.task_id or parsed_payload.get("print", {}).get("task_id")
        if not task_id:
            return None

        gcode_filename = (
            parsed_payload.get("print", {}).get("gcode_file")
            or parsed_payload.get("print", {}).get("subtask_name")
            or parsed_payload.get("gcode_file")
            or parsed_payload.get("subtask_name")
            or job.name
            or "unknown"
        )

        try:
            from app.services.gcode_ftp_service import get_gcode_ftp_service

            ftp_service = get_gcode_ftp_service()

            # Versuche Details zu laden (Gesamt + per-Filament für Multi-Color)
            details = ftp_service.download_gcode_details(
                printer_ip=printer.ip_address,
                api_key=printer.api_key,
                task_id=str(task_id),
                gcode_filename=str(gcode_filename),
            )
            weight = details.get("total_weight")
            per_filament: list = details.get("per_filament") or []

            if weight is not None and float(weight) > 0:
                weight_f = float(weight)
                job_info["prefetched_gcode_weight"] = weight_f
                self.logger.info(
                    f"[JOB UPDATE] Prefetched G-Code weight={weight_f:.2f}g "
                    f"for job={job.id} task_id={task_id}"
                )

            # Per-Filament Gewichte als Slot-Map speichern (Index = AMS-Slot)
            if per_filament:
                slot_weight_map = {i: w for i, w in enumerate(per_filament) if w > 0}
                job_info["gcode_weight_per_slot"] = slot_weight_map
                self.logger.info(
                    f"[JOB UPDATE] Per-Slot G-Code Gewichte: {slot_weight_map} "
                    f"(Multi-Color: {len(slot_weight_map)} Slots)"
                )

            if weight is not None and float(weight) > 0:
                return float(weight)

        except Exception as e:
            self.logger.debug(f"[JOB UPDATE] G-Code weight prefetch failed for job={job.id}: {e}")

        return None


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
            spool: Spulen-Objekt (fÃ¼r Gewichtsberechnung)
            start_remain: Start-Restmenge in %
            end_remain: End-Restmenge in %
            start_total_len: Totale LÃ¤nge in mm

        Returns:
            (used_mm, used_g)
        """
        if start_remain is None or end_remain is None:
            return 0.0, 0.0

        # FIX: Bambu Lab's "remain" ist EXTREM unzuverlÃ¤ssig und kann sogar steigen!
        # Wir ignorieren Anstiege (bleiben beim letzten Wert)
        # Dies ist eine defensive Strategie, um negative VerbrÃ¤uche zu vermeiden
        used_percent = max(0.0, float(start_remain) - float(end_remain))

        # Wenn remain GESTIEGEN ist (end_remain > start_remain), ist used_percent = 0
        # Das ist technisch korrekt, aber wir verlieren Tracking-Genauigkeit

        # LÃ¤nge in mm
        used_mm = (used_percent / 100.0) * float(start_total_len) if start_total_len else 0.0

        # Gewicht in g
        used_g = 0.0
        if spool and spool.weight_full is not None and spool.weight_empty is not None:
            used_g = (used_percent / 100.0) * (float(spool.weight_full) - float(spool.weight_empty))

        return used_mm, used_g

    def _update_spool_weight_from_remain(
        self,
        spool: Spool,
        remain_percent: float
    ) -> None:
        """
        Aktualisiert Spulen-Gewicht basierend auf remain-Prozent.

        Berechnet direkt aus dem gemeldeten Prozentsatz statt
        inkrementell, um Fehlerakkumulation zu vermeiden.

        Formel: weight_current = weight_empty + (remain% / 100 * net_weight)

        Args:
            spool: Spulen-Objekt
            remain_percent: Verbleibende Filament-Menge in % (0-100)
        """
        if spool.weight_full is None or spool.weight_empty is None:
            self.logger.debug(
                f"[WEIGHT] Spule {spool.id}: Kann Gewicht nicht berechnen - "
                f"weight_full oder weight_empty fehlt"
            )
            return

        net_weight = float(spool.weight_full) - float(spool.weight_empty)
        new_weight = float(spool.weight_empty) + (float(remain_percent) / 100.0 * net_weight)

        # Validierung & Capping
        if new_weight < float(spool.weight_empty):
            self.logger.warning(
                f"[WEIGHT] Spule {spool.id}: Berechnetes Gewicht ({new_weight:.1f}g) "
                f"unter Leergewicht ({spool.weight_empty}g) - auf Leergewicht begrenzt"
            )
            new_weight = float(spool.weight_empty)
        elif new_weight > float(spool.weight_full):
            self.logger.warning(
                f"[WEIGHT] Spule {spool.id}: Berechnetes Gewicht ({new_weight:.1f}g) "
                f"ueber Vollgewicht ({spool.weight_full}g) - auf Vollgewicht begrenzt"
            )
            new_weight = float(spool.weight_full)

        # Log nur bei signifikanter Aenderung (> 1g)
        if spool.weight_current is None or abs(new_weight - spool.weight_current) > 1.0:
            old_weight_text = f"{float(spool.weight_current):.1f}" if spool.weight_current is not None else "NULL"
            self.logger.debug(
                f"[WEIGHT] Spule {spool.id}: "
                f"{old_weight_text}g -> "
                f"{new_weight:.1f}g (remain={remain_percent:.2f}%)"
            )

        spool.weight_current = new_weight

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
        """Speichert Job-Snapshot in JSON-Datei fÃ¼r Server-Neustart-Recovery"""
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
                    self.logger.exception("[SNAPSHOT] Failed to remove temp snapshot file %s", tmp_path)

    def _load_snapshot(self, cloud_serial: str, printer_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """LÃ¤dt Job-Snapshot fÃ¼r einen Drucker"""
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
        """LÃ¶scht Job-Snapshot nach Job-Ende"""
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
                    self.logger.exception("[SNAPSHOT] Failed to remove temp snapshot file %s", tmp_path)

    def _find_tray(
        self,
        ams_units: List[Dict[str, Any]],
        slot: Optional[int],
        parsed_payload: Optional[Dict[str, Any]] = None,
        printer: Optional['Printer'] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Findet Tray-Info fÃ¼r einen bestimmten Slot.

        UnterstÃ¼tzt:
        - AMS-Trays (aus ams_units)
        - Externe Spulen (aus vt_tray bei slot 254/255)

        Args:
            ams_units: Liste von AMS-Units
            slot: Slot-Nummer (0-3 fÃ¼r AMS, 254/255 fÃ¼r externe Spule)
            parsed_payload: MQTT-Payload (optional, fÃ¼r vt_tray)
            printer: Printer-Objekt (optional, fÃ¼r externe Spulen-Erkennung)

        Returns:
            Tray-Info Dict oder None
        """
        if slot is None:
            return None

        # NEU: Externe Spulen via vt_tray
        # PrÃ¼fe ob es eine externe Spule ist (254 fÃ¼r A-Serie, 255 fÃ¼r X1/P-Serie)
        if printer and parsed_payload and is_external_tray(printer, slot):
            vt_tray = parsed_payload.get("print", {}).get("vt_tray")
            if vt_tray and isinstance(vt_tray, dict):
                vt_tray_id = vt_tray.get("id")
                if vt_tray_id is not None:
                    try:
                        if int(vt_tray_id) == int(slot):
                            self.logger.debug(
                                f"[TRAY] Found vt_tray for external slot={slot}, "
                                f"remain={vt_tray.get('remain')}, type={vt_tray.get('tray_type')}"
                            )
                            return vt_tray  # âœ… vt_tray als Tray-Info
                    except (ValueError, TypeError):
                        self.logger.warning(f"[TRAY] Invalid vt_tray id={vt_tray_id}")

        # BESTEHEND: AMS-Trays (unverÃ¤ndert)
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
        Extrahiert print.filament_used_mm aus verschiedenen mÃ¶glichen Pfaden.

        Args:
            parsed_payload: Geparste MQTT Payload

        Returns:
            Filament-verbrauch in mm oder None falls nicht vorhanden
        """
        # PrimÃ¤rquelle: print.filament_used_mm
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
                    self.logger.exception(
                        "[FILAMENT] Failed to parse filament_used_mm from print.filament_used_mm=%s",
                        filament_used,
                    )

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
                        self.logger.exception(
                            "[FILAMENT] Failed to parse filament_used_mm from print.3D.filament_used_mm=%s",
                            filament_used,
                        )

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
                self.logger.exception(
                    "[FILAMENT] Failed to parse filament_used_mm from filament_used_mm=%s",
                    filament_used,
                )

        return None

    def _get_density_g_per_m(self, spool_id: str, session: Session) -> float:
        """
        Berechnet Filament-Density in g/m aus dem Material der Spule.

        Args:
            spool_id: ID der Spule
            session: SQLModel Session

        Returns:
            Density in g/m (Fallback: 2.4 fÃ¼r PLA 1.75mm)
        """
        try:
            spool = session.get(Spool, spool_id)
            if not spool or not spool.material_id:
                self.logger.debug(
                    f"[DENSITY] No material for spool {spool_id}, using fallback 2.4 g/m"
                )
                return 2.4

            material = session.get(Material, spool.material_id)
            if not material:
                self.logger.debug(
                    f"[DENSITY] Material {spool.material_id} not found, using fallback 2.4 g/m"
                )
                return 2.4

            # Berechne Density von g/cmÂ³ zu g/m
            # Formel: density_g_per_cm3 * (Ï€ * (diameter/2)Â²) * 100
            # diameter in mm -> radius in cm -> area in cmÂ² -> * 100cm = g/m
            import math
            radius_cm = (material.diameter / 10.0) / 2.0  # mm -> cm -> radius
            area_cm2 = math.pi * radius_cm * radius_cm
            density_g_per_m = material.density * area_cm2 * 100.0

            self.logger.debug(
                f"[DENSITY] Calculated density for spool {spool_id}: "
                f"{density_g_per_m:.2f} g/m (material={material.name}, "
                f"density={material.density} g/cmÂ³, diameter={material.diameter}mm)"
            )

            return density_g_per_m

        except Exception as e:
            self.logger.exception(
                f"[DENSITY] Error calculating density for spool {spool_id}: {e}"
            )
            return 2.4  # Fallback

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
            self.logger.exception("[FILAMENT] Invalid total_len value=%s", total_len)
            return None

        remain = tray_info.get("remain")
        if remain is None:
            return None

        try:
            remain_percent = float(remain)
        except (ValueError, TypeError):
            self.logger.exception("[FILAMENT] Invalid remain percent value=%s", remain)
            return None

        # Berechne: total_len_mm * (1 - remain_percent / 100)
        filament_used_mm = total_len_mm * (1 - remain_percent / 100.0)
        return max(0.0, filament_used_mm)  # Keine negativen Werte

    def _calculate_weight_from_length(
        self,
        length_mm: float,
        material_type: Optional[str] = None,
        diameter_mm: float = 1.75
    ) -> float:
        """
        Berechnet Gewicht aus Filament-LÃ¤nge fÃ¼r Spulen ohne RFID.

        Wird verwendet wenn:
        - Externe Spule (print_source="external")
        - Kein RFID (remain=0, used_g=0)
        - LÃ¤nge verfÃ¼gbar (filament_used_mm > 0)

        Formel: Gewicht = Volumen Ã— Dichte
        Volumen = LÃ¤nge Ã— QuerschnittsflÃ¤che

        Args:
            length_mm: Filament-LÃ¤nge in mm
            material_type: Material-Typ (PLA, PETG, ABS, etc.)
            diameter_mm: Filament-Durchmesser in mm (Standard: 1.75)

        Returns:
            Berechnetes Gewicht in g
        """
        # Material-Dichten (g/cmÂ³) - Typische Werte
        MATERIAL_DENSITIES = {
            "PLA": 1.24,
            "PETG": 1.27,
            "ABS": 1.04,
            "TPU": 1.21,
            "ASA": 1.07,
            "PA": 1.14,      # Nylon
            "PC": 1.20,
            "PLA-CF": 1.29,  # Carbon Fiber
            "PETG-CF": 1.30,
            "PA-CF": 1.18
        }

        # Material-Typ normalisieren (GroÃŸbuchstaben, Leerzeichen entfernen)
        material_key = material_type.upper().strip() if material_type else "PLA"
        density = MATERIAL_DENSITIES.get(material_key, 1.24)  # Default: PLA

        # Geometrische Berechnung
        radius_cm = (diameter_mm / 2.0) / 10.0  # mm -> cm
        area_cm2 = 3.14159265359 * (radius_cm ** 2)  # KreisflÃ¤che
        length_cm = length_mm / 10.0  # mm -> cm

        # Gewicht = Volumen Ã— Dichte
        weight_g = length_cm * area_cm2 * density

        self.logger.debug(
            f"[WEIGHT] Calculated from length: {length_mm:.1f}mm Ã— {material_key} "
            f"(density={density}) = {weight_g:.2f}g"
        )

        return weight_g

    def _validate_cloud_task_match(
        self,
        job: Job,
        cloud_task: Any,
        printer_cloud_serial: Optional[str]
    ) -> tuple[bool, str, float]:
        """
        Validiert ob ein Cloud-Task zum lokalen Job passt.

        FÃ¼hrt mehrere Sicherheitschecks durch:
        1. Task-ID Match (hÃ¶chste PrioritÃ¤t)
        2. Drucker-Serial Match
        3. Zeitfenster-Check (Â±3 Minuten)
        4. Name-Ã„hnlichkeit (optional)

        Args:
            job: Lokaler Job aus DB
            cloud_task: Task aus Bambu Cloud API
            printer_cloud_serial: Cloud-Serial des Druckers

        Returns:
            (is_valid, reason, confidence_score)
            - is_valid: True wenn Match sicher genug
            - reason: Beschreibung des Match-Grundes oder Fehlers
            - confidence_score: 0.0-1.0 (1.0 = perfekter Match)
        """
        from datetime import timedelta

        confidence = 0.0
        reasons = []

        # 1. Task-ID Match (40% Gewichtung) - wichtigster Check
        if job.task_id and cloud_task.id:
            if str(job.task_id) == str(cloud_task.id):
                confidence += 0.4
                reasons.append("task_id_match")
            else:
                # Task-ID vorhanden aber stimmt nicht Ã¼berein = definitiv falscher Task
                return False, "task_id_mismatch", 0.0

        # 2. Drucker-Serial Match (30% Gewichtung)
        if printer_cloud_serial and cloud_task.device_id:
            if str(printer_cloud_serial) == str(cloud_task.device_id):
                confidence += 0.3
                reasons.append("device_match")
            else:
                # Falscher Drucker = definitiv falscher Task
                return False, "device_mismatch", 0.0

        # 3. Zeitfenster-Check (20% Gewichtung)
        time_valid = False
        if job.finished_at and cloud_task.end_time:
            try:
                # Parse Cloud-Zeit (kann verschiedene Formate haben)
                cloud_end = cloud_task.end_time
                if isinstance(cloud_end, str):
                    # ISO 8601 Format parsen (Standard fÃ¼r Bambu Cloud API)
                    # Formate: "2026-01-31T12:30:45Z", "2026-01-31T12:30:45+00:00"
                    cloud_end_str = cloud_end.replace("Z", "+00:00")
                    try:
                        cloud_end = datetime.fromisoformat(cloud_end_str)
                    except ValueError:
                        # Fallback: Versuche ohne Timezone
                        cloud_end = datetime.fromisoformat(cloud_end.split("+")[0].split("Z")[0])

                # Mache job.finished_at timezone-aware wenn nÃ¶tig
                job_finished = job.finished_at
                if job_finished.tzinfo is None and hasattr(cloud_end, 'tzinfo') and cloud_end.tzinfo is not None:
                    job_finished = job_finished.replace(tzinfo=cloud_end.tzinfo)
                elif hasattr(job_finished, 'tzinfo') and job_finished.tzinfo is not None and (not hasattr(cloud_end, 'tzinfo') or cloud_end.tzinfo is None):
                    cloud_end = cloud_end.replace(tzinfo=job_finished.tzinfo)

                time_diff = abs((job_finished - cloud_end).total_seconds())

                if time_diff <= 180:  # Â±3 Minuten
                    confidence += 0.2
                    reasons.append(f"time_match({int(time_diff)}s)")
                    time_valid = True
                elif time_diff <= 600:  # Â±10 Minuten - noch akzeptabel mit Warnung
                    confidence += 0.1
                    reasons.append(f"time_close({int(time_diff)}s)")
                    time_valid = True
                else:
                    reasons.append(f"time_mismatch({int(time_diff)}s)")
            except Exception as e:
                self.logger.warning(f"[CLOUD VALIDATE] Time comparison failed: {e}")
                reasons.append("time_parse_error")

        # 4. Name-Ã„hnlichkeit (10% Gewichtung)
        if job.name and cloud_task.title:
            job_name_lower = job.name.lower().strip()
            cloud_name_lower = cloud_task.title.lower().strip()

            # Exakter Match
            if job_name_lower == cloud_name_lower:
                confidence += 0.1
                reasons.append("name_exact_match")
            # Teilweise Match (einer enthÃ¤lt den anderen)
            elif job_name_lower in cloud_name_lower or cloud_name_lower in job_name_lower:
                confidence += 0.05
                reasons.append("name_partial_match")

        # Entscheidung: Mindestens 50% Confidence fÃ¼r automatischen Match
        is_valid = confidence >= 0.5
        reason = ", ".join(reasons) if reasons else "no_match_criteria"

        self.logger.info(
            f"[CLOUD VALIDATE] Job '{job.name}' vs Cloud '{cloud_task.title}': "
            f"valid={is_valid}, confidence={confidence:.0%}, reasons={reason}"
        )

        return is_valid, reason, confidence

    async def _fetch_cloud_fallback_data_async(
        self,
        job_id: str,
        printer_id: str,
        printer_cloud_serial: Optional[str],
        task_id: Optional[str],
        job_name: str,
        job_finished_at: Optional[datetime]
    ) -> Optional[Dict[str, Any]]:
        """
        Async-Version: Holt Filament-Verbrauchsdaten aus der Bambu Cloud API als Fallback.

        Wird aufgerufen wenn:
        - Job ist completed
        - MQTT-Tracking hat keine/unvollstÃ¤ndige Daten (used_g=0 oder keine JobSpoolUsage)

        Sicherheits-Features:
        - Validiert Cloud-Task mit mehreren Kriterien (task_id, device, time, name)
        - Nur Tasks mit â‰¥50% Confidence werden akzeptiert
        - Loggt alle Match-Entscheidungen fÃ¼r Audit

        Args:
            job_id: Job-ID in der DB
            printer_id: Printer-ID in der DB
            printer_cloud_serial: Cloud-Serial des Druckers
            task_id: Bambu Cloud Task-ID (kann None sein)
            job_name: Job-Name fÃ¼r Matching
            job_finished_at: Job-Ende-Zeit fÃ¼r Zeitfenster-Check

        Returns:
            Dict mit:
            - total_used_g: Gesamtverbrauch in Gramm
            - usages_created: Anzahl erstellter JobSpoolUsage EintrÃ¤ge
            - spools_updated: Liste der aktualisierten Spool-IDs
            - match_confidence: Confidence-Score des Matches
            - match_reason: Grund fÃ¼r den Match
        """
        from app.models.bambu_cloud_config import BambuCloudConfig
        from app.services.bambu_cloud_service import BambuCloudService
        from app.services.token_encryption import decrypt_token
        from app.models.job import JobSpoolUsage
        from app.models.weight_history import WeightHistory

        cloud_service = None

        # Eigene Session erstellen (thread-safe)
        with Session(engine) as session:
            # 1. Cloud-Konfiguration laden
            config = session.exec(select(BambuCloudConfig)).first()
            if not config or not config.access_token_encrypted:
                self.logger.warning("[CLOUD FALLBACK] No cloud config or token available")
                return None

            if not config.sync_enabled:
                self.logger.debug("[CLOUD FALLBACK] Cloud sync is disabled")
                return None

            if config.sync_paused:
                self.logger.debug("[CLOUD FALLBACK] Cloud sync is paused")
                return None

            is_dry_run = config.dry_run_mode

            try:
                access_token = decrypt_token(config.access_token_encrypted)
            except Exception as e:
                self.logger.error(f"[CLOUD FALLBACK] Failed to decrypt token: {e}")
                return None

            region = config.region or "eu"

            # 2. Cloud Service erstellen und Tasks abrufen
            cloud_service = BambuCloudService(
                access_token=access_token,
                region=region
            )

            try:
                # Hole alle Tasks fÃ¼r diesen Drucker
                tasks = await cloud_service.get_tasks(device_id=printer_cloud_serial, limit=50)

                if not tasks:
                    self.logger.warning("[CLOUD FALLBACK] No tasks found in cloud")
                    return None

                # Job aus DB laden fÃ¼r Validierung
                job = session.get(Job, job_id)
                if not job:
                    self.logger.error(f"[CLOUD FALLBACK] Job {job_id} not found in DB")
                    return None

                # === SICHERHEITS-VALIDIERUNG ===
                # Finde den besten passenden Task mit Validierung
                matching_task = None
                best_confidence = 0.0
                match_reason = ""

                for task in tasks:
                    is_valid, reason, confidence = self._validate_cloud_task_match(
                        job, task, printer_cloud_serial
                    )

                    if is_valid and confidence > best_confidence:
                        matching_task = task
                        best_confidence = confidence
                        match_reason = reason

                        # Bei perfektem Match (task_id + device + time) sofort abbrechen
                        if confidence >= 0.9:
                            break

                if not matching_task:
                    self.logger.warning(
                        f"[CLOUD FALLBACK] No matching task found for job '{job_name}' "
                        f"(task_id={task_id}, searched {len(tasks)} tasks)"
                    )
                    return None

                # Log den gefundenen Match
                self.logger.info(
                    f"[CLOUD FALLBACK] Matched task: '{matching_task.title}' "
                    f"(confidence={best_confidence:.0%}, reason={match_reason})"
                )
                self.logger.info(
                    f"[CLOUD FALLBACK] Task details: weight={matching_task.weight}g, "
                    f"ams_mapping={len(matching_task.ams_mapping or [])} entries"
                )

                # 3. amsDetailMapping auswerten fÃ¼r Multi-Spool-Daten
                result = {
                    "total_used_g": matching_task.weight or 0,
                    "usages_created": 0,
                    "spools_updated": [],
                    "match_confidence": best_confidence,
                    "match_reason": match_reason
                }
                if not job:
                    self.logger.error(f"[CLOUD FALLBACK] Job {job_id} not found")
                    return None

                ams_mapping = matching_task.ams_mapping or []
                if not ams_mapping:
                    # Keine Multi-Spool-Daten, aber Gesamtgewicht vorhanden
                    if matching_task.weight > 0:
                        if is_dry_run:
                            self.logger.info(
                                f"[CLOUD FALLBACK DRY-RUN] Would update job total: {matching_task.weight}g"
                            )
                        else:
                            job.filament_used_g = matching_task.weight
                            job.filament_used_mm = matching_task.length or 0
                            session.add(job)
                            session.commit()
                            self.logger.info(
                                f"[CLOUD FALLBACK] Updated job total: {matching_task.weight}g"
                            )
                    return result

                # 4. FÃ¼r jeden Eintrag in amsDetailMapping: JobSpoolUsage erstellen
                order_index = 0
                for ams_entry in ams_mapping:
                    # amsDetailMapping Struktur (aus Cloud API):
                    # {
                    #   "ams_id": 0,           # AMS Unit ID
                    #   "slot_id": 0,          # Slot in AMS (0-3)
                    #   "weight": 8.22,        # Verbrauch in Gramm
                    #   "filament_id": "...",  # Filament-ID
                    #   "filament_type": "PLA",
                    #   "color": "FFFFFF"
                    # }
                    slot_id = ams_entry.get("slot_id")
                    ams_id = ams_entry.get("ams_id", 0)
                    weight_g = float(ams_entry.get("weight", 0) or 0)

                    if weight_g <= 0:
                        continue

                    # Berechne globalen Slot (AMS-Unit * 4 + Slot)
                    global_slot = (ams_id * 4) + slot_id if slot_id is not None else None

                    # Finde passende Spule in DB anhand von Slot und Drucker
                    spool = None
                    spool_id = None
                    if global_slot is not None:
                        spool = session.exec(
                            select(Spool)
                            .where(Spool.printer_id == printer_id)
                            .where(Spool.ams_slot == global_slot)
                        ).first()
                        if spool:
                            spool_id = spool.id

                    # PrÃ¼fe ob bereits ein Usage-Eintrag existiert
                    existing_usage = session.exec(
                        select(JobSpoolUsage)
                        .where(JobSpoolUsage.job_id == job_id)
                        .where(JobSpoolUsage.slot == global_slot)
                    ).first()

                    if existing_usage:
                        # Update existierenden Eintrag wenn Cloud mehr Daten hat
                        if weight_g > existing_usage.used_g:
                            existing_usage.used_g = weight_g
                            session.add(existing_usage)
                            self.logger.debug(
                                f"[CLOUD FALLBACK] Updated usage for slot {global_slot}: {weight_g}g"
                            )
                    else:
                        # Neuen JobSpoolUsage erstellen
                        usage = JobSpoolUsage(
                            job_id=job_id,
                            spool_id=spool_id,
                            slot=global_slot,
                            used_mm=0,  # Cloud gibt nur Gewicht, nicht LÃ¤nge
                            used_g=weight_g,
                            order_index=order_index
                        )
                        session.add(usage)
                        result["usages_created"] += 1
                        self.logger.info(
                            f"[CLOUD FALLBACK] Created usage: slot={global_slot}, "
                            f"spool_id={spool_id}, weight={weight_g}g"
                        )

                    # 5. Spulengewicht aktualisieren
                        if spool and spool.weight_current is not None:
                            old_weight = float(spool.weight_current)
                            new_weight = max(0, old_weight - weight_g)
                            spool.weight_current = new_weight
                            session.add(spool)
                            result["spools_updated"].append(spool_id)

                            # WeightHistory erstellen
                            weight_history = WeightHistory(
                                spool_uuid=(spool.tray_uuid or ""),
                                spool_number=spool.spool_number,
                                old_weight=old_weight,
                                new_weight=new_weight,
                                source="bambu_cloud",
                                change_reason="cloud_fallback_job_completed",
                                user="System",
                                details=f"Cloud fallback for job '{job_name}' (task_id: {task_id})"
                            )
                            session.add(weight_history)

                            self.logger.info(
                                f"[CLOUD FALLBACK] Updated spool {spool.spool_number}: "
                                f"{old_weight:.1f}g -> {new_weight:.1f}g (-{weight_g:.1f}g)"
                            )

                    order_index += 1

                # 6. Job-Gesamtwert aktualisieren
                if is_dry_run:
                    self.logger.info(
                        f"[CLOUD FALLBACK DRY-RUN] Would create {result['usages_created']} usages, "
                        f"update {len(result['spools_updated'])} spools, "
                        f"total={matching_task.weight}g"
                    )
                    session.rollback()
                else:
                    if matching_task.weight > 0:
                        job.filament_used_g = matching_task.weight
                        if matching_task.length:
                            job.filament_used_mm = matching_task.length
                        session.add(job)

                    session.commit()

                return result

            except Exception as e:
                self.logger.error(f"[CLOUD FALLBACK] Error fetching cloud data: {e}", exc_info=True)
                return None
            finally:
                if cloud_service:
                    await cloud_service.close()

    def _fetch_cloud_fallback_data(
        self,
        job: Job,
        printer: Optional['Printer'],
        session: Session
    ) -> Optional[Dict[str, Any]]:
        """
        Synchroner Wrapper fÃ¼r die async Cloud-Fallback-Funktion.

        Wird von _on_job_end aufgerufen wenn MQTT-Daten unvollstÃ¤ndig sind.

        Sicherheits-Features:
        - Task wird mit mehreren Kriterien validiert (nicht nur task_id)
        - Funktioniert auch ohne task_id (Ã¼ber Zeit + Name + Drucker)
        - Nur Tasks mit â‰¥50% Confidence werden akzeptiert
        """
        import asyncio

        # Extrahiere benÃ¶tigte Werte vor dem async-Aufruf
        job_id = job.id
        printer_id = job.printer_id
        printer_cloud_serial = printer.cloud_serial if printer else None
        task_id = job.task_id  # Kann None sein - Validierung findet trotzdem statt
        job_name = job.name or "Unknown"
        job_finished_at = job.finished_at

        # Mindestens Drucker-Serial oder task_id muss vorhanden sein
        if not printer_cloud_serial and not task_id:
            self.logger.debug("[CLOUD FALLBACK] No printer_cloud_serial and no task_id - cannot match")
            return None

        self.logger.info(
            f"[CLOUD FALLBACK] Starting fallback for job '{job_name}' "
            f"(task_id={task_id}, printer={printer_cloud_serial})"
        )

        try:
            # PrÃ¼fe ob bereits eine Event-Loop lÃ¤uft
            try:
                loop = asyncio.get_running_loop()
                # Loop lÃ¤uft bereits - erstelle Task in separatem Thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self._fetch_cloud_fallback_data_async(
                            job_id, printer_id, printer_cloud_serial,
                            task_id, job_name, job_finished_at
                        )
                    )
                    return future.result(timeout=30)
            except RuntimeError:
                # Keine Loop lÃ¤uft - normal ausfÃ¼hren
                return asyncio.run(
                    self._fetch_cloud_fallback_data_async(
                        job_id, printer_id, printer_cloud_serial,
                        task_id, job_name, job_finished_at
                    )
                )
        except Exception as e:
            self.logger.error(f"[CLOUD FALLBACK] Sync wrapper error: {e}", exc_info=True)
            return None

    def _finalize_current(
        self,
        session: Session,
        info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Berechnet finalen Verbrauch fÃ¼r aktuellen Slot

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

        # Fallback: Wenn remain->g nicht berechenbar war, aber mm vorliegt,
        # berechne Gewicht ueber Material-Dichte.
        if used_mm > 0 and used_g <= 0:
            spool_id_val = info.get("spool_id")
            if isinstance(spool_id_val, str) and spool_id_val:
                density_g_per_m = self._get_density_g_per_m(spool_id_val, session)
            else:
                density_g_per_m = 2.4
            used_g = (used_mm / 1000.0) * density_g_per_m

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
        Hauptfunktion: Verarbeitet eine MQTT Message fÃ¼r Job-Tracking

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
        # === DEBUG LOGGING: Zeige empfangene Payload und Statuswerte ===
        self.logger.debug(f"[JOB TRACKING] MQTT-Payload fÃ¼r {cloud_serial}: {parsed_payload}")
        debug_gstate = parsed_payload.get("print", {}).get("gcode_state") or parsed_payload.get("gcode_state")
        debug_mc_percent = parsed_payload.get("print", {}).get("mc_percent")
        self.logger.debug(f"[JOB TRACKING] gcode_state={debug_gstate}, mc_percent={debug_mc_percent}, printer_id={printer_id}")

        # Hat dieser Drucker einen aktiven Job?
        has_active_job = cloud_serial in self.active_jobs

        # State-Mapping fÃ¼r Bambu Lab Drucker
        PRINT_STATES = {
            "PRINTING", "RUNNING",
            "PURGING", "CHANGING_FILAMENT", "CALIBRATING"  # ZÃ¤hlt als aktiver Druck
        }
        COMPLETED_STATES = {"FINISH", "FINISHED", "COMPLETED", "COMPLETE"}
        FAILED_STATES = {"FAILED", "ERROR", "EXCEPTION"}
        ABORTED_STATES = {"ABORT", "ABORTED", "STOPPED", "CANCELLED", "CANCELED"}

        # ===================================================================
        # JOB START
        # ===================================================================
        if not has_active_job and current_gstate in PRINT_STATES:
            # Cooldown-Check: Post-Print-Signale (PURGING, CHANGING_FILAMENT) nach Job-Ende ignorieren
            import time as _t
            _cooldown_ts = self._job_finish_cooldown.get(cloud_serial, 0.0)
            if (_t.monotonic() - _cooldown_ts) < self._JOB_FINISH_COOLDOWN_SECS:
                self.logger.debug(
                    f"[JOB START] Cooldown aktiv für {cloud_serial} – "
                    f"ignoriere Post-Print-Signal gcode_state={current_gstate!r}"
                )
                return None
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
        # A1 Mini sendet kein gcode_state â†’ PrÃ¼fe auch mc_percent == 100
        finish_by_gcode_state = (
            current_gstate in COMPLETED_STATES or
            current_gstate in FAILED_STATES or
            current_gstate in ABORTED_STATES
        )
        # A1 Mini Fix: current_gstate ist niemals None (default ""), sondern
        # entweder "" (kein state gesendet) oder "IDLE" (nach Druckende).
        # Beide Fälle müssen als "kein aktiver Druckstatus" erkannt werden.
        finish_by_progress = (
            has_active_job and
            current_gstate in ("", "IDLE") and  # A1 Mini: kein state ("") oder IDLE nach Druck
            parsed_payload.get("print", {}).get("mc_percent") == 100
        )
        
        if has_active_job and (finish_by_gcode_state or finish_by_progress):
            return self._handle_job_finish(
                cloud_serial,
                parsed_payload,
                ams_data,
                current_gstate or "FINISH",  # Fallback wenn kein gcode_state
                COMPLETED_STATES,
                FAILED_STATES,
                ABORTED_STATES
            )

        # ===================================================================
        # NACHSTART-FIX: Job war noch "running" in DB nach Server-Neustart
        # ===================================================================
        # Wenn kein aktiver Job im RAM ist (Neustart) aber der Drucker ein
        # Finish-Signal sendet ("FINISH", "IDLE"+100%, "")+100%):
        # → laufenden DB-Job für diesen Drucker wiederherstellen und abschließen.
        #
        # Bekannte Fälle:
        #   A1 Mini: sendet gcode_state="FINISH" ODER IDLE+100% nach Neustart
        #   Bambu allgemein: sendet FINISH/COMPLETED nach Neustart
        _is_finish_signal = (
            finish_by_gcode_state or  # FINISH, COMPLETED, FAILED, ABORT, ...
            (current_gstate in ("", "IDLE") and parsed_payload.get("print", {}).get("mc_percent") == 100)
        )
        if not has_active_job and _is_finish_signal:
            try:
                with Session(engine) as _sess:
                    _running_job = _sess.exec(
                        select(Job).where(
                            Job.printer_id == printer_id,
                            Job.status == "running",
                            Job.finished_at == None
                        ).order_by(Job.started_at.desc())
                    ).first()

                    if _running_job:
                        self.logger.info(
                            f"[NACHSTART-FIX] Job {_running_job.id} war 'running' nach Neustart. "
                            f"Drucker meldet gcode_state='{current_gstate}' → restore + finish."
                        )
                        # Job kurz in RAM eintragen damit _handle_job_finish greift
                        self.active_jobs[cloud_serial] = {
                            "job_id": _running_job.id,
                            "printer_id": printer_id,
                            "slot": None,
                            "spool_id": _running_job.spool_id,
                            "start_remain": None,
                            "last_remain": None,
                            "start_total_len": None,
                            "usages": [],
                        }
                        return self._handle_job_finish(
                            cloud_serial,
                            parsed_payload,
                            ams_data,
                            "FINISH",
                            COMPLETED_STATES,
                            FAILED_STATES,
                            ABORTED_STATES
                        )
            except Exception as _e:
                self.logger.error(f"[A1 MINI NACHSTART] Fehler beim Nachstart-Fix: {_e}")

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
            from sqlmodel import select
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

                # Kalibrierungsjobs ignorieren (kein echter Druckauftrag fuer Historie/Verbrauch)
                job_name_norm = str(job_name).replace("\\", "/").split("/")[-1].strip().lower()
                calibration_markers = (
                    "auto_cali_for_user_param",
                    "auto_cali",
                    "calibration.gcode",
                )
                if any(marker in job_name_norm for marker in calibration_markers):
                    self.logger.info(f"[JOB START] Ignoring calibration job '{job_name}'")
                    return None

                # Extrahiere Bambu Cloud Task ID (fÃ¼r zukÃ¼nftige Cloud-Integration)
                task_id = parsed_payload.get("print", {}).get("task_id")
                if task_id:
                    self.logger.debug(f"[JOB START] Extracted task_id={task_id} from MQTT payload")
                    
                    # DEDUPLICATION: PrÃ¼fe, ob bereits ein Job mit dieser task_id existiert
                    existing_job_with_task = session.exec(
                        select(Job)
                        .where(Job.printer_id == printer_id)
                        .where(Job.task_id == str(task_id))
                        .where(Job.status == "running")
                    ).first()
                    
                    if existing_job_with_task:
                        # Job mit dieser task_id existiert bereits â†’ in RAM laden
                        self.logger.info(
                            f"[JOB START] Job with task_id={task_id} already exists (job={existing_job_with_task.id}). "
                            f"Skipping duplicate creation (deduplication)."
                        )
                        
                        # PrÃ¼fe, ob Job bereits in active_jobs ist
                        if cloud_serial not in self.active_jobs:
                            # Job in RAM laden (kÃ¶nnte nach Server-Neustart fehlen)
                            spool = session.get(Spool, existing_job_with_task.spool_id) if existing_job_with_task.spool_id else None
                            self.active_jobs[cloud_serial] = {
                                "job_id": existing_job_with_task.id,
                                "printer_id": printer_id,
                                "slot": None,  # Wird bei nÃ¤chstem Update aktualisiert
                                "spool_id": spool.id if spool else None,
                                "start_remain": None,
                                "last_remain": None,
                                "start_total_len": None,
                                "usages": [],
                                "filament_start_mm": None,
                                "filament_started": False,
                                "using_fallback": False,
                                "fallback_warned": False,
                                "spool_binding_attempted": False,
                                "no_spool_warned": False,
                                "job_name_updated": existing_job_with_task.name != "Unnamed Job",
                                "no_name_warned": False,
                            }
                            self.logger.info(f"[JOB START] Loaded existing job into RAM: job={existing_job_with_task.id}")
                        
                        return {"job_id": existing_job_with_task.id, "status": "running"}

                # Aktuelle Layer/Fortschritt aus MQTT
                current_layer = parsed_payload.get("print", {}).get("layer_num") or 0

                current_percent = parsed_payload.get("print", {}).get("mc_percent") or 0

                # Aktiven Slot finden + externe Spulen-Erkennung (modellabhÃ¤ngig)
                active_slot = None
                is_external = False
                # A1 Mini: ams ist direkt unter payload, X1C: unter print.ams
                ams_block = parsed_payload.get("ams") or parsed_payload.get("print", {}).get("ams") or {}
                self.logger.info(f"[DEBUG-AMS] ams_block keys: {list(ams_block.keys()) if ams_block else 'NONE'}")
                tray_now = ams_block.get("tray_now")
                tray_tar = ams_block.get("tray_tar")
                self.logger.info(f"[DEBUG-AMS] RAW tray_tar={tray_tar}, tray_now={tray_now}")

                # KRITISCH: tray_tar/tray_now kommen als Strings ("254"), mÃ¼ssen zu int konvertiert werden
                if tray_tar is not None:
                    try:
                        tray_tar = int(tray_tar)
                    except (ValueError, TypeError):
                        tray_tar = None

                if tray_now is not None:
                    try:
                        tray_now = int(tray_now)
                    except (ValueError, TypeError):
                        tray_now = None

                # ZusÃ¤tzlich: vt_tray prÃ¼fen (A-Serie nutzt vt_tray fÃ¼r externe Spule)
                vt_tray = parsed_payload.get("print", {}).get("vt_tray")
                self.logger.info(f"[DEBUG-VT] vt_tray={vt_tray}")
                vt_tray_id = vt_tray.get("id") if isinstance(vt_tray, dict) else None
                self.logger.info(f"[DEBUG-VT] vt_tray_id={vt_tray_id} (type={type(vt_tray_id)})")
                if vt_tray_id is not None:
                    try:
                        vt_tray_id = int(vt_tray_id)
                        self.logger.info(f"[DEBUG-VT] vt_tray_id after int()={vt_tray_id}")
                    except (ValueError, TypeError):
                        vt_tray_id = None
                        self.logger.warning(f"[DEBUG-VT] Failed to convert vt_tray_id to int")

                # Lade Printer fÃ¼r modellabhÃ¤ngige Tray-Erkennung
                printer = session.get(Printer, printer_id)

                # Externe Spulen-Erkennung (A-Serie: 254, X1/P: 255)
                #
                # FIX A1 Mini AMS Lite: vt_tray.id=254 ist IMMER vorhanden, auch bei AMS-Drucken.
                # tray_tar / tray_now haben Vorrang. Nur wenn BEIDE extern/None sind, gilt vt_tray.
                has_ams_slot = (
                    (tray_tar is not None and not is_external_tray(printer, tray_tar)) or
                    (tray_now is not None and not is_external_tray(printer, tray_now))
                )

                if has_ams_slot:
                    # Aktiver AMS-Slot hat Vorrang – kein externer Druck
                    is_external = False
                    if tray_tar is not None and not is_external_tray(printer, tray_tar):
                        active_slot = int(tray_tar)
                    elif tray_now is not None and not is_external_tray(printer, tray_now):
                        active_slot = int(tray_now)
                elif (is_external_tray(printer, tray_tar) or
                      is_external_tray(printer, tray_now) or
                      is_external_tray(printer, vt_tray_id)):
                    is_external = True
                    active_slot = None
                    detected_tray = tray_tar or tray_now or vt_tray_id
                    self.logger.info(
                        f"[JOB START] Detected external print (tray_id={detected_tray}) "
                        f"for printer={printer_id} series={getattr(printer, 'series', 'UNKNOWN')}"
                    )

                # === SNAPSHOT-BASIERTE ERKENNUNG: Server-Neustart vs. Neuer Job ===
                snapshot = self._load_snapshot(cloud_serial, printer_id)
                existing_jobs = session.exec(
                    select(Job)
                    .where(Job.printer_id == printer_id)
                    .where(Job.status == "running")
                    .order_by(cast(Any, Job.started_at))
                ).all()

                # CLEANUP: Duplikate lÃ¶schen (behalte Ã¤ltesten)
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

                # PrÃ¼fe ob existing Job wiederhergestellt werden soll
                should_restore = False
                if existing_job and snapshot:
                    # Validierung: Ist das der gleiche Druck?
                    job_age = datetime.utcnow() - existing_job.started_at

                    # Check 1: Job zu alt (>48h) â†’ stale
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
                        # Fortschritt passt â†’ gleicher Druck, Server-Neustart!
                        should_restore = True
                        self.logger.info(
                            f"[JOB START] Detected server restart. "
                            f"Restoring job={existing_job.id} "
                            f"(layer: {snapshot.get('layer_num')}â†’{current_layer}, "
                            f"progress: {snapshot.get('mc_percent')}%â†’{current_percent}%)"
                        )

                    else:
                        # Fortschritt NICHT gestiegen â†’ neuer Druck!
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
                    # Job existiert aber kein Snapshot â†’ vermutlich alter stale Job
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
                    # Tray-Info fÃ¼r remain-Tracking
                    # NEU: Bei externen Spulen vt_tray verwenden
                    tray_info = self._find_tray(
                        ams_data or [],
                        active_slot,
                        parsed_payload=parsed_payload,
                        printer=printer
                    ) if active_slot is not None else None
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
                        "spool_binding_attempted": existing_job.spool_id is not None,
                        "no_spool_warned": False,
                        "job_name_updated": existing_job.name != "Unnamed Job",
                        "no_name_warned": False,
                    }

                    return {"job_id": existing_job.id, "status": "restored"}

                # === NEUER JOB ERSTELLEN ===

                # Spule finden (via ams_slot ODER externe Spule)
                spool = None
                if active_slot is not None:
                    # AMS-Slot (0-3)
                    spool = session.exec(
                        select(Spool)
                        .where(Spool.printer_id == printer_id)
                        .where(Spool.ams_slot == active_slot)
                    ).first()
                elif is_external:
                    # Externe Spule (tray_id 254/255)
                    external_tray_id = get_external_tray_id(printer)
                    spool = session.exec(
                        select(Spool)
                        .where(Spool.printer_id == printer_id)
                        .where(Spool.ams_slot == external_tray_id)
                    ).first()
                    if spool:
                        self.logger.info(
                            f"[JOB START] Bound external spool={spool.id} "
                            f"(tray={external_tray_id}) to job"
                        )

                # Job erstellen mit print_source und task_id
                new_job = Job(
                    printer_id=printer_id,
                    spool_id=spool.id if spool else None,
                    name=job_name,
                    task_id=task_id,  # Bambu Cloud Task ID (kann None sein)
                    started_at=datetime.utcnow(),
                    filament_used_mm=0,
                    filament_used_g=0,
                    status="running",
                    print_source="external" if is_external else ("ams" if active_slot is not None else "unknown")
                )

                session.add(new_job)
                session.commit()
                session.refresh(new_job)

                # === FIX Bug #1: GEWICHTS-TRACKING INITIALISIEREN ===
                # Snapshot: Aktuelles Spulen-Gewicht bei Job-Start speichern
                if spool:
                    if spool.weight_current is not None and spool.weight_current > 0:
                        new_job.start_weight = spool.weight_current
                        session.add(new_job)
                        session.commit()
                        self.logger.info(
                            f"[WEIGHT] Job {new_job.id} ({new_job.name}): "
                            f"start_weight={spool.weight_current:.1f}g "
                            f"von Spule {spool.id} (slot={active_slot})"
                        )
                    else:
                        self.logger.warning(
                            f"[WEIGHT] Job {new_job.id} ({new_job.name}): "
                            f"Spule {spool.id} hat keine Gewichtsdaten"
                        )
                else:
                    self.logger.warning(
                        f"[WEIGHT] Job {new_job.id} ({new_job.name}): "
                        f"Ohne Spule gestartet (slot={active_slot})"
                    )

                # Spulen-Status aktualisieren (fÃ¼r ALLE Spulen, nicht nur mit spool_number)
                if spool and not spool.is_empty:
                    if spool.status != "Aktiv":
                        spool.status = "Aktiv"
                        spool.is_open = True
                        session.add(spool)
                        session.commit()

                # Job-Info in RAM speichern
                # NEU: Bei externen Spulen vt_tray verwenden
                tray_info = self._find_tray(
                    ams_data or [],
                    active_slot,
                    parsed_payload=parsed_payload,
                    printer=printer
                ) if active_slot is not None else None
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
                    "using_fallback": False,  # Flag fÃ¼r Fallback-Modus
                    "fallback_warned": False,  # Flag fÃ¼r einmalige Warnung
                    "spool_binding_attempted": False,  # Wird bei Update gesetzt
                    "no_spool_warned": False,  # Warnung erst nach Binding-Versuch
                    "job_name_updated": new_job.name != "Unnamed Job",
                    "no_name_warned": False,
                }

                # === SNAPSHOT SPEICHERN (fÃ¼r Server-Neustart-Recovery) ===
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
                    f"print_source={new_job.print_source} "
                    f"task_id={task_id or 'None'} "
                    f"(snapshot saved: layer={current_layer}, progress={current_percent}%)"
                )

                result = {"job_id": new_job.id, "status": "started"}
                
                # Trigger Bambu Cloud Sync bei Druckstart (wenn aktiviert)
                try:
                    from app.models.bambu_cloud_config import BambuCloudConfig
                    from app.services.bambu_cloud_scheduler import trigger_immediate_sync
                    from sqlmodel import select
                    import asyncio
                    
                    config = session.exec(select(BambuCloudConfig)).first()
                    if config and config.sync_enabled and config.sync_on_print_start:
                        # Async Trigger (non-blocking)
                        # Versuche Task zu erstellen, falls Loop lÃ¤uft
                        try:
                            loop = asyncio.get_running_loop()
                            # Loop lÃ¤uft bereits, erstelle Task
                            loop.create_task(trigger_immediate_sync())
                            self.logger.info(f"[JOB START] Bambu Cloud Sync Task erstellt fÃ¼r Job {new_job.id}")
                        except RuntimeError:
                            # Kein laufender Loop - starte in Background Thread
                            import threading
                            def run_sync():
                                try:
                                    asyncio.run(trigger_immediate_sync())
                                except Exception as e:
                                    self.logger.warning(f"[JOB START] Background Sync Fehler: {e}")
                            
                            thread = threading.Thread(target=run_sync, daemon=True)
                            thread.start()
                            self.logger.info(f"[JOB START] Bambu Cloud Sync Thread gestartet fÃ¼r Job {new_job.id}")
                except Exception as sync_error:
                    # Sync-Fehler soll Job-Start nicht blockieren
                    self.logger.warning(f"[JOB START] Bambu Cloud Sync konnte nicht getriggert werden: {sync_error}")
                
                return result

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
            from sqlmodel import select
            with Session(engine) as session:
                job = session.get(Job, job_info.get("job_id"))
                if not job:
                    # Job in DB nicht gefunden - cleanup
                    del self.active_jobs[cloud_serial]
                    return None

                # Initialize usage accumulators to avoid UnboundLocalError
                total_used_mm = 0.0
                total_used_g = 0.0

                # Aktuelle Layer-Nummer prÃ¼fen
                current_layer = parsed_payload.get("print", {}).get("layer_num") or 0

                # ============================================================
                # A-SERIES JOB PROGRESS / ETA UPDATE
                #
                # GILT NUR F?R: A1 / A1 mini
                #
                # Hintergrund:
                # Die A-Serie liefert ?ber MQTT keine zuverl?ssige globale ETA
                # oder Prozentwerte (mc_remaining_time ist ein phasenbezogener
                # Countdown und NICHT f?r Gesamtfortschritt geeignet).
                #
                # Deshalb werden Progress und ETA hier bewusst:
                # - aus Layer-Daten berechnet
                # - im Job persistiert
                # - vom Frontend direkt verwendet
                #
                # WICHTIG:
                # - Diese Logik darf f?r X1C / P-Serie NICHT verwendet werden.
                # - Anpassungen f?r X1C geh?ren in einen separaten Codepfad.
                # ============================================================
                print_block = parsed_payload.get("print", {})
                total_layer_num = None
                if isinstance(print_block, dict):
                    total_layer_num = (
                        print_block.get("total_layer_num")
                        or print_block.get("layer_total")
                        or print_block.get("total_layers")
                        or print_block.get("layer_count")
                    )
                try:
                    layer_num = int(current_layer) if current_layer is not None else None
                except (TypeError, ValueError):
                    layer_num = None
                try:
                    total_layer_num = int(total_layer_num) if total_layer_num is not None else None
                except (TypeError, ValueError):
                    total_layer_num = None

                printer = session.get(Printer, job.printer_id)
                series = str(getattr(printer, "series", "UNKNOWN") or "UNKNOWN").upper() if printer else "UNKNOWN"
                is_a_series = series == "A"

                if job_info.get("running_started_at") is None:
                    job_info["running_started_at"] = datetime.utcnow()

                started_at = job.started_at or job_info.get("running_started_at")

                if job.status == "running" and is_a_series and layer_num is not None and total_layer_num and total_layer_num > 0:
                    # ========================================================
                    # KRITISCH: Pre-Print-Phase (layer_num = 0)
                    #
                    # Bei A-Serie gilt: Solange layer_num == 0, ist der Druck
                    # noch in der Vorbereitungsphase (Aufheizen, Kalibrieren).
                    # In dieser Phase darf KEIN Fortschritt angezeigt werden!
                    # ========================================================
                    if layer_num == 0:
                        # Pre-Print-Phase: Kein Fortschritt, keine ETA
                        object.__setattr__(job, "progress", None)
                        job.eta_seconds = None
                    elif job.finished_at is not None:
                        # Job ist fertig
                        progress = 1.0
                        object.__setattr__(job, "progress", progress)
                        job.eta_seconds = 0
                    else:
                        # Normaler Druckfortschritt (layer_num > 0)
                        progress = layer_num / float(total_layer_num)
                        eta_seconds = None
                        if started_at:
                            eta_seconds = estimate_remaining_time_from_layers(
                                started_at=started_at,
                                layer_num=layer_num,
                                total_layer_num=total_layer_num
                            )
                        object.__setattr__(job, "progress", progress)
                        job.eta_seconds = eta_seconds

                    session.add(job)
                    session.commit()

                # === LAYER-BASIERTER FILAMENT-START ===
                # Filament-Tracking startet erst bei layer_num >= 1
                if current_layer >= 1 and not job_info.get("filament_started"):
                    # Guard-Flag setzen (einmalig)
                    job_info["filament_started"] = True

                    # Extrahiere PrimÃ¤rquelle
                    current_filament = self._extract_filament_used_mm(parsed_payload)

                    if current_filament is not None:
                        # PrimÃ¤rquelle verfÃ¼gbar
                        job_info["filament_start_mm"] = current_filament
                        job.filament_start_mm = current_filament
                        job_info["using_fallback"] = False

                        self.logger.info(
                            f"[FILAMENT START] Tracking started at layer={current_layer}, "
                            f"start_mm={current_filament:.1f} (primary source) for job={job.id}"
                        )
                    else:
                        # Fallback: Berechne aus remain und total_len
                        # NEU: Bei externen Spulen vt_tray verwenden
                        current_tray = self._find_tray(
                            ams_data or [],
                            job_info.get("slot"),
                            parsed_payload=parsed_payload,
                            printer=printer
                        )
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
                            # Externe Spule ohne total_len: Starte mit 0 und tracke Ã„nderungen
                            # WICHTIG: A1 Mini sendet keine filament_used_mm Daten Ã¼ber MQTT!
                            # Verbrauch wird erst am Job-Ende aus LÃ¤nge berechnet (weight-from-length)
                            if job.print_source == "external":
                                job_info["filament_start_mm"] = 0.0
                                job.filament_start_mm = 0.0
                                job_info["using_fallback"] = False
                                self.logger.info(
                                    f"[FILAMENT START] External spool tracking started at layer={current_layer}, "
                                    f"start_mm=0.0 (no total_len, tracking deltas only) for job={job.id}"
                                )
                            else:
                                # RegulÃ¤re Spule ohne Daten: Tracking nicht mÃ¶glich
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

                # === SLOT-WECHSEL-DETECTION (Multi-Color-Support) ===
                # Erkennt Slot-Wechsel wÃ¤hrend des Drucks und erstellt neue JobSpoolUsage-EintrÃ¤ge
                ams_block = parsed_payload.get("ams") or parsed_payload.get("print", {}).get("ams") or {}
                current_tray_now = ams_block.get("tray_now")
                current_tray_tar = ams_block.get("tray_tar")
                last_slot = job_info.get("slot")

                # Konvertiere zu Int fÃ¼r Vergleich
                if current_tray_now is not None:
                    try:
                        current_tray_now = int(current_tray_now)
                    except (ValueError, TypeError):
                        current_tray_now = None

                if current_tray_tar is not None:
                    try:
                        current_tray_tar = int(current_tray_tar)
                    except (ValueError, TypeError):
                        current_tray_tar = None

                # Nutze tray_now als primÃ¤re Quelle (aktuell aktiver Slot)
                current_slot = current_tray_now or current_tray_tar

                # Slot-Wechsel erkannt?
                # WICHTIG: Nur wenn sich der Slot WIRKLICH geÃ¤ndert hat UND nicht der gleiche wie vorher
                if current_slot is not None and last_slot is not None and current_slot != last_slot:
                    # GUARD: PrÃ¼fe ob fÃ¼r diesen Slot bereits ein Usage-Eintrag existiert
                    # (verhindert Duplikate bei schnellen MQTT-Payloads)
                    from app.models.job import JobSpoolUsage
                    existing_for_slot = session.exec(
                        select(JobSpoolUsage)
                        .where(JobSpoolUsage.job_id == job.id)
                        .where(JobSpoolUsage.slot == current_slot)
                    ).first()

                    if existing_for_slot:
                        # Bereits ein Eintrag fÃ¼r diesen Slot â†’ nur RAM-Tracking aktualisieren
                        job_info["slot"] = current_slot
                        self.logger.debug(
                            f"[SLOT CHANGE] Slot {current_slot} already has usage entry, skipping duplicate"
                        )
                    else:
                        # Neuer Slot-Wechsel - erstelle Usage-Eintrag
                        self.logger.info(
                            f"[SLOT CHANGE] Detected slot change: {last_slot} â†’ {current_slot} "
                            f"for job={job.id} (Multi-Color print)"
                        )

                        # Legacy-RAM-Fallback: finalisiere alten Slot auch in job_info["usages"].
                        # Wird von aelteren Fallback-Pfaden und Tests erwartet.
                        finalized_usage = self._finalize_current(session, job_info)
                        if finalized_usage:
                            job_info.setdefault("usages", []).append(finalized_usage)

                        # === BERECHNE VERBRAUCH DER VORHERIGEN SPULE ===
                        existing_usages = session.exec(
                            select(JobSpoolUsage)
                            .where(JobSpoolUsage.job_id == job.id)
                            .order_by(col(JobSpoolUsage.order_index))
                        ).all()

                        if existing_usages:
                            previous_usage = existing_usages[-1]  # Letzte Spule

                            # Extrahiere aktuellen Filament-Verbrauch
                            current_filament_mm = self._extract_filament_used_mm(parsed_payload)

                            if current_filament_mm is not None and job_info.get("filament_start_mm") is not None:
                                # Berechne Gesamtverbrauch bis jetzt
                                if job_info["filament_start_mm"] is not None:
                                    total_used_mm = current_filament_mm - job_info["filament_start_mm"]
                                else:
                                    total_used_mm = 0.0

                                # Berechne Verbrauch der vorherigen Spulen
                                previous_spools_total_mm = sum(u.used_mm for u in existing_usages[:-1])

                                # Verbrauch der aktuellen (vorherigen) Spule = Differenz
                                previous_spool_used_mm = total_used_mm - previous_spools_total_mm

                                if previous_spool_used_mm > 0:
                                    previous_usage.used_mm = previous_spool_used_mm

                                    # Gewicht berechnen aus Material-Datenbank
                                    if previous_usage.spool_id is not None:
                                        density_g_per_m = self._get_density_g_per_m(previous_usage.spool_id, session)
                                    else:
                                        density_g_per_m = 2.4
                                    previous_usage.used_g = previous_spool_used_mm / 1000.0 * density_g_per_m

                                    session.add(previous_usage)
                                    session.commit()

                                    self.logger.info(
                                        f"[SLOT CHANGE] Updated previous spool usage: "
                                        f"slot={last_slot} used_mm={previous_spool_used_mm:.1f} "
                                        f"used_g={previous_usage.used_g:.2f}"
                                    )
                                else:
                                    self.logger.warning(
                                        f"[SLOT CHANGE] Negative usage calculated for previous spool: "
                                        f"{previous_spool_used_mm:.1f}mm (skipped update)"
                                    )
                            else:
                                self.logger.warning(
                                    f"[SLOT CHANGE] Cannot calculate usage for previous spool: "
                                    f"filament_used_mm={current_filament_mm} "
                                    f"filament_start_mm={job_info.get('filament_start_mm')}"
                                )

                        # Finde neue Spule fÃ¼r aktuellen Slot
                        new_spool = session.exec(
                            select(Spool)
                            .where(Spool.printer_id == job_info.get("printer_id"))
                            .where(Spool.ams_slot == current_slot)
                        ).first()

                        if new_spool:
                            # Berechne nÃ¤chste order_index
                            next_order_index = len(existing_usages) if existing_usages else 0

                            # Erstelle DB-Usage erst wenn Filament-Tracking gestartet hat (layer >= 1).
                            # Vorherige Slotwechsel (Pre-Print/Prep) sollen keine persistente Usage erzeugen.
                            if job_info.get("filament_started"):
                                new_usage = JobSpoolUsage(
                                    job_id=job.id,
                                    spool_id=new_spool.id,
                                    slot=current_slot,
                                    used_mm=0.0,
                                    used_g=0.0,
                                    order_index=next_order_index
                                )
                                session.add(new_usage)
                                session.commit()
                                self.logger.info(
                                    f"[SLOT CHANGE] Created JobSpoolUsage entry: "
                                    f"job={job.id} spool={new_spool.id} slot={current_slot} order_index={next_order_index}"
                                )
                            else:
                                self.logger.debug(
                                    f"[SLOT CHANGE] Skipped JobSpoolUsage persist before filament start: "
                                    f"job={job.id} slot={current_slot}"
                                )

                            # Update RAM-Tracking
                            job_info["slot"] = current_slot
                            job_info["spool_id"] = new_spool.id

                            # Update Snapshot
                            self._save_snapshot(
                                cloud_serial=cloud_serial,
                                printer_id=job_info.get("printer_id"),
                                job_id=job.id,
                                job_name=job.name,
                                slot=current_slot,
                                layer_num=current_layer,
                                mc_percent=parsed_payload.get("print", {}).get("mc_percent") or 0,
                                started_at=job.started_at,
                                filament_start_mm=job_info.get("filament_start_mm"),
                                filament_started=job_info.get("filament_started", False),
                                using_fallback=job_info.get("using_fallback", False),
                                fallback_warned=job_info.get("fallback_warned", False),
                            )

                        else:
                            # Kein Spool gefunden, aber Slot trotzdem tracken
                            job_info["slot"] = current_slot
                            self.logger.warning(
                                f"[SLOT CHANGE] Slot changed to {current_slot}, but no spool found "
                                f"for job={job.id} printer={job_info.get('printer_id')}"
                            )

                # === RETROACTIVE EXTERNAL SPOOL BINDING ===
                # Wenn Job ohne Spule gestartet wurde (Race Condition: AMS-Daten kamen zu spÃ¤t),
                # aber jetzt AMS/vt_tray-Daten verfÃ¼gbar sind, binde externe Spule nachtrÃ¤glich
                if job.spool_id is None and not job_info.get("spool_binding_attempted"):
                    # Guard-Flag setzen (nur einmal versuchen)
                    job_info["spool_binding_attempted"] = True

                    # PrÃ¼fe beide AMS-Pfade
                    ams_block_check = parsed_payload.get("ams") or parsed_payload.get("print", {}).get("ams") or {}
                    tray_tar_check = ams_block_check.get("tray_tar")
                    tray_now_check = ams_block_check.get("tray_now")
                    vt_tray_check = parsed_payload.get("print", {}).get("vt_tray")
                    vt_tray_id_check = vt_tray_check.get("id") if isinstance(vt_tray_check, dict) else None

                    # String -> Int Konvertierung
                    if tray_tar_check is not None:
                        try:
                            tray_tar_check = int(tray_tar_check)
                        except (ValueError, TypeError):
                            tray_tar_check = None
                    if tray_now_check is not None:
                        try:
                            tray_now_check = int(tray_now_check)
                        except (ValueError, TypeError):
                            tray_now_check = None
                    if vt_tray_id_check is not None:
                        try:
                            vt_tray_id_check = int(vt_tray_id_check)
                        except (ValueError, TypeError):
                            vt_tray_id_check = None

                    # Externe Spule erkennen
                    detected_external_tray = None
                    if is_external_tray(printer, tray_tar_check):
                        detected_external_tray = tray_tar_check
                    elif is_external_tray(printer, tray_now_check):
                        detected_external_tray = tray_now_check
                    elif is_external_tray(printer, vt_tray_id_check):
                        detected_external_tray = vt_tray_id_check

                    # BerÃ¼cksichtige `is_ams_lite` (AMS angeschlossen vs. extern)
                    # Wenn ein echtes AMS angeschlossen ist, dann ist der
                    # virtuelle Externalâ€‘Slot (z.B. 254) nicht relevant fÃ¼r
                    # Retro-Bindung. PrÃ¼fe daher Payload/ams_data auf Flag.
                    ams_attached = False
                    try:
                        # PrÃ¼fe optional Ã¼bergegebenes ams_data (normalisiert)
                        # Sicherstellen, dass ams_data iterierbar ist, um Pylance-Fehler zu vermeiden
                        if isinstance(ams_data, (list, tuple)):
                            for unit in ams_data:
                                if unit.get("is_ams_lite"):
                                    ams_attached = True
                                    break

                        # PrÃ¼fe Rohâ€‘Payload-Pfade fallback
                        if not ams_attached:
                            ams_block_full = parsed_payload.get("ams") or parsed_payload.get("print", {}).get("ams") or {}
                            if isinstance(ams_block_full, dict) and ams_block_full.get("is_ams_lite"):
                                ams_attached = True

                            # PrÃ¼fe auf eingebettete ams_units
                            if not ams_attached:
                                ams_units = parsed_payload.get("ams_units")
                                if isinstance(ams_units, list):
                                    for u in ams_units:
                                        if u.get("is_ams_lite"):
                                            ams_attached = True
                                            break
                    except Exception:
                        # defensiv: falls Payload-Struktur unerwartet, ignoriere und fahre fort
                        ams_attached = False

                    # Wenn AMS angeschlossen ist, ignoriere Detektion von virtuellem
                    # external tray (z.B. 254) fÃ¼r Retro-Bindung â€” dieser Pfad ist
                    # nur relevant, wenn kein AMS physisch angebunden ist.
                    if ams_attached and detected_external_tray is not None:
                        external_tray_id_tmp = get_external_tray_id(printer)
                        if detected_external_tray == external_tray_id_tmp:
                            detected_external_tray = None

                    if detected_external_tray is not None:
                        # Externe Spule fÃ¼r diesen Drucker finden
                        external_tray_id = get_external_tray_id(printer)
                        job_printer_id = job_info.get("printer_id")
                        external_spool = session.exec(
                            select(Spool)
                            .where(Spool.printer_id == job_printer_id)
                            .where(Spool.ams_slot == external_tray_id)
                        ).first()

                        if external_spool:
                            # Retroaktiv binden!
                            job.spool_id = external_spool.id
                            job.print_source = "external"
                            job_info["spool_id"] = external_spool.id
                            session.add(job)
                            session.commit()

                            self.logger.info(
                                f"[SPOOL BINDING] Retroactively bound external spool={external_spool.id} "
                                f"(tray={external_tray_id}, detected={detected_external_tray}) to job={job.id} "
                                f"(race condition resolved)"
                            )
                        else:
                            self.logger.warning(
                                f"[SPOOL BINDING] Detected external print (tray={detected_external_tray}) "
                                f"but no external spool configured for printer={job_printer_id}"
                            )

                # Wenn nach Binding-Versuch noch immer keine Spule: warnen (einmalig)
                if (
                    current_layer >= self.binding_warning_layer_threshold
                    and job.spool_id is None
                    and job_info.get("spool_binding_attempted")
                    and not job_info.get("no_spool_warned")
                ):
                    printer_name = printer.name if printer else "Unbekannt"
                    self.logger.warning(
                        f"[JOB UPDATE] Still no spool bound for job={job.id}. "
                        f"printer={printer_name}, "
                        f"slot={job_info.get('slot')}"
                    )
                    trigger_notification_sync(
                        "job_no_spool",
                        job_name=self._extract_job_name(parsed_payload) or job.name,
                        printer_name=printer_name
                    )
                    job_info["no_spool_warned"] = True

                # === RETROACTIVE JOB NAME UPDATE ===
                # Wenn Job mit "Unnamed Job" gestartet wurde (Race Condition: Job-Name kam zu spÃ¤t),
                # aber jetzt subtask_name/gcode_file verfÃ¼gbar sind, aktualisiere nachtrÃ¤glich
                if job.name == "Unnamed Job" and not job_info.get("job_name_updated"):
                    # Job-Namen aus aktuellem MQTT-Payload extrahieren
                    new_job_name = self._extract_job_name(parsed_payload)

                    # Nur updaten wenn tatsÃ¤chlich ein Name gefunden wurde
                    if new_job_name:
                        job.name = new_job_name
                        job_info["job_name_updated"] = True
                        session.add(job)
                        session.commit()

                        self.logger.info(
                            f"[JOB NAME] Retroactively updated job name from 'Unnamed Job' to '{new_job_name}' "
                            f"for job={job.id} (race condition resolved)"
                        )

                if (
                    current_layer >= self.binding_warning_layer_threshold
                    and (not job.name or job.name == "Unnamed Job")
                    and not job_info.get("no_name_warned")
                ):
                    printer_name = printer.name if printer else "Unbekannt"
                    self.logger.warning(
                        f"[JOB UPDATE] No job name bound after layer={current_layer} for job={job.id}. "
                        f"printer={printer_name}"
                    )
                    trigger_notification_sync(
                        "job_no_name",
                        job_name=job.name,
                        printer_name=printer_name
                    )
                    job_info["no_name_warned"] = True

                # === RETROACTIVE PRINT_SOURCE UPDATE ===
                # Wenn Job mit "unknown" gestartet wurde (Race Condition: Spule kam zu spÃ¤t),
                # aber jetzt Spule gebunden ist, aktualisiere print_source nachtrÃ¤glich
                if job.print_source == "unknown" and not job_info.get("print_source_updated") and job.spool_id:
                    # Guard-Flag setzen (nur einmal versuchen)
                    job_info["print_source_updated"] = True

                    # PrÃ¼fe ob Spule external ist (ams_slot = 254 fÃ¼r A1 Mini, 255 fÃ¼r andere)
                    bound_spool = session.get(Spool, job.spool_id)
                    if bound_spool:
                        external_tray_id = get_external_tray_id(printer)
                        if bound_spool.ams_slot == external_tray_id:
                            # Externe Spule erkannt - aktualisiere print_source
                            job.print_source = "external"
                            session.add(job)
                            session.commit()

                            self.logger.info(
                                f"[PRINT SOURCE] Retroactively updated print_source from 'unknown' to 'external' "
                                f"for job={job.id} (spool_id={job.spool_id}, ams_slot={bound_spool.ams_slot}, "
                                f"race condition resolved)"
                            )
                        elif bound_spool.ams_slot is not None and 0 <= bound_spool.ams_slot <= 3:
                            # AMS-Spule erkannt
                            job.print_source = "ams"
                            session.add(job)
                            session.commit()

                            self.logger.info(
                                f"[PRINT SOURCE] Retroactively updated print_source from 'unknown' to 'ams' "
                                f"for job={job.id} (spool_id={job.spool_id}, ams_slot={bound_spool.ams_slot}, "
                                f"race condition resolved)"
                            )

                # === RETROACTIVE TASK_ID UPDATE ===
                # Wenn Job ohne task_id gestartet wurde (Race Condition: task_id kam zu spÃ¤t),
                # aber jetzt task_id im MQTT-Payload verfÃ¼gbar ist, aktualisiere nachtrÃ¤glich
                if not job.task_id and not job_info.get("task_id_updated"):
                    # Extrahiere task_id aus aktuellem Payload
                    task_id = parsed_payload.get("print", {}).get("task_id")
                    if task_id:
                        # Guard-Flag setzen (nur einmal versuchen)
                        job_info["task_id_updated"] = True

                        # Aktualisiere task_id in Datenbank
                        job.task_id = str(task_id)  # Konvertiere zu String falls int
                        session.add(job)
                        session.commit()

                        self.logger.info(
                            f"[TASK ID] Retroactively updated task_id to '{task_id}' "
                            f"for job={job.id} (race condition resolved, enables Cloud API integration)"
                        )

                # Aktuellen Slot prÃ¼fen (externe Spulen modellabhÃ¤ngig filtern)
                ams_block = parsed_payload.get("print", {}).get("ams") or {}
                current_slot = ams_block.get("tray_tar")

                # Verwende bereits geladenen printer (von Zeile 790)
                if is_external_tray(printer, current_slot):
                    current_slot = ams_block.get("tray_now")
                if is_external_tray(printer, current_slot):
                    current_slot = None

                # Slot-Wechsel erkennen
                if current_slot is not None and job_info.get("slot") != current_slot:
                    # Finalize old slot
                    usage = self._finalize_current(session, job_info)
                    if usage:
                        job_info.setdefault("usages", []).append(usage)

                    # Start new slot
                    # NEU: Bei externen Spulen vt_tray verwenden
                    tray_new = self._find_tray(
                        ams_data or [],
                        current_slot,
                        parsed_payload=parsed_payload,
                        printer=printer
                    )
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
                # NEU: Bei externen Spulen vt_tray verwenden
                current_tray = self._find_tray(
                    ams_data or [],
                    job_info.get("slot"),
                    parsed_payload=parsed_payload,
                    printer=printer
                )
                if current_tray:
                    current_remain = current_tray.get("remain")

                    # FIX: Bambu Lab's "remain" kann willkÃ¼rlich steigen/fallen
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

                    # === FIX Bug #2: Spulen-Gewicht aus remain berechnen ===
                    # Direkte Berechnung aus remain-Prozent statt fehlerhafter
                    # Subtraktion von weight_full (die vorherigen Verbrauch ignorierte)
                    current_remain_for_weight = job_info.get("last_remain")
                    spool_id = job_info.get("spool_id")

                    if current_remain_for_weight is not None and spool_id:
                        spool = session.get(Spool, spool_id)
                        if spool:
                            self._update_spool_weight_from_remain(spool, current_remain_for_weight)
                            session.add(spool)

                # === FILAMENT-BERECHNUNG (NEUE LOGIK) ===
                # Verwende Delta-Methode ab layer_num >= 1
                start_mm_raw = job_info.get("filament_start_mm")
                start_mm = None
                if start_mm_raw is not None:
                    try:
                        start_mm = float(start_mm_raw)
                    except (TypeError, ValueError):
                        self.logger.exception(
                            "[FILAMENT] Invalid filament_start_mm value=%s for job=%s",
                            start_mm_raw,
                            job_info.get("job_id"),
                        )
                        start_mm = None

                if start_mm is not None:
                    # Filament-Tracking ist aktiv (layer_num >= 1 erreicht)
                    current_filament = self._extract_filament_used_mm(parsed_payload)

                    if current_filament is not None:
                        # PrimÃ¤rquelle verfÃ¼gbar
                        if current_filament < start_mm:
                            self.logger.warning(
                                "[FILAMENT] Current filament_used_mm (%s) is less than start_mm (%s) for job=%s",
                                current_filament,
                                start_mm,
                                job.id,
                            )
                        else:
                            job_filament_used_mm = current_filament - start_mm

                            # Wechsel von Fallback zu PrimÃ¤rquelle?
                            if job_info.get("using_fallback"):
                                self.logger.info(
                                    f"[FILAMENT] Switched from fallback to primary source for job={job.id}"
                                )
                                job_info["using_fallback"] = False

                            # === GEWICHT BERECHNEN: filament_used_mm + Material-Density ===
                            # FÃ¼r Multi-Color: Nutze prÃ¤zise Density-Berechnung statt remain%
                            # Total = (Summe bereits finalisierter Spulen) + (aktuelle Spule)

                            from app.models.job import JobSpoolUsage

                            # Lade bereits finalisierte Spulen (aus Slot-Wechseln)
                            existing_usages = session.exec(
                                select(JobSpoolUsage)
                                .where(JobSpoolUsage.job_id == job.id)
                            ).all()

                            # Summiere Gewicht der finalisierten Spulen
                            finalized_g = sum(float(u.used_g) for u in existing_usages)

                            # Berechne Gewicht der aktuellen Spule (noch nicht finalisiert)
                            current_spool_g = 0.0
                            if job_info.get("spool_id") and job_info.get("filament_start_mm") is not None:
                                # Verbrauch der aktuellen Spule = total - (summe finalisierter Spulen in mm)
                                finalized_mm = sum(float(u.used_mm) for u in existing_usages)
                                current_spool_mm = max(0.0, job_filament_used_mm - finalized_mm)

                                # Gewicht aus LÃ¤nge + Density
                                spool_id_val = job_info.get("spool_id")
                                if isinstance(spool_id_val, str) and spool_id_val:
                                    density_g_per_m = self._get_density_g_per_m(spool_id_val, session)
                                else:
                                    density_g_per_m = 2.4
                                current_spool_g = current_spool_mm / 1000.0 * density_g_per_m

                                self.logger.debug(
                                    f"[JOB UPDATE] Weight: finalized={finalized_g:.2f}g + "
                                    f"current={current_spool_g:.2f}g ({current_spool_mm:.1f}mm * {density_g_per_m:.2f}g/m)"
                                )

                            total_used_g = finalized_g + current_spool_g

                            job.filament_used_mm = max(0.0, job_filament_used_mm)
                            job.filament_used_g = total_used_g
                    else:
                        # PrimÃ¤rquelle nicht verfÃ¼gbar, aber Fallback aktiv?
                        if job_info.get("using_fallback"):
                            # Fallback: Berechne weiterhin aus remain-Delta
                            if job_info.get("start_total_len") is None:
                                self.logger.error(
                                    "[FILAMENT] Fallback delta unavailable: missing total_len for job=%s",
                                    job.id,
                                )
                                # Keine Quelle verfÃœgbar, behalte letzten Wert
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
                                        if current_mm > 0 and current_g <= 0:
                                            density_g_per_m = self._get_density_g_per_m(sp.id, session)
                                            current_g = (current_mm / 1000.0) * density_g_per_m
                                        total_used_mm += current_mm
                                        total_used_g += current_g

                                if total_used_mm > 0 and total_used_g <= 0:
                                    spool_id_val = job_info.get("spool_id")
                                    if isinstance(spool_id_val, str) and spool_id_val:
                                        density_g_per_m = self._get_density_g_per_m(spool_id_val, session)
                                    else:
                                        density_g_per_m = 2.4
                                    total_used_g = (total_used_mm / 1000.0) * density_g_per_m

                                job.filament_used_mm = max(0.0, total_used_mm)
                                job.filament_used_g = total_used_g
                        else:
                            # Keine Quelle verfÃ¼gbar, behalte letzten Wert
                            pass
                else:
                    # Filament-Tracking noch nicht gestartet (layer_num < 1)
                    # Setze Verbrauch auf 0
                    job.filament_used_mm = 0.0
                    job.filament_used_g = 0.0

                # Live-Fallback: Wenn MQTT keine brauchbaren Verbrauchsdaten liefert
                # (z.B. remain=0 bei A1), schaetze g ueber Fortschritt * erwartetes G-Code-Gewicht.
                current_used_g = float(job.filament_used_g or 0.0)
                if job.status == "running" and current_used_g <= 0.0:
                    prefetched_weight_g = self._get_or_prefetch_gcode_weight(
                        session=session,
                        job=job,
                        job_info=job_info,
                        parsed_payload=parsed_payload,
                        printer=printer,
                    )
                    if prefetched_weight_g and prefetched_weight_g > 0:
                        progress_fraction = 0.0
                        if total_layer_num and total_layer_num > 0 and current_layer is not None:
                            try:
                                progress_fraction = float(current_layer) / float(total_layer_num)
                            except (TypeError, ValueError, ZeroDivisionError):
                                progress_fraction = 0.0
                        if progress_fraction <= 0:
                            try:
                                mc_percent_val = parsed_payload.get("print", {}).get("mc_percent")
                                if mc_percent_val is not None:
                                    progress_fraction = float(mc_percent_val) / 100.0
                            except (TypeError, ValueError):
                                progress_fraction = 0.0

                        progress_fraction = max(0.0, min(1.0, progress_fraction))
                        if progress_fraction > 0:
                            estimated_used_g = prefetched_weight_g * progress_fraction
                            if estimated_used_g > 0:
                                job.filament_used_g = estimated_used_g
                                total_used_g = estimated_used_g

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
            from sqlmodel import select
            with Session(engine) as session:
                job = session.get(Job, job_info.get("job_id"))
                if not job:
                    del self.active_jobs[cloud_serial]
                    return None

                # Extrahiere current_layer fÃ¼r weight-from-length Berechnung
                current_layer = parsed_payload.get("print", {}).get("layer_num") or 0

                # Letzter Versuch: Jobname beim Finish aus MQTT nachziehen
                if job.name == "Unnamed Job":
                    final_job_name = self._extract_job_name(parsed_payload)
                    if final_job_name:
                        job.name = final_job_name
                        job_info["job_name_updated"] = True
                        session.add(job)
                        session.commit()
                        self.logger.info(
                            f"[JOB FINISH] Updated job name from 'Unnamed Job' to '{final_job_name}' for job={job.id}"
                        )

                # === FINALISIERE LETZTE SPULE (Multi-Color-Support) ===
                # Wenn Multi-Color-Job mit JobSpoolUsage-EintrÃ¤gen:
                # Update die letzte Spule mit finalem Verbrauch
                from app.models.job import JobSpoolUsage

                existing_usages = session.exec(
                    select(JobSpoolUsage)
                    .where(JobSpoolUsage.job_id == job.id)
                    .order_by(col(JobSpoolUsage.order_index))
                ).all()

                if existing_usages:
                    last_usage = existing_usages[-1]

                    # Nur updaten wenn noch nicht berechnet (used_mm == 0)
                    if last_usage.used_mm == 0.0:
                        current_filament_mm = self._extract_filament_used_mm(parsed_payload)

                        if current_filament_mm is not None and job_info.get("filament_start_mm") is not None:
                            # Berechne Gesamtverbrauch
                            total_used_mm = current_filament_mm - job_info["filament_start_mm"]

                            # Berechne Verbrauch der vorherigen Spulen
                            previous_spools_total_mm = sum(u.used_mm for u in existing_usages[:-1])

                            # Verbrauch der letzten Spule = Differenz
                            last_spool_used_mm = total_used_mm - previous_spools_total_mm

                            if last_spool_used_mm > 0:
                                last_usage.used_mm = last_spool_used_mm

                                # Gewicht berechnen aus Material-Datenbank
                                if last_usage.spool_id is not None:
                                    density_g_per_m = self._get_density_g_per_m(last_usage.spool_id, session)
                                else:
                                    density_g_per_m = 2.4
                                last_usage.used_g = last_spool_used_mm / 1000.0 * density_g_per_m

                                session.add(last_usage)
                                session.commit()

                                self.logger.info(
                                    f"[JOB FINISH] Updated last spool usage: "
                                    f"slot={job_info.get('slot')} used_mm={last_spool_used_mm:.1f} "
                                    f"used_g={last_usage.used_g:.2f}"
                                )
                            else:
                                self.logger.warning(
                                    f"[JOB FINISH] Negative usage for last spool: "
                                    f"{last_spool_used_mm:.1f}mm (skipped update)"
                                )

                # Initialize accumulators to ensure defined values in all code paths
                total_used_mm = 0.0
                total_used_g = 0.0
                final_used_mm = 0.0

                # Finalize letzten Slot
                # NEU: Bei externen Spulen vt_tray verwenden
                printer = session.get(Printer, job.printer_id)
                final_tray = self._find_tray(
                    ams_data or [],
                    job_info.get("slot"),
                    parsed_payload=parsed_payload,
                    printer=printer
                )
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
                        # PrimÃ¤rquelle verfÃ¼gbar
                        try:
                            start_mm = float(job_info["filament_start_mm"])
                        except (TypeError, ValueError):
                            self.logger.exception(
                                "[FILAMENT] Invalid filament_start_mm value=%s for job=%s",
                                job_info.get("filament_start_mm"),
                                job.id,
                            )
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
                    # Filament-Tracking nie gestartet (layer_num < 1 wÃ¤hrend gesamten Jobs)
                    # Berechne Verbrauch aus finalisierten Usages (remain-delta)
                    total_used_mm = sum(u.get("used_mm", 0) for u in job_info.get("usages", []))
                    if job_info.get("spool_id"):
                        sp = session.get(Spool, job_info.get("spool_id"))
                        if sp:
                            # Wenn _finalize_current bereits ein Usage-Entry fÃ¼r den aktuellen
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

                # === GEWICHT BERECHNEN: PrioritÃ¤t auf JobSpoolUsage ===
                # Bei Multi-Color-Drucken haben wir mehrere JobSpoolUsage-EintrÃ¤ge mit
                # korrektem used_g (berechnet aus filament_used_mm + Material-Density).
                # Diese Werte sind prÃ¤ziser als remain%-basierte Berechnung!

                from app.models.job import JobSpoolUsage
                existing_usages = session.exec(
                    select(JobSpoolUsage)
                    .where(JobSpoolUsage.job_id == job.id)
                    .order_by(col(JobSpoolUsage.order_index))
                ).all()

                if existing_usages:
                    # Summiere used_g aus JobSpoolUsage (prÃ¤zise Material-Density-Berechnung)
                    total_used_g = sum(float(u.used_g) for u in existing_usages)

                    self.logger.info(
                        f"[JOB FINISH] Using JobSpoolUsage for weight: "
                        f"{len(existing_usages)} spool(s), total={total_used_g:.2f}g"
                    )
                else:
                    # Fallback: Alte remain%-basierte Berechnung (fÃ¼r alte Jobs ohne JobSpoolUsage)
                    total_used_g = sum(u.get("used_g", 0) for u in job_info.get("usages", []))
                    if job_info.get("spool_id"):
                        sp = session.get(Spool, job_info.get("spool_id"))
                        if sp:
                            if not usage:
                                _, current_g = self._calc_usage(
                                    sp,
                                    job_info.get("start_remain"),
                                    job_info.get("last_remain"),
                                    job_info.get("start_total_len")
                                )
                                total_used_g += current_g

                    self.logger.debug(
                        f"[JOB FINISH] Using legacy remain% calculation: {total_used_g:.2f}g"
                    )

                job.filament_used_mm = max(0.0, final_used_mm)
                job.filament_used_g = total_used_g
                # Ensure variables used in logging are set
                total_used_mm = final_used_mm

                # === GEWICHT AUS LÃ„NGE BERECHNEN (fÃ¼r externe Spulen ohne RFID) ===
                # WICHTIG: A1 Mini sendet KEINE filament_used_mm fÃ¼r externe Spulen!
                # Problem: Bei gcode_state=FINISH ist layer_num=0 (trotz gedruckter Layers)
                # LÃ¶sung: PrÃ¼fe nur print_source="external" - wenn externe Spule, versuche Weight-Calculation
                #
                # Bedingungen:
                # 1. Externe Spule (print_source="external")
                # 2. Kein Gewicht aus remain ermittelt (total_used_g == 0)
                #
                # Bei A1 Mini (final_used_mm=0): Loggt Warnung mit task_id fÃ¼r Cloud API
                # Bei anderen Druckern (final_used_mm>0): Berechnet Gewicht aus LÃ¤nge

                # DEBUG: Log Bedingungen fÃ¼r Weight-Calculation
                self.logger.info(
                    f"[WEIGHT-CHECK] job={job.id} print_source={job.print_source} "
                    f"total_used_g={total_used_g} final_used_mm={final_used_mm}"
                )

                if total_used_g == 0:
                    # Kein Gewicht aus remain%-Tracking oder filament_used_mm verfügbar.
                    # Gilt für:
                    # - Externe Spulen (print_source="external")
                    # - A1 Mini AMS Lite (print_source="ams"): remain ist immer 0 (keine Waage)
                    # - Nachstart-Fix: Tracking-Daten verloren, prefetched_weight nicht vorhanden
                    # Fallback: G-Code Gewicht (prefetched oder FTP-Download)

                    # Material-Typ aus AMS-Tray oder vt_tray extrahieren
                    material_type = None
                    # Zuerst aus dem aktiven AMS-Slot (falls vorhanden)
                    ams_block = parsed_payload.get("print", {}).get("ams") or parsed_payload.get("ams") or {}
                    ams_list = ams_block.get("ams") if isinstance(ams_block, dict) else None
                    if ams_list and isinstance(ams_list, list):
                        active_slot = job_info.get("slot")
                        if active_slot is not None:
                            for unit in ams_list:
                                trays = unit.get("tray") or []
                                for tray in trays:
                                    if str(tray.get("id")) == str(active_slot):
                                        material_type = tray.get("tray_type")
                                        break
                    # Fallback: aus vt_tray
                    if not material_type:
                        vt_tray = parsed_payload.get("print", {}).get("vt_tray")
                        if vt_tray and isinstance(vt_tray, dict):
                            material_type = vt_tray.get("tray_type")

                    # Versuche Gewicht direkt aus print.weight_used zu bekommen (A1 Mini Fallback)
                    calculated_weight = 0.0
                    print_block = parsed_payload.get("print", {})
                    
                    # Zuerst: Versuche LÃ¤nge-basierte Berechnung
                    if final_used_mm > 0:
                        # Gewicht aus LÃ¤nge berechnen (normale Drucker mit LÃ¤ngen-Daten)
                        calculated_weight = self._calculate_weight_from_length(
                            length_mm=final_used_mm,
                            material_type=material_type,
                            diameter_mm=1.75
                        )
                    # Zweiter Versuch: print.weight_used direkt verwenden (wenn vorhanden)
                    elif isinstance(print_block, dict):
                        weight_used = print_block.get("weight_used")
                        if weight_used is not None:
                            try:
                                calculated_weight = float(weight_used)
                                self.logger.info(
                                    f"[JOB FINISH] Using print.weight_used={calculated_weight:.2f}g "
                                    f"for external spool job={job.id}"
                                )
                            except (ValueError, TypeError):
                                pass

                    # Zweieinhalbter Versuch: Bereits prefetchedes G-Code-Gewicht nutzen
                    if calculated_weight == 0:
                        prefetched_weight = job_info.get("prefetched_gcode_weight")
                        if prefetched_weight and prefetched_weight > 0:
                            calculated_weight = prefetched_weight
                            self.logger.info(
                                f"[JOB FINISH] Using prefetched G-Code weight={prefetched_weight:.2f}g for job={job.id}"
                            )
                    
                    # Dritter Versuch: FTP G-Code Download (A1 Mini mit Bambu Studio)
                    if calculated_weight == 0 and job.task_id and printer:
                        try:
                            from app.services.gcode_ftp_service import get_gcode_ftp_service
                            
                            ftp_service = get_gcode_ftp_service()
                            
                            # PrÃ¼fe, ob Drucker IP und API Key vorhanden sind
                            if printer.ip_address and printer.api_key:
                                # Dateiname vom Job oder MQTT extrahieren
                                gcode_filename = job.name or "unknown"
                                
                                # Versuche auch vom payload zu nehmen (falls noch vorhanden)
                                gcode_from_payload = (
                                    parsed_payload.get("print", {}).get("gcode_file") or
                                    parsed_payload.get("print", {}).get("subtask_name") or
                                    parsed_payload.get("gcode_file") or
                                    parsed_payload.get("subtask_name")
                                )
                                if gcode_from_payload:
                                    gcode_filename = gcode_from_payload
                                
                                self.logger.info(
                                    f"[JOB FINISH] Attempting FTP G-Code download for task_id={job.task_id}, "
                                    f"filename={gcode_filename}"
                                )
                                
                                ftp_weight = ftp_service.download_gcode_weight(
                                    printer_ip=printer.ip_address,
                                    api_key=printer.api_key,
                                    task_id=str(job.task_id),
                                    gcode_filename=gcode_filename
                                )
                                
                                if ftp_weight is not None and ftp_weight > 0:
                                    calculated_weight = ftp_weight
                                    self.logger.info(
                                        f"[JOB FINISH] âœ… Downloaded weight from G-Code: {calculated_weight:.2f}g "
                                        f"for external spool job={job.id} (task_id={job.task_id}, file={gcode_filename})"
                                    )
                            else:
                                self.logger.debug(
                                    f"[JOB FINISH] FTP download skipped: "
                                    f"ip_address={bool(printer.ip_address)}, "
                                    f"api_key={bool(printer.api_key)}"
                                )
                        except Exception as e:
                            self.logger.warning(
                                f"[JOB FINISH] FTP G-Code download failed for task_id={job.task_id}: {e}"
                            )
                    
                    # Fallback: A1 Mini ohne alle anderen Quellen
                    if calculated_weight == 0:
                        self.logger.warning(
                            f"[JOB FINISH] External spool without length data for job={job.id} "
                            f"(task_id={job.task_id}). Weight calculation requires Cloud API integration or manual input."
                        )

                    # PARTIAL-CANCEL-WEIGHT:
                    # Bei ABORT/FAILED nur den Fortschrittsanteil vom Gesamtgewicht buchen.
                    if calculated_weight > 0:
                        gstate_norm = (current_gstate or "").upper()
                        is_completed_state = gstate_norm in completed_states

                        if not is_completed_state:
                            progress_fraction = 0.0
                            try:
                                mc_percent_val = parsed_payload.get("print", {}).get("mc_percent")
                                if mc_percent_val is not None:
                                    progress_fraction = float(mc_percent_val) / 100.0
                            except (TypeError, ValueError):
                                progress_fraction = 0.0

                            if progress_fraction <= 0:
                                try:
                                    layer_val = parsed_payload.get("print", {}).get("layer_num")
                                    total_layer_val = parsed_payload.get("print", {}).get("total_layer_num")
                                    if layer_val is not None and total_layer_val is not None and float(total_layer_val) > 0:
                                        progress_fraction = float(layer_val) / float(total_layer_val)
                                except (TypeError, ValueError, ZeroDivisionError):
                                    progress_fraction = 0.0

                            progress_fraction = max(0.0, min(1.0, progress_fraction))
                            calculated_weight = calculated_weight * progress_fraction
                            self.logger.info(
                                f"[JOB FINISH] PARTIAL-CANCEL-WEIGHT: "
                                f"progress={progress_fraction * 100:.1f}% -> used_g={calculated_weight:.2f}g"
                            )

                        job.filament_used_g = calculated_weight
                        total_used_g = calculated_weight

                        self.logger.info(
                            f"[JOB FINISH] Calculated weight for external spool: "
                            f"{final_used_mm:.1f}mm -> {calculated_weight:.2f}g "
                            f"(material={material_type or 'PLA'})"
                        )

                job.finished_at = datetime.utcnow()

                # Status-Mapping: Bambu gcode_state â†’ Job Status
                # Normalisiere gcode_state zu Uppercase fÃ¼r Vergleich
                gstate_normalized = (current_gstate or "").upper()
                is_klipper = bool(printer and (printer.printer_type or "").lower() == "klipper")

                # Kein Gewicht UND keine Spule -> pending_weight (gilt fuer alle Drucker)
                _no_data = float(total_used_g or 0.0) <= 0 and not job.spool_id

                if gstate_normalized in completed_states:
                    if _no_data:
                        job.status = "pending_weight"
                    else:
                        job.status = "completed"
                elif gstate_normalized in aborted_states:
                    # ABORT, ABORTED, STOPPED, CANCELLED, CANCELED â†’ aborted
                    if gstate_normalized in {"CANCELLED", "CANCELED"}:
                        job.status = "cancelled"
                    elif gstate_normalized in {"ABORT", "ABORTED"}:
                        job.status = "aborted"
                    else:  # STOPPED
                        job.status = "stopped"
                elif gstate_normalized in failed_states:
                    # FAILED, ERROR, EXCEPTION â†’ failed/error/exception
                    if gstate_normalized == "EXCEPTION":
                        job.status = "exception"
                    elif gstate_normalized == "ERROR":
                        job.status = "error"
                    else:
                        job.status = "failed"
                else:
                    # Fallback: Wenn mc_percent==100 aber kein gcode_state â†’ "completed"
                    if parsed_payload.get("print", {}).get("mc_percent") == 100:
                        if _no_data:
                            job.status = "pending_weight"
                        else:
                            job.status = "completed"
                    else:
                        job.status = "failed"

                # Spool ID setzen (falls noch nicht gesetzt)
                if not job.spool_id and job_info.get("usages"):
                    first_spool = next((u.get("spool_id") for u in job_info["usages"] if u.get("spool_id")), None)
                    if first_spool:
                        job.spool_id = first_spool

                # === KRITISCH: Job-Status SOFORT committen ===
                # Spool-Weight-Updates und WeightHistory-Erstellung können scheitern
                # (z.B. FK-Fehler, DB-Fehler). Der Job muss IMMER als abgeschlossen
                # gespeichert werden, unabhängig davon ob Gewichts-Updates klappen.
                session.add(job)
                session.commit()
                self.logger.info(
                    f"[JOB FINISH] Job {job.id} status={job.status!r} committed "
                    f"(used_g={total_used_g:.2f}g, used_mm={total_used_mm:.1f}mm)"
                )

                # WICHTIG: Finales Spulen-Gewicht aktualisieren!
                # Bei abgebrochenen/fehlgeschlagenen Jobs wird das Gewicht sonst nicht gesetzt

                # Alle verwendeten Spulen aktualisieren
                updated_spools = set()

                # 1. Hole JobSpoolUsage-EintrÃ¤ge aus der Datenbank (haben korrekten Verbrauch)
                from app.models.job import JobSpoolUsage
                db_usages = session.exec(
                    select(JobSpoolUsage)
                    .where(JobSpoolUsage.job_id == job.id)
                ).all()

                # 2. Verarbeite alle JobSpoolUsage-EintrÃ¤ge
                for db_usage in db_usages:
                    spool_id = db_usage.spool_id
                    if spool_id and spool_id not in updated_spools:
                        spool = session.get(Spool, spool_id)
                        if spool and spool.weight_current is not None:
                            # Verbrauch aus DB-Eintrag oder aus job_info berechnen
                            used_g = float(db_usage.used_g or 0)

                            # Wenn DB-Eintrag 0 hat, versuche aus job_info zu holen
                            if used_g == 0:
                                for usage in job_info.get("usages", []):
                                    if usage.get("spool_id") == spool_id:
                                        used_g = float(usage.get("used_g", 0))
                                        break

                            # Wenn immer noch 0, berechne aus total_used_g (Single-Spool)
                            if used_g == 0 and len(db_usages) == 1:
                                used_g = total_used_g
                                # Update auch den DB-Eintrag
                                db_usage.used_g = used_g
                                db_usage.used_mm = total_used_mm
                                session.add(db_usage)

                            if used_g > 0:
                                old_weight = float(spool.weight_current)
                                # Vom aktuellen Gewicht abziehen
                                new_weight = max(0, old_weight - used_g)
                                spool.weight_current = new_weight
                                session.add(spool)
                                updated_spools.add(spool_id)

                                # WeightHistory erstellen
                                from app.models.weight_history import WeightHistory
                                weight_history = WeightHistory(
                                    spool_uuid=(spool.tray_uuid or spool.id),
                                    spool_number=spool.spool_number,
                                    old_weight=old_weight,
                                    new_weight=new_weight,
                                    source="mqtt_tracking",
                                    change_reason=f"Job abgeschlossen: {job.name}",
                                    user="System",
                                    details=f"Job-ID: {job.id}, Slot: {db_usage.slot}"
                                )
                                session.add(weight_history)
                                self.logger.info(
                                    f"[JOB FINISH] WeightHistory created for spool #{spool.spool_number}: "
                                    f"{old_weight:.1f}g -> {new_weight:.1f}g (-{used_g:.1f}g)"
                                )

                # 2. Aktueller Slot (falls nicht bereits in usages)
                current_spool_id = job_info.get("spool_id")
                if current_spool_id and current_spool_id not in updated_spools:
                    spool = session.get(Spool, current_spool_id)
                    if spool and spool.weight_current is not None:
                        # Berechne Verbrauch fÃ¼r aktuellen Slot
                        used_mm, used_g = self._calc_usage(
                            spool,
                            job_info.get("start_remain"),
                            job_info.get("last_remain"),
                            job_info.get("start_total_len")
                        )
                        if used_g > 0:
                            old_weight = float(spool.weight_current)
                            new_weight = max(0, old_weight - used_g)
                            spool.weight_current = new_weight
                            session.add(spool)

                            # WeightHistory erstellen
                            from app.models.weight_history import WeightHistory
                            weight_history = WeightHistory(
                                spool_uuid=(spool.tray_uuid or spool.id),
                                spool_number=spool.spool_number,
                                old_weight=old_weight,
                                new_weight=new_weight,
                                source="mqtt_tracking",
                                change_reason=f"Job abgeschlossen: {job.name}",
                                user="System",
                                details=f"Job-ID: {job.id}, Aktueller Slot"
                            )
                            session.add(weight_history)
                            self.logger.debug(
                                f"[JOB FINISH] WeightHistory created for current spool #{spool.spool_number}: "
                                f"{old_weight:.1f}g -> {new_weight:.1f}g (-{used_g:.1f}g)"
                            )

                # === FIX Bug #1: END-GEWICHT SETZEN + VALIDIERUNG ===
                final_spool_id = job.spool_id
                if not final_spool_id and job_info.get("usages"):
                    final_spool_id = next(
                        (u.get("spool_id") for u in reversed(job_info["usages"]) if u.get("spool_id")),
                        None
                    )

                # [BETA] Single-Spool-Fallback:
                # Wenn Gewicht bekannt ist, aber keine Usage gebucht wurde, trotzdem abbuchen + History.
                if total_used_g > 0 and final_spool_id and not updated_spools:
                    fallback_spool = session.get(Spool, final_spool_id)
                    if fallback_spool and fallback_spool.weight_current is not None:
                        old_weight = float(fallback_spool.weight_current)
                        new_weight = max(0.0, old_weight - float(total_used_g))
                        fallback_spool.weight_current = new_weight
                        session.add(fallback_spool)
                        updated_spools.add(final_spool_id)

                        from app.models.weight_history import WeightHistory
                        session.add(
                            WeightHistory(
                                spool_uuid=(fallback_spool.tray_uuid or fallback_spool.id),
                                spool_number=fallback_spool.spool_number,
                                old_weight=old_weight,
                                new_weight=new_weight,
                                source="mqtt_tracking",
                                change_reason="job_completed_fallback_no_usages",
                                user="System",
                                details=f"Job-ID: {job.id}, fallback without usages",
                            )
                        )

                if final_spool_id:
                    final_spool = session.get(Spool, final_spool_id)
                    if final_spool and final_spool.weight_current is not None:
                        job.end_weight = final_spool.weight_current

                        if job.start_weight is not None:
                            weight_consumption = job.start_weight - job.end_weight

                            if weight_consumption < 0:
                                self.logger.warning(
                                    f"[WEIGHT] Job {job.id}: Negativer Verbrauch "
                                    f"({weight_consumption:.1f}g) - Spule aufgefuellt?"
                                )
                            elif total_used_g > 0 and abs(weight_consumption - total_used_g) > 10.0:
                                deviation = abs(weight_consumption - total_used_g) / total_used_g * 100
                                self.logger.warning(
                                    f"[WEIGHT] Job {job.id}: Gewichtsdelta "
                                    f"({weight_consumption:.1f}g) weicht von berechnetem Wert "
                                    f"({total_used_g:.1f}g) um {deviation:.1f}% ab"
                                )
                            else:
                                self.logger.info(
                                    f"[WEIGHT] Job {job.id}: Verbrauch {weight_consumption:.1f}g "
                                    f"({job.start_weight:.1f}g -> {job.end_weight:.1f}g)"
                                )
                        else:
                            self.logger.warning(
                                f"[WEIGHT] Job {job.id}: end_weight gesetzt, "
                                f"aber start_weight fehlt"
                            )
                    else:
                        self.logger.warning(
                            f"[WEIGHT] Job {job.id}: Finale Spule hat keine Gewichtsdaten"
                        )
                else:
                    self.logger.warning(
                        f"[WEIGHT] Job {job.id}: Keine Spule zugeordnet"
                    )

                session.add(job)
                session.commit()
                session.refresh(job)

                self.logger.info(
                    f"[JOB FINISH] job={job.id} status={job.status} "
                    f"used_mm={total_used_mm:.1f} used_g={total_used_g:.1f}"
                )

                # === CLOUD-FALLBACK fÃ¼r unvollstÃ¤ndige Daten ===
                # Wenn MQTT-Tracking unvollstÃ¤ndig (kein Gewicht oder keine Multi-Spool-Daten),
                # versuche Cloud-API als Fallback
                existing_usages_count = len(existing_usages) if existing_usages else 0
                needs_cloud_fallback = (
                    job.status in {"completed", "pending_weight"} and
                    (total_used_g == 0 or existing_usages_count == 0) and
                    job.task_id  # Nur wenn Cloud task_id vorhanden
                )

                if needs_cloud_fallback:
                    self.logger.info(
                        f"[CLOUD FALLBACK] Attempting cloud data fetch for job={job.id} "
                        f"(used_g={total_used_g}, usages={existing_usages_count})"
                    )
                    try:
                        cloud_result = self._fetch_cloud_fallback_data(job, printer, session)
                        if cloud_result:
                            total_used_g = cloud_result.get("total_used_g", total_used_g)
                            if job.status == "pending_weight" and float(total_used_g or 0.0) > 0:
                                job.status = "completed"
                                # filament_used_g muss ebenfalls gesetzt werden, sonst zeigt UI "Warnung 0g"
                                if job.filament_used_g == 0:
                                    job.filament_used_g = float(total_used_g)
                                session.add(job)
                                session.commit()
                                session.refresh(job)
                            self.logger.info(
                                f"[CLOUD FALLBACK] Success! Updated job={job.id} with cloud data: "
                                f"{cloud_result.get('usages_created', 0)} spools, {total_used_g:.2f}g total"
                            )
                    except Exception as cloud_err:
                        self.logger.warning(
                            f"[CLOUD FALLBACK] Failed for job={job.id}: {cloud_err}"
                        )

                # Lade Printer fÃ¼r Notification-Kontext
                printer = session.get(Printer, job.printer_id)
                printer_name = printer.name if printer else "Unbekannt"

                # Finale Binding-Pruefung: Wenn bis Job-Ende kein Name/keine Spule gebunden wurde,
                # Warnung auch ohne Layer-Threshold triggern.
                if job.spool_id is None and not job_info.get("no_spool_warned"):
                    trigger_notification_sync(
                        "job_no_spool",
                        job_name=job.name,
                        printer_name=printer_name
                    )
                    job_info["no_spool_warned"] = True

                if (not job.name or job.name == "Unnamed Job") and not job_info.get("no_name_warned"):
                    trigger_notification_sync(
                        "job_no_name",
                        job_name=job.name,
                        printer_name=printer_name
                    )
                    job_info["no_name_warned"] = True

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

                # 3. Job completed successfully (COMPLETED)
                if job.status == "completed":
                    trigger_notification_sync(
                        "print_done",
                        job_name=job.name,
                        printer_name=printer_name
                    )

                # 4. Job ohne Tracking (kein Verbrauch oder keine Spule)
                if not job.spool_id or total_used_g == 0:
                    trigger_notification_sync(
                        "job_no_tracking",
                        job_name=job.name,
                        printer_name=printer_name
                    )

                # Cleanup RAM
                del self.active_jobs[cloud_serial]

                # Cooldown setzen – verhindert Phantomjobs durch Post-Print-Signale (PURGING etc.)
                import time as _t
                self._job_finish_cooldown[cloud_serial] = _t.monotonic()
                self.logger.info(f"[JOB FINISH] Cooldown gesetzt für {cloud_serial} ({self._JOB_FINISH_COOLDOWN_SECS}s)")

                # === SNAPSHOT LÃ–SCHEN (Job ist fertig) ===
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


def get_active_job_for_printer(printer_id: str) -> Optional[Dict[str, Any]]:
    """
    PrÃ¼fe ob ein Job aktiv fÃ¼r einen Drucker lÃ¤uft.
    Wird genutzt von mqtt_runtime um zu prÃ¼fen ob eine Notification gesendet werden soll.
    
    Args:
        printer_id: Die UUID des Druckers
        
    Returns:
        Dict mit Job-Info (name, status, started_at, etc.) oder None wenn kein Job aktiv
    """
    try:
        with Session(engine) as session:
            job = session.exec(
                select(Job)
                .where(Job.printer_id == printer_id)
                .where(Job.finished_at == None)  # Noch nicht beendet
            ).first()
            
            if job:
                # Berechne verstrichene Zeit
                elapsed_min = 0
                if job.started_at:
                    from datetime import datetime, timezone
                    elapsed_sec = (datetime.now(timezone.utc) - job.started_at).total_seconds()
                    elapsed_min = int(elapsed_sec // 60)
                
                # Format Start-Zeit
                start_time_str = ""
                if job.started_at:
                    start_time_str = job.started_at.strftime("%H:%M")
                
                return {
                    "id": str(job.id),
                    "name": job.name or "Unnamed Job",
                    "status": job.status,
                    "started_at": start_time_str,
                    "elapsed_minutes": elapsed_min,
                }
    except Exception as e:
        logging.getLogger("services").debug(f"Failed to get active job: {e}")
    
    return None

