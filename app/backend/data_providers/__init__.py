"""Multi-source data provider layer.

Provides a unified interface for fetching market data from multiple providers,
with automatic fallback and graceful degradation when providers lack coverage.
"""

from app.backend.data_providers.provider_manager import ProviderManager
from app.backend.data_providers.models import (
    PriceBar,
    FundamentalData,
    NewsItem,
    SentimentResult,
    ProviderResult,
    DataAvailability,
)

__all__ = [
    "ProviderManager",
    "PriceBar",
    "FundamentalData",
    "NewsItem",
    "SentimentResult",
    "ProviderResult",
    "DataAvailability",
]
