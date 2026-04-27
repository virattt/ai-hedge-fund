"""Sync run execution: wraps ``run_hedge_fund`` and persists the result.

This is the F1 sync path. Streaming (F2) will live alongside in
``server/services/streaming.py``. Both call into the same compiled LangGraph
workflow that the CLI builds via ``create_workflow`` (`src/main.py:110`).

Reuse contract (per ADR-001 "reuse map"):
  - ``run_hedge_fund`` is called as-is, never re-implemented.
  - The CLI ``progress`` singleton at ``src/utils/progress.py:88`` is left
    untouched in F1; F2 will introduce a ContextVar-scoped sink for
    concurrent runs (B9 #2).
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

# Repo's ``src/`` on sys.path — same shim as ``server/api/reference.py``.
# Ruff E402 is suppressed below because the sys.path mutation must precede
# the bare-name imports that the CLI codebase uses.
_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from main import run_hedge_fund  # noqa: E402

from ..db.models import Run, RunDecision, RunSignal  # noqa: E402
from ..schemas import AnalystSignal, AnalyzeRequest, Decision, RunSummary  # noqa: E402

if TYPE_CHECKING:
    from sqlmodel import Session


async def execute_analyze_run(req: AnalyzeRequest, session: Session) -> RunSummary:
    """Execute one synchronous analyze run end-to-end and persist it."""
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

    portfolio_for_cli: dict = {
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

    t0 = time.monotonic()
    try:
        # The CLI function is synchronous and CPU/IO-bound (LangGraph + LLM
        # calls + blocking ``requests`` in tools/api.py). Run in a worker
        # thread so the FastAPI event loop stays responsive.
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
        session.refresh(run)
        return _to_summary(run, decisions={}, signals={}, config=req)

    decisions_raw: dict = result.get("decisions") or {}
    analyst_signals_raw: dict = result.get("analyst_signals") or {}

    # Persist decisions
    decisions: dict[str, Decision] = {}
    for ticker, dec in decisions_raw.items():
        d = Decision(
            action=dec.get("action", "hold"),
            quantity=int(dec.get("quantity", 0)),
            confidence=float(dec.get("confidence", 0)),
            reasoning=dec.get("reasoning"),
        )
        decisions[ticker] = d
        session.add(
            RunDecision(
                run_id=run.id,
                ticker=ticker,
                action=d.action,
                quantity=d.quantity,
                confidence=d.confidence,
                reasoning=d.reasoning,
            )
        )

    # Persist analyst signals
    signals: dict[str, dict[str, AnalystSignal]] = {}
    for agent_name, per_ticker in analyst_signals_raw.items():
        signals[agent_name] = {}
        for ticker, sig in (per_ticker or {}).items():
            signal = AnalystSignal(**_coerce_signal(sig))
            signals[agent_name][ticker] = signal
            session.add(
                RunSignal(
                    run_id=run.id,
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
    session.refresh(run)

    return _to_summary(run, decisions=decisions, signals=signals, config=req)


def _coerce_signal(sig: dict) -> dict:
    """Normalize the various agent output shapes into AnalystSignal kwargs."""
    return {
        "signal": sig.get("signal"),
        "confidence": sig.get("confidence"),
        "reasoning": sig.get("reasoning"),
        "remaining_position_limit": sig.get("remaining_position_limit"),
        "current_price": sig.get("current_price"),
    }


def _to_summary(
    run: Run,
    *,
    decisions: dict[str, Decision],
    signals: dict[str, dict[str, AnalystSignal]],
    config: AnalyzeRequest,
) -> RunSummary:
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
