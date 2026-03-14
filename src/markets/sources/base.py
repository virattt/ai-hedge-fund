"""Base class for data sources."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class DataSource(ABC):
    """Abstract base class for data sources."""

    def __init__(self, name: str):
        """
        Initialize data source.

        Args:
            name: Unique name for this data source
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @abstractmethod
    def get_prices(
        self, ticker: str, start_date: str, end_date: str
    ) -> List[Dict]:
        """
        Get price data for a ticker.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            List of price dictionaries with keys: open, close, high, low, volume, time
        """
        pass

    @abstractmethod
    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> Optional[Dict]:
        """
        Get financial metrics for a ticker.

        Args:
            ticker: Stock ticker symbol
            end_date: End date in YYYY-MM-DD format
            period: Period type (ttm, quarterly, annual)
            limit: Number of periods to fetch

        Returns:
            Dictionary with financial metrics or None if not available
        """
        pass

    @abstractmethod
    def get_company_news(
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Get company news for a ticker.

        Args:
            ticker: Stock ticker symbol
            end_date: End date in YYYY-MM-DD format
            start_date: Start date in YYYY-MM-DD format (optional)
            limit: Maximum number of news items

        Returns:
            List of news dictionaries with keys: title, date, source, url, sentiment
        """
        pass

    @abstractmethod
    def supports_market(self, market: str) -> bool:
        """
        Check if this data source supports a specific market.

        Args:
            market: Market identifier (e.g., 'CN', 'HK', 'US')

        Returns:
            True if market is supported
        """
        pass

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"

    def __repr__(self) -> str:
        return self.__str__()
