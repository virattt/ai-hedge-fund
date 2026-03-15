"""
Tests for MySQL Cache Manager.

Tests the MySQL cache manager for dual-layer caching (L1 memory + L2 MySQL).
"""
import pytest
from datetime import datetime, date, timedelta
from src.data.mysql_cache import MySQLCacheManager
from src.data.models import Price, FinancialMetrics, CompanyNews


@pytest.fixture
def cache_manager():
    """Create a MySQL cache manager with test database."""
    # Use in-memory SQLite for testing
    import os
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    manager = MySQLCacheManager()
    yield manager

    # Cleanup
    manager.close()


class TestMySQLCacheManager:
    """Tests for MySQLCacheManager class."""

    def test_initialization(self, cache_manager):
        """Test that cache manager initializes correctly."""
        assert cache_manager is not None
        assert cache_manager.session is not None

    def test_save_and_get_prices(self, cache_manager):
        """Test saving and retrieving stock prices."""
        # Create test price data (Price model doesn't include ticker)
        prices = [
            Price(
                time=f"2024-01-0{i}T16:00:00",
                open=150.0 + i,
                close=152.5 + i,
                high=153.0 + i,
                low=149.5 + i,
                volume=1000000 + i,
            )
            for i in range(1, 4)
        ]

        # Save to cache
        cache_manager.save_prices("AAPL", prices)

        # Retrieve from cache
        cached_prices = cache_manager.get_prices("AAPL", "2024-01-01", "2024-01-03")

        assert len(cached_prices) == 3
        # Prices are ordered by time, so first price should be from i=1
        assert cached_prices[0].close == 153.5  # 152.5 + 1 from loop

    def test_price_deduplication(self, cache_manager):
        """Test that duplicate prices are not inserted."""
        # Create test price data
        price = Price(
            ticker="AAPL",
            time="2024-01-01T16:00:00",
            open=150.0,
            close=152.5,
            high=153.0,
            low=149.5,
            volume=1000000,
        )

        # Save twice
        cache_manager.save_prices("AAPL", [price])
        cache_manager.save_prices("AAPL", [price])

        # Should only have one record
        cached_prices = cache_manager.get_prices("AAPL", "2024-01-01", "2024-01-01")
        assert len(cached_prices) == 1

    def test_is_data_fresh_historical(self, cache_manager):
        """Test that historical data is always considered fresh."""
        # Historical date (yesterday)
        yesterday = (datetime.now() - timedelta(days=1)).date()

        is_fresh = cache_manager.is_data_fresh(yesterday.isoformat())
        assert is_fresh is True

    def test_is_data_fresh_current_within_hour(self, cache_manager):
        """Test that current data within 1 hour is fresh."""
        # Current date (today)
        today = datetime.now().date()

        # Provide an updated_at timestamp (just now)
        is_fresh = cache_manager.is_data_fresh(today.isoformat(), datetime.now())
        assert is_fresh is True

    def test_save_and_get_financial_metrics(self, cache_manager):
        """Test saving and retrieving financial metrics."""
        # Create test metrics
        metric = FinancialMetrics(
            ticker="AAPL",
            report_period="2024-01-01",
            period="ttm",
            currency="USD",
            market_cap=3000000000000.0,
            price_to_earnings_ratio=25.5,
        )

        # Save to cache
        cache_manager.save_financial_metrics("AAPL", [metric])

        # Retrieve from cache
        cached_metrics = cache_manager.get_financial_metrics("AAPL", "2024-01-01", "ttm")

        assert len(cached_metrics) == 1
        assert cached_metrics[0].ticker == "AAPL"
        assert cached_metrics[0].market_cap == 3000000000000.0

    def test_save_and_get_company_news(self, cache_manager):
        """Test saving and retrieving company news."""
        # Create test news (CompanyNews model requires author field)
        news_items = [
            CompanyNews(
                ticker="AAPL",
                date=f"2024-01-0{i}T10:00:00",
                title=f"News {i}",
                author="Test Author",
                url=f"https://example.com/news/{i}",
                source="Example News",
            )
            for i in range(1, 4)
        ]

        # Save to cache
        cache_manager.save_company_news("AAPL", news_items)

        # Retrieve from cache
        cached_news = cache_manager.get_company_news("AAPL", "2024-01-01", "2024-01-03")

        assert len(cached_news) == 3
        assert cached_news[0].ticker == "AAPL"
        assert "News" in cached_news[0].title

    def test_get_nonexistent_data(self, cache_manager):
        """Test that getting nonexistent data returns empty list."""
        prices = cache_manager.get_prices("NONEXISTENT", "2024-01-01", "2024-01-01")
        assert prices == []

        metrics = cache_manager.get_financial_metrics("NONEXISTENT", "2024-01-01", "ttm")
        assert metrics == []

        news = cache_manager.get_company_news("NONEXISTENT", "2024-01-01", "2024-01-01")
        assert news == []
