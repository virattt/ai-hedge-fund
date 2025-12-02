"""
Tests for the cache module.

This module tests the in-memory caching functionality including:
- Basic get/set operations
- TTL-based expiration
- Data deduplication on merge
- Cache cleanup
"""

import time
import pytest
from unittest.mock import patch

from src.data.cache import Cache, CacheEntry, get_cache


class TestCacheEntry:
    """Tests for the CacheEntry class."""

    def test_cache_entry_creation(self):
        """Test that a cache entry is created with correct data."""
        data = [{"time": "2024-01-01", "price": 100.0}]
        entry = CacheEntry(data, ttl_seconds=3600)
        
        assert entry.data == data
        assert entry.ttl_seconds == 3600
        assert entry.created_at <= time.time()

    def test_cache_entry_not_expired(self):
        """Test that a fresh cache entry is not expired."""
        data = [{"time": "2024-01-01", "price": 100.0}]
        entry = CacheEntry(data, ttl_seconds=3600)
        
        assert entry.is_expired() is False

    def test_cache_entry_expired(self):
        """Test that an old cache entry is correctly marked as expired."""
        data = [{"time": "2024-01-01", "price": 100.0}]
        entry = CacheEntry(data, ttl_seconds=1)
        
        # Mock time to simulate expiration
        with patch.object(entry, 'created_at', time.time() - 2):
            assert entry.is_expired() is True

    def test_cache_entry_with_zero_ttl(self):
        """Test that a cache entry with zero TTL expires immediately."""
        data = [{"time": "2024-01-01", "price": 100.0}]
        entry = CacheEntry(data, ttl_seconds=0)
        
        # Even with 0 TTL, it shouldn't be expired in the same instant
        # But after any time passes, it should be
        with patch.object(entry, 'created_at', time.time() - 0.001):
            assert entry.is_expired() is True


class TestCachePrices:
    """Tests for price caching functionality."""

    def test_set_and_get_prices(self):
        """Test basic set and get for prices."""
        cache = Cache()
        prices = [
            {"time": "2024-01-01", "close": 100.0},
            {"time": "2024-01-02", "close": 101.0},
        ]
        
        cache.set_prices("AAPL", prices)
        result = cache.get_prices("AAPL")
        
        assert result == prices

    def test_get_prices_returns_none_for_missing_ticker(self):
        """Test that getting prices for a non-existent ticker returns None."""
        cache = Cache()
        
        result = cache.get_prices("UNKNOWN")
        
        assert result is None

    def test_prices_expiration(self):
        """Test that expired price data is not returned."""
        cache = Cache()
        prices = [{"time": "2024-01-01", "close": 100.0}]
        
        cache.set_prices("AAPL", prices)
        
        # Mock the cache entry to be expired
        cache._prices_cache["AAPL"].created_at = time.time() - cache.DEFAULT_TTL - 1
        
        result = cache.get_prices("AAPL")
        
        assert result is None

    def test_prices_merge_deduplication(self):
        """Test that duplicate prices are not added on merge."""
        cache = Cache()
        
        # Set initial prices
        initial_prices = [
            {"time": "2024-01-01", "close": 100.0},
            {"time": "2024-01-02", "close": 101.0},
        ]
        cache.set_prices("AAPL", initial_prices)
        
        # Add overlapping + new prices
        new_prices = [
            {"time": "2024-01-02", "close": 101.0},  # Duplicate
            {"time": "2024-01-03", "close": 102.0},  # New
        ]
        cache.set_prices("AAPL", new_prices)
        
        result = cache.get_prices("AAPL")
        
        # Should have 3 unique entries, not 4
        assert len(result) == 3
        times = [p["time"] for p in result]
        assert times == ["2024-01-01", "2024-01-02", "2024-01-03"]


