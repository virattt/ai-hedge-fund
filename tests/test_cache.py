"""Tests for the in-memory cache in src/data/cache.py.

Validates cache hit/miss behavior and the deduplication merge logic.
"""

from src.data.cache import Cache


class TestCachePrices:
    def test_get_returns_none_on_miss(self):
        cache = Cache()
        assert cache.get_prices("AAPL_2024-01-01_2024-02-01") is None

    def test_set_then_get(self):
        cache = Cache()
        data = [{"time": "2024-01-01", "close": 100.0}]
        cache.set_prices("AAPL_2024-01-01_2024-02-01", data)
        result = cache.get_prices("AAPL_2024-01-01_2024-02-01")
        assert result == data

    def test_set_merges_without_duplicates(self):
        cache = Cache()
        batch1 = [
            {"time": "2024-01-01", "close": 100.0},
            {"time": "2024-01-02", "close": 101.0},
        ]
        batch2 = [
            {"time": "2024-01-02", "close": 101.0},  # duplicate
            {"time": "2024-01-03", "close": 102.0},  # new
        ]
        cache.set_prices("key", batch1)
        cache.set_prices("key", batch2)
        result = cache.get_prices("key")
        assert len(result) == 3
        times = [r["time"] for r in result]
        assert times == ["2024-01-01", "2024-01-02", "2024-01-03"]


class TestCacheFinancialMetrics:
    def test_get_returns_none_on_miss(self):
        cache = Cache()
        assert cache.get_financial_metrics("AAPL_ttm_2024-01-01_10") is None

    def test_set_then_get(self):
        cache = Cache()
        data = [{"report_period": "2024-Q1", "market_cap": 3e12}]
        cache.set_financial_metrics("key", data)
        assert cache.get_financial_metrics("key") == data

    def test_dedup_by_report_period(self):
        cache = Cache()
        batch1 = [{"report_period": "2024-Q1", "market_cap": 3e12}]
        batch2 = [
            {"report_period": "2024-Q1", "market_cap": 3.1e12},  # dup key, different value
            {"report_period": "2024-Q2", "market_cap": 3.2e12},
        ]
        cache.set_financial_metrics("key", batch1)
        cache.set_financial_metrics("key", batch2)
        result = cache.get_financial_metrics("key")
        assert len(result) == 2
        # First entry keeps original value (dedup keeps existing)
        assert result[0]["market_cap"] == 3e12


class TestCacheInsiderTrades:
    def test_set_then_get(self):
        cache = Cache()
        data = [{"filing_date": "2024-03-15", "ticker": "AAPL"}]
        cache.set_insider_trades("key", data)
        assert cache.get_insider_trades("key") is not None

    def test_dedup_by_filing_date(self):
        cache = Cache()
        cache.set_insider_trades("key", [{"filing_date": "2024-03-15", "shares": 100}])
        cache.set_insider_trades("key", [
            {"filing_date": "2024-03-15", "shares": 200},  # dup
            {"filing_date": "2024-03-16", "shares": 300},
        ])
        result = cache.get_insider_trades("key")
        assert len(result) == 2


class TestCacheCompanyNews:
    def test_set_then_get(self):
        cache = Cache()
        data = [{"date": "2024-01-25", "title": "Earnings Beat"}]
        cache.set_company_news("key", data)
        assert cache.get_company_news("key") == data

    def test_dedup_by_date(self):
        cache = Cache()
        cache.set_company_news("key", [{"date": "2024-01-25", "title": "A"}])
        cache.set_company_news("key", [
            {"date": "2024-01-25", "title": "B"},
            {"date": "2024-01-26", "title": "C"},
        ])
        result = cache.get_company_news("key")
        assert len(result) == 2
        assert result[0]["title"] == "A"  # original preserved


class TestCacheMergeData:
    def test_merge_with_none_existing(self):
        cache = Cache()
        result = cache._merge_data(None, [{"time": "a"}], "time")
        assert result == [{"time": "a"}]

    def test_merge_with_empty_existing(self):
        cache = Cache()
        result = cache._merge_data([], [{"time": "a"}], "time")
        assert result == [{"time": "a"}]

    def test_merge_all_duplicates(self):
        cache = Cache()
        existing = [{"time": "a"}, {"time": "b"}]
        new_data = [{"time": "a"}, {"time": "b"}]
        result = cache._merge_data(existing, new_data, "time")
        assert len(result) == 2
