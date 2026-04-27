"""FastAPI entry point for the ai-hedge-fund web service.

Run with: ``uvicorn server.main:app --reload`` from the repo root.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import backtests as backtests_api
from .api import health as health_api
from .api import reference as reference_api
from .api import runs as runs_api
from .api import tickers as tickers_api
from .auth.middleware import require_token
from .config import get_settings
from .db.session import init_db
from .log_config import configure_logging, get_logger


@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ARG001
    configure_logging()
    log = get_logger("server.startup")
    settings = get_settings()
    init_db()
    log.info(
        "server.started",
        version=__version__,
        cors_origins=settings.cors_origin_list,
        max_concurrent_runs=settings.max_concurrent_runs,
    )
    yield
    log.info("server.stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ai-hedge-fund",
        version=__version__,
        lifespan=_lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(health_api.router, prefix="/api", tags=["system"])
    app.include_router(reference_api.router, prefix="/api", tags=["reference"])
    app.include_router(
        runs_api.router,
        prefix="/api",
        tags=["runs"],
        dependencies=[Depends(require_token)],
    )
    app.include_router(
        backtests_api.router,
        prefix="/api",
        tags=["backtests"],
        dependencies=[Depends(require_token)],
    )
    app.include_router(tickers_api.router, prefix="/api", tags=["tickers"])

    return app


app = create_app()
