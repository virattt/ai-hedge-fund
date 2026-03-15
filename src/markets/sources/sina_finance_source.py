"""Sina Finance data source for CN/HK/US markets."""
import logging
import re
import time
import random
from typing import Dict, List, Optional
from datetime import datetime

import requests

from src.markets.sources.base import DataSource

logger = logging.getLogger(__name__)


class SinaFinanceSource(DataSource):
    """
    Sina Finance data source.

    Features:
    - Supports CN/HK/US three markets
    - Real-time quotes with <1 minute delay
    - High stability, rare rate limiting
    - Direct HTTP calls, no SDK required
    """

    QUOTE_API = "https://hq.sinajs.cn/list={symbol}"
    KLINE_API_CN = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
    KLINE_API_HK = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

    def __init__(self):
        super().__init__("SinaFinance")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        })

    def supports_market(self, market: str) -> bool:
        """Sina Finance supports CN/HK/US markets."""
        return market.upper() in ["US", "CN", "HK"]

    def _detect_market(self, ticker: str) -> str:
        """
        Detect market from ticker format.

        Args:
            ticker: Stock ticker

        Returns:
            Market code: "CN", "HK", or "US"
        """
        ticker_upper = ticker.upper()
        if '.SH' in ticker_upper or '.SZ' in ticker_upper:
            return "CN"
        elif '.HK' in ticker_upper:
            return "HK"
        else:
            return "US"

    def _to_sina_symbol(self, ticker: str, market: str) -> str:
        """
        Convert ticker to Sina Finance format.

        Rules:
        - CN: 600000.SH → sh600000, 000001.SZ → sz000001
        - HK: 0700.HK → hk00700
        - US: AAPL → gb_aapl

        Args:
            ticker: Original ticker
            market: Market code

        Returns:
            Sina format ticker
        """
        code = ticker.split('.')[0]

        if market == "CN":
            prefix = "sh" if ".SH" in ticker.upper() else "sz"
            return f"{prefix}{code}"
        elif market == "HK":
            return f"hk{code.zfill(5)}"
        else:  # US
            return f"gb_{code.lower()}"

    def get_prices(
        self, ticker: str, start_date: str, end_date: str
    ) -> List[Dict]:
        """
        Get price data from Sina Finance.

        This is a placeholder that will be implemented in next task.
        """
        return []

    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> Optional[Dict]:
        """
        Get basic financial metrics from Sina Finance.

        Note: Sina only provides basic metrics (PE, PB, market cap).
        """
        return None

    def get_company_news(
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """Sina Finance does not provide news data."""
        return []
