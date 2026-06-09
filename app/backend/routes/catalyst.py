"""Catalyst routes — surface SEC catalysts (Form 10/10-12B spin-offs)."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.backend.models.catalyst_schemas import SpinoffInsiderSummary, SpinoffListResponse
from app.backend.services.catalyst_service import (
    SpinoffFetchError,
    get_spinoff_filings,
    get_spinoff_insiders,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalysts", tags=["catalysts"])


@router.get("/spinoffs", response_model=SpinoffListResponse)
async def spinoffs_endpoint(
    date_from: str | None = Query(None, description="ISO date (YYYY-MM-DD), inclusive"),
    date_to: str | None = Query(None, description="ISO date (YYYY-MM-DD), inclusive"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=10000),
) -> SpinoffListResponse:
    try:
        return await get_spinoff_filings(date_from, date_to, limit, offset)
    except SpinoffFetchError as exc:
        logger.error("Spin-off fetch failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error in spinoffs endpoint")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/spinoffs/{cik}/insiders", response_model=SpinoffInsiderSummary)
async def spinoff_insiders_endpoint(cik: int) -> SpinoffInsiderSummary:
    if cik <= 0:
        raise HTTPException(status_code=400, detail="Invalid CIK")
    try:
        return await get_spinoff_insiders(cik)
    except Exception as exc:
        logger.exception("Failed to fetch insiders for CIK %s", cik)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
