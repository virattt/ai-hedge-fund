"""Tests for NewsNowSource."""
import pytest
from src.markets.sources.newsnow_source import NewsNowSource


class TestNewsNowSourceInit:
    def test_initialization(self):
        """Test NewsNowSource initializes correctly."""
        source = NewsNowSource()

        assert source.name == "NewsNow"
        assert source.supports_market("US")
        assert source.supports_market("CN")
        assert source.supports_market("HK")
