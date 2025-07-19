from typing import Any
import time
from datetime import datetime, timedelta

from src.data.cache_interface import CacheInterface


class MemoryCache(CacheInterface):
    """In-memory cache implementation."""

    def __init__(self, ttl_seconds: int = None):
        self._prices_cache: dict[str, list[dict[str, Any]]] = {}
        self._financial_metrics_cache: dict[str, list[dict[str, Any]]] = {}
        self._line_items_cache: dict[str, list[dict[str, Any]]] = {}
        self._insider_trades_cache: dict[str, list[dict[str, Any]]] = {}
        self._company_news_cache: dict[str, list[dict[str, Any]]] = {}
        self._line_item_search_cache: dict[str, list[dict[str, Any]]] = {}

        # TTL tracking
        self._ttl_seconds = ttl_seconds
        self._cache_timestamps: dict[str, dict[str, datetime]] = {
            "prices": {},
            "financial_metrics": {},
            "line_items": {},
            "insider_trades": {},
            "company_news": {},
            "line_item_search": {}
        }

    def _get_cache_and_table(self, table_name: str):
        """Get the cache dictionary and timestamp table for a given table name."""
        cache_map = {
            "prices": self._prices_cache,
            "financial_metrics": self._financial_metrics_cache,
            "line_items": self._line_items_cache,
            "insider_trades": self._insider_trades_cache,
            "company_news": self._company_news_cache,
            "line_item_search": self._line_item_search_cache
        }
        return cache_map.get(table_name), self._cache_timestamps.get(table_name)

    def _is_cache_expired(self, cache_key: str, table_name: str) -> bool:
        """Check if a cache entry is expired."""
        if not self._ttl_seconds:
            return False

        _, timestamp_table = self._get_cache_and_table(table_name)
        if not timestamp_table or cache_key not in timestamp_table:
            return False

        cache_time = timestamp_table[cache_key]
        return datetime.now() - cache_time > timedelta(seconds=self._ttl_seconds)

    def _set_cache_timestamp(self, cache_key: str, table_name: str):
        """Set the timestamp for a cache entry."""
        if self._ttl_seconds:
            _, timestamp_table = self._get_cache_and_table(table_name)
            if timestamp_table is not None:
                timestamp_table[cache_key] = datetime.now()

    def is_expired(self, cache_key: str, table_name: str) -> bool:
        """Check if a cache entry is expired."""
        return self._is_cache_expired(cache_key, table_name)

    def cleanup_expired(self) -> None:
        """Remove expired cache entries."""
        if not self._ttl_seconds:
            return

        tables = ["prices", "financial_metrics", "line_items", "insider_trades", "company_news", "line_item_search"]
        for table_name in tables:
            cache_dict, timestamp_table = self._get_cache_and_table(table_name)
            if cache_dict is None or timestamp_table is None:
                continue

            expired_keys = []
            for cache_key in list(timestamp_table.keys()):
                if self._is_cache_expired(cache_key, table_name):
                    expired_keys.append(cache_key)

            for key in expired_keys:
                cache_dict.pop(key, None)
                timestamp_table.pop(key, None)

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

    def get_prices(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached price data if available."""
        if self._is_cache_expired(cache_key, "prices"):
            self._prices_cache.pop(cache_key, None)
            return None
        return self._prices_cache.get(cache_key)

    def set_prices(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache price data with merging."""
        self._prices_cache[cache_key] = self._merge_data(
            self._prices_cache.get(cache_key), data, key_field="time"
        )
        self._set_cache_timestamp(cache_key, "prices")

    def get_financial_metrics(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached financial metrics if available."""
        if self._is_cache_expired(cache_key, "financial_metrics"):
            self._financial_metrics_cache.pop(cache_key, None)
            return None
        return self._financial_metrics_cache.get(cache_key)

    def set_financial_metrics(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache financial metrics with merging."""
        self._financial_metrics_cache[cache_key] = self._merge_data(
            self._financial_metrics_cache.get(cache_key), data, key_field="report_period"
        )
        self._set_cache_timestamp(cache_key, "financial_metrics")

    def get_line_items(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached line items if available."""
        if self._is_cache_expired(cache_key, "line_items"):
            self._line_items_cache.pop(cache_key, None)
            return None
        return self._line_items_cache.get(cache_key)

    def set_line_items(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache line items with merging."""
        self._line_items_cache[cache_key] = self._merge_data(
            self._line_items_cache.get(cache_key), data, key_field="report_period"
        )
        self._set_cache_timestamp(cache_key, "line_items")

    def get_insider_trades(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached insider trades if available."""
        if self._is_cache_expired(cache_key, "insider_trades"):
            self._insider_trades_cache.pop(cache_key, None)
            return None
        return self._insider_trades_cache.get(cache_key)

    def set_insider_trades(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache insider trades with merging."""
        self._insider_trades_cache[cache_key] = self._merge_data(
            self._insider_trades_cache.get(cache_key), data, key_field="filing_date"
        )
        self._set_cache_timestamp(cache_key, "insider_trades")

    def get_company_news(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached company news if available."""
        if self._is_cache_expired(cache_key, "company_news"):
            self._company_news_cache.pop(cache_key, None)
            return None
        return self._company_news_cache.get(cache_key)

    def set_company_news(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache company news with merging."""
        self._company_news_cache[cache_key] = self._merge_data(
            self._company_news_cache.get(cache_key), data, key_field="date"
        )
        self._set_cache_timestamp(cache_key, "company_news")

    def get_line_item_search(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached line item search results if available."""
        if self._is_cache_expired(cache_key, "line_item_search"):
            self._line_item_search_cache.pop(cache_key, None)
            return None
        return self._line_item_search_cache.get(cache_key)

    def set_line_item_search(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache line item search results."""
        # Line item search results don't need merging as they are complete result sets
        self._line_item_search_cache[cache_key] = data
        self._set_cache_timestamp(cache_key, "line_item_search")

    def close(self) -> None:
        """Close the cache connection (no-op for memory cache)."""
        pass
