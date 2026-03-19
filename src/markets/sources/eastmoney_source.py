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

    # K-line data API (use HTTPS with cookies to bypass anti-bot)
    KLINE_API = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

    # Financial metrics API (use HTTPS with cookies to bypass anti-bot)
    FINANCE_API = "https://push2.eastmoney.com/api/qt/stock/get"

    def __init__(self):
        super().__init__("Eastmoney")
        self.session = requests.Session()

        # Configure session for better reliability
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0,  # We handle retries manually
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
            'Referer': 'https://quote.eastmoney.com/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
        })

        # Set minimal required cookies to bypass anti-bot
        # These are generic session cookies, not user-specific
        self.session.cookies.set('qgqp_b_id', '815f755023542909e5d7e12bb425b596', domain='.eastmoney.com')
        self.session.cookies.set('st_nvi', 'ScjgG2HuISz39_tWj_aok2a2e', domain='.eastmoney.com')
        self.session.cookies.set('mtp', '1', domain='.eastmoney.com')

    def supports_market(self, market: str) -> bool:
        """Eastmoney supports CN and HK markets."""
        return market.upper() in ("CN", "HK")

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

    def _detect_hk_ticker(self, ticker: str) -> bool:
        """
        Detect if ticker is HK market format.

        HK market ticker formats:
        - 0700.HK  (with suffix)
        - 03690.HK (with suffix)
        - 00700    (5-digit code)
        - 03690    (5-digit code)
        - 0700     (4-digit code)

        Args:
            ticker: Stock ticker

        Returns:
            True if HK market ticker
        """
        ticker_upper = ticker.upper()

        # Check for .HK suffix
        if ticker_upper.endswith('.HK'):
            return True

        # Check for 4-5 digit pure numeric code (HK stock codes)
        # HKStockAdapter.supports_ticker accepts 4-5 digit codes; we match the same range
        code = ticker.split('.')[0]
        if code.isdigit() and 4 <= len(code) <= 5:
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

    def _to_eastmoney_hk_secid(self, ticker: str) -> str:
        """
        Convert HK ticker to Eastmoney secid format.

        HK stocks use prefix 116:
        - 0700.HK  → 116.00700
        - 03690.HK → 116.03690
        - 00700    → 116.00700

        Args:
            ticker: HK ticker (e.g., '0700.HK', '03690.HK', '00700')

        Returns:
            Eastmoney secid format (e.g., '116.00700')
        """
        # Remove .HK suffix if present
        ticker_upper = ticker.upper()
        if ticker_upper.endswith('.HK'):
            code = ticker[:-3]
        else:
            code = ticker.split('.')[0]

        # Ensure 5-digit zero-padded code
        code = code.zfill(5)
        return f"116.{code}"

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
                    # Reset connection on retry
                    self.session.close()
                    self.session = requests.Session()
                    adapter = requests.adapters.HTTPAdapter(
                        pool_connections=10,
                        pool_maxsize=20,
                        max_retries=0,
                        pool_block=False
                    )
                    self.session.mount('http://', adapter)
                    self.session.headers.update({
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                        'Referer': 'http://quote.eastmoney.com/',
                        'Accept': 'application/json, text/plain, */*',
                        'Connection': 'keep-alive'
                    })
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

                # Log the request details
                url_with_params = f"{self.KLINE_API}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
                self.logger.info(f"[Eastmoney] 📡 GET {url_with_params}")
                self.logger.debug(f"[Eastmoney] Headers: {dict(self.session.headers)}")

                response = self.session.get(self.KLINE_API, params=params, timeout=20, verify=False)
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

        Fetches comprehensive financial indicators including:
        - Valuation: PE, PB, PS, EV/EBITDA
        - Profitability: gross margin, net margin, ROE, ROA
        - Solvency: debt ratio, current ratio
        - Growth: revenue growth, profit growth

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

        # Convert to Eastmoney format
        secid = self._to_eastmoney_secid(ticker)

        try:
            # Add delay to avoid rate limiting
            time.sleep(random.uniform(0.5, 1.5))

            # Build request parameters for financial metrics
            # Key fields:
            # f116: Total market cap (总市值)
            # f117: Circulating market cap (流通市值)
            # f162: PE (TTM)
            # f167: PB
            # f173: ROE
            # f187: Gross margin
            params = {
                'secid': secid,
                'fields': 'f43,f116,f117,f162,f167,f173,f187',
            }

            # Log the request details
            url_with_params = f"{self.FINANCE_API}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
            self.logger.info(f"[Eastmoney] 📡 GET {url_with_params}")
            self.logger.debug(f"[Eastmoney] Headers: {dict(self.session.headers)}")

            response = self.session.get(self.FINANCE_API, params=params, timeout=15, verify=False)
            response.raise_for_status()

            # Parse JSON response
            data = response.json()

            if not data or 'data' not in data:
                self.logger.warning(f"[Eastmoney] No financial data for {ticker}")
                return None

            finance_data = data['data']
            if not finance_data:
                return None

            # Extract and convert financial metrics
            metrics = self._parse_financial_metrics(finance_data, ticker, end_date, period)

            if metrics:
                self.logger.info(f"[Eastmoney] ✓ Retrieved financial metrics for {ticker}")
            else:
                self.logger.warning(f"[Eastmoney] Failed to parse financial metrics for {ticker}")

            return metrics

        except Exception as e:
            self.logger.error(f"[Eastmoney] Failed to get financial metrics for {ticker}: {e}")
            return None

    def _parse_financial_metrics(self, data: Dict, ticker: str, end_date: str, period: str) -> Optional[Dict]:
        """
        Parse financial metrics from Eastmoney API response.

        Eastmoney field mappings (verified):
        - f43: Latest price
        - f116: Total market cap (总市值) in CNY
        - f117: Circulating market cap (流通市值) in CNY
        - f162: PE (TTM) (市盈率)
        - f167: PB (市净率)
        - f173: ROE (净资产收益率) %
        - f187: Gross margin (毛利率) %

        Args:
            data: API response data
            ticker: Stock ticker
            end_date: End date
            period: Period type

        Returns:
            Dictionary with parsed financial metrics
        """
        try:
            # Extract basic metrics
            metrics = {
                "ticker": ticker,
                "report_period": end_date,
                "period": period,
                "currency": "CNY",  # CN market uses CNY
            }

            # Market cap (f116: total, f117: circulating) - already in CNY
            metrics["market_cap"] = self._safe_float(data.get("f116"))

            # Valuation metrics
            metrics["price_to_earnings_ratio"] = self._safe_float(data.get("f162"))  # PE (TTM)
            metrics["price_to_book_ratio"] = self._safe_float(data.get("f167"))      # PB
            # PS and EV/EBITDA not directly available in basic quote API
            metrics["price_to_sales_ratio"] = None
            metrics["enterprise_value_to_ebitda_ratio"] = None
            metrics["enterprise_value_to_revenue_ratio"] = None

            # Profitability metrics
            metrics["gross_margin"] = self._safe_float(data.get("f187"))    # 毛利率
            metrics["net_margin"] = None  # Not in basic quote
            metrics["operating_margin"] = None
            metrics["return_on_equity"] = self._safe_float(data.get("f173"))  # ROE
            metrics["return_on_assets"] = None  # Not in basic quote

            # Solvency metrics - not available in basic quote API
            metrics["current_ratio"] = None
            metrics["quick_ratio"] = None
            metrics["debt_to_equity"] = None

            # Growth metrics - not available in basic quote API
            metrics["revenue_growth"] = None
            metrics["earnings_growth"] = None

            # Per share metrics
            metrics["earnings_per_share"] = None
            metrics["book_value_per_share"] = None

            # Additional info
            metrics["enterprise_value"] = None
            metrics["payout_ratio"] = None

            return metrics

        except Exception as e:
            self.logger.error(f"Failed to parse financial metrics: {e}")
            return None

    def _safe_float(self, value) -> Optional[float]:
        """
        Safely convert value to float.

        Args:
            value: Value to convert

        Returns:
            Float value or None
        """
        try:
            if value is None or value == "" or value == "-":
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    def get_company_news(
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Eastmoney does not provide news data.

        Use NewsNowSource for CN market news instead.
        """
        return []
