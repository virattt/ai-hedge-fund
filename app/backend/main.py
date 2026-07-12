import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import logging

from app.backend.routes import api_router
from app.backend.database.connection import engine
from app.backend.database.models import Base

# Load .env from repo root (two levels up from this file)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Hedge Fund API",
    description="Backend API for AI Hedge Fund",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Initialize database tables
Base.metadata.create_all(bind=engine)

# CORS — allow configured origins, auto-detect Railway, or default to localhost
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "")
if not _allowed_origins:
    railway_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if railway_url:
        _allowed_origins = f"https://{railway_url}"
    else:
        _allowed_origins = "http://localhost:5173,http://127.0.0.1:5173"
origins = [o.strip() for o in _allowed_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Include API routes (these take priority over SPA catch-all)
app.include_router(api_router)

# Serve frontend static build in production
_static_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="static-assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(str(_static_dir / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve static file if it exists, otherwise fallback to index.html for SPA routing."""
        file_path = _static_dir / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_static_dir / "index.html"))


@app.on_event("startup")
async def startup_event():
    logger.info("AI Hedge Fund API starting up")
    db_url = os.environ.get("DATABASE_URL", "sqlite (local)")
    logger.info(f"Database: {'PostgreSQL' if 'postgresql' in db_url else 'SQLite'}")

    if not os.environ.get("RAILWAY_ENVIRONMENT"):
        try:
            from app.backend.services.ollama_service import ollama_service
            status = await ollama_service.check_ollama_status()
            if status.get("running"):
                logger.info(f"Ollama running at {status['server_url']}")
        except Exception:
            pass
