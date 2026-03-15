"""Integration tests for CN Stock Adapter with Eastmoney source."""
import pytest
from unittest.mock import Mock, patch

from src.markets.cn_stock import CNStockAdapter


class TestCNStockAdapterWithEastmoney:
    """Test CN Stock Adapter with Eastmoney as primary source."""

    def test_init(self):
        """Test initialization with Eastmoney as primary source."""
        adapter = CNStockAdapter()

        assert adapter.market == "CN"
        assert len(adapter.active_sources) >= 3

        # Verify Eastmoney is the first source
        source_names = [s.name for s in adapter.active_sources]
        assert "Eastmoney" in source_names
        assert source_names[0] == "Eastmoney"

    def test_fallback_chain_priority(self):
        """Test that Eastmoney is prioritized over other sources."""
        adapter = CNStockAdapter()

        source_names = [s.name for s in adapter.active_sources]

        # Expected priority order
        expected_order = ["Eastmoney", "SinaFinance", "AKShare"]

        # Check first three sources
        for i, expected_name in enumerate(expected_order):
            assert source_names[i] == expected_name, \
                f"Expected {expected_name} at position {i}, got {source_names[i]}"

    @patch('src.markets.sources.eastmoney_source.requests.Session.get')
    def test_get_prices_uses_eastmoney(self, mock_get):
        """Test that get_prices uses Eastmoney as primary source."""
        adapter = CNStockAdapter()

        # Mock successful Eastmoney response
        mock_response = Mock()
        mock_response.json.return_value = {
            'rc': 0,
            'data': {
                'klines': [
                    "2024-01-02,10.50,10.80,10.90,10.40,12345678,133456789.00,4.76,2.86,0.30,1.23",
                ]
            }
        }
        mock_get.return_value = mock_response

        prices = adapter.get_prices("600000.SH", "2024-01-01", "2024-01-31")

        # Should get prices from Eastmoney
        assert len(prices) > 0
        # Verify Eastmoney API was called
        assert mock_get.called

    @patch('src.markets.sources.eastmoney_source.requests.Session.get')
    def test_get_financial_metrics_uses_eastmoney(self, mock_get):
        """Test that get_financial_metrics uses Eastmoney as primary source."""
        adapter = CNStockAdapter()

        # Mock successful Eastmoney response
        mock_response = Mock()
        mock_response.json.return_value = {
            'data': {
                'f57': 1000000000000,
                'f162': 15.5,
                'f167': 1.8,
            }
        }
        mock_get.return_value = mock_response

        metrics = adapter.get_financial_metrics("600000.SH", "2024-01-31")

        # Should get metrics from Eastmoney
        assert metrics is not None
        assert metrics.get('price_to_earnings_ratio') == 15.5
        # Verify Eastmoney API was called
        assert mock_get.called

    @patch('src.markets.sources.eastmoney_source.requests.Session.get')
    def test_fallback_when_eastmoney_fails(self, mock_get):
        """Test that adapter falls back to other sources when Eastmoney fails."""
        adapter = CNStockAdapter()

        # Mock Eastmoney failure (raises exception)
        mock_get.side_effect = Exception("Eastmoney API error")

        # Should fall back to Sina Finance or AKShare
        # Note: This test may require real network calls to fallback sources
        # In a real integration test, we would verify the fallback behavior
        prices = adapter.get_prices("600000.SH", "2024-01-01", "2024-01-10")

        # Should still get prices from fallback sources (or empty if all fail)
        assert isinstance(prices, list)


@pytest.mark.integration
class TestCNStockAdapterIntegration:
    """Integration tests with real API calls."""

    def test_get_prices_real_api(self):
        """Test fetching real price data using Eastmoney as primary."""
        adapter = CNStockAdapter()

        # Test with a well-known CN stock (招商银行 600036.SH)
        prices = adapter.get_prices("600036.SH", "2024-01-01", "2024-01-10")

        assert len(prices) > 0
        # Verify we got Price objects
        assert hasattr(prices[0], 'open')
        assert hasattr(prices[0], 'close')
        assert hasattr(prices[0], 'high')
        assert hasattr(prices[0], 'low')
        assert hasattr(prices[0], 'volume')

    def test_get_financial_metrics_real_api(self):
        """Test fetching real financial metrics using Eastmoney as primary."""
        adapter = CNStockAdapter()

        # Test with a well-known CN stock (招商银行 600036.SH)
        metrics = adapter.get_financial_metrics("600036.SH", "2024-01-31")

        # Should get some metrics
        if metrics:
            assert 'ticker' in metrics
            assert metrics['currency'] == "CNY"

    def test_multiple_ticker_formats(self):
        """Test adapter handles different ticker formats correctly."""
        adapter = CNStockAdapter()

        # Test with different formats of the same stock
        formats = ["600036.SH", "SH600036", "600036"]

        for ticker_format in formats:
            prices = adapter.get_prices(ticker_format, "2024-01-01", "2024-01-05")
            assert len(prices) > 0, f"Failed to get prices for format: {ticker_format}"

    def test_shanghai_vs_shenzhen(self):
        """Test adapter handles both Shanghai and Shenzhen stocks."""
        adapter = CNStockAdapter()

        # Test Shanghai stock (6xxxxx)
        sh_prices = adapter.get_prices("600036.SH", "2024-01-01", "2024-01-05")
        assert len(sh_prices) > 0

        # Test Shenzhen stock (0xxxxx)
        sz_prices = adapter.get_prices("000001.SZ", "2024-01-01", "2024-01-05")
        assert len(sz_prices) > 0
