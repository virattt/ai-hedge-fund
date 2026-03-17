"""
MySQL Cache Manager for persistent data caching.

Implements dual-layer caching:
- L1: In-memory cache (existing src/data/cache.py)
- L2: MySQL/SQLite persistent cache (this module)

Smart freshness rules:
- Historical data (date < today): 永久有效 (永久缓存)
- Current data (date = today): 1小时内有效
"""
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, date, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.data.database import get_session, init_db, new_session
from src.data.mysql_models import StockPrice, FinancialMetric, CompanyNewsItem
from src.data.models import Price, FinancialMetrics, CompanyNews

logger = logging.getLogger(__name__)

# Global initialization lock and flag to prevent concurrent init_db() calls
_init_lock = threading.Lock()
_db_initialized = False


class MySQLCacheManager:
    """
    MySQL persistent cache manager.

    Handles L2 caching layer for stock prices, financial metrics, and company news.
    Uses thread-local sessions to safely support concurrent access from multiple threads.
    """

    def __init__(self):
        """Initialize the MySQL cache manager."""
        global _db_initialized

        # Initialize database tables if they don't exist (thread-safe)
        with _init_lock:
            if not _db_initialized:
                init_db()
                _db_initialized = True

        logger.info("MySQLCacheManager initialized")

    @property
    def session(self):
        """Get the thread-local session."""
        return get_session()

    @contextmanager
    def _get_session(self):
        """Context manager that provides a fresh session and handles cleanup."""
        session = new_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self):
        """No-op: sessions are thread-local and managed globally."""
        pass

    def __del__(self):
        """Cleanup on deletion."""
        pass

    def save_prices(self, ticker: str, prices: List[Price], data_source: str = "financial_api"):
        """
        Save price data to MySQL cache.

        Args:
            ticker: Stock ticker symbol
            prices: List of Price objects
            data_source: Source of the data (e.g., 'financial_api', 'yfinance')
        """
        if not prices:
            return

        try:
            with self._get_session() as session:
                for price in prices:
                    # Parse datetime
                    time_dt = datetime.fromisoformat(price.time.replace("Z", "+00:00"))
                    date_dt = time_dt.date()

                    # Check if record already exists
                    existing = (
                        session.query(StockPrice)
                        .filter(
                            and_(
                                StockPrice.ticker == ticker,
                                StockPrice.time == time_dt,
                            )
                        )
                        .first()
                    )

                    if existing:
                        # Update existing record
                        existing.open = float(price.open) if price.open else None
                        existing.close = float(price.close) if price.close else None
                        existing.high = float(price.high) if price.high else None
                        existing.low = float(price.low) if price.low else None
                        existing.volume = int(price.volume) if price.volume else None
                        existing.updated_at = datetime.now()
                    else:
                        # Insert new record
                        new_price = StockPrice(
                            ticker=ticker,
                            date=date_dt,
                            time=time_dt,
                            open=float(price.open) if price.open else None,
                            close=float(price.close) if price.close else None,
                            high=float(price.high) if price.high else None,
                            low=float(price.low) if price.low else None,
                            volume=int(price.volume) if price.volume else None,
                            data_source=data_source,
                        )
                        session.add(new_price)

            logger.debug(f"Saved {len(prices)} price records for {ticker}")

        except Exception as e:
            logger.error(f"Failed to save prices for {ticker}: {e}")

    def get_prices(self, ticker: str, start_date: str, end_date: str) -> List[Price]:
        """
        Get price data from MySQL cache.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of Price objects
        """
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

            with self._get_session() as session:
                results = (
                    session.query(StockPrice)
                    .filter(
                        and_(
                            StockPrice.ticker == ticker,
                            StockPrice.date >= start_dt,
                            StockPrice.date <= end_dt,
                        )
                    )
                    .order_by(StockPrice.time)
                    .all()
                )

                # Convert to Price objects (Price model doesn't include ticker)
                prices = [
                    Price(
                        time=result.time.isoformat(),
                        open=float(result.open) if result.open else 0.0,
                        close=float(result.close) if result.close else 0.0,
                        high=float(result.high) if result.high else 0.0,
                        low=float(result.low) if result.low else 0.0,
                        volume=int(result.volume) if result.volume else 0,
                    )
                    for result in results
                ]

            logger.debug(f"Retrieved {len(prices)} price records for {ticker}")
            return prices

        except Exception as e:
            logger.error(f"Failed to get prices for {ticker}: {e}")
            return []

    def is_data_fresh(self, end_date: str, updated_at: Optional[datetime] = None) -> bool:
        """
        Check if cached data is still fresh.

        Rules:
        - Historical data (date < today): Always fresh (永久有效)
        - Current data (date = today): Fresh if updated within 1 hour

        Args:
            end_date: End date of the requested data (YYYY-MM-DD)
            updated_at: When the data was last updated

        Returns:
            True if data is fresh, False otherwise
        """
        try:
            request_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            today = datetime.now().date()

            # Historical data is always fresh
            if request_date < today:
                return True

            # Current data: check if updated within 1 hour
            if request_date == today:
                if updated_at is None:
                    return False

                time_since_update = datetime.now() - updated_at
                return time_since_update.total_seconds() < 3600  # 1 hour

            # Future dates are not fresh (shouldn't happen)
            return False

        except Exception as e:
            logger.error(f"Error checking data freshness: {e}")
            return False

    def save_financial_metrics(self, ticker: str, metrics: List[FinancialMetrics], data_source: str = "financial_api"):
        """
        Save financial metrics to MySQL cache.

        Args:
            ticker: Stock ticker symbol
            metrics: List of FinancialMetrics objects
            data_source: Source of the data
        """
        if not metrics:
            return

        try:
            with self._get_session() as session:
                for metric in metrics:
                    # Parse date - handle empty report_period for non-US stocks
                    if metric.report_period and metric.report_period.strip():
                        try:
                            report_date = datetime.strptime(metric.report_period, "%Y-%m-%d").date()
                        except ValueError:
                            # If date format is invalid, use today's date
                            report_date = datetime.now().date()
                            logger.warning(f"Invalid report_period format for {ticker}: {metric.report_period}, using today's date")
                    else:
                        # For empty report_period (e.g., HK stocks with TTM data), use today's date
                        report_date = datetime.now().date()

                    # Check if record already exists
                    existing = (
                        session.query(FinancialMetric)
                        .filter(
                            and_(
                                FinancialMetric.ticker == ticker,
                                FinancialMetric.report_period == report_date,
                                FinancialMetric.period == metric.period,
                            )
                        )
                        .first()
                    )

                    if existing:
                        # Update existing record
                        existing.market_cap = float(metric.market_cap) if metric.market_cap else None
                        existing.pe_ratio = float(metric.price_to_earnings_ratio) if metric.price_to_earnings_ratio else None
                        existing.pb_ratio = float(metric.price_to_book_ratio) if metric.price_to_book_ratio else None
                        existing.ps_ratio = float(metric.price_to_sales_ratio) if metric.price_to_sales_ratio else None
                        existing.revenue = float(metric.revenue) if hasattr(metric, 'revenue') and metric.revenue else None
                        existing.net_income = float(metric.net_income) if hasattr(metric, 'net_income') and metric.net_income else None
                        existing.metrics_json = metric.model_dump()
                        existing.updated_at = datetime.now()
                    else:
                        # Insert new record
                        new_metric = FinancialMetric(
                            ticker=ticker,
                            report_period=report_date,
                            period=metric.period,
                            currency=metric.currency,
                            market_cap=float(metric.market_cap) if metric.market_cap else None,
                            pe_ratio=float(metric.price_to_earnings_ratio) if metric.price_to_earnings_ratio else None,
                            pb_ratio=float(metric.price_to_book_ratio) if metric.price_to_book_ratio else None,
                            ps_ratio=float(metric.price_to_sales_ratio) if metric.price_to_sales_ratio else None,
                            revenue=float(metric.revenue) if hasattr(metric, 'revenue') and metric.revenue else None,
                            net_income=float(metric.net_income) if hasattr(metric, 'net_income') and metric.net_income else None,
                            metrics_json=metric.model_dump(),  # Store full metrics as JSON
                            data_source=data_source,
                        )
                        session.add(new_metric)

            logger.debug(f"Saved {len(metrics)} financial metric records for {ticker}")

        except Exception as e:
            logger.error(f"Failed to save financial metrics for {ticker}: {e}")

    def get_financial_metrics(self, ticker: str, end_date: str, period: str = "ttm") -> List[FinancialMetrics]:
        """
        Get financial metrics from MySQL cache.

        Args:
            ticker: Stock ticker symbol
            end_date: End date (YYYY-MM-DD)
            period: Period type (ttm, quarterly, annual)

        Returns:
            List of FinancialMetrics objects
        """
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

            with self._get_session() as session:
                results = (
                    session.query(FinancialMetric)
                    .filter(
                        and_(
                            FinancialMetric.ticker == ticker,
                            FinancialMetric.report_period <= end_dt,
                            FinancialMetric.period == period,
                        )
                    )
                    .order_by(FinancialMetric.report_period.desc())
                    .limit(10)
                    .all()
                )

                # Convert to FinancialMetrics objects (inside context to avoid detached instance)
                metrics = []
                for result in results:
                    # Use stored JSON if available, otherwise construct from fields
                    if result.metrics_json:
                        metric = FinancialMetrics(**result.metrics_json)
                    else:
                        metric = FinancialMetrics(
                            ticker=result.ticker,
                            report_period=result.report_period.isoformat(),
                            period=result.period,
                            currency=result.currency or "USD",
                            market_cap=float(result.market_cap) if result.market_cap else None,
                            price_to_earnings_ratio=float(result.pe_ratio) if result.pe_ratio else None,
                            price_to_book_ratio=float(result.pb_ratio) if result.pb_ratio else None,
                            price_to_sales_ratio=float(result.ps_ratio) if result.ps_ratio else None,
                        )
                    metrics.append(metric)

            logger.debug(f"Retrieved {len(metrics)} financial metric records for {ticker}")
            return metrics

        except Exception as e:
            logger.error(f"Failed to get financial metrics for {ticker}: {e}")
            return []

    def save_company_news(self, ticker: str, news_items: List[CompanyNews], data_source: str = "financial_api"):
        """
        Save company news to MySQL cache.

        Args:
            ticker: Stock ticker symbol
            news_items: List of CompanyNews objects
            data_source: Source of the data
        """
        if not news_items:
            return

        try:
            with self._get_session() as session:
                for news in news_items:
                    # Parse datetime
                    news_dt = datetime.fromisoformat(news.date.replace("Z", "+00:00"))

                    # Check if similar record exists (by ticker, date, and title)
                    existing = (
                        session.query(CompanyNewsItem)
                        .filter(
                            and_(
                                CompanyNewsItem.ticker == ticker,
                                CompanyNewsItem.date == news_dt,
                                CompanyNewsItem.title == news.title,
                            )
                        )
                        .first()
                    )

                    if not existing:
                        # Insert new record
                        new_news = CompanyNewsItem(
                            ticker=ticker,
                            date=news_dt,
                            title=news.title if hasattr(news, "title") else None,
                            content=news.content if hasattr(news, "content") else None,
                            url=news.url if hasattr(news, "url") else None,
                            source=news.source if hasattr(news, "source") else None,
                            data_source=data_source,
                        )
                        session.add(new_news)

            logger.debug(f"Saved {len(news_items)} company news records for {ticker}")

        except Exception as e:
            logger.error(f"Failed to save company news for {ticker}: {e}")

    def get_company_news(self, ticker: str, start_date: str, end_date: str) -> List[CompanyNews]:
        """
        Get company news from MySQL cache.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of CompanyNews objects
        """
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)  # Include end date

            with self._get_session() as session:
                results = (
                    session.query(CompanyNewsItem)
                    .filter(
                        and_(
                            CompanyNewsItem.ticker == ticker,
                            CompanyNewsItem.date >= start_dt,
                            CompanyNewsItem.date < end_dt,
                        )
                    )
                    .order_by(CompanyNewsItem.date.desc())
                    .all()
                )

                # Convert to CompanyNews objects (inside context to avoid detached instance)
                news_list = [
                    CompanyNews(
                        ticker=result.ticker,
                        date=result.date.isoformat(),
                        title=result.title or "",
                        author="Unknown",  # CompanyNews model requires author field
                        url=result.url or "",
                        source=result.source or "Unknown",
                        sentiment=None,
                    )
                    for result in results
                ]

            logger.debug(f"Retrieved {len(news_list)} company news records for {ticker}")
            return news_list

        except Exception as e:
            logger.error(f"Failed to get company news for {ticker}: {e}")
            return []
