"""Base class for market adapters."""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.markets.sources.base import DataSource
from src.data.validation import DataValidator
from src.data.models import Price

logger = logging.getLogger(__name__)


class MarketAdapter(ABC):
    """Base class for market-specific adapters."""

    def __init__(
        self,
        market: str,
        data_sources: List[DataSource],
        validator: Optional[DataValidator] = None,
    ):
        """
        Initialize market adapter.

        Args:
            market: Market identifier (e.g., 'CN', 'HK', 'US')
            data_sources: List of data sources to use (in priority order)
            validator: Data validator instance
        """
        self.market = market
        self.data_sources = data_sources
        self.validator = validator or DataValidator()
        self.logger = logging.getLogger(f"{__name__}.{market}")

        # Filter sources that support this market
        self.active_sources = [
            source for source in data_sources if source.supports_market(market)
        ]

        if not self.active_sources:
            self.logger.warning(f"No data sources available for market {market}")
        else:
            source_names = [s.name for s in self.active_sources]
            self.logger.debug(f"Initialized {market} adapter with sources: {source_names}")

    @abstractmethod
    def normalize_ticker(self, ticker: str) -> str:
        """
        Normalize ticker symbol for this market.

        Args:
            ticker: Raw ticker symbol

        Returns:
            Normalized ticker symbol
        """
        pass

    def get_prices(
        self, ticker: str, start_date: str, end_date: str
    ) -> List[Price]:
        """
        Get price data with multi-source validation (parallel requests).

        Args:
            ticker: Stock ticker
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            List of validated Price objects
        """
        ticker = self.normalize_ticker(ticker)

        if not self.active_sources:
            self.logger.error(f"No data sources available for {ticker}")
            return []

        # Collect data from all sources in parallel
        source_data = {}

        def fetch_from_source(source):
            """Fetch prices from a single source."""
            try:
                self.logger.info(f"[{self.market}Adapter] 🔄 Fetching prices from {source.name} for {ticker}...")
                prices = source.get_prices(ticker, start_date, end_date)
                if prices:
                    self.logger.info(
                        f"[{self.market}Adapter] ✓ Got {len(prices)} prices from {source.name} for {ticker}"
                    )
                    return source.name, prices
                else:
                    self.logger.warning(f"[{self.market}Adapter] ⚠ {source.name} returned no data for {ticker}")
                    return None
            except Exception as e:
                self.logger.error(
                    f"[{self.market}Adapter] ✗ Failed to get prices from {source.name} for {ticker}: {e}"
                )
                return None

        # Use ThreadPoolExecutor for parallel requests
        with ThreadPoolExecutor(max_workers=len(self.active_sources)) as executor:
            futures = {executor.submit(fetch_from_source, source): source for source in self.active_sources}

            for future in as_completed(futures):
                result = future.result()
                if result:
                    source_name, prices = result
                    source_data[source_name] = prices

        if not source_data:
            self.logger.warning(f"[{self.market}Adapter] No price data available from any source for {ticker}")
            return []

        # Validate and merge data
        try:
            validated_prices = self.validator.cross_validate_prices(source_data)

            # Convert to Price objects
            price_objects = []
            for price_dict in validated_prices:
                try:
                    # Remove validation metadata before creating Price object
                    clean_dict = {
                        "open": price_dict["open"],
                        "close": price_dict["close"],
                        "high": price_dict["high"],
                        "low": price_dict["low"],
                        "volume": price_dict["volume"],
                        "time": price_dict["time"],
                    }
                    price_objects.append(Price(**clean_dict))
                except Exception as e:
                    self.logger.warning(f"Failed to create Price object: {e}")

            self.logger.info(
                f"[{self.market}Adapter] ✓ Retrieved {len(price_objects)} validated prices for {ticker}"
            )
            return price_objects

        except Exception as e:
            self.logger.error(f"Failed to validate prices for {ticker}: {e}")
            # Fallback to first available source
            if source_data:
                first_source = list(source_data.values())[0]
                self.logger.warning(
                    f"Using fallback data from first source ({len(first_source)} records)"
                )
                return [Price(**p) for p in first_source]
            return []

    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> Optional[Dict]:
        """
        Get financial metrics with multi-source validation (parallel requests).

        Args:
            ticker: Stock ticker
            end_date: End date in YYYY-MM-DD format
            period: Period type (ttm, quarterly, annual)
            limit: Number of periods to fetch

        Returns:
            Dictionary with validated financial metrics
        """
        ticker = self.normalize_ticker(ticker)

        if not self.active_sources:
            self.logger.error(f"[{self.market}Adapter] No data sources available for {ticker}")
            return None

        # Collect data from all sources in parallel
        source_data = {}

        def fetch_from_source(source):
            """Fetch financial metrics from a single source."""
            try:
                self.logger.info(f"[{self.market}Adapter] 🔄 Fetching financial metrics from {source.name} for {ticker}...")
                metrics = source.get_financial_metrics(ticker, end_date, period, limit)
                if metrics:
                    self.logger.info(f"[{self.market}Adapter] ✓ Got financial metrics from {source.name} for {ticker}")
                    return source.name, metrics
                else:
                    self.logger.warning(f"[{self.market}Adapter] ⚠ {source.name} returned no financial metrics for {ticker}")
                    return None
            except Exception as e:
                self.logger.error(
                    f"[{self.market}Adapter] ✗ Failed to get financial metrics from {source.name} for {ticker}: {e}"
                )
                return None

        # Use ThreadPoolExecutor for parallel requests
        with ThreadPoolExecutor(max_workers=len(self.active_sources)) as executor:
            futures = {executor.submit(fetch_from_source, source): source for source in self.active_sources}

            for future in as_completed(futures):
                result = future.result()
                if result:
                    source_name, metrics = result
                    source_data[source_name] = metrics

        if not source_data:
            self.logger.warning(
                f"[{self.market}Adapter] No financial metrics available from any source for {ticker}"
            )
            return None

        # Validate and merge data
        try:
            validated_metrics = self.validator.validate_financial_metrics(source_data)
            if validated_metrics:
                self.logger.info(
                    f"Retrieved validated financial metrics for {ticker} "
                    f"(confidence: {validated_metrics.get('confidence', 0):.2f})"
                )
            return validated_metrics

        except Exception as e:
            self.logger.error(f"Failed to validate financial metrics for {ticker}: {e}")
            # Fallback to first available source
            if source_data:
                first_metrics = list(source_data.values())[0]
                self.logger.warning(f"Using fallback financial metrics from first source")
                return first_metrics
            return None

    def get_company_news(
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Get company news with multi-source validation (parallel requests).

        Args:
            ticker: Stock ticker
            end_date: End date in YYYY-MM-DD format
            start_date: Start date in YYYY-MM-DD format (optional)
            limit: Maximum number of news items

        Returns:
            List of validated news items
        """
        ticker = self.normalize_ticker(ticker)

        if not self.active_sources:
            self.logger.error(f"[{self.market}Adapter] No data sources available for {ticker}")
            return []

        # Collect data from all sources in parallel
        source_data = {}

        def fetch_from_source(source):
            """Fetch news from a single source."""
            try:
                self.logger.info(f"[{self.market}Adapter] 🔄 Fetching news from {source.name} for {ticker}...")
                news = source.get_company_news(ticker, end_date, start_date, limit)
                if news:
                    self.logger.info(f"[{self.market}Adapter] ✓ Got {len(news)} news items from {source.name} for {ticker}")
                    return source.name, news
                else:
                    self.logger.warning(f"[{self.market}Adapter] ⚠ {source.name} returned no news for {ticker}")
                    return None
            except Exception as e:
                self.logger.error(
                    f"[{self.market}Adapter] ✗ Failed to get news from {source.name} for {ticker}: {e}"
                )
                return None

        # Use ThreadPoolExecutor for parallel requests
        with ThreadPoolExecutor(max_workers=len(self.active_sources)) as executor:
            futures = {executor.submit(fetch_from_source, source): source for source in self.active_sources}

            for future in as_completed(futures):
                result = future.result()
                if result:
                    source_name, news = result
                    source_data[source_name] = news

        if not source_data:
            self.logger.warning(f"[{self.market}Adapter] No news available from any source for {ticker}")
            return []

        # Validate and merge data
        try:
            validated_news = self.validator.validate_news(source_data)
            self.logger.info(f"[{self.market}Adapter] ✓ Retrieved {len(validated_news)} validated news items for {ticker}")
            return validated_news[:limit]

        except Exception as e:
            self.logger.error(f"Failed to validate news for {ticker}: {e}")
            # Fallback to first available source
            if source_data:
                first_news = list(source_data.values())[0]
                self.logger.warning(
                    f"Using fallback news from first source ({len(first_news)} items)"
                )
                return first_news[:limit]
            return []

    def get_insider_trades(
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Get insider trading data with multi-source support (parallel requests).

        Args:
            ticker: Stock ticker
            end_date: End date in YYYY-MM-DD format
            start_date: Start date in YYYY-MM-DD format (optional)
            limit: Maximum number of trades

        Returns:
            List of insider trade dictionaries
        """
        ticker = self.normalize_ticker(ticker)

        if not self.active_sources:
            self.logger.error(f"[{self.market}Adapter] No data sources available for {ticker}")
            return []

        # Collect data from all sources in parallel
        source_data = {}

        def fetch_from_source(source):
            """Fetch insider trades from a single source."""
            try:
                self.logger.info(f"[{self.market}Adapter] 🔄 Fetching insider trades from {source.name} for {ticker}...")
                trades = source.get_insider_trades(ticker, end_date, start_date, limit)
                if trades:
                    self.logger.info(f"[{self.market}Adapter] ✓ Got {len(trades)} insider trades from {source.name} for {ticker}")
                    return source.name, trades
                else:
                    self.logger.info(f"[{self.market}Adapter] ⚠ {source.name} returned no insider trades for {ticker}")
                    return None
            except Exception as e:
                self.logger.warning(
                    f"[{self.market}Adapter] ✗ Failed to get insider trades from {source.name} for {ticker}: {e}"
                )
                return None

        # Use ThreadPoolExecutor for parallel requests
        with ThreadPoolExecutor(max_workers=len(self.active_sources)) as executor:
            futures = {executor.submit(fetch_from_source, source): source for source in self.active_sources}

            for future in as_completed(futures):
                result = future.result()
                if result:
                    source_name, trades = result
                    source_data[source_name] = trades

        if not source_data:
            self.logger.info(f"[{self.market}Adapter] No insider trades available from any source for {ticker}")
            return []

        # Use first available source (no cross-validation for insider trades)
        first_trades = list(source_data.values())[0]
        self.logger.info(f"[{self.market}Adapter] ✓ Retrieved {len(first_trades)} insider trades for {ticker}")
        return first_trades[:limit]
