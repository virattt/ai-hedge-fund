"""FastAPI routes for insider trading data.

Exposes four endpoints:
- GET /insider/summary  -- filing-level summaries for the dashboard table and cards
- GET /insider/detail   -- per-transaction drill-down for a specific SEC filing
- GET /insider/ownership -- per-insider ownership change history for the ownership sub-page
- GET /insider/grants   -- derivative trades (grants, exercises, conversions) sub-page

All endpoints validate the ``ticker`` query parameter against ``^[A-Z]{1,5}$``
using FastAPI's ``Query`` validator to prevent malformed values from reaching
the edgartools backend.
"""
import logging

from fastapi import APIRouter, HTTPException, Query

from app.backend.models.insider_schemas import GrantsResponse, InsiderDetailResponse, InsiderSummaryResponse, OwnershipChangesResponse
from app.backend.services.insider_service import get_insider_detail, get_insider_grants, get_insider_summary, get_ownership_changes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insider", tags=["insider"])


@router.get(
    "/summary",
    response_model=InsiderSummaryResponse,
    responses={
        422: {"description": "Invalid query parameters (e.g. ticker fails regex)"},
        500: {"description": "Internal server error"},
    },
)
async def insider_summary(
    ticker: str = Query(..., pattern=r"^[A-Z]{1,5}$", description="Stock ticker symbol (1-5 uppercase letters)"),
    form_type: str = Query("4", pattern=r"^[345]$", description="SEC form type: '3', '4', or '5'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of filings to process"),
    offset: int = Query(0, ge=0, le=10000, description="Number of filings to skip before processing"),
) -> InsiderSummaryResponse:
    """Return filing-level summaries for the insider trading dashboard.

    Each entry in ``filings`` corresponds to one SEC filing and includes
    ``accession_no`` as the stable filing identifier for follow-up detail
    requests. ``skipped_count`` reports how many filings failed to parse.
    """
    try:
        return await get_insider_summary(ticker=ticker, form_type=form_type, limit=limit, offset=offset)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch insider summary for ticker=%s form_type=%s", ticker, form_type)
        raise HTTPException(status_code=500, detail=f"Failed to fetch insider summary: {exc}") from exc


@router.get(
    "/detail",
    response_model=InsiderDetailResponse,
    responses={
        404: {"description": "Filing not found for given accession_no"},
        422: {"description": "Invalid query parameters (e.g. ticker fails regex)"},
        500: {"description": "Internal server error"},
    },
)
async def insider_detail(
    ticker: str = Query(..., pattern=r"^[A-Z]{1,5}$", description="Stock ticker symbol (1-5 uppercase letters)"),
    form_type: str = Query("4", pattern=r"^[345]$", description="SEC form type: '3', '4', or '5'"),
    accession_no: str = Query(..., description="SEC accession number (e.g. '0000320193-24-000081')"),
) -> InsiderDetailResponse:
    """Return per-transaction drill-down for a specific SEC filing.

    ``accession_no`` is the stable SEC filing identifier returned by the
    summary endpoint. Raises 404 if no matching filing is found.
    """
    try:
        return await get_insider_detail(ticker=ticker, form_type=form_type, accession_no=accession_no)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to fetch insider detail for ticker=%s accession_no=%s", ticker, accession_no
        )
        raise HTTPException(status_code=500, detail=f"Failed to fetch insider detail: {exc}") from exc


@router.get(
    "/ownership",
    response_model=OwnershipChangesResponse,
    responses={
        422: {"description": "Invalid query parameters (e.g. ticker fails regex)"},
        500: {"description": "Internal server error"},
    },
)
async def insider_ownership(
    ticker: str = Query(..., pattern=r"^[A-Z]{1,5}$", description="Stock ticker symbol (1-5 uppercase letters)"),
    form_type: str = Query("4", pattern=r"^[345]$", description="SEC form type: '3', '4', or '5'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of filings to process"),
    offset: int = Query(0, ge=0, le=10000, description="Number of filings to skip before processing"),
) -> OwnershipChangesResponse:
    """Return per-insider ownership change history for the ownership sub-page.

    Records are ordered by filing_date ascending (oldest first) for chart rendering.
    The ``insiders`` list is sorted by activity count (most active first), top 10.
    ``skipped_count`` reports how many filings failed to parse.
    """
    try:
        return await get_ownership_changes(ticker=ticker, form_type=form_type, limit=limit, offset=offset)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch ownership changes for ticker=%s", ticker)
        raise HTTPException(status_code=500, detail=f"Failed to fetch ownership changes: {exc}") from exc


@router.get(
    "/grants",
    response_model=GrantsResponse,
    responses={
        422: {"description": "Invalid query parameters (e.g. ticker fails regex)"},
        500: {"description": "Internal server error"},
    },
)
async def insider_grants(
    ticker: str = Query(..., pattern=r"^[A-Z]{1,5}$", description="Stock ticker symbol (1-5 uppercase letters)"),
    form_type: str = Query("4", pattern=r"^[345]$", description="SEC form type: '3', '4', or '5'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of filings to process"),
    offset: int = Query(0, ge=0, le=10000, description="Number of filings to skip before processing"),
) -> GrantsResponse:
    """Return derivative trades (grants, exercises, conversions) for the grants sub-page.

    Each entry in ``records`` corresponds to one row from the derivative_trades
    DataFrame of a Form 4 filing. ``skipped_count`` reports how many filings
    failed to parse.
    """
    try:
        return await get_insider_grants(ticker=ticker, form_type=form_type, limit=limit, offset=offset)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch insider grants for ticker=%s", ticker)
        raise HTTPException(status_code=500, detail=f"Failed to fetch insider grants: {exc}") from exc
