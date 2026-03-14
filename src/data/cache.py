import time
import logging
from dataclasses import dataclass
from threading import Lock
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Cache statistics for monitoring performance."""
    hits: int = 0
    misses: int = 0

    @property
    def total(self) -> int:
        """Total number of cache operations."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total == 0:
            return 0.0
        return self.hits / self.total


class Cache:
    """In-memory cache for API responses with TTL and statistics support."""

    def __init__(self, ttl: int = 300):
        """
        Initialize cache with TTL support.

        Args:
            ttl: Time-to-live in seconds (default: 300 = 5 minutes)
        """
        self._prices_cache: Dict[str, Dict[str, Any]] = {}
        self._financial_metrics_cache: Dict[str, Dict[str, Any]] = {}
        self._line_items_cache: Dict[str, Dict[str, Any]] = {}
        self._insider_trades_cache: Dict[str, Dict[str, Any]] = {}
        self._company_news_cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        self._ttl = ttl
        self.stats = CacheStats()
        logger.info(f"Cache initialized with TTL={ttl}s")

    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """
        Check if a cache entry has expired.

        Args:
            entry: Cache entry dictionary with 'timestamp' field

        Returns:
            True if expired or no timestamp, False otherwise
        """
        if 'timestamp' not in entry:
            return True
        return time.time() - entry['timestamp'] > self._ttl

    def _merge_data(self, existing: List[dict] | None, new_data: List[dict], key_field: str) -> List[dict]:
        """Merge existing and new data, avoiding duplicates based on a key field."""
        if not existing:
            return new_data

        # Create a set of existing keys for O(1) lookup
        existing_keys = {item[key_field] for item in existing}

        # Only add items that don't exist yet
        merged = existing.copy()
        merged.extend([item for item in new_data if item[key_field] not in existing_keys])
        return merged

    def get_prices(self, ticker: str) -> List[dict[str, Any]] | None:
        """
        Get cached price data if available and not expired.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of price data or None if not cached or expired
        """
        with self._lock:
            entry = self._prices_cache.get(ticker)
            if entry is None:
                self.stats.misses += 1
                logger.debug(f"Cache miss: prices for {ticker}")
                return None

            if self._is_expired(entry):
                self.stats.misses += 1
                logger.debug(f"Cache expired: prices for {ticker}")
                del self._prices_cache[ticker]
                return None

            self.stats.hits += 1
            logger.debug(f"Cache hit: prices for {ticker}")
            return entry['data']

    def set_prices(self, ticker: str, data: List[dict[str, Any]]):
        """
        Set price data in cache with timestamp.

        Args:
            ticker: Stock ticker symbol
            data: List of price data
        """
        with self._lock:
            existing_entry = self._prices_cache.get(ticker)
            existing_data = existing_entry['data'] if existing_entry and not self._is_expired(existing_entry) else None
            merged_data = self._merge_data(existing_data, data, key_field="time")
            self._prices_cache[ticker] = {
                'data': merged_data,
                'timestamp': time.time()
            }
            logger.debug(f"Cache set: prices for {ticker} ({len(merged_data)} items)")

    def get_financial_metrics(self, ticker: str) -> List[dict[str, Any]] | None:
        """
        Get cached financial metrics if available and not expired.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of financial metrics or None if not cached or expired
        """
        with self._lock:
            entry = self._financial_metrics_cache.get(ticker)
            if entry is None:
                self.stats.misses += 1
                logger.debug(f"Cache miss: financial_metrics for {ticker}")
                return None

            if self._is_expired(entry):
                self.stats.misses += 1
                logger.debug(f"Cache expired: financial_metrics for {ticker}")
                del self._financial_metrics_cache[ticker]
                return None

            self.stats.hits += 1
            logger.debug(f"Cache hit: financial_metrics for {ticker}")
            return entry['data']

    def set_financial_metrics(self, ticker: str, data: List[dict[str, Any]]):
        """
        Set financial metrics in cache with timestamp.

        Args:
            ticker: Stock ticker symbol
            data: List of financial metrics
        """
        with self._lock:
            existing_entry = self._financial_metrics_cache.get(ticker)
            existing_data = existing_entry['data'] if existing_entry and not self._is_expired(existing_entry) else None
            merged_data = self._merge_data(existing_data, data, key_field="report_period")
            self._financial_metrics_cache[ticker] = {
                'data': merged_data,
                'timestamp': time.time()
            }
            logger.debug(f"Cache set: financial_metrics for {ticker} ({len(merged_data)} items)")

    def get_line_items(self, ticker: str) -> List[dict[str, Any]] | None:
        """
        Get cached line items if available and not expired.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of line items or None if not cached or expired
        """
        with self._lock:
            entry = self._line_items_cache.get(ticker)
            if entry is None:
                self.stats.misses += 1
                logger.debug(f"Cache miss: line_items for {ticker}")
                return None

            if self._is_expired(entry):
                self.stats.misses += 1
                logger.debug(f"Cache expired: line_items for {ticker}")
                del self._line_items_cache[ticker]
                return None

            self.stats.hits += 1
            logger.debug(f"Cache hit: line_items for {ticker}")
            return entry['data']

    def set_line_items(self, ticker: str, data: List[dict[str, Any]]):
        """
        Set line items in cache with timestamp.

        Args:
            ticker: Stock ticker symbol
            data: List of line items
        """
        with self._lock:
            existing_entry = self._line_items_cache.get(ticker)
            existing_data = existing_entry['data'] if existing_entry and not self._is_expired(existing_entry) else None
            merged_data = self._merge_data(existing_data, data, key_field="report_period")
            self._line_items_cache[ticker] = {
                'data': merged_data,
                'timestamp': time.time()
            }
            logger.debug(f"Cache set: line_items for {ticker} ({len(merged_data)} items)")

    def get_insider_trades(self, ticker: str) -> List[dict[str, Any]] | None:
        """
        Get cached insider trades if available and not expired.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of insider trades or None if not cached or expired
        """
        with self._lock:
            entry = self._insider_trades_cache.get(ticker)
            if entry is None:
                self.stats.misses += 1
                logger.debug(f"Cache miss: insider_trades for {ticker}")
                return None

            if self._is_expired(entry):
                self.stats.misses += 1
                logger.debug(f"Cache expired: insider_trades for {ticker}")
                del self._insider_trades_cache[ticker]
                return None

            self.stats.hits += 1
            logger.debug(f"Cache hit: insider_trades for {ticker}")
            return entry['data']

    def set_insider_trades(self, ticker: str, data: List[dict[str, Any]]):
        """
        Set insider trades in cache with timestamp.

        Args:
            ticker: Stock ticker symbol
            data: List of insider trades
        """
        with self._lock:
            existing_entry = self._insider_trades_cache.get(ticker)
            existing_data = existing_entry['data'] if existing_entry and not self._is_expired(existing_entry) else None
            merged_data = self._merge_data(existing_data, data, key_field="filing_date")
            self._insider_trades_cache[ticker] = {
                'data': merged_data,
                'timestamp': time.time()
            }
            logger.debug(f"Cache set: insider_trades for {ticker} ({len(merged_data)} items)")

    def get_company_news(self, ticker: str) -> List[dict[str, Any]] | None:
        """
        Get cached company news if available and not expired.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of company news or None if not cached or expired
        """
        with self._lock:
            entry = self._company_news_cache.get(ticker)
            if entry is None:
                self.stats.misses += 1
                logger.debug(f"Cache miss: company_news for {ticker}")
                return None

            if self._is_expired(entry):
                self.stats.misses += 1
                logger.debug(f"Cache expired: company_news for {ticker}")
                del self._company_news_cache[ticker]
                return None

            self.stats.hits += 1
            logger.debug(f"Cache hit: company_news for {ticker}")
            return entry['data']

    def set_company_news(self, ticker: str, data: List[dict[str, Any]]):
        """
        Set company news in cache with timestamp.

        Args:
            ticker: Stock ticker symbol
            data: List of company news
        """
        with self._lock:
            existing_entry = self._company_news_cache.get(ticker)
            existing_data = existing_entry['data'] if existing_entry and not self._is_expired(existing_entry) else None
            merged_data = self._merge_data(existing_data, data, key_field="date")
            self._company_news_cache[ticker] = {
                'data': merged_data,
                'timestamp': time.time()
            }
            logger.debug(f"Cache set: company_news for {ticker} ({len(merged_data)} items)")

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from all caches.

        Returns:
            Number of entries removed
        """
        with self._lock:
            removed = 0

            # Clean prices cache
            expired_keys = [k for k, v in self._prices_cache.items() if self._is_expired(v)]
            for key in expired_keys:
                del self._prices_cache[key]
                removed += 1

            # Clean financial metrics cache
            expired_keys = [k for k, v in self._financial_metrics_cache.items() if self._is_expired(v)]
            for key in expired_keys:
                del self._financial_metrics_cache[key]
                removed += 1

            # Clean line items cache
            expired_keys = [k for k, v in self._line_items_cache.items() if self._is_expired(v)]
            for key in expired_keys:
                del self._line_items_cache[key]
                removed += 1

            # Clean insider trades cache
            expired_keys = [k for k, v in self._insider_trades_cache.items() if self._is_expired(v)]
            for key in expired_keys:
                del self._insider_trades_cache[key]
                removed += 1

            # Clean company news cache
            expired_keys = [k for k, v in self._company_news_cache.items() if self._is_expired(v)]
            for key in expired_keys:
                del self._company_news_cache[key]
                removed += 1

            if removed > 0:
                logger.info(f"Cleaned up {removed} expired cache entries")

            return removed

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        with self._lock:
            return {
                'hits': self.stats.hits,
                'misses': self.stats.misses,
                'total': self.stats.total,
                'hit_rate': f"{self.stats.hit_rate * 100:.2f}%",
                'prices_size': len(self._prices_cache),
                'financial_metrics_size': len(self._financial_metrics_cache),
                'line_items_size': len(self._line_items_cache),
                'insider_trades_size': len(self._insider_trades_cache),
                'company_news_size': len(self._company_news_cache),
                'ttl': self._ttl
            }

    def clear(self):
        """Clear all caches and reset statistics."""
        with self._lock:
            self._prices_cache.clear()
            self._financial_metrics_cache.clear()
            self._line_items_cache.clear()
            self._insider_trades_cache.clear()
            self._company_news_cache.clear()
            self.stats = CacheStats()
            logger.info("Cache cleared")


# Global cache instance
_cache = Cache()


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache
