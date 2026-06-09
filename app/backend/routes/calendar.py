"""Earnings calendar route."""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.backend.models.calendar_schemas import EarningsCalendarResponse
from app.backend.services.earnings_calendar_service import get_calendar

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _default_range() -> tuple[str, str]:
    today = date.today()
    return today.isoformat(), (today + timedelta(days=14)).isoformat()


@router.get("/earnings", response_model=EarningsCalendarResponse)
async def calendar_endpoint(
    date_from: str | None = Query(None, description="ISO date YYYY-MM-DD; default = today"),
    date_to: str | None = Query(None, description="ISO date YYYY-MM-DD; default = today + 14d"),
) -> EarningsCalendarResponse:
    if not date_from or not date_to:
        df, dt = _default_range()
        date_from = date_from or df
        date_to = date_to or dt
    try:
        return await get_calendar(date_from, date_to)
    except Exception as exc:
        logger.exception("Calendar fetch failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
