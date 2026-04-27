"""ContextVar-scoped event queue for per-agent progress events.

Used by F2.5 to shuttle ``agent.started`` / ``agent.completed`` events from
the worker thread (where ``run_hedge_fund`` executes) to the async SSE
generator.

F3 will upgrade to truly live streaming; for now events are batched after
the synchronous run completes.
"""

from __future__ import annotations

import contextvars
import queue  # noqa: TC003 — used at runtime for queue.SimpleQueue()
from typing import Any

_event_queue: contextvars.ContextVar[queue.SimpleQueue[dict[str, Any]] | None] = contextvars.ContextVar(
    "_event_queue", default=None
)


def get_queue() -> queue.SimpleQueue[dict[str, Any]] | None:
    """Return the queue bound to the current context, or *None*."""
    return _event_queue.get()


def set_queue(q: queue.SimpleQueue[dict[str, Any]]) -> contextvars.Token[queue.SimpleQueue[dict[str, Any]] | None]:
    """Bind *q* to the current context.  Returns a reset token."""
    return _event_queue.set(q)


def reset_queue(token: contextvars.Token[queue.SimpleQueue[dict[str, Any]] | None]) -> None:
    """Restore the previous queue value."""
    _event_queue.reset(token)


def emit(event_type: str, data: dict[str, Any]) -> None:
    """Push an event onto the queue.  Safe to call from any thread."""
    q = _event_queue.get()
    if q is not None:
        q.put_nowait({"event": event_type, "data": data})
