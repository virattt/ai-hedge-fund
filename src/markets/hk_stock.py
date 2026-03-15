"""Hong Kong market adapter."""
import logging
from typing import Optional

from src.markets.base import MarketAdapter
from src.markets.sources.akshare_source import AKShareSource
from src.markets.sources.yfinance_source import YFinanceSource
from src.data.validation import DataValidator

logger = logging.getLogger(__name__)


class HKStockAdapter(MarketAdapter):
    """Adapter for Hong Kong stock market."""

    def __init__(self, validator: Optional[DataValidator] = None):
        """
        Initialize HK stock adapter.

        Args:
            validator: Data validator instance
        """
        # Primary source: AKShare, Fallback: YFinance
        data_sources = [
            AKShareSource(),
            YFinanceSource(),
        ]

        super().__init__(
            market="HK",
            data_sources=data_sources,
            validator=validator,
        )

    def supports_ticker(self, ticker: str) -> bool:
        """
        检查是否支持该ticker（港股格式）

        港股ticker特征：
        - 包含 .HK 后缀（如 0700.HK, 3690.HK）
        - 或者是4-5位纯数字（如 700, 0700, 03690）

        Args:
            ticker: 股票代码

        Returns:
            bool: True表示支持港股格式，False表示不支持
        """
        ticker = ticker.upper().strip()

        # 检查是否有 .HK 后缀
        if ticker.endswith(".HK"):
            return True

        # 检查是否是4-5位纯数字（港股代码范围）
        if ticker.isdigit() and 4 <= len(ticker) <= 5:
            return True

        return False

    def normalize_ticker(self, ticker: str) -> str:
        """
        Normalize ticker for Hong Kong market.

        Args:
            ticker: Raw ticker (e.g., '700', '00700', '0700.HK')

        Returns:
            Normalized ticker (5-digit format: '00700')
        """
        ticker = ticker.upper().strip()

        # Remove .HK suffix if present
        if ticker.endswith(".HK"):
            ticker = ticker[:-3]

        # Remove non-digits
        ticker = "".join(c for c in ticker if c.isdigit())

        # Ensure 5 digits (pad with zeros)
        if ticker.isdigit():
            return ticker.zfill(5)

        self.logger.warning(f"Invalid HK ticker format: {ticker}")
        return ticker

    def get_yfinance_ticker(self, ticker: str) -> str:
        """
        Convert to YFinance format.

        Args:
            ticker: Normalized 5-digit ticker

        Returns:
            YFinance format (e.g., '0700.HK')
        """
        ticker = self.normalize_ticker(ticker)
        # YFinance uses 4-digit format with .HK suffix
        return f"{int(ticker):04d}.HK"
