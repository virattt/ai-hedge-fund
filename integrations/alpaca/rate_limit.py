"""Simple sliding-window rate limiter for market data API calls."""

from __future__ import annotations

import time
from collections import deque


class RateLimiter:
    """Allow at most `max_per_minute` events per rolling 60-second window."""

    def __init__(self, max_per_minute: int) -> None:
        self._max = max(1, max_per_minute)
        self._events: deque[float] = deque()

    def wait(self, cost: int = 1) -> None:
        cost = max(1, cost)
        while True:
            now = time.monotonic()
            self._prune(now)
            if len(self._events) + cost <= self._max:
                for _ in range(cost):
                    self._events.append(now)
                return
            sleep_for = 60.0 - (now - self._events[0]) + 0.05
            time.sleep(min(max(sleep_for, 0.1), 5.0))

    def _prune(self, now: float) -> None:
        while self._events and now - self._events[0] >= 60.0:
            self._events.popleft()

    @property
    def available(self) -> int:
        now = time.monotonic()
        self._prune(now)
        return max(0, self._max - len(self._events))
