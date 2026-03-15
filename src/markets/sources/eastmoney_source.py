"""Eastmoney data source for comprehensive CN market data (A股专用深度数据源)."""
import json
import logging
import time
import random
from typing import Dict, List, Optional
from datetime import datetime

import requests

from src.markets.sources.base import DataSource

logger = logging.getLogger(__name__)


class EastmoneySource(DataSource):
    """
    Eastmoney (东方财富) data source.

    Features:
    - Most comprehensive CN market data
    - Zero dependencies, pure HTTP calls
    - Supports complete financial statements
    - Forward-adjusted K-line data (前复权)
    - CN market only (.SH/.SZ tickers)
    """

    # K-line data API
    KLINE_API = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

    # Financial metrics API (to be implemented in Task 3.3)
    FINANCE_API = "http://push2.eastmoney.com/api/qt/stock/get"

    def __init__(self):
        super().__init__("Eastmoney")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'http://quote.eastmoney.com/'
        })

    def supports_market(self, market: str) -> bool:
        """Eastmoney only supports CN market."""
        return market.upper() == "CN"

    def _detect_cn_ticker(self, ticker: str) -> bool:
        """
        Detect if ticker is CN market format.

        CN market ticker formats:
        - 600000.SH (Shanghai)
        - 000001.SZ (Shenzhen)
        - SH600000
        - SZ000001
        - 600000 (6-digit code)

        Args:
            ticker: Stock ticker

        Returns:
            True if CN market ticker
        """
        ticker_upper = ticker.upper()

        # Check for .SH/.SZ suffix
        if '.SH' in ticker_upper or '.SZ' in ticker_upper:
            return True

        # Check for SH/SZ prefix
        if ticker_upper.startswith('SH') or ticker_upper.startswith('SZ'):
            return True

        # Check for 6-digit code (CN market standard)
        code = ticker.split('.')[0]
        if code.isdigit() and len(code) == 6:
            return True

        return False

    def _to_eastmoney_secid(self, ticker: str) -> str:
        """
        Convert ticker to Eastmoney secid format.

        Rules:
        - Shanghai (6xxxxx): 1.600000
        - Shenzhen (0xxxxx, 3xxxxx): 0.000001

        Args:
            ticker: Original ticker (e.g., '600000.SH', '000001.SZ')

        Returns:
            Eastmoney secid format (e.g., '1.600000', '0.000001')
        """
        ticker_upper = ticker.upper()

        # Extract code
        if '.SH' in ticker_upper:
            code = ticker_upper.split('.')[0]
            return f"1.{code}"
        elif '.SZ' in ticker_upper:
            code = ticker_upper.split('.')[0]
            return f"0.{code}"
        elif ticker_upper.startswith('SH'):
            code = ticker_upper[2:]
            return f"1.{code}"
        elif ticker_upper.startswith('SZ'):
            code = ticker_upper[2:]
            return f"0.{code}"
        else:
            # 6-digit code without suffix
            # Determine market by first digit:
            # - 6: Shanghai (1.)
            # - 0, 3: Shenzhen (0.)
            code = ticker.split('.')[0]
            if code.startswith('6'):
                return f"1.{code}"
            else:
                return f"0.{code}"

    def get_prices(
        self, ticker: str, start_date: str, end_date: str, max_retries: int = 3
    ) -> List[Dict]:
        """
        Get price data from Eastmoney.

        Implementation in Task 3.2.

        Args:
            ticker: Stock ticker (CN market format)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            max_retries: Maximum retry attempts

        Returns:
            List of price dictionaries
        """
        # Validate CN market ticker
        if not self._detect_cn_ticker(ticker):
            self.logger.warning(f"[Eastmoney] Ticker {ticker} is not CN market format")
            return []

        # Convert to Eastmoney format
        secid = self._to_eastmoney_secid(ticker)

        for attempt in range(max_retries):
            try:
                # Add delay to avoid rate limiting
                if attempt > 0:
                    delay = 2 ** attempt
                    self.logger.info(f"[Eastmoney] Retry {attempt+1}, waiting {delay}s")
                    time.sleep(delay)
                else:
                    time.sleep(random.uniform(0.5, 1.5))

                # Build request parameters
                params = {
                    'secid': secid,
                    'fields1': 'f1,f2,f3,f4,f5,f6',
                    'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                    'klt': '101',  # 101=daily, 102=weekly, 103=monthly
                    'fqt': '1',    # 0=no adjustment, 1=forward adjustment, 2=backward adjustment
                    'beg': start_date.replace('-', ''),  # Format: YYYYMMDD
                    'end': end_date.replace('-', ''),
                }

                response = self.session.get(self.KLINE_API, params=params, timeout=15)
                response.raise_for_status()

                # Parse JSON response
                data = response.json()

                if data.get('rc') != 0:
                    self.logger.warning(f"[Eastmoney] API returned error code: {data.get('rc')}")
                    return []

                # Extract K-line data
                kline_data = data.get('data', {})
                if not kline_data:
                    self.logger.warning(f"[Eastmoney] No data for {ticker}")
                    return []

                klines = kline_data.get('klines', [])
                if not klines:
                    self.logger.warning(f"[Eastmoney] No klines for {ticker}")
                    return []

                # Parse K-line data
                prices = self._parse_klines(klines)

                if prices:
                    self.logger.info(f"[Eastmoney] ✓ Retrieved {len(prices)} prices for {ticker}")
                    return prices
                else:
                    self.logger.warning(f"[Eastmoney] Failed to parse klines for {ticker}")
                    return []

            except Exception as e:
                self.logger.warning(f"[Eastmoney] Attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"[Eastmoney] All retries failed for {ticker}")
                    return []

        return []

    def _parse_klines(self, klines: List[str]) -> List[Dict]:
        """
        Parse K-line data from Eastmoney format.

        K-line format: "date,open,close,high,low,volume,amount,amplitude,pct_change,change,turnover"
        Example: "2024-01-02,10.50,10.80,10.90,10.40,12345678,133456789.00,4.76,2.86,0.30,1.23"

        Args:
            klines: List of K-line strings

        Returns:
            List of price dictionaries
        """
        prices = []

        for kline in klines:
            try:
                parts = kline.split(',')
                if len(parts) < 6:
                    self.logger.warning(f"Invalid kline format: {kline}")
                    continue

                # Extract OHLCV data
                date_str = parts[0]       # Date: YYYY-MM-DD
                open_price = float(parts[1])
                close_price = float(parts[2])
                high_price = float(parts[3])
                low_price = float(parts[4])
                volume = int(float(parts[5]))  # Convert to int, handle scientific notation

                price_dict = {
                    'open': open_price,
                    'close': close_price,
                    'high': high_price,
                    'low': low_price,
                    'volume': volume,
                    'time': f"{date_str}T00:00:00Z"
                }
                prices.append(price_dict)

            except (ValueError, IndexError) as e:
                self.logger.warning(f"Failed to parse kline: {kline}, error: {e}")
                continue

        return prices

    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> Optional[Dict]:
        """
        Get financial metrics from Eastmoney.

        Implementation in Task 3.3.

        Args:
            ticker: Stock ticker (CN market format)
            end_date: End date (YYYY-MM-DD)
            period: Period type (ttm, quarterly, annual)
            limit: Number of periods to fetch

        Returns:
            Dictionary with financial metrics
        """
        # Validate CN market ticker
        if not self._detect_cn_ticker(ticker):
            self.logger.warning(f"[Eastmoney] Ticker {ticker} is not CN market format")
            return None

        # To be implemented in Task 3.3
        self.logger.info(f"[Eastmoney] Financial metrics not yet implemented")
        return None

    def get_company_news(
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Eastmoney does not provide news data.

        Use NewsNowSource for CN market news instead.
        """
        return []