class TestCacheFinancialMetrics:
    """Tests for financial metrics caching functionality."""

    def test_set_and_get_financial_metrics(self):
        """Test basic set and get for financial metrics."""
        cache = Cache()
        metrics = [
            {"report_period": "2024-Q1", "revenue": 1000000},
            {"report_period": "2024-Q2", "revenue": 1100000},
        ]
        
        cache.set_financial_metrics("AAPL", metrics)
        result = cache.get_financial_metrics("AAPL")
        
        assert result == metrics

    def test_financial_metrics_uses_longer_ttl(self):
        """Test that financial metrics use the METRICS_TTL (24 hours)."""
        cache = Cache()
        metrics = [{"report_period": "2024-Q1", "revenue": 1000000}]
        
        cache.set_financial_metrics("AAPL", metrics)
        
        # Should still be valid after DEFAULT_TTL (1 hour)
        cache._financial_metrics_cache["AAPL"].created_at = time.time() - cache.DEFAULT_TTL - 1
        result = cache.get_financial_metrics("AAPL")
        
        assert result is not None  # Still valid because METRICS_TTL > DEFAULT_TTL


class TestCacheCompanyNews:
    """Tests for company news caching functionality."""

    def test_set_and_get_company_news(self):
        """Test basic set and get for company news."""
        cache = Cache()
        news = [
            {"date": "2024-01-01", "title": "News 1"},
            {"date": "2024-01-02", "title": "News 2"},
        ]
        
        cache.set_company_news("AAPL", news)
        result = cache.get_company_news("AAPL")
        
        assert result == news

    def test_company_news_uses_shorter_ttl(self):
        """Test that company news uses the shorter NEWS_TTL (30 minutes)."""
        cache = Cache()
        news = [{"date": "2024-01-01", "title": "Breaking News"}]
        
        cache.set_company_news("AAPL", news)
        
        # Should be expired after NEWS_TTL
        cache._company_news_cache["AAPL"].created_at = time.time() - cache.NEWS_TTL - 1
        result = cache.get_company_news("AAPL")
        
        assert result is None


class TestCacheInsiderTrades:
    """Tests for insider trades caching functionality."""

    def test_set_and_get_insider_trades(self):
        """Test basic set and get for insider trades."""
        cache = Cache()
        trades = [
            {"filing_date": "2024-01-01", "shares": 1000},
            {"filing_date": "2024-01-02", "shares": 500},
        ]
        
        cache.set_insider_trades("AAPL", trades)
        result = cache.get_insider_trades("AAPL")
        
        assert result == trades

    def test_insider_trades_merge_deduplication(self):
        """Test that duplicate insider trades are not added."""
        cache = Cache()
        
        initial_trades = [{"filing_date": "2024-01-01", "shares": 1000}]
        cache.set_insider_trades("AAPL", initial_trades)
        
        new_trades = [
            {"filing_date": "2024-01-01", "shares": 1000},  # Duplicate
            {"filing_date": "2024-01-02", "shares": 500},   # New
        ]
        cache.set_insider_trades("AAPL", new_trades)
        
        result = cache.get_insider_trades("AAPL")
        
        assert len(result) == 2


class TestCacheLineItems:
    """Tests for line items caching functionality."""

    def test_set_and_get_line_items(self):
        """Test basic set and get for line items."""
        cache = Cache()
        line_items = [
            {"report_period": "2024-Q1", "net_income": 50000},
            {"report_period": "2024-Q2", "net_income": 55000},
        ]
        
        cache.set_line_items("AAPL", line_items)
        result = cache.get_line_items("AAPL")
        
        assert result == line_items


class TestCacheClear:
    """Tests for cache clearing functionality."""

    def test_clear_removes_all_data(self):
        """Test that clear() removes all cached data."""
        cache = Cache()
        
        # Populate all cache types
        cache.set_prices("AAPL", [{"time": "2024-01-01", "close": 100}])
        cache.set_financial_metrics("AAPL", [{"report_period": "2024-Q1", "revenue": 1000}])
        cache.set_line_items("AAPL", [{"report_period": "2024-Q1", "net_income": 100}])
        cache.set_insider_trades("AAPL", [{"filing_date": "2024-01-01", "shares": 100}])
        cache.set_company_news("AAPL", [{"date": "2024-01-01", "title": "News"}])
        
        cache.clear()
        
        assert cache.get_prices("AAPL") is None
        assert cache.get_financial_metrics("AAPL") is None
        assert cache.get_line_items("AAPL") is None
        assert cache.get_insider_trades("AAPL") is None
        assert cache.get_company_news("AAPL") is None


