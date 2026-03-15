"""Tests for YFinance rate limiting enhancements."""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from src.markets.sources.yfinance_source import YFinanceSource


class TestYFinanceRateLimiting:
    """Test YFinance rate limiting mechanisms."""

    def test_enforce_rate_limit_adds_delay(self):
        """Test that rate limiting adds proper delay."""
        source = YFinanceSource()

        # First call should add delay
        start_time = time.time()
        source._enforce_rate_limit(min_delay=0.1, max_delay=0.2)
        elapsed = time.time() - start_time

        # Should have delayed at least min_delay
        assert elapsed >= 0.1, "Should enforce minimum delay"
        assert elapsed <= 0.5, "Should not delay excessively"

    def test_enforce_rate_limit_prevents_rapid_requests(self):
        """Test that rate limiting prevents rapid successive requests."""
        source = YFinanceSource()

        # Make two requests in quick succession
        source._enforce_rate_limit(min_delay=0.1, max_delay=0.15)
        start_time = time.time()
        source._enforce_rate_limit(min_delay=0.1, max_delay=0.15)
        elapsed = time.time() - start_time

        # Second request should be delayed even more
        assert elapsed >= 0.1, "Should enforce rate limit between requests"

    def test_cache_key_generation(self):
        """Test cache key generation is deterministic."""
        source = YFinanceSource()

        key1 = source._get_cache_key("get_prices", ticker="AAPL", start="2024-01-01", end="2024-12-31")
        key2 = source._get_cache_key("get_prices", ticker="AAPL", start="2024-01-01", end="2024-12-31")
        key3 = source._get_cache_key("get_prices", ticker="MSFT", start="2024-01-01", end="2024-12-31")

        # Same parameters should generate same key
        assert key1 == key2, "Same parameters should generate same key"

        # Different parameters should generate different key
        assert key1 != key3, "Different parameters should generate different keys"

    def test_cache_saves_and_retrieves_data(self):
        """Test caching mechanism saves and retrieves data."""
        source = YFinanceSource()

        cache_key = "test_key"
        test_data = {"price": 150.0}

        # Save to cache
        source._save_to_cache(cache_key, test_data)

        # Retrieve from cache
        cached_data = source._get_from_cache(cache_key, max_age=60)

        assert cached_data == test_data, "Should retrieve cached data"

    def test_cache_expires_old_data(self):
        """Test that cache expires old data."""
        source = YFinanceSource()

        cache_key = "test_key"
        test_data = {"price": 150.0}

        # Save to cache
        source._save_to_cache(cache_key, test_data)

        # Immediately retrieve should work
        cached_data = source._get_from_cache(cache_key, max_age=0.01)
        assert cached_data == test_data

        # Wait for expiration
        time.sleep(0.02)

        # Should return None after expiration
        expired_data = source._get_from_cache(cache_key, max_age=0.01)
        assert expired_data is None, "Should expire old cached data"

    def test_get_prices_uses_cache(self):
        """Test that get_prices uses cache to avoid duplicate requests."""
        source = YFinanceSource()

        # Mock yfinance module
        mock_yf = Mock()
        mock_ticker = Mock()
        mock_df = Mock()
        mock_df.empty = False
        mock_df.iterrows.return_value = [
            (
                Mock(strftime=lambda x: "2024-01-01T00:00:00Z"),
                {"Open": 150.0, "Close": 151.0, "High": 152.0, "Low": 149.0, "Volume": 1000000}
            )
        ]
        mock_ticker.history.return_value = mock_df
        mock_yf.Ticker.return_value = mock_ticker
        source._yf = mock_yf

        # First call - should hit API
        prices1 = source.get_prices("AAPL", "2024-01-01", "2024-01-31")
        assert len(prices1) > 0

        # Second call with same parameters - should use cache
        prices2 = source.get_prices("AAPL", "2024-01-01", "2024-01-31")
        assert prices1 == prices2

        # Should only call the API once due to caching
        assert mock_yf.Ticker.call_count == 1, "Should use cache for duplicate requests"

    def test_get_prices_retries_on_rate_limit(self):
        """Test that get_prices retries with exponential backoff on rate limit."""
        source = YFinanceSource()

        # Mock yfinance module
        mock_yf = Mock()
        mock_ticker = Mock()
        mock_df = Mock()
        mock_df.empty = False
        mock_df.iterrows.return_value = [
            (
                Mock(strftime=lambda x: "2024-01-01T00:00:00Z"),
                {"Open": 150.0, "Close": 151.0, "High": 152.0, "Low": 149.0, "Volume": 1000000}
            )
        ]

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Too Many Requests. Rate limited")
            return mock_df

        mock_ticker.history.side_effect = side_effect
        mock_yf.Ticker.return_value = mock_ticker
        source._yf = mock_yf

        # Should retry and succeed
        prices = source.get_prices("AAPL", "2024-01-01", "2024-01-31")
        assert len(prices) > 0
        assert call_count == 2, "Should retry after rate limit"

    def test_get_financial_metrics_uses_cache(self):
        """Test that get_financial_metrics uses cache."""
        source = YFinanceSource()

        # Mock yfinance module
        mock_yf = Mock()
        mock_ticker = Mock()
        mock_ticker.info = {
            "marketCap": 3000000000000,
            "trailingPE": 30.5,
            "currency": "USD"
        }
        mock_yf.Ticker.return_value = mock_ticker
        source._yf = mock_yf

        # First call
        metrics1 = source.get_financial_metrics("AAPL", "2024-01-31")
        assert metrics1 is not None

        # Second call should use cache
        metrics2 = source.get_financial_metrics("AAPL", "2024-01-31")
        assert metrics1 == metrics2

        # Should only call the API once
        assert mock_yf.Ticker.call_count == 1

    def test_get_company_news_uses_cache(self):
        """Test that get_company_news uses cache."""
        source = YFinanceSource()

        # Mock yfinance module
        mock_yf = Mock()
        mock_ticker = Mock()
        mock_ticker.news = [
            {
                "title": "Test News",
                "providerPublishTime": 1704067200,  # 2024-01-01
                "publisher": "Test Publisher",
                "link": "https://example.com"
            }
        ]
        mock_yf.Ticker.return_value = mock_ticker
        source._yf = mock_yf

        # First call
        news1 = source.get_company_news("AAPL", "2024-12-31")
        assert len(news1) > 0

        # Second call should use cache
        news2 = source.get_company_news("AAPL", "2024-12-31")
        assert news1 == news2

        # Should only call the API once
        assert mock_yf.Ticker.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
