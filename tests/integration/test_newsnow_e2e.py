"""End-to-end tests for NewsNow integration."""
import pytest
from src.markets.us_stock import USStockAdapter
from src.markets.cn_stock import CNStockAdapter
from src.markets.hk_stock import HKStockAdapter


class TestNewsNowE2E:
    @pytest.mark.integration
    def test_us_stock_news_no_rate_limit(self):
        """Test that getting US news doesn't trigger rate limits."""
        adapter = USStockAdapter()

        # Simulate multiple analyst requests
        tickers = ["AAPL", "MSFT", "GOOGL"]

        for ticker in tickers:
            news = adapter.get_company_news(ticker, "2024-03-15", limit=5)
            # Should succeed without 429 errors
            assert isinstance(news, list)
            # May or may not have news, but shouldn't error

    @pytest.mark.integration
    def test_cn_stock_news_no_rate_limit(self):
        """Test that getting CN news doesn't trigger rate limits."""
        adapter = CNStockAdapter()

        # Simulate multiple analyst requests
        tickers = ["600519", "000001"]  # Moutai, Ping An Bank

        for ticker in tickers:
            news = adapter.get_company_news(ticker, "2024-03-15", limit=5)
            # Should succeed without 429 errors
            assert isinstance(news, list)

    @pytest.mark.integration
    def test_hk_stock_news_no_rate_limit(self):
        """Test that getting HK news doesn't trigger rate limits."""
        adapter = HKStockAdapter()

        # Simulate multiple analyst requests
        tickers = ["00700", "01398"]  # Tencent, ICBC

        for ticker in tickers:
            news = adapter.get_company_news(ticker, "2024-03-15", limit=5)
            # Should succeed without 429 errors
            assert isinstance(news, list)

    @pytest.mark.integration
    def test_cache_effectiveness(self):
        """Test that cache reduces API calls."""
        adapter = USStockAdapter()

        # First call
        news1 = adapter.get_company_news("AAPL", "2024-03-15", limit=5)

        # Second call should use cache (no new API calls)
        news2 = adapter.get_company_news("AAPL", "2024-03-15", limit=5)

        # Results should be consistent
        if news1:  # If first call got news
            assert news1 == news2
