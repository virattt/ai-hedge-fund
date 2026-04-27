"""Health and readiness probe.

Reports DB liveness and which LLM/data providers have keys configured. Resolves
A9 (key validation should be observable, not mid-run only).
"""

from __future__ import annotations

import os

from fastapi import APIRouter
from sqlalchemy import text

from .. import __version__
from ..db.session import engine
from ..schemas import HealthResponse

router = APIRouter()


_PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "google": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "financial_datasets": "FINANCIAL_DATASETS_API_KEY",
}


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    providers = {name: bool(os.environ.get(env)) for name, env in _PROVIDER_KEYS.items()}

    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - probe path
        db_ok = False

    return HealthResponse(version=__version__, providers_configured=providers, db_ok=db_ok)
