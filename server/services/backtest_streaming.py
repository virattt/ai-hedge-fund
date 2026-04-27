"""Streaming adapter for backtests (F3).

Subclasses ``Backtester`` to emit per-day SSE events without modifying
``src/backtester.py``.  Events are pushed onto a ``queue.SimpleQueue``
that the async SSE endpoint drains.
"""

from __future__ import annotations

import queue  # noqa: TC003 — used at runtime
import sys
from pathlib import Path
from typing import Any

# Ensure ``src/`` is importable.
_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from backtester import Backtester  # noqa: E402


class BacktesterStreamAdapter(Backtester):
    """Backtester that pushes ``day.completed`` events into a queue."""

    def __init__(
        self,
        *args: Any,
        event_queue: queue.SimpleQueue[dict[str, Any]],
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._event_queue = event_queue

    def execute_trade(
        self,
        ticker: str,
        action: str,
        quantity: float,
        current_price: float,
    ) -> int:
        result: int = super().execute_trade(ticker, action, quantity, current_price)
        self._event_queue.put_nowait(
            {
                "event": "day.completed",
                "data": {
                    "ticker": ticker,
                    "action": action,
                    "quantity": result,
                    "price": current_price,
                    "cash": self.portfolio["cash"],
                },
            }
        )
        return result
