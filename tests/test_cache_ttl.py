import pytest
import threading
import time

from src.data.cache import _TTLCache, Cache


class TestTTLCache:
    """Test _TTLCache LRU + TTL behavior."""

    def test_basic_set_get(self):
        cache = _TTLCache(max_entries=10, ttl=60)
        cache.set("key", [{"x": 1}])
        result = cache.get("key")
        assert result == [{"x": 1}]

    def test_max_entries_eviction(self):
        """Evicts oldest entry when capacity is exceeded."""
        cache = _TTLCache(max_entries=3, ttl=60)
        cache.set("a", [{"x": 1}])
        cache.set("b", [{"x": 2}])
        cache.set("c", [{"x": 3}])
        cache.set("d", [{"x": 4}])
        assert cache.get("a") is None
        assert cache.get("d") is not None

    def test_ttl_expiration(self):
        """get() returns None after TTL expires."""
        cache = _TTLCache(max_entries=10, ttl=1)
        cache.set("key", [{"x": 1}])
        assert cache.get("key") is not None
        time.sleep(1.1)
        assert cache.get("key") is None

    def test_lru_order(self):
        """Recently accessed entry is not evicted."""
        cache = _TTLCache(max_entries=3, ttl=60)
        cache.set("a", [{"x": 1}])
        cache.set("b", [{"x": 2}])
        cache.set("c", [{"x": 3}])
        cache.get("a")  # access a, moves it to end
        cache.set("d", [{"x": 4}])  # should evict b (oldest untouched)
        assert cache.get("a") is not None
        assert cache.get("b") is None

    def test_get_returns_copy(self):
        """get() returns a shallow copy so mutations do not affect the cache."""
        cache = _TTLCache(max_entries=10, ttl=60)
        cache.set("key", [{"x": 1}])
        result = cache.get("key")
        result.append({"x": 2})
        assert len(cache.get("key")) == 1

    def test_get_nonexistent_key(self):
        cache = _TTLCache(max_entries=10, ttl=60)
        assert cache.get("nonexistent") is None

    def test_overwrite_existing_key(self):
        cache = _TTLCache(max_entries=10, ttl=60)
        cache.set("key", [{"x": 1}])
        cache.set("key", [{"x": 2}])
        assert cache.get("key") == [{"x": 2}]

    def test_overwrite_does_not_reduce_capacity(self):
        """Overwriting a key should not count as an extra entry."""
        cache = _TTLCache(max_entries=2, ttl=60)
        cache.set("a", [{"x": 1}])
        cache.set("b", [{"x": 2}])
        cache.set("a", [{"x": 10}])  # overwrite, not a new entry
        assert cache.get("a") == [{"x": 10}]
        assert cache.get("b") is not None

    def test_thread_safety(self):
        """Concurrent set/get operations do not raise exceptions."""
        cache = _TTLCache(max_entries=100, ttl=60)
        errors = []

        def worker(n):
            try:
                for i in range(50):
                    cache.set(f"key_{n}_{i}", [{"v": i}])
                    cache.get(f"key_{n}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


class TestCacheIntegration:
    """Test Cache high-level methods (prices with merge/dedup)."""

    def test_cache_set_get_prices(self):
        cache = Cache()
        cache.set_prices("AAPL", [{"time": "2024-01-01", "close": 100}])
        result = cache.get_prices("AAPL")
        assert result is not None
        assert len(result) == 1

    def test_cache_merge_dedup(self):
        cache = Cache()
        cache.set_prices("AAPL", [{"time": "2024-01-01", "close": 100}])
        cache.set_prices("AAPL", [{"time": "2024-01-01", "close": 101}, {"time": "2024-01-02", "close": 102}])
        result = cache.get_prices("AAPL")
        # Dedup on "time": 2024-01-01 already exists, so only 2024-01-02 is added
        assert len(result) == 2
        # Original value for 2024-01-01 is preserved
        assert result[0]["close"] == 100

    def test_cache_get_prices_returns_none_when_empty(self):
        cache = Cache()
        assert cache.get_prices("AAPL") is None
