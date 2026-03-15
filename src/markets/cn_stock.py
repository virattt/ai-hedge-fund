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
        # Import here to avoid circular dependency
        from src.markets.sources.yfinance_source import YFinanceSource
        from src.markets.sources.tushare_source import TushareSource

        # Data sources in priority order:
        # 1. Tushare Pro - Most stable for CN market (requires token)
        # 2. AKShare - Free but may be rate limited
        # 3. YFinance - Global coverage, backup source
        data_sources = [
            TushareSource(),    # Primary: Best for CN stocks
            AKShareSource(),    # Fallback 1: Free but rate limited
            YFinanceSource(),   # Fallback 2: Global coverage
        ]

        super().__init__(
            market="CN",
            data_sources=data_sources,
            validator=validator,
        )

    def supports_ticker(self, ticker: str) -> bool:
        """
        检查是否支持该ticker（A股格式）

        A股ticker特征：
        - 包含 .SH 或 .SZ 后缀（如 600000.SH, 000001.SZ）
        - 或者以 SH/SZ 开头后接6位数字（如 SH600000, SZ000001）
        - 或者是6位纯数字（如 600000, 000001）

        Args:
            ticker: 股票代码

        Returns:
            bool: True表示支持A股格式，False表示不支持
        """
        ticker = ticker.upper().strip()

        # 检查是否有 .SH 或 .SZ 后缀
        if ticker.endswith(".SH") or ticker.endswith(".SZ"):
            return True

        # 检查是否以 SH 或 SZ 开头后接数字
        if ticker.startswith("SH") or ticker.startswith("SZ"):
            code = ticker[2:]
            return code.isdigit() and len(code) == 6

        # 检查是否是6位纯数字
        if ticker.isdigit() and len(ticker) == 6:
            return True

        return False

    def normalize_ticker(self, ticker: str) -> str:
        """
        Normalize ticker for China A-share market.

        Args:
            ticker: Raw ticker (e.g., '000001', '600000', 'SH600000', 'SZ000001')

        Returns:
            Normalized ticker (6-digit format)
        """
        ticker = ticker.upper().strip()

        # Remove .SH/.SZ suffix if present
        if ticker.endswith(".SH"):
            ticker = ticker[:-3]
        elif ticker.endswith(".SZ"):
            ticker = ticker[:-3]

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
