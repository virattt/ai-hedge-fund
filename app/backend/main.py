from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Explicitly load .env from the project root (two levels above app/backend/)
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path, override=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"Loading .env from: {_env_path} (exists={_env_path.exists()})")
logger.info(f"TENCENT_MAAS_API_KEY loaded: {bool(os.getenv('TENCENT_MAAS_API_KEY'))}")

from app.backend.routes import api_router
from app.backend.database.connection import engine, SessionLocal
from app.backend.database.models import Base
from app.backend.services.ollama_service import ollama_service
from app.backend.services.api_key_service import ApiKeyService

app = FastAPI(title="AI Hedge Fund API", description="Backend API for AI Hedge Fund", version="0.1.0")

# Initialize database tables (this is safe to run multiple times)
Base.metadata.create_all(bind=engine)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routes
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    """Startup event: sync .env API keys to DB, then check Ollama availability."""
    # Sync .env API key values into the database on first start
    try:
        db = SessionLocal()
        ApiKeyService(db).sync_env_to_db()
        db.close()
        logger.info("✓ API keys synced from .env to database")
    except Exception as e:
        logger.warning(f"Could not sync API keys from .env: {e}")

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
