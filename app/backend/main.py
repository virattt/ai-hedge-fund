from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
import os

from app.backend.routes import api_router
from app.backend.services.ollama_service import ollama_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Hedge Fund API", description="Backend API for AI Hedge Fund", version="0.1.0")

# The database schema is owned by Alembic — migrations run on deploy via the
# service startCommand (`alembic upgrade head`) and locally via the one-time
# step documented in the README. We deliberately do NOT call
# Base.metadata.create_all here: it only ever creates missing tables (never
# ALTERs/drops), which would silently diverge from the migration history.

# Configure CORS. Local dev defaults are always allowed. Every other allowed
# origin must be listed explicitly in the comma-separated FRONTEND_URL env var
# (the Blueprint auto-wires this to the deployed frontend's host). We deliberately
# do NOT use a wildcard regex: allowing all *.onrender.com would let any other
# Render tenant make credentialed requests to this API.
default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _normalize_origin(origin: str) -> str:
    """Normalize an origin for the CORS allow-list.

    Render's `fromService` host property yields a scheme-less host (e.g.
    "my-app.onrender.com"), so prepend https:// when no scheme is present —
    mirroring the frontend's own handling in app/frontend/src/lib/api-base.ts.
    """
    origin = origin.strip().rstrip("/")
    if origin and "://" not in origin:
        origin = f"https://{origin}"
    return origin


extra_origins = [
    _normalize_origin(origin)
    for origin in os.environ.get("FRONTEND_URL", "").split(",")
    if origin.strip()
]
allow_origins = default_origins + extra_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routes
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    """Startup event to check Ollama availability."""
    try:
        logger.info("Checking Ollama availability...")
        status = await ollama_service.check_ollama_status()
        
        if status["installed"]:
            if status["running"]:
                logger.info(f"✓ Ollama is installed and running at {status['server_url']}")
                if status["available_models"]:
                    logger.info(f"✓ Available models: {', '.join(status['available_models'])}")
                else:
                    logger.info("ℹ No models are currently downloaded")
            else:
                logger.info("ℹ Ollama is installed but not running")
                logger.info("ℹ You can start it from the Settings page or manually with 'ollama serve'")
        else:
            logger.info("ℹ Ollama is not installed. Install it to use local models.")
            logger.info("ℹ Visit https://ollama.com to download and install Ollama")
            
    except Exception as e:
        logger.warning(f"Could not check Ollama status: {e}")
        logger.info("ℹ Ollama integration is available if you install it later")
