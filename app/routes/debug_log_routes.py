from fastapi import APIRouter, HTTPException, Query, Request
from app.services import log_reader


router = APIRouter(prefix="/api/debug", tags=["Debug Logs"])

DEFAULT_LIMIT = 200
MAX_LIMIT = log_reader.MAX_LIMIT


def _is_admin(request: Request | None) -> bool:
    """
    Leichte Admin-Prüfung: nutzt das bestehende admin_token-Cookie,
    um Admin-Logs nur für authentifizierte Nutzer freizugeben.
    """
    if request is None:
        return False
    try:
        from app.routes.admin_routes import admin_tokens  # type: ignore
    except Exception:
        return False
    token = request.cookies.get("admin_token")
    return bool(token and token in admin_tokens)


@router.get("/logs")
async def debug_logs(
    request: Request,
    module: str = Query("app"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    level: str | None = Query(None, description="off/basic/verbose filter, optional"),
    search: str | None = Query(None, description="Freitext-Suche, optional"),
):
    try:
        allow_admin = _is_admin(request)
        result = log_reader.read_logs(
            module=module,
            limit=limit,
            offset=offset,
            level=level,
            search=search,
            allow_admin=allow_admin,
        )
        return result
    except log_reader.LogAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
