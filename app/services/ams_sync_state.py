from __future__ import annotations

from typing import Literal

SyncState = Literal["pending", "syncing", "ok", "error"]

_sync_state: SyncState = "pending"
_invalid_payloads: int = 0


def get_ams_sync_state() -> SyncState:
    return _sync_state


def set_ams_sync_state(state: SyncState) -> None:
    global _sync_state
    _sync_state = state


def reset_invalid_payloads() -> None:
    global _invalid_payloads
    _invalid_payloads = 0


def note_invalid_payload(max_failures: int = 3) -> SyncState:
    global _invalid_payloads
    _invalid_payloads += 1
    if _invalid_payloads >= max_failures:
        set_ams_sync_state("error")
    else:
        set_ams_sync_state("pending")
    return _sync_state
