"""Comprehensive tests for enhanced cache functionality."""

import time
import threading
import pytest
from unittest.mock import patch

from src.data.cache import Cache, CacheStats
from src.data.cache_decorators import cached, get_decorator_cache
from src.data.cache_cleaner import CacheCleaner


@pytest.fixture(autouse=True)
def clear_decorator_cache():
    """Clear decorator cache before each test."""
    get_decorator_cache().clear()
    yield
    get_decorator_cache().clear()


class TestCacheStats:
    """Test cache statistics functionality."""

    def test_cache_stats_initialization(self):
        """Test CacheStats initialization."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.total == 0
        assert stats.hit_rate == 0.0

    def test_cache_stats_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats(hits=8, misses=2)
        assert stats.total == 10
        assert stats.hit_rate == 0.8

    def test_cache_stats_no_operations(self):
        """Test hit rate with no operations."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0


class TestCacheTTL:
    """Test cache TTL (time-to-live) functionality."""

    def test_cache_initialization_with_ttl(self):
        """Test cache initialization with custom TTL."""
        cache = Cache(ttl=600)
        assert cache._ttl == 600

    def test_cache_default_ttl(self):
        """Test cache with default TTL."""
        cache = Cache()
        assert cache._ttl == 300

    def test_cache_hit_within_ttl(self):
        """Test cache hit when data is within TTL."""
        cache = Cache(ttl=10)
        test_data = [{"time": "2024-01-01", "price": 100.0}]

        cache.set_prices("AAPL", test_data)
        result = cache.get_prices("AAPL")

        assert result is not None
        assert len(result) == 1
        assert result[0]["price"] == 100.0
        assert cache.stats.hits == 1
        assert cache.stats.misses == 0

    def test_cache_miss_after_ttl_expired(self):
        """Test cache miss when data has expired."""
        cache = Cache(ttl=1)  # 1 second TTL
        test_data = [{"time": "2024-01-01", "price": 100.0}]

        cache.set_prices("AAPL", test_data)
        time.sleep(1.1)  # Wait for expiration

        result = cache.get_prices("AAPL")

        assert result is None
        assert cache.stats.hits == 0
        assert cache.stats.misses == 1

    def test_cache_miss_nonexistent_key(self):
        """Test cache miss for non-existent key."""
        cache = Cache()
        result = cache.get_prices("NONEXISTENT")

        assert result is None
        assert cache.stats.hits == 0
        assert cache.stats.misses == 1


class TestCacheStatistics:
    """Test cache statistics tracking."""

    def test_statistics_tracking(self):
        """Test that cache tracks hits and misses correctly."""
        cache = Cache(ttl=10)
        test_data = [{"time": "2024-01-01", "price": 100.0}]

        # First access - miss
        cache.get_prices("AAPL")
        assert cache.stats.hits == 0
        assert cache.stats.misses == 1

        # Set data
        cache.set_prices("AAPL", test_data)

        # Second access - hit
        cache.get_prices("AAPL")
        assert cache.stats.hits == 1
        assert cache.stats.misses == 1

        # Third access - hit
        cache.get_prices("AAPL")
        assert cache.stats.hits == 2
        assert cache.stats.misses == 1

    def test_get_stats_method(self):
        """Test get_stats returns correct statistics."""
        cache = Cache(ttl=300)
        test_data = [{"time": "2024-01-01", "price": 100.0}]

        cache.set_prices("AAPL", test_data)
        cache.get_prices("AAPL")  # Hit
        cache.get_prices("MSFT")  # Miss

        stats = cache.get_stats()

        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['total'] == 2
        assert stats['hit_rate'] == "50.00%"
        assert stats['prices_size'] == 1
        assert stats['ttl'] == 300


class TestCacheCleanup:
    """Test automatic cache cleanup functionality."""

    def test_cleanup_expired_entries(self):
        """Test manual cleanup of expired entries."""
        cache = Cache(ttl=1)
        test_data1 = [{"time": "2024-01-01", "price": 100.0}]
        test_data2 = [{"time": "2024-01-02", "price": 101.0}]

        # Add data
        cache.set_prices("AAPL", test_data1)
        cache.set_prices("MSFT", test_data2)

        # Wait for expiration
        time.sleep(1.1)

        # Cleanup
        removed = cache.cleanup_expired()

        assert removed == 2
        assert len(cache._prices_cache) == 0

    def test_cleanup_no_expired_entries(self):
        """Test cleanup when no entries are expired."""
        cache = Cache(ttl=10)
        test_data = [{"time": "2024-01-01", "price": 100.0}]

        cache.set_prices("AAPL", test_data)
        removed = cache.cleanup_expired()

        assert removed == 0
        assert len(cache._prices_cache) == 1

    def test_cleanup_mixed_expired_and_valid(self):
        """Test cleanup with mix of expired and valid entries."""
        cache = Cache(ttl=2)
        test_data1 = [{"time": "2024-01-01", "price": 100.0}]
        test_data2 = [{"time": "2024-01-02", "price": 101.0}]

        # Add first entry
        cache.set_prices("AAPL", test_data1)

        # Wait
        time.sleep(1.1)

        # Add second entry (will not be expired)
        cache.set_prices("MSFT", test_data2)

        # Wait for first to expire
        time.sleep(1)

        # Cleanup
        removed = cache.cleanup_expired()

        assert removed == 1
        assert len(cache._prices_cache) == 1
        assert cache.get_prices("MSFT") is not None


