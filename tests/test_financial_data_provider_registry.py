import pytest

from src.data.models import Price
from src.data.providers import registry
from src.data.providers.financial_datasets import FinancialDatasetsProvider
from src.data.providers.yfinance import YFinanceProvider
from src.tools import api


def test_default_provider_is_yfinance(monkeypatch):
    monkeypatch.delenv("FINANCIAL_DATA_PROVIDER", raising=False)
    monkeypatch.delenv("FINANCIAL_DATA_SOURCE", raising=False)
    registry.reset_financial_data_provider_cache()

    assert registry.get_configured_provider_name() == "yfinance"
    assert isinstance(registry.get_financial_data_provider(), YFinanceProvider)


def test_provider_aliases_select_financialdatasets(monkeypatch):
    monkeypatch.setenv("FINANCIAL_DATA_PROVIDER", "financial_datasets")
    monkeypatch.delenv("FINANCIAL_DATA_SOURCE", raising=False)
    registry.reset_financial_data_provider_cache()

    assert isinstance(registry.get_financial_data_provider(), FinancialDatasetsProvider)


def test_source_alias_is_supported_when_provider_is_absent(monkeypatch):
    monkeypatch.delenv("FINANCIAL_DATA_PROVIDER", raising=False)
    monkeypatch.setenv("FINANCIAL_DATA_SOURCE", "yf")
    registry.reset_financial_data_provider_cache()

    assert registry.get_configured_provider_name() == "yfinance"


def test_unknown_provider_fails_fast(monkeypatch):
    monkeypatch.setenv("FINANCIAL_DATA_PROVIDER", "not-a-provider")
    registry.reset_financial_data_provider_cache()

    with pytest.raises(ValueError, match="Unknown financial data provider"):
        registry.get_financial_data_provider()


def test_api_facade_delegates_to_configured_provider(monkeypatch):
    class StubProvider:
        def __init__(self):
            self.calls = []

        def get_prices(self, ticker, start_date, end_date, api_key=None):
            self.calls.append((ticker, start_date, end_date, api_key))
            return [
                Price(
                    open=100.0,
                    close=101.0,
                    high=102.0,
                    low=99.0,
                    volume=1000,
                    time="2024-01-02T00:00:00",
                )
            ]

    provider = StubProvider()
    monkeypatch.setattr(api, "get_financial_data_provider", lambda: provider)

    prices = api.get_prices("AAPL", "2024-01-01", "2024-01-02", api_key="key")

    assert provider.calls == [("AAPL", "2024-01-01", "2024-01-02", "key")]
    assert prices[0].close == 101.0
