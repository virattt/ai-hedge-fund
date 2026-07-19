"""Broker protocol — the interface all brokers implement.

Mirrors the DataClient pattern (v2/data/protocol.py): structural typing, no
inheritance required. SimBroker backs backtests; PaperBroker and a live
broker implement the same three methods later.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from v2.brokers.models import Fill, Order, Position


@runtime_checkable
class Broker(Protocol):
    """Protocol that all brokers must satisfy.

    Contract: place_order either fills the order COMPLETELY and returns a
    Fill, or raises — no partial fills, no silent drops. A silently dropped
    order would desync the fund's books from the broker's.

    Deliberately no equity() method: equity requires marking positions, and
    only the pipeline knows the point-in-time marks. The broker reports what
    it holds; the pipeline computes what it's worth.
    """

    def positions(self) -> dict[str, Position]:
        """Current holdings keyed by ticker. A copy; no zero-share rows."""
        ...

    def cash(self) -> float: ...

    def place_order(self, order: Order) -> Fill: ...
