"""LangChain callback handler that emits SSE progress events.

This handler translates LangGraph chain lifecycle events into
``agent.started`` / ``agent.completed`` events via the progress sink queue.

Note: For F2.5 these events arrive in batch (after the synchronous
``run_hedge_fund`` completes) rather than truly live.  F3 will upgrade
to live streaming by injecting this handler into the LangGraph config.
"""

from __future__ import annotations

from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from .progress_sink import emit


class SSEProgressHandler(BaseCallbackHandler):
    """Emits ``agent.started`` and ``agent.completed`` into the progress sink."""

    def __init__(self, run_id: str) -> None:
        super().__init__()
        self.run_id = run_id

    def on_chain_start(
        self,
        serialized: dict[str, Any] | None,
        inputs: dict[str, Any] | Any,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        name = (serialized or {}).get("name", "unknown")
        emit(
            "agent.started",
            {"run_id": self.run_id, "agent": name, "status": "running"},
        )

    def on_chain_end(self, outputs: dict[str, Any] | Any, **kwargs: Any) -> None:  # noqa: ARG002
        emit(
            "agent.completed",
            {
                "run_id": self.run_id,
                "outputs": str(outputs)[:500],
            },
        )
