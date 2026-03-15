"""YFinance data source for global markets."""
import logging
from typing import Dict, List, Optional
from datetime import datetime
import time
import random
from functools import lru_cache
import hashlib

from src.markets.sources.base import DataSource

logger = logging.getLogger(__name__)


class YFinanceSource(DataSource):
    """YFinance data source for global markets including HK."""

    def __init__(self):
        super().__init__("YFinance")
        self._yf = None
        self._initialize_yfinance()
        self._request_cache = {}  # Simple in-memory cache for requests
        self._last_request_time = 0  # Track last request time for rate limiting

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

    def _enforce_rate_limit(self, min_delay: float = 2.0, max_delay: float = 5.0):
        """
        Enforce rate limiting by adding delay before each request.

        Args:
            min_delay: Minimum delay in seconds (default: 2.0)
            max_delay: Maximum delay in seconds (default: 5.0)
        """
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time

        # Always add a minimum delay, plus random jitter
        base_delay = random.uniform(min_delay, max_delay)

        # If we made a request too recently, add additional wait time
        if time_since_last_request < min_delay:
            additional_wait = min_delay - time_since_last_request
            total_delay = base_delay + additional_wait
        else:
            total_delay = base_delay

        self.logger.debug(f"[YFinance] Rate limit: waiting {total_delay:.2f}s before request")
        time.sleep(total_delay)
        self._last_request_time = time.time()

    def _get_cache_key(self, method: str, **kwargs) -> str:
        """Generate cache key from method and parameters."""
        # Create deterministic key from method and sorted kwargs
        key_parts = [method]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str, max_age: int = 300):
        """
        Get data from cache if available and not expired.

        Args:
            cache_key: Cache key
            max_age: Maximum cache age in seconds (default: 5 minutes)

        Returns:
            Cached data if available and fresh, None otherwise
        """
        if cache_key in self._request_cache:
            cached_data, timestamp = self._request_cache[cache_key]
            age = time.time() - timestamp
            if age < max_age:
                self.logger.debug(f"[YFinance] Cache hit for {cache_key[:8]}... (age: {age:.1f}s)")
                return cached_data
            else:
                self.logger.debug(f"[YFinance] Cache expired for {cache_key[:8]}... (age: {age:.1f}s)")
        return None

    def _save_to_cache(self, cache_key: str, data):
        """Save data to cache with timestamp."""
        self._request_cache[cache_key] = (data, time.time())
        self.logger.debug(f"[YFinance] Cached data for {cache_key[:8]}...")

    def supports_market(self, market: str) -> bool:
        """Check if this data source supports a specific market."""
        # YFinance supports most global markets
        return market.upper() in ["US", "HK", "CN"]

    def get_prices(
        self, ticker: str, start_date: str, end_date: str, max_retries: int = 3
    ) -> List[Dict]:
        """
        Get price data from YFinance with enhanced rate limiting and caching.

        Args:
            ticker: Stock ticker (e.g., '0700.HK' for HK, 'AAPL' for US)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            max_retries: Maximum retry attempts

        Returns:
            List of price dictionaries
        """
        self._ensure_yfinance()

        # Check cache first
        cache_key = self._get_cache_key(
            "get_prices", ticker=ticker, start_date=start_date, end_date=end_date
        )
        cached_result = self._get_from_cache(cache_key, max_age=300)  # 5 minute cache
        if cached_result is not None:
            self.logger.info(f"[YFinance] Using cached price data for {ticker}")
            return cached_result

        for attempt in range(max_retries):
            try:
                # Exponential backoff with jitter for retries
                if attempt > 0:
                    # Exponential backoff: 4s, 8s, 16s with random jitter
                    base_delay = 4 * (2 ** (attempt - 1))
                    jitter = random.uniform(0, 2)
                    delay = min(base_delay + jitter, 30)  # Cap at 30 seconds
                    self.logger.info(
                        f"[YFinance] Exponential backoff: waiting {delay:.1f}s "
                        f"before retry {attempt + 1}/{max_retries}"
                    )
                    time.sleep(delay)
                else:
                    # Enforce rate limit on first attempt (2-5 seconds)
                    self._enforce_rate_limit(min_delay=2.0, max_delay=5.0)

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
                    result = []
                    self._save_to_cache(cache_key, result)
                    return result

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
                self._save_to_cache(cache_key, prices)
                return prices

            except Exception as e:
                error_msg = str(e).lower()
                is_rate_limit = any(
                    phrase in error_msg
                    for phrase in ["rate limit", "too many requests", "429", "quota"]
                )

                if is_rate_limit:
                    self.logger.warning(
                        f"[YFinance] Rate limit hit for {ticker} on attempt {attempt + 1}/{max_retries}"
                    )
                else:
                    self.logger.warning(
                        f"[YFinance] Attempt {attempt + 1}/{max_retries} failed for {ticker}: {e}"
                    )

                if attempt >= max_retries - 1:
                    self.logger.error(
                        f"[YFinance] Failed to get prices for {ticker} after {max_retries} attempts"
                    )
                    return []
                # Exponential backoff delay handled at start of next iteration

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
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10, max_retries: int = 3
    ) -> Optional[Dict]:
        """
        Get financial metrics from YFinance with enhanced rate limiting and caching.

        Note: YFinance provides basic financial metrics through the info API.
        """
        self._ensure_yfinance()

        # Check cache first
        cache_key = self._get_cache_key(
            "get_financial_metrics", ticker=ticker, end_date=end_date, period=period
        )
        cached_result = self._get_from_cache(cache_key, max_age=600)  # 10 minute cache
        if cached_result is not None:
            self.logger.info(f"[YFinance] Using cached financial metrics for {ticker}")
            return cached_result

        for attempt in range(max_retries):
            try:
                # Exponential backoff with jitter for retries
                if attempt > 0:
                    base_delay = 4 * (2 ** (attempt - 1))
                    jitter = random.uniform(0, 2)
                    delay = min(base_delay + jitter, 30)
                    self.logger.info(
                        f"[YFinance] Exponential backoff: waiting {delay:.1f}s "
                        f"before retry {attempt + 1}/{max_retries}"
                    )
                    time.sleep(delay)
                else:
                    # Enforce rate limit on first attempt
                    self._enforce_rate_limit(min_delay=2.0, max_delay=5.0)

                yf_ticker = self._format_ticker_for_yfinance(ticker)

                self.logger.info(f"[YFinance] 📡 Calling Ticker({yf_ticker}).info")

                stock = self._yf.Ticker(yf_ticker)
                info = stock.info

                if not info:
                    self.logger.warning(f"[YFinance] No financial metrics for {ticker}")
                    result = None
                    self._save_to_cache(cache_key, result)
                    return result

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

                self.logger.info(f"[YFinance] ✓ Retrieved financial metrics for {ticker}")
                self._save_to_cache(cache_key, metrics)
                return metrics

            except Exception as e:
                error_msg = str(e).lower()
                is_rate_limit = any(
                    phrase in error_msg
                    for phrase in ["rate limit", "too many requests", "429", "quota"]
                )

                if is_rate_limit:
                    self.logger.warning(
                        f"[YFinance] Rate limit hit for {ticker} on attempt {attempt + 1}/{max_retries}"
                    )
                else:
                    self.logger.warning(
                        f"[YFinance] Attempt {attempt + 1}/{max_retries} failed for {ticker}: {e}"
                    )

                if attempt >= max_retries - 1:
                    self.logger.error(
                        f"[YFinance] Failed to get financial metrics for {ticker} after {max_retries} attempts"
                    )
                    return None
                # Exponential backoff delay handled at start of next iteration

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
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100,
        max_retries: int = 3
    ) -> List[Dict]:
        """
        Get company news from YFinance with enhanced rate limiting and caching.

        Note: YFinance provides limited news through the news API.
        """
        self._ensure_yfinance()

        # Check cache first
        cache_key = self._get_cache_key(
            "get_company_news",
            ticker=ticker,
            end_date=end_date,
            start_date=start_date or "",
            limit=limit,
        )
        cached_result = self._get_from_cache(cache_key, max_age=600)  # 10 minute cache
        if cached_result is not None:
            self.logger.info(f"[YFinance] Using cached news for {ticker}")
            return cached_result

        for attempt in range(max_retries):
            try:
                # Exponential backoff with jitter for retries
                if attempt > 0:
                    base_delay = 4 * (2 ** (attempt - 1))
                    jitter = random.uniform(0, 2)
                    delay = min(base_delay + jitter, 30)
                    self.logger.info(
                        f"[YFinance] Exponential backoff: waiting {delay:.1f}s "
                        f"before retry {attempt + 1}/{max_retries}"
                    )
                    time.sleep(delay)
                else:
                    # Enforce rate limit on first attempt
                    self._enforce_rate_limit(min_delay=2.0, max_delay=5.0)

                yf_ticker = self._format_ticker_for_yfinance(ticker)

                self.logger.info(f"[YFinance] 📡 Calling Ticker({yf_ticker}).news")

                stock = self._yf.Ticker(yf_ticker)
                news = stock.news

                if not news:
                    self.logger.warning(f"[YFinance] No news for {ticker}")
                    result = []
                    self._save_to_cache(cache_key, result)
                    return result

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

                result = news_list[:limit]
                self.logger.info(f"[YFinance] ✓ Retrieved {len(result)} news items for {ticker}")
                self._save_to_cache(cache_key, result)
                return result

            except Exception as e:
                error_msg = str(e).lower()
                is_rate_limit = any(
                    phrase in error_msg
                    for phrase in ["rate limit", "too many requests", "429", "quota"]
                )

                if is_rate_limit:
                    self.logger.warning(
                        f"[YFinance] Rate limit hit for {ticker} on attempt {attempt + 1}/{max_retries}"
                    )
                else:
                    self.logger.warning(
                        f"[YFinance] Attempt {attempt + 1}/{max_retries} failed for {ticker}: {e}"
                    )

                if attempt >= max_retries - 1:
                    self.logger.error(
                        f"[YFinance] Failed to get company news for {ticker} after {max_retries} attempts"
                    )
                    return []
                # Exponential backoff delay handled at start of next iteration

        return []
