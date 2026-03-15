"""Tests for enhanced AKShare HK financial metrics."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.markets.sources.akshare_source import AKShareSource
import pandas as pd


class TestAKShareHKEnhanced:
    """Test enhanced AKShare HK financial data retrieval."""

    @pytest.fixture
    def mock_akshare_data(self):
        """Mock data from AKShare API."""
        return pd.DataFrame([{
            "基本每股收益(元)": 18.316,
            "每股净资产(元)": 128.054145,
            "法定股本(股)": 50000000000,
            "每手股": 100,
            "每股股息TTM(港元)": 4.5,
            "派息比率(%)": 17.3535,
            "已发行股本(股)": 9106356125,
            "已发行股本-H股(股)": 9106356125,
            "每股经营现金流(元)": 25.846926,
            "股息率TTM(%)": 0.821918,
            "总市值(港元)": 4985729978437.5,
            "港股市值(港元)": 4985729978437.5,
            "营业总收入": 557395000000,
            "营业总收入滚动环比增长(%)": 3.646304,
            "销售净利率(%)": 30.626755,
            "净利润": 166582000000,
            "净利润滚动环比增长(%)": 4.760989,
            "股东权益回报率(%)": 15.527575,
            "市盈率": 21.330468,
            "市净率": 3.883585,
            "总资产回报率(%)": 8.644030,
        }])

    @patch('akshare.stock_hk_financial_indicator_em')
    def test_enhanced_metrics_completeness(self, mock_api, mock_akshare_data):
        """Test that enhanced implementation provides all critical fields."""
        mock_api.return_value = mock_akshare_data

        source = AKShareSource()
        metrics = source.get_financial_metrics("00700", "2024-12-31")

        assert metrics is not None

        # Critical fields that analysts need
        critical_fields = [
            "return_on_equity",
            "net_margin",
            "operating_margin",  # Should be estimated
            "gross_margin",      # Should be estimated
            "debt_to_equity",    # Should be estimated
            "current_ratio",     # Should be estimated
            "revenue",
            "net_income",
            "revenue_growth",
            "earnings_growth",
            "price_to_earnings_ratio",
            "price_to_book_ratio",
            "market_cap",
            "earnings_per_share",
            "book_value_per_share",
        ]

        # All critical fields should be present and non-null
        for field in critical_fields:
            assert field in metrics, f"Missing field: {field}"
            assert metrics[field] is not None, f"Field {field} is None"

    @patch('akshare.stock_hk_financial_indicator_em')
    def test_margin_estimations(self, mock_api, mock_akshare_data):
        """Test that margin estimations are reasonable."""
        mock_api.return_value = mock_akshare_data

        source = AKShareSource()
        metrics = source.get_financial_metrics("00700", "2024-12-31")

        net_margin = metrics["net_margin"]
        operating_margin = metrics["operating_margin"]
        gross_margin = metrics["gross_margin"]

        # Operating margin should be higher than net margin
        assert operating_margin > net_margin, "Operating margin should be > net margin"

        # Gross margin should be higher than operating margin
        assert gross_margin > operating_margin, "Gross margin should be > operating margin"

        # Reasonable ranges (converted from % to decimal)
        assert 0.20 < net_margin < 0.50, "Net margin should be 20-50%"
        assert 0.30 < operating_margin < 0.70, "Operating margin should be 30-70%"
        assert 0.40 < gross_margin < 0.80, "Gross margin should be 40-80%"

    @patch('akshare.stock_hk_financial_indicator_em')
    def test_debt_to_equity_estimation(self, mock_api, mock_akshare_data):
        """Test debt-to-equity estimation from ROE and ROA."""
        mock_api.return_value = mock_akshare_data

        source = AKShareSource()
        metrics = source.get_financial_metrics("00700", "2024-12-31")

        debt_to_equity = metrics["debt_to_equity"]

        # Should be estimated from ROE/ROA relationship
        assert debt_to_equity is not None
        # Should be reasonable (0-5 range)
        assert 0 <= debt_to_equity <= 5, f"Debt to equity {debt_to_equity} out of reasonable range"

        # Verify calculation: D/E = (ROE/ROA) - 1
        roe = metrics["return_on_equity"]
        roa = metrics["return_on_assets"]
        expected_de = (roe / roa) - 1
        assert abs(debt_to_equity - expected_de) < 0.01, "Debt to equity calculation incorrect"

    @patch('akshare.stock_hk_financial_indicator_em')
    def test_current_ratio_estimation(self, mock_api, mock_akshare_data):
        """Test current ratio estimation based on ROE."""
        mock_api.return_value = mock_akshare_data

        source = AKShareSource()
        metrics = source.get_financial_metrics("00700", "2024-12-31")

        current_ratio = metrics["current_ratio"]
        roe = metrics["return_on_equity"]

        # Should be estimated based on ROE
        assert current_ratio is not None

        # For ROE >= 15%, should estimate 2.0
        if roe >= 0.15:
            assert current_ratio == 2.0, "High ROE should imply current ratio of 2.0"

    @patch('akshare.stock_hk_financial_indicator_em')
    def test_percentage_conversion(self, mock_api, mock_akshare_data):
        """Test that percentages are converted from API format (0-100) to decimal (0-1)."""
        mock_api.return_value = mock_akshare_data

        source = AKShareSource()
        metrics = source.get_financial_metrics("00700", "2024-12-31")

        # These should be decimals (not percentages)
        assert metrics["return_on_equity"] < 1, "ROE should be decimal, not percentage"
        assert metrics["net_margin"] < 1, "Net margin should be decimal, not percentage"
        assert metrics["revenue_growth"] < 1, "Revenue growth should be decimal, not percentage"

        # Original API value was 15.527575%, should be ~0.155
        assert 0.15 < metrics["return_on_equity"] < 0.16

    @patch('akshare.stock_hk_financial_indicator_em')
    def test_shareholders_equity_calculation(self, mock_api, mock_akshare_data):
        """Test shareholders equity calculation."""
        mock_api.return_value = mock_akshare_data

        source = AKShareSource()
        metrics = source.get_financial_metrics("00700", "2024-12-31")

        shareholders_equity = metrics["shareholders_equity"]
        book_value_per_share = metrics["book_value_per_share"]
        shares_outstanding = metrics["shares_outstanding"]

        # Should be calculated from BVPS * shares
        expected_equity = book_value_per_share * shares_outstanding
        assert abs(shareholders_equity - expected_equity) < 1000, "Shareholders equity calculation incorrect"

    @patch('akshare.stock_hk_financial_indicator_em')
    def test_handles_missing_data_gracefully(self, mock_api):
        """Test that missing fields are handled gracefully."""
        # Mock data with some fields missing
        incomplete_data = pd.DataFrame([{
            "股东权益回报率(%)": 15.5,
            "总资产回报率(%)": 8.6,
            # Missing net margin, revenue, etc.
        }])
        mock_api.return_value = incomplete_data

        source = AKShareSource()
        metrics = source.get_financial_metrics("00700", "2024-12-31")

        assert metrics is not None
        # Should still have ROE and ROA
        assert metrics["return_on_equity"] is not None
        assert metrics["return_on_assets"] is not None
        # Missing fields should be None
        assert metrics["net_margin"] is None
        assert metrics["revenue"] is None

    @patch('akshare.stock_hk_financial_indicator_em')
    def test_empty_dataframe_handling(self, mock_api):
        """Test handling of empty dataframe from API."""
        mock_api.return_value = pd.DataFrame()

        source = AKShareSource()
        metrics = source.get_financial_metrics("00700", "2024-12-31")

        assert metrics is None

    @patch('akshare.stock_hk_financial_indicator_em')
    def test_api_exception_handling(self, mock_api):
        """Test handling of API exceptions."""
        mock_api.side_effect = Exception("API Error")

        source = AKShareSource()
        metrics = source.get_financial_metrics("00700", "2024-12-31")

        assert metrics is None

    @patch('akshare.stock_hk_financial_indicator_em')
    def test_field_aliases(self, mock_api, mock_akshare_data):
        """Test that field aliases are provided for compatibility."""
        mock_api.return_value = mock_akshare_data

        source = AKShareSource()
        metrics = source.get_financial_metrics("00700", "2024-12-31")

        # Check aliases exist
        assert "earnings_growth" in metrics
        assert "outstanding_shares" in metrics

        # Aliases should match primary fields
        assert metrics["earnings_growth"] == metrics["net_income_growth"]
        assert metrics["outstanding_shares"] == metrics["shares_outstanding"]

    @patch('akshare.stock_hk_financial_indicator_em')
    def test_logging_completeness(self, mock_api, mock_akshare_data, caplog):
        """Test that data completeness is logged properly."""
        mock_api.return_value = mock_akshare_data

        source = AKShareSource()
        with caplog.at_level("INFO"):
            metrics = source.get_financial_metrics("00700", "2024-12-31")

        # Should log completeness statistics
        assert any("fields populated" in record.message for record in caplog.records)
        assert any("estimated" in record.message for record in caplog.records)
