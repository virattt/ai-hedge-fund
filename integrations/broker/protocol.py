"""Broker protocol — the interface all brokers must satisfy.

Mirrors the v2 DataClient pattern: structural typing via Protocol, no inheritance
required. Any class implementing these methods can be used as a broker.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from integrations.broker.models import (
    AccountSnapshot,
    MarketClock,
    OrderResult,
    OrderStatus,
    Position,
    TradeOrder,
)


@runtime_checkable
class BrokerClient(Protocol):
    """Contract for account state and order execution.

    Implementations:
    - NoOpBroker: logs orders, never submits (default, safe)
    - AlpacaBroker: Alpaca paper or live account
    """

    @property
    def name(self) -> str: ...

    def get_account(self) -> AccountSnapshot: ...

    def get_positions(self) -> list[Position]: ...

    def get_open_orders(self) -> list[OrderStatus]: ...

    def is_market_open(self) -> bool: ...

    def submit_order(self, order: TradeOrder) -> OrderResult: ...

    def cancel_all_orders(self) -> None: ...
