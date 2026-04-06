"""
Update-Check Route
==================
GET /api/version/check
  → Vergleicht laufende Version mit der aktuellen GitHub-Version.
  → Kanal (stable/beta) wird aus der DB-Einstellung "update_channel" gelesen.
  → Cached 6h damit GitHub nicht zugespammt wird.

GET /api/version/current
  → Gibt nur die laufende Version zurück (kein GitHub-Request).
"""

import logging
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.routes.settings_routes import get_setting

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/version", tags=["version"])

_CACHE_TTL = 6 * 3600
_cache: dict = {"latest": None, "fetched_at": 0.0, "channel": None}

_VERSION_URLS = {
    "beta":   "https://raw.githubusercontent.com/d3nn3s08/FilamentHub/beta/VERSION",
    "stable": "https://raw.githubusercontent.com/d3nn3s08/FilamentHub/main/VERSION",
}


def _read_current_version() -> str:
    try:
        p = Path(__file__).resolve().parent.parent.parent / "VERSION"
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.0.0"


def is_newer_version(current: str, latest: str) -> bool:
    """True wenn latest > current (semver MAJOR.MINOR.PATCH)."""
    try:
        def parts(v: str):
            return [int(x) for x in v.strip().split(".")]
        c, l = parts(current), parts(latest)
        max_len = max(len(c), len(l))
        c += [0] * (max_len - len(c))
        l += [0] * (max_len - len(l))
        return l > c
    except (ValueError, AttributeError):
        return False


async def _fetch_latest(channel: str) -> str | None:
    now = time.time()
    if (
        _cache["latest"]
        and _cache["channel"] == channel
        and (now - _cache["fetched_at"]) < _CACHE_TTL
    ):
        return _cache["latest"]

    url = _VERSION_URLS.get(channel, _VERSION_URLS["stable"])
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0, follow_redirects=True)
        if resp.status_code == 200:
            version = resp.text.strip()
            _cache.update({"latest": version, "fetched_at": now, "channel": channel})
            return version
    except Exception as exc:
        logger.debug("[Version] GitHub-Check fehlgeschlagen: %s", exc)
    return None


@router.get("/current")
def get_current_version():
    return {"version": _read_current_version()}


@router.get("/check")
async def check_for_update(session: Session = Depends(get_session), channel: str | None = None):
    if channel not in ("stable", "beta"):
        channel = get_setting(session, "update_channel", "beta") or "beta"
    current = _read_current_version()
    latest  = await _fetch_latest(channel)

    if latest is None:
        return {
            "current": current,
            "latest": None,
            "update_available": False,
            "channel": channel,
            "error": "GitHub nicht erreichbar",
        }

    return {
        "current":          current,
        "latest":           latest,
        "update_available": is_newer_version(current, latest),
        "channel":          channel,
    }
