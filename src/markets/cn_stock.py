"""China A-share market adapter."""
import logging
from typing import List, Optional

from src.markets.base import MarketAdapter
from src.markets.sources.akshare_source import AKShareSource
from src.data.validation import DataValidator

logger = logging.getLogger(__name__)


class CNStockAdapter(MarketAdapter):
    """Adapter for China A-share market."""

    def __init__(self, validator: Optional[DataValidator] = None):
        """
        Initialize CN stock adapter.

        Args:
            validator: Data validator instance
        """
        # Primary source: AKShare (best for CN stocks)
        data_sources = [
            AKShareSource(),
        ]

        super().__init__(
            market="CN",
            data_sources=data_sources,
            validator=validator,
        )

    def normalize_ticker(self, ticker: str) -> str:
        """
        Normalize ticker for China A-share market.

        Args:
            ticker: Raw ticker (e.g., '000001', '600000', 'SH600000', 'SZ000001')

        Returns:
            Normalized ticker (6-digit format)
        """
        ticker = ticker.upper().strip()

        # Remove exchange prefix if present
        if ticker.startswith("SH"):
            ticker = ticker[2:]
        elif ticker.startswith("SZ"):
            ticker = ticker[2:]

        # Ensure 6 digits
        if len(ticker) == 6 and ticker.isdigit():
            return ticker

        # Pad with zeros if needed
        if ticker.isdigit() and len(ticker) < 6:
            return ticker.zfill(6)

        self.logger.warning(f"Invalid CN ticker format: {ticker}")
        return ticker

    def detect_exchange(self, ticker: str) -> str:
        """
        Detect exchange for a CN ticker.

        Args:
            ticker: Normalized 6-digit ticker

        Returns:
            'SH' for Shanghai, 'SZ' for Shenzhen
        """
        ticker = self.normalize_ticker(ticker)

        # Shanghai stocks start with 6
        if ticker.startswith("6"):
            return "SH"
        # Shenzhen stocks start with 0 or 3
        elif ticker.startswith(("0", "3")):
            return "SZ"
        else:
            self.logger.warning(f"Unknown exchange for ticker {ticker}, defaulting to SH")
            return "SH"

    def get_full_ticker(self, ticker: str) -> str:
        """
        Get full ticker with exchange prefix.

        Args:
            ticker: Normalized ticker

        Returns:
            Full ticker (e.g., 'SH600000', 'SZ000001')
        """
        ticker = self.normalize_ticker(ticker)
        exchange = self.detect_exchange(ticker)
        return f"{exchange}{ticker}"
