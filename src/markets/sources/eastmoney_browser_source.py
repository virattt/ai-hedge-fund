"""Eastmoney data source using browser automation to bypass anti-bot protection."""
import json
import logging
import time
import random
from typing import Dict, List, Optional
from datetime import datetime

from src.markets.sources.base import DataSource

logger = logging.getLogger(__name__)


class EastmoneyBrowserSource(DataSource):
    """
    Eastmoney data source using Playwright browser automation.

    This bypasses Eastmoney's anti-bot protection by using a real browser.
    Falls back to regular EastmoneySource if Playwright is not available.
    """

    def __init__(self):
        super().__init__("EastmoneyBrowser")
        self.browser = None
        self.page = None
        self._playwright = None
        self._browser_instance = None

        # Try to initialize Playwright
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser_instance = self._playwright.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )
            self.browser = self._browser_instance.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
            )
            self.page = self.browser.new_page()
            self.logger.info("[EastmoneyBrowser] Initialized with Playwright")
        except ImportError:
            self.logger.warning("[EastmoneyBrowser] Playwright not installed, will not be available")
            self.browser = None
        except Exception as e:
            self.logger.warning(f"[EastmoneyBrowser] Failed to initialize Playwright: {e}")
            self.browser = None

    def __del__(self):
        """Clean up browser resources."""
        try:
            if self.page:
                self.page.close()
            if self.browser:
                self.browser.close()
            if self._browser_instance:
                self._browser_instance.close()
            if self._playwright:
                self._playwright.stop()
        except:
            pass

    def supports_market(self, market: str) -> bool:
        """Eastmoney only supports CN market."""
        return market.upper() == "CN" and self.browser is not None

    def _fetch_json_via_browser(self, url: str, max_retries: int = 3) -> Optional[Dict]:
        """
        Fetch JSON data using Playwright browser.

        Args:
            url: URL to fetch
            max_retries: Maximum retry attempts

        Returns:
            JSON data or None
        """
        if not self.page:
            return None

        for attempt in range(max_retries):
            try:
                # Add delay to avoid rate limiting
                if attempt > 0:
                    delay = 2 ** attempt
                    self.logger.info(f"[EastmoneyBrowser] Retry {attempt+1}, waiting {delay}s")
                    time.sleep(delay)
                else:
                    time.sleep(random.uniform(0.5, 1.5))

                # Navigate to URL
                response = self.page.goto(url, timeout=15000, wait_until='networkidle')

                if not response or not response.ok:
                    self.logger.warning(f"[EastmoneyBrowser] HTTP {response.status if response else 'None'}")
                    continue

                # Get page content (JSON is usually in <pre> or <body>)
                try:
                    # Try to get from <pre> tag first
                    json_text = self.page.inner_text('pre')
                except:
                    # Fallback to body
                    json_text = self.page.inner_text('body')

                # Parse JSON
                data = json.loads(json_text)
                return data

            except Exception as e:
                self.logger.warning(f"[EastmoneyBrowser] Attempt {attempt+1} failed: {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"[EastmoneyBrowser] All retries failed")
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
        Get financial metrics using browser automation.

        Args:
            ticker: Stock ticker
            end_date: End date
            period: Period type
            limit: Number of periods

        Returns:
            Financial metrics dictionary
        """
        if not self.browser:
            self.logger.warning("[EastmoneyBrowser] Browser not available")
            return None

        secid = self._to_eastmoney_secid(ticker)

        # Build URL
        url = (
            f"https://push2.eastmoney.com/api/qt/stock/get"
            f"?secid={secid}"
            f"&fields=f43,f116,f117,f162,f167,f173,f187"
        )

        # Fetch data via browser
        data = self._fetch_json_via_browser(url)

        if not data or 'data' not in data:
            self.logger.warning(f"[EastmoneyBrowser] No data for {ticker}")
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

            self.logger.info(f"[EastmoneyBrowser] ✓ Retrieved financial metrics for {ticker}")
            return metrics

        except Exception as e:
            self.logger.error(f"[EastmoneyBrowser] Failed to parse metrics: {e}")
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
        """Get price data (not implemented yet for browser source)."""
        self.logger.warning("[EastmoneyBrowser] get_prices not implemented yet")
        return []

    def get_company_news(self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get company news (not supported)."""
        return []
