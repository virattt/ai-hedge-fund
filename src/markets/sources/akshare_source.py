"""AKShare data source for CN and HK markets."""
import logging
from typing import Dict, List, Optional
from datetime import datetime
import time

from src.markets.sources.base import DataSource

logger = logging.getLogger(__name__)


class AKShareSource(DataSource):
    """AKShare data source for Chinese and Hong Kong markets."""

    def __init__(self):
        super().__init__("AKShare")
        self._akshare = None
        self._initialize_akshare()

    def _initialize_akshare(self):
        """Lazy initialization of akshare module."""
        try:
            import akshare as ak
            self._akshare = ak
            self.logger.info("AKShare initialized successfully")
        except ImportError:
            self.logger.error("AKShare not installed. Install with: pip install akshare")
            self._akshare = None

    def _ensure_akshare(self):
        """Ensure akshare is available."""
        if self._akshare is None:
            self._initialize_akshare()
        if self._akshare is None:
            raise RuntimeError("AKShare is not available")

    def supports_market(self, market: str) -> bool:
        """Check if this data source supports a specific market."""
        return market.upper() in ["CN", "HK"]

    def get_prices(
        self, ticker: str, start_date: str, end_date: str, max_retries: int = 3
    ) -> List[Dict]:
        """
        Get price data from AKShare.

        Args:
            ticker: Stock ticker (e.g., '000001' for CN, '00700' for HK)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            max_retries: Maximum retry attempts

        Returns:
            List of price dictionaries
        """
        self._ensure_akshare()

        for attempt in range(max_retries):
            # Add delay before each request to avoid rate limiting
            if attempt > 0:
                delay = 3 * (attempt + 1)  # 3s, 6s, 9s...
                self.logger.info(f"[AKShare] Waiting {delay}s before retry {attempt + 1}/{max_retries}")
                time.sleep(delay)
            else:
                # Small delay even on first attempt
                time.sleep(1)

            try:
                # Determine market from ticker format
                if self._is_hk_ticker(ticker):
                    df = self._get_hk_prices(ticker, start_date, end_date)
                else:
                    df = self._get_cn_prices(ticker, start_date, end_date)

                if df is None or df.empty:
                    self.logger.warning(f"[AKShare] No price data for {ticker}")
                    return []

                # Convert to standard format
                prices = []
                for _, row in df.iterrows():
                    try:
                        price_dict = {
                            "open": float(row.get("开盘", row.get("open", 0))),
                            "close": float(row.get("收盘", row.get("close", 0))),
                            "high": float(row.get("最高", row.get("high", 0))),
                            "low": float(row.get("最低", row.get("low", 0))),
                            "volume": int(row.get("成交量", row.get("volume", 0))),
                            "time": self._parse_date(row.get("日期", row.name)),
                        }
                        prices.append(price_dict)
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"Failed to parse row for {ticker}: {e}")
                        continue

                self.logger.info(f"[AKShare] ✓ Retrieved {len(prices)} price records for {ticker}")
                return prices

            except Exception as e:
                self.logger.warning(
                    f"[AKShare] Attempt {attempt + 1}/{max_retries} failed for {ticker}: {e}"
                )
                if attempt >= max_retries - 1:
                    self.logger.error(f"[AKShare] Failed to get prices for {ticker} after {max_retries} attempts")
                    return []
                # Delay is handled at the start of the next iteration

        return []

    def _is_hk_ticker(self, ticker: str) -> bool:
        """Check if ticker is Hong Kong stock."""
        # HK tickers are typically 5 digits starting with 0
        return len(ticker) == 5 and ticker.isdigit()

    def _get_cn_prices(self, ticker: str, start_date: str, end_date: str):
        """Get CN A-share prices."""
        try:
            # Format dates for akshare (YYYYMMDD)
            start = start_date.replace("-", "")
            end = end_date.replace("-", "")

            # Use stock_zh_a_hist for A-share historical data
            df = self._akshare.stock_zh_a_hist(
                symbol=ticker,
                start_date=start,
                end_date=end,
                adjust="qfq"  # Forward adjusted
            )
            return df
        except Exception as e:
            self.logger.error(f"[AKShare] Failed to get CN prices for {ticker}: {e}")
            return None

    def _get_hk_prices(self, ticker: str, start_date: str, end_date: str):
        """Get HK stock prices."""
        try:
            # Format dates for akshare (YYYYMMDD)
            start = start_date.replace("-", "")
            end = end_date.replace("-", "")

            # Use stock_hk_hist for HK stock historical data
            df = self._akshare.stock_hk_hist(
                symbol=ticker,
                start_date=start,
                end_date=end,
                adjust="qfq"  # Forward adjusted
            )
            return df
        except Exception as e:
            self.logger.error(f"[AKShare] Failed to get HK prices for {ticker}: {e}")
            return None

    def _parse_date(self, date_value) -> str:
        """Parse date to ISO format."""
        if isinstance(date_value, str):
            # Already in string format
            try:
                dt = datetime.strptime(date_value, "%Y-%m-%d")
                return dt.strftime("%Y-%m-%dT00:00:00Z")
            except ValueError:
                return date_value
        else:
            # Pandas Timestamp
            return date_value.strftime("%Y-%m-%dT00:00:00Z")

    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> Optional[Dict]:
        """
        Get financial metrics from AKShare.

        Note: AKShare provides limited financial metrics compared to US APIs.
        """
        self._ensure_akshare()

        try:
            if self._is_hk_ticker(ticker):
                return self._get_hk_financial_metrics(ticker)
            else:
                return self._get_cn_financial_metrics(ticker)
        except Exception as e:
            self.logger.error(f"[AKShare] Failed to get financial metrics for {ticker}: {e}")
            return None

    def _get_cn_financial_metrics(self, ticker: str) -> Optional[Dict]:
        """Get CN stock financial metrics."""
        try:
            # Get basic financial indicators
            df = self._akshare.stock_financial_analysis_indicator(symbol=ticker)

            if df is None or df.empty:
                return None

            # Get the most recent row
            latest = df.iloc[0]

            metrics = {
                "ticker": ticker,
                "report_period": str(latest.get("报告期", "")),
                "period": "ttm",
                "currency": "CNY",
                "price_to_earnings_ratio": self._safe_float(latest.get("市盈率")),
                "price_to_book_ratio": self._safe_float(latest.get("市净率")),
                "return_on_equity": self._safe_float(latest.get("净资产收益率")),
                "gross_margin": self._safe_float(latest.get("销售毛利率")),
                "net_margin": self._safe_float(latest.get("销售净利率")),
                "debt_to_equity": self._safe_float(latest.get("资产负债率")),
                "revenue_growth": self._safe_float(latest.get("营业收入同比增长率")),
                "earnings_growth": self._safe_float(latest.get("净利润同比增长率")),
            }

            return metrics
        except Exception as e:
            self.logger.error(f"[AKShare] Failed to get CN financial metrics for {ticker}: {e}")
            return None

    def _get_hk_financial_metrics(self, ticker: str) -> Optional[Dict]:
        """Get HK stock financial metrics."""
        try:
            # AKShare has limited HK financial data
            # Return basic metrics if available
            return {
                "ticker": ticker,
                "report_period": "",
                "period": "ttm",
                "currency": "HKD",
            }
        except Exception as e:
            self.logger.error(f"[AKShare] Failed to get HK financial metrics for {ticker}: {e}")
            return None

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        try:
            if value is None or value == "" or value == "--":
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    def get_company_news(
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Get company news from AKShare.

        Note: AKShare has limited news coverage.
        """
        self._ensure_akshare()

        try:
            # AKShare news functions are limited
            # Try to get general market news
            news_list = []

            # For CN stocks, try to get news
            if not self._is_hk_ticker(ticker):
                try:
                    df = self._akshare.stock_news_em(symbol=ticker)
                    if df is not None and not df.empty:
                        for _, row in df.head(limit).iterrows():
                            news_item = {
                                "ticker": ticker,
                                "title": str(row.get("新闻标题", "")),
                                "date": self._parse_date(row.get("发布时间", "")),
                                "source": str(row.get("新闻来源", "东方财富")),
                                "url": str(row.get("新闻链接", "")),
                                "author": "",
                                "sentiment": None,
                            }
                            news_list.append(news_item)
                except Exception as e:
                    self.logger.warning(f"Failed to get news for {ticker}: {e}")

            return news_list[:limit]

        except Exception as e:
            self.logger.error(f"[AKShare] Failed to get company news for {ticker}: {e}")
            return []
