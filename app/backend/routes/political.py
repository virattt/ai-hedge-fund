"""Political & Policy routes — government contracts and congressional trades."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.backend.models.political_schemas import CongressTradesResponse, GovContractsResponse
from app.backend.services.political_service import PoliticalFetchError, get_congress_trades, get_gov_contracts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insider/political", tags=["political"])


@router.get("/contracts", response_model=GovContractsResponse)
async def gov_contracts_endpoint(
    companies: str = Query(..., description="Comma-separated company names (e.g. Lockheed Martin,Raytheon)"),
) -> GovContractsResponse:
    """Fetch government contract awards from the USA Spending API."""
    company_list = [c.strip() for c in companies.split(",") if c.strip()]
    if not company_list:
        raise HTTPException(status_code=400, detail="At least one company name is required")
    try:
        return await get_gov_contracts(company_list)
    except PoliticalFetchError as exc:
        logger.error("Gov contracts fetch failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/congress", response_model=CongressTradesResponse)
async def congress_trades_endpoint(
    ticker: str | None = Query(None, description="Optional ticker filter (e.g. AAPL)"),
) -> CongressTradesResponse:
    """Fetch congressional stock trades from House Stock Watcher."""
    return await get_congress_trades(ticker)
