from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Simple in-memory live state store for printers
# key: device_id (cloud_serial), value: { device, ts, payload }
live_state: Dict[str, Dict[str, Any]] = {}


def _deep_merge(base: Any, incoming: Any) -> Any:
    if not isinstance(base, dict) or not isinstance(incoming, dict):
        return incoming
    merged = dict(base)
    for key, value in incoming.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged.get(key), value)
        else:
            merged[key] = value
    return merged


def set_live_state(device_id: str, payload: Any) -> None:
    existing = live_state.get(device_id, {}).get("payload")
    if isinstance(existing, dict) and isinstance(payload, dict):
        payload = _deep_merge(existing, payload)
    live_state[device_id] = {
        "device": device_id,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": payload,
    }
    # Debug-Log entfernt (verursacht I/O-Last bei jedem MQTT-Update)


def get_live_state(device_id: str) -> Optional[Dict[str, Any]]:
    return live_state.get(device_id)


def get_all_live_state() -> Dict[str, Dict[str, Any]]:
    return live_state
