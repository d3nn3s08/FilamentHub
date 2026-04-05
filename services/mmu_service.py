"""
Happy Hare MMU Service
======================
Erkennt und verwaltet Multi-Material Unit (MMU) Unterstützung für Klipper-Drucker
über die Happy Hare Firmware (https://github.com/moggieuk/Happy-Hare).

Happy Hare exponiert seine Daten über Moonraker als Printer-Objekte:
  - `mmu`      → Haupt-MMU-Status, Gate-Arrays, TTG-Map
  - `mmu_gate` → Detaillierter Gate-Status

Datenfluss:
  klipper_polling_service.py
      → _poll_single() fragt mmu + mmu_gate ab
      → ruft MmuService.process_poll_data() auf
      → MmuService parsed Daten, updated live_state

API:
  GET  /api/mmu/{printer_id}/status    → MMU Live-Status
  GET  /api/mmu/{printer_id}/gates     → Alle Gates mit Spool-Mapping
  POST /api/mmu/{printer_id}/gates/{gate}/assign  → Spool einem Gate zuweisen
"""

import logging
from typing import Dict, List, Optional, Any

from sqlmodel import Session, select

from app.database import engine
from app.models.printer import Printer
from app.models.spool import Spool
from app.services.live_state import set_live_state, get_live_state

logger = logging.getLogger("mmu_service")

# ---------------------------------------------------------------------------
# Action-Codes (Happy Hare MMU action Enum-Werte als Klartext)
# ---------------------------------------------------------------------------
_ACTION_LABELS: Dict[int, str] = {
    0:  "idle",
    1:  "loading",
    2:  "unloading",
    3:  "loading_extruder",
    4:  "unloading_extruder",
    5:  "exiting_extruder",
    6:  "forming_tip",
    7:  "heating",
    8:  "checking_gate",
    9:  "selecting_tool",
    10: "calibrating_bowden",
    11: "homing",
    12: "unknown",
}

# Filament-Positions-Codes
_FILAMENT_POS_LABELS: Dict[int, str] = {
    0: "unknown",
    1: "unloaded",
    2: "start_bowden",
    3: "in_bowden",
    4: "end_bowden",
    5: "homed_gate",
    6: "homed_extruder",
    7: "extruder_entry",
    8: "loaded",
    9: "homed_ts",
    10: "past_ts",
}

# Gate-Status-Codes
_GATE_STATUS_LABELS: Dict[int, str] = {
    0: "empty",
    1: "available",
    2: "available_from_buffer",
    -1: "unknown",
}


