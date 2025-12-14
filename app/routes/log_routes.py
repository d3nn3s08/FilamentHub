from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/logs", tags=["Logs"])


def _deprecated_response():
    return JSONResponse({"deprecated": True, "use": "/api/debug/logs"}, status_code=410)


@router.get("/modules")
def get_modules():
    return _deprecated_response()


@router.get("/today")
def get_today_log():
    return _deprecated_response()


@router.get("/date/{date}")
def get_log_by_date(date: str):
    return _deprecated_response()


@router.get("/errors/latest")
def latest_error():
    return _deprecated_response()
