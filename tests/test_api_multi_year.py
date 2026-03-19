from unittest.mock import MagicMock, patch
from src.markets.router import MarketRouter


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
