from abc import ABC, abstractmethod
from typing import Any


class CacheInterface(ABC):
    """Abstract interface for cache implementations."""

    @abstractmethod
    def get_prices(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached price data if available."""
        pass

    @abstractmethod
    def set_prices(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache price data."""
        pass

    @abstractmethod
    def get_financial_metrics(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached financial metrics if available."""
        pass

    @abstractmethod
    def set_financial_metrics(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache financial metrics."""
        pass

    @abstractmethod
    def get_line_items(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached line items if available."""
        pass

    @abstractmethod
    def set_line_items(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache line items."""
        pass

    @abstractmethod
    def get_insider_trades(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached insider trades if available."""
        pass

    @abstractmethod
    def set_insider_trades(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache insider trades."""
        pass

    @abstractmethod
    def get_company_news(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached company news if available."""
        pass

    @abstractmethod
    def set_company_news(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache company news."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the cache connection if needed."""
        pass