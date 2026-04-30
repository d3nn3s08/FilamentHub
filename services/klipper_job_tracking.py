import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlmodel import Session, select

from app.database import engine
from app.models.job import Job
from app.models.printer import Printer
from app.models.spool import Spool

logger = logging.getLogger("klipper_job_tracker")

_ACTIVE_STATES = {"PRINTING", "PAUSED"}
_COMPLETED_STATES = {"COMPLETE", "COMPLETED"}
_CANCELLED_STATES = {"CANCELLED", "CANCELED"}
_FAILED_STATES = {"ERROR", "FAILED", "ABORTED", "STOPPED", "EXCEPTION"}


class KlipperJobTracker:
    def __init__(self) -> None:
        self._last_state: Dict[str, str] = {}

    def recover_on_startup(self) -> None:
        logger.info("[Klipper JobTracker] Startup-Recovery im defensiven Modus übersprungen")

    def process_poll(self, printer: Printer, payload: Dict[str, Any]) -> None:
        status = payload.get("status") or {}
        print_stats = status.get("print_stats") or {}
        raw_state = str(print_stats.get("state") or "").upper().strip()
        printer_id = str(printer.id)

        prev_state = self._last_state.get(printer_id, "")
        self._last_state[printer_id] = raw_state

        try:
            with Session(engine) as session:
                running_job = session.exec(
                    select(Job)
                    .where(Job.printer_id == printer_id)
                    .where(Job.finished_at == None)  # noqa: E711
                ).first()

                if raw_state in _ACTIVE_STATES:
                    if running_job is None:
                        self._start_job(session, printer, payload)
                    else:
                        self._update_job(session, running_job, payload)
                    return

                if running_job is None:
                    return

                if prev_state in _ACTIVE_STATES and raw_state not in _ACTIVE_STATES:
                    self._finish_job(session, running_job, raw_state, payload)
        except Exception:
            logger.exception("[Klipper JobTracker] Fehler bei process_poll für %s", printer.name)

    def _extract_active_spool_id(self, payload: Dict[str, Any]) -> Optional[str]:
        hint = (payload.get("filamenthub") or {}).get("active_spool") or {}
        if hint.get("source") not in {"mmu", "moonraker"}:
            return None
        if hint.get("resolved") is not True:
            return None
        spool_id = hint.get("local_spool_id")
        return str(spool_id) if spool_id else None

    def _load_spool(self, session: Session, spool_id: Optional[str]) -> Optional[Spool]:
        if not spool_id:
            return None
        return session.get(Spool, spool_id)

    def _job_name(self, payload: Dict[str, Any]) -> str:
        status = payload.get("status") or {}
        print_stats = status.get("print_stats") or {}
        filename = print_stats.get("filename")
        return str(filename) if filename else "Unnamed Job"

    def _print_source(self, payload: Dict[str, Any]) -> str:
        hint = (payload.get("filamenthub") or {}).get("active_spool") or {}
        source = hint.get("source")
        if source == "mmu":
            return "mmu"
        if source == "moonraker":
            return "spoolman"
        return "unknown"

    def _start_job(self, session: Session, printer: Printer, payload: Dict[str, Any]) -> None:
        spool_id = self._extract_active_spool_id(payload)
        spool = self._load_spool(session, spool_id)
        job_name = self._job_name(payload)

        job = Job(
            printer_id=str(printer.id),
            spool_id=spool.id if spool else None,
            name=job_name,
            task_name=job_name,
            gcode_file=job_name,
            started_at=datetime.utcnow(),
            status="running",
            print_source=self._print_source(payload),
        )

        if spool:
            job.spool_number = spool.spool_number
            job.spool_name = spool.name
            job.spool_vendor = spool.vendor
            job.spool_color = spool.color
            if spool.weight_current is not None:
                job.start_weight = spool.weight_current

        session.add(job)
        session.commit()
        logger.info(
            "[Klipper JobTracker] Job gestartet printer=%s job=%s source=%s spool=%s",
            printer.name,
            job.id,
            job.print_source,
            job.spool_id,
        )

    def _update_job(self, session: Session, job: Job, payload: Dict[str, Any]) -> None:
        changed = False
        job_name = self._job_name(payload)
        if job.name == "Unnamed Job" and job_name != "Unnamed Job":
            job.name = job_name
            job.task_name = job_name
            job.gcode_file = job_name
            changed = True

        if not job.spool_id:
            spool_id = self._extract_active_spool_id(payload)
            spool = self._load_spool(session, spool_id)
            if spool:
                job.spool_id = spool.id
                job.spool_number = spool.spool_number
                job.spool_name = spool.name
                job.spool_vendor = spool.vendor
                job.spool_color = spool.color
                if job.start_weight is None and spool.weight_current is not None:
                    job.start_weight = spool.weight_current
                changed = True
                logger.info(
                    "[Klipper JobTracker] Auto-Binding job=%s spool=%s via %s",
                    job.id,
                    spool.id,
                    ((payload.get("filamenthub") or {}).get("active_spool") or {}).get("source"),
                )

        if changed:
            session.add(job)
            session.commit()

    def _finish_job(self, session: Session, job: Job, raw_state: str, payload: Dict[str, Any]) -> None:
        self._update_job(session, job, payload)

        if raw_state in _COMPLETED_STATES:
            job.status = "completed"
        elif raw_state in _CANCELLED_STATES:
            job.status = "cancelled"
        elif raw_state in _FAILED_STATES:
            job.status = "failed"
        else:
            job.status = "completed"

        spool = self._load_spool(session, job.spool_id)
        if spool and spool.weight_current is not None:
            job.end_weight = spool.weight_current
        job.finished_at = datetime.utcnow()

        session.add(job)
        session.commit()
        logger.info(
            "[Klipper JobTracker] Job beendet job=%s status=%s spool=%s",
            job.id,
            job.status,
            job.spool_id,
        )


_tracker_instance: Optional[KlipperJobTracker] = None


def get_job_tracker() -> KlipperJobTracker:
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = KlipperJobTracker()
    return _tracker_instance
