"""Backtest endpoints — F3.

``POST /api/backtests/stream`` runs a full backtest via SSE, emitting
``backtest.started``, ``day.completed`` (one per trade), and
``backtest.done`` events.

``GET /api/backtests`` lists past backtest runs.
"""

from __future__ import annotations

import asyncio
import json
import queue
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlmodel import col, select
from sse_starlette.sse import EventSourceResponse

from ..db.models import Run
from ..db.session import get_session
from ..schemas import BacktestRequest, RunListItem, RunListResponse

# Ensure ``src/`` is importable.
_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from main import run_hedge_fund  # noqa: E402

from ..services.backtest_streaming import BacktesterStreamAdapter  # noqa: E402

if TYPE_CHECKING:
    from sqlmodel import Session

router = APIRouter()


class BacktestListResponse(BaseModel):
    items: list[RunListItem] = []


@router.get("/backtests", response_model=RunListResponse)
def list_backtests(session: Session = Depends(get_session)) -> RunListResponse:
    stmt = select(Run).where(Run.kind == "backtest").order_by(col(Run.created_at).desc()).limit(20)
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


@router.post("/backtests/stream")
async def stream_backtest(
    req: BacktestRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> EventSourceResponse:
    """SSE streaming endpoint for backtests."""

    async def _event_generator():  # noqa: C901
        async for event in _run_backtest_stream(req, session):
            if await request.is_disconnected():
                break
            yield event

    return EventSourceResponse(_event_generator())


async def _run_backtest_stream(
    req: BacktestRequest,
    session: Session,
) -> Any:
    """Yield SSE-shaped dicts for a backtest run."""
    started_at = datetime.now(UTC)

    run = Run(
        kind="backtest",
        status="running",
        started_at=started_at,
        model_name=req.model_name,
        model_provider=req.model_provider,
        tickers=req.tickers,
        start_date=req.start_date,
        end_date=req.end_date,
        initial_cash=req.initial_cash,
        margin_requirement=req.margin_requirement,
        selected_analysts=req.selected_analysts,
        show_reasoning=False,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    run_id = run.id

    yield {
        "event": "backtest.started",
        "data": json.dumps({"run_id": run_id, "status": "running"}),
    }

    event_q: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()

    t0 = time.monotonic()
    try:
        backtester = BacktesterStreamAdapter(
            agent=run_hedge_fund,
            tickers=req.tickers,
            start_date=req.start_date,
            end_date=req.end_date,
            initial_capital=req.initial_cash,
            model_name=req.model_name,
            model_provider=req.model_provider,
            selected_analysts=req.selected_analysts,
            initial_margin_requirement=req.margin_requirement,
            event_queue=event_q,
        )
        await asyncio.to_thread(backtester.run_backtest)
    except Exception as exc:  # noqa: BLE001
        run.status = "error"
        run.completed_at = datetime.now(UTC)
        run.duration_ms = int((time.monotonic() - t0) * 1000)
        run.error_message = repr(exc)
        session.add(run)
        session.commit()
        yield {
            "event": "error",
            "data": json.dumps({"message": repr(exc), "retryable": False}),
        }
        return

    # Drain day events
    while True:
        try:
            evt = event_q.get_nowait()
            yield {
                "event": evt["event"],
                "data": json.dumps(evt["data"]),
            }
        except queue.Empty:
            break

    # Build final metrics from backtester state
    portfolio_values = backtester.portfolio_values
    final_value = portfolio_values[-1]["Portfolio Value"] if portfolio_values else req.initial_cash
    total_return_pct = ((final_value / req.initial_cash) - 1) * 100

    run.status = "done"
    run.completed_at = datetime.now(UTC)
    run.duration_ms = int((time.monotonic() - t0) * 1000)
    session.add(run)
    session.commit()

    yield {
        "event": "backtest.done",
        "data": json.dumps(
            {
                "run_id": run_id,
                "status": "done",
                "final_value": round(final_value, 2),
                "total_return_pct": round(total_return_pct, 2),
                "portfolio_values": [
                    {
                        "date": pv["Date"].strftime("%Y-%m-%d") if hasattr(pv["Date"], "strftime") else str(pv["Date"]),
                        "value": round(pv["Portfolio Value"], 2),
                    }
                    for pv in portfolio_values
                ],
            }
        ),
    }
