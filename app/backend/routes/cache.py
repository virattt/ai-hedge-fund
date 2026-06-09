"""Cache management — flush every in-memory cache across the platform."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.backend.services.cache_service import flush_all

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cache", tags=["cache"])


class FlushResponse(BaseModel):
    cleared: dict[str, int]
    total_entries: int


@router.post("/flush", response_model=FlushResponse)
def flush_endpoint() -> FlushResponse:
    cleared = flush_all()
    return FlushResponse(cleared=cleared, total_entries=sum(cleared.values()))
