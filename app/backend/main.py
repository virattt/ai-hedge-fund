from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio

from app.backend.routes import api_router
from app.backend.database.connection import engine
from app.backend.database.models import Base
from app.backend.services.ollama_service import ollama_service
from app.backend.services.scraping_scheduler import ScrapingScheduler
from app.backend.services.alert_service._scheduler import get_scheduler as get_alert_scheduler
from app.backend.services.watchlist_service._scheduler import get_scheduler as get_watchlist_scheduler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Silence noisy third-party loggers — these libs log expected misses at ERROR level:
#   - yfinance: 404s for delisted/invalid tickers (Finnhub squeeze data has many)
#   - edgar.core: per-filing parser warnings on legacy SEC documents
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

app = FastAPI(title="AI Hedge Fund API", description="Backend API for AI Hedge Fund", version="0.1.0")

# Scheduler instance (lifecycle managed via startup/shutdown events)
_scraping_scheduler = ScrapingScheduler()

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
async def startup_event() -> None:
    """Startup event to check Ollama availability and start the scraping scheduler."""
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

    # Start the scraping scheduler after Ollama check
    try:
        await _scraping_scheduler.start()
    except Exception as e:
        logger.error("Failed to start scraping scheduler: %s", e)

    # Start the alert scheduler
    try:
        await get_alert_scheduler().start()
    except Exception as e:
        logger.error("Failed to start alert scheduler: %s", e)

    # Start the watchlist batch scheduler
    try:
        await get_watchlist_scheduler().start()
    except Exception as e:
        logger.error("Failed to start watchlist scheduler: %s", e)

    # Sync 13F company list from edgartools in background (non-blocking)
    async def _bg_sync_companies() -> None:
        try:
            from app.backend.services.insider_service._thirteenf_companies import _sync_companies_to_db
            await asyncio.to_thread(_sync_companies_to_db)
        except Exception as exc:
            logger.warning("Background 13F company sync failed: %s", exc)

    asyncio.create_task(_bg_sync_companies())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Shutdown event to stop the scraping scheduler cleanly."""
    try:
        await _scraping_scheduler.stop()
    except Exception as e:
        logger.error("Error stopping scraping scheduler: %s", e)
    try:
        await get_alert_scheduler().stop()
    except Exception as e:
        logger.error("Error stopping alert scheduler: %s", e)
    try:
        await get_watchlist_scheduler().stop()
    except Exception as e:
        logger.error("Error stopping watchlist scheduler: %s", e)
