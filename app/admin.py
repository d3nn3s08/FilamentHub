import logging
from typing import Optional

logger = logging.getLogger("app")

_enabled: bool = False
_admin_hash: Optional[str] = None


def enable_admin(hash_value: str) -> None:
    """Aktiviere optionalen Admin-Modus (nur beim Startup).

    Diese Funktion speichert nur den gehashten Password-String und
    setzt ein internes Flag. Keine weiteren Side-Effects.
    """
    global _enabled, _admin_hash
    _admin_hash = hash_value
    _enabled = True
    logger.info("Admin enabled via environment variable")


def is_admin_enabled() -> bool:
    return _enabled


def get_admin_hash() -> Optional[str]:
    return _admin_hash
