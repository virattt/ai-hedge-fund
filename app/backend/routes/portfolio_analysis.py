"""Portfolio analysis routes — async agent execution on holdings."""

import json
import threading
import logging
import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.backend.database import get_db
from app.backend.database.connection import SessionLocal
from app.backend.database.models import AnalysisJob, PortfolioAnalysisResult, Holding
from app.backend.models.analysis import (
    AnalyzeRequest,
    AnalysisJobResponse,
    AnalysisResultResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio")


def _run_analysis_job(
    job_id: int,
    holding_ids: list[int] | None,
    model_name: str,
    model_provider: str,
    analysis_mode: str,
):
    """Background thread that runs the agent pipeline."""
    from app.backend.portfolio.portfolio_agent_service import run_portfolio_analysis, ApiKeyMissingError
    from app.backend.portfolio.analysis_modes import AnalysisMode, TIER_AGENTS, ESTIMATED_TOKENS

    db = SessionLocal()
    start_time = time.time()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            return
        job.status = "running"
        db.commit()

        results = run_portfolio_analysis(
            db=db,
            holding_ids=holding_ids,
            model_name=model_name,
            model_provider=model_provider,
            analysis_mode=analysis_mode,
        )

        elapsed = time.time() - start_time

        # Compute token usage stats
        mode = AnalysisMode(analysis_mode) if analysis_mode in [m.value for m in AnalysisMode] else AnalysisMode.QUICK_SCAN
        tier_agents = TIER_AGENTS.get(mode, [])
        agent_count = len(tier_agents) if tier_agents else (18 if mode == AnalysisMode.DEEP_DIVE else 0)
        est_tokens_per_ticker = ESTIMATED_TOKENS.get(mode, 0)
        total_tickers_analyzed = len(results)

        job.status = "completed"
        job.completed_tickers = total_tickers_analyzed
        job.result_ids = json.dumps([r["id"] for r in results])
        job.analysis_mode = analysis_mode
        job.model_name = model_name
        job.agent_count = agent_count
        job.estimated_tokens = est_tokens_per_ticker * total_tickers_analyzed
        job.elapsed_seconds = round(elapsed, 1)
        db.commit()

    except ApiKeyMissingError as e:
        logger.error(f"Analysis job {job_id} failed — API key missing: {e}")
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = f"API_KEY_MISSING: {e}"
            job.elapsed_seconds = round(time.time() - start_time, 1)
            db.commit()

    except Exception as e:
        logger.error(f"Analysis job {job_id} failed: {e}")
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)[:1000]
            job.elapsed_seconds = round(time.time() - start_time, 1)
            db.commit()
    finally:
        db.close()


@router.post("/analyze", response_model=AnalysisJobResponse)
async def analyze_portfolio(data: AnalyzeRequest, db: Session = Depends(get_db)):
    """Start async portfolio analysis.

    Modes: quick_scan (default, zero tokens), standard (4 agents), deep_dive (all agents).
    """
    from app.backend.services.rate_limiter import check_analysis_allowed, record_analysis

    if data.holding_ids:
        total = len(data.holding_ids)
    else:
        total = db.query(Holding).count()

    allowed, reason = check_analysis_allowed(data.analysis_mode, ticker_count=total)
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    if total == 0:
        raise HTTPException(status_code=400, detail="No holdings to analyze")

    record_analysis(data.analysis_mode)

    job = AnalysisJob(
        status="pending",
        job_type="portfolio",
        total_tickers=total,
        completed_tickers=0,
        analysis_mode=data.analysis_mode,
        model_name=data.model_name,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    thread = threading.Thread(
        target=_run_analysis_job,
        args=(job.id, data.holding_ids, data.model_name, data.model_provider, data.analysis_mode),
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
        model_name=data.model_name,
        created_at=job.created_at,
    )


@router.get("/analyze/{job_id}", response_model=AnalysisJobResponse)
async def get_analysis_job(job_id: int, db: Session = Depends(get_db)):
    """Poll for analysis job status and results."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    results = None
    if job.status == "completed" and job.result_ids:
        result_ids = json.loads(job.result_ids)
        db_results = db.query(PortfolioAnalysisResult).filter(
            PortfolioAnalysisResult.id.in_(result_ids)
        ).all()
        results = [_to_response(r) for r in db_results]

    return AnalysisJobResponse(
        job_id=job.id,
        status=job.status,
        job_type=job.job_type,
        total_tickers=job.total_tickers,
        completed_tickers=job.completed_tickers,
        error_message=job.error_message,
        results=results,
        created_at=job.created_at,
        analysis_mode=job.analysis_mode,
        model_name=job.model_name,
        agent_count=job.agent_count,
        estimated_tokens=job.estimated_tokens,
        elapsed_seconds=job.elapsed_seconds,
    )


@router.get("/analysis/latest", response_model=list[AnalysisResultResponse])
async def get_latest_analysis(db: Session = Depends(get_db)):
    """Get the most recent analysis result for each holding."""
    from sqlalchemy import func

    # Subquery: max id per holding_id
    subq = (
        db.query(
            PortfolioAnalysisResult.holding_id,
            func.max(PortfolioAnalysisResult.id).label("max_id"),
        )
        .filter(PortfolioAnalysisResult.holding_id.isnot(None))
        .group_by(PortfolioAnalysisResult.holding_id)
        .subquery()
    )

    results = (
        db.query(PortfolioAnalysisResult)
        .join(subq, PortfolioAnalysisResult.id == subq.c.max_id)
        .all()
    )

    return [_to_response(r) for r in results]


@router.get("/analysis/limits")
async def get_analysis_limits():
    """Get current rate limit usage and availability."""
    from app.backend.services.rate_limiter import get_usage_stats
    return get_usage_stats()


def _to_response(r: PortfolioAnalysisResult) -> AnalysisResultResponse:
    price_estimate = None
    if r.price_estimate:
        try:
            price_estimate = json.loads(r.price_estimate)
        except (json.JSONDecodeError, TypeError):
            pass

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
        price_estimate=price_estimate,
        created_at=r.created_at,
    )
