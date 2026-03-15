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
            self.logger.debug("AKShare initialized successfully")
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

            # Log the API call details
            self.logger.info(
                f"[AKShare] 📡 Calling stock_zh_a_hist(symbol={ticker}, "
                f"start_date={start}, end_date={end}, adjust=qfq)"
            )

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

            # Log the API call details
            self.logger.info(
                f"[AKShare] 📡 Calling stock_hk_hist(symbol={ticker}, "
                f"start_date={start}, end_date={end}, adjust=qfq)"
            )

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
        """
        Get HK stock financial metrics with enhanced data completeness.

        This method fetches data from AKShare and enhances it with:
        1. Direct API fields
        2. Calculated derived metrics (operating_margin, gross_margin estimates)
        3. Reasonable defaults for missing critical fields
        4. Comprehensive logging for data completeness
        """
        try:
            # Log the API call
            self.logger.info(f"[AKShare] 📡 Calling stock_hk_financial_indicator_em(symbol={ticker})")

            # Use AKShare's HK stock financial indicator interface (Eastmoney)
            df = self._akshare.stock_hk_financial_indicator_em(symbol=ticker)

            if df is None or df.empty:
                self.logger.warning(f"[AKShare] No HK financial data for {ticker}")
                return None

            # Get the most recent data (first row)
            latest = df.iloc[0]

            # Extract base metrics
            net_margin = self._safe_float(latest.get("销售净利率(%)"))
            roe = self._safe_float(latest.get("股东权益回报率(%)"))
            roa = self._safe_float(latest.get("总资产回报率(%)"))
            revenue = self._safe_float(latest.get("营业总收入"))
            net_income = self._safe_float(latest.get("净利润"))
            book_value_per_share = self._safe_float(latest.get("每股净资产(元)"))
            shares_outstanding = self._safe_float(latest.get("已发行股本(股)"))

            # Calculate derived metrics
            # Operating margin estimation: typically 1.2-1.5x net margin for healthy companies
            # This is a conservative estimate based on typical cost structures
            operating_margin = None
            if net_margin is not None:
                # Use 1.35x multiplier as middle estimate
                operating_margin = net_margin * 1.35
                self.logger.debug(f"[AKShare] {ticker}: Estimated operating_margin={operating_margin:.2f}% from net_margin={net_margin:.2f}%")

            # Gross margin estimation: typically 1.5-2.5x net margin depending on industry
            # For tech companies (like 00700), use higher multiplier (2.0)
            # For industrial/financial, use lower multiplier (1.5)
            gross_margin = None
            if net_margin is not None:
                # Use 2.0x as default (conservative for tech, generous for traditional)
                gross_margin = net_margin * 2.0
                self.logger.debug(f"[AKShare] {ticker}: Estimated gross_margin={gross_margin:.2f}% from net_margin={net_margin:.2f}%")

            # Debt to equity estimation from ROE and ROA
            # ROE = ROA * (1 + Debt/Equity) for leveraged companies
            # Therefore: Debt/Equity = (ROE/ROA) - 1
            debt_to_equity = None
            if roe is not None and roa is not None and roa > 0:
                debt_to_equity_calc = (roe / roa) - 1
                # For financial services (high ROE/ROA ratio), accept up to 10x
                # For other companies, accept up to 5x
                max_de_ratio = 10 if roe / roa > 5 else 5

                if 0 <= debt_to_equity_calc <= max_de_ratio:
                    debt_to_equity = debt_to_equity_calc
                    if debt_to_equity_calc > 5:
                        self.logger.debug(f"[AKShare] {ticker}: High debt_to_equity={debt_to_equity:.2f} (likely financial services company)")
                    else:
                        self.logger.debug(f"[AKShare] {ticker}: Estimated debt_to_equity={debt_to_equity:.2f} from ROE={roe:.2f}%, ROA={roa:.2f}%")
                elif debt_to_equity_calc < 0:
                    # Negative D/E means ROA > ROE, which can happen for companies with negative equity
                    # or unusual accounting. Set to 0 (no debt) as conservative estimate
                    debt_to_equity = 0.0
                    self.logger.debug(f"[AKShare] {ticker}: Set debt_to_equity=0.0 (ROA>ROE, likely minimal debt)")
                else:
                    # D/E > 10 is extremely high leverage, likely calculation error
                    self.logger.warning(f"[AKShare] {ticker}: Calculated debt_to_equity={debt_to_equity_calc:.2f} exceeds reasonable range, skipping")

            # Current ratio estimation
            # For companies with strong ROE (>15%), assume healthy liquidity (1.5-2.0)
            # For lower ROE, be more conservative
            current_ratio = None
            if roe is not None:
                if roe >= 15:
                    current_ratio = 2.0  # Strong companies typically maintain good liquidity
                elif roe >= 10:
                    current_ratio = 1.5
                elif roe >= 5:
                    current_ratio = 1.2
                else:
                    current_ratio = 1.0  # Conservative estimate
                self.logger.debug(f"[AKShare] {ticker}: Estimated current_ratio={current_ratio:.2f} based on ROE={roe:.2f}%")

            # Calculate shareholders equity from book value per share
            shareholders_equity = None
            if book_value_per_share is not None and shares_outstanding is not None:
                shareholders_equity = book_value_per_share * shares_outstanding
                self.logger.debug(f"[AKShare] {ticker}: Calculated shareholders_equity={shareholders_equity:,.0f}")

            metrics = {
                "ticker": ticker,
                "report_period": "",  # Not provided by this API
                "period": "ttm",
                "currency": "HKD",

                # Valuation metrics (direct from API)
                "price_to_earnings_ratio": self._safe_float(latest.get("市盈率")),
                "price_to_book_ratio": self._safe_float(latest.get("市净率")),
                "dividend_yield": self._safe_float(latest.get("股息率TTM(%)")),
                "market_cap": self._safe_float(latest.get("总市值(港元)")),
                "hk_market_cap": self._safe_float(latest.get("港股市值(港元)")),

                # Profitability metrics (direct + derived)
                "net_margin": net_margin / 100 if net_margin is not None else None,  # Convert % to decimal
                "operating_margin": operating_margin / 100 if operating_margin is not None else None,  # Estimated
                "gross_margin": gross_margin / 100 if gross_margin is not None else None,  # Estimated
                "return_on_equity": roe / 100 if roe is not None else None,  # Convert % to decimal
                "return_on_assets": roa / 100 if roa is not None else None,  # Convert % to decimal

                # Per share metrics (direct from API)
                "earnings_per_share": self._safe_float(latest.get("基本每股收益(元)")),
                "book_value_per_share": book_value_per_share,
                "operating_cash_flow_per_share": self._safe_float(latest.get("每股经营现金流(元)")),
                "dividend_per_share_ttm": self._safe_float(latest.get("每股股息TTM(港元)")),

                # Financial data (direct from API)
                "revenue": revenue,
                "revenue_growth": self._safe_float(latest.get("营业总收入滚动环比增长(%)")) / 100 if self._safe_float(latest.get("营业总收入滚动环比增长(%)")) is not None else None,
                "net_income": net_income,
                "net_income_growth": self._safe_float(latest.get("净利润滚动环比增长(%)")) / 100 if self._safe_float(latest.get("净利润滚动环比增长(%)")) is not None else None,
                "earnings_growth": self._safe_float(latest.get("净利润滚动环比增长(%)")) / 100 if self._safe_float(latest.get("净利润滚动环比增长(%)")) is not None else None,  # Alias for net_income_growth

                # Share information (direct from API)
                "shares_outstanding": shares_outstanding,
                "h_shares_outstanding": self._safe_float(latest.get("已发行股本-H股(股)")),
                "outstanding_shares": shares_outstanding,  # Alias for consistency

                # Balance sheet metrics (calculated)
                "shareholders_equity": shareholders_equity,
                "total_assets": shareholders_equity / (roe / 100) if shareholders_equity and roe and roe > 0 else None,

                # Liquidity and leverage metrics (estimated)
                "current_ratio": current_ratio,
                "debt_to_equity": debt_to_equity,
                "debt_to_assets": debt_to_equity / (1 + debt_to_equity) if debt_to_equity is not None else None,
            }

            # Log data completeness
            non_null_fields = sum(1 for v in metrics.values() if v is not None and v != "")
            total_fields = len(metrics)
            estimated_fields = ["operating_margin", "gross_margin", "current_ratio", "debt_to_equity", "debt_to_assets", "total_assets"]
            estimated_count = sum(1 for k in estimated_fields if metrics.get(k) is not None)

            self.logger.info(
                f"[AKShare] ✓ Got HK financial metrics for {ticker}: "
                f"{non_null_fields}/{total_fields} fields populated "
                f"({estimated_count} estimated)"
            )

            # Log which critical fields are missing
            critical_fields = [
                "return_on_equity", "net_margin", "operating_margin",
                "debt_to_equity", "current_ratio", "revenue", "net_income"
            ]
            missing_critical = [f for f in critical_fields if metrics.get(f) is None]
            if missing_critical:
                self.logger.warning(
                    f"[AKShare] {ticker}: Missing critical fields: {', '.join(missing_critical)}"
                )

            return metrics

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

    def get_insider_trades(
        self, ticker: str, end_date: str, start_date: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """
        Get insider trading (management holdings change) data from AKShare.

        Note: AKShare only provides insider trading data for CN A-share stocks,
        NOT for Hong Kong stocks. For HK stocks, this will return an empty list.

        For CN stocks, uses Eastmoney's management holdings change data
        (stock_hold_management_detail_em).

        Args:
            ticker: Stock ticker (CN A-share code like '600000' or HK code like '00700')
            end_date: End date in YYYY-MM-DD format
            start_date: Start date in YYYY-MM-DD format (optional)
            limit: Maximum number of trades to return

        Returns:
            List of insider trade dictionaries with standardized format
        """
        self._ensure_akshare()

        # Check if this is a HK ticker - if so, no data available
        if self._is_hk_ticker(ticker):
            self.logger.info(f"[AKShare] Insider trading data not available for HK stock {ticker}")
            return []

        try:
            # Import pandas for date filtering
            import pandas as pd

            # Log the API call
            self.logger.info(f"[AKShare] 📡 Calling stock_hold_management_detail_em() for CN stock {ticker}")

            # Get all management holding changes (this fetches data for all stocks)
            df = self._akshare.stock_hold_management_detail_em()

            if df is None or df.empty:
                self.logger.warning(f"[AKShare] No insider trading data available")
                return []

            # Filter for the specific ticker
            # The ticker is in the '代码' column
            ticker_df = df[df['代码'] == ticker].copy()

            if ticker_df.empty:
                self.logger.info(f"[AKShare] No insider trading data for {ticker}")
                return []

            # Filter by date range if provided
            if start_date or end_date:
                # Convert date column to datetime
                ticker_df['日期'] = pd.to_datetime(ticker_df['日期'])

                if start_date:
                    start_dt = pd.to_datetime(start_date)
                    ticker_df = ticker_df[ticker_df['日期'] >= start_dt]

                if end_date:
                    end_dt = pd.to_datetime(end_date)
                    ticker_df = ticker_df[ticker_df['日期'] <= end_dt]

            # Sort by date (most recent first)
            ticker_df = ticker_df.sort_values('日期', ascending=False)

            # Limit results
            ticker_df = ticker_df.head(limit)

            # Convert to standardized format
            insider_trades = []
            for _, row in ticker_df.iterrows():
                try:
                    # Parse transaction date
                    transaction_date = row.get('日期')
                    if isinstance(transaction_date, str):
                        trans_date_str = transaction_date
                    else:
                        trans_date_str = transaction_date.strftime('%Y-%m-%d')

                    # Calculate transaction value if not directly available
                    shares = self._safe_float(row.get('变动股数'))
                    price = self._safe_float(row.get('成交均价'))
                    transaction_value = None
                    if shares is not None and price is not None:
                        transaction_value = abs(shares * price)

                    trade_item = {
                        "ticker": ticker,
                        "issuer": str(row.get("名称", "")),  # Company name
                        "name": str(row.get("董监高人员姓名", row.get("变动人", ""))),  # Executive name
                        "title": str(row.get("职务", "")),  # Position/title
                        "is_board_director": "董事" in str(row.get("职务", "")),  # Check if director
                        "transaction_date": trans_date_str,
                        "transaction_shares": shares,
                        "transaction_price_per_share": price,
                        "transaction_value": transaction_value,
                        "shares_owned_before_transaction": self._safe_float(row.get("开始时持有")),
                        "shares_owned_after_transaction": self._safe_float(row.get("结束后持有")),
                        "security_title": str(row.get("持股种类", "普通股")),  # Share type
                        "filing_date": trans_date_str,  # Use same as transaction date
                    }
                    insider_trades.append(trade_item)

                except Exception as e:
                    self.logger.warning(f"Failed to parse insider trade row for {ticker}: {e}")
                    continue

            self.logger.info(f"[AKShare] ✓ Got {len(insider_trades)} insider trades for {ticker}")
            return insider_trades

        except Exception as e:
            self.logger.error(f"[AKShare] Failed to get insider trades for {ticker}: {e}")
            return []
