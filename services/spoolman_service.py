import logging
from typing import Any, Dict, Optional

import httpx
from sqlmodel import Session, select

from app.database import engine
from app.models.spool import Spool

logger = logging.getLogger("spoolman_service")


def _normalize_spoolman_id(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def fetch_active_spoolman_id(
    client: httpx.AsyncClient,
    base_url: str,
    timeout: float,
) -> Optional[int]:
    try:
        resp = await client.get(f"{base_url}/server/spoolman/spool_id", timeout=timeout)
        if resp.status_code != 200:
            return None
        result = resp.json().get("result", {})
        return _normalize_spoolman_id(result.get("spool_id"))
    except Exception:
        logger.debug("[Spoolman] Konnte aktive Moonraker-Spule nicht lesen", exc_info=True)
        return None


def get_active_mmu_spoolman_id(objects_status: Dict[str, Any]) -> Optional[int]:
    mmu = objects_status.get("mmu") or {}
    if not isinstance(mmu, dict):
        return None

    gate_spool_ids = mmu.get("gate_spool_id")
    if not isinstance(gate_spool_ids, list) or not gate_spool_ids:
        return None

    try:
        gate_index = int(mmu.get("gate", -1))
    except (TypeError, ValueError):
        return None

    if gate_index < 0 or gate_index >= len(gate_spool_ids):
        return None

    return _normalize_spoolman_id(gate_spool_ids[gate_index])


def resolve_local_spool_by_spoolman_id(printer_id: str, spoolman_id: int) -> Optional[Spool]:
    spoolman_id_str = str(spoolman_id)

    with Session(engine) as session:
        matches = session.exec(
            select(Spool).where(
                Spool.printer_id == printer_id,
                Spool.external_id == spoolman_id_str,
            )
        ).all()

        if len(matches) == 1:
            return matches[0]

        if len(matches) > 1:
            assigned_matches = [spool for spool in matches if spool.assigned]
            if len(assigned_matches) == 1:
                return assigned_matches[0]
            logger.warning(
                "[Spoolman] Mehrdeutiges Mapping printer=%s spoolman_id=%s (%d Treffer)",
                printer_id,
                spoolman_id,
                len(matches),
            )
            return None

    return None


def build_active_spool_hint(
    printer_id: str,
    objects_status: Dict[str, Any],
    moonraker_spoolman_id: Optional[int],
) -> Dict[str, Any]:
    mmu_spoolman_id = get_active_mmu_spoolman_id(objects_status)

    source = "none"
    spoolman_id = None
    if mmu_spoolman_id is not None:
        source = "mmu"
        spoolman_id = mmu_spoolman_id
    elif moonraker_spoolman_id is not None:
        source = "moonraker"
        spoolman_id = moonraker_spoolman_id

    hint: Dict[str, Any] = {
        "source": source,
        "spoolman_id": spoolman_id,
        "resolved": False,
        "local_spool_id": None,
        "local_spool_number": None,
        "local_spool_label": None,
    }

    if spoolman_id is None:
        return hint

    local_spool = resolve_local_spool_by_spoolman_id(printer_id, spoolman_id)
    if local_spool is None:
        return hint

    hint.update(
        {
            "resolved": True,
            "local_spool_id": local_spool.id,
            "local_spool_number": local_spool.spool_number,
            "local_spool_label": local_spool.label or local_spool.name,
        }
    )
    return hint
