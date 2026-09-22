from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import Settings, load_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or load_settings()
    app = FastAPI(
        title="Cluster Assurance Orchestrator API",
        version="0.1.0",
        description=(
            "Independent operational health assurance API for Nutanix-compatible "
            "lab validation and controlled assurance workflows."
        ),
    )
    app.state.settings = active_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
            "http://127.0.0.1:5175",
            "http://localhost:5175",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api/v1")
    static_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="console")
    return app


app = create_app()
