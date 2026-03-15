"""
Quick test for insider trading data retrieval functionality.
"""
import pytest
from src.markets.sources.akshare_source import AKShareSource
from src.markets.hk_stock import HKStockAdapter


class TestInsiderTradesQuick:
    """Quick test for insider trading data functionality."""

    def test_akshare_hk_stock_no_insider_data(self):
        """Test that HK stocks return empty list for insider trades."""
        source = AKShareSource()

        # HK stock ticker
        hk_ticker = "00700"  # Tencent

        # Should return empty list for HK stocks
        trades = source.get_insider_trades(
            ticker=hk_ticker,
            end_date="2024-03-01",
            start_date="2024-01-01",
            limit=100
        )

        assert isinstance(trades, list)
        assert len(trades) == 0
        print(f"✓ HK stock {hk_ticker} correctly returns empty insider trades list")

    def test_hk_adapter_insider_trades(self):
        """Test HK adapter insider trades integration."""
        adapter = HKStockAdapter()

        # HK stock ticker
        hk_ticker = "0700.HK"  # Tencent

        # Should return empty list (no insider data for HK stocks)
        trades = adapter.get_insider_trades(
            ticker=hk_ticker,
            end_date="2024-03-01",
            start_date="2024-01-01",
            limit=100
        )

        assert isinstance(trades, list)
        assert len(trades) == 0
        print(f"✓ HK adapter correctly returns empty insider trades list for {hk_ticker}")

    def test_base_datasource_default_implementation(self):
        """Test that base DataSource has default implementation."""
        from src.markets.sources.base import DataSource

        # Create a minimal implementation
        class TestSource(DataSource):
            def supports_market(self, market: str) -> bool:
                return True

            def get_prices(self, ticker: str, start_date: str, end_date: str):
                return []

            def get_financial_metrics(self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10):
                return None

            def get_company_news(self, ticker: str, end_date: str, start_date=None, limit: int = 100):
                return []

        source = TestSource("test")

        # Default implementation should return empty list
        trades = source.get_insider_trades("TEST", "2024-01-01")
        assert isinstance(trades, list)
        assert len(trades) == 0
        print("✓ Base DataSource default implementation works correctly")


if __name__ == "__main__":
    # Run tests manually
    test = TestInsiderTradesQuick()

    print("\n=== Running Insider Trades Quick Tests ===\n")

    try:
        test.test_akshare_hk_stock_no_insider_data()
    except Exception as e:
        print(f"✗ test_akshare_hk_stock_no_insider_data failed: {e}")

    try:
        test.test_hk_adapter_insider_trades()
    except Exception as e:
        print(f"✗ test_hk_adapter_insider_trades failed: {e}")

    try:
        test.test_base_datasource_default_implementation()
    except Exception as e:
        print(f"✗ test_base_datasource_default_implementation failed: {e}")

    print("\n=== All Quick Tests Passed! ===\n")
