"""Integration tests for YFinance with real API (optional, slow)."""
import pytest
import os
from src.markets.sources.yfinance_source import YFinanceSource


# Mark as slow and skip by default
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("RUN_SLOW_TESTS") != "1",
    reason="Slow integration test, set RUN_SLOW_TESTS=1 to run"
)
class TestYFinanceIntegration:
    """Integration tests with real YFinance API."""

    def test_get_prices_real_api(self):
        """Test getting prices from real YFinance API."""
        source = YFinanceSource()

        # Get prices for a well-known stock
        prices = source.get_prices("AAPL", "2024-01-01", "2024-01-31")

        assert len(prices) > 0, "Should get price data"
        assert "open" in prices[0]
        assert "close" in prices[0]
        assert "high" in prices[0]
        assert "low" in prices[0]
        assert "volume" in prices[0]

    def test_get_prices_uses_cache_real_api(self):
        """Test that cache works with real API."""
        source = YFinanceSource()

        # First call
        import time
        start = time.time()
        prices1 = source.get_prices("AAPL", "2024-01-01", "2024-01-31")
        first_call_time = time.time() - start

        # Second call should be from cache (much faster)
        start = time.time()
        prices2 = source.get_prices("AAPL", "2024-01-01", "2024-01-31")
        second_call_time = time.time() - start

        assert prices1 == prices2, "Should return same data"
        assert second_call_time < 0.1, "Cached call should be very fast"
        assert first_call_time > second_call_time, "First call should be slower"

    def test_rate_limiting_prevents_rapid_requests(self):
        """Test that rate limiting adds delays between requests."""
        source = YFinanceSource()

        import time

        # Make two different requests
        start = time.time()
        source.get_prices("AAPL", "2024-01-01", "2024-01-31")
        first_call_time = time.time() - start

        start = time.time()
        source.get_prices("MSFT", "2024-01-01", "2024-01-31")
        second_call_time = time.time() - start

        # Both should have delays
        assert first_call_time >= 2.0, "First call should have rate limit delay"
        assert second_call_time >= 2.0, "Second call should have rate limit delay"

    def test_get_financial_metrics_real_api(self):
        """Test getting financial metrics from real API."""
        source = YFinanceSource()

        metrics = source.get_financial_metrics("AAPL", "2024-01-31")

        assert metrics is not None
        assert metrics["ticker"] == "AAPL"
        assert "market_cap" in metrics

    def test_get_company_news_real_api(self):
        """Test getting company news from real API."""
        source = YFinanceSource()

        news = source.get_company_news("AAPL", "2024-12-31", limit=10)

        # News may or may not be available, so just check it doesn't crash
        assert isinstance(news, list)


if __name__ == "__main__":
    # Run with: RUN_SLOW_TESTS=1 pytest tests/markets/test_yfinance_integration.py -v -s
    pytest.main([__file__, "-v", "-s"])
