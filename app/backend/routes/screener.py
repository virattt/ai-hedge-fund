"""FastAPI routes for finviz-style stock screener."""
import logging

from fastapi import APIRouter, HTTPException

from app.backend.models.screener_schemas import ScreenerFiltersResponse, ScreenerRequest, ScreenerResponse
from app.backend.services.screener_service import get_screener_filters, run_screener

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/screener", tags=["screener"])


@router.get(
    "/filters",
    response_model=ScreenerFiltersResponse,
    responses={500: {"description": "Internal server error"}},
)
async def screener_filters() -> ScreenerFiltersResponse:
    """Return all available screener filter names, options, signals, and sort orders."""
    try:
        data = await get_screener_filters()
        return ScreenerFiltersResponse(**data)
    except Exception as e:
        logger.exception("Failed to fetch screener filters")
        raise HTTPException(status_code=500, detail=f"Failed to fetch screener filters: {str(e)}") from e


@router.post(
    "/search",
    response_model=ScreenerResponse,
    responses={500: {"description": "Internal server error"}},
)
async def screener_search(request: ScreenerRequest) -> ScreenerResponse:
    """Run a screener query with the given filters and return table data."""
    try:
        data = await run_screener(
            filters_dict=request.filters,
            signal=request.signal,
            ticker=request.ticker,
            order=request.order,
            ascend=request.ascend,
            limit=request.limit,
            view=request.view,
        )
        return ScreenerResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to run screener")
        raise HTTPException(status_code=500, detail=f"Failed to run screener: {str(e)}") from e
