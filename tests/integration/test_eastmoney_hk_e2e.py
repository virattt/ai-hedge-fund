"""End-to-end integration tests for Eastmoney HK stock data.

These tests hit the real Eastmoney API. Run only when internet is available.
Mark with pytest.mark.integration to skip in CI if needed.
"""
import pytest
from src.markets.sources.eastmoney_source import EastmoneySource


@pytest.mark.integration
class TestEastmoneyHKPrices:
    """Test Eastmoney price fetching for HK stocks."""

    def setup_method(self):
        self.source = EastmoneySource()

    def test_get_prices_meituan_hk_suffix(self):
        """Fetch Meituan prices using .HK suffix format."""
        prices = self.source.get_prices("03690.HK", "2024-01-01", "2024-01-31")
        assert len(prices) > 0, "Should return price data for Meituan"
        price = prices[0]
        assert 'open' in price
        assert 'close' in price
        assert 'high' in price
        assert 'low' in price
        assert 'volume' in price
        assert 'time' in price
        assert price['close'] > 0

    def test_get_prices_tencent_five_digit(self):
        """Fetch Tencent prices using 5-digit format."""
        prices = self.source.get_prices("00700", "2024-01-01", "2024-01-31")
        assert len(prices) > 0, "Should return price data for Tencent"
        assert prices[0]['close'] > 0

    def test_price_data_within_date_range(self):
        """Prices should fall within requested date range."""
        prices = self.source.get_prices("03690.HK", "2024-06-01", "2024-06-30")
        assert len(prices) > 0
        for p in prices:
            date_str = p['time'][:10]  # YYYY-MM-DD
            assert "2024-06" in date_str, f"Date {date_str} outside June 2024"


@pytest.mark.integration
class TestEastmoneyHKFinancialMetrics:
    """Test Eastmoney financial metrics for HK stocks."""

    def setup_method(self):
        self.source = EastmoneySource()

    def test_get_financial_metrics_meituan(self):
        """Fetch Meituan financial metrics."""
        metrics = self.source.get_financial_metrics("03690.HK", "2024-01-31")
        assert metrics is not None, "Should return metrics for Meituan"
        assert metrics['ticker'] == '03690.HK'
        assert metrics['currency'] == 'HKD'

    def test_financial_metrics_has_key_fields(self):
        """Financial metrics should have required fields."""
        metrics = self.source.get_financial_metrics("00700", "2024-01-31")
        assert metrics is not None
        # These fields should be present (may be None if not available)
        for field in ['market_cap', 'price_to_earnings_ratio', 'price_to_book_ratio',
                      'return_on_equity', 'gross_margin']:
            assert field in metrics, f"Missing field: {field}"

    def test_market_cap_is_positive(self):
        """Market cap should be a positive number for major HK stocks."""
        metrics = self.source.get_financial_metrics("00700", "2024-01-31")
        assert metrics is not None
        if metrics.get('market_cap'):
            assert metrics['market_cap'] > 0
