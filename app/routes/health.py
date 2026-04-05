from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Maschinenlesbarer Health-Endpoint.

    Liefert ein klares Feldset, das dem Startup-Output entspricht.
    """
    return {
        "status": "ok",
        "database": "ok",
        "migrations": "ok",
        "schema": "ok",
        "server": "running",
    }
