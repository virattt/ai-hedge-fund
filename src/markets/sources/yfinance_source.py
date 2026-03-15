"""YFinance data source for global markets."""
import logging
from typing import Dict, List, Optional
from datetime import datetime
import time
import random

from src.markets.sources.base import DataSource

logger = logging.getLogger(__name__)


class YFinanceSource(DataSource):
    """YFinance data source for global markets including HK."""

    def __init__(self):
        super().__init__("YFinance")
        self._yf = None
        self._initialize_yfinance()

    def _initialize_yfinance(self):
        """Lazy initialization of yfinance module with anti-rate-limit configuration."""
        try:
            import yfinance as yf

            # YFinance now handles sessions internally using curl_cffi
            # We just need to add delays between requests
            self._yf = yf
            self.logger.debug("YFinance initialized successfully with rate-limit protection")
        except ImportError:
            self.logger.error("YFinance not installed. Install with: pip install yfinance")
            self._yf = None

    def _ensure_yfinance(self):
        """Ensure yfinance is available."""
        if self._yf is None:
            self._initialize_yfinance()
        if self._yf is None:
            raise RuntimeError("YFinance is not available")

    def supports_market(self, market: str) -> bool:
        """Check if this data source supports a specific market."""
        # YFinance supports most global markets
        return market.upper() in ["US", "HK", "CN"]

    def get_prices(
        self, ticker: str, start_date: str, end_date: str, max_retries: int = 3
    ) -> List[Dict]:
        """
        Get price data from YFinance.

        Args:
            ticker: Stock ticker (e.g., '0700.HK' for HK, 'AAPL' for US)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            max_retries: Maximum retry attempts

        Returns:
            List of price dictionaries
        """
        self._ensure_yfinance()

        for attempt in range(max_retries):
            try:
                # Add random delay before request to avoid rate limiting
                if attempt > 0:
                    delay = random.uniform(2, 5) * (attempt + 1)
                    self.logger.info(f"[YFinance] Waiting {delay:.1f}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(delay)
                else:
                    # Small random delay even on first attempt
                    time.sleep(random.uniform(0.5, 1.5))

                # Format ticker for yfinance
                yf_ticker = self._format_ticker_for_yfinance(ticker)

                # Log the API call details
                self.logger.info(
                    f"[YFinance] 📡 Calling Ticker({yf_ticker}).history("
                    f"start={start_date}, end={end_date})"
                )

                # Download data (let YFinance handle session management)
                stock = self._yf.Ticker(yf_ticker)
                df = stock.history(start=start_date, end=end_date)

                if df is None or df.empty:
                    self.logger.warning(f"[YFinance] No price data for {ticker} ({yf_ticker})")
                    return []

                # Convert to standard format
                prices = []
                for date, row in df.iterrows():
                    try:
                        price_dict = {
                            "open": float(row["Open"]),
                            "close": float(row["Close"]),
                            "high": float(row["High"]),
                            "low": float(row["Low"]),
                            "volume": int(row["Volume"]),
                            "time": date.strftime("%Y-%m-%dT00:00:00Z"),
                        }
                        prices.append(price_dict)
                    except (ValueError, TypeError, KeyError) as e:
                        self.logger.warning(f"Failed to parse row for {ticker}: {e}")
                        continue

                self.logger.info(f"[YFinance] ✓ Retrieved {len(prices)} price records for {ticker}")
                return prices

            except Exception as e:
                self.logger.warning(
                    f"[YFinance] Attempt {attempt + 1}/{max_retries} failed for {ticker}: {e}"
                )
                if attempt >= max_retries - 1:
                    self.logger.error(f"[YFinance] Failed to get prices for {ticker} after {max_retries} attempts")
                    return []
                # Delay is handled at the start of the next iteration

        return []

    def _format_ticker_for_yfinance(self, ticker: str) -> str:
        """
        Format ticker for yfinance.

        Examples:
            - HK: '00700' -> '0700.HK'
            - CN: '000001' -> '000001.SS' (Shanghai) or '000001.SZ' (Shenzhen)
            - US: 'AAPL' -> 'AAPL'
        """
        # If already formatted with suffix, return as is
        if "." in ticker:
            return ticker

        # HK stocks: 5 digits
        if len(ticker) == 5 and ticker.isdigit():
            # Remove leading zero for yfinance
            return f"{int(ticker):04d}.HK"

        # CN stocks: 6 digits
        if len(ticker) == 6 and ticker.isdigit():
            # Shanghai stocks start with 6, Shenzhen with 0 or 3
            if ticker.startswith("6"):
                return f"{ticker}.SS"
            else:
                return f"{ticker}.SZ"

        # Default: return as is (assume US or already formatted)
        return ticker

    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> Optional[Dict]:
        """
        Get financial metrics from YFinance.

        Note: YFinance provides basic financial metrics through the info API.
        """
        self._ensure_yfinance()

        # Add small random delay to avoid rate limiting
        time.sleep(random.uniform(0.5, 1.5))

        try:
            yf_ticker = self._format_ticker_for_yfinance(ticker)
            stock = self._yf.Ticker(yf_ticker)
            info = stock.info

            if not info:
                return None

            # Map yfinance info to our standard format
            metrics = {
                "ticker": ticker,
                "report_period": end_date,
                "period": period,
                "currency": info.get("currency", "USD"),
                "market_cap": self._safe_float(info.get("marketCap")),
                "enterprise_value": self._safe_float(info.get("enterpriseValue")),
                "price_to_earnings_ratio": self._safe_float(info.get("trailingPE")),
                "price_to_book_ratio": self._safe_float(info.get("priceToBook")),
                "price_to_sales_ratio": self._safe_float(info.get("priceToSalesTrailing12Months")),
                "enterprise_value_to_ebitda_ratio": self._safe_float(info.get("enterpriseToEbitda")),
                "enterprise_value_to_revenue_ratio": self._safe_float(info.get("enterpriseToRevenue")),
                "gross_margin": self._safe_float(info.get("grossMargins")),
                "operating_margin": self._safe_float(info.get("operatingMargins")),
                "net_margin": self._safe_float(info.get("profitMargins")),
                "return_on_equity": self._safe_float(info.get("returnOnEquity")),
                "return_on_assets": self._safe_float(info.get("returnOnAssets")),
                "current_ratio": self._safe_float(info.get("currentRatio")),
                "quick_ratio": self._safe_float(info.get("quickRatio")),
                "debt_to_equity": self._safe_float(info.get("debtToEquity")),
                "revenue_growth": self._safe_float(info.get("revenueGrowth")),
                "earnings_growth": self._safe_float(info.get("earningsGrowth")),
                "payout_ratio": self._safe_float(info.get("payoutRatio")),
                "earnings_per_share": self._safe_float(info.get("trailingEps")),
                "book_value_per_share": self._safe_float(info.get("bookValue")),
            }

            return metrics

        except Exception as e:
            self.logger.error(f"[YFinance] Failed to get financial metrics for {ticker}: {e}")
            return None

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        try:
            if value is None or value == "" or value == "N/A":
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    def get_company_news(
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Get company news from YFinance.

        Note: YFinance provides limited news through the news API.
        """
        self._ensure_yfinance()

        # Add small random delay to avoid rate limiting
        time.sleep(random.uniform(0.5, 1.5))

        try:
            yf_ticker = self._format_ticker_for_yfinance(ticker)
            stock = self._yf.Ticker(yf_ticker)
            news = stock.news

            if not news:
                return []

            news_list = []
            for item in news[:limit]:
                try:
                    # Parse timestamp
                    news_date = datetime.fromtimestamp(item.get("providerPublishTime", 0))
                    date_str = news_date.strftime("%Y-%m-%dT%H:%M:%SZ")

                    # Filter by date range if provided
                    if start_date and date_str < start_date:
                        continue
                    if end_date and date_str > end_date:
                        continue

                    news_item = {
                        "ticker": ticker,
                        "title": item.get("title", ""),
                        "date": date_str,
                        "source": item.get("publisher", ""),
                        "url": item.get("link", ""),
                        "author": "",
                        "sentiment": None,
                    }
                    news_list.append(news_item)
                except Exception as e:
                    self.logger.warning(f"Failed to parse news item: {e}")
                    continue

            return news_list[:limit]

        except Exception as e:
            self.logger.error(f"[YFinance] Failed to get company news for {ticker}: {e}")
            return []
