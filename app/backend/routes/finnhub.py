"""Short interest routes (yfinance-backed) for short interest and squeeze screener."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.backend.models.finnhub_schemas import ShortInterestResponse, SqueezeScreenerResponse
from app.backend.services.finnhub_service import ShortInterestFetchError, get_short_interest, get_squeeze_candidates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insider/finnhub", tags=["finnhub"])


@router.get("/short-interest", response_model=ShortInterestResponse)
async def short_interest_endpoint(
    symbol: str = Query(..., description="Ticker symbol (e.g. AAPL)"),
) -> ShortInterestResponse:
    """Fetch short interest metrics for a single ticker via yfinance."""
    try:
        return await get_short_interest(symbol.upper())
    except ShortInterestFetchError as exc:
        logger.error("Short interest fetch failed for %s: %s", symbol, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/squeeze", response_model=SqueezeScreenerResponse)
async def squeeze_screener_endpoint() -> SqueezeScreenerResponse:
    """Cross-reference insider buys with yfinance short interest data."""
    try:
        return await get_squeeze_candidates()
    except ShortInterestFetchError as exc:
        logger.error("Squeeze screener failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
