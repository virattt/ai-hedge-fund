"""Watchlist routes — add/remove tickers and run analysis."""

import json
import threading
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.database import get_db
from app.backend.database.connection import SessionLocal
from app.backend.database.models import AnalysisJob, PortfolioAnalysisResult, Watchlist
from app.backend.repositories.watchlist_repository import WatchlistRepository
from app.backend.models.watchlist import WatchlistCreate, WatchlistResponse
from app.backend.models.analysis import (
    WatchlistAnalyzeRequest,
    AnalysisJobResponse,
    AnalysisResultResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/watchlist")


@router.get("", response_model=list[WatchlistResponse])
async def list_watchlist(db: Session = Depends(get_db)):
    repo = WatchlistRepository(db)
    items = repo.get_all()
    return [WatchlistResponse.model_validate(i) for i in items]


@router.post("", response_model=WatchlistResponse, status_code=201)
async def add_to_watchlist(data: WatchlistCreate, db: Session = Depends(get_db)):
    repo = WatchlistRepository(db)
    item = repo.create(ticker=data.ticker, investment_name=data.investment_name, notes=data.notes)
    return WatchlistResponse.model_validate(item)


@router.delete("/{item_id}", status_code=204)
async def remove_from_watchlist(item_id: int, db: Session = Depends(get_db)):
    repo = WatchlistRepository(db)
    deleted = repo.delete(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Watchlist item not found")


def _run_watchlist_analysis_job(
    job_id: int,
    watchlist_ids: list[int] | None,
    model_name: str,
    model_provider: str,
    analysis_mode: str = "quick_scan",
):
    """Background thread for watchlist analysis."""
    import time
    from app.backend.portfolio.portfolio_agent_service import run_portfolio_analysis

    db = SessionLocal()
    start_time = time.time()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            return
        job.status = "running"
        db.commit()

        if not watchlist_ids:
            all_items = db.query(Watchlist).all()
            watchlist_ids = [w.id for w in all_items]

        results = run_portfolio_analysis(
            db=db,
            watchlist_ids=watchlist_ids,
            model_name=model_name,
            model_provider=model_provider,
            analysis_mode=analysis_mode,
        )

        job.status = "completed"
        job.completed_tickers = len(results)
        job.result_ids = json.dumps([r["id"] for r in results])
        job.elapsed_seconds = round(time.time() - start_time, 1)
        db.commit()

    except Exception as e:
        logger.error(f"Watchlist analysis job {job_id} failed: {e}")
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)[:1000]
            job.elapsed_seconds = round(time.time() - start_time, 1)
            db.commit()
    finally:
        db.close()


@router.post("/analyze", response_model=AnalysisJobResponse)
async def analyze_watchlist(data: WatchlistAnalyzeRequest, db: Session = Depends(get_db)):
    """Start async watchlist analysis using all hedge-fund agents."""
    from app.backend.services.rate_limiter import check_analysis_allowed, record_analysis

    allowed, reason = check_analysis_allowed(data.analysis_mode)
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    if data.watchlist_ids:
        total = len(data.watchlist_ids)
    else:
        total = db.query(Watchlist).count()

    if total == 0:
        raise HTTPException(status_code=400, detail="No watchlist items to analyze")

    record_analysis(data.analysis_mode)

    job = AnalysisJob(
        status="pending",
        job_type="watchlist",
        total_tickers=total,
        completed_tickers=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    thread = threading.Thread(
        target=_run_watchlist_analysis_job,
        args=(job.id, data.watchlist_ids, data.model_name, data.model_provider, data.analysis_mode),
        daemon=True,
    )
    thread.start()

    return AnalysisJobResponse(
        job_id=job.id,
        status=job.status,
        job_type=job.job_type,
        total_tickers=job.total_tickers,
        completed_tickers=0,
        analysis_mode=data.analysis_mode,
        created_at=job.created_at,
    )


@router.get("/analysis/latest", response_model=list[AnalysisResultResponse])
async def get_latest_watchlist_analysis(db: Session = Depends(get_db)):
    """Get the most recent analysis result for each watchlist item."""
    from sqlalchemy import func

    subq = (
        db.query(
            PortfolioAnalysisResult.watchlist_id,
            func.max(PortfolioAnalysisResult.id).label("max_id"),
        )
        .filter(PortfolioAnalysisResult.watchlist_id.isnot(None))
        .group_by(PortfolioAnalysisResult.watchlist_id)
        .subquery()
    )

    results = (
        db.query(PortfolioAnalysisResult)
        .join(subq, PortfolioAnalysisResult.id == subq.c.max_id)
        .all()
    )

    return [_to_response(r) for r in results]


def _to_response(r: PortfolioAnalysisResult) -> AnalysisResultResponse:
    return AnalysisResultResponse(
        id=r.id,
        holding_id=r.holding_id,
        watchlist_id=r.watchlist_id,
        ticker=r.ticker,
        analysis_ticker=r.analysis_ticker,
        final_action=r.final_action,
        confidence=r.confidence,
        technical_summary=r.technical_summary,
        fundamental_summary=r.fundamental_summary,
        sentiment_summary=r.sentiment_summary,
        valuation_summary=r.valuation_summary,
        risk_summary=r.risk_summary,
        portfolio_manager_summary=r.portfolio_manager_summary,
        positive_factors=json.loads(r.positive_factors) if r.positive_factors else [],
        risk_factors=json.loads(r.risk_factors) if r.risk_factors else [],
        uncertainties=json.loads(r.uncertainties) if r.uncertainties else [],
        created_at=r.created_at,
    )
