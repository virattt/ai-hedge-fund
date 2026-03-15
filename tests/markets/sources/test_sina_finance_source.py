"""Tests for SinaFinanceSource."""
import pytest
import re
from src.markets.sources.sina_finance_source import SinaFinanceSource


class TestSinaFinanceSourceInit:
    def test_initialization(self):
        """Test SinaFinanceSource initializes correctly."""
        source = SinaFinanceSource()

        assert source.name == "SinaFinance"
        assert source.supports_market("US")
        assert source.supports_market("CN")
        assert source.supports_market("HK")

    def test_ticker_format_conversion(self):
        """Test ticker format conversion."""
        source = SinaFinanceSource()

        # CN market
        assert source._to_sina_symbol("600000.SH", "CN") == "sh600000"
        assert source._to_sina_symbol("000001.SZ", "CN") == "sz000001"

        # HK market
        assert source._to_sina_symbol("0700.HK", "HK") == "hk00700"

        # US market
        assert source._to_sina_symbol("AAPL", "US") == "gb_aapl"


class TestSinaFinancePricesCN:
    def test_get_prices_cn_stock(self, requests_mock):
        """Test fetching CN stock prices."""
        source = SinaFinanceSource()

        # Mock Sina CN K-line API
        requests_mock.get(
            re.compile(r'https://quotes\.sina\.cn/cn/api/json_v2\.php.*'),
            json=[
                {
                    'day': '2024-01-01',
                    'open': '100.00',
                    'close': '105.00',
                    'high': '106.00',
                    'low': '99.00',
                    'volume': '1000000'
                },
                {
                    'day': '2024-01-02',
                    'open': '105.00',
                    'close': '107.00',
                    'high': '108.00',
                    'low': '104.00',
                    'volume': '1200000'
                }
            ]
        )

        prices = source.get_prices("600000.SH", "2024-01-01", "2024-01-02")

        assert len(prices) == 2
        assert prices[0]["open"] == 100.0
        assert prices[0]["close"] == 105.0
        assert "time" in prices[0]
