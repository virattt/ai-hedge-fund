"""
Dual-Layer Cache Manager.

Integrates L1 (memory) and L2 (MySQL) caching layers for optimal performance.

Cache Strategy:
- L1 (Memory): Fast, in-memory cache with TTL
- L2 (MySQL): Persistent cache with data freshness rules
  - Historical data (date < today): Permanent
  - Current data (date = today): 1 hour freshness

Query Flow:
1. Check L1 cache → return if hit
2. Check L2 cache → return if hit and fresh, populate L1
3. Call API → populate both L1 and L2
"""
import logging
import os
import threading
from typing import List, Optional
from datetime import datetime, timedelta

from src.data.cache import get_cache as get_l1_cache
from src.data.mysql_cache import MySQLCacheManager
from src.data.models import Price, FinancialMetrics, CompanyNews

logger = logging.getLogger(__name__)


class DualLayerCacheManager:
    """
    Dual-layer cache manager integrating L1 (memory) and L2 (MySQL) caching.
    """

    def __init__(self, enable_l2: bool = True):
        """
        Initialize dual-layer cache manager.

        Args:
            enable_l2: Enable L2 (MySQL) cache. If False, only L1 is used.
        """
        self.l1_cache = get_l1_cache()
        self.l2_cache = None
        self.enable_l2 = enable_l2

        # Only initialize L2 cache if enabled and DATABASE_URL is set
        if enable_l2 and os.environ.get("DATABASE_URL"):
            try:
                self.l2_cache = MySQLCacheManager()
                logger.info("Dual-layer cache initialized with L2 (MySQL)")
            except Exception as e:
                logger.warning(f"Failed to initialize L2 cache: {e}. Using L1 only.")
                self.l2_cache = None
        else:
            logger.info("Dual-layer cache initialized with L1 only")

    def _create_cache_key(self, *args, **kwargs) -> str:
        """
        Create a cache key for L1 cache.

        Args:
            *args: Positional arguments (ticker, dates, etc.)
            **kwargs: Additional parameters

        Returns:
            Cache key string
        """
        key_parts = [str(arg) for arg in args if arg is not None]
        for value in kwargs.values():
            if value is not None:
                key_parts.append(str(value))
        return "_".join(key_parts)

    def get_prices(
        self, ticker: str, start_date: str, end_date: str
    ) -> Optional[List[Price]]:
        """
        Get prices from cache (L1 then L2).

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of Price objects if found in cache, None otherwise
        """
        cache_key = self._create_cache_key(ticker, start_date, end_date)

        # Try L1 cache first
        if cached_data := self.l1_cache.get_prices(cache_key):
            logger.debug(f"L1 cache hit: prices for {ticker}")
            return [Price(**price) for price in cached_data]

        # Try L2 cache if enabled
        if self.l2_cache:
            try:
                l2_prices = self.l2_cache.get_prices(ticker, start_date, end_date)
                if l2_prices:
                    # Check if data is fresh
                    if self.l2_cache.is_data_fresh(end_date):
                        logger.debug(f"L2 cache hit: prices for {ticker}")
                        # Populate L1 cache
                        self.l1_cache.set_prices(cache_key, [p.model_dump() for p in l2_prices])
                        return l2_prices
                    else:
                        logger.debug(f"L2 cache stale: prices for {ticker}")
            except Exception as e:
                logger.warning(f"L2 cache error for prices {ticker}: {e}")

        return None

    def set_prices(
        self, ticker: str, start_date: str, end_date: str, prices: List[Price]
    ):
        """
        Set prices in both L1 and L2 caches.

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            prices: List of Price objects
        """
        cache_key = self._create_cache_key(ticker, start_date, end_date)

        # Set in L1 cache
        self.l1_cache.set_prices(cache_key, [p.model_dump() for p in prices])

        # Set in L2 cache if enabled
        if self.l2_cache:
            try:
                self.l2_cache.save_prices(ticker, prices)
                logger.debug(f"Saved prices to L2 cache: {ticker}")
            except Exception as e:
                logger.warning(f"Failed to save prices to L2 cache: {e}")

    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> Optional[List[FinancialMetrics]]:
        """
        Get financial metrics from cache (L1 then L2).

        Args:
            ticker: Stock ticker
            end_date: End date (YYYY-MM-DD)
            period: Period type (ttm, quarterly, annual)
            limit: Maximum number of results

        Returns:
            List of FinancialMetrics objects if found in cache, None otherwise
        """
        cache_key = self._create_cache_key(ticker, period, end_date, limit)

        # Try L1 cache first
        if cached_data := self.l1_cache.get_financial_metrics(cache_key):
            logger.debug(f"L1 cache hit: financial_metrics for {ticker}")
            return [FinancialMetrics(**metric) for metric in cached_data]

        # Try L2 cache if enabled
        if self.l2_cache:
            try:
                l2_metrics = self.l2_cache.get_financial_metrics(ticker, end_date, period)
                if l2_metrics:
                    # Check if data is fresh
                    if self.l2_cache.is_data_fresh(end_date):
                        logger.debug(f"L2 cache hit: financial_metrics for {ticker}")
                        # Populate L1 cache
                        self.l1_cache.set_financial_metrics(
                            cache_key, [m.model_dump() for m in l2_metrics]
                        )
                        return l2_metrics
                    else:
                        logger.debug(f"L2 cache stale: financial_metrics for {ticker}")
            except Exception as e:
                logger.warning(f"L2 cache error for financial_metrics {ticker}: {e}")

        return None

    def set_financial_metrics(
        self, ticker: str, end_date: str, period: str, limit: int, metrics: List[FinancialMetrics]
    ):
        """
        Set financial metrics in both L1 and L2 caches.

        Args:
            ticker: Stock ticker
            end_date: End date (YYYY-MM-DD)
            period: Period type (ttm, quarterly, annual)
            limit: Maximum number of results
            metrics: List of FinancialMetrics objects
        """
        cache_key = self._create_cache_key(ticker, period, end_date, limit)

        # Set in L1 cache
        self.l1_cache.set_financial_metrics(cache_key, [m.model_dump() for m in metrics])

        # Set in L2 cache if enabled
        if self.l2_cache:
            try:
                self.l2_cache.save_financial_metrics(ticker, metrics)
                logger.debug(f"Saved financial_metrics to L2 cache: {ticker}")
            except Exception as e:
                logger.warning(f"Failed to save financial_metrics to L2 cache: {e}")

    def get_company_news(
        self, ticker: str, start_date: str, end_date: str, limit: int = 1000
    ) -> Optional[List[CompanyNews]]:
        """
        Get company news from cache (L1 then L2).

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Maximum number of results

        Returns:
            List of CompanyNews objects if found in cache, None otherwise
        """
        cache_key = self._create_cache_key(ticker, start_date or "none", end_date, limit)

        # Try L1 cache first
        if cached_data := self.l1_cache.get_company_news(cache_key):
            logger.debug(f"L1 cache hit: company_news for {ticker}")
            return [CompanyNews(**news) for news in cached_data]

        # Try L2 cache if enabled
        if self.l2_cache:
            try:
                l2_news = self.l2_cache.get_company_news(ticker, start_date or end_date, end_date)
                if l2_news:
                    # Check if data is fresh
                    if self.l2_cache.is_data_fresh(end_date):
                        logger.debug(f"L2 cache hit: company_news for {ticker}")
                        # Populate L1 cache
                        self.l1_cache.set_company_news(
                            cache_key, [n.model_dump() for n in l2_news]
                        )
                        return l2_news
                    else:
                        logger.debug(f"L2 cache stale: company_news for {ticker}")
            except Exception as e:
                logger.warning(f"L2 cache error for company_news {ticker}: {e}")

        return None

    def set_company_news(
        self, ticker: str, start_date: str, end_date: str, limit: int, news: List[CompanyNews]
    ):
        """
        Set company news in both L1 and L2 caches.

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Maximum number of results
            news: List of CompanyNews objects
        """
        cache_key = self._create_cache_key(ticker, start_date or "none", end_date, limit)

        # Set in L1 cache
        self.l1_cache.set_company_news(cache_key, [n.model_dump() for n in news])

        # Set in L2 cache if enabled
        if self.l2_cache:
            try:
                self.l2_cache.save_company_news(ticker, news)
                logger.debug(f"Saved company_news to L2 cache: {ticker}")
            except Exception as e:
                logger.warning(f"Failed to save company_news to L2 cache: {e}")


# Global dual-layer cache instance with thread-safe initialization
_dual_cache = None
_dual_cache_lock = threading.Lock()


def get_dual_cache(enable_l2: bool = True) -> DualLayerCacheManager:
    """
    Get the global dual-layer cache instance (thread-safe singleton).

    Args:
        enable_l2: Enable L2 (MySQL) cache

    Returns:
        DualLayerCacheManager instance
    """
    global _dual_cache
    if _dual_cache is None:
        with _dual_cache_lock:
            if _dual_cache is None:
                _dual_cache = DualLayerCacheManager(enable_l2=enable_l2)
    return _dual_cache
