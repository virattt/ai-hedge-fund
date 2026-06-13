import os

from src.data.providers.base import FinancialDataProvider
from src.data.providers.financial_datasets import FinancialDatasetsProvider
from src.data.providers.yfinance import YFinanceProvider

DEFAULT_PROVIDER_NAME = "yfinance"

_PROVIDER_ALIASES = {
    "financialdatasets": "financialdatasets",
    "financial_datasets": "financialdatasets",
    "financialdatasets.ai": "financialdatasets",
    "financial-datasets": "financialdatasets",
    "yahoo": "yfinance",
    "yahoo_finance": "yfinance",
    "yahoo-finance": "yfinance",
    "yf": "yfinance",
    "yfinance": "yfinance",
}

_providers: dict[str, FinancialDataProvider] = {}


def normalize_provider_name(provider_name: str | None) -> str:
    raw_name = (provider_name or DEFAULT_PROVIDER_NAME).strip().lower()
    return _PROVIDER_ALIASES.get(raw_name, raw_name)


def get_configured_provider_name() -> str:
    provider_name = os.environ.get("FINANCIAL_DATA_PROVIDER") or os.environ.get("FINANCIAL_DATA_SOURCE")
    return normalize_provider_name(provider_name)


def get_financial_data_provider(provider_name: str | None = None) -> FinancialDataProvider:
    name = normalize_provider_name(provider_name) if provider_name else get_configured_provider_name()
    if name not in _providers:
        if name == "yfinance":
            _providers[name] = YFinanceProvider()
        elif name == "financialdatasets":
            _providers[name] = FinancialDatasetsProvider()
        else:
            valid = ", ".join(sorted(set(_PROVIDER_ALIASES.values())))
            raise ValueError(f"Unknown financial data provider '{name}'. Valid providers: {valid}")
    return _providers[name]


def reset_financial_data_provider_cache() -> None:
    _providers.clear()
