"""Tests for CN stock adapter."""
import pytest
from unittest.mock import Mock, patch
from src.markets.cn_stock import CNStockAdapter
from src.data.models import Price


class TestCNStockAdapter:
    """Test CN stock adapter."""

    def test_normalize_ticker(self):
        """Test ticker normalization."""
        adapter = CNStockAdapter()

        # Test 6-digit ticker
        assert adapter.normalize_ticker("000001") == "000001"
        assert adapter.normalize_ticker("600000") == "600000"

        # Test with exchange prefix
        assert adapter.normalize_ticker("SH600000") == "600000"
        assert adapter.normalize_ticker("SZ000001") == "000001"

        # Test padding
        assert adapter.normalize_ticker("1") == "000001"
        assert adapter.normalize_ticker("001") == "000001"

    def test_detect_exchange(self):
        """Test exchange detection."""
        adapter = CNStockAdapter()

        # Shanghai stocks (start with 6)
        assert adapter.detect_exchange("600000") == "SH"
        assert adapter.detect_exchange("601398") == "SH"

        # Shenzhen stocks (start with 0 or 3)
        assert adapter.detect_exchange("000001") == "SZ"
        assert adapter.detect_exchange("000002") == "SZ"
        assert adapter.detect_exchange("300001") == "SZ"

    def test_get_full_ticker(self):
        """Test full ticker generation."""
        adapter = CNStockAdapter()

        assert adapter.get_full_ticker("600000") == "SH600000"
        assert adapter.get_full_ticker("000001") == "SZ000001"
        assert adapter.get_full_ticker("300001") == "SZ300001"

    @patch('src.markets.sources.akshare_source.AKShareSource.get_prices')
    def test_get_prices(self, mock_get_prices):
        """Test getting prices with mocked data source."""
        adapter = CNStockAdapter()

        # Mock data
        mock_prices = [
            {
                "open": 10.0,
                "close": 10.5,
                "high": 11.0,
                "low": 9.5,
                "volume": 1000000,
                "time": "2024-01-01T00:00:00Z",
            }
        ]
        mock_get_prices.return_value = mock_prices

        # Get prices
        prices = adapter.get_prices("000001", "2024-01-01", "2024-01-31")

        # Verify
        assert len(prices) > 0
        assert isinstance(prices[0], Price)
        mock_get_prices.assert_called_once()

    @patch('src.markets.sources.akshare_source.AKShareSource.get_financial_metrics')
    def test_get_financial_metrics(self, mock_get_metrics):
        """Test getting financial metrics with mocked data source."""
        adapter = CNStockAdapter()

        # Mock data
        mock_metrics = {
            "ticker": "000001",
            "price_to_earnings_ratio": 15.5,
            "price_to_book_ratio": 2.0,
            "return_on_equity": 0.15,
        }
        mock_get_metrics.return_value = mock_metrics

        # Get metrics
        metrics = adapter.get_financial_metrics("000001", "2024-01-31")

        # Verify
        assert metrics is not None
        assert metrics["ticker"] == "000001"
        mock_get_metrics.assert_called_once()

    @patch('src.markets.sources.akshare_source.AKShareSource.get_company_news')
    def test_get_company_news(self, mock_get_news):
        """Test getting company news with mocked data source."""
        adapter = CNStockAdapter()

        # Mock data
        mock_news = [
            {
                "ticker": "000001",
                "title": "Company announces earnings",
                "date": "2024-01-15T00:00:00Z",
                "source": "News Source",
                "url": "https://example.com/news",
                "author": "Author",
                "sentiment": None,
            }
        ]
        mock_get_news.return_value = mock_news

        # Get news
        news = adapter.get_company_news("000001", "2024-01-31")

        # Verify
        assert len(news) > 0
        assert news[0]["ticker"] == "000001"
        mock_get_news.assert_called_once()
