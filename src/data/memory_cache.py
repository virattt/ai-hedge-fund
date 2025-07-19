from typing import Any

from src.data.cache_interface import CacheInterface


class MemoryCache(CacheInterface):
    """In-memory cache implementation."""

    def __init__(self):
        self._prices_cache: dict[str, list[dict[str, Any]]] = {}
        self._financial_metrics_cache: dict[str, list[dict[str, Any]]] = {}
        self._line_items_cache: dict[str, list[dict[str, Any]]] = {}
        self._insider_trades_cache: dict[str, list[dict[str, Any]]] = {}
        self._company_news_cache: dict[str, list[dict[str, Any]]] = {}

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
        return self._prices_cache.get(cache_key)

    def set_prices(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache price data with merging."""
        self._prices_cache[cache_key] = self._merge_data(
            self._prices_cache.get(cache_key), data, key_field="time"
        )

    def get_financial_metrics(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached financial metrics if available."""
        return self._financial_metrics_cache.get(cache_key)

    def set_financial_metrics(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache financial metrics with merging."""
        self._financial_metrics_cache[cache_key] = self._merge_data(
            self._financial_metrics_cache.get(cache_key), data, key_field="report_period"
        )

    def get_line_items(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached line items if available."""
        return self._line_items_cache.get(cache_key)

    def set_line_items(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache line items with merging."""
        self._line_items_cache[cache_key] = self._merge_data(
            self._line_items_cache.get(cache_key), data, key_field="report_period"
        )

    def get_insider_trades(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached insider trades if available."""
        return self._insider_trades_cache.get(cache_key)

    def set_insider_trades(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache insider trades with merging."""
        self._insider_trades_cache[cache_key] = self._merge_data(
            self._insider_trades_cache.get(cache_key), data, key_field="filing_date"
        )

    def get_company_news(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached company news if available."""
        return self._company_news_cache.get(cache_key)

    def set_company_news(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache company news with merging."""
        self._company_news_cache[cache_key] = self._merge_data(
            self._company_news_cache.get(cache_key), data, key_field="date"
        )

    def close(self) -> None:
        """Close the cache connection (no-op for memory cache)."""
        pass