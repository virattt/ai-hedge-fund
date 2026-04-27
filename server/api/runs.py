"""Analyze-run endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlmodel import Session, col, select
from sse_starlette.sse import EventSourceResponse

from ..db.models import Run, RunDecision, RunSignal
from ..db.session import get_session
from ..schemas import (
    AnalystSignal,
    AnalyzeRequest,
    Decision,
    Portfolio,
    PortfolioPosition,
    RunListItem,
    RunListResponse,
    RunSummary,
)
from ..services.run_service import execute_analyze_run
from ..services.streaming import stream_analyze_run

router = APIRouter()


@router.post("/runs", response_model=RunSummary, status_code=status.HTTP_201_CREATED)
async def create_run(req: AnalyzeRequest, session: Session = Depends(get_session)) -> RunSummary:
    """Synchronously execute an analyze run and return the full summary.

    F2 will add ``POST /runs/stream`` for SSE; this endpoint stays for
    scriptable / non-browser callers and as the parity target for the CLI
    ("±1% runtime" — F1 acceptance).
    """
    return await execute_analyze_run(req, session)


@router.post("/runs/stream")
async def stream_run(
    req: AnalyzeRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> EventSourceResponse:
    """SSE streaming endpoint for analyze runs.

    Emits ``run.started``, ``run.done``, and ``error`` events.
    """

    async def _event_generator():
        async for event in stream_analyze_run(req, session):
            if await request.is_disconnected():
                break
            yield event

    return EventSourceResponse(_event_generator())


@router.get("/runs", response_model=RunListResponse)
def list_runs(
    session: Session = Depends(get_session),
    limit: int = Query(20, ge=1, le=100),
    kind: str | None = Query(None, pattern="^(analyze|backtest)$"),
) -> RunListResponse:
    stmt = select(Run).order_by(col(Run.created_at).desc())
    if kind:
        stmt = stmt.where(Run.kind == kind)
    stmt = stmt.limit(limit)
    rows = session.exec(stmt).all()
    return RunListResponse(
        items=[
            RunListItem(
                id=r.id,
                status=r.status,  # type: ignore[arg-type]
                kind=r.kind,  # type: ignore[arg-type]
                started_at=r.started_at or r.created_at,
                completed_at=r.completed_at,
                duration_ms=r.duration_ms,
                tickers=r.tickers,
                model_name=r.model_name,
                model_provider=r.model_provider,
            )
            for r in rows
        ]
    )


@router.get("/runs/{run_id}", response_model=RunSummary)
def get_run(run_id: str, session: Session = Depends(get_session)) -> RunSummary:
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="run not found")

    decisions = {
        d.ticker: Decision(
            action=d.action,  # type: ignore[arg-type]
            quantity=d.quantity,
            confidence=d.confidence,
            reasoning=d.reasoning,
        )
        for d in session.exec(select(RunDecision).where(RunDecision.run_id == run_id)).all()
    }

    signals: dict[str, dict[str, AnalystSignal]] = {}
    for s in session.exec(select(RunSignal).where(RunSignal.run_id == run_id)).all():
        signals.setdefault(s.agent_name, {})[s.ticker] = AnalystSignal(
            signal=s.signal,  # type: ignore[arg-type]
            confidence=s.confidence,
            reasoning=s.reasoning,
        )

    config = AnalyzeRequest(
        tickers=run.tickers,
        start_date=run.start_date,
        end_date=run.end_date,
        portfolio=Portfolio(
            cash=run.initial_cash,
            margin_requirement=run.margin_requirement,
            positions={t: PortfolioPosition() for t in run.tickers},
        ),
        show_reasoning=run.show_reasoning,
        selected_analysts=run.selected_analysts,
        model_name=run.model_name,
        model_provider=run.model_provider,
    )

    return RunSummary(
        id=run.id,
        status=run.status,  # type: ignore[arg-type]
        started_at=run.started_at or run.created_at,
        completed_at=run.completed_at,
        duration_ms=run.duration_ms,
        error_message=run.error_message,
        cost_usd=run.cost_usd,
        config=config,
        decisions=decisions,
        analyst_signals=signals,
    )
