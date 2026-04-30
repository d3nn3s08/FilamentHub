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

import base64
import logging
import re
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

_VERSION_SOURCES = {
    "beta": [
        "https://raw.githubusercontent.com/d3nn3s08/FilamentHub/beta/VERSION",
        "https://api.github.com/repos/d3nn3s08/FilamentHub/contents/VERSION?ref=beta",
    ],
    "stable": [
        "https://raw.githubusercontent.com/d3nn3s08/FilamentHub/main/VERSION",
        "https://api.github.com/repos/d3nn3s08/FilamentHub/contents/VERSION?ref=main",
    ],
}


def _normalize_version_string(version: str | None) -> str | None:
    if not version:
        return None

    cleaned = str(version).strip()
    if not cleaned:
        return None

    match = re.search(r"(\d+(?:\.\d+){0,2})", cleaned)
    return match.group(1) if match else cleaned


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
            normalized = _normalize_version_string(v) or "0.0.0"
            return [int(x) for x in normalized.split(".")]
        c, l = parts(current), parts(latest)
        max_len = max(len(c), len(l))
        c += [0] * (max_len - len(c))
        l += [0] * (max_len - len(l))
        return l > c
    except (ValueError, AttributeError):
        return False


def compare_versions(current: str, other: str) -> int:
    """-1 wenn other < current, 0 wenn gleich, 1 wenn other > current."""
    try:
        def parts(v: str):
            normalized = _normalize_version_string(v) or "0.0.0"
            return [int(x) for x in normalized.split(".")]

        c, o = parts(current), parts(other)
        max_len = max(len(c), len(o))
        c += [0] * (max_len - len(c))
        o += [0] * (max_len - len(o))
        if o > c:
            return 1
        if o < c:
            return -1
        return 0
    except (ValueError, AttributeError):
        return 0


async def _fetch_latest(channel: str) -> str | None:
    now = time.time()
    if (
        _cache["latest"]
        and _cache["channel"] == channel
        and (now - _cache["fetched_at"]) < _CACHE_TTL
    ):
        return _cache["latest"]

    urls = _VERSION_SOURCES.get(channel, _VERSION_SOURCES["stable"])
    try:
        async with httpx.AsyncClient(headers={"User-Agent": "FilamentHub-Version-Check"}) as client:
            for url in urls:
                try:
                    resp = await client.get(url, timeout=8.0, follow_redirects=True)
                    if resp.status_code != 200:
                        continue

                    version: str | None = None
                    if "api.github.com/repos/" in url:
                        data = resp.json()
                        if "/contents/" in url:
                            content = data.get("content")
                            encoding = data.get("encoding")
                            if content and encoding == "base64":
                                version = base64.b64decode(content).decode("utf-8").strip()
                    else:
                        version = resp.text.strip()

                    if version:
                        normalized_version = _normalize_version_string(version)
                        if normalized_version:
                            _cache.update({"latest": normalized_version, "fetched_at": now, "channel": channel})
                            return normalized_version
                except Exception as exc:
                    logger.debug("[Version] Quelle fehlgeschlagen (%s): %s", url, exc)
                    continue
    except Exception as exc:
        logger.debug("[Version] GitHub-Check fehlgeschlagen: %s", exc)
    return None


@router.get("/current")
def get_current_version():
    return {"version": _read_current_version()}


@router.get("/check")
async def check_for_update(session: Session = Depends(get_session), channel: str | None = None):
    if channel not in ("stable", "beta"):
        channel = get_setting(session, "update_channel", "stable") or "stable"
    current = _read_current_version()
    latest  = await _fetch_latest(channel)

    if latest is None:
        error_message = "GitHub nicht erreichbar"
        if channel == "stable":
            error_message = "VERSION fehlt im main-Branch"
        elif channel == "beta":
            error_message = "VERSION fehlt im beta-Branch"
        return {
            "current": current,
            "latest": None,
            "update_available": False,
            "channel": channel,
            "error": error_message,
        }

    comparison = compare_versions(current, latest)
    return {
        "current":          current,
        "latest":           latest,
        "update_available": comparison == 1,
        "current_is_newer": comparison == -1,
        "is_equal":         comparison == 0,
        "channel":          channel,
    }
