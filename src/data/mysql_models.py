"""
SQLAlchemy models for MySQL cache layer.

These models represent cached data from financial APIs:
- StockPrice: Historical and current stock prices
- FinancialMetric: Financial metrics (PE ratio, market cap, etc.)
- CompanyNewsItem: Company news articles
"""
from sqlalchemy import Column, BigInteger, String, Date, DateTime, DECIMAL, JSON, Integer, Text, Index, Float
from sqlalchemy.sql import func
from src.data.database import Base
import os
from datetime import datetime as dt

# Check if using SQLite to adjust column types
is_sqlite = os.getenv("DATABASE_URL", "sqlite:///./cache.db").startswith("sqlite")


class StockPrice(Base):
    """
    Stock price data cache table.

    Stores OHLCV (Open, High, Low, Close, Volume) data for stocks.
    Historical data (date < today) is永久有效.
    Current data (date = today) is有效 for 1 hour.
    """

    __tablename__ = "stock_prices"

    id = Column(Integer if is_sqlite else BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    time = Column(DateTime, nullable=False)
    open = Column(Float if is_sqlite else DECIMAL(20, 6), nullable=True)
    close = Column(Float if is_sqlite else DECIMAL(20, 6), nullable=True)
    high = Column(Float if is_sqlite else DECIMAL(20, 6), nullable=True)
    low = Column(Float if is_sqlite else DECIMAL(20, 6), nullable=True)
    volume = Column(BigInteger, nullable=True)
    data_source = Column(String(50), nullable=False)  # 'financial_api', 'yfinance', 'akshare', etc.
    created_at = Column(DateTime, default=dt.now if is_sqlite else func.now(), nullable=False)
    updated_at = Column(DateTime, default=dt.now if is_sqlite else func.now(), onupdate=dt.now if is_sqlite else func.now(), nullable=False)

    __table_args__ = (
        Index("idx_stock_prices_ticker_date", "ticker", "date"),
        Index("uk_stock_prices_ticker_time", "ticker", "time", unique=True),
    )

    def __repr__(self):
        return f"<StockPrice(ticker={self.ticker}, date={self.date}, close={self.close})>"


class FinancialMetric(Base):
    """
    Financial metrics cache table.

    Stores company financial metrics like PE ratio, market cap, margins, etc.
    Metrics are typically updated quarterly or annually.
    """

    __tablename__ = "financial_metrics"

    id = Column(Integer if is_sqlite else BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    report_period = Column(Date, nullable=False)
    period = Column(String(20), nullable=False)  # 'ttm', 'quarterly', 'annual'
    currency = Column(String(10), nullable=True)

    # Common financial metrics (denormalized for quick access)
    market_cap = Column(Float if is_sqlite else DECIMAL(20, 2), nullable=True)
    pe_ratio = Column(Float if is_sqlite else DECIMAL(10, 4), nullable=True)
    pb_ratio = Column(Float if is_sqlite else DECIMAL(10, 4), nullable=True)
    ps_ratio = Column(Float if is_sqlite else DECIMAL(10, 4), nullable=True)
    revenue = Column(Float if is_sqlite else DECIMAL(20, 2), nullable=True)
    net_income = Column(Float if is_sqlite else DECIMAL(20, 2), nullable=True)

    # Store full metrics as JSON for flexibility
    metrics_json = Column(JSON, nullable=True)

    data_source = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=dt.now if is_sqlite else func.now(), nullable=False)
    updated_at = Column(DateTime, default=dt.now if is_sqlite else func.now(), onupdate=dt.now if is_sqlite else func.now(), nullable=False)

    __table_args__ = (
        Index("uk_financial_metrics_ticker_period", "ticker", "report_period", "period", unique=True),
    )

    def __repr__(self):
        return f"<FinancialMetric(ticker={self.ticker}, period={self.period}, market_cap={self.market_cap})>"


class CompanyNewsItem(Base):
    """
    Company news cache table.

    Stores news articles related to companies.
    News is cached indefinitely as it's historical data.
    """

    __tablename__ = "company_news"

    id = Column(Integer if is_sqlite else BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    url = Column(String(500), nullable=True)
    source = Column(String(100), nullable=True)
    data_source = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=dt.now if is_sqlite else func.now(), nullable=False)
    updated_at = Column(DateTime, default=dt.now if is_sqlite else func.now(), onupdate=dt.now if is_sqlite else func.now(), nullable=False)

    __table_args__ = (Index("idx_company_news_ticker_date", "ticker", "date"),)

    def __repr__(self):
        return f"<CompanyNewsItem(ticker={self.ticker}, date={self.date}, title={self.title[:50]}...)>"
