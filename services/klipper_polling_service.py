"""
[BETA] Klipper-Support: Moonraker HTTP Polling Service
Fragt alle Klipper-Drucker per Moonraker REST-API ab (1s-Intervall).
Schreibt Live-Daten in live_state + PrinterService — komplett getrennt von Bambu/MQTT.

Happy Hare MMU-Integration:
  Wenn ein Drucker Happy Hare hat, werden zusätzlich `mmu` + `mmu_gate` abgefragt.
  Erkennung: Beim ersten Poll wird geprüft ob das `mmu`-Objekt verfügbar ist.
  Danach: MmuService.process_poll_data() parsed + speichert die MMU-Daten.
"""
import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Optional, Set

import httpx
from sqlmodel import Session, select

from app.database import engine
from app.models.printer import Printer
from app.services.live_state import set_live_state
from services.spoolman_service import build_active_spool_hint, fetch_active_spoolman_id

logger = logging.getLogger("klipper_poller")

# ---------------------------------------------------------------------------
# Moonraker-Objekte die wir abfragen (Basis — ohne MMU)
# ---------------------------------------------------------------------------
_QUERY_OBJECTS = (
    "print_stats"
    "&extruder"
    "&heater_bed"
    "&fan"
    "&display_status"
    "&temperature_sensor"
)

# Happy Hare MMU-Objekte (werden nur abgefragt wenn MMU erkannt)
_MMU_QUERY_OBJECTS = (
    "&mmu"
    "&mmu_gate"
)

# Drucker-IDs für die MMU bereits erkannt wurde (verhindert wiederholte Detection-Requests)
_mmu_detected_printers:  Set[str] = set()
_mmu_no_mmu_printers:    Set[str] = set()
# Intervall für Re-Detection (alle N Poll-Zyklen erneut prüfen ob MMU hinzugekommen)
_MMU_REDETECT_INTERVAL = 60  # Sekunden
_mmu_last_check: Dict[str, float] = {}

_POLL_INTERVAL = 2    # Sekunden zwischen Abfragen
_HTTP_TIMEOUT  = 3.0  # Sekunden pro Request (erhöht für Beta-Tester mit WAN/VPN)

_stop_event: Optional[asyncio.Event] = None

# ---------------------------------------------------------------------------
# [BETA] Klipper-Support: Server-seitige Temperatur-History für Detail-Modal Chart
# 600 Einträge = 10 Min. bei 1s Polling-Intervall
# ---------------------------------------------------------------------------
_klipper_temp_history: Dict[str, deque] = {}


def get_klipper_temp_history(printer_id: str) -> list:
    """Gibt die Temperaturhistorie eines Klipper-Druckers zurück (für /api/live-state/klipper/{id}/temp-history)."""
    return list(_klipper_temp_history.get(str(printer_id), []))


# ---------------------------------------------------------------------------
# Happy Hare MMU-Erkennung
# ---------------------------------------------------------------------------
async def _detect_mmu(printer: Printer, client: httpx.AsyncClient, base_url: str) -> bool:
    """
    Prüft ob Happy Hare auf diesem Drucker installiert ist.
    Fragt das `mmu`-Objekt ab — wenn es existiert und `enabled` True ist → MMU vorhanden.
    Wird gecacht: einmal erkannt = dauerhaft aktiv (bis Neustart).
    """
    import time
    pid = str(printer.id)
    now = time.monotonic()

    # Bereits positiv erkannt → kein Re-Check nötig
    if pid in _mmu_detected_printers:
        return True

    # Negativ erkannt aber Re-Detection-Intervall noch nicht abgelaufen
    if pid in _mmu_no_mmu_printers:
        last = _mmu_last_check.get(pid, 0.0)
        if (now - last) < _MMU_REDETECT_INTERVAL:
            return False

    # Detection-Request senden
    try:
        resp = await client.get(
            f"{base_url}/printer/objects/query?mmu",
            timeout=_HTTP_TIMEOUT,
        )
        if resp.status_code != 200:
            _mmu_no_mmu_printers.add(pid)
            _mmu_last_check[pid] = now
            return False

        result = resp.json().get("result", {})
        mmu_data = result.get("status", {}).get("mmu")

        if mmu_data is not None and mmu_data.get("enabled", False):
            _mmu_detected_printers.add(pid)
            _mmu_no_mmu_printers.discard(pid)
            logger.info("[MMU Detection] Happy Hare erkannt auf: %s", printer.name)
            return True
        else:
            _mmu_no_mmu_printers.add(pid)
            _mmu_last_check[pid] = now
            return False

    except Exception:
        _mmu_no_mmu_printers.add(pid)
        _mmu_last_check[pid] = now
        return False


