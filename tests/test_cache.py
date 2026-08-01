import pytest
import threading
import time

from src.data.cache import _TTLCache, Cache, get_cache


class TestTTLCache:
    """Test the _TTLCache low-level implementation."""

    def test_max_entries_eviction(self):
        """Exceeding capacity evicts the oldest entry."""
        cache = _TTLCache(max_entries=3, ttl=60)
        cache.set("a", [{"x": 1}])
        cache.set("b", [{"x": 2}])
        cache.set("c", [{"x": 3}])
        cache.set("d", [{"x": 4}])  # should evict "a"
        assert cache.get("a") is None
        assert cache.get("d") is not None

    def test_ttl_expiration(self):
        """Expired entries return None on get."""
        cache = _TTLCache(max_entries=10, ttl=1)  # 1-second TTL
        cache.set("key", [{"x": 1}])
        assert cache.get("key") is not None
        time.sleep(1.1)
        assert cache.get("key") is None

    def test_lru_order(self):
        """Recently accessed entries are not evicted."""
        cache = _TTLCache(max_entries=3, ttl=60)
        cache.set("a", [{"x": 1}])
        cache.set("b", [{"x": 2}])
        cache.set("c", [{"x": 3}])
        cache.get("a")  # touch "a" so it becomes most-recently-used
        cache.set("d", [{"x": 4}])  # should evict "b" (least-recently-used)
        assert cache.get("a") is not None
        assert cache.get("b") is None

    def test_get_returns_copy(self):
        """get() returns a shallow copy; mutating it does not affect the cache."""
        cache = _TTLCache(max_entries=10, ttl=60)
        cache.set("key", [{"x": 1}])
        result = cache.get("key")
        result.append({"x": 2})
        assert len(cache.get("key")) == 1  # internal data unmodified

    def test_overwrite_existing_key(self):
        """Setting the same key replaces its value and resets TTL."""
        cache = _TTLCache(max_entries=10, ttl=60)
        cache.set("key", [{"old": True}])
        cache.set("key", [{"new": True}])
        result = cache.get("key")
        assert len(result) == 1
        assert result[0]["new"] is True

    def test_thread_safety(self):
        """Concurrent set/get operations do not raise exceptions."""
        cache = _TTLCache(max_entries=100, ttl=60)
        errors = []

        def writer(n):
            try:
                for i in range(50):
                    cache.set(f"key_{n}_{i}", [{"v": i}])
            except Exception as e:
                errors.append(e)

        def reader(n):
            try:
                for i in range(50):
                    cache.get(f"key_{n}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        threads += [threading.Thread(target=reader, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


class TestCacheInit:
    """Test Cache initialization."""

    def test_new_cache_has_empty_stores(self):
        cache = Cache()
        assert cache.get_prices("AAPL") is None
        assert cache.get_financial_metrics("AAPL") is None
        assert cache.get_line_items("AAPL") is None
        assert cache.get_insider_trades("AAPL") is None
        assert cache.get_company_news("AAPL") is None


class TestGetCache:
    """Test the global cache singleton."""

    def test_returns_cache_instance(self):
        cache = get_cache()
        assert isinstance(cache, Cache)

    def test_returns_same_instance(self):
        assert get_cache() is get_cache()


class TestMergeData:
    """Test the _merge_data deduplication logic."""

    def test_returns_new_data_when_existing_is_none(self):
        cache = Cache()
        new_data = [{"id": 1, "value": "a"}]
        result = cache._merge_data(None, new_data, key_field="id")
        assert result == new_data

    def test_returns_new_data_when_existing_is_empty(self):
        cache = Cache()
        result = cache._merge_data([], [{"id": 1}], key_field="id")
        assert result == [{"id": 1}]

    def test_merges_without_duplicates(self):
        cache = Cache()
        existing = [{"id": 1, "value": "a"}]
        new_data = [{"id": 1, "value": "updated"}, {"id": 2, "value": "b"}]
        result = cache._merge_data(existing, new_data, key_field="id")
        assert len(result) == 2
        # Existing value is preserved (not overwritten)
        assert result[0] == {"id": 1, "value": "a"}
        assert result[1] == {"id": 2, "value": "b"}

    def test_does_not_mutate_existing_list(self):
        cache = Cache()
        existing = [{"id": 1}]
        original_len = len(existing)
        cache._merge_data(existing, [{"id": 2}], key_field="id")
        assert len(existing) == original_len


class TestPricesCache:
    """Test price data caching."""

    def test_set_and_get(self):
        cache = Cache()
        prices = [{"time": "2024-01-01", "close": 150.0}]
        cache.set_prices("AAPL", prices)
        assert cache.get_prices("AAPL") == prices

    def test_get_returns_none_for_unknown_ticker(self):
        cache = Cache()
        assert cache.get_prices("UNKNOWN") is None

    def test_deduplicates_by_time(self):
        cache = Cache()
        cache.set_prices("AAPL", [{"time": "2024-01-01", "close": 150.0}])
        cache.set_prices("AAPL", [{"time": "2024-01-01", "close": 999.0}, {"time": "2024-01-02", "close": 155.0}])
        result = cache.get_prices("AAPL")
        assert len(result) == 2
        # Original value preserved
        assert result[0]["close"] == 150.0

    def test_different_tickers_are_independent(self):
        cache = Cache()
        cache.set_prices("AAPL", [{"time": "2024-01-01", "close": 150.0}])
        cache.set_prices("MSFT", [{"time": "2024-01-01", "close": 400.0}])
        assert cache.get_prices("AAPL")[0]["close"] == 150.0
        assert cache.get_prices("MSFT")[0]["close"] == 400.0


class TestFinancialMetricsCache:
    """Test financial metrics caching."""

    def test_set_and_get(self):
        cache = Cache()
        metrics = [{"report_period": "2024-Q1", "revenue": 1000}]
        cache.set_financial_metrics("AAPL", metrics)
        assert cache.get_financial_metrics("AAPL") == metrics

    def test_deduplicates_by_report_period(self):
        cache = Cache()
        cache.set_financial_metrics("AAPL", [{"report_period": "2024-Q1", "revenue": 1000}])
        cache.set_financial_metrics("AAPL", [{"report_period": "2024-Q1", "revenue": 9999}, {"report_period": "2024-Q2", "revenue": 1100}])
        result = cache.get_financial_metrics("AAPL")
        assert len(result) == 2


class TestLineItemsCache:
    """Test line items caching."""

    def test_set_and_get(self):
        cache = Cache()
        items = [{"report_period": "2024-Q1", "total_revenue": 5000}]
        cache.set_line_items("AAPL", items)
        assert cache.get_line_items("AAPL") == items

    def test_deduplicates_by_report_period(self):
        cache = Cache()
        cache.set_line_items("AAPL", [{"report_period": "2024-Q1", "total_revenue": 5000}])
        cache.set_line_items("AAPL", [{"report_period": "2024-Q1", "total_revenue": 9999}, {"report_period": "2024-Q2", "total_revenue": 5500}])
        result = cache.get_line_items("AAPL")
        assert len(result) == 2


class TestInsiderTradesCache:
    """Test insider trades caching."""

    def test_set_and_get(self):
        cache = Cache()
        trades = [{"filing_date": "2024-01-15", "shares": 1000}]
        cache.set_insider_trades("AAPL", trades)
        assert cache.get_insider_trades("AAPL") == trades

    def test_deduplicates_by_filing_date(self):
        cache = Cache()
        cache.set_insider_trades("AAPL", [{"filing_date": "2024-01-15", "shares": 1000}])
        cache.set_insider_trades("AAPL", [{"filing_date": "2024-01-15", "shares": 9999}, {"filing_date": "2024-02-15", "shares": 500}])
        result = cache.get_insider_trades("AAPL")
        assert len(result) == 2
        assert result[0]["shares"] == 1000  # original preserved


class TestCompanyNewsCache:
    """Test company news caching."""

    def test_set_and_get(self):
        cache = Cache()
        news = [{"date": "2024-01-01", "title": "Earnings Beat"}]
        cache.set_company_news("AAPL", news)
        assert cache.get_company_news("AAPL") == news

    def test_deduplicates_by_date(self):
        cache = Cache()
        cache.set_company_news("AAPL", [{"date": "2024-01-01", "title": "Earnings Beat"}])
        cache.set_company_news("AAPL", [{"date": "2024-01-01", "title": "Duplicate"}, {"date": "2024-01-02", "title": "New Product"}])
        result = cache.get_company_news("AAPL")
        assert len(result) == 2
        assert result[0]["title"] == "Earnings Beat"  # original preserved
