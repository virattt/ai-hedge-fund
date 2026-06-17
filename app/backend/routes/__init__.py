from fastapi import APIRouter, Depends

from app.backend.routes.hedge_fund import router as hedge_fund_router
from app.backend.routes.health import router as health_router
from app.backend.routes.storage import router as storage_router
from app.backend.routes.flows import router as flows_router
from app.backend.routes.flow_runs import router as flow_runs_router
from app.backend.routes.ollama import router as ollama_router
from app.backend.routes.language_models import router as language_models_router
from app.backend.routes.api_keys import router as api_keys_router
from app.backend.routes.holdings import router as holdings_router
from app.backend.routes.dashboard import router as dashboard_router
from app.backend.routes.accounts import router as accounts_router
from app.backend.routes.export import router as export_router
from app.backend.routes.portfolio_analysis import router as portfolio_analysis_router
from app.backend.routes.watchlist import router as watchlist_router
from app.backend.services.auth_service import verify_api_key

# Main API router
api_router = APIRouter()

# Public routes (no auth required)
api_router.include_router(health_router, tags=["health"])

# Protected routes (auth required when APP_PASSWORD_HASH is set)
_auth = [Depends(verify_api_key)]
api_router.include_router(hedge_fund_router, tags=["hedge-fund"], dependencies=_auth)
api_router.include_router(storage_router, tags=["storage"], dependencies=_auth)
api_router.include_router(flows_router, tags=["flows"], dependencies=_auth)
api_router.include_router(flow_runs_router, tags=["flow-runs"], dependencies=_auth)
api_router.include_router(ollama_router, tags=["ollama"], dependencies=_auth)
api_router.include_router(language_models_router, tags=["language-models"], dependencies=_auth)
api_router.include_router(api_keys_router, tags=["api-keys"], dependencies=_auth)
api_router.include_router(holdings_router, tags=["holdings"], dependencies=_auth)
api_router.include_router(dashboard_router, tags=["dashboard"], dependencies=_auth)
api_router.include_router(accounts_router, tags=["accounts"], dependencies=_auth)
api_router.include_router(export_router, tags=["export"], dependencies=_auth)
api_router.include_router(portfolio_analysis_router, tags=["portfolio-analysis"], dependencies=_auth)
api_router.include_router(watchlist_router, tags=["watchlist"], dependencies=_auth)
