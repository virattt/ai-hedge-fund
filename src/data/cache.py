import time
from typing import Any


class CacheEntry:
    """A cache entry with TTL support."""
    
    def __init__(self, data: list[dict[str, Any]], ttl_seconds: int = 3600):
        self.data = data
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.created_at > self.ttl_seconds


class Cache:
    """In-memory cache for API responses with TTL support."""

    # Default TTL: 1 hour for most data, 24 hours for less volatile data
    DEFAULT_TTL = 3600  # 1 hour
    METRICS_TTL = 86400  # 24 hours (metrics don't change frequently)
    NEWS_TTL = 1800  # 30 minutes (news is more time-sensitive)

    def __init__(self):
        self._prices_cache: dict[str, CacheEntry] = {}
        self._financial_metrics_cache: dict[str, CacheEntry] = {}
        self._line_items_cache: dict[str, CacheEntry] = {}
        self._insider_trades_cache: dict[str, CacheEntry] = {}
        self._company_news_cache: dict[str, CacheEntry] = {}

    def _merge_data(self, existing: list[dict] | None, new_data: list[dict], key_field: str) -> list[dict]:
        """Merge existing and new data, avoiding duplicates based on a key field."""
        if not existing:
            return new_data

        # Create a set of existing keys for O(1) lookup
        existing_keys = {item[key_field] for item in existing}

        # Only add items that don't exist yet
        merged = existing.copy()
        merged.extend([item for item in new_data if item[key_field] not in existing_keys])
        return merged

    def _cleanup_expired(self, cache_dict: dict[str, CacheEntry]) -> None:
        """Remove expired entries from a cache dictionary."""
        expired_keys = [key for key, entry in cache_dict.items() if entry.is_expired()]
        for key in expired_keys:
            del cache_dict[key]

    def get_prices(self, ticker: str) -> list[dict[str, Any]] | None:
        """Get cached price data if available and not expired."""
        self._cleanup_expired(self._prices_cache)
        entry = self._prices_cache.get(ticker)
        if entry and not entry.is_expired():
            return entry.data
        return None

    def set_prices(self, ticker: str, data: list[dict[str, Any]]):
        """Append new price data to cache with TTL."""
        existing_data = self.get_prices(ticker)
        merged = self._merge_data(existing_data, data, key_field="time")
        self._prices_cache[ticker] = CacheEntry(merged, ttl_seconds=self.DEFAULT_TTL)

    def get_financial_metrics(self, ticker: str) -> list[dict[str, Any]] | None:
        """Get cached financial metrics if available and not expired."""
        self._cleanup_expired(self._financial_metrics_cache)
        entry = self._financial_metrics_cache.get(ticker)
        if entry and not entry.is_expired():
            return entry.data
        return None

    def set_financial_metrics(self, ticker: str, data: list[dict[str, Any]]):
        """Append new financial metrics to cache with TTL."""
        existing_data = self.get_financial_metrics(ticker)
        merged = self._merge_data(existing_data, data, key_field="report_period")
        self._financial_metrics_cache[ticker] = CacheEntry(merged, ttl_seconds=self.METRICS_TTL)

    def get_line_items(self, ticker: str) -> list[dict[str, Any]] | None:
        """Get cached line items if available and not expired."""
        self._cleanup_expired(self._line_items_cache)
        entry = self._line_items_cache.get(ticker)
        if entry and not entry.is_expired():
            return entry.data
        return None

    def set_line_items(self, ticker: str, data: list[dict[str, Any]]):
        """Append new line items to cache with TTL."""
        existing_data = self.get_line_items(ticker)
        merged = self._merge_data(existing_data, data, key_field="report_period")
        self._line_items_cache[ticker] = CacheEntry(merged, ttl_seconds=self.METRICS_TTL)

    def get_insider_trades(self, ticker: str) -> list[dict[str, Any]] | None:
        """Get cached insider trades if available and not expired."""
        self._cleanup_expired(self._insider_trades_cache)
        entry = self._insider_trades_cache.get(ticker)
        if entry and not entry.is_expired():
            return entry.data
        return None

    def set_insider_trades(self, ticker: str, data: list[dict[str, Any]]):
        """Append new insider trades to cache with TTL."""
        existing_data = self.get_insider_trades(ticker)
        merged = self._merge_data(existing_data, data, key_field="filing_date")
        self._insider_trades_cache[ticker] = CacheEntry(merged, ttl_seconds=self.DEFAULT_TTL)

    def get_company_news(self, ticker: str) -> list[dict[str, Any]] | None:
        """Get cached company news if available and not expired."""
        self._cleanup_expired(self._company_news_cache)
        entry = self._company_news_cache.get(ticker)
        if entry and not entry.is_expired():
            return entry.data
        return None

    def set_company_news(self, ticker: str, data: list[dict[str, Any]]):
        """Append new company news to cache with TTL."""
        existing_data = self.get_company_news(ticker)
        merged = self._merge_data(existing_data, data, key_field="date")
        self._company_news_cache[ticker] = CacheEntry(merged, ttl_seconds=self.NEWS_TTL)

    def clear(self) -> None:
        """Clear all caches."""
        self._prices_cache.clear()
        self._financial_metrics_cache.clear()
        self._line_items_cache.clear()
        self._insider_trades_cache.clear()
        self._company_news_cache.clear()


# Global cache instance
_cache = Cache()


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache
