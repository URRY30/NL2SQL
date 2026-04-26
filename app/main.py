from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import router
from app.core.config import PROJECT_ROOT, get_settings
from app.core.responses import ok
from app.db import engine


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.mount("/ui", StaticFiles(directory=PROJECT_ROOT / "web", html=True), name="ui")


@app.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/")


@app.get("/api")
async def api_root() -> dict:
    return ok({"service": settings.app_name, "status": "ok"})
