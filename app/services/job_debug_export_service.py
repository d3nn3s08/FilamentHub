import json
import logging
import threading
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from sqlmodel import Session, select

from app.database import engine
from app.models.job import Job
from app.models.printer import Printer
from app.models.settings import Setting

logger = logging.getLogger("services")


class JobDebugExportService:
    def __init__(self) -> None:
        self.base_dir = Path("data/debug/job_exports")
        self.manifest_path = self.base_dir / "manifest.json"
        self._lock = threading.Lock()
        self._enabled_cache: Optional[bool] = None
        self._enabled_cache_ts = 0.0
        self._cache_ttl_secs = 3.0
        self._default_max_jobs = 2

    def _ensure_storage(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize(self, value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(k): self._sanitize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._sanitize(v) for v in value]
        if hasattr(value, "model_dump"):
            try:
                return self._sanitize(value.model_dump())
            except Exception:
                return str(value)
        if hasattr(value, "__dict__"):
            try:
                return self._sanitize(vars(value))
            except Exception:
                return str(value)
        return str(value)

    def _load_setting_value(self, key: str) -> Optional[str]:
        try:
            with Session(engine) as session:
                setting = session.exec(select(Setting).where(Setting.key == key)).first()
                return setting.value if setting else None
        except Exception:
            logger.exception("[JOB EXPORT] Failed to load setting %s", key)
            return None

    def is_enabled(self, force_refresh: bool = False) -> bool:
        now = time.monotonic()
        if not force_refresh and self._enabled_cache is not None and now - self._enabled_cache_ts < self._cache_ttl_secs:
            return self._enabled_cache

        raw = self._load_setting_value("debug.job_export.enabled")
        enabled = str(raw).strip().lower() in {"1", "true", "yes", "on"} if raw is not None else False
        self._enabled_cache = enabled
        self._enabled_cache_ts = now
        return enabled

    def get_max_jobs(self) -> int:
        raw = self._load_setting_value("debug.job_export.max_jobs")
        try:
            value = int(raw) if raw is not None else self._default_max_jobs
        except (TypeError, ValueError):
            value = self._default_max_jobs
        return max(1, min(value, self._default_max_jobs))

    def _load_manifest(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("[JOB EXPORT] Failed to read manifest")
            return []
        if not isinstance(data, list):
            return []
        cleaned: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            rel_path = item.get("file_path")
            if not rel_path:
                continue
            file_path = self.base_dir / str(rel_path)
            if not file_path.exists():
                continue
            cleaned.append(item)
        return cleaned

    def _write_manifest(self, manifest: list[dict[str, Any]]) -> None:
        self._ensure_storage()
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _build_job_snapshot(self, job: Optional[Job]) -> Optional[dict[str, Any]]:
        if job is None:
            return None
        return {
            "id": job.id,
            "printer_id": job.printer_id,
            "spool_id": job.spool_id,
            "name": job.name,
            "display_name": job.display_name,
            "status": job.status,
            "print_source": job.print_source,
            "task_id": job.task_id,
            "printer_job_id": getattr(job, "printer_job_id", None),
            "printer_subtask_id": getattr(job, "printer_subtask_id", None),
            "task_name": job.task_name,
            "gcode_file": job.gcode_file,
            "filament_used_mm": job.filament_used_mm,
            "filament_used_g": job.filament_used_g,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "start_weight": job.start_weight,
            "end_weight": job.end_weight,
            "spool_number": job.spool_number,
            "spool_name": job.spool_name,
            "spool_vendor": job.spool_vendor,
            "spool_color": job.spool_color,
        }

    def _build_printer_snapshot(self, printer: Optional[Printer]) -> Optional[dict[str, Any]]:
        if printer is None:
            return None
        return {
            "id": printer.id,
            "name": printer.name,
            "printer_type": getattr(printer, "printer_type", None),
            "model": getattr(printer, "model", None),
            "series": getattr(printer, "series", None),
            "cloud_serial": getattr(printer, "cloud_serial", None),
            "ip_address": getattr(printer, "ip_address", None),
        }

    def _make_filename(self, job: Optional[Job], source: str) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        job_name = (job.name if job and job.name else "unnamed_job").strip()
        safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in job_name)[:60].strip("_")
        if not safe_name:
            safe_name = "unnamed_job"
        return f"{timestamp}_{source}_{safe_name}.json"

    def _prune_oldest_locked(self, manifest: list[dict[str, Any]], keep_log_id: Optional[str] = None) -> list[dict[str, Any]]:
        max_jobs = self.get_max_jobs()
        prunable = [item for item in manifest if item.get("log_id") != keep_log_id]
        while len(manifest) >= max_jobs and prunable:
            oldest = sorted(prunable, key=lambda item: item.get("updated_at") or item.get("created_at") or "")[0]
            rel_path = oldest.get("file_path")
            if rel_path:
                try:
                    (self.base_dir / str(rel_path)).unlink(missing_ok=True)
                except Exception:
                    logger.exception("[JOB EXPORT] Failed to remove old export file %s", rel_path)
            manifest = [item for item in manifest if item.get("log_id") != oldest.get("log_id")]
            prunable = [item for item in manifest if item.get("log_id") != keep_log_id]
        return manifest

    def record_event(
        self,
        *,
        source: str,
        event_type: str,
        job: Optional[Job] = None,
        printer: Optional[Printer] = None,
        payload: Any = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.is_enabled():
            return

        log_id = job.id if job and getattr(job, "id", None) else None
        if not log_id:
            return

        event_timestamp = datetime.utcnow().isoformat()
        event_payload = {
            "timestamp": event_timestamp,
            "type": event_type,
            "payload": self._sanitize(payload),
            "extra": self._sanitize(extra or {}),
            "job": self._build_job_snapshot(job),
            "printer": self._build_printer_snapshot(printer),
        }

        with self._lock:
            self._ensure_storage()
            manifest = self._load_manifest()
            manifest_item = next((item for item in manifest if item.get("log_id") == log_id), None)

            if manifest_item is None:
                manifest = self._prune_oldest_locked(manifest)
                filename = self._make_filename(job, source)
                manifest_item = {
                    "log_id": log_id,
                    "file_path": filename,
                    "source": source,
                    "created_at": event_timestamp,
                }
                manifest.append(manifest_item)

            file_path = self.base_dir / str(manifest_item["file_path"])
            if file_path.exists():
                try:
                    document = json.loads(file_path.read_text(encoding="utf-8"))
                except Exception:
                    logger.exception("[JOB EXPORT] Failed to load export file %s", file_path)
                    document = {}
            else:
                document = {}

            if not isinstance(document, dict):
                document = {}

            events = document.get("events")
            if not isinstance(events, list):
                events = []

            meta = document.get("meta")
            if not isinstance(meta, dict):
                meta = {}

            meta.update({
                "log_id": log_id,
                "source": source,
                "job_id": log_id,
                "job_name": job.name if job else meta.get("job_name"),
                "job_status": job.status if job else meta.get("job_status"),
                "printer_id": printer.id if printer else meta.get("printer_id"),
                "printer_name": printer.name if printer else meta.get("printer_name"),
                "task_id": getattr(job, "task_id", None) if job else meta.get("task_id"),
                "printer_job_id": getattr(job, "printer_job_id", None) if job else meta.get("printer_job_id"),
                "printer_subtask_id": getattr(job, "printer_subtask_id", None) if job else meta.get("printer_subtask_id"),
                "started_at": job.started_at.isoformat() if job and job.started_at else meta.get("started_at"),
                "finished_at": job.finished_at.isoformat() if job and job.finished_at else meta.get("finished_at"),
                "updated_at": event_timestamp,
                "event_count": len(events) + 1,
            })

            events.append(event_payload)

            document["meta"] = meta
            document["events"] = events
            document["latest_job_snapshot"] = self._build_job_snapshot(job)
            document["latest_printer_snapshot"] = self._build_printer_snapshot(printer)

            file_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            manifest_item.update({
                "source": source,
                "job_name": meta.get("job_name"),
                "job_status": meta.get("job_status"),
                "printer_name": meta.get("printer_name"),
                "created_at": manifest_item.get("created_at") or event_timestamp,
                "updated_at": event_timestamp,
                "event_count": len(events),
                "task_id": meta.get("task_id"),
                "printer_job_id": meta.get("printer_job_id"),
                "printer_subtask_id": meta.get("printer_subtask_id"),
                "file_size_bytes": file_path.stat().st_size if file_path.exists() else 0,
            })

            manifest = sorted(manifest, key=lambda item: item.get("updated_at") or item.get("created_at") or "", reverse=True)
            self._write_manifest(manifest)

    def list_exports(self) -> list[dict[str, Any]]:
        with self._lock:
            manifest = self._load_manifest()
            exports: list[dict[str, Any]] = []
            for item in sorted(manifest, key=lambda row: row.get("updated_at") or row.get("created_at") or "", reverse=True):
                rel_path = item.get("file_path")
                if not rel_path:
                    continue
                file_path = self.base_dir / str(rel_path)
                if not file_path.exists():
                    continue
                exports.append(deepcopy(item))
            if len(exports) != len(manifest):
                self._write_manifest(exports)
            return exports

    def get_export_file(self, log_id: str) -> Optional[Path]:
        with self._lock:
            manifest = self._load_manifest()
            item = next((entry for entry in manifest if entry.get("log_id") == log_id), None)
            if not item:
                return None
            file_path = self.base_dir / str(item.get("file_path"))
            return file_path if file_path.exists() else None


_service_instance: Optional[JobDebugExportService] = None


def get_job_debug_export_service() -> JobDebugExportService:
    global _service_instance
    if _service_instance is None:
        _service_instance = JobDebugExportService()
    return _service_instance
