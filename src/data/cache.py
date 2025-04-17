import threading
import pickle
from datetime import datetime, timedelta

class Cache:
    """In-memory cache for API responses with expiration, thread safety, and size limits."""
    
    MAX_CACHE_SIZE = 10_000  # Maximum items per cache dictionary
    
    def __init__(self):
        self._prices_cache: dict[str, list[dict[str, any]]] = {}
        self._financial_metrics_cache: dict[str, list[dict[str, any]]] = {}
        self._line_items_cache: dict[str, list[dict[str, any]]] = {}
        self._insider_trades_cache: dict[str, list[dict[str, any]]] = {}
        self._company_news_cache: dict[str, list[dict[str, any]]] = {}
        
        # For thread safety
        self._lock = threading.RLock()
        
        # For cache expiration
        self._cache_expiry: dict[str, datetime] = {}
        self._ttl = timedelta(hours=1)  # Default 1 hour TTL

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
    
    def _is_expired(self, ticker: str) -> bool:
        """Check if the cache for a ticker has expired."""
        expiry = self._cache_expiry.get(ticker)
        return expiry is not None and datetime.now() > expiry
    
    def _enforce_size_limit(self, cache: dict):
        """Enforce the maximum cache size by removing oldest entries first."""
        if len(cache) > self.MAX_CACHE_SIZE:
            for _ in range(len(cache) - self.MAX_CACHE_SIZE):
                cache.popitem(last=False)  # Remove oldest item (first inserted)

    def get_prices(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached price data if available and not expired."""
        with self._lock:
            if self._is_expired(ticker):
                self._prices_cache.pop(ticker, None)
                self._cache_expiry.pop(ticker, None)
                return None
            return self._prices_cache.get(ticker)

    def set_prices(self, ticker: str, data: list[dict[str, any]]):
        """Append new price data to cache and update expiration time."""
        with self._lock:
            self._prices_cache[ticker] = self._merge_data(self._prices_cache.get(ticker), data, key_field="time")
            self._cache_expiry[ticker] = datetime.now() + self._ttl
            self._enforce_size_limit(self._prices_cache)

    def get_financial_metrics(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached financial metrics if available and not expired."""
        with self._lock:
            if self._is_expired(ticker):
                self._financial_metrics_cache.pop(ticker, None)
                self._cache_expiry.pop(ticker, None)
                return None
            return self._financial_metrics_cache.get(ticker)

    def set_financial_metrics(self, ticker: str, data: list[dict[str, any]]):
        """Append new financial metrics to cache and update expiration time."""
        with self._lock:
            self._financial_metrics_cache[ticker] = self._merge_data(
                self._financial_metrics_cache.get(ticker), data, key_field="report_period"
            )
            self._cache_expiry[ticker] = datetime.now() + self._ttl
            self._enforce_size_limit(self._financial_metrics_cache)

    def get_line_items(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached line items if available and not expired."""
        with self._lock:
            if self._is_expired(ticker):
                self._line_items_cache.pop(ticker, None)
                self._cache_expiry.pop(ticker, None)
                return None
            return self._line_items_cache.get(ticker)

    def set_line_items(self, ticker: str, data: list[dict[str, any]]):
        """Append new line items to cache and update expiration time."""
        with self._lock:
            self._line_items_cache[ticker] = self._merge_data(
                self._line_items_cache.get(ticker), data, key_field="report_period"
            )
            self._cache_expiry[ticker] = datetime.now() + self._ttl
            self._enforce_size_limit(self._line_items_cache)

    def get_insider_trades(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached insider trades if available and not expired."""
        with self._lock:
            if self._is_expired(ticker):
                self._insider_trades_cache.pop(ticker, None)
                self._cache_expiry.pop(ticker, None)
                return None
            return self._insider_trades_cache.get(ticker)

    def set_insider_trades(self, ticker: str, data: list[dict[str, any]]):
        """Append new insider trades to cache and update expiration time."""
        with self._lock:
            self._insider_trades_cache[ticker] = self._merge_data(
                self._insider_trades_cache.get(ticker), data, key_field="filing_date"
            )
            self._cache_expiry[ticker] = datetime.now() + self._ttl
            self._enforce_size_limit(self._insider_trades_cache)

    def get_company_news(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached company news if available and not expired."""
        with self._lock:
            if self._is_expired(ticker):
                self._company_news_cache.pop(ticker, None)
                self._cache_expiry.pop(ticker, None)
                return None
            return self._company_news_cache.get(ticker)

    def set_company_news(self, ticker: str, data: list[dict[str, any]]):
        """Append new company news to cache and update expiration time."""
        with self._lock:
            self._company_news_cache[ticker] = self._merge_data(
                self._company_news_cache.get(ticker), data, key_field="date"
            )
            self._cache_expiry[ticker] = datetime.now() + self._ttl
            self._enforce_size_limit(self._company_news_cache)
    
    def set_ttl(self, hours: float):
        """Set a new time-to-live for cache entries."""
        with self._lock:
            self._ttl = timedelta(hours=hours)
    
    def save_to_disk(self, path: str = "./cache.pkl"):
        """Save the current cache state to disk."""
        with self._lock:
            with open(path, "wb") as f:
                pickle.dump({
                    "prices": self._prices_cache,
                    "financial_metrics": self._financial_metrics_cache,
                    "line_items": self._line_items_cache,
                    "insider_trades": self._insider_trades_cache,
                    "company_news": self._company_news_cache,
                    "expiry": self._cache_expiry,
                    "ttl": self._ttl
                }, f)
    
    def load_from_disk(self, path: str = "./cache.pkl"):
        """Load cache state from disk."""
        with self._lock:
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)
                    self._prices_cache = data["prices"]
                    self._financial_metrics_cache = data["financial_metrics"]
                    self._line_items_cache = data["line_items"]
                    self._insider_trades_cache = data["insider_trades"]
                    self._company_news_cache = data["company_news"]
                    self._cache_expiry = data["expiry"]
                    self._ttl = data.get("ttl", timedelta(hours=1))
            except FileNotFoundError:
                pass


# Global cache instance
_cache = Cache()


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache