"""Tests for API tool functions in src/tools/api.py.

Tests prices_to_df conversion and API functions with mocked HTTP responses.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.models import Price
from src.tools.api import prices_to_df, get_prices, get_financial_metrics


class TestPricesToDf:
    def test_basic_conversion(self):
        prices = [
            Price(open=100.0, close=105.0, high=110.0, low=95.0, volume=1000, time="2024-01-02"),
            Price(open=105.0, close=102.0, high=106.0, low=101.0, volume=2000, time="2024-01-03"),
        ]
        df = prices_to_df(prices)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "close" in df.columns
        assert "open" in df.columns

    def test_sorted_by_date(self):
        prices = [
            Price(open=100.0, close=105.0, high=110.0, low=95.0, volume=1000, time="2024-01-05"),
            Price(open=105.0, close=102.0, high=106.0, low=101.0, volume=2000, time="2024-01-02"),
        ]
        df = prices_to_df(prices)
        assert df.index[0] < df.index[1]

    def test_numeric_columns(self):
        prices = [
            Price(open=100.0, close=105.0, high=110.0, low=95.0, volume=1000, time="2024-01-02"),
        ]
        df = prices_to_df(prices)
        for col in ["open", "close", "high", "low", "volume"]:
            assert pd.api.types.is_numeric_dtype(df[col])

    def test_empty_list_raises(self):
        """prices_to_df does not handle empty input gracefully — documents current behavior."""
        with pytest.raises(KeyError):
            prices_to_df([])

    def test_index_is_datetime(self):
        prices = [
            Price(open=100.0, close=105.0, high=110.0, low=95.0, volume=1000, time="2024-01-02"),
        ]
        df = prices_to_df(prices)
        assert df.index.name == "Date"
        assert pd.api.types.is_datetime64_any_dtype(df.index)


class TestGetPricesWithMock:
    """Test get_prices with mocked HTTP calls — no real API hits."""

    @patch("src.tools.api._cache")
    @patch("src.tools.api._make_api_request")
    def test_returns_prices_on_success(self, mock_request, mock_cache):
        mock_cache.get_prices.return_value = None  # cache miss
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ticker": "AAPL",
            "prices": [
                {"open": 100.0, "close": 105.0, "high": 110.0, "low": 95.0, "volume": 1000, "time": "2024-01-02"},
            ],
        }
        mock_request.return_value = mock_response

        result = get_prices("AAPL", "2024-01-01", "2024-01-31", api_key="test-key")
        assert len(result) == 1
        assert result[0].close == 105.0
        mock_cache.set_prices.assert_called_once()

    @patch("src.tools.api._cache")
    @patch("src.tools.api._make_api_request")
    def test_returns_empty_on_http_error(self, mock_request, mock_cache):
        mock_cache.get_prices.return_value = None
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_request.return_value = mock_response

        result = get_prices("AAPL", "2024-01-01", "2024-01-31", api_key="test-key")
        assert result == []

    @patch("src.tools.api._cache")
    def test_returns_cached_data(self, mock_cache):
        mock_cache.get_prices.return_value = [
            {"open": 100.0, "close": 105.0, "high": 110.0, "low": 95.0, "volume": 1000, "time": "2024-01-02"},
        ]
        result = get_prices("AAPL", "2024-01-01", "2024-01-31")
        assert len(result) == 1
        assert result[0].close == 105.0

    @patch("src.tools.api._cache")
    @patch("src.tools.api._make_api_request")
    def test_returns_empty_on_malformed_response(self, mock_request, mock_cache):
        mock_cache.get_prices.return_value = None
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"unexpected": "format"}
        mock_request.return_value = mock_response

        result = get_prices("AAPL", "2024-01-01", "2024-01-31", api_key="test-key")
        assert result == []


class TestGetFinancialMetricsWithMock:

    @patch("src.tools.api._cache")
    @patch("src.tools.api._make_api_request")
    def test_returns_metrics_on_success(self, mock_request, mock_cache):
        mock_cache.get_financial_metrics.return_value = None
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Must include all required fields (float|None without defaults)
        full_metric = {
            "ticker": "AAPL",
            "report_period": "2024-Q1",
            "period": "ttm",
            "currency": "USD",
            "market_cap": 3e12,
            "enterprise_value": None,
            "price_to_earnings_ratio": 28.5,
            "price_to_book_ratio": None,
            "price_to_sales_ratio": None,
            "enterprise_value_to_ebitda_ratio": None,
            "enterprise_value_to_revenue_ratio": None,
            "free_cash_flow_yield": None,
            "peg_ratio": None,
            "gross_margin": None,
            "operating_margin": None,
            "net_margin": None,
            "return_on_equity": None,
            "return_on_assets": None,
            "return_on_invested_capital": None,
            "asset_turnover": None,
            "inventory_turnover": None,
            "receivables_turnover": None,
            "days_sales_outstanding": None,
            "operating_cycle": None,
            "working_capital_turnover": None,
            "current_ratio": None,
            "quick_ratio": None,
            "cash_ratio": None,
            "operating_cash_flow_ratio": None,
            "debt_to_equity": None,
            "debt_to_assets": None,
            "interest_coverage": None,
            "revenue_growth": None,
            "earnings_growth": None,
            "book_value_growth": None,
            "earnings_per_share_growth": None,
            "free_cash_flow_growth": None,
            "operating_income_growth": None,
            "ebitda_growth": None,
            "payout_ratio": None,
            "earnings_per_share": None,
            "book_value_per_share": None,
            "free_cash_flow_per_share": None,
        }
        mock_response.json.return_value = {"financial_metrics": [full_metric]}
        mock_request.return_value = mock_response

        result = get_financial_metrics("AAPL", "2024-03-31", api_key="test-key")
        assert len(result) == 1
        assert result[0].market_cap == 3e12

    @patch("src.tools.api._cache")
    @patch("src.tools.api._make_api_request")
    def test_returns_empty_on_error(self, mock_request, mock_cache):
        mock_cache.get_financial_metrics.return_value = None
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_request.return_value = mock_response

        result = get_financial_metrics("AAPL", "2024-03-31", api_key="test-key")
        assert result == []
