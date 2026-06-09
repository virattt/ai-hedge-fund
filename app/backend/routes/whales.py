"""Whale-tracking routes: whale fund CRUD + per-ticker entry lookup."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.backend.database import get_db
from app.backend.models.whale_schemas import (
    TickerWhaleSummaryResponse,
    WhaleEntryResponse,
    WhaleFundAddRequest,
    WhaleFundCandidate,
    WhaleFundCandidatesResponse,
    WhaleFundListResponse,
    WhaleFundResponse,
    WhaleRefreshResponse,
)
from app.backend.services.whale_entry_service import (
    get_entries_for_ticker,
    get_ticker_summary,
    refresh_all,
    refresh_whale,
)
from app.backend.services.whale_service import (
    add_whale,
    find_candidates_by_name,
    list_whales,
    remove_whale,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whales", tags=["whales"])


def _to_fund_response(dto) -> WhaleFundResponse:
    return WhaleFundResponse(
        id=dto.id, cik=dto.cik, name=dto.name, notes=dto.notes, added_at=dto.added_at,
    )


@router.get("/funds", response_model=WhaleFundListResponse)
def list_funds(db: Session = Depends(get_db)) -> WhaleFundListResponse:
    items = list_whales(db)
    return WhaleFundListResponse(items=[_to_fund_response(i) for i in items], total=len(items))


@router.post("/funds", response_model=WhaleFundResponse)
def add_fund(req: WhaleFundAddRequest, db: Session = Depends(get_db)) -> WhaleFundResponse:
    try:
        dto = add_whale(db, req.cik, req.name, req.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_fund_response(dto)


@router.delete("/funds/{cik}", response_model=dict)
def delete_fund(cik: int, db: Session = Depends(get_db)) -> dict:
    if not remove_whale(db, cik):
        raise HTTPException(status_code=404, detail=f"CIK {cik} not in whale funds")
    return {"ok": True}


@router.get("/funds/search", response_model=WhaleFundCandidatesResponse)
def search_funds(q: str = Query(..., min_length=2), limit: int = 10, db: Session = Depends(get_db)) -> WhaleFundCandidatesResponse:
    """Fuzzy search the 13F filer universe for candidate whales to add."""
    pairs = find_candidates_by_name(db, q, limit=limit)
    return WhaleFundCandidatesResponse(
        candidates=[WhaleFundCandidate(cik=c, company=name) for c, name in pairs],
    )


@router.post("/refresh", response_model=WhaleRefreshResponse)
async def refresh_endpoint(force: bool = False) -> WhaleRefreshResponse:
    """Recompute whale entries for all funds. force=True bypasses the 7d cache."""
    try:
        refreshed = await refresh_all(force=force)
    except Exception as exc:
        logger.exception("Whale refresh failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return WhaleRefreshResponse(
        refreshed=refreshed,
        total_rows_written=sum(refreshed.values()),
    )


@router.post("/refresh/{cik}", response_model=WhaleRefreshResponse)
async def refresh_one_endpoint(cik: int, force: bool = False) -> WhaleRefreshResponse:
    try:
        written = await refresh_whale(cik, force=force)
    except Exception as exc:
        logger.exception("Whale refresh failed for CIK %d", cik)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return WhaleRefreshResponse(refreshed={cik: written}, total_rows_written=written)


def _to_entry_response(summary) -> WhaleEntryResponse:
    return WhaleEntryResponse(
        whale_cik=summary.whale_cik,
        whale_name=summary.whale_name,
        ticker=summary.ticker,
        entry_quarter_label=summary.entry_quarter_label,
        entry_period_start=summary.entry_period_start,
        entry_period_end=summary.entry_period_end,
        entry_vwap=summary.entry_vwap,
        entry_low=summary.entry_low,
        entry_high=summary.entry_high,
        share_count_at_entry=summary.share_count_at_entry,
        is_pre_lookback=summary.is_pre_lookback,
        computed_at=summary.computed_at,
    )


@router.get("/entries/{ticker}", response_model=TickerWhaleSummaryResponse)
async def ticker_summary_endpoint(ticker: str) -> TickerWhaleSummaryResponse:
    """Returns all whale entries for one ticker + current price + distance from best entry."""
    summary = await get_ticker_summary(ticker)
    return TickerWhaleSummaryResponse(
        ticker=summary.ticker,
        current_price=summary.current_price,
        best_entry_vwap=summary.best_entry_vwap,
        best_entry_whale_cik=summary.best_entry_whale_cik,
        best_entry_whale_name=summary.best_entry_whale_name,
        distance_from_best_entry_pct=summary.distance_from_best_entry_pct,
        whale_count=summary.whale_count,
        entries=[_to_entry_response(e) for e in summary.entries],
    )
