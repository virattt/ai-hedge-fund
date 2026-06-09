"""Watchlist routes — CRUD + batch refresh."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.backend.database import get_db
from app.backend.models.watchlist_schemas import (
    BatchRunResponse,
    IsWatchedResponse,
    WatchlistAddRequest,
    WatchlistItemResponse,
    WatchlistListResponse,
    WatchlistNotesUpdateRequest,
)
from app.backend.services.watchlist_service import (
    add_ticker,
    is_watched,
    list_tickers_with_returns,
    refresh_one,
    remove_ticker,
    run_batch_analysis,
    update_notes,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("/", response_model=WatchlistListResponse)
async def list_endpoint(db: Session = Depends(get_db)) -> WatchlistListResponse:
    return await list_tickers_with_returns(db)


@router.post("/", response_model=WatchlistItemResponse)
def add_endpoint(req: WatchlistAddRequest, db: Session = Depends(get_db)) -> WatchlistItemResponse:
    try:
        return add_ticker(db, req.ticker, req.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{ticker}", response_model=dict)
def delete_endpoint(ticker: str, db: Session = Depends(get_db)) -> dict:
    if not remove_ticker(db, ticker):
        raise HTTPException(status_code=404, detail=f"{ticker} not in watchlist")
    return {"ok": True}


@router.put("/{ticker}/notes", response_model=WatchlistItemResponse)
def notes_endpoint(
    ticker: str,
    req: WatchlistNotesUpdateRequest,
    db: Session = Depends(get_db),
) -> WatchlistItemResponse:
    item = update_notes(db, ticker, req.notes)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{ticker} not in watchlist")
    return item


@router.get("/{ticker}/is-watched", response_model=IsWatchedResponse)
def is_watched_endpoint(ticker: str, db: Session = Depends(get_db)) -> IsWatchedResponse:
    return IsWatchedResponse(ticker=ticker.upper(), is_watched=is_watched(db, ticker))


@router.post("/batch/run", response_model=BatchRunResponse)
async def batch_run_endpoint() -> BatchRunResponse:
    try:
        return await run_batch_analysis()
    except Exception as exc:
        logger.exception("Watchlist batch failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{ticker}/refresh", response_model=WatchlistItemResponse)
async def refresh_endpoint(ticker: str) -> WatchlistItemResponse:
    try:
        return await refresh_one(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Refresh failed for %s", ticker)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
