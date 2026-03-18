"""Hong Kong market adapter."""
import logging
from typing import Optional, List, Dict

from src.markets.base import MarketAdapter
from src.markets.sources.akshare_source import AKShareSource

# from src.markets.sources.yfinance_source import YFinanceSource  # Disabled: Not available in China
from src.markets.sources.newsnow_source import NewsNowSource
from src.markets.sources.akshare_news_source import AKShareNewsSource
from src.markets.sources.sina_finance_source import SinaFinanceSource
from src.markets.sources.xueqiu_source import XueqiuSource
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
        # Data sources in priority order (per spec):
        # 1. Xueqiu - Primary for financials: most complete statements (TTM data)
        # 2. Sina Finance - Primary for prices: free, stable, real-time HK quotes
        # 3. AKShare - Backup source (single-period data, lower reliability for financials)
        # Note: YFinance disabled (not available in China)
        data_sources = [
            XueqiuSource(),  # Primary for financials: most complete statements
            SinaFinanceSource(),  # Primary for prices: free, stable
            # YFinanceSource(),     # Disabled: Not available in China
            AKShareSource(),  # Fallback: Backup
        ]

        # Xueqiu provides TTM financial data (more accurate for HK stocks).
        # AKShare's stock_hk_financial_indicator_em returns single-period data
        # which can show negative earnings in profitable TTM periods.
        # Set Xueqiu weight much higher so its data dominates the merge.
        hk_validator = validator or DataValidator(
            source_weights={
                "Xueqiu": 1.0,    # Primary: TTM financials, real-time P/E
                "AKShare": 0.05,  # Minimal: single-period data, unreliable for financials
                "SinaFinance": 0.5,
            }
        )

        super().__init__(
            market="HK",
            data_sources=data_sources,
            validator=hk_validator,
        )

        # News sources in priority order:
        # 1. AKShareNews - Reliable Eastmoney news
        # 2. NewsNow - Aggregator (may be unreliable)
        # Note: YFinance disabled (not available in China)
        self.news_sources = [
            AKShareNewsSource(),  # Primary: Eastmoney news
            NewsNowSource(),  # Fallback: News aggregator
            # YFinanceSource(),   # Disabled: Not available in China
        ]

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
                            f"[HKStock] ✓ Got {len(results)} historical periods from Xueqiu for {normalized}"
                        )
                        return results
                except Exception as e:
                    self.logger.warning(f"[HKStock] Xueqiu historical failed for {normalized}: {e}")
                break

        self.logger.warning(f"[HKStock] Falling back to single-period data for {normalized}")
        return super().get_historical_financial_metrics(ticker, end_date, limit)

    def get_company_news(self, ticker: str, end_date: str, start_date=None, limit: int = 100):
        """
        Get company news with multi-source fallback.

        Fallback order:
        1. AKShareNews (Eastmoney - reliable for CN/HK stocks)
        2. NewsNow (free aggregator - may be unreliable)
        3. YFinance (rate limited)

        Args:
            ticker: Stock ticker
            end_date: End date (YYYY-MM-DD)
            start_date: Start date (optional, not used)
            limit: Maximum number of news items

        Returns:
            List of news dictionaries
        """
        ticker = self.normalize_ticker(ticker)

        # Try news sources in priority order
        for source in self.news_sources:
            try:
                self.logger.info(f"[HKStock] Trying {source.name} for news...")
                news = source.get_company_news(ticker, end_date, start_date, limit)
                if news:
                    logger.info(f"[HKStock] ✓ Got {len(news)} news from {source.name}")
                    return news
                else:
                    logger.info(f"[HKStock] ⚠ {source.name} returned no data")
            except Exception as e:
                logger.warning(f"[HKStock] ✗ {source.name} failed: {e}")
                continue

        # If all news sources fail, return empty list
        logger.warning(f"[HKStock] All news sources failed for {ticker}")
        return []
