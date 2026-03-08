"""Abstract broker interface. All broker adapters implement this."""

from abc import ABC, abstractmethod

from src.execution.models import (
    AccountInfo,
    Order,
    OrderResult,
    OrderStatus,
    Position,
)


class BaseBroker(ABC):
    """Abstract base for broker adapters (paper, Tastytrade, Hyperliquid)."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection / login. No-op for paper broker."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection. No-op for paper broker."""
        ...

    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """Return current account summary and positions."""
        ...

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Return current positions."""
        ...

    @abstractmethod
    async def submit_order(self, order: Order) -> OrderResult:
        """Submit a single order. Returns order id and status."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True if cancelled."""
        ...

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get current status of an order."""
        ...
