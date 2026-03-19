"""Integration tests for multi-source data validation."""
import pytest
from unittest.mock import patch
from src.markets.cn_stock import CNStockAdapter
from src.markets.hk_stock import HKStockAdapter
from src.data.validation import DataValidator


class TestMultiSourceIntegration:
    """Test multi-source integration."""

    @patch('src.markets.sources.akshare_source.AKShareSource.get_prices')
    def test_cn_stock_single_source_integration(self, mock_ak_prices):
        """Test CN stock adapter with single source."""
        # Mock AKShare data
        mock_ak_prices.return_value = [
            {
                "open": 10.0,
                "close": 10.5,
                "high": 11.0,
                "low": 9.5,
                "volume": 1000000,
                "time": "2024-01-01T00:00:00Z",
            },
            {
                "open": 10.5,
                "close": 11.0,
                "high": 11.5,
                "low": 10.0,
                "volume": 1100000,
                "time": "2024-01-02T00:00:00Z",
            },
        ]

        # Create adapter with custom validator
        validator = DataValidator(price_threshold=0.02)
        adapter = CNStockAdapter(validator=validator)

        # Get prices
        prices = adapter.get_prices("000001", "2024-01-01", "2024-01-02")

        # Verify results
        assert len(prices) == 2
        assert prices[0].close == 10.5
        assert prices[1].close == 11.0

    @patch('src.markets.sources.akshare_source.AKShareSource.get_prices')
    @patch('src.markets.sources.yfinance_source.YFinanceSource.get_prices')
    def test_hk_stock_multi_source_integration(self, mock_yf_prices, mock_ak_prices):
        """Test HK stock adapter with multiple sources and validation."""
        # Mock AKShare data
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

        # Mock YFinance data (slightly different)
        mock_yf_prices.return_value = [
            {
                "open": 100.2,
                "close": 101.2,
                "high": 102.2,
                "low": 99.2,
                "volume": 1050000,
                "time": "2024-01-01T00:00:00Z",
            }
        ]

        # Create adapter with custom validator
        validator = DataValidator(
            source_weights={
                "AKShare": 1.0,
                "YFinance": 0.8,
            },
            price_threshold=0.02
        )
        adapter = HKStockAdapter(validator=validator)

        # Get prices (should merge from both sources)
        prices = adapter.get_prices("00700", "2024-01-01", "2024-01-01")

        # Verify results
        assert len(prices) == 1
        # Should be weighted average between 101.0 and 101.2
        assert 101.0 <= prices[0].close <= 101.2

    @patch('src.markets.sources.akshare_source.AKShareSource.get_prices')
    @patch('src.markets.sources.yfinance_source.YFinanceSource.get_prices')
    def test_data_source_fallback(self, mock_yf_prices, mock_ak_prices):
        """Test fallback when primary source fails."""
        # Primary source (AKShare) fails
        mock_ak_prices.side_effect = Exception("Connection error")

        # Fallback source (YFinance) succeeds
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

        # Create adapter
        adapter = HKStockAdapter()

        # Get prices (should use fallback)
        prices = adapter.get_prices("00700", "2024-01-01", "2024-01-01")

        # Verify fallback worked
        assert len(prices) == 1
        assert prices[0].close == 101.0

    @patch('src.markets.sources.akshare_source.AKShareSource.get_prices')
    @patch('src.markets.sources.yfinance_source.YFinanceSource.get_prices')
    def test_high_deviation_handling(self, mock_yf_prices, mock_ak_prices):
        """Test handling of high price deviation between sources."""
        # Mock AKShare data
        mock_ak_prices.return_value = [
            {
                "open": 100.0,
                "close": 100.0,
                "high": 102.0,
                "low": 99.0,
                "volume": 1000000,
                "time": "2024-01-01T00:00:00Z",
            }
        ]

        # Mock YFinance data with significant deviation
        mock_yf_prices.return_value = [
            {
                "open": 100.0,
                "close": 105.0,  # 5% deviation
                "high": 106.0,
                "low": 99.0,
                "volume": 1000000,
                "time": "2024-01-01T00:00:00Z",
            }
        ]

        # Create adapter with strict threshold
        validator = DataValidator(price_threshold=0.02)
        adapter = HKStockAdapter(validator=validator)

        # Get prices
        prices = adapter.get_prices("00700", "2024-01-01", "2024-01-01")

        # Should still return data (weighted average) despite deviation
        assert len(prices) == 1
        # Price should be weighted average
        assert 100.0 <= prices[0].close <= 105.0

    def test_ticker_normalization(self):
        """Test ticker normalization across adapters."""
        cn_adapter = CNStockAdapter()
        hk_adapter = HKStockAdapter()

        # Test CN normalization
        assert cn_adapter.normalize_ticker("SH600000") == "600000"
        assert cn_adapter.normalize_ticker("000001") == "000001"
        assert cn_adapter.normalize_ticker("1") == "000001"

        # Test HK normalization
        assert hk_adapter.normalize_ticker("700") == "00700"
        assert hk_adapter.normalize_ticker("0700.HK") == "00700"
        assert hk_adapter.normalize_ticker("00700") == "00700"

    @patch('src.markets.sources.akshare_source.AKShareSource.get_financial_metrics')
    @patch('src.markets.sources.xueqiu_source.XueqiuSource.get_financial_metrics')
    def test_financial_metrics_merging(self, mock_xq_metrics, mock_ak_metrics):
        """Test merging of financial metrics from multiple sources."""
        # Mock AKShare metrics
        mock_ak_metrics.return_value = {
            "ticker": "00700",
            "price_to_earnings_ratio": 25.0,
            "return_on_equity": 0.20,
            "gross_margin": 0.45,
        }

        # Mock Xueqiu metrics
        mock_xq_metrics.return_value = {
            "ticker": "00700",
            "price_to_earnings_ratio": 26.0,
            "return_on_equity": 0.22,
            "gross_margin": 0.46,
        }

        # Create adapter with custom weights
        validator = DataValidator(
            source_weights={
                "AKShare": 1.0,
                "Xueqiu": 0.8,
            }
        )
        adapter = HKStockAdapter(validator=validator)

        # Get metrics
        metrics = adapter.get_financial_metrics("00700", "2024-01-31")

        # Verify merging
        assert metrics is not None
        # Should be weighted average of AKShare(25.0, w=1.0) and Xueqiu(26.0, w=0.8)
        # = (25*1.0 + 26*0.8) / (1.0+0.8) = 45.8/1.8 = 25.44
        assert 25.0 <= metrics["price_to_earnings_ratio"] <= 26.0
        assert 0.20 <= metrics["return_on_equity"] <= 0.22
        # Should include metadata
        assert "num_sources" in metrics
        assert metrics["num_sources"] == 2
        assert "confidence" in metrics
        assert metrics["confidence"] > 0.6
