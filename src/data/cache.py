import threading
import time
from collections import OrderedDict


MAX_ENTRIES = 100
TTL_SECONDS = 1800  # 30 minutes


class _TTLCache:
    """Simple thread-safe LRU cache with TTL expiration."""

    def __init__(self, max_entries: int = MAX_ENTRIES, ttl: int = TTL_SECONDS):
        self._data: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()
        self._max_entries = max_entries
        self._ttl = ttl
        self._lock = threading.Lock()

    def get(self, key: str) -> list[dict[str, any]] | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.monotonic() - ts > self._ttl:
                del self._data[key]
                return None
            # Move to end (most recently used)
            self._data.move_to_end(key)
            return list(value)  # shallow copy

    def set(self, key: str, value: list[dict[str, any]]) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]
            elif len(self._data) >= self._max_entries:
                self._data.popitem(last=False)  # evict oldest
            self._data[key] = (time.monotonic(), value)


class Cache:
    """In-memory cache for API responses."""

    def __init__(self):
        self._prices_cache = _TTLCache()
        self._financial_metrics_cache = _TTLCache()
        self._line_items_cache = _TTLCache()
        self._insider_trades_cache = _TTLCache()
        self._company_news_cache = _TTLCache()

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

    def get_prices(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached price data if available."""
        return self._prices_cache.get(ticker)

    def set_prices(self, ticker: str, data: list[dict[str, any]]):
        """Append new price data to cache."""
        existing = self._prices_cache.get(ticker)
        self._prices_cache.set(ticker, self._merge_data(existing, data, key_field="time"))

    def get_financial_metrics(self, ticker: str) -> list[dict[str, any]]:
        """Get cached financial metrics if available."""
        return self._financial_metrics_cache.get(ticker)

    def set_financial_metrics(self, ticker: str, data: list[dict[str, any]]):
        """Append new financial metrics to cache."""
        existing = self._financial_metrics_cache.get(ticker)
        self._financial_metrics_cache.set(ticker, self._merge_data(existing, data, key_field="report_period"))

    def get_line_items(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached line items if available."""
        return self._line_items_cache.get(ticker)

    def set_line_items(self, ticker: str, data: list[dict[str, any]]):
        """Append new line items to cache."""
        existing = self._line_items_cache.get(ticker)
        self._line_items_cache.set(ticker, self._merge_data(existing, data, key_field="report_period"))

    def get_insider_trades(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached insider trades if available."""
        return self._insider_trades_cache.get(ticker)

    def set_insider_trades(self, ticker: str, data: list[dict[str, any]]):
        """Append new insider trades to cache."""
        existing = self._insider_trades_cache.get(ticker)
        self._insider_trades_cache.set(ticker, self._merge_data(existing, data, key_field="filing_date"))

    def get_company_news(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached company news if available."""
        return self._company_news_cache.get(ticker)

    def set_company_news(self, ticker: str, data: list[dict[str, any]]):
        """Append new company news to cache."""
        existing = self._company_news_cache.get(ticker)
        self._company_news_cache.set(ticker, self._merge_data(existing, data, key_field="date"))


# Global cache instance
_cache = Cache()


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache
