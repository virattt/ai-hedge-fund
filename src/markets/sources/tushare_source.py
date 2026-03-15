"""Tushare data source for CN market."""
import logging
from typing import Dict, List, Optional
from datetime import datetime
import time
import os

from src.markets.sources.base import DataSource

logger = logging.getLogger(__name__)


class TushareSource(DataSource):
    """Tushare Pro data source for Chinese market."""

    def __init__(self, token: Optional[str] = None):
        super().__init__("Tushare")
        self._tushare = None
        self._token = token or os.getenv("TUSHARE_TOKEN")
        self._initialize_tushare()

    def _initialize_tushare(self):
        """Lazy initialization of tushare module."""
        if not self._token:
            self.logger.warning(
                "Tushare token not provided. Set TUSHARE_TOKEN environment variable. "
                "Get token from: https://tushare.pro/register"
            )
            return

        try:
            import tushare as ts
            ts.set_token(self._token)
            self._tushare = ts.pro_api()
            self.logger.debug("Tushare initialized successfully")
        except ImportError:
            self.logger.error("Tushare not installed. Install with: pip install tushare")
            self._tushare = None
        except Exception as e:
            self.logger.error(f"Failed to initialize Tushare: {e}")
            self._tushare = None

    def _ensure_tushare(self):
        """Ensure tushare is available."""
        if self._tushare is None:
            self._initialize_tushare()
        if self._tushare is None:
            raise RuntimeError("Tushare is not available")

    def supports_market(self, market: str) -> bool:
        """Check if this data source supports a specific market."""
        return market.upper() == "CN"

    def get_prices(
        self, ticker: str, start_date: str, end_date: str, max_retries: int = 3
    ) -> List[Dict]:
        """
        Get price data from Tushare.

        Args:
            ticker: Stock ticker (e.g., '000001' for CN)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            max_retries: Maximum retry attempts

        Returns:
            List of price dictionaries
        """
        self._ensure_tushare()

        for attempt in range(max_retries):
            try:
                # Add delay to respect rate limits (200/min for basic, 500/min for pro)
                time.sleep(0.5)

                # Convert ticker format: 000001 -> 000001.SZ, 600000 -> 600000.SH
                ts_code = self._convert_to_ts_code(ticker)

                # Format dates for tushare (YYYYMMDD)
                start = start_date.replace("-", "")
                end = end_date.replace("-", "")

                # Log the API call details
                self.logger.info(
                    f"[Tushare] 📡 Calling daily(ts_code={ts_code}, "
                    f"start_date={start}, end_date={end})"
                )

                # Get daily price data
                df = self._tushare.daily(
                    ts_code=ts_code,
                    start_date=start,
                    end_date=end,
                    fields='trade_date,open,high,low,close,vol'
                )

                if df is None or df.empty:
                    self.logger.warning(f"[Tushare] No price data for {ticker} ({ts_code})")
                    return []

                # Convert to standard format
                prices = []
                for _, row in df.iterrows():
                    try:
                        price_dict = {
                            "open": float(row["open"]),
                            "close": float(row["close"]),
                            "high": float(row["high"]),
                            "low": float(row["low"]),
                            "volume": int(row["vol"] * 100),  # Tushare uses 手 (100 shares)
                            "time": self._parse_date(row["trade_date"]),
                        }
                        prices.append(price_dict)
                    except (ValueError, TypeError, KeyError) as e:
                        self.logger.warning(f"Failed to parse row for {ticker}: {e}")
                        continue

                # Sort by date ascending
                prices.sort(key=lambda x: x["time"])

                self.logger.info(f"[Tushare] ✓ Retrieved {len(prices)} price records for {ticker}")
                return prices

            except Exception as e:
                self.logger.warning(
                    f"[Tushare] Attempt {attempt + 1}/{max_retries} failed for {ticker}: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))  # Exponential backoff
                else:
                    self.logger.error(f"[Tushare] Failed to get prices for {ticker} after {max_retries} attempts")
                    return []

        return []

    def _convert_to_ts_code(self, ticker: str) -> str:
        """
        Convert ticker to Tushare code format.

        Args:
            ticker: Stock ticker (e.g., '000001', '600000')

        Returns:
            Tushare code (e.g., '000001.SZ', '600000.SH')
        """
        # Remove any existing suffix
        ticker = ticker.split('.')[0]

        # Pad with zeros if needed
        if len(ticker) < 6:
            ticker = ticker.zfill(6)

        # Determine exchange
        if ticker.startswith('6'):
            return f"{ticker}.SH"  # Shanghai
        elif ticker.startswith(('0', '3')):
            return f"{ticker}.SZ"  # Shenzhen
        else:
            self.logger.warning(f"Unknown exchange for ticker {ticker}, defaulting to SH")
            return f"{ticker}.SH"

    def _parse_date(self, date_str: str) -> str:
        """
        Parse Tushare date to ISO format.

        Args:
            date_str: Date string in YYYYMMDD format

        Returns:
            ISO format date string
        """
        try:
            dt = datetime.strptime(str(date_str), "%Y%m%d")
            return dt.strftime("%Y-%m-%dT00:00:00Z")
        except ValueError:
            return date_str

    def get_financial_metrics(
        self, ticker: str, end_date: str, period: str = "ttm", limit: int = 10
    ) -> Optional[Dict]:
        """
        Get financial metrics from Tushare.

        Note: Requires Tushare Pro 5000+ points.
        """
        self._ensure_tushare()

        try:
            time.sleep(0.5)  # Rate limiting

            ts_code = self._convert_to_ts_code(ticker)

            # Get basic financial indicators
            df = self._tushare.fina_indicator(
                ts_code=ts_code,
                period=end_date.replace('-', '')[:6],  # YYYYMM
                fields='ts_code,end_date,pe,pb,roe,gross_margin,net_margin,debt_to_assets'
            )

            if df is None or df.empty:
                return None

            # Get the most recent row
            latest = df.iloc[0]

            metrics = {
                "ticker": ticker,
                "report_period": str(latest.get("end_date", "")),
                "period": period,
                "currency": "CNY",
                "price_to_earnings_ratio": self._safe_float(latest.get("pe")),
                "price_to_book_ratio": self._safe_float(latest.get("pb")),
                "return_on_equity": self._safe_float(latest.get("roe")),
                "gross_margin": self._safe_float(latest.get("gross_margin")),
                "net_margin": self._safe_float(latest.get("net_margin")),
                "debt_to_equity": self._safe_float(latest.get("debt_to_assets")),
            }

            return metrics

        except Exception as e:
            self.logger.error(f"[Tushare] Failed to get financial metrics for {ticker}: {e}")
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
        Get company news from Tushare.

        Note: Tushare has limited news coverage. Returns empty list.
        """
        # Tushare doesn't provide comprehensive news API
        return []