# ---------------------------------------------------------------------------
# Interner Hilfsfunktion: einzelnen Drucker abfragen
# ---------------------------------------------------------------------------
async def _poll_single(printer: Printer, client: httpx.AsyncClient, printer_service=None) -> None:
    base_url = f"http://{printer.ip_address}:{printer.port or 7125}"
    key = f"klipper_{printer.id}"

    try:
        # 1. Klippy-Status (online check)
        info_resp = await client.get(f"{base_url}/server/info", timeout=_HTTP_TIMEOUT)
        info_resp.raise_for_status()
        server_info = info_resp.json().get("result", {})
        klippy_state = server_info.get("klippy_state", "unknown")

        # Drucker ist erreichbar sobald /server/info erfolgreich ist
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if printer_service:
            printer_service.set_connected(key, True, last_seen=now_iso)

        # 2. Happy Hare MMU erkennen (non-blocking, gecacht)
        has_mmu = await _detect_mmu(printer, client, base_url)

        # 3. Druckerobjekte abfragen (mit optionalen MMU-Objekten)
        # Moonraker gibt 400 zurück wenn ein Objekt (z.B. display_status, temperature_sensor)
        # nicht in der Drucker-Config vorhanden ist → kein raise_for_status(), stattdessen
        # graceful fallback auf leere Status-Daten.
        query_str = _QUERY_OBJECTS + (_MMU_QUERY_OBJECTS if has_mmu else "")
        objects_data: dict = {}
        try:
            objects_resp = await client.get(
                f"{base_url}/printer/objects/query?{query_str}",
                timeout=_HTTP_TIMEOUT,
            )
            if objects_resp.status_code == 200:
                objects_data = objects_resp.json().get("result", {})
            else:
                logger.debug(
                    "[Klipper Poller] Objects-Query HTTP %d für %s — optionale Objekte fehlen in Config",
                    objects_resp.status_code, printer.name,
                )
        except Exception as obj_exc:
            logger.debug("[Klipper Poller] Objects-Query Fehler für %s: %s", printer.name, obj_exc)

        _status = objects_data.get("status", {})

        # Aktive Spule additiv erkennen:
        # Priorität MMU > Moonraker-Spoolman > none.
        moonraker_spoolman_id = None
        mmu_obj = _status.get("mmu") or {}
        mmu_gate_spool_ids = mmu_obj.get("gate_spool_id") if isinstance(mmu_obj, dict) else None
        if not isinstance(mmu_gate_spool_ids, list) or not mmu_gate_spool_ids:
            moonraker_spoolman_id = await fetch_active_spoolman_id(client, base_url, _HTTP_TIMEOUT)

        active_spool_hint = build_active_spool_hint(
            printer_id=str(printer.id),
            objects_status=_status,
            moonraker_spoolman_id=moonraker_spoolman_id,
        )

        payload = {
            "klippy_state": klippy_state,
            **objects_data,
            "filamenthub": {
                "active_spool": active_spool_hint,
            },
        }
        set_live_state(key, {"ts": now_iso, "payload": payload})

        # --- 4b. [BETA] Klipper-Support: Temperatur-Verlauf für Detail-Modal Chart speichern ---
        # Enthält auch Heizleistung (power 0.0–1.0) für zusätzliche Chart-Linien
        _nozzle       = _status.get("extruder", {}).get("temperature")
        _bed          = _status.get("heater_bed", {}).get("temperature")
        _nozzle_power = _status.get("extruder", {}).get("power")
        _bed_power    = _status.get("heater_bed", {}).get("power")
        if _nozzle is not None or _bed is not None:
            _pid_str = str(printer.id)
            if _pid_str not in _klipper_temp_history:
                # [BETA] Klipper-Support: 600 Einträge = 10 Min. bei 1s Polling-Intervall
                _klipper_temp_history[_pid_str] = deque(maxlen=600)
            _klipper_temp_history[_pid_str].append({
                "ts":           now_iso,
                "nozzle":       _nozzle,
                "bed":          _bed,
                "nozzle_power": _nozzle_power,
                "bed_power":    _bed_power,
            })

        # --- 5. Happy Hare MMU-Daten verarbeiten ---
        if has_mmu:
            try:
                from services.mmu_service import get_mmu_service
                get_mmu_service().process_poll_data(printer, _status)
            except Exception:
                logger.debug("[Klipper Poller] MMU-Verarbeitung Fehler für %s", printer.name)

        # --- 6. Job-Tracking ---
        try:
            from services.klipper_job_tracking import get_job_tracker
            get_job_tracker().process_poll(printer, payload)
        except Exception:
            pass  # Job-Tracking ist optional, Fehler sollen den Poller nicht stoppen

        state = _status.get("print_stats", {}).get("state", "?")
        mmu_tag = " [MMU✓]" if has_mmu else ""
        logger.debug("[Klipper Poller] Poll OK | %s%s | klippy=%s | state=%s",
                     printer.name, mmu_tag, klippy_state, state)

    except httpx.TimeoutException:
        logger.debug("[Klipper Poller] Timeout | %s (%s)", printer.name, base_url)
        if printer_service:
            printer_service.set_connected(key, False)
    except Exception as exc:
        logger.debug("[Klipper Poller] Fehler | %s: %s", printer.name, exc)
        if printer_service:
            printer_service.set_connected(key, False)