class TestCacheConcurrency:
    """Test cache thread safety."""

    def test_concurrent_reads_and_writes(self):
        """Test concurrent access to cache."""
        cache = Cache(ttl=10)
        test_data = [{"time": "2024-01-01", "price": 100.0}]
        errors = []

        def writer():
            try:
                for i in range(50):
                    cache.set_prices(f"TICKER{i}", test_data)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(50):
                    cache.get_prices(f"TICKER{i}")
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=writer))
            threads.append(threading.Thread(target=reader))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # No errors should occur
        assert len(errors) == 0

    def test_concurrent_cleanup(self):
        """Test concurrent cleanup operations."""
        cache = Cache(ttl=1)
        test_data = [{"time": "2024-01-01", "price": 100.0}]
        errors = []

        # Populate cache
        for i in range(10):
            cache.set_prices(f"TICKER{i}", test_data)

        time.sleep(1.1)

        def cleanup():
            try:
                cache.cleanup_expired()
            except Exception as e:
                errors.append(e)

        # Start multiple cleanup threads
        threads = [threading.Thread(target=cleanup) for _ in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert len(cache._prices_cache) == 0


class TestCacheDecorators:
    """Test cache decorator functionality."""

    def test_cached_decorator_basic(self):
        """Test basic cached decorator functionality."""
        call_count = [0]

        @cached(ttl=10)
        def expensive_function(x):
            call_count[0] += 1
            return x * 2

        # First call - cache miss
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count[0] == 1

        # Second call - cache hit
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count[0] == 1  # Function not called again

    def test_cached_decorator_different_args(self):
        """Test cached decorator with different arguments."""
        call_count = [0]

        @cached(ttl=10)
        def expensive_function(x):
            call_count[0] += 1
            return x * 2

        result1 = expensive_function(5)
        result2 = expensive_function(10)

        assert result1 == 10
        assert result2 == 20
        assert call_count[0] == 2  # Called twice for different args

    def test_cached_decorator_expiration(self):
        """Test cached decorator with expiration."""
        call_count = [0]

        @cached(ttl=1)
        def expensive_function(x):
            call_count[0] += 1
            return x * 2

        # First call
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count[0] == 1

        # Wait for expiration
        time.sleep(1.1)

        # Second call - cache expired
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count[0] == 2

    def test_cached_decorator_with_prefix(self):
        """Test cached decorator with key prefix."""
        call_count = [0]

        @cached(ttl=10, key_prefix="api:")
        def fetch_data(ticker):
            call_count[0] += 1
            return f"data for {ticker}"

        result1 = fetch_data("AAPL")
        result2 = fetch_data("AAPL")

        assert result1 == "data for AAPL"
        assert result2 == "data for AAPL"
        assert call_count[0] == 1

    def test_cached_decorator_cache_clear(self):
        """Test cache clear method on decorated function."""
        call_count = [0]

        @cached(ttl=10)
        def expensive_function(x):
            call_count[0] += 1
            return x * 2

        expensive_function(5)
        assert call_count[0] == 1

        # Clear cache
        expensive_function.cache_clear()

        # Should call function again
        expensive_function(5)
        assert call_count[0] == 2


class TestCacheCleaner:
    """Test automatic cache cleaner."""

    def test_cache_cleaner_initialization(self):
        """Test CacheCleaner initialization."""
        cache = Cache(ttl=1)
        cleaner = CacheCleaner(cache, interval=5)

        assert cleaner.cache is cache
        assert cleaner.interval == 5
        assert not cleaner.is_running()

    def test_cache_cleaner_start_stop(self):
        """Test starting and stopping cache cleaner."""
        cache = Cache(ttl=1)
        cleaner = CacheCleaner(cache, interval=1)

        cleaner.start()
        assert cleaner.is_running()

        cleaner.stop()
        assert not cleaner.is_running()

    def test_cache_cleaner_auto_cleanup(self):
        """Test automatic cleanup by cleaner."""
        cache = Cache(ttl=1)
        test_data = [{"time": "2024-01-01", "price": 100.0}]

        # Add data
        cache.set_prices("AAPL", test_data)

        # Start cleaner with short interval
        cleaner = CacheCleaner(cache, interval=1)
        cleaner.start()

        # Wait for data to expire and cleanup to run
        time.sleep(2.5)

        cleaner.stop()

        # Cache should be empty
        assert len(cache._prices_cache) == 0

    def test_cache_cleaner_context_manager(self):
        """Test CacheCleaner as context manager."""
        cache = Cache(ttl=1)
        test_data = [{"time": "2024-01-01", "price": 100.0}]

        with CacheCleaner(cache, interval=1) as cleaner:
            assert cleaner.is_running()
            cache.set_prices("AAPL", test_data)

        # Should be stopped after context
        assert not cleaner.is_running()


class TestCacheAllDataTypes:
    """Test cache functionality for all data types."""

    def test_financial_metrics_cache(self):
        """Test financial metrics caching."""
        cache = Cache(ttl=10)
        test_data = [{"report_period": "2024-Q1", "revenue": 1000000}]

        cache.set_financial_metrics("AAPL", test_data)
        result = cache.get_financial_metrics("AAPL")

        assert result is not None
        assert len(result) == 1
        assert result[0]["revenue"] == 1000000

    def test_line_items_cache(self):
        """Test line items caching."""
        cache = Cache(ttl=10)
        test_data = [{"report_period": "2024-Q1", "item": "cost_of_revenue"}]

        cache.set_line_items("AAPL", test_data)
        result = cache.get_line_items("AAPL")

        assert result is not None
        assert len(result) == 1

    def test_insider_trades_cache(self):
        """Test insider trades caching."""
        cache = Cache(ttl=10)
        test_data = [{"filing_date": "2024-01-01", "shares": 1000}]

        cache.set_insider_trades("AAPL", test_data)
        result = cache.get_insider_trades("AAPL")

        assert result is not None
        assert len(result) == 1

    def test_company_news_cache(self):
        """Test company news caching."""
        cache = Cache(ttl=10)
        test_data = [{"date": "2024-01-01", "title": "Company announces earnings"}]

        cache.set_company_news("AAPL", test_data)
        result = cache.get_company_news("AAPL")

        assert result is not None
        assert len(result) == 1


class TestCacheClear:
    """Test cache clear functionality."""

    def test_clear_all_caches(self):
        """Test clearing all cache types."""
        cache = Cache(ttl=10)

        # Populate all cache types
        cache.set_prices("AAPL", [{"time": "2024-01-01", "price": 100.0}])
        cache.set_financial_metrics("AAPL", [{"report_period": "2024-Q1", "revenue": 1000000}])
        cache.set_line_items("AAPL", [{"report_period": "2024-Q1", "item": "revenue"}])
        cache.set_insider_trades("AAPL", [{"filing_date": "2024-01-01", "shares": 1000}])
        cache.set_company_news("AAPL", [{"date": "2024-01-01", "title": "News"}])

        # Clear all
        cache.clear()

        # All should be empty
        assert len(cache._prices_cache) == 0
        assert len(cache._financial_metrics_cache) == 0
        assert len(cache._line_items_cache) == 0
        assert len(cache._insider_trades_cache) == 0
        assert len(cache._company_news_cache) == 0

    def test_clear_resets_statistics(self):
        """Test that clear resets statistics."""
        cache = Cache(ttl=10)
        test_data = [{"time": "2024-01-01", "price": 100.0}]

        cache.set_prices("AAPL", test_data)
        cache.get_prices("AAPL")
        cache.get_prices("MSFT")

        assert cache.stats.hits > 0 or cache.stats.misses > 0

        cache.clear()

        assert cache.stats.hits == 0
        assert cache.stats.misses == 0


class TestCacheMergeData:
    """Test cache data merging functionality."""

    def test_merge_data_no_duplicates(self):
        """Test that merge avoids duplicates."""
        cache = Cache(ttl=10)

        # First set
        data1 = [{"time": "2024-01-01", "price": 100.0}]
        cache.set_prices("AAPL", data1)

        # Second set with same time (should not duplicate)
        data2 = [{"time": "2024-01-01", "price": 101.0}]
        cache.set_prices("AAPL", data2)

        result = cache.get_prices("AAPL")

        # Should only have one entry (first one, not overwritten)
        assert len(result) == 1
        assert result[0]["price"] == 100.0

    def test_merge_data_new_entries(self):
        """Test that merge adds new entries."""
        cache = Cache(ttl=10)

        # First set
        data1 = [{"time": "2024-01-01", "price": 100.0}]
        cache.set_prices("AAPL", data1)

        # Second set with different time
        data2 = [{"time": "2024-01-02", "price": 101.0}]
        cache.set_prices("AAPL", data2)

        result = cache.get_prices("AAPL")

        # Should have both entries
        assert len(result) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
