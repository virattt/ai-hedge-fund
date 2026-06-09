"""Discovery routes — aggregated ranked ticker ideas + history + movers."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.backend.models.discovery_schemas import (
    DiscoveryHistoryResponse,
    DiscoveryMoversResponse,
    DiscoveryResponse,
)
from app.backend.services.discovery_service import get_history, get_ideas, get_movers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/ideas", response_model=DiscoveryResponse)
async def ideas_endpoint(
    limit: int = Query(50, ge=1, le=200),
    max_above_whale_pct: float | None = Query(
        None,
        description="If set, filter out ideas trading more than this % above the best whale entry. 0 = off.",
    ),
    max_pe: float | None = Query(
        None,
        description="If set, filter out ideas with trailing P/E above this. 0 = off. None = unfiltered.",
    ),
    max_de: float | None = Query(
        None,
        description="If set, filter out ideas with debt/equity above this (zombie-company guard). 0 = off.",
    ),
) -> DiscoveryResponse:
    try:
        response = await get_ideas(limit)
    except Exception as exc:
        logger.exception("Discovery aggregation failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    needs_whale = max_above_whale_pct is not None and max_above_whale_pct > 0
    needs_pe = max_pe is not None and max_pe > 0
    needs_de = max_de is not None and max_de > 0

    if not (needs_whale or needs_pe or needs_de):
        return response

    metrics_by_ticker: dict[str, object] = {}
    if needs_pe or needs_de:
        from app.backend.services.fundamentals_service import get_company_metrics_batch
        ticker_keys = [i.ticker for i in response.ideas if i.is_ticker and i.ticker]
        if ticker_keys:
            metrics_by_ticker = await get_company_metrics_batch(ticker_keys)

    def _passes(idea) -> bool:
        if needs_whale:
            d = idea.distance_from_whale_entry_pct
            if d is not None and d > max_above_whale_pct:
                return False
        if needs_pe or needs_de:
            m = metrics_by_ticker.get(idea.ticker.upper()) if idea.is_ticker else None
            if m is not None:
                if needs_pe and m.trailing_pe is not None and m.trailing_pe > max_pe:
                    return False
                if needs_de:
                    dte = m.debt_to_equity
                    # yfinance returns debtToEquity as a percentage (50.0 = 0.5)
                    if dte is not None and dte > 5.0:
                        dte = dte / 100.0
                    if dte is not None and dte > max_de:
                        return False
        return True

    filtered = [idea for idea in response.ideas if _passes(idea)]
    return DiscoveryResponse(
        ideas=filtered,
        total=len(filtered),
        cached=response.cached,
        generated_at=response.generated_at,
    )


@router.get("/history/{ticker}", response_model=DiscoveryHistoryResponse)
def history_endpoint(
    ticker: str,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(200, ge=1, le=1000),
) -> DiscoveryHistoryResponse:
    return get_history(ticker, days=days, limit=limit)


@router.get("/movers", response_model=DiscoveryMoversResponse)
def movers_endpoint(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    min_abs_delta: float = Query(20.0, ge=0),
) -> DiscoveryMoversResponse:
    return get_movers(days=days, limit=limit, min_abs_delta=min_abs_delta)
