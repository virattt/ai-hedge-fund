"""
Tests for MySQL cache models.

Tests the SQLAlchemy models for stock prices, financial metrics, and company news.
"""
import pytest
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.data.database import Base
from src.data.mysql_models import StockPrice, FinancialMetric, CompanyNewsItem


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestStockPrice:
    """Tests for StockPrice model."""

    def test_create_stock_price(self, db_session):
        """Test creating a stock price record."""
        price = StockPrice(
            ticker="AAPL",
            date=date(2024, 1, 1),
            time=datetime(2024, 1, 1, 16, 0, 0),
            open=150.0,
            close=152.5,
            high=153.0,
            low=149.5,
            volume=1000000,
            data_source="test_source",
        )
        db_session.add(price)
        db_session.commit()

        assert price.id is not None
        assert price.ticker == "AAPL"
        assert price.close == 152.5

    def test_unique_constraint_ticker_time(self, db_session):
        """Test that (ticker, time) combination is unique."""
        price1 = StockPrice(
            ticker="AAPL",
            date=date(2024, 1, 1),
            time=datetime(2024, 1, 1, 16, 0, 0),
            open=150.0,
            close=152.5,
            high=153.0,
            low=149.5,
            volume=1000000,
            data_source="test_source",
        )
        db_session.add(price1)
        db_session.commit()

        # Try to add duplicate
        price2 = StockPrice(
            ticker="AAPL",
            date=date(2024, 1, 1),
            time=datetime(2024, 1, 1, 16, 0, 0),
            open=151.0,
            close=153.0,
            high=154.0,
            low=150.0,
            volume=2000000,
            data_source="test_source",
        )
        db_session.add(price2)

        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            db_session.commit()

    def test_query_by_ticker_and_date_range(self, db_session):
        """Test querying prices by ticker and date range."""
        # Add multiple price records
        prices = [
            StockPrice(
                ticker="AAPL",
                date=date(2024, 1, i),
                time=datetime(2024, 1, i, 16, 0, 0),
                open=150.0 + i,
                close=152.5 + i,
                high=153.0 + i,
                low=149.5 + i,
                volume=1000000 + i,
                data_source="test_source",
            )
            for i in range(1, 6)
        ]
        db_session.add_all(prices)
        db_session.commit()

        # Query date range
        results = (
            db_session.query(StockPrice)
            .filter(
                StockPrice.ticker == "AAPL",
                StockPrice.date >= date(2024, 1, 2),
                StockPrice.date <= date(2024, 1, 4),
            )
            .all()
        )

        assert len(results) == 3
        assert results[0].date == date(2024, 1, 2)
        assert results[-1].date == date(2024, 1, 4)

    def test_timestamps(self, db_session):
        """Test that created_at and updated_at timestamps are set."""
        price = StockPrice(
            ticker="AAPL",
            date=date(2024, 1, 1),
            time=datetime(2024, 1, 1, 16, 0, 0),
            open=150.0,
            close=152.5,
            high=153.0,
            low=149.5,
            volume=1000000,
            data_source="test_source",
        )
        db_session.add(price)
        db_session.commit()

        assert price.created_at is not None
        assert price.updated_at is not None


class TestFinancialMetric:
    """Tests for FinancialMetric model."""

    def test_create_financial_metric(self, db_session):
        """Test creating a financial metric record."""
        metric = FinancialMetric(
            ticker="AAPL",
            report_period=date(2024, 1, 1),
            period="ttm",
            currency="USD",
            market_cap=3000000000000.0,
            pe_ratio=25.5,
            data_source="test_source",
        )
        db_session.add(metric)
        db_session.commit()

        assert metric.id is not None
        assert metric.ticker == "AAPL"
        assert metric.market_cap == 3000000000000.0

    def test_unique_constraint_ticker_period(self, db_session):
        """Test that (ticker, report_period, period) combination is unique."""
        metric1 = FinancialMetric(
            ticker="AAPL",
            report_period=date(2024, 1, 1),
            period="ttm",
            currency="USD",
            market_cap=3000000000000.0,
            data_source="test_source",
        )
        db_session.add(metric1)
        db_session.commit()

        # Try to add duplicate
        metric2 = FinancialMetric(
            ticker="AAPL",
            report_period=date(2024, 1, 1),
            period="ttm",
            currency="USD",
            market_cap=3100000000000.0,
            data_source="test_source",
        )
        db_session.add(metric2)

        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            db_session.commit()

    def test_metrics_json_field(self, db_session):
        """Test storing full metrics in JSON field."""
        metrics_data = {
            "revenue_growth": 0.15,
            "earnings_growth": 0.20,
            "operating_margin": 0.30,
        }
        metric = FinancialMetric(
            ticker="AAPL",
            report_period=date(2024, 1, 1),
            period="ttm",
            currency="USD",
            metrics_json=metrics_data,
            data_source="test_source",
        )
        db_session.add(metric)
        db_session.commit()

        # Retrieve and verify JSON data
        retrieved = db_session.query(FinancialMetric).filter_by(ticker="AAPL").first()
        assert retrieved.metrics_json == metrics_data
        assert retrieved.metrics_json["revenue_growth"] == 0.15


class TestCompanyNewsItem:
    """Tests for CompanyNewsItem model."""

    def test_create_company_news(self, db_session):
        """Test creating a company news record."""
        news = CompanyNewsItem(
            ticker="AAPL",
            date=datetime(2024, 1, 1, 10, 0, 0),
            title="Apple Announces New Product",
            content="Apple Inc. announced a new product today...",
            url="https://example.com/news/1",
            source="Example News",
            data_source="test_source",
        )
        db_session.add(news)
        db_session.commit()

        assert news.id is not None
        assert news.ticker == "AAPL"
        assert news.title == "Apple Announces New Product"

    def test_query_news_by_ticker_and_date_range(self, db_session):
        """Test querying news by ticker and date range."""
        # Add multiple news records
        news_items = [
            CompanyNewsItem(
                ticker="AAPL",
                date=datetime(2024, 1, i, 10, 0, 0),
                title=f"News {i}",
                content=f"Content {i}",
                url=f"https://example.com/news/{i}",
                source="Example News",
                data_source="test_source",
            )
            for i in range(1, 6)
        ]
        db_session.add_all(news_items)
        db_session.commit()

        # Query date range
        results = (
            db_session.query(CompanyNewsItem)
            .filter(
                CompanyNewsItem.ticker == "AAPL",
                CompanyNewsItem.date >= datetime(2024, 1, 2, 0, 0, 0),
                CompanyNewsItem.date < datetime(2024, 1, 5, 0, 0, 0),
            )
            .all()
        )

        assert len(results) == 3

    def test_nullable_fields(self, db_session):
        """Test that content, url, and source are optional."""
        news = CompanyNewsItem(
            ticker="AAPL",
            date=datetime(2024, 1, 1, 10, 0, 0),
            title="Minimal News",
            data_source="test_source",
        )
        db_session.add(news)
        db_session.commit()

        assert news.id is not None
        assert news.content is None
        assert news.url is None
        assert news.source is None
