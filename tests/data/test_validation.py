"""Tests for data validation."""
import pytest
from src.data.validation import DataValidator


class TestDataValidator:
    """Test data validator."""

    def test_init(self):
        """Test initialization."""
        validator = DataValidator()

        assert validator.price_threshold == 0.02
        assert "AKShare" in validator.source_weights
        assert "YFinance" in validator.source_weights

    def test_cross_validate_prices_single_source(self):
        """Test validation with single data source."""
        validator = DataValidator()

        data_sources = {
            "AKShare": [
                {
                    "open": 10.0,
                    "close": 10.5,
                    "high": 11.0,
                    "low": 9.5,
                    "volume": 1000000,
                    "time": "2024-01-01T00:00:00Z",
                },
                {
                    "open": 10.5,
                    "close": 11.0,
                    "high": 11.5,
                    "low": 10.0,
                    "volume": 1100000,
                    "time": "2024-01-02T00:00:00Z",
                },
            ]
        }

        validated = validator.cross_validate_prices(data_sources)

        assert len(validated) == 2
        assert validated[0]["confidence"] > 0
        assert validated[0]["data_source"] == "AKShare"
        assert validated[0]["num_sources"] == 1

    def test_cross_validate_prices_multi_source(self):
        """Test validation with multiple data sources."""
        validator = DataValidator()

        data_sources = {
            "AKShare": [
                {
                    "open": 10.0,
                    "close": 10.5,
                    "high": 11.0,
                    "low": 9.5,
                    "volume": 1000000,
                    "time": "2024-01-01T00:00:00Z",
                }
            ],
            "YFinance": [
                {
                    "open": 10.1,
                    "close": 10.6,
                    "high": 11.1,
                    "low": 9.6,
                    "volume": 1050000,
                    "time": "2024-01-01T00:00:00Z",
                }
            ],
        }

        validated = validator.cross_validate_prices(data_sources)

        assert len(validated) == 1
        # Should be weighted average
        assert 10.0 <= validated[0]["close"] <= 10.6
        assert validated[0]["num_sources"] == 2
        assert validated[0]["confidence"] > 0.5

    def test_cross_validate_prices_with_deviation(self):
        """Test validation with price deviation."""
        validator = DataValidator(price_threshold=0.02)

        data_sources = {
            "AKShare": [
                {
                    "open": 10.0,
                    "close": 10.0,
                    "high": 11.0,
                    "low": 9.5,
                    "volume": 1000000,
                    "time": "2024-01-01T00:00:00Z",
                }
            ],
            "YFinance": [
                {
                    "open": 10.0,
                    "close": 12.0,  # 20% deviation
                    "high": 11.0,
                    "low": 9.5,
                    "volume": 1000000,
                    "time": "2024-01-01T00:00:00Z",
                }
            ],
        }

        validated = validator.cross_validate_prices(data_sources)

        assert len(validated) == 1
        # High deviation should reduce confidence
        assert validated[0]["confidence"] < 0.8
        assert validated[0]["max_deviation"] > validator.price_threshold

    def test_validate_financial_metrics_single_source(self):
        """Test financial metrics validation with single source."""
        validator = DataValidator()

        data_sources = {
            "AKShare": {
                "ticker": "000001",
                "price_to_earnings_ratio": 15.0,
                "return_on_equity": 0.15,
            }
        }

        validated = validator.validate_financial_metrics(data_sources)

        assert validated is not None
        assert validated["ticker"] == "000001"
        assert validated["confidence"] > 0
        assert validated["num_sources"] == 1

    def test_validate_financial_metrics_multi_source(self):
        """Test financial metrics validation with multiple sources."""
        validator = DataValidator()

        data_sources = {
            "AKShare": {
                "ticker": "00700",
                "price_to_earnings_ratio": 25.0,
                "return_on_equity": 0.20,
            },
            "YFinance": {
                "ticker": "00700",
                "price_to_earnings_ratio": 26.0,
                "return_on_equity": 0.21,
            },
        }

        validated = validator.validate_financial_metrics(data_sources)

        assert validated is not None
        assert validated["ticker"] == "00700"
        # Should be weighted average
        assert 25.0 <= validated["price_to_earnings_ratio"] <= 26.0
        assert validated["num_sources"] == 2
        assert validated["confidence"] > 0.6

    def test_calculate_confidence(self):
        """Test confidence calculation."""
        validator = DataValidator(price_threshold=0.02)

        # Single source, no deviation
        confidence = validator._calculate_confidence(1, 0.0)
        assert confidence == 0.5

        # Two sources, no deviation
        confidence = validator._calculate_confidence(2, 0.0)
        assert confidence == 0.7

        # Three sources, no deviation
        confidence = validator._calculate_confidence(3, 0.0)
        assert confidence == 0.9

        # Two sources, small deviation (within threshold)
        confidence = validator._calculate_confidence(2, 0.01)
        assert confidence == 0.7

        # Two sources, large deviation
        confidence = validator._calculate_confidence(2, 0.10)
        assert confidence < 0.7

    def test_validate_news(self):
        """Test news validation."""
        validator = DataValidator()

        data_sources = {
            "AKShare": [
                {
                    "ticker": "000001",
                    "title": "Company announces earnings",
                    "date": "2024-01-15T00:00:00Z",
                    "source": "News Source 1",
                    "url": "https://example.com/news1",
                }
            ],
            "YFinance": [
                {
                    "ticker": "000001",
                    "title": "Company reports revenue growth",
                    "date": "2024-01-16T00:00:00Z",
                    "source": "News Source 2",
                    "url": "https://example.com/news2",
                }
            ],
        }

        validated = validator.validate_news(data_sources)

        assert len(validated) == 2
        assert all("data_source" in news for news in validated)

    def test_normalize_date(self):
        """Test date normalization."""
        validator = DataValidator()

        # ISO format with timezone
        assert validator._normalize_date("2024-01-01T00:00:00Z") == "2024-01-01"

        # ISO format without timezone
        assert validator._normalize_date("2024-01-01 12:34:56") == "2024-01-01"

        # Simple date format
        assert validator._normalize_date("2024-01-01") == "2024-01-01"

        # Invalid date
        assert validator._normalize_date("invalid") == ""
        assert validator._normalize_date("") == ""
