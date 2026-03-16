"""
End-to-end integration tests for dual-layer cache.

Tests the full flow: request → L1 → L2 → API → cache population
"""
import pytest
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.tools.api import get_prices, get_financial_metrics, get_company_news
from src.data.dual_cache import get_dual_cache
from src.data.cache import get_cache
from src.data.mysql_cache import MySQLCacheManager
from src.data.models import Price, FinancialMetrics, CompanyNews


@pytest.mark.integration
@pytest.mark.e2e
@pytest.fixture
def clean_test_env():
    """Setup clean test environment with in-memory database."""
    # Use in-memory SQLite for testing
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    # Clear L1 cache
    l1_cache = get_cache()
    l1_cache.clear()

    # Reset global dual cache to force re-initialization
    import src.data.dual_cache as dual_cache_module
    dual_cache_module._dual_cache = None

    # Create fresh dual cache instance with L2 enabled
    from src.data.dual_cache import DualLayerCacheManager
    dual_cache = DualLayerCacheManager(enable_l2=True)

    # Update global instance
    dual_cache_module._dual_cache = dual_cache

    yield dual_cache

    # Cleanup
    if dual_cache.l2_cache:
        dual_cache.l2_cache.close()

    # Reset global instance again
    dual_cache_module._dual_cache = None

    os.environ.pop("DATABASE_URL", None)


