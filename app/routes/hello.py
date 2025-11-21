from fastapi import APIRouter

router = APIRouter(tags=["System"])


@router.get("/api/hello")
async def hello():
    return {"message": "FilamentHub läuft!"}
