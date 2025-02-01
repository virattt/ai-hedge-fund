from datetime import datetime
from typing import Any

from .base import AbstractCache, T


class MemoryCache(AbstractCache[T]):
    """Simple in-memory cache implementation with TTL, size limits, and namespaced keys."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self._cache: dict[
            str, tuple[T, datetime, int]
        ] = {}  # (value, timestamp, access_count)
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> T | None:
        """
        Get value from cache if it exists and hasn't expired.

        Args:
            key: Cache key to retrieve

        Returns:
            Cached value if found and valid, None otherwise
        """
        if entry := self._cache.get(key):
            value, timestamp, access_count = entry
            age = (datetime.now() - timestamp).total_seconds()

            if age < self._ttl_seconds:
                self._hits += 1
                self._cache[key] = (value, timestamp, access_count + 1)
                return value

            self.remove(key)

        self._misses += 1
        return None

    def set(self, key: str, value: T) -> None:
        """
        Set value in cache with current timestamp.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = (value, datetime.now(), 0)
        if len(self._cache) > self._max_size:
            self._evict_entries()

    def clear(self) -> None:
        """Remove all entries from cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def remove(self, key: str) -> None:
        """
        Remove specific key from cache.

        Args:
            key: Cache key to remove
        """
        self._cache.pop(key, None)

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        total_requests = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl_seconds": self._ttl_seconds,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total_requests if total_requests > 0 else 0,
        }

    def _evict_entries(self) -> None:
        """Remove least recently used entries when cache is full."""
        # Sort by access count (primary) and timestamp (secondary)
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: (x[1][2], x[1][1]),  # access_count, timestamp
        )

        # Remove 10% of the least accessed items
        num_to_remove = max(1, len(self._cache) // 10)
        for key, _ in sorted_items[:num_to_remove]:
            self.remove(key)
