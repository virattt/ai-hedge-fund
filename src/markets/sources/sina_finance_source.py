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
        self, ticker: str, start_date: str, end_date: str, max_retries: int = 3
    ) -> List[Dict]:
        """
        Get price data from Sina Finance.

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            max_retries: Maximum retry attempts

        Returns:
            List of price dictionaries
        """
        market = self._detect_market(ticker)
        sina_symbol = self._to_sina_symbol(ticker, market)

        for attempt in range(max_retries):
            try:
                # Add delay to avoid rate limiting
                if attempt > 0:
                    delay = 2 ** attempt
                    self.logger.info(f"[SinaFinance] Retry {attempt+1}, waiting {delay}s")
                    time.sleep(delay)
                else:
                    time.sleep(random.uniform(0.5, 1.5))

                # Route to market-specific implementation
                if market == "CN":
                    prices = self._get_cn_prices(sina_symbol, start_date, end_date)
                elif market == "HK":
                    prices = self._get_hk_prices(sina_symbol, start_date, end_date)
                else:  # US
                    prices = self._get_us_prices(sina_symbol, start_date, end_date)

                if prices:
                    self.logger.info(f"[SinaFinance] ✓ Retrieved {len(prices)} prices for {ticker}")
                    return prices
                else:
                    self.logger.warning(f"[SinaFinance] No price data for {ticker}")
                    return []

            except Exception as e:
                self.logger.warning(f"[SinaFinance] Attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"[SinaFinance] All retries failed for {ticker}")
                    return []

        return []

    def _get_cn_prices(self, sina_symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Get CN stock prices.

        Args:
            sina_symbol: Sina format symbol (e.g., 'sh600000')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of price dictionaries
        """
        # Calculate number of days
        from datetime import datetime
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        days = (end_dt - start_dt).days
        datalen = min(days + 10, 500)  # Add buffer, max 500

        params = {
            'symbol': sina_symbol,
            'scale': '240',  # Daily K-line
            'ma': 'no',
            'datalen': str(datalen)
        }

        response = self.session.get(self.KLINE_API_CN, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()
        if not data or not isinstance(data, list):
            return []

        prices = []
        for item in data:
            try:
                prices.append({
                    'open': float(item['open']),
                    'close': float(item['close']),
                    'high': float(item['high']),
                    'low': float(item['low']),
                    'volume': int(float(item['volume'])),
                    'time': f"{item['day']}T00:00:00Z"
                })
            except (KeyError, ValueError) as e:
                self.logger.warning(f"Failed to parse CN price data: {e}")
                continue

        return prices

    def _get_hk_prices(self, sina_symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Get HK stock prices.

        Implementation placeholder - will be added in next task.
        """
        return []

    def _get_us_prices(self, sina_symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Get US stock prices.

        Implementation placeholder - will be added in next task.
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
