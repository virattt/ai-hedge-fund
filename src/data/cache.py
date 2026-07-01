import threading
from contextlib import contextmanager


class Cache:
    """In-memory cache for API responses.

    Shared across every analyst agent in a run (global singleton, see
    :func:`get_cache`). Two behaviours go beyond a plain exact-match store:

    * ``line_items`` tracks the *set of fields* fetched per cache key and merges
      new fields into existing rows (field-level union). This lets a second
      agent that asks for an overlapping set of line items reuse the first
      agent's data and only fetch the missing fields.
    * ``financial_metrics`` tracks the *max limit* fetched per key, so a request
      for a smaller limit can reuse a larger cached fetch (subset-on-limit).

    Both are safe for the concurrent analyst fan-out: :meth:`fetch_lock` gives
    callers a per-key lock so that simultaneous misses on the same key don't
    trigger duplicate API calls (thundering herd).
    """

    def __init__(self):
        self._prices_cache: dict[str, list[dict[str, any]]] = {}
        self._financial_metrics_cache: dict[str, dict[str, any]] = {}  # key -> {"data": list, "limit": int|None}
        self._line_items_cache: dict[str, dict[str, any]] = {}  # key -> {"data": list, "fields": set}
        self._insider_trades_cache: dict[str, list[dict[str, any]]] = {}
        self._company_news_cache: dict[str, list[dict[str, any]]] = {}

        # Per-key locks for serialising check-fetch-populate across threads.
        self._locks_guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

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

    @contextmanager
    def fetch_lock(self, key: str):
        """Per-key lock. Use to make a check-cache -> fetch -> populate sequence
        atomic for a given key, so concurrent agents don't double-fetch."""
        with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    def get_prices(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached price data if available."""
        return self._prices_cache.get(ticker)

    def set_prices(self, ticker: str, data: list[dict[str, any]]):
        """Append new price data to cache."""
        self._prices_cache[ticker] = self._merge_data(self._prices_cache.get(ticker), data, key_field="time")

    def get_financial_metrics(self, ticker: str) -> list[dict[str, any]]:
        """Get cached financial metrics if available."""
        entry = self._financial_metrics_cache.get(ticker)
        return entry["data"] if entry else None

    def get_financial_metrics_limit(self, ticker: str) -> int | None:
        """Get the largest ``limit`` fetched so far for this key, or None."""
        entry = self._financial_metrics_cache.get(ticker)
        return entry["limit"] if entry else None

    def set_financial_metrics(self, ticker: str, data: list[dict[str, any]], limit: int | None = None):
        """Append new financial metrics to cache and track the max ``limit`` seen.

        Tracking the limit enables subset-on-limit reuse: once we have fetched
        ``limit=10``, a later request for ``limit=5`` can be served from cache.
        """
        existing = self._financial_metrics_cache.get(ticker)
        merged_data = self._merge_data(existing["data"] if existing else None, data, key_field="report_period")
        prev_limit = existing["limit"] if existing else None
        if limit is None:
            new_limit = prev_limit
        elif prev_limit is None:
            new_limit = limit
        else:
            new_limit = max(prev_limit, limit)
        self._financial_metrics_cache[ticker] = {"data": merged_data, "limit": new_limit}

    def get_line_items(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached line items if available."""
        entry = self._line_items_cache.get(ticker)
        return entry["data"] if entry else None

    def get_line_items_fields(self, ticker: str) -> set[str] | None:
        """Get the set of fields fetched so far for this key, or None if absent."""
        entry = self._line_items_cache.get(ticker)
        return set(entry["fields"]) if entry else None

    def set_line_items(self, ticker: str, data: list[dict[str, any]], fields: set[str] | list[str] | None = None):
        """Merge new line items into the cache using a *field-level* union keyed
        by ``report_period``.

        Unlike :meth:`_merge_data` (row-level), this merges additional fields
        into an existing row for the same ``report_period`` — so two agents that
        each request a few overlapping line items end up with one combined row
        per period instead of dropping the second agent's fields.
        """
        field_set: set[str] = set(fields) if fields else set()
        existing = self._line_items_cache.get(ticker)
        if existing is None:
            self._line_items_cache[ticker] = {
                "data": [dict(row) for row in data],
                "fields": set(field_set),
            }
            return

        # Preserve row order of the existing data; append genuinely new periods.
        by_period: dict[str, dict[str, any]] = {row["report_period"]: row for row in existing["data"]}
        order: list[str] = [row["report_period"] for row in existing["data"]]
        for row in data:
            period = row["report_period"]
            if period in by_period:
                target = by_period[period]
                # Fill in fields the existing row doesn't have (or has as None);
                # never overwrite a value already present.
                for k, v in row.items():
                    if k not in target or target[k] is None:
                        target[k] = v
            else:
                by_period[period] = dict(row)
                order.append(period)

        self._line_items_cache[ticker] = {
            "data": [by_period[period] for period in order],
            "fields": existing["fields"] | field_set,
        }

    def get_insider_trades(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached insider trades if available."""
        return self._insider_trades_cache.get(ticker)

    def set_insider_trades(self, ticker: str, data: list[dict[str, any]]):
        """Append new insider trades to cache."""
        self._insider_trades_cache[ticker] = self._merge_data(self._insider_trades_cache.get(ticker), data, key_field="filing_date")  # Could also use transaction_date if preferred

    def get_company_news(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached company news if available."""
        return self._company_news_cache.get(ticker)

    def set_company_news(self, ticker: str, data: list[dict[str, any]]):
        """Append new company news to cache."""
        self._company_news_cache[ticker] = self._merge_data(self._company_news_cache.get(ticker), data, key_field="date")


# Global cache instance
_cache = Cache()


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache
