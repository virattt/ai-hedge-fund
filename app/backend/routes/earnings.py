"""Earnings Sentiment routes — transcript analysis and conviction scoring."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.database import get_db
from app.backend.models.earnings_schemas import (
    ConvictionRequest,
    ConvictionResponse,
    EarningsAnalysisRequest,
    EarningsAnalysisResponse,
)
from app.backend.services.api_key_service import ApiKeyService
from app.backend.services.earnings_service import EarningsFetchError, EarningsLLMError, get_conviction_signals, get_earnings_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insider/earnings", tags=["earnings"])


@router.post("/analysis", response_model=EarningsAnalysisResponse)
async def earnings_analysis_endpoint(
    request: EarningsAnalysisRequest,
    db: Session = Depends(get_db),
) -> EarningsAnalysisResponse:
    ticker = request.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")
    try:
        api_keys = ApiKeyService(db).get_api_keys_dict()
        return await get_earnings_analysis(ticker, request.model_name, request.model_provider, api_keys)
    except EarningsFetchError as exc:
        logger.error("Earnings fetch failed for %s: %s", ticker, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except EarningsLLMError as exc:
        logger.error("Earnings LLM error for %s: %s", ticker, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/conviction", response_model=ConvictionResponse)
async def conviction_endpoint(
    request: ConvictionRequest,
    db: Session = Depends(get_db),
) -> ConvictionResponse:
    ticker_list = [t.strip().upper() for t in request.tickers if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="At least one ticker is required")
    try:
        api_keys = ApiKeyService(db).get_api_keys_dict()
        return await get_conviction_signals(ticker_list, request.model_name, request.model_provider, api_keys)
    except (EarningsFetchError, EarningsLLMError) as exc:
        logger.error("Conviction analysis failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
