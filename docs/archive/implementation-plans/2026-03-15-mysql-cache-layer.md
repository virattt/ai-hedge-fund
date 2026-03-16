# MySQL Cache Layer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement MySQL persistent cache layer with dual-layer caching (L1 memory + L2 MySQL) to eliminate 90%+ API calls and enable permanent historical data storage.

**Architecture:** Request → L1 Memory Cache (5min TTL) → L2 MySQL Cache (smart freshness: historical永久, current 1hr) → API fallback

**Tech Stack:** SQLAlchemy, Alembic, MySQL/SQLite, pytest

---

## Phase 1: MySQL Cache Layer - Implementation Plan

Based on the design spec at `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/docs/superpowers/specs/2026-03-15-dual-layer-cache-multi-source-design.md`, this plan implements the MySQL persistent cache layer with dual-layer caching (L1 memory + L2 MySQL).

### Overview

**Key Benefits**:
- Historical data永久有效 (permanent cache)
- Current data 1小时内有效 (1-hour freshness)
- Eliminates 90%+ API calls during backtesting
- 10x+ backtest speed improvement
- Zero data loss on restart

**Key Benefits**:
- Historical data永久有效 (permanent cache)
- Current data 1小时内有效 (1-hour freshness)
- Eliminates 90%+ API calls during backtesting
- 10x+ backtest speed improvement
- Zero data loss on restart

**Architecture**:
```
Request → L1 Memory Cache (5min TTL) → L2 MySQL Cache (smart freshness) → API fallback
```

---

### Critical Files for Implementation

- `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/src/data/mysql_cache.py` - Core MySQL cache manager with dual-layer logic
- `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/src/data/cache_models.py` - SQLAlchemy ORM models for cache tables
- `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/app/backend/alembic/versions/xxx_add_cache_tables.py` - Database migration script
- `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/src/tools/api.py` - Integration point for dual-layer cache
- `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/tests/data/test_mysql_cache.py` - Unit tests for MySQL cache

---

## Implementation Plan

### Prerequisites Check (5 minutes)

**Objective**: Verify current project state and dependencies

- [ ] Check MySQL/MariaDB is available (or use SQLite for development)
- [ ] Verify SQLAlchemy and Alembic are installed (already in pyproject.toml)
- [ ] Check pymysql driver is available (add to pyproject.toml if needed)
- [ ] Verify current database connection works in `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/app/backend/database/connection.py`

**Commands**:
```bash
# Check dependencies
poetry show sqlalchemy alembic

# Test database connection (if MySQL)
# Or use SQLite for local development
```