@pytest.mark.integration
@pytest.mark.e2e
class TestDualLayerCacheE2E:
    """End-to-end integration tests for dual-layer cache."""

    def test_full_cache_flow_prices(self, clean_test_env):
        """
        Test full cache flow for prices:
        1. Verify L2 cache is enabled
        2. Save data directly to L2
        3. Verify L2 → L1 promotion on cache miss
        """
        dual_cache = clean_test_env

        # Verify L2 cache is initialized
        assert dual_cache.l2_cache is not None

        # Create test data
        test_prices = [
            Price(
                time="2024-01-01T16:00:00",
                open=150.0,
                close=152.5,
                high=153.0,
                low=149.5,
                volume=1000000,
            )
        ]

        # Step 1: Save to L2 directly (bypass L1)
        dual_cache.l2_cache.save_prices("TESTCACHE", test_prices)

        # Step 2: Verify data is in L2
        l2_prices = dual_cache.l2_cache.get_prices("TESTCACHE", "2024-01-01", "2024-01-01")
        assert len(l2_prices) == 1
        assert l2_prices[0].close == 152.5

        # Step 3: Get via dual cache (should retrieve from L2 and populate L1)
        cached_prices = dual_cache.get_prices("TESTCACHE", "2024-01-01", "2024-01-01")
        assert cached_prices is not None
        assert len(cached_prices) == 1
        assert cached_prices[0].close == 152.5

        # Step 4: Verify L1 now has the data
        l1_key = dual_cache._create_cache_key("TESTCACHE", "2024-01-01", "2024-01-01")
        l1_cached = dual_cache.l1_cache.get_prices(l1_key)
        assert l1_cached is not None
        assert len(l1_cached) == 1

    def test_cache_freshness_historical_data(self, clean_test_env):
        """Test that historical data is cached permanently."""
        dual_cache = clean_test_env
        old_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        # Verify historical data is always fresh
        assert dual_cache.l2_cache.is_data_fresh(old_date) is True

        # Save historical data to L2
        test_prices = [
            Price(
                time=f"{old_date}T16:00:00",
                open=150.0,
                close=152.5,
                high=153.0,
                low=149.5,
                volume=1000000,
            )
        ]
        dual_cache.l2_cache.save_prices("HISTTEST", test_prices)

        # Verify data persists and is considered fresh
        l2_prices = dual_cache.l2_cache.get_prices("HISTTEST", old_date, old_date)
        assert len(l2_prices) == 1

    def test_cache_freshness_current_data(self, clean_test_env):
        """Test that current data respects 1-hour freshness rule."""
        dual_cache = clean_test_env

        # Verify freshness logic works
        today = datetime.now().strftime("%Y-%m-%d")
        assert dual_cache.l2_cache.is_data_fresh(today, datetime.now()) is True

        # Data older than 1 hour should be stale
        old_timestamp = datetime.now() - timedelta(hours=2)
        assert dual_cache.l2_cache.is_data_fresh(today, old_timestamp) is False

    def test_l2_cache_disabled_fallback(self):
        """Test that system works when L2 cache is disabled."""
        # Don't set DATABASE_URL - L2 should be disabled
        os.environ.pop("DATABASE_URL", None)

        # Clear L1 cache
        l1_cache = get_cache()
        l1_cache.clear()

        with patch('src.tools.api._make_api_request') as mock_request:
            # Mock API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "ticker": "AAPL",
                "prices": [
                    {
                        "time": "2024-01-01T16:00:00",
                        "open": 150.0,
                        "close": 152.5,
                        "high": 153.0,
                        "low": 149.5,
                        "volume": 1000000,
                    }
                ]
            }
            mock_request.return_value = mock_response

            # Should still work with L1 only
            prices = get_prices("AAPL", "2024-01-01", "2024-01-01")
            assert len(prices) == 1
            assert mock_request.called

    def test_financial_metrics_cache_flow(self, clean_test_env):
        """Test cache flow for financial metrics."""
        dual_cache = clean_test_env

        # Create test metrics
        test_metrics = [
            FinancialMetrics(
                ticker="METRICTEST",
                report_period="2024-01-01",
                period="ttm",
                currency="USD",
                market_cap=3000000000000.0,
                price_to_earnings_ratio=25.5,
            )
        ]

        # Save to L2 directly
        dual_cache.l2_cache.save_financial_metrics("METRICTEST", test_metrics)

        # Verify data is in L2
        l2_metrics = dual_cache.l2_cache.get_financial_metrics("METRICTEST", "2024-01-01", "ttm")
        assert len(l2_metrics) == 1
        assert l2_metrics[0].market_cap == 3000000000000.0

        # Get via dual cache (should retrieve from L2)
        cached_metrics = dual_cache.get_financial_metrics("METRICTEST", "2024-01-01", "ttm", 10)
        assert cached_metrics is not None
        assert len(cached_metrics) == 1

    def test_company_news_cache_flow(self, clean_test_env):
        """Test cache flow for company news."""
        dual_cache = clean_test_env

        # Create test news
        test_news = [
            CompanyNews(
                ticker="NEWSTEST",
                date="2024-01-01T10:00:00",
                title="Test News",
                author="Test Author",
                url="https://example.com/news/1",
                source="Example News",
            )
        ]

        # Save to L2 directly
        dual_cache.l2_cache.save_company_news("NEWSTEST", test_news)

        # Verify data is in L2
        l2_news = dual_cache.l2_cache.get_company_news("NEWSTEST", "2024-01-01", "2024-01-01")
        assert len(l2_news) == 1
        assert l2_news[0].title == "Test News"

        # Get via dual cache (should retrieve from L2)
        cached_news = dual_cache.get_company_news("NEWSTEST", "2024-01-01", "2024-01-01", 1000)
        assert cached_news is not None
        assert len(cached_news) == 1

    def test_cache_hit_rate_statistics(self, clean_test_env):
        """Test cache hit rate statistics."""
        dual_cache = clean_test_env

        with patch('src.tools.api._make_api_request') as mock_request:
            # Mock API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "ticker": "AAPL",
                "prices": [
                    {
                        "time": "2024-01-01T16:00:00",
                        "open": 150.0,
                        "close": 152.5,
                        "high": 153.0,
                        "low": 149.5,
                        "volume": 1000000,
                    }
                ]
            }
            mock_request.return_value = mock_response

            # Make multiple requests
            for _ in range(5):
                get_prices("AAPL", "2024-01-01", "2024-01-01")

            # Check L1 cache statistics
            stats = dual_cache.l1_cache.get_stats()
            assert stats["hits"] >= 4  # First miss, then 4 hits
            assert stats["total"] == 5