# ---------------------------------------------------------------------------
# Alle Klipper-Drucker aus DB laden und im PrinterService registrieren
# ---------------------------------------------------------------------------
async def _register_klipper_printers(printer_service=None) -> list:
    with Session(engine) as session:
        printers = session.exec(
            select(Printer).where(Printer.printer_type == "klipper")
        ).all()

    for printer in printers:
        key = f"klipper_{printer.id}"
        logger.info("[Klipper Poller] Registriert: %s → key=%s", printer.name, key)
        if printer_service:
            # [BETA] Klipper-Support: register_printer() ist die korrekte Methode des PrinterService
            # (NICHT register() — das existiert nicht und würde AttributeError → Task-Crash verursachen)
            printer_service.register_printer(
                key,
                name=printer.name,
                model="klipper",
                printer_id=str(printer.id),
                source="klipper_poller",
            )
    return list(printers)


# ---------------------------------------------------------------------------
# Haupt-Polling-Loop (läuft als asyncio.Task)
# ---------------------------------------------------------------------------
async def run_klipper_poller(printer_service=None) -> None:
    global _stop_event
    _stop_event = asyncio.Event()

    # Drucker registrieren
    printers = await _register_klipper_printers(printer_service)

    logger.info("[Klipper Poller] Gestartet (Intervall: %ds, %d Drucker)",
                _POLL_INTERVAL, len(printers))

    # [BETA] Klipper-Support: Startup-Recovery — verwaiste "running" Jobs bereinigen
    try:
        from services.klipper_job_tracking import get_job_tracker
        get_job_tracker().recover_on_startup()
    except Exception:
        pass

    from app.database import engine as _engine
    # Bereits registrierte Keys tracken → Neuregistrierung nur für neue Drucker
    _registered_keys: set = {f"klipper_{p.id}" for p in printers}

    async with httpx.AsyncClient() as client:
        while not _stop_event.is_set():
            # Drucker-Liste bei jedem Zyklus neu laden (falls Drucker hinzugefügt wurden)
            with Session(_engine) as session:
                printers = session.exec(
                    select(Printer).where(Printer.printer_type == "klipper")
                ).all()

            # Neu hinzugefügte Drucker dynamisch im PrinterService registrieren
            for printer in printers:
                key = f"klipper_{printer.id}"
                if key not in _registered_keys:
                    logger.info("[Klipper Poller] Neuer Drucker erkannt: %s → key=%s", printer.name, key)
                    if printer_service:
                        printer_service.register_printer(
                            key,
                            name=printer.name,
                            model="klipper",
                            printer_id=str(printer.id),
                            source="klipper_poller",
                        )
                    _registered_keys.add(key)

            for printer in printers:
                if _stop_event.is_set():
                    break
                await _poll_single(printer, client, printer_service)

            # Warte auf nächsten Poll-Zyklus (oder Stop-Signal)
            try:
                await asyncio.wait_for(_stop_event.wait(), timeout=_POLL_INTERVAL)
            except asyncio.TimeoutError:
                pass  # Normales Timeout → nächster Zyklus


def stop_klipper_poller() -> None:
    """Stoppt den Polling-Loop (aus dem Shutdown-Handler aufrufen)."""
    if _stop_event:
        _stop_event.set()
        logger.info("[Klipper Poller] Stop-Signal gesendet")