class TestCacheMergeData:
    """Tests for the _merge_data helper method."""

    def test_merge_with_none_existing(self):
        """Test merge when existing data is None."""
        cache = Cache()
        new_data = [{"time": "2024-01-01", "value": 1}]
        
        result = cache._merge_data(None, new_data, "time")
        
        assert result == new_data

    def test_merge_with_empty_existing(self):
        """Test merge when existing data is empty list."""
        cache = Cache()
        new_data = [{"time": "2024-01-01", "value": 1}]
        
        # Empty list is falsy, so treated same as None
        result = cache._merge_data([], new_data, "time")
        
        assert result == new_data

    def test_merge_preserves_order(self):
        """Test that merge preserves order of existing data."""
        cache = Cache()
        existing = [
            {"time": "2024-01-01", "value": 1},
            {"time": "2024-01-02", "value": 2},
        ]
        new_data = [{"time": "2024-01-03", "value": 3}]
        
        result = cache._merge_data(existing, new_data, "time")
        
        assert result[0]["time"] == "2024-01-01"
        assert result[1]["time"] == "2024-01-02"
        assert result[2]["time"] == "2024-01-03"


class TestCacheCleanupExpired:
    """Tests for expired entry cleanup."""

    def test_cleanup_removes_expired_entries(self):
        """Test that cleanup removes expired entries from cache."""
        cache = Cache()
        
        # Add two tickers
        cache.set_prices("AAPL", [{"time": "2024-01-01", "close": 100}])
        cache.set_prices("GOOGL", [{"time": "2024-01-01", "close": 200}])
        
        # Expire only AAPL
        cache._prices_cache["AAPL"].created_at = time.time() - cache.DEFAULT_TTL - 1
        
        # Access GOOGL (this triggers cleanup)
        result = cache.get_prices("GOOGL")
        
        # GOOGL should still be there
        assert result is not None
        # AAPL should be cleaned up
        assert "AAPL" not in cache._prices_cache


class TestGlobalCache:
    """Tests for the global cache instance."""

    def test_get_cache_returns_cache_instance(self):
        """Test that get_cache returns a Cache instance."""
        cache = get_cache()
        
        assert isinstance(cache, Cache)

    def test_get_cache_returns_same_instance(self):
        """Test that get_cache returns the same global instance."""
        cache1 = get_cache()
        cache2 = get_cache()
        
        assert cache1 is cache2


class TestCacheMultipleTickers:
    """Tests for caching data for multiple tickers."""

    def test_different_tickers_stored_separately(self):
        """Test that different tickers have separate cache entries."""
        cache = Cache()
        
        aapl_prices = [{"time": "2024-01-01", "close": 100}]
        googl_prices = [{"time": "2024-01-01", "close": 200}]
        
        cache.set_prices("AAPL", aapl_prices)
        cache.set_prices("GOOGL", googl_prices)
        
        assert cache.get_prices("AAPL")[0]["close"] == 100
        assert cache.get_prices("GOOGL")[0]["close"] == 200

    def test_updating_one_ticker_doesnt_affect_others(self):
        """Test that updating one ticker doesn't affect other tickers."""
        cache = Cache()
        
        cache.set_prices("AAPL", [{"time": "2024-01-01", "close": 100}])
        cache.set_prices("GOOGL", [{"time": "2024-01-01", "close": 200}])
        
        # Update AAPL
        cache.set_prices("AAPL", [{"time": "2024-01-02", "close": 110}])
        
        # GOOGL should be unchanged
        googl_result = cache.get_prices("GOOGL")
        assert len(googl_result) == 1
        assert googl_result[0]["close"] == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