# ---------------------------------------------------------------------------
# MmuService Singleton
# ---------------------------------------------------------------------------
class MmuService:
    """
    Verwaltet MMU-Daten für alle Klipper-Drucker die Happy Hare haben.
    Wird als Singleton verwendet (get_mmu_service()).
    """

    def __init__(self):
        # printer_id → hat_mmu (bool, None = noch unbekannt)
        self._mmu_detected: Dict[str, Optional[bool]] = {}

    # ------------------------------------------------------------------
    # Erkennung
    # ------------------------------------------------------------------
    def is_mmu_present(self, printer_id: str) -> Optional[bool]:
        """
        Gibt zurück ob für diesen Drucker MMU erkannt wurde.
        None = noch nicht geprüft.
        """
        return self._mmu_detected.get(str(printer_id))

    def mark_mmu_present(self, printer_id: str, present: bool) -> None:
        """Setzt MMU-Erkennungsstatus (wird vom Poller aufgerufen)."""
        pid = str(printer_id)
        old = self._mmu_detected.get(pid)
        self._mmu_detected[pid] = present
        if old != present:
            status = "ERKANNT" if present else "NICHT ERKANNT"
            logger.info("[MMU] Drucker %s: Happy Hare %s", printer_id, status)

    # ------------------------------------------------------------------
    # Daten verarbeiten (vom Klipper-Poller aufgerufen)
    # ------------------------------------------------------------------
    def process_poll_data(self, printer: Printer, objects_status: Dict[str, Any]) -> bool:
        """
        Verarbeitet die gepollten Moonraker-Objekte und extrahiert MMU-Daten.
        Schreibt das Ergebnis in den live_state.

        Returns:
            True  → MMU-Daten gefunden und verarbeitet
            False → Kein MMU oder Fehler
        """
        pid = str(printer.id)
        mmu_raw = objects_status.get("mmu")

        if mmu_raw is None:
            # Kein mmu-Objekt → Happy Hare nicht installiert
            self.mark_mmu_present(pid, False)
            return False

        try:
            mmu_data = self._parse_mmu_state(mmu_raw, objects_status)
            mmu_data["printer_id"] = pid
            mmu_data["printer_name"] = printer.name

            # Spool-Mapping aus DB holen und einbetten
            mmu_data["gates"] = self._enrich_gates_with_spools(pid, mmu_data["gates"])

            # In live_state schreiben → key: "mmu_{printer_id}"
            set_live_state(f"mmu_{pid}", mmu_data)

            self.mark_mmu_present(pid, True)
            logger.debug("[MMU] Drucker %s: %d Gates, Tool=%s, Action=%s",
                         printer.name,
                         mmu_data.get("num_gates", 0),
                         mmu_data.get("tool"),
                         mmu_data.get("action_label"))
            return True

        except Exception:
            logger.exception("[MMU] Fehler beim Verarbeiten der MMU-Daten für %s", printer.name)
            return False

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def _parse_mmu_state(self, mmu_raw: Dict, objects_status: Dict) -> Dict:
        """Parsed das rohe mmu-Objekt in ein sauberes Dict."""

        num_gates = int(mmu_raw.get("num_gates", 0))

        # Happy Hare liefert "action" je nach Version als String ("Idle") oder Int (0)
        action_raw = mmu_raw.get("action", 12)
        if isinstance(action_raw, str):
            action_label = action_raw
            action_code = next(
                (k for k, v in _ACTION_LABELS.items() if v == action_raw.lower()),
                12,
            )
        else:
            action_code = int(action_raw)
            action_label = _ACTION_LABELS.get(action_code, "unknown")

        filament_pos_code = int(mmu_raw.get("filament_pos", 0))

        # Gate-Arrays auslesen (Happy Hare liefert Listen)
        gate_material   = mmu_raw.get("gate_material", [])
        gate_color      = mmu_raw.get("gate_color", [])
        gate_status     = mmu_raw.get("gate_status", [])
        gate_spool_id   = mmu_raw.get("gate_spool_id", [])   # Spoolman IDs
        gate_filament_name = mmu_raw.get("gate_filament_name", [])
        gate_speed_override = mmu_raw.get("gate_speed_override", [])
        gate_temperature = mmu_raw.get("gate_temperature", [])
        ttg_map         = mmu_raw.get("ttg_map", [])           # tool→gate Mapping

        # Gates zusammenbauen
        gates = []
        for i in range(num_gates):
            g_status_code = _safe_list_get(gate_status, i, -1)
            gates.append({
                "gate":          i,
                "material":      _safe_list_get(gate_material, i, ""),
                "color":         _normalize_color(_safe_list_get(gate_color, i, "")),
                "filament_name": _safe_list_get(gate_filament_name, i, ""),
                "status":        g_status_code,
                "status_label":  _GATE_STATUS_LABELS.get(g_status_code, "unknown"),
                "spool_id_spoolman": _safe_list_get(gate_spool_id, i, None),
                "speed_override": _safe_list_get(gate_speed_override, i, 100),
                "temperature":   _safe_list_get(gate_temperature, i, 0),
                "is_active":     (int(mmu_raw.get("gate", -1)) == i),
            })

        # Tool→Gate Reverse-Map erstellen
        tool_to_gate = {}
        for tool_idx, gate_idx in enumerate(ttg_map):
            tool_to_gate[tool_idx] = int(gate_idx)

        return {
            "enabled":           bool(mmu_raw.get("enabled", False)),
            "is_homed":          bool(mmu_raw.get("is_homed", False)),
            "num_gates":         num_gates,
            "tool":              mmu_raw.get("tool", -1),
            "gate":              mmu_raw.get("gate", -1),
            "material":          mmu_raw.get("material", ""),
            "filament_pos":      filament_pos_code,
            "filament_pos_label": _FILAMENT_POS_LABELS.get(filament_pos_code, "unknown"),
            "action":            action_code,
            "action_label":      action_label,
            "print_state":       mmu_raw.get("print_state", ""),
            "has_bypass":        bool(mmu_raw.get("has_bypass", False)),
            "is_locked":         bool(mmu_raw.get("is_locked", False)),
            "is_paused":         bool(mmu_raw.get("is_paused", False)),
            "is_in_print":       bool(mmu_raw.get("is_in_print", False)),
            "num_toolchanges":   int(mmu_raw.get("num_toolchanges", 0)),
            "sync_drive":        bool(mmu_raw.get("sync_drive", False)),
            "ttg_map":           ttg_map,
            "tool_to_gate":      tool_to_gate,
            "gates":             gates,
            # Endless Spool
            "endless_spool_enabled": bool(mmu_raw.get("endless_spool_enabled", False)),
            "endless_spool_groups": mmu_raw.get("endless_spool_groups", []),
        }

    # ------------------------------------------------------------------
    # Spool-Mapping
    # ------------------------------------------------------------------
    def _enrich_gates_with_spools(self, printer_id: str, gates: List[Dict]) -> List[Dict]:
        """
        Reichert Gate-Daten mit Spool-Informationen aus der FilamentHub-DB an.
        Spulen werden über printer_id + printer_slot (=Gate-Nummer) gemappt.
        """
        try:
            with Session(engine) as session:
                assigned_spools = session.exec(
                    select(Spool).where(
                        Spool.printer_id == printer_id,
                        Spool.assigned == True,  # noqa: E712
                    )
                ).all()

            # slot → Spool Dict
            slot_map: Dict[int, Dict] = {}
            for spool in assigned_spools:
                if spool.printer_slot is not None:
                    slot_map[int(spool.printer_slot)] = {
                        "spool_id":       spool.id,
                        "spool_number":   spool.spool_number,
                        "spool_name":     spool.name,
                        "spool_color":    spool.color,
                        "spool_vendor":   spool.vendor,
                        "weight_current": spool.weight_current,
                        "weight_full":    spool.weight_full,
                        "weight_empty":   spool.weight_empty,
                        "remain_percent": spool.remain_percent,
                    }

            # Gates anreichern
            enriched = []
            for gate in gates:
                gate_idx = gate["gate"]
                spool_info = slot_map.get(gate_idx)
                enriched.append({
                    **gate,
                    "filamenthub_spool": spool_info,  # None wenn kein Mapping
                })
            return enriched

        except Exception:
            logger.exception("[MMU] Fehler beim Spool-Mapping für Drucker %s", printer_id)
            return gates

    # ------------------------------------------------------------------
    # Spool einem Gate zuweisen
    # ------------------------------------------------------------------
    def assign_spool_to_gate(self, printer_id: str, gate: int, spool_id: str) -> bool:
        """
        Weist einer Spule einen MMU-Gate zu (setzt printer_id + printer_slot).
        Returns True bei Erfolg.
        """
        try:
            with Session(engine) as session:
                spool = session.get(Spool, spool_id)
                if not spool:
                    logger.warning("[MMU] Spool %s nicht gefunden", spool_id)
                    return False

                # Bestehende Zuweisung für diesen Gate aufheben
                existing = session.exec(
                    select(Spool).where(
                        Spool.printer_id == printer_id,
                        Spool.printer_slot == gate,
                        Spool.assigned == True,  # noqa: E712
                        Spool.id != spool_id,
                    )
                ).all()
                for old_spool in existing:
                    old_spool.assigned = False
                    old_spool.printer_id = None
                    old_spool.printer_slot = None
                    session.add(old_spool)

                # Neue Zuweisung
                spool.printer_id = printer_id
                spool.printer_slot = gate
                spool.assigned = True
                session.add(spool)
                session.commit()

            logger.info("[MMU] Spool %s → Gate %d (Drucker %s)", spool_id, gate, printer_id)
            return True

        except Exception:
            logger.exception("[MMU] Fehler beim Zuweisen von Spool %s an Gate %d", spool_id, gate)
            return False

    def unassign_gate(self, printer_id: str, gate: int) -> bool:
        """Hebt die Spool-Zuweisung für einen Gate auf."""
        try:
            with Session(engine) as session:
                spools = session.exec(
                    select(Spool).where(
                        Spool.printer_id == printer_id,
                        Spool.printer_slot == gate,
                        Spool.assigned == True,  # noqa: E712
                    )
                ).all()
                for s in spools:
                    s.assigned = False
                    s.printer_id = None
                    s.printer_slot = None
                    session.add(s)
                session.commit()

            logger.info("[MMU] Gate %d (Drucker %s) Zuweisung aufgehoben", gate, printer_id)
            return True
        except Exception:
            logger.exception("[MMU] Fehler beim Aufheben Gate %d", gate)
            return False

    # ------------------------------------------------------------------
    # Live-State lesen
    # ------------------------------------------------------------------
    def get_mmu_live_state(self, printer_id: str) -> Optional[Dict]:
        """Gibt den aktuellen MMU-Zustand aus dem live_state zurück."""
        return get_live_state(f"mmu_{printer_id}")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_mmu_service_instance: Optional[MmuService] = None


def get_mmu_service() -> MmuService:
    """Gibt den globalen MmuService zurück (Singleton)."""
    global _mmu_service_instance
    if _mmu_service_instance is None:
        _mmu_service_instance = MmuService()
    return _mmu_service_instance


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def _safe_list_get(lst: list, index: int, default):
    """Sicherer Listen-Zugriff mit Fallback."""
    try:
        return lst[index]
    except (IndexError, TypeError):
        return default


def _normalize_color(color_str: str) -> str:
    """
    Normalisiert Happy Hare Farb-Strings zu CSS-kompatiblen Hex-Farben.
    Happy Hare liefert entweder 'RRGGBB' (ohne #) oder '' (leer).
    """
    if not color_str:
        return ""
    color_str = color_str.strip()
    if not color_str.startswith("#"):
        color_str = f"#{color_str}"
    return color_str
