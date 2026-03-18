"""Tests for Eastmoney data source."""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.markets.sources.eastmoney_source import EastmoneySource


class TestEastmoneySource:
    """Test Eastmoney data source."""

    def test_init(self):
        """Test initialization."""
        source = EastmoneySource()
        assert source.name == "Eastmoney"
        assert source.session is not None

    def test_supports_market(self):
        """Test market support detection."""
        source = EastmoneySource()
        assert source.supports_market("CN") is True
        assert source.supports_market("cn") is True
        assert source.supports_market("HK") is False
        assert source.supports_market("US") is False

    def test_detect_cn_ticker(self):
        """Test CN ticker detection."""
        source = EastmoneySource()

        # Valid CN tickers
        assert source._detect_cn_ticker("600000.SH") is True
        assert source._detect_cn_ticker("000001.SZ") is True
        assert source._detect_cn_ticker("SH600000") is True
        assert source._detect_cn_ticker("SZ000001") is True
        assert source._detect_cn_ticker("600000") is True
        assert source._detect_cn_ticker("000001") is True

        # Invalid tickers
        assert source._detect_cn_ticker("AAPL") is False
        assert source._detect_cn_ticker("0700.HK") is False
        assert source._detect_cn_ticker("12345") is False

    def test_to_eastmoney_secid_shanghai(self):
        """Test ticker conversion for Shanghai stocks."""
        source = EastmoneySource()

        # Different Shanghai formats
        assert source._to_eastmoney_secid("600000.SH") == "1.600000"
        assert source._to_eastmoney_secid("SH600000") == "1.600000"
        assert source._to_eastmoney_secid("600000") == "1.600000"
        assert source._to_eastmoney_secid("601318.SH") == "1.601318"

    def test_to_eastmoney_secid_shenzhen(self):
        """Test ticker conversion for Shenzhen stocks."""
        source = EastmoneySource()

        # Different Shenzhen formats
        assert source._to_eastmoney_secid("000001.SZ") == "0.000001"
        assert source._to_eastmoney_secid("SZ000001") == "0.000001"
        assert source._to_eastmoney_secid("000001") == "0.000001"
        assert source._to_eastmoney_secid("300750.SZ") == "0.300750"
        assert source._to_eastmoney_secid("300750") == "0.300750"

    def test_parse_klines(self):
        """Test K-line parsing."""
        source = EastmoneySource()

        # Sample K-line data
        klines = [
            "2024-01-02,10.50,10.80,10.90,10.40,12345678,133456789.00,4.76,2.86,0.30,1.23",
            "2024-01-03,10.80,11.00,11.10,10.70,15678901,172456789.00,3.70,1.85,0.20,1.50",
        ]

        prices = source._parse_klines(klines)

        assert len(prices) == 2

        # Check first price
        assert prices[0]['open'] == 10.50
        assert prices[0]['close'] == 10.80
        assert prices[0]['high'] == 10.90
        assert prices[0]['low'] == 10.40
        assert prices[0]['volume'] == 12345678
        assert prices[0]['time'] == "2024-01-02T00:00:00Z"

        # Check second price
        assert prices[1]['open'] == 10.80
        assert prices[1]['close'] == 11.00
        assert prices[1]['high'] == 11.10
        assert prices[1]['low'] == 10.70
        assert prices[1]['volume'] == 15678901
        assert prices[1]['time'] == "2024-01-03T00:00:00Z"

    def test_parse_klines_invalid_format(self):
        """Test K-line parsing with invalid format."""
        source = EastmoneySource()

        # Invalid K-line data
        klines = [
            "2024-01-02,10.50",  # Too few fields
            "invalid,data,format",  # Invalid numbers
            "2024-01-03,10.80,11.00,11.10,10.70,15678901,172456789.00,3.70,1.85,0.20,1.50",  # Valid
        ]

        prices = source._parse_klines(klines)

        # Should only parse the valid one
        assert len(prices) == 1
        assert prices[0]['time'] == "2024-01-03T00:00:00Z"

    @patch('src.markets.sources.eastmoney_source.requests.Session.get')
    def test_get_prices_success(self, mock_get):
        """Test successful price fetching."""
        source = EastmoneySource()

        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'rc': 0,
            'data': {
                'klines': [
                    "2024-01-02,10.50,10.80,10.90,10.40,12345678,133456789.00,4.76,2.86,0.30,1.23",
                    "2024-01-03,10.80,11.00,11.10,10.70,15678901,172456789.00,3.70,1.85,0.20,1.50",
                ]
            }
        }
        mock_get.return_value = mock_response

        prices = source.get_prices("600000.SH", "2024-01-01", "2024-01-31")

        assert len(prices) == 2
        assert prices[0]['open'] == 10.50
        assert prices[1]['open'] == 10.80

    @patch('src.markets.sources.eastmoney_source.requests.Session.get')
    def test_get_prices_empty_response(self, mock_get):
        """Test price fetching with empty response."""
        source = EastmoneySource()

        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = {
            'rc': 0,
            'data': {}
        }
        mock_get.return_value = mock_response

        prices = source.get_prices("600000.SH", "2024-01-01", "2024-01-31")

        assert prices == []

    @patch('src.markets.sources.eastmoney_source.requests.Session.get')
    def test_get_prices_api_error(self, mock_get):
        """Test price fetching with API error."""
        source = EastmoneySource()

        # Mock API error
        mock_response = Mock()
        mock_response.json.return_value = {
            'rc': -1,
            'message': 'Error'
        }
        mock_get.return_value = mock_response

        prices = source.get_prices("600000.SH", "2024-01-01", "2024-01-31")

        assert prices == []

    def test_get_prices_non_cn_ticker(self):
        """Test price fetching with non-CN ticker."""
        source = EastmoneySource()

        prices = source.get_prices("AAPL", "2024-01-01", "2024-01-31")

        assert prices == []

    @patch('src.markets.sources.eastmoney_source.requests.Session.get')
    def test_get_financial_metrics_success(self, mock_get):
        """Test successful financial metrics fetching."""
        source = EastmoneySource()

        # Mock API response with financial data
        mock_response = Mock()
        mock_response.json.return_value = {
            'data': {
                'f116': 1000000000000,  # Market cap (1 trillion) - f116 is total market cap
                'f162': 15.5,           # PE ratio
                'f167': 1.8,            # PB ratio
                'f173': 12.5,           # ROE
                'f187': 35.2,           # Gross margin
            }
        }
        mock_get.return_value = mock_response

        metrics = source.get_financial_metrics("600000.SH", "2024-01-31")

        assert metrics is not None
        assert metrics['ticker'] == "600000.SH"
        assert metrics['currency'] == "CNY"
        assert metrics['market_cap'] == 1000000000000
        assert metrics['price_to_earnings_ratio'] == 15.5
        assert metrics['price_to_book_ratio'] == 1.8
        assert metrics['return_on_equity'] == 12.5
        assert metrics['gross_margin'] == 35.2

    @patch('src.markets.sources.eastmoney_source.requests.Session.get')
    def test_get_financial_metrics_empty_response(self, mock_get):
        """Test financial metrics with empty response."""
        source = EastmoneySource()

        # Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        metrics = source.get_financial_metrics("600000.SH", "2024-01-31")

        assert metrics is None

    def test_get_financial_metrics_non_cn_ticker(self):
        """Test financial metrics with non-CN ticker."""
        source = EastmoneySource()

        metrics = source.get_financial_metrics("AAPL", "2024-01-31")

        assert metrics is None

    def test_safe_float(self):
        """Test safe float conversion."""
        source = EastmoneySource()

        # Valid conversions
        assert source._safe_float(15.5) == 15.5
        assert source._safe_float("15.5") == 15.5
        assert source._safe_float(100) == 100.0

        # Invalid values
        assert source._safe_float(None) is None
        assert source._safe_float("") is None
        assert source._safe_float("-") is None
        assert source._safe_float("invalid") is None

    def test_get_company_news_not_supported(self):
        """Test company news (not supported)."""
        source = EastmoneySource()

        news = source.get_company_news("600000.SH", "2024-01-31")

        assert news == []


