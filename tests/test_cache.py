import pytest

from src.data.cache import Cache, get_cache


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


class TestLineItemsFieldTracking:
    """Line-items cache now tracks which fields have been fetched per key and
    merges new fields into existing rows (field-level union), so multiple agents
    requesting overlapping fields share one logical fetch."""

    def test_returns_none_fields_for_absent_key(self):
        cache = Cache()
        assert cache.get_line_items_fields("AAPL") is None

    def test_tracks_fetched_fields(self):
        cache = Cache()
        cache.set_line_items("AAPL", [{"report_period": "2024-Q1", "revenue": 100}], fields={"revenue"})
        assert cache.get_line_items_fields("AAPL") == {"revenue"}

    def test_field_union_accumulates_across_sets(self):
        cache = Cache()
        cache.set_line_items("AAPL", [{"report_period": "2024-Q1", "revenue": 100}], fields={"revenue"})
        cache.set_line_items("AAPL", [{"report_period": "2024-Q1", "net_income": 10}], fields={"net_income"})
        assert cache.get_line_items_fields("AAPL") == {"revenue", "net_income"}

    def test_merges_fields_within_same_report_period(self):
        """Critical: row-level dedup would drop net_income here. Field-level merge keeps both."""
        cache = Cache()
        cache.set_line_items("AAPL", [{"report_period": "2024-Q1", "revenue": 100}], fields={"revenue"})
        cache.set_line_items("AAPL", [{"report_period": "2024-Q1", "net_income": 10}], fields={"net_income"})
        result = cache.get_line_items("AAPL")
        assert len(result) == 1  # same report_period, not a new row
        assert result[0]["revenue"] == 100
        assert result[0]["net_income"] == 10

    def test_preserves_existing_value_when_merging(self):
        cache = Cache()
        cache.set_line_items("AAPL", [{"report_period": "2024-Q1", "revenue": 100}], fields={"revenue"})
        # second set targets a different field; revenue must be untouched
        cache.set_line_items("AAPL", [{"report_period": "2024-Q1", "revenue": 999, "net_income": 10}], fields={"net_income"})
        result = cache.get_line_items("AAPL")
        assert result[0]["revenue"] == 100  # original preserved
        assert result[0]["net_income"] == 10

    def test_appends_new_report_periods(self):
        cache = Cache()
        cache.set_line_items("AAPL", [{"report_period": "2024-Q1", "revenue": 100}], fields={"revenue"})
        cache.set_line_items("AAPL", [{"report_period": "2023-Q4", "revenue": 90}], fields={"revenue"})
        result = cache.get_line_items("AAPL")
        assert len(result) == 2

    def test_back_compat_set_without_fields(self):
        """Existing callers that omit `fields` still work; key is marked present."""
        cache = Cache()
        items = [{"report_period": "2024-Q1", "total_revenue": 5000}]
        cache.set_line_items("AAPL", items)
        assert cache.get_line_items("AAPL") == items
        assert cache.get_line_items_fields("AAPL") == set()


class TestFinancialMetricsLimitTracking:
    """financial-metrics cache tracks the max limit fetched so a request for a
    smaller limit can reuse a larger cached fetch (subset-on-limit)."""

    def test_returns_none_limit_for_absent_key(self):
        cache = Cache()
        assert cache.get_financial_metrics_limit("AAPL") is None

    def test_tracks_limit(self):
        cache = Cache()
        cache.set_financial_metrics("AAPL", [{"report_period": "2024-Q1"}], limit=10)
        assert cache.get_financial_metrics_limit("AAPL") == 10

    def test_limit_tracks_max(self):
        cache = Cache()
        cache.set_financial_metrics("AAPL", [{"report_period": "2024-Q1"}], limit=5)
        cache.set_financial_metrics("AAPL", [{"report_period": "2024-Q1"}, {"report_period": "2023-Q4"}], limit=10)
        assert cache.get_financial_metrics_limit("AAPL") == 10

    def test_back_compat_set_without_limit(self):
        cache = Cache()
        metrics = [{"report_period": "2024-Q1", "revenue": 1000}]
        cache.set_financial_metrics("AAPL", metrics)
        assert cache.get_financial_metrics("AAPL") == metrics
        assert cache.get_financial_metrics_limit("AAPL") is None


class TestFetchLock:
    """Per-key lock that lets concurrent agents serialize check-fetch-populate
    for the same cache key (prevents thundering-herd duplicate API calls)."""

    def test_is_usable_as_context_manager(self):
        cache = Cache()
        with cache.fetch_lock("AAPL_metrics"):
            pass  # does not raise

    def test_distinct_keys_do_not_deadlock(self):
        cache = Cache()
        with cache.fetch_lock("AAPL"):
            with cache.fetch_lock("MSFT"):
                pass

    def test_serializes_concurrent_access_to_same_key(self):
        import threading

        cache = Cache()
        state = {"current": 0, "max_concurrent": 0, "done": 0}
        guard = threading.Lock()

        def worker():
            with cache.fetch_lock("K"):
                with guard:
                    state["current"] += 1
                    state["max_concurrent"] = max(state["max_concurrent"], state["current"])
                # burn a little time so overlap would be detected if lock failed
                total = 0
                for i in range(2000):
                    total += i
                with guard:
                    state["current"] -= 1
                    state["done"] += 1
                assert total >= 0

        threads = [threading.Thread(target=worker) for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert state["done"] == 12
        assert state["max_concurrent"] == 1  # proof of mutual exclusion
