"""Eastmoney data source using curl subprocess to bypass anti-bot protection."""
import json
import logging
import subprocess
import time
import random
from typing import Dict, List, Optional

from src.markets.sources.base import DataSource

logger = logging.getLogger(__name__)


class EastmoneyCurlSource(DataSource):
    """
    Eastmoney data source using system curl command.

    This bypasses Eastmoney's anti-bot protection by using curl,
    which has different TLS fingerprint than Python requests.
    """

    # Cookies required for access (generic, not user-specific)
    # These are minimal session cookies that allow API access
    COOKIES = 'qgqp_b_id=815f755023542909e5d7e12bb425b596; st_nvi=ScjgG2HuISz39_tWj_aok2a2e; nid18=09eb187f79dc909ec16bdbde4b035e7c; nid18_create_time=1772700178728; gviem=a_KccyxJy-mrAKnziDt975b61; gviem_create_time=1772700178728; mtp=1'

    def __init__(self):
        super().__init__("EastmoneyCurl")

    def supports_market(self, market: str) -> bool:
        """Eastmoney only supports CN market."""
        return market.upper() == "CN"

    def _curl_get(self, url: str, max_retries: int = 3) -> Optional[Dict]:
        """
        Fetch JSON data using curl command.

        Args:
            url: URL to fetch
            max_retries: Maximum retry attempts

        Returns:
            JSON data or None
        """
        # Always log the URL being requested
        self.logger.info(f"[EastmoneyCurl] 📡 Requesting URL: {url}")

        for attempt in range(max_retries):
            try:
                # Add delay to avoid rate limiting
                if attempt > 0:
                    delay = 2 ** attempt
                    self.logger.info(f"[EastmoneyCurl] Retry {attempt+1}, waiting {delay}s")
                    time.sleep(delay)
                else:
                    time.sleep(random.uniform(0.5, 1.5))

                # Build curl command
                cmd = [
                    'curl', '-s', '-k',  # silent, insecure (skip cert verification)
                    url,
                    '-b', self.COOKIES,
                    '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
                    '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    '-H', 'Accept-Language: zh-CN,zh;q=0.9',
                    '--max-time', '20',  # Increased timeout
                    '--connect-timeout', '10',  # Connection timeout
                ]

                # Log the curl command for debugging
                self.logger.debug(f"[EastmoneyCurl] Executing: {' '.join(cmd)}")

                # Execute curl
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=25  # Increased timeout
                )

                if result.returncode != 0:
                    error_msg = result.stderr.strip() if result.stderr else f"curl failed with code {result.returncode}"
                    self.logger.warning(f"[EastmoneyCurl] {error_msg}")
                    continue

                if not result.stdout:
                    self.logger.warning(f"[EastmoneyCurl] Empty response")
                    continue

                # Parse JSON
                data = json.loads(result.stdout)
                return data

            except subprocess.TimeoutExpired:
                self.logger.warning(f"[EastmoneyCurl] Attempt {attempt+1} timeout")
            except json.JSONDecodeError as e:
                self.logger.warning(f"[EastmoneyCurl] Attempt {attempt+1} JSON error: {e}")
            except Exception as e:
                self.logger.warning(f"[EastmoneyCurl] Attempt {attempt+1} failed: {e}")

            if attempt == max_retries - 1:
                self.logger.error(f"[EastmoneyCurl] All retries failed")
                return None

        return None

    def _to_eastmoney_secid(self, ticker: str) -> str:
        """Convert ticker to Eastmoney secid format."""
        ticker_upper = ticker.upper()

        # Extract code
        if '.SH' in ticker_upper:
            code = ticker_upper.split('.')[0]
            return f"1.{code}"
        elif '.SZ' in ticker_upper:
            code = ticker_upper.split('.')[0]
            return f"0.{code}"
        else:
            # 6-digit code without suffix
            code = ticker.split('.')[0]
            if code.startswith('6'):
                return f"1.{code}"
            else:
                return f"0.{code}"

    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> Optional[Dict]:
        """
        Get financial metrics using curl.

        Args:
            ticker: Stock ticker
            end_date: End date
            period: Period type
            limit: Number of periods

        Returns:
            Financial metrics dictionary
        """
        secid = self._to_eastmoney_secid(ticker)

        # Build URL
        url = (
            f"https://push2.eastmoney.com/api/qt/stock/get"
            f"?secid={secid}"
            f"&fields=f43,f116,f117,f162,f167,f173,f187"
        )

        # Fetch data
        data = self._curl_get(url)

        if not data or 'data' not in data:
            self.logger.warning(f"[EastmoneyCurl] No data for {ticker}")
            return None

        finance_data = data['data']
        if not finance_data:
            return None

        # Parse metrics
        try:
            metrics = {
                "ticker": ticker,
                "report_period": end_date,
                "period": period,
                "currency": "CNY",
                "market_cap": self._safe_float(finance_data.get("f116")),
                "price_to_earnings_ratio": self._safe_float(finance_data.get("f162")),
                "price_to_book_ratio": self._safe_float(finance_data.get("f167")),
                "price_to_sales_ratio": None,
                "enterprise_value_to_ebitda_ratio": None,
                "enterprise_value_to_revenue_ratio": None,
                "gross_margin": self._safe_float(finance_data.get("f187")),
                "net_margin": None,
                "operating_margin": None,
                "return_on_equity": self._safe_float(finance_data.get("f173")),
                "return_on_assets": None,
                "current_ratio": None,
                "quick_ratio": None,
                "debt_to_equity": None,
                "revenue_growth": None,
                "earnings_growth": None,
                "earnings_per_share": None,
                "book_value_per_share": None,
                "enterprise_value": None,
                "payout_ratio": None,
            }

            self.logger.info(f"[EastmoneyCurl] ✓ Retrieved financial metrics for {ticker}")
            return metrics

        except Exception as e:
            self.logger.error(f"[EastmoneyCurl] Failed to parse metrics: {e}")
            return None

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        try:
            if value is None or value == "" or value == "-":
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Get price data using curl.

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of price dictionaries
        """
        secid = self._to_eastmoney_secid(ticker)

        # Build URL
        url = (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}"
            f"&fields1=f1,f2,f3,f4,f5,f6"
            f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            f"&klt=101"  # 101=daily
            f"&fqt=1"    # 1=forward adjustment
            f"&beg={start_date.replace('-', '')}"
            f"&end={end_date.replace('-', '')}"
        )

        # Fetch data
        data = self._curl_get(url)

        if not data or 'data' not in data:
            self.logger.warning(f"[EastmoneyCurl] No price data for {ticker}")
            return []

        kline_data = data.get('data', {})
        if not kline_data:
            return []

        klines = kline_data.get('klines', [])
        if not klines:
            return []

        # Parse K-line data
        prices = []
        for kline in klines:
            try:
                # Format: "date,open,close,high,low,volume,amount,amplitude,pct_change,change,turnover"
                parts = kline.split(',')
                if len(parts) >= 7:
                    prices.append({
                        'time': f"{parts[0]}T00:00:00Z",
                        'open': float(parts[1]),
                        'close': float(parts[2]),
                        'high': float(parts[3]),
                        'low': float(parts[4]),
                        'volume': int(float(parts[5])),
                    })
            except (ValueError, IndexError) as e:
                self.logger.warning(f"[EastmoneyCurl] Failed to parse kline: {e}")
                continue

        if prices:
            self.logger.info(f"[EastmoneyCurl] ✓ Retrieved {len(prices)} prices for {ticker}")

        return prices

    def get_company_news(self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get company news (not supported)."""
        return []
