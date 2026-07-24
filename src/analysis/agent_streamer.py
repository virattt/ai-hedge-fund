"""Stream LangGraph progress as Server-Sent Events.

Hooks into `src.utils.progress.progress.register_handler` to intercept every
agent status update emitted while `run_hedge_fund` runs. Pushes those to an
asyncio queue from a background thread (run_hedge_fund is synchronous), then
the FastAPI endpoint drains the queue and yields SSE-formatted events.

Event shapes (all JSON):
    {"type": "start", "ticker": "NVDA", "estimated_agents": 14}
    {"type": "agent_update", "agent_id": "warren_buffett_agent",
     "agent_name": "Warren Buffett", "status": "Analyzing", "ticker": "NVDA",
     "elapsed": 12.4}
    {"type": "agent_done", ...}    # status == "done"
    {"type": "agent_error", ...}   # status == "error"
    {"type": "done", "elapsed": 41.2}
    {"type": "error", "message": "..."}
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import threading
import time
from datetime import datetime, timedelta
from typing import AsyncIterator

from src.utils.progress import progress as global_progress

# Reuse the pretty-name table from agent_runner
from src.analysis.agent_runner import _PRETTY_AGENT_NAMES


def _portfolio_for(ticker: str) -> dict:
    return {
        "cash": 100_000.0,
        "margin_requirement": 0.0,
        "margin_used": 0.0,
        "positions": {
            ticker: {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
        },
        "realized_gains": {ticker: {"long": 0.0, "short": 0.0}},
    }


async def stream_agent_run(
    ticker: str,
    *,
    model_name: str = "claude-opus-4-7",
    model_provider: str = "Anthropic",
    selected_analysts: list[str] | None = None,
    days_back: int = 180,
) -> AsyncIterator[dict]:
    """Yield progress events from a running LangGraph pipeline.

    The pipeline runs in a background thread; the main asyncio loop pulls
    events from a queue and yields them. The caller wraps each dict in
    `data: {json}\\n\\n` for SSE.
    """
    from src.main import run_hedge_fund

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    started = time.perf_counter()

    def push(event: dict) -> None:
        # Safe from any thread
        try:
            loop.call_soon_threadsafe(queue.put_nowait, event)
        except RuntimeError:
            pass  # loop may have closed early

    seen_done: set[str] = set()

    def on_progress(agent_name: str, ticker_: str | None, status: str, analysis: str | None, timestamp: str) -> None:
        s_lower = (status or "").lower()
        if s_lower == "done":
            if agent_name in seen_done:
                return
            seen_done.add(agent_name)
            event_type = "agent_done"
        elif s_lower == "error":
            event_type = "agent_error"
        else:
            event_type = "agent_update"

        push(
            {
                "type": event_type,
                "agent_id": agent_name,
                "agent_name": _PRETTY_AGENT_NAMES.get(
                    agent_name,
                    agent_name.replace("_agent", "").replace("_", " ").title(),
                ),
                "ticker": ticker_,
                "status": status,
                "elapsed": round(time.perf_counter() - started, 2),
            }
        )

    global_progress.register_handler(on_progress)

    def runner() -> None:
        end = datetime.now()
        start = end - timedelta(days=days_back)
        captured = io.StringIO()
        try:
            with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                run_hedge_fund(
                    tickers=[ticker],
                    start_date=start.strftime("%Y-%m-%d"),
                    end_date=end.strftime("%Y-%m-%d"),
                    portfolio=_portfolio_for(ticker),
                    show_reasoning=False,
                    selected_analysts=selected_analysts or [],
                    model_name=model_name,
                    model_provider=model_provider,
                )
            push({"type": "done", "elapsed": round(time.perf_counter() - started, 2)})
        except Exception as exc:
            push(
                {
                    "type": "error",
                    "message": f"{type(exc).__name__}: {exc}",
                    "elapsed": round(time.perf_counter() - started, 2),
                }
            )

    threading.Thread(target=runner, daemon=True).start()

    # Initial event so the UI can render the agent grid immediately
    yield {
        "type": "start",
        "ticker": ticker,
        "estimated_agents": 14,
        "estimated_seconds": 45,
    }

    try:
        while True:
            event = await queue.get()
            yield event
            if event.get("type") in ("done", "error"):
                break
    finally:
        global_progress.unregister_handler(on_progress)
