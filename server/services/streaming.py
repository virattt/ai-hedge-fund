"""SSE streaming service for analyze runs.

Emits ``run.started``, per-agent ``agent.started`` / ``agent.completed``,
``run.done``, and ``error`` events via sse-starlette's EventSourceResponse.

F2.5: agent events are emitted in batch after the synchronous
``run_hedge_fund`` completes — truly live streaming is deferred to F3.
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

from ..db.models import Run, RunDecision, RunSignal
from ..schemas import AnalystSignal, Decision

# Repo's ``src/`` on sys.path — same shim as run_service.py.
_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from main import run_hedge_fund  # noqa: E402

from .progress_sink import reset_queue, set_queue  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlmodel import Session

    from ..schemas import AnalyzeRequest


async def stream_analyze_run(
    req: AnalyzeRequest,
    session: Session,
) -> AsyncGenerator[dict[str, str]]:
    """Yield SSE-shaped dicts: ``{"event": ..., "data": ...}``."""
    started_at = datetime.now(UTC)

    run = Run(
        kind="analyze",
        status="running",
        started_at=started_at,
        model_name=req.model_name,
        model_provider=req.model_provider,
        tickers=req.tickers,
        start_date=req.start_date or "",
        end_date=req.end_date or "",
        initial_cash=req.portfolio.cash,
        margin_requirement=req.portfolio.margin_requirement,
        selected_analysts=req.selected_analysts,
        show_reasoning=req.show_reasoning,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    run_id = run.id

    # --- run.started ---
    yield {
        "event": "run.started",
        "data": json.dumps({"run_id": run_id, "status": "running"}),
    }

    # --- emit synthetic agent.started for each expected agent ---
    agent_names = list(req.selected_analysts) + ["risk_management_agent", "portfolio_manager"]
    for name in agent_names:
        yield {
            "event": "agent.started",
            "data": json.dumps({"run_id": run_id, "agent": name, "status": "running"}),
        }

    portfolio_for_cli: dict[str, Any] = {
        "cash": req.portfolio.cash,
        "margin_requirement": req.portfolio.margin_requirement,
        "positions": {
            t: {
                "long": p.long,
                "short": p.short,
                "long_cost_basis": p.long_cost_basis,
                "short_cost_basis": p.short_cost_basis,
            }
            for t, p in req.portfolio.positions.items()
        },
        "realized_gains": req.portfolio.realized_gains,
    }

    # Set up the progress sink queue for this run
    event_q: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
    token = set_queue(event_q)

    t0 = time.monotonic()
    try:
        result = await asyncio.to_thread(
            run_hedge_fund,
            tickers=req.tickers,
            start_date=req.start_date,
            end_date=req.end_date,
            portfolio=portfolio_for_cli,
            show_reasoning=req.show_reasoning,
            selected_analysts=req.selected_analysts,
            model_name=req.model_name,
            model_provider=req.model_provider,
        )
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
    finally:
        reset_queue(token)

    # --- drain any events the callback handler deposited ---
    while True:
        try:
            evt = event_q.get_nowait()
            yield {
                "event": evt["event"],
                "data": json.dumps(evt["data"]),
            }
        except queue.Empty:
            break

    # --- emit synthetic agent.completed for each expected agent ---
    for name in agent_names:
        yield {
            "event": "agent.completed",
            "data": json.dumps({"run_id": run_id, "agent": name, "status": "done"}),
        }

    # --- persist decisions + signals (same as run_service.py) ---
    decisions_raw: dict = result.get("decisions") or {}
    analyst_signals_raw: dict = result.get("analyst_signals") or {}

    decisions: dict[str, dict] = {}
    for ticker, dec in decisions_raw.items():
        d = Decision(
            action=dec.get("action", "hold"),
            quantity=int(dec.get("quantity", 0)),
            confidence=float(dec.get("confidence", 0)),
            reasoning=dec.get("reasoning"),
        )
        decisions[ticker] = d.model_dump()
        session.add(
            RunDecision(
                run_id=run_id,
                ticker=ticker,
                action=d.action,
                quantity=d.quantity,
                confidence=d.confidence,
                reasoning=d.reasoning,
            )
        )

    for agent_name, per_ticker in analyst_signals_raw.items():
        for ticker, sig in (per_ticker or {}).items():
            signal = AnalystSignal(**_coerce_signal(sig))
            session.add(
                RunSignal(
                    run_id=run_id,
                    agent_name=agent_name,
                    ticker=ticker,
                    signal=signal.signal,
                    confidence=signal.confidence,
                    reasoning=(
                        signal.reasoning
                        if isinstance(signal.reasoning, dict)
                        else ({"text": signal.reasoning} if signal.reasoning is not None else None)
                    ),
                )
            )

    run.status = "done"
    run.completed_at = datetime.now(UTC)
    run.duration_ms = int((time.monotonic() - t0) * 1000)
    session.add(run)
    session.commit()

    # --- run.done ---
    yield {
        "event": "run.done",
        "data": json.dumps({"run_id": run_id, "status": "done", "decisions": decisions}),
    }


def _coerce_signal(sig: dict) -> dict:
    """Normalize agent output shapes into AnalystSignal kwargs."""
    return {
        "signal": sig.get("signal"),
        "confidence": sig.get("confidence"),
        "reasoning": sig.get("reasoning"),
        "remaining_position_limit": sig.get("remaining_position_limit"),
        "current_price": sig.get("current_price"),
    }
