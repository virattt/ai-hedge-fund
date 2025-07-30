"""Comprehensive tests for cache functionality."""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.data.cache_factory import CacheFactory, CacheType
from src.data.memory_cache import MemoryCache
from src.data.cache_monitor import get_cache_monitor
from src.data.cache_validator import validate_cache_entry


class TestCacheFactory:
    """Test cache factory functionality."""

    def test_memory_cache_creation(self):
        """Test memory cache creation."""
        cache = CacheFactory.create_cache(CacheType.MEMORY)
        assert isinstance(cache, MemoryCache)

    def test_duckdb_cache_creation(self):
        """Test DuckDB cache creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            cache = CacheFactory.create_cache(CacheType.DUCKDB, db_path=db_path)
            assert cache is not None
            cache.close()

    def test_singleton_behavior(self):
        """Test that cache factory returns the same instance."""
        CacheFactory.reset_instance()
        cache1 = CacheFactory.get_cache()
        cache2 = CacheFactory.get_cache()
        assert cache1 is cache2

    def test_ttl_parameter_passing(self):
        """Test that TTL parameters are passed correctly."""
        CacheFactory.reset_instance()
        cache = CacheFactory.create_cache(CacheType.MEMORY, ttl_seconds=3600)
        assert cache._ttl_seconds == 3600


class TestMemoryCache:
    """Test memory cache functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cache = MemoryCache()
        self.test_data = [
            {"time": "2023-01-01", "open": 100.0, "close": 101.0, "high": 102.0, "low": 99.0, "volume": 1000},
            {"time": "2023-01-02", "open": 101.0, "close": 102.0, "high": 103.0, "low": 100.0, "volume": 1100}
        ]

    def test_cache_set_and_get_prices(self):
        """Test setting and getting price data."""
        cache_key = "AAPL_2023-01-01_2023-01-02"
        self.cache.set_prices(cache_key, self.test_data)
        result = self.cache.get_prices(cache_key)
        assert result == self.test_data

    def test_cache_miss(self):
        """Test cache miss returns None."""
        result = self.cache.get_prices("nonexistent_key")
        assert result is None

    def test_data_merging(self):
        """Test that data is properly merged to avoid duplicates."""
        cache_key = "AAPL_2023-01-01_2023-01-02"

        # Add initial data
        self.cache.set_prices(cache_key, self.test_data[:1])

        # Add overlapping data
        self.cache.set_prices(cache_key, self.test_data)

        result = self.cache.get_prices(cache_key)
        assert len(result) == 2  # Should not have duplicates

    def test_ttl_functionality(self):
        """Test TTL functionality."""
        cache = MemoryCache(ttl_seconds=1)
        cache_key = "test_ttl"

        cache.set_prices(cache_key, self.test_data)

        # Should be available immediately
        result = cache.get_prices(cache_key)
        assert result == self.test_data

        # Mock time to simulate expiration
        with patch('src.data.memory_cache.datetime') as mock_datetime:
            future_time = datetime.now() + timedelta(seconds=2)
            mock_datetime.now.return_value = future_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            result = cache.get_prices(cache_key)
            assert result is None

    def test_cleanup_expired(self):
        """Test cleanup of expired entries."""
        cache = MemoryCache(ttl_seconds=1)
        cache_key = "test_cleanup"

        cache.set_prices(cache_key, self.test_data)

        # Mock time to simulate expiration
        with patch('src.data.memory_cache.datetime') as mock_datetime:
            future_time = datetime.now() + timedelta(seconds=2)
            mock_datetime.now.return_value = future_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            cache.cleanup_expired()
            assert cache_key not in cache._prices_cache


class TestCacheMonitor:
    """Test cache monitoring functionality."""

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        monitor = get_cache_monitor()
        monitor.reset_stats()

        monitor.record_hit()
        monitor.record_hit()
        monitor.record_miss()

        assert round(monitor.get_hit_rate(), 2) == 66.67  # 2/3 * 100, rounded    def test_stats_collection(self):
        """Test stats collection."""
        monitor = get_cache_monitor()
        monitor.reset_stats()

        monitor.record_hit()
        monitor.record_miss()

        stats = monitor.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert "hit_rate" in stats
        assert "last_cleanup" in stats


class TestCacheValidator:
    """Test cache validation functionality."""

    def test_data_integrity_validation(self):
        """Test data integrity validation."""
        valid_data = [
            {"time": "2023-01-01", "open": 100.0, "close": 101.0, "high": 102.0, "low": 99.0, "volume": 1000}
        ]

        invalid_data = [
            {"open": 100.0, "close": 101.0}  # Missing required fields
        ]

        assert validate_cache_entry("prices", "test_key", valid_data) is True
        assert validate_cache_entry("prices", "test_key", invalid_data) is False

    def test_json_serializable_validation(self):
        """Test JSON serialization validation."""
        # Valid data
        valid_data = [{"time": "2023-01-01T00:00:00", "open": 100.0, "high": 105.0,
                      "low": 95.0, "close": 102.0, "volume": 1000}]
        assert validate_cache_entry("prices", "test_key", valid_data) is True

        # Invalid data (contains non-serializable object)
        invalid_data = [{"time": "2023-01-01", "value": set()}]
        assert validate_cache_entry("prices", "test_key", invalid_data) is False


class TestCacheIntegration:
    """Integration tests for cache system."""

    def test_api_cache_integration(self):
        """Test cache integration with API calls."""
        from src.tools.api import get_prices

        with patch('src.tools.api._make_api_request') as mock_request:
            # Mock API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "ticker": "AAPL",
                "prices": [
                    {"time": "2023-01-01", "open": 100.0, "close": 101.0, "high": 102.0, "low": 99.0, "volume": 1000}
                ]
            }
            mock_request.return_value = mock_response

            # First call should hit API
            result1 = get_prices("AAPL", "2023-01-01", "2023-01-01")
            assert len(result1) == 1
            assert mock_request.call_count == 1

            # Second call should hit cache
            result2 = get_prices("AAPL", "2023-01-01", "2023-01-01")
            assert len(result2) == 1
            assert mock_request.call_count == 1  # Should not have increased

    def test_line_item_search_caching(self):
        """Test line item search caching."""
        from src.tools.api import search_line_items

        with patch('src.tools.api._make_api_request') as mock_request:
            # Mock API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "search_results": [
                    {"ticker": "AAPL", "report_period": "2023-12-31", "period": "annual", "revenue": 1000000, "currency": "USD"}
                ]
            }
            mock_request.return_value = mock_response

            # First call should hit API
            result1 = search_line_items("AAPL", ["revenue"], "2023-12-31")
            assert len(result1) == 1
            assert mock_request.call_count == 1

            # Second call should hit cache
            result2 = search_line_items("AAPL", ["revenue"], "2023-12-31")
            assert len(result2) == 1
            assert mock_request.call_count == 1  # Should not have increased


@pytest.fixture(autouse=True)
def reset_cache_factory():
    """Reset cache factory before each test."""
    CacheFactory.reset_instance()
    yield
    CacheFactory.reset_instance()
