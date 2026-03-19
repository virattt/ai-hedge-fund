from unittest.mock import MagicMock, patch
from src.markets.router import MarketRouter
from src.tools.api import get_financial_metrics
from src.data.models import FinancialMetrics


def test_market_router_has_get_historical_financial_metrics():
    """MarketRouter should expose get_historical_financial_metrics."""
    router = MarketRouter.__new__(MarketRouter)
    router.adapters = []
    assert hasattr(router, "get_historical_financial_metrics")


def test_market_router_get_historical_routes_to_adapter():
    """get_historical_financial_metrics routes to the correct adapter."""
    mock_adapter = MagicMock()
    mock_adapter.supports_ticker.return_value = True
    mock_adapter.get_historical_financial_metrics.return_value = [
        {"ticker": "03690", "report_period": "2024-12-31"},
        {"ticker": "03690", "report_period": "2023-12-31"},
    ]

    router = MarketRouter.__new__(MarketRouter)
    router.adapters = [mock_adapter]

    results = router.get_historical_financial_metrics("3690.HK", "2025-01-01", limit=5)

    mock_adapter.get_historical_financial_metrics.assert_called_once_with(
        "3690.HK", "2025-01-01", limit=5
    )
    assert len(results) == 2


def _make_metrics_dict(report_period: str) -> dict:
    return {
        "ticker": "3690.HK",
        "report_period": report_period,
        "period": "annual",
        "currency": "HKD",
        "revenue": 100000000000.0,
        "net_income": 10000000000.0,
    }


def _mock_cache(mocker):
    """Helper: patch the dual cache to always return None (cache miss)."""
    mock_cache = mocker.patch("src.tools.api._get_dual_cache")
    mock_cache.return_value.get_financial_metrics.return_value = None
    return mock_cache


def test_get_financial_metrics_returns_single_period_for_ttm(mocker):
    """period='ttm' still returns single-period data for non-US stocks."""
    mock_router = MagicMock()
    mock_router.return_value.get_financial_metrics.return_value = _make_metrics_dict("2024-12-31")

    mocker.patch("src.tools.api._get_market_router", mock_router)
    mocker.patch("src.tools.api._is_us_stock", return_value=False)
    _mock_cache(mocker)

    results = get_financial_metrics("3690.HK", "2025-01-01", period="ttm", limit=5)

    assert len(results) == 1
    assert isinstance(results[0], FinancialMetrics)
    mock_router.return_value.get_financial_metrics.assert_called_once()
    mock_router.return_value.get_historical_financial_metrics.assert_not_called()


def test_get_financial_metrics_returns_multi_year_for_annual_with_limit(mocker):
    """period='annual' + limit>1 calls get_historical_financial_metrics for non-US stocks."""
    mock_router = MagicMock()
    mock_router.return_value.get_historical_financial_metrics.return_value = [
        _make_metrics_dict("2024-12-31"),
        _make_metrics_dict("2023-12-31"),
        _make_metrics_dict("2022-12-31"),
    ]

    mocker.patch("src.tools.api._get_market_router", mock_router)
    mocker.patch("src.tools.api._is_us_stock", return_value=False)
    _mock_cache(mocker)

    results = get_financial_metrics("3690.HK", "2025-01-01", period="annual", limit=5)

    assert len(results) == 3
    assert all(isinstance(r, FinancialMetrics) for r in results)
    mock_router.return_value.get_historical_financial_metrics.assert_called_once_with(
        "3690.HK", "2025-01-01", limit=5
    )
    mock_router.return_value.get_financial_metrics.assert_not_called()


def test_get_financial_metrics_annual_limit_1_uses_single_period(mocker):
    """period='annual' + limit=1 still uses single-period path."""
    mock_router = MagicMock()
    mock_router.return_value.get_financial_metrics.return_value = _make_metrics_dict("2024-12-31")

    mocker.patch("src.tools.api._get_market_router", mock_router)
    mocker.patch("src.tools.api._is_us_stock", return_value=False)
    _mock_cache(mocker)

    results = get_financial_metrics("3690.HK", "2025-01-01", period="annual", limit=1)

    assert len(results) == 1
    mock_router.return_value.get_financial_metrics.assert_called_once()
    mock_router.return_value.get_historical_financial_metrics.assert_not_called()


def test_get_financial_metrics_returns_empty_when_historical_returns_none(mocker):
    """Returns [] when historical data source returns None."""
    mock_router = MagicMock()
    mock_router.return_value.get_historical_financial_metrics.return_value = None

    mocker.patch("src.tools.api._get_market_router", mock_router)
    mocker.patch("src.tools.api._is_us_stock", return_value=False)
    _mock_cache(mocker)

    results = get_financial_metrics("3690.HK", "2025-01-01", period="annual", limit=5)

    assert results == []
