from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.database import init_db
from app.routes.hello import router as hello_router
from app.routes.materials import router as materials_router
from app.routes.spools import router as spools_router

app = FastAPI(
    title="FilamentHub",
    description="Filament Management System für Bambu, Klipper & Standalone",
    version="0.1.0",
)

templates = Jinja2Templates(directory="frontend/templates")


@app.on_event("startup")
def on_startup():
    init_db()


# Router registrieren
app.include_router(hello_router)
app.include_router(materials_router)
app.include_router(spools_router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "FilamentHub – Dashboard"},
    )
