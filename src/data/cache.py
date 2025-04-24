from typing import TypedDict, List, Dict, Optional, Union, Any
from datetime import datetime, timedelta
import threading
from collections import OrderedDict


class PriceData(TypedDict):
    time: str  # ISO format timestamp
    price: float
    # Other price-related fields


class FinancialMetric(TypedDict):
    report_period: str  # e.g., "2023-Q1"
    # Financial metric fields


class LineItem(TypedDict):
    report_period: str  # e.g., "2023-Q1"
    # Line item fields


class InsiderTrade(TypedDict):
    filing_date: str  # ISO format date
    transaction_date: str  # ISO format date
    # Other insider trade fields


class CompanyNews(TypedDict):
    date: str  # ISO format date
    # News-related fields


# Generic type for cache data
CacheData = Union[PriceData, FinancialMetric, LineItem, InsiderTrade, CompanyNews]


class CacheEntry:
    """Represents a single entry in the cache with expiration time."""
    
    def __init__(self, data: List[Dict[str, Any]], expiry: Optional[datetime] = None):
        self.data = data
        self.expiry = expiry
        self.last_accessed = datetime.now()
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.expiry is None:
            return False
        return datetime.now() > self.expiry


class Cache:
    """In-memory cache for API responses with expiration and size limits."""

    def __init__(self, max_items_per_category: int = 1000, default_ttl: Optional[timedelta] = timedelta(hours=24)):
        """
        Initialize the cache.
        
        Args:
            max_items_per_category: Maximum number of ticker entries per category
            default_ttl: Default time-to-live for cache entries
        """
        self._lock = threading.RLock()
        self._max_items = max_items_per_category
        self._default_ttl = default_ttl
        
        # Using OrderedDict to track insertion order for LRU eviction
        self._prices_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._financial_metrics_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._line_items_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._insider_trades_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._company_news_cache: OrderedDict[str, CacheEntry] = OrderedDict()

    def _merge_data(self, existing: Optional[List[Dict[str, Any]]], new_data: List[Dict[str, Any]], 
                   key_field: str) -> List[Dict[str, Any]]:
        """Merge existing and new data, avoiding duplicates based on a key field."""
        if not existing:
            return new_data

        # Create a set of existing keys for O(1) lookup
        existing_keys = {item.get(key_field) for item in existing if key_field in item}

        # Only add items that don't exist yet
        merged = existing.copy()
        merged.extend([item for item in new_data if key_field in item and item[key_field] not in existing_keys])
        return merged

    def _manage_cache_size(self, cache_dict: OrderedDict[str, CacheEntry]) -> None:
        """Remove least recently used items if cache exceeds maximum size."""
        if len(cache_dict) > self._max_items:
            # Remove oldest items first (at the beginning of the OrderedDict)
            while len(cache_dict) > self._max_items:
                cache_dict.popitem(last=False)

    def _get_from_cache(self, cache_dict: OrderedDict[str, CacheEntry], ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Common method to retrieve and update data from a specific cache."""
        with self._lock:
            entry = cache_dict.get(ticker)
            if entry is None:
                return None
                
            # Check for expiration
            if entry.is_expired():
                del cache_dict[ticker]
                return None
                
            # Update last accessed time and move to end (most recently used)
            entry.last_accessed = datetime.now()
            cache_dict.move_to_end(ticker)
            
            return entry.data

    def _set_to_cache(self, cache_dict: OrderedDict[str, CacheEntry], ticker: str, 
                     data: List[Dict[str, Any]], key_field: str, ttl: Optional[timedelta] = None) -> None:
        """Common method to set data in a specific cache."""
        if not data:
            return
            
        with self._lock:
            # Calculate expiry time
            expiry = None
            if ttl is not None:
                expiry = datetime.now() + ttl
            elif self._default_ttl is not None:
                expiry = datetime.now() + self._default_ttl
                
            # Get existing data and merge
            existing_entry = cache_dict.get(ticker)
            existing_data = existing_entry.data if existing_entry else None
            merged_data = self._merge_data(existing_data, data, key_field)
            
            # Update cache
            cache_dict[ticker] = CacheEntry(merged_data, expiry)
            cache_dict.move_to_end(ticker)  # Move to end (most recently used)
            
            # Manage cache size
            self._manage_cache_size(cache_dict)

    # Prices methods
    def get_prices(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached price data if available."""
        return self._get_from_cache(self._prices_cache, ticker)

    def set_prices(self, ticker: str, data: List[Dict[str, Any]], ttl: Optional[timedelta] = None) -> None:
        """Append new price data to cache with optional custom TTL."""
        self._set_to_cache(self._prices_cache, ticker, data, "time", ttl)

    # Financial metrics methods
    def get_financial_metrics(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached financial metrics if available."""
        return self._get_from_cache(self._financial_metrics_cache, ticker)

    def set_financial_metrics(self, ticker: str, data: List[Dict[str, Any]], ttl: Optional[timedelta] = None) -> None:
        """Append new financial metrics to cache with optional custom TTL."""
        self._set_to_cache(self._financial_metrics_cache, ticker, data, "report_period", ttl)

    # Line items methods
    def get_line_items(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached line items if available."""
        return self._get_from_cache(self._line_items_cache, ticker)

    def set_line_items(self, ticker: str, data: List[Dict[str, Any]], ttl: Optional[timedelta] = None) -> None:
        """Append new line items to cache with optional custom TTL."""
        self._set_to_cache(self._line_items_cache, ticker, data, "report_period", ttl)

    # Insider trades methods
    def get_insider_trades(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached insider trades if available."""
        return self._get_from_cache(self._insider_trades_cache, ticker)

    def set_insider_trades(self, ticker: str, data: List[Dict[str, Any]], ttl: Optional[timedelta] = None) -> None:
        """Append new insider trades to cache with optional custom TTL."""
        self._set_to_cache(self._insider_trades_cache, ticker, data, "filing_date", ttl)

    # Company news methods
    def get_company_news(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached company news if available."""
        return self._get_from_cache(self._company_news_cache, ticker)

    def set_company_news(self, ticker: str, data: List[Dict[str, Any]], ttl: Optional[timedelta] = None) -> None:
        """Append new company news to cache with optional custom TTL."""
        self._set_to_cache(self._company_news_cache, ticker, data, "date", ttl)
        
    def clear(self, ticker: Optional[str] = None) -> None:
        """
        Clear cache entries.
        
        Args:
            ticker: If provided, clear only entries for this ticker, otherwise clear all entries
        """
        with self._lock:
            if ticker is None:
                # Clear all caches
                self._prices_cache.clear()
                self._financial_metrics_cache.clear()
                self._line_items_cache.clear()
                self._insider_trades_cache.clear()
                self._company_news_cache.clear()
            else:
                # Clear only entries for the specified ticker
                if ticker in self._prices_cache:
                    del self._prices_cache[ticker]
                if ticker in self._financial_metrics_cache:
                    del self._financial_metrics_cache[ticker]
                if ticker in self._line_items_cache:
                    del self._line_items_cache[ticker]
                if ticker in self._insider_trades_cache:
                    del self._insider_trades_cache[ticker]
                if ticker in self._company_news_cache:
                    del self._company_news_cache[ticker]


# Global cache instance with default settings
_cache = Cache()


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache


def create_cache(max_items: int = 1000, default_ttl: Optional[timedelta] = timedelta(hours=24)) -> Cache:
    """Create a new cache instance with custom settings."""
    return Cache(max_items_per_category=max_items, default_ttl=default_ttl)