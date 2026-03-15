"""Tests for HK stock adapter."""
import pytest
import requests_mock as rm_module
from unittest.mock import Mock, patch
from src.markets.hk_stock import HKStockAdapter
from src.data.models import Price


class TestHKStockAdapter:
    """Test HK stock adapter."""

    def test_normalize_ticker(self):
        """Test ticker normalization."""
        adapter = HKStockAdapter()

        # Test 5-digit ticker
        assert adapter.normalize_ticker("00700") == "00700"
        assert adapter.normalize_ticker("01398") == "01398"

        # Test without leading zeros
        assert adapter.normalize_ticker("700") == "00700"
        assert adapter.normalize_ticker("1398") == "01398"

        # Test with .HK suffix
        assert adapter.normalize_ticker("0700.HK") == "00700"
        assert adapter.normalize_ticker("700.HK") == "00700"

    def test_get_yfinance_ticker(self):
        """Test YFinance ticker format."""
        adapter = HKStockAdapter()

        assert adapter.get_yfinance_ticker("00700") == "0700.HK"
        assert adapter.get_yfinance_ticker("01398") == "1398.HK"
        assert adapter.get_yfinance_ticker("700") == "0700.HK"

    @patch('src.markets.sources.akshare_source.AKShareSource.get_prices')
    @patch('src.markets.sources.yfinance_source.YFinanceSource.get_prices')
    def test_get_prices_multi_source(self, mock_yf_prices, mock_ak_prices):
        """Test getting prices from multiple sources."""
        adapter = HKStockAdapter()

        # Mock data from both sources
        mock_ak_prices.return_value = [
            {
                "open": 100.0,
                "close": 101.0,
                "high": 102.0,
                "low": 99.0,
                "volume": 1000000,
                "time": "2024-01-01T00:00:00Z",
            }
        ]

        mock_yf_prices.return_value = [
            {
                "open": 100.5,
                "close": 101.5,
                "high": 102.5,
                "low": 99.5,
                "volume": 1100000,
                "time": "2024-01-01T00:00:00Z",
            }
        ]

        # Get prices (should merge from both sources)
        prices = adapter.get_prices("00700", "2024-01-01", "2024-01-31")

        # Verify
        assert len(prices) > 0
        assert isinstance(prices[0], Price)

        # Both sources should be called
        mock_ak_prices.assert_called_once()
        mock_yf_prices.assert_called_once()

    @patch('src.markets.sources.akshare_source.AKShareSource.get_prices')
    @patch('src.markets.sources.yfinance_source.YFinanceSource.get_prices')
    def test_get_prices_fallback(self, mock_yf_prices, mock_ak_prices):
        """Test fallback when primary source fails."""
        adapter = HKStockAdapter()

        # Primary source fails
        mock_ak_prices.return_value = []

        # Fallback source succeeds
        mock_yf_prices.return_value = [
            {
                "open": 100.0,
                "close": 101.0,
                "high": 102.0,
                "low": 99.0,
                "volume": 1000000,
                "time": "2024-01-01T00:00:00Z",
            }
        ]

        # Get prices (should use fallback)
        prices = adapter.get_prices("00700", "2024-01-01", "2024-01-31")

        # Verify
        assert len(prices) > 0
        assert isinstance(prices[0], Price)

    @patch('src.markets.sources.akshare_source.AKShareSource.get_financial_metrics')
    def test_get_financial_metrics(self, mock_get_metrics):
        """Test getting financial metrics."""
        adapter = HKStockAdapter()

        # Mock data
        mock_metrics = {
            "ticker": "00700",
            "price_to_earnings_ratio": 25.5,
            "price_to_book_ratio": 5.0,
            "return_on_equity": 0.20,
        }
        mock_get_metrics.return_value = mock_metrics

        # Get metrics
        metrics = adapter.get_financial_metrics("00700", "2024-01-31")

        # Verify
        assert metrics is not None
        assert metrics["ticker"] == "00700"


class TestHKStockNewsNowIntegration:
    def test_get_company_news_uses_newsnow_first(self):
        """Test that NewsNow is used as primary news source."""
        adapter = HKStockAdapter()

        # Mock NewsNow API - use normalized ticker in title (00700)
        with rm_module.Mocker() as m:
            m.get(
                "https://newsnow.busiyi.world/api/s?id=cls",
                json={
                    "items": [
                        {
                            "id": "1",
                            "title": "腾讯 00700 股价上涨",
                            "url": "https://example.com/1",
                            "publish_time": "2024-03-15T10:00:00Z"
                        }
                    ]
                }
            )
            m.get("https://newsnow.busiyi.world/api/s?id=wallstreetcn", json={"items": []})
            m.get("https://newsnow.busiyi.world/api/s?id=xueqiu", json={"items": []})

            news = adapter.get_company_news("0700", "2024-03-15", limit=10)

        assert len(news) > 0
        assert news[0]["source"] == "NewsNow"
