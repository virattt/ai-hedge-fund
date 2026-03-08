"""Abstract base class for data providers."""

from abc import ABC, abstractmethod

from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    InsiderTrade,
    LineItem,
    Price,
)


class DataProvider(ABC):
    """Abstract base for financial data providers. All implementations normalize to shared Pydantic models."""

    @property
    def name(self) -> str:
        """Provider identifier for logging and fallback chain."""
        return self.__class__.__name__

    @abstractmethod
    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        **kwargs: object,
    ) -> list[Price]:
        """Fetch OHLCV price data. Returns empty list on failure or no data."""
        ...

    @abstractmethod
    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        **kwargs: object,
    ) -> list[FinancialMetrics]:
        """Fetch financial metrics (ratios, margins, growth). Returns empty list on failure."""
        ...

    @abstractmethod
    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        **kwargs: object,
    ) -> list[CompanyNews]:
        """Fetch company news. Returns empty list on failure."""
        ...

    @abstractmethod
    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        **kwargs: object,
    ) -> list[InsiderTrade]:
        """Fetch insider trades. Returns empty list on failure."""
        ...

    def get_market_cap(
        self,
        ticker: str,
        end_date: str,
        **kwargs: object,
    ) -> float | None:
        """Fetch market cap. Default implementation uses get_financial_metrics; override if provider has direct API."""
        metrics = self.get_financial_metrics(ticker, end_date, limit=1, **kwargs)
        if not metrics or metrics[0].market_cap is None:
            return None
        return metrics[0].market_cap

    def search_line_items(
        self,
        ticker: str,
        line_items: list[str],
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        **kwargs: object,
    ) -> list[LineItem]:
        """Fetch line items (earnings, revenue, etc.). Default: empty list; only some providers support this."""
        return []
