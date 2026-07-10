"""Composite market data layer — Alpaca (prices/news) + Finnhub (fundamentals)."""

from integrations.data.composite import CompositeDataClient
from integrations.data.config import load_data_config
from integrations.data.v1_bridge import V1DataAPI

__all__ = ["CompositeDataClient", "V1DataAPI", "get_data_client", "use_composite_provider"]


def use_composite_provider() -> bool:
    config = load_data_config()
    return config.provider == "composite"


def get_data_client() -> CompositeDataClient:
    """Return the composite v2 DataClient (Alpaca + Finnhub)."""
    config = load_data_config()
    if config.provider != "composite":
        raise ValueError(
            f"DATA_PROVIDER is '{config.provider}', expected 'composite'. "
            "Set DATA_PROVIDER=composite in your .env file."
        )
    return CompositeDataClient(config)
