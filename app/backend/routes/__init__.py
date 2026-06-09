from fastapi import APIRouter

from app.backend.routes.hedge_fund import router as hedge_fund_router
from app.backend.routes.health import router as health_router
from app.backend.routes.storage import router as storage_router
from app.backend.routes.flows import router as flows_router
from app.backend.routes.flow_runs import router as flow_runs_router
from app.backend.routes.ollama import router as ollama_router
from app.backend.routes.language_models import router as language_models_router
from app.backend.routes.api_keys import router as api_keys_router
from app.backend.routes.scraping import router as scraping_router
from app.backend.routes.news import router as news_router
from app.backend.routes.screener import router as screener_router
from app.backend.routes.insider import router as insider_router
from app.backend.routes.openinsider import router as openinsider_router
from app.backend.routes.finnhub import router as finnhub_router
from app.backend.routes.political import router as political_router
from app.backend.routes.earnings import router as earnings_router
from app.backend.routes.settings import router as settings_router
from app.backend.routes.catalyst import router as catalyst_router
from app.backend.routes.alert import router as alert_router
from app.backend.routes.watchlist import router as watchlist_router
from app.backend.routes.calendar import router as calendar_router
from app.backend.routes.discovery import router as discovery_router
from app.backend.routes.whales import router as whales_router
from app.backend.routes.backtest import router as backtest_router
from app.backend.routes.cache import router as cache_router

# Main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health_router, tags=["health"])
api_router.include_router(hedge_fund_router, tags=["hedge-fund"])
api_router.include_router(storage_router, tags=["storage"])
api_router.include_router(flows_router, tags=["flows"])
api_router.include_router(flow_runs_router, tags=["flow-runs"])
api_router.include_router(ollama_router, tags=["ollama"])
api_router.include_router(language_models_router, tags=["language-models"])
api_router.include_router(api_keys_router, tags=["api-keys"])
api_router.include_router(scraping_router, tags=["scraping"])
api_router.include_router(news_router, tags=["news"])
api_router.include_router(screener_router, tags=["screener"])
api_router.include_router(insider_router, tags=["insider"])
api_router.include_router(openinsider_router, tags=["openinsider"])
api_router.include_router(finnhub_router, tags=["finnhub"])
api_router.include_router(political_router, tags=["political"])
api_router.include_router(earnings_router, tags=["earnings"])
api_router.include_router(settings_router, tags=["settings"])
api_router.include_router(catalyst_router, tags=["catalysts"])
api_router.include_router(alert_router, tags=["alerts"])
api_router.include_router(watchlist_router, tags=["watchlist"])
api_router.include_router(calendar_router, tags=["calendar"])
api_router.include_router(discovery_router, tags=["discovery"])
api_router.include_router(whales_router, tags=["whales"])
api_router.include_router(backtest_router, tags=["backtest"])
api_router.include_router(cache_router, tags=["cache"])
