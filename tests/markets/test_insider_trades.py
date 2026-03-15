"""
Test insider trading data retrieval functionality.
"""
import pytest
from src.markets.sources.akshare_source import AKShareSource
from src.markets.hk_stock import HKStockAdapter


class TestInsiderTrades:
    """Test insider trading data functionality."""

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

    def test_akshare_cn_stock_insider_data_format(self):
        """Test that CN stocks return properly formatted insider trades (if available)."""
        source = AKShareSource()

        # CN stock ticker (using a major stock that likely has insider trades)
        cn_ticker = "600000"  # 浦发银行

        # Get insider trades
        trades = source.get_insider_trades(
            ticker=cn_ticker,
            end_date="2026-03-01",
            start_date="2025-01-01",
            limit=10
        )

        # Should return a list (may be empty if no trades in period)
        assert isinstance(trades, list)

        # If trades exist, verify format
        if len(trades) > 0:
            trade = trades[0]

            # Check required fields exist
            assert "ticker" in trade
            assert "name" in trade
            assert "title" in trade
            assert "transaction_date" in trade
            assert "transaction_shares" in trade
            assert "transaction_price_per_share" in trade
            assert "filing_date" in trade

            # Verify ticker matches
            assert trade["ticker"] == cn_ticker

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

    def test_insider_trades_date_filtering(self):
        """Test that date filtering works correctly."""
        source = AKShareSource()

        # Use a CN stock
        cn_ticker = "600000"

        # Get trades for a short period
        trades_short = source.get_insider_trades(
            ticker=cn_ticker,
            end_date="2026-03-01",
            start_date="2026-02-01",
            limit=100
        )

        # Get trades for a longer period
        trades_long = source.get_insider_trades(
            ticker=cn_ticker,
            end_date="2026-03-01",
            start_date="2025-01-01",
            limit=100
        )

        # Both should be lists
        assert isinstance(trades_short, list)
        assert isinstance(trades_long, list)

        # Longer period should have >= trades than shorter period
        assert len(trades_long) >= len(trades_short)

    def test_insider_trades_limit(self):
        """Test that limit parameter works correctly."""
        source = AKShareSource()

        # Use a CN stock that likely has many insider trades
        cn_ticker = "600000"

        # Get trades with small limit
        trades = source.get_insider_trades(
            ticker=cn_ticker,
            end_date="2026-03-01",
            start_date="2024-01-01",
            limit=5
        )

        # Should respect limit
        assert isinstance(trades, list)
        assert len(trades) <= 5

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
