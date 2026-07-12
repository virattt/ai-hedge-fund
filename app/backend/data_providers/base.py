"""Base class for data providers."""

from abc import ABC, abstractmethod
from typing import Optional
from app.backend.data_providers.models import (
    PriceBar,
    FundamentalData,
    NewsItem,
    SentimentResult,
    ProviderResult,
)


class DataProvider(ABC):
    """Abstract base class for market data providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""
        ...

    @abstractmethod
    def supports_ticker(self, ticker: str) -> bool:
        """Quick check: can this provider handle this ticker format?"""
        ...

    @abstractmethod
    def get_prices(
        self, ticker: str, start_date: str, end_date: str
    ) -> ProviderResult:
        """Fetch OHLCV price bars. Returns ProviderResult with list[PriceBar] as data."""
        ...

    def get_fundamentals(self, ticker: str) -> ProviderResult:
        """Fetch fundamental metrics. Override if provider supports it."""
        from app.backend.data_providers.models import DataAvailability
        return ProviderResult(
            availability=DataAvailability.UNSUPPORTED_TICKER,
            provider_name=self.name,
            error_message=f"{self.name} does not provide fundamentals for {ticker}",
        )

    def get_news(self, ticker: str, limit: int = 20) -> ProviderResult:
        """Fetch news articles. Override if provider supports it."""
        from app.backend.data_providers.models import DataAvailability
        return ProviderResult(
            availability=DataAvailability.UNSUPPORTED_TICKER,
            provider_name=self.name,
            error_message=f"{self.name} does not provide news for {ticker}",
        )
