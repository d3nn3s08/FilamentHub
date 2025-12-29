from datetime import datetime
from typing import Any, Dict, Optional

# Simple in-memory live state store for printers
# key: device_id (cloud_serial), value: { device, ts, payload }
live_state: Dict[str, Dict[str, Any]] = {}


def set_live_state(device_id: str, payload: Any) -> None:
    live_state[device_id] = {
        "device": device_id,
        "ts": datetime.utcnow().isoformat(),
        "payload": payload,
    }
    print(f"[live_state] Updated: device={device_id}, keys={len(live_state)}")


def get_live_state(device_id: str) -> Optional[Dict[str, Any]]:
    return live_state.get(device_id)


def get_all_live_state() -> Dict[str, Dict[str, Any]]:
    return live_state
