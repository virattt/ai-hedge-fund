"""Cycle health — structured events, a heartbeat file, optional failure webhook.

``run_cycle`` stays the pipeline. This package wraps a call to it so the CLI
paper path (and a future scheduler/daemon) can emit start/end/error events,
refresh a heartbeat file, and optionally POST a failure summary — without
rewriting the pipeline core.

Events always log. JSONL, the heartbeat file, and the webhook are opt-in
via env vars or CLI flags. Webhook failures are logged and never swallow
the original cycle exception.
"""

from hedge_fund.observability.observe import (
    CYCLE_END,
    CYCLE_ERROR,
    CYCLE_START,
    CycleObserver,
    observe_cycle,
)

__all__ = [
    "CYCLE_END",
    "CYCLE_ERROR",
    "CYCLE_START",
    "CycleObserver",
    "observe_cycle",
]
