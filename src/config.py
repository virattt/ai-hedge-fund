"""Centralized application configuration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Optional


@dataclass(slots=True)
class CosmosSettings:
    """Settings required to talk to Azure Cosmos DB."""

    endpoint: Optional[str]
    key: Optional[str]
    database: Optional[str]
    portfolio_container: Optional[str]
    analyst_signals_container: Optional[str]
    decisions_container: Optional[str]

    @property
    def is_configured(self) -> bool:
        """Return True when the minimum Cosmos settings are present."""

        return bool(self.endpoint and self.key and self.database)


@lru_cache(maxsize=1)
def get_cosmos_settings() -> CosmosSettings:
    """Load Cosmos DB configuration from environment variables."""

    return CosmosSettings(
        endpoint=os.getenv("COSMOS_ENDPOINT"),
        key=os.getenv("COSMOS_KEY"),
        database=os.getenv("COSMOS_DATABASE"),
        portfolio_container=os.getenv("COSMOS_PORTFOLIOS_CONTAINER"),
        analyst_signals_container=os.getenv("COSMOS_ANALYST_SIGNALS_CONTAINER"),
        decisions_container=os.getenv("COSMOS_DECISIONS_CONTAINER"),
    )


__all__ = ["CosmosSettings", "get_cosmos_settings"]