@pytest.mark.integration
class TestEastmoneySourceIntegration:
    """Integration tests for Eastmoney data source (requires network)."""

    def test_get_prices_real_api(self):
        """Test fetching real price data from Eastmoney API."""
        source = EastmoneySource()

        # Test with a well-known CN stock (招商银行 600036.SH)
        prices = source.get_prices("600036.SH", "2024-01-01", "2024-01-31")

        # Should have price data for January 2024
        assert len(prices) > 0
        assert all('open' in p for p in prices)
        assert all('close' in p for p in prices)
        assert all('high' in p for p in prices)
        assert all('low' in p for p in prices)
        assert all('volume' in p for p in prices)
        assert all('time' in p for p in prices)

        # Verify price data is reasonable
        for price in prices:
            assert price['open'] > 0
            assert price['close'] > 0
            assert price['high'] >= price['low']
            assert price['volume'] >= 0

    def test_get_prices_different_formats(self):
        """Test price fetching with different ticker formats."""
        source = EastmoneySource()

        # Same stock, different formats
        prices_1 = source.get_prices("600036.SH", "2024-01-01", "2024-01-10")
        prices_2 = source.get_prices("SH600036", "2024-01-01", "2024-01-10")
        prices_3 = source.get_prices("600036", "2024-01-01", "2024-01-10")

        # All should return data
        assert len(prices_1) > 0
        assert len(prices_2) > 0
        assert len(prices_3) > 0

        # Should have same number of records
        assert len(prices_1) == len(prices_2) == len(prices_3)

    def test_get_financial_metrics_real_api(self):
        """Test fetching real financial metrics from Eastmoney API."""
        source = EastmoneySource()

        # Test with a well-known CN stock (招商银行 600036.SH)
        metrics = source.get_financial_metrics("600036.SH", "2024-01-31")

        # Should have basic metrics
        assert metrics is not None
        assert metrics['ticker'] == "600036.SH"
        assert metrics['currency'] == "CNY"

        # Check that we have some valuation metrics
        # PE and PB are typically available
        if metrics.get('price_to_earnings_ratio'):
            assert metrics['price_to_earnings_ratio'] > 0

        if metrics.get('price_to_book_ratio'):
            assert metrics['price_to_book_ratio'] > 0
