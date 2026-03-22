from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

from app.backend.routes import api_router
from app.backend.database.connection import engine, SessionLocal
from app.backend.database.models import Base
from app.backend.services.ollama_service import ollama_service
from app.backend.repositories.api_key_repository import ApiKeyRepository

# Load .env from project root (two levels up from app/backend/)
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API keys to seed from environment, with human-readable descriptions
_ENV_API_KEYS = {
    "FINANCIAL_DATASETS_API_KEY": "Financial Datasets (financialdatasets.ai)",
    "OPENAI_API_KEY":             "OpenAI",
    "ANTHROPIC_API_KEY":          "Anthropic",
    "DEEPSEEK_API_KEY":           "DeepSeek",
    "GROQ_API_KEY":               "Groq",
    "GOOGLE_API_KEY":             "Google Gemini",
    "XAI_API_KEY":                "xAI (Grok)",
    "GIGACHAT_API_KEY":           "GigaChat",
    "OPENROUTER_API_KEY":         "OpenRouter",
    "AZURE_OPENAI_API_KEY":       "Azure OpenAI",
}

app = FastAPI(title="AI Hedge Fund API", description="Backend API for AI Hedge Fund", version="0.1.0")

# Initialize database tables (this is safe to run multiple times)
Base.metadata.create_all(bind=engine)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all headers for SSE
)

# Include all routes
app.include_router(api_router)

def _seed_api_keys_from_env() -> None:
    """Seed API keys from environment variables into the database (only if not already present)."""
    db = SessionLocal()
    try:
        repo = ApiKeyRepository(db)
        seeded = []
        for env_var, description in _ENV_API_KEYS.items():
            value = os.getenv(env_var, "").strip()
            if not value or value.startswith("your-"):
                continue
            existing = repo.get_api_key_by_provider(env_var)
            if not existing:
                repo.create_or_update_api_key(
                    provider=env_var,
                    key_value=value,
                    description=description,
                )
                seeded.append(env_var)
        if seeded:
            logger.info(f"✓ Seeded API keys from environment: {', '.join(seeded)}")
        else:
            logger.debug("No new API keys to seed from environment")
    except Exception as e:
        logger.warning(f"Could not seed API keys from environment: {e}")
    finally:
        db.close()


@app.on_event("startup")
async def startup_event():
    """Startup event to seed API keys and check Ollama availability."""
    _seed_api_keys_from_env()

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