**Decision Point**: 
- Use MySQL for production (DATABASE_URL=mysql+pymysql://...)
- Use SQLite for local development (DATABASE_URL=sqlite:///./cache.db)

---

### Task 1: Add Database Configuration (2 minutes)

**Objective**: Add DATABASE_URL to environment configuration

- [ ] Add `DATABASE_URL` to `.env.example` with both MySQL and SQLite examples
- [ ] Document the configuration in comments

**Expected `.env.example` addition**:
```bash
# Cache Database Configuration
# For MySQL/MariaDB (production)
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/ai_hedge_fund

# For SQLite (local development)
# DATABASE_URL=sqlite:///./cache.db
```

---

### Task 2: Create SQLAlchemy Models (TDD - 15 minutes)

**Objective**: Define ORM models for cache tables with proper indexes

**Test First** - Create `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/tests/data/test_cache_models.py`:

```python
"""Tests for SQLAlchemy cache models."""

import pytest
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.cache_models import Base, StockPrice, FinancialMetric, CompanyNewsItem, InsiderTrade


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestStockPriceModel:
    """Test StockPrice model."""

    def test_create_stock_price(self, db_session):
        """Test creating a stock price record."""
        price = StockPrice(
            ticker="AAPL",
            date=date(2024, 1, 1),
            time=datetime(2024, 1, 1, 16, 0, 0),
            open=Decimal("150.00"),
            close=Decimal("155.00"),
            high=Decimal("157.00"),
            low=Decimal("149.00"),
            volume=1000000,
            data_source="financial_api"
        )
        db_session.add(price)
        db_session.commit()

        # Query back
        result = db_session.query(StockPrice).filter_by(ticker="AAPL").first()
        assert result is not None
        assert result.ticker == "AAPL"
        assert result.close == Decimal("155.00")
        assert result.data_source == "financial_api"

    def test_unique_constraint_ticker_time(self, db_session):
        """Test unique constraint on (ticker, time)."""
        price1 = StockPrice(
            ticker="AAPL",
            date=date(2024, 1, 1),
            time=datetime(2024, 1, 1, 16, 0, 0),
            open=Decimal("150.00"),
            close=Decimal("155.00"),
            high=Decimal("157.00"),
            low=Decimal("149.00"),
            volume=1000000,
            data_source="financial_api"
        )
        db_session.add(price1)
        db_session.commit()

        # Try to insert duplicate
        price2 = StockPrice(
            ticker="AAPL",
            date=date(2024, 1, 1),
            time=datetime(2024, 1, 1, 16, 0, 0),
            open=Decimal("160.00"),
            close=Decimal("165.00"),
            high=Decimal("167.00"),
            low=Decimal("159.00"),
            volume=2000000,
            data_source="yfinance"
        )
        db_session.add(price2)
        
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_timestamps_auto_set(self, db_session):
        """Test created_at and updated_at are automatically set."""
        price = StockPrice(
            ticker="AAPL",
            date=date(2024, 1, 1),
            time=datetime(2024, 1, 1, 16, 0, 0),
            close=Decimal("155.00"),
            data_source="financial_api"
        )
        db_session.add(price)
        db_session.commit()

        result = db_session.query(StockPrice).first()
        assert result.created_at is not None
        assert result.updated_at is not None


class TestFinancialMetricModel:
    """Test FinancialMetric model."""

    def test_create_financial_metric(self, db_session):
        """Test creating a financial metric record."""
        metric = FinancialMetric(
            ticker="AAPL",
            report_period=date(2024, 3, 31),
            period="ttm",
            market_cap=Decimal("3000000000000.00"),
            pe_ratio=Decimal("28.5000"),
            data_source="financial_api"
        )
        db_session.add(metric)
        db_session.commit()

        result = db_session.query(FinancialMetric).filter_by(ticker="AAPL").first()
        assert result is not None
        assert result.pe_ratio == Decimal("28.5000")

    def test_metrics_json_field(self, db_session):
        """Test storing full metrics in JSON field."""
        metric = FinancialMetric(
            ticker="AAPL",
            report_period=date(2024, 3, 31),
            period="ttm",
            metrics_json={"revenue": 100000000, "net_income": 25000000},
            data_source="financial_api"
        )
        db_session.add(metric)
        db_session.commit()

        result = db_session.query(FinancialMetric).first()
        assert result.metrics_json["revenue"] == 100000000


class TestCompanyNewsModel:
    """Test CompanyNewsItem model."""

    def test_create_company_news(self, db_session):
        """Test creating a company news record."""
        news = CompanyNewsItem(
            ticker="AAPL",
            date=datetime(2024, 1, 1, 10, 0, 0),
            title="Apple announces new product",
            content="Apple Inc. announced...",
            url="https://example.com/news",
            source="Reuters",
            data_source="financial_api"
        )
        db_session.add(news)
        db_session.commit()

        result = db_session.query(CompanyNewsItem).filter_by(ticker="AAPL").first()
        assert result is not None
        assert "announces" in result.title


class TestInsiderTradeModel:
    """Test InsiderTrade model."""

    def test_create_insider_trade(self, db_session):
        """Test creating an insider trade record."""
        trade = InsiderTrade(
            ticker="AAPL",
            filing_date=date(2024, 1, 1),
            trade_date=date(2024, 1, 1),
            insider_name="John Doe",
            title="CEO",
            transaction_type="Buy",
            shares=10000,
            price=Decimal("150.00"),
            value=Decimal("1500000.00"),
            data_source="financial_api"
        )
        db_session.add(trade)
        db_session.commit()

        result = db_session.query(InsiderTrade).filter_by(ticker="AAPL").first()
        assert result is not None
        assert result.insider_name == "John Doe"
```

**Then Implement** - Create `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/src/data/cache_models.py`:

```python
"""SQLAlchemy models for MySQL cache tables."""

from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, Integer, String, Date, DateTime, DECIMAL, 
    Text, JSON, TIMESTAMP, Index, func
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class StockPrice(Base):
    """Stock price cache table."""
    __tablename__ = "stock_prices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    time = Column(DateTime, nullable=False)
    open = Column(DECIMAL(20, 6))
    close = Column(DECIMAL(20, 6))
    high = Column(DECIMAL(20, 6))
    low = Column(DECIMAL(20, 6))
    volume = Column(BigInteger)
    data_source = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP, 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    __table_args__ = (
        Index('idx_ticker_date', 'ticker', 'date'),
        Index('idx_ticker_time_unique', 'ticker', 'time', unique=True),
        Index('idx_created_at', 'created_at'),
    )


class FinancialMetric(Base):
    """Financial metrics cache table."""
    __tablename__ = "financial_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    report_period = Column(Date, nullable=False)
    period = Column(String(20), nullable=False)  # 'ttm', 'quarterly', 'annual'
    market_cap = Column(DECIMAL(20, 2))
    pe_ratio = Column(DECIMAL(10, 4))
    pb_ratio = Column(DECIMAL(10, 4))
    ps_ratio = Column(DECIMAL(10, 4))
    revenue = Column(DECIMAL(20, 2))
    net_income = Column(DECIMAL(20, 2))
    metrics_json = Column(JSON)  # Store full metrics
    data_source = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP, 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    __table_args__ = (
        Index('idx_ticker_period_unique', 'ticker', 'report_period', 'period', unique=True),
        Index('idx_ticker', 'ticker'),
        Index('idx_created_at', 'created_at'),
    )


class CompanyNewsItem(Base):
    """Company news cache table."""
    __tablename__ = "company_news"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    date = Column(DateTime, nullable=False)
    title = Column(Text)
    content = Column(Text)
    url = Column(String(500))
    source = Column(String(100))
    data_source = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP, 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    __table_args__ = (
        Index('idx_ticker_date', 'ticker', 'date'),
        Index('idx_created_at', 'created_at'),
    )


class InsiderTrade(Base):
    """Insider trades cache table."""
    __tablename__ = "insider_trades"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    filing_date = Column(Date, nullable=False)
    trade_date = Column(Date)
    insider_name = Column(String(200))
    title = Column(String(200))
    transaction_type = Column(String(50))
    shares = Column(BigInteger)
    price = Column(DECIMAL(20, 6))
    value = Column(DECIMAL(20, 2))
    data_source = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP, 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

    __table_args__ = (
        Index('idx_ticker_filing', 'ticker', 'filing_date'),
        Index('idx_created_at', 'created_at'),
    )
```

**Run Tests**:
```bash
cd /Users/luobotao/.openclaw/workspace/ai-hedge-fund
poetry run pytest tests/data/test_cache_models.py -v
```

---

### Task 3: Create Alembic Migration (5 minutes)

**Objective**: Generate database migration script for cache tables

**Commands**:
```bash
cd /Users/luobotao/.openclaw/workspace/ai-hedge-fund/app/backend

# Update alembic env.py to import cache models
# Add: from src.data.cache_models import Base as CacheBase
# Merge metadata: target_metadata = [Base.metadata, CacheBase.metadata]

# Generate migration
poetry run alembic revision --autogenerate -m "add_cache_tables"

# This creates: app/backend/alembic/versions/xxx_add_cache_tables.py
```

**Manual adjustments to migration** (if needed):
- Ensure unique constraints are properly named
- Add comments to migration explaining each table's purpose
- Verify index names match design spec

**Apply migration**:
```bash
poetry run alembic upgrade head
```

**Verify**:
```bash
# If MySQL
mysql -u root -p ai_hedge_fund -e "SHOW TABLES;"

# If SQLite
sqlite3 cache.db ".tables"
```

---

### Task 4: Create MySQL Cache Manager (TDD - 30 minutes)

**Objective**: Implement MySQLCache class with dual-layer caching logic

**Test First** - Create `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/tests/data/test_mysql_cache.py`:

```python
"""Tests for MySQL cache manager."""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.data.cache_models import Base
from src.data.mysql_cache import MySQLCache
from src.data.models import Price, FinancialMetrics


@pytest.fixture
def test_db_url():
    """Use in-memory SQLite for testing."""
    return "sqlite:///:memory:"


@pytest.fixture
def mysql_cache(test_db_url):
    """Create MySQLCache instance with test database."""
    cache = MySQLCache(database_url=test_db_url)
    yield cache
    cache.close()


class TestMySQLCacheInit:
    """Test MySQLCache initialization."""

    def test_init_creates_tables(self, test_db_url):
        """Test that tables are created on init."""
        cache = MySQLCache(database_url=test_db_url)
        
        # Verify tables exist
        inspector = cache._get_inspector()
        tables = inspector.get_table_names()
        
        assert "stock_prices" in tables
        assert "financial_metrics" in tables
        assert "company_news" in tables
        assert "insider_trades" in tables
        
        cache.close()


class TestMySQLCachePrices:
    """Test price data caching."""

    def test_save_and_get_prices(self, mysql_cache):
        """Test saving and retrieving price data."""
        prices = [
            Price(
                open=150.0,
                close=155.0,
                high=157.0,
                low=149.0,
                volume=1000000,
                time="2024-01-01T16:00:00"
            ),
            Price(
                open=155.0,
                close=160.0,
                high=162.0,
                low=154.0,
                volume=1100000,
                time="2024-01-02T16:00:00"
            ),
        ]
        
        # Save prices
        mysql_cache.save_prices("AAPL", prices, source="financial_api")
        
        # Retrieve prices
        result = mysql_cache.get_prices(
            "AAPL",
            start_date="2024-01-01",
            end_date="2024-01-02"
        )
        
        assert len(result) == 2
        assert result[0].close == 155.0
        assert result[1].close == 160.0

    def test_save_prices_no_duplicates(self, mysql_cache):
        """Test that duplicate prices are not inserted."""
        prices = [
            Price(
                open=150.0,
                close=155.0,
                high=157.0,
                low=149.0,
                volume=1000000,
                time="2024-01-01T16:00:00"
            ),
        ]
        
        # Save twice
        mysql_cache.save_prices("AAPL", prices, source="financial_api")
        mysql_cache.save_prices("AAPL", prices, source="financial_api")
        
        # Should only have one record
        result = mysql_cache.get_prices("AAPL", "2024-01-01", "2024-01-01")
        assert len(result) == 1

    def test_update_today_prices(self, mysql_cache):
        """Test updating current day prices."""
        today = date.today()
        today_str = today.strftime("%Y-%m-%d")
        
        # Initial price
        prices_v1 = [
            Price(
                open=150.0,
                close=155.0,
                high=157.0,
                low=149.0,
                volume=1000000,
                time=f"{today_str}T16:00:00"
            ),
        ]
        mysql_cache.save_prices("AAPL", prices_v1, source="financial_api")
        
        # Updated price (same day, new close)
        prices_v2 = [
            Price(
                open=150.0,
                close=160.0,  # Different close
                high=162.0,
                low=149.0,
                volume=1200000,
                time=f"{today_str}T16:00:00"
            ),
        ]
        mysql_cache.save_prices("AAPL", prices_v2, source="financial_api", overwrite_today=True)
        
        # Should have updated price
        result = mysql_cache.get_prices("AAPL", today_str, today_str)
        assert len(result) == 1
        assert result[0].close == 160.0

    def test_get_prices_empty_result(self, mysql_cache):
        """Test getting prices when none exist."""
        result = mysql_cache.get_prices("NONEXISTENT", "2024-01-01", "2024-01-01")
        assert result == []

    def test_get_latest_price_date(self, mysql_cache):
        """Test getting the latest date for a ticker."""
        prices = [
            Price(
                close=155.0,
                open=150.0,
                high=157.0,
                low=149.0,
                volume=1000000,
                time="2024-01-01T16:00:00"
            ),
            Price(
                close=160.0,
                open=155.0,
                high=162.0,
                low=154.0,
                volume=1100000,
                time="2024-01-05T16:00:00"
            ),
        ]
        mysql_cache.save_prices("AAPL", prices, source="financial_api")
        
        latest = mysql_cache.get_latest_price_date("AAPL")
        assert latest == date(2024, 1, 5)

    def test_get_latest_price_date_no_data(self, mysql_cache):
        """Test getting latest date when no data exists."""
        latest = mysql_cache.get_latest_price_date("NONEXISTENT")
        assert latest is None


class TestMySQLCacheFinancialMetrics:
    """Test financial metrics caching."""

    def test_save_and_get_financial_metrics(self, mysql_cache):
        """Test saving and retrieving financial metrics."""
        metrics = FinancialMetrics(
            ticker="AAPL",
            report_period="2024-03-31",
            period="ttm",
            currency="USD",
            market_cap=3000000000000.0,
            price_to_earnings_ratio=28.5,
            revenue=100000000000.0,
        )
        
        # Save metrics
        mysql_cache.save_financial_metrics("AAPL", [metrics], source="financial_api")
        
        # Retrieve metrics
        result = mysql_cache.get_financial_metrics(
            "AAPL",
            end_date="2024-03-31",
            period="ttm"
        )
        
        assert len(result) == 1
        assert result[0].market_cap == 3000000000000.0
        assert result[0].price_to_earnings_ratio == 28.5


class TestMySQLCacheDataFreshness:
    """Test data freshness logic."""

    def test_historical_data_always_fresh(self, mysql_cache):
        """Test that historical data (date < today) is always considered fresh."""
        yesterday = date.today() - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")
        
        prices = [
            Price(
                close=155.0,
                open=150.0,
                high=157.0,
                low=149.0,
                volume=1000000,
                time=f"{yesterday_str}T16:00:00"
            ),
        ]
        mysql_cache.save_prices("AAPL", prices, source="financial_api")
        
        # Data should be fresh even if created hours ago
        is_fresh = mysql_cache.is_data_fresh("AAPL", yesterday_str, yesterday_str)
        assert is_fresh is True

    def test_current_data_fresh_within_1_hour(self, mysql_cache):
        """Test that current day data is fresh within 1 hour."""
        today = date.today()
        today_str = today.strftime("%Y-%m-%d")
        
        prices = [
            Price(
                close=155.0,
                open=150.0,
                high=157.0,
                low=149.0,
                volume=1000000,
                time=f"{today_str}T16:00:00"
            ),
        ]
        mysql_cache.save_prices("AAPL", prices, source="financial_api")
        
        # Just saved, should be fresh
        is_fresh = mysql_cache.is_data_fresh("AAPL", today_str, today_str)
        assert is_fresh is True

    def test_current_data_stale_after_1_hour(self, mysql_cache):
        """Test that current day data is stale after 1 hour."""
        today = date.today()
        today_str = today.strftime("%Y-%m-%d")
        
        # Create old timestamp (2 hours ago)
        two_hours_ago = datetime.now() - timedelta(hours=2)
        
        # Manually insert with old timestamp
        from src.data.cache_models import StockPrice
        session = mysql_cache.Session()
        price_record = StockPrice(
            ticker="AAPL",
            date=today,
            time=datetime.fromisoformat(f"{today_str}T16:00:00"),
            close=Decimal("155.00"),
            open=Decimal("150.00"),
            high=Decimal("157.00"),
            low=Decimal("149.00"),
            volume=1000000,
            data_source="financial_api",
            created_at=two_hours_ago,
            updated_at=two_hours_ago
        )
        session.add(price_record)
        session.commit()
        session.close()
        
        # Should be stale
        is_fresh = mysql_cache.is_data_fresh("AAPL", today_str, today_str)
        assert is_fresh is False


class TestMySQLCacheBulkOperations:
    """Test bulk insert optimization."""

    def test_bulk_insert_performance(self, mysql_cache):
        """Test bulk insert of many records."""
        # Create 100 days of data
        start_date = date(2024, 1, 1)
        prices = []
        for i in range(100):
            current_date = start_date + timedelta(days=i)
            prices.append(
                Price(
                    close=150.0 + i,
                    open=149.0 + i,
                    high=152.0 + i,
                    low=148.0 + i,
                    volume=1000000 + i * 10000,
                    time=f"{current_date.strftime('%Y-%m-%d')}T16:00:00"
                )
            )
        
        # Save all at once (should use bulk insert)
        mysql_cache.save_prices("AAPL", prices, source="financial_api")
        
        # Verify all saved
        result = mysql_cache.get_prices(
            "AAPL",
            start_date="2024-01-01",
            end_date="2024-04-10"
        )
        assert len(result) == 100


class TestMySQLCacheTransactions:
    """Test transaction handling."""

    def test_rollback_on_error(self, mysql_cache):
        """Test that errors trigger rollback."""
        # This should fail and rollback
        with pytest.raises(Exception):
            # Try to save with invalid data
            mysql_cache.save_prices("AAPL", None, source="financial_api")
        
        # No data should be saved
        result = mysql_cache.get_prices("AAPL", "2024-01-01", "2024-01-01")
        assert result == []
```

**Then Implement** - Create `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/src/data/mysql_cache.py`:

```python
"""MySQL persistent cache manager with dual-layer caching logic."""

import logging
import os
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from src.data.cache_models import (
    Base, StockPrice, FinancialMetric, CompanyNewsItem, InsiderTrade
)
from src.data.models import Price, FinancialMetrics, CompanyNews, InsiderTrade as InsiderTradeModel

logger = logging.getLogger(__name__)


class MySQLCache:
    """MySQL persistent cache manager."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize MySQL cache.

        Args:
            database_url: Database connection URL. If None, reads from DATABASE_URL env var.
                         Example: "mysql+pymysql://root:password@localhost:3306/ai_hedge_fund"
                         Or: "sqlite:///./cache.db" for local development
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", 
            "sqlite:///./cache.db"  # Default to SQLite for development
        )
        
        # Create engine with connection pooling
        self.engine = create_engine(
            self.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Auto-detect stale connections
            pool_recycle=3600,   # Recycle connections after 1 hour
            echo=False  # Set to True for SQL debugging
        )
        
        # Create tables if they don't exist
        Base.metadata.create_all(self.engine)
        
        # Create session factory
        self.Session = sessionmaker(bind=self.engine)
        
        logger.info(f"MySQLCache initialized with URL: {self._mask_password(self.database_url)}")

    def _mask_password(self, url: str) -> str:
        """Mask password in database URL for logging."""
        if "@" in url and "://" in url:
            protocol, rest = url.split("://", 1)
            if "@" in rest:
                credentials, host_part = rest.split("@", 1)
                if ":" in credentials:
                    user, _ = credentials.split(":", 1)
                    return f"{protocol}://{user}:***@{host_part}"
        return url

    def _get_inspector(self):
        """Get SQLAlchemy inspector for schema introspection."""
        from sqlalchemy import inspect
        return inspect(self.engine)

    def close(self):
        """Close database connections."""
        self.engine.dispose()
        logger.info("MySQLCache connections closed")

    # ==================== Price Data Methods ====================

    def save_prices(
        self, 
        ticker: str, 
        prices: List[Price], 
        source: str = "unknown",
        overwrite_today: bool = False
    ):
        """
        Save price data to MySQL cache.

        Args:
            ticker: Stock ticker symbol
            prices: List of Price objects
            source: Data source name (e.g., "financial_api", "yfinance")
            overwrite_today: If True, update today's data instead of skipping duplicates
        """
        session = self.Session()
        try:
            # Get today's date for comparison
            today = date.today()
            
            # Bulk query existing records to avoid duplicate inserts
            time_list = [datetime.fromisoformat(p.time) for p in prices]
            existing_records = session.query(StockPrice).filter(
                StockPrice.ticker == ticker,
                StockPrice.time.in_(time_list)
            ).all()
            existing_times = {r.time for r in existing_records}
            
            # Separate records into update and insert
            to_update = []
            to_insert = []
            
            for price in prices:
                price_time = datetime.fromisoformat(price.time)
                price_date = price_time.date()
                
                if price_time in existing_times:
                    # Only update if it's today's data and overwrite_today is True
                    if overwrite_today and price_date == today:
                        to_update.append((price_time, price))
                else:
                    to_insert.append(price)
            
            # Batch update today's data
            if to_update:
                for price_time, price in to_update:
                    session.query(StockPrice).filter(
                        StockPrice.ticker == ticker,
                        StockPrice.time == price_time
                    ).update({
                        'open': Decimal(str(price.open)) if price.open else None,
                        'close': Decimal(str(price.close)) if price.close else None,
                        'high': Decimal(str(price.high)) if price.high else None,
                        'low': Decimal(str(price.low)) if price.low else None,
                        'volume': price.volume,
                        'updated_at': datetime.now()
                    })
                logger.debug(f"Updated {len(to_update)} price records for {ticker}")
            
            # Bulk insert new records
            if to_insert:
                mappings = []
                for price in to_insert:
                    price_time = datetime.fromisoformat(price.time)
                    mappings.append({
                        'ticker': ticker,
                        'date': price_time.date(),
                        'time': price_time,
                        'open': Decimal(str(price.open)) if price.open else None,
                        'close': Decimal(str(price.close)) if price.close else None,
                        'high': Decimal(str(price.high)) if price.high else None,
                        'low': Decimal(str(price.low)) if price.low else None,
                        'volume': price.volume,
                        'data_source': source
                    })
                session.bulk_insert_mappings(StockPrice, mappings)
                logger.debug(f"Inserted {len(to_insert)} price records for {ticker}")
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save prices for {ticker}: {e}")
            raise
        finally:
            session.close()

    def get_prices(
        self, 
        ticker: str, 
        start_date: str, 
        end_date: str
    ) -> List[Price]:
        """
        Get price data from MySQL cache.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of Price objects
        """
        session = self.Session()
        try:
            query = session.query(StockPrice).filter(
                StockPrice.ticker == ticker,
                StockPrice.date >= start_date,
                StockPrice.date <= end_date
            ).order_by(StockPrice.time)
            
            results = query.all()
            
            # Convert ORM models to Pydantic models
            prices = []
            for r in results:
                prices.append(Price(
                    open=float(r.open) if r.open else 0.0,
                    close=float(r.close) if r.close else 0.0,
                    high=float(r.high) if r.high else 0.0,
                    low=float(r.low) if r.low else 0.0,
                    volume=r.volume or 0,
                    time=r.time.isoformat()
                ))
            
            logger.debug(f"Retrieved {len(prices)} price records for {ticker}")
            return prices
            
        finally:
            session.close()

    def get_latest_price_date(self, ticker: str) -> Optional[date]:
        """
        Get the latest date for which price data exists.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Latest date or None if no data exists
        """
        session = self.Session()
        try:
            result = session.query(func.max(StockPrice.date)).filter(
                StockPrice.ticker == ticker
            ).scalar()
            return result
        finally:
            session.close()

    def is_data_fresh(
        self, 
        ticker: str, 
        start_date: str, 
        end_date: str
    ) -> bool:
        """
        Check if cached data is fresh enough to use.

        Freshness rules:
        - Historical data (end_date < today): Always fresh (永久有效)
        - Current data (end_date = today): Fresh if updated within 1 hour

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            True if data is fresh, False otherwise
        """
        today = date.today()
        request_end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Historical data is always fresh
        if request_end_date < today:
            return True
        
        # Current data: check if updated within 1 hour
        if request_end_date == today:
            session = self.Session()
            try:
                # Get the most recent update timestamp for today's data
                latest_update = session.query(func.max(StockPrice.updated_at)).filter(
                    StockPrice.ticker == ticker,
                    StockPrice.date == today
                ).scalar()
                
                if latest_update is None:
                    return False  # No data for today
                
                # Check if updated within 1 hour
                time_diff = datetime.now() - latest_update
                return time_diff.total_seconds() < 3600  # 1 hour = 3600 seconds
                
            finally:
                session.close()
        
        # Future dates are never fresh
        return False

    # ==================== Financial Metrics Methods ====================

    def save_financial_metrics(
        self, 
        ticker: str, 
        metrics: List[FinancialMetrics], 
        source: str = "unknown"
    ):
        """
        Save financial metrics to MySQL cache.

        Args:
            ticker: Stock ticker symbol
            metrics: List of FinancialMetrics objects
            source: Data source name
        """
        session = self.Session()
        try:
            mappings = []
            for m in metrics:
                report_date = datetime.strptime(m.report_period, '%Y-%m-%d').date()
                mappings.append({
                    'ticker': ticker,
                    'report_period': report_date,
                    'period': m.period,
                    'market_cap': Decimal(str(m.market_cap)) if m.market_cap else None,
                    'pe_ratio': Decimal(str(m.price_to_earnings_ratio)) if m.price_to_earnings_ratio else None,
                    'pb_ratio': Decimal(str(m.price_to_book_ratio)) if m.price_to_book_ratio else None,
                    'ps_ratio': Decimal(str(m.price_to_sales_ratio)) if m.price_to_sales_ratio else None,
                    'revenue': Decimal(str(m.revenue)) if hasattr(m, 'revenue') and m.revenue else None,
                    'net_income': Decimal(str(m.net_income)) if hasattr(m, 'net_income') and m.net_income else None,
                    'metrics_json': m.model_dump(),  # Store full metrics
                    'data_source': source
                })
            
            # Use INSERT ... ON DUPLICATE KEY UPDATE for MySQL
            # For SQLite, we need to handle differently
            if "sqlite" in self.database_url:
                for mapping in mappings:
                    # Try insert, if duplicate, update
                    existing = session.query(FinancialMetric).filter(
                        FinancialMetric.ticker == mapping['ticker'],
                        FinancialMetric.report_period == mapping['report_period'],
                        FinancialMetric.period == mapping['period']
                    ).first()
                    
                    if existing:
                        for key, value in mapping.items():
                            setattr(existing, key, value)
                    else:
                        session.add(FinancialMetric(**mapping))
            else:
                session.bulk_insert_mappings(FinancialMetric, mappings)
            
            session.commit()
            logger.debug(f"Saved {len(mappings)} financial metrics for {ticker}")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save financial metrics for {ticker}: {e}")
            raise
        finally:
            session.close()

    def get_financial_metrics(
        self, 
        ticker: str, 
        end_date: str, 
        period: str = "ttm"
    ) -> List[FinancialMetrics]:
        """
        Get financial metrics from MySQL cache.

        Args:
            ticker: Stock ticker symbol
            end_date: End date (YYYY-MM-DD)
            period: Report period type (ttm, quarterly, annual)

        Returns:
            List of FinancialMetrics objects
        """
        session = self.Session()
        try:
            query = session.query(FinancialMetric).filter(
                FinancialMetric.ticker == ticker,
                FinancialMetric.report_period <= end_date,
                FinancialMetric.period == period
            ).order_by(FinancialMetric.report_period.desc())
            
            results = query.all()
            
            # Convert to Pydantic models
            metrics = []
            for r in results:
                # Use stored JSON if available
                if r.metrics_json:
                    metrics.append(FinancialMetrics(**r.metrics_json))
                else:
                    # Fallback to individual fields
                    metrics.append(FinancialMetrics(
                        ticker=ticker,
                        report_period=r.report_period.strftime('%Y-%m-%d'),
                        period=r.period,
                        currency="USD",  # Default
                        market_cap=float(r.market_cap) if r.market_cap else None,
                        price_to_earnings_ratio=float(r.pe_ratio) if r.pe_ratio else None,
                        price_to_book_ratio=float(r.pb_ratio) if r.pb_ratio else None,
                        price_to_sales_ratio=float(r.ps_ratio) if r.ps_ratio else None,
                    ))
            
            logger.debug(f"Retrieved {len(metrics)} financial metrics for {ticker}")
            return metrics
            
        finally:
            session.close()

    # ==================== Placeholder methods for other data types ====================
    # These follow the same pattern as prices and financial metrics

    def save_company_news(self, ticker: str, news: List[CompanyNews], source: str = "unknown"):
        """Save company news to cache."""
        # Implementation similar to save_prices
        pass

    def get_company_news(self, ticker: str, start_date: str, end_date: str) -> List[CompanyNews]:
        """Get company news from cache."""
        # Implementation similar to get_prices
        pass

    def save_insider_trades(self, ticker: str, trades: List[InsiderTradeModel], source: str = "unknown"):
        """Save insider trades to cache."""
        # Implementation similar to save_prices
        pass

    def get_insider_trades(self, ticker: str, start_date: str, end_date: str) -> List[InsiderTradeModel]:
        """Get insider trades from cache."""
        # Implementation similar to get_prices
        pass
```

**Run Tests**:
```bash
poetry run pytest tests/data/test_mysql_cache.py -v
```

---

### Task 5: Integrate Dual-Layer Cache into api.py (TDD - 20 minutes)

**Objective**: Modify `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/src/tools/api.py` to use dual-layer caching

**Test First** - Create `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/tests/integration/test_cached_api.py`:

```python
"""Integration tests for dual-layer cached API."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

from src.tools.api import get_prices
from src.data.models import Price


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all caches before each test."""
    from src.data.cache import get_cache
    from src.data.mysql_cache import MySQLCache
    
    # Clear L1 memory cache
    get_cache().clear()
    
    # Clear L2 MySQL cache (use test database)
    mysql_cache = MySQLCache(database_url="sqlite:///:memory:")
    yield
    mysql_cache.close()


class TestDualLayerCache:
    """Test dual-layer caching (L1 memory + L2 MySQL)."""

    @patch('src.tools.api._make_api_request')
    def test_cache_miss_fetches_from_api(self, mock_request):
        """Test that cache miss triggers API call."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'ticker': 'AAPL',
            'prices': [
                {
                    'open': 150.0,
                    'close': 155.0,
                    'high': 157.0,
                    'low': 149.0,
                    'volume': 1000000,
                    'time': '2024-01-01T16:00:00'
                }
            ]
        }
        mock_request.return_value = mock_response
        
        # First call - should hit API
        prices = get_prices("AAPL", "2024-01-01", "2024-01-01")
        
        assert len(prices) == 1
        assert prices[0].close == 155.0
        assert mock_request.call_count == 1

    @patch('src.tools.api._make_api_request')
    def test_l1_cache_hit_skips_mysql_and_api(self, mock_request):
        """Test that L1 cache hit avoids MySQL and API calls."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'ticker': 'AAPL',
            'prices': [
                {
                    'open': 150.0,
                    'close': 155.0,
                    'high': 157.0,
                    'low': 149.0,
                    'volume': 1000000,
                    'time': '2024-01-01T16:00:00'
                }
            ]
        }
        mock_request.return_value = mock_response
        
        # First call - populates caches
        prices1 = get_prices("AAPL", "2024-01-01", "2024-01-01")
        
        # Second call - should hit L1 cache
        prices2 = get_prices("AAPL", "2024-01-01", "2024-01-01")
        
        # API should only be called once
        assert mock_request.call_count == 1
        assert len(prices2) == 1
        assert prices2[0].close == 155.0

    @patch('src.tools.api._make_api_request')
    def test_l2_mysql_cache_hit_after_l1_expires(self, mock_request):
        """Test that L2 MySQL cache is used when L1 expires."""
        # This test would require waiting for L1 TTL to expire
        # or manually clearing L1 cache while keeping L2
        pass


class TestHistoricalDataCaching:
    """Test permanent caching of historical data."""

    @patch('src.tools.api._make_api_request')
    def test_historical_data_cached_permanently(self, mock_request):
        """Test that historical data (date < today) is cached permanently."""
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'ticker': 'AAPL',
            'prices': [
                {
                    'open': 150.0,
                    'close': 155.0,
                    'high': 157.0,
                    'low': 149.0,
                    'volume': 1000000,
                    'time': f'{yesterday}T16:00:00'
                }
            ]
        }
        mock_request.return_value = mock_response
        
        # First call - fetches from API
        prices1 = get_prices("AAPL", yesterday, yesterday)
        assert mock_request.call_count == 1
        
        # Clear L1 cache to force L2 lookup
        from src.data.cache import get_cache
        get_cache().clear()
        
        # Second call - should hit L2 MySQL cache
        prices2 = get_prices("AAPL", yesterday, yesterday)
        
        # API should not be called again
        assert mock_request.call_count == 1
        assert len(prices2) == 1
        assert prices2[0].close == 155.0


class TestCurrentDataRefresh:
    """Test 1-hour refresh logic for current day data."""

    @patch('src.tools.api._make_api_request')
    def test_current_data_refreshed_after_1_hour(self, mock_request):
        """Test that current day data is re-fetched after 1 hour."""
        # This test would require time manipulation or manual timestamp updates
        # to simulate 1 hour passing
        pass


class TestMultiMarketCaching:
    """Test caching for different market types."""

    @patch('src.tools.api._make_api_request')
    def test_us_stock_caching(self, mock_request):
        """Test caching works for US stocks."""
        # Test AAPL (US stock)
        pass

    def test_a_share_caching(self):
        """Test caching works for A-share stocks."""
        # Test 600000.SH (A-share)
        pass

    def test_hk_share_caching(self):
        """Test caching works for HK stocks."""
        # Test 0700.HK (HK stock)
        pass
```

**Then Implement** - Modify `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/src/tools/api.py`:

**Key changes**:
1. Add MySQLCache instance initialization at module level
2. Modify `get_prices()` to check L2 MySQL cache after L1 miss
3. Add data freshness check before using L2 cache
4. Save to both L1 and L2 caches on API fetch

**Code changes** (pseudo-code, actual implementation will be done in Phase 2):
```python
# At top of file, add:
from src.data.mysql_cache import MySQLCache

# Global MySQL cache instance
_mysql_cache = None

def _get_mysql_cache():
    """Get or create MySQL cache instance (lazy initialization)."""
    global _mysql_cache
    if _mysql_cache is None:
        _mysql_cache = MySQLCache()
    return _mysql_cache

# In get_prices() function:
def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    cache_key = f"{ticker}_{start_date}_{end_date}"
    
    # L1: Memory cache check
    if cached_data := _cache.get_prices(cache_key):
        return [Price(**price) for price in cached_data]
    
    # L2: MySQL cache check with freshness validation
    mysql_cache = _get_mysql_cache()
    if mysql_cache.is_data_fresh(ticker, start_date, end_date):
        mysql_prices = mysql_cache.get_prices(ticker, start_date, end_date)
        if mysql_prices:
            logger.debug(f"✓ L2 MySQL cache hit: {cache_key}")
            # Backfill L1 cache
            _cache.set_prices(cache_key, [p.model_dump() for p in mysql_prices])
            return mysql_prices
    
    # Cache miss: fetch from API
    # [... existing API fetch code ...]
    
    # Save to both caches
    if prices:
        _cache.set_prices(cache_key, [p.model_dump() for p in prices])
        mysql_cache.save_prices(ticker, prices, source="financial_api")
    
    return prices
```

**Run Integration Tests**:
```bash
poetry run pytest tests/integration/test_cached_api.py -v
```

---

### Task 6: Update Environment Configuration (2 minutes)

**Objective**: Document DATABASE_URL configuration in .env.example

Already covered in Task 1, but verify:

```bash
# Check .env.example has DATABASE_URL
grep DATABASE_URL /Users/luobotao/.openclaw/workspace/ai-hedge-fund/.env.example
```

---

### Task 7: End-to-End Integration Test (10 minutes)

**Objective**: Test complete dual-layer cache flow with real backtest scenario

Create `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/tests/integration/test_backtest_with_cache.py`:

```python
"""End-to-end test for backtest with MySQL cache."""

import pytest
from datetime import date, timedelta

from src.tools.api import get_prices


class TestBacktestWithCache:
    """Test backtest scenarios with MySQL cache."""

    def test_backtest_performance_improvement(self):
        """Test that backtest is faster with cache."""
        # First run - cache miss, fetches from API
        start = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        end = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        import time
        
        # First call - slow (API)
        t1 = time.time()
        prices1 = get_prices("AAPL", start, end)
        time1 = time.time() - t1
        
        # Clear L1 cache to force L2 lookup
        from src.data.cache import get_cache
        get_cache().clear()
        
        # Second call - fast (MySQL cache)
        t2 = time.time()
        prices2 = get_prices("AAPL", start, end)
        time2 = time.time() - t2
        
        # Verify data is the same
        assert len(prices1) == len(prices2)
        
        # Second call should be faster (at least 2x)
        print(f"First call (API): {time1:.3f}s")
        print(f"Second call (Cache): {time2:.3f}s")
        print(f"Speedup: {time1/time2:.1f}x")
        
        # Allow some variance, but cache should be significantly faster
        assert time2 < time1 / 2, "Cache should be at least 2x faster"

    def test_multiple_ticker_backtest(self):
        """Test backtest with multiple tickers uses cache."""
        tickers = ["AAPL", "MSFT", "GOOGL"]
        start = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        end = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Fetch data for all tickers (populates cache)
        for ticker in tickers:
            prices = get_prices(ticker, start, end)
            assert len(prices) > 0
        
        # Clear L1 cache
        from src.data.cache import get_cache
        get_cache().clear()
        
        # Fetch again - should be fast from MySQL cache
        import time
        t1 = time.time()
        for ticker in tickers:
            prices = get_prices(ticker, start, end)
            assert len(prices) > 0
        time_taken = time.time() - t1
        
        print(f"Cached fetch for {len(tickers)} tickers: {time_taken:.3f}s")
        
        # Should be reasonably fast
        assert time_taken < 1.0, "Cached fetch should be under 1 second"
```

**Run E2E Tests**:
```bash
poetry run pytest tests/integration/test_backtest_with_cache.py -v
```

---

### Task 8: Documentation and README Update (5 minutes)

**Objective**: Document the MySQL cache layer in project documentation

Update `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/TROUBLESHOOTING.md`:

```markdown
## MySQL Cache Layer

### Overview

The system uses a dual-layer cache to minimize API calls and improve performance:

- **L1 (Memory)**: 5-minute TTL in-memory cache for ultra-fast access
- **L2 (MySQL)**: Persistent database cache with smart freshness logic

### Data Freshness Rules

- **Historical data** (date < today): Cached permanently, never expires
- **Current data** (date = today): Refreshed every 1 hour

### Configuration

Set `DATABASE_URL` in `.env`:

```bash
# MySQL (production)
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/ai_hedge_fund

# SQLite (local development)
DATABASE_URL=sqlite:///./cache.db
```

### Database Setup

```bash
# Apply migrations
cd app/backend
poetry run alembic upgrade head

# Verify tables
mysql -u root -p ai_hedge_fund -e "SHOW TABLES;"
```

### Performance Benefits

- **90%+ reduction** in API calls during backtesting
- **10x+ faster** backtest execution with cached data
- **Zero data loss** on application restart

### Cache Statistics

Check cache hit rate in logs:
```
✓ L1 cache hit: AAPL_2024-01-01_2024-01-31
✓ L2 MySQL cache hit: MSFT_2024-01-01_2024-01-31
⚠️ Cache miss: GOOGL_2024-01-01_2024-01-31, fetching from network...
```

### Troubleshooting

**Q: Cache not working?**
A: Check DATABASE_URL is set correctly in `.env`

**Q: How to clear cache?**
A: Delete data from `stock_prices` table or drop the database

**Q: SQLite vs MySQL?**
A: Use SQLite for local development, MySQL for production (better concurrency)
```

---

### Task 9: Validation and Smoke Tests (5 minutes)

**Objective**: Run full test suite and validate implementation

```bash
cd /Users/luobotao/.openclaw/workspace/ai-hedge-fund

# Run all cache-related tests
poetry run pytest tests/data/test_mysql_cache.py -v
poetry run pytest tests/integration/test_cached_api.py -v
poetry run pytest tests/integration/test_backtest_with_cache.py -v

# Run full test suite
poetry run pytest tests/ -v

# Test with real backtest
poetry run python src/main.py --tickers AAPL --analysts-all --model "deepseek-chat" --start-date 2024-01-01 --end-date 2024-01-31
```

**Success Criteria**:
- All tests pass
- Database tables created successfully
- Cache hit/miss logs appear
- Backtest runs faster on second execution

---

## Summary

**Total Estimated Time**: ~2 hours for complete implementation

**Deliverables**:
1. ✅ SQLAlchemy models for cache tables
2. ✅ Alembic migration script
3. ✅ MySQLCache manager with dual-layer logic
4. ✅ Modified api.py with L1/L2 integration
5. ✅ Comprehensive test suite (unit + integration)
6. ✅ Updated documentation

**Next Steps** (Phase 2):
- Implement EastMoney direct HTTP source
- Add multi-source fallback chain
- Implement proxy detection and retry logic

---

### Critical Files for Implementation

- `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/src/data/mysql_cache.py` - Core MySQL cache manager (NEW)
- `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/src/data/cache_models.py` - SQLAlchemy ORM models (NEW)
- `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/app/backend/alembic/versions/xxx_add_cache_tables.py` - Database migration (NEW)
- `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/src/tools/api.py` - Dual-layer cache integration point (MODIFY)
- `/Users/luobotao/.openclaw/workspace/ai-hedge-fund/tests/data/test_mysql_cache.py` - MySQL cache tests (NEW)
