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
