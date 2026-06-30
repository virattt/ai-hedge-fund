"""Financial Modeling Prep (FMP) provider — placeholder for future implementation.

FMP provides comprehensive fundamental data, financial statements,
and company profiles for US and international equities.
"""

import logging
import os
from typing import Optional

from app.backend.data_providers.base import DataProvider
from app.backend.data_providers.models import DataAvailability, ProviderResult

logger = logging.getLogger(__name__)


class FMPProvider(DataProvider):
    """Placeholder — not yet implemented."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.environ.get("FMP_API_KEY")

    @property
    def name(self) -> str:
        return "Financial Modeling Prep"

    def supports_ticker(self, ticker: str) -> bool:
        return False  # Disabled until implemented

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> ProviderResult:
        return ProviderResult(
            availability=DataAvailability.UNSUPPORTED_TICKER,
            provider_name=self.name,
            error_message="FMP provider not yet implemented",
        )
