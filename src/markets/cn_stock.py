"""China A-share market adapter."""
import logging
from typing import List, Optional, Dict

from src.markets.base import MarketAdapter
from src.markets.sources.akshare_source import AKShareSource
from src.markets.sources.newsnow_source import NewsNowSource
from src.markets.sources.sina_finance_source import SinaFinanceSource
from src.markets.sources.xueqiu_source import XueqiuSource
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
        # from src.markets.sources.yfinance_source import YFinanceSource  # Disabled: Not available in China
        from src.markets.sources.tushare_source import TushareSource
        from src.markets.sources.eastmoney_curl_source import EastmoneyCurlSource

        # Data sources in priority order:
        # 1. EastmoneyCurl - Most comprehensive CN market data (uses curl to bypass anti-bot)
        # 2. Xueqiu - Complete financial statements
        # 3. Tushare Pro - Most stable for CN market (requires token)
        # 4. AKShare - Free, good CN market coverage
        # 5. Sina Finance - Free, stable, real-time quotes
        # Note: YFinance disabled (not available in China)
        data_sources = [
            EastmoneyCurlSource(),  # Primary: Most comprehensive, bypasses anti-bot
            XueqiuSource(),  # Secondary: Complete financial statements
            TushareSource(),  # Fallback 1: Requires token
            AKShareSource(),  # Fallback 2: Free, good coverage
            SinaFinanceSource(),  # Fallback 3: Free, stable
            # YFinanceSource(),     # Disabled: Not available in China
        ]

        super().__init__(
            market="CN",
            data_sources=data_sources,
            validator=validator,
        )

        # Add NewsNow as primary news source (财联社 for Chinese market)
        self.news_sources = [
            NewsNowSource(),  # Free, primary news source
            # Existing sources as fallback
        ]

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

    def get_historical_financial_metrics(
        self, ticker: str, end_date: str, limit: int = 10
    ) -> Optional[List[Dict]]:
        """Get multi-year annual financial data via XueqiuSource."""
        normalized = self.normalize_ticker(ticker)

        for source in self.active_sources:
            if source.name == "Xueqiu":
                try:
                    results = source.get_historical_financial_data(normalized, limit=limit)
                    if results:
                        self.logger.info(
                            f"[CNStock] ✓ Got {len(results)} historical periods from Xueqiu for {normalized}"
                        )
                        return results
                except Exception as e:
                    self.logger.warning(f"[CNStock] Xueqiu historical failed for {normalized}: {e}")
                break

        self.logger.warning(f"[CNStock] Falling back to single-period data for {normalized}")
        return super().get_historical_financial_metrics(ticker, end_date, limit)

    def get_company_news(self, ticker: str, end_date: str, start_date=None, limit: int = 100):
        """
        Get company news with NewsNow as primary source.

        Fallback order:
        1. NewsNow (free, 财联社 for CN market)
        2. AKShare, Tushare, YFinance (existing sources)

        Args:
            ticker: Stock ticker
            end_date: End date (YYYY-MM-DD)
            start_date: Start date (optional, not used)
            limit: Maximum number of news items

        Returns:
            List of news dictionaries
        """
        ticker = self.normalize_ticker(ticker)

        # Try NewsNow first
        for source in self.news_sources:
            try:
                news = source.get_company_news(ticker, end_date, start_date, limit)
                if news:
                    logger.info(f"[CNStock] ✓ Got {len(news)} news from {source.name}")
                    return news
                else:
                    logger.info(f"[CNStock] ⚠ {source.name} returned no data")
            except Exception as e:
                logger.warning(f"[CNStock] ✗ {source.name} failed: {e}")
                continue

        # Fallback to existing sources via base class
        logger.warning(f"[CNStock] NewsNow failed, using existing sources")
        return super().get_company_news(ticker, end_date, start_date, limit)
