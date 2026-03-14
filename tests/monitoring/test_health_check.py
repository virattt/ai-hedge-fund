"""Tests for health check module."""

import pytest
from datetime import datetime
from src.monitoring.health_check import DataSourceHealthChecker, HealthStatus


class MockDataSource:
    """Mock data source for testing."""

    def __init__(self, name="MockSource", should_fail=False, return_empty=False):
        self._name = name
        self.should_fail = should_fail
        self.return_empty = return_empty

    @property
    def name(self):
        return self._name

    def get_prices(self, ticker, start_date, end_date):
        """Mock get_prices method."""
        if self.should_fail:
            raise Exception("Mock failure")
        if self.return_empty:
            return []
        return [
            {'open': 100, 'close': 105, 'high': 106, 'low': 99, 'volume': 1000, 'time': '2024-01-01'}
        ]

    def supports_market(self, market):
        """Mock supports_market method."""
        return market in ["US", "CN"]


class TestHealthStatus:
    """Tests for HealthStatus dataclass."""

    def test_health_status_creation(self):
        """Test creating HealthStatus instance."""
        status = HealthStatus(
            source_name="TestSource",
            is_healthy=True,
            response_time=150.5,
            success_rate=0.95,
            last_check=datetime.now()
        )

        assert status.source_name == "TestSource"
        assert status.is_healthy is True
        assert status.response_time == 150.5
        assert status.success_rate == 0.95
        assert status.error_message is None

    def test_health_status_with_error(self):
        """Test HealthStatus with error message."""
        status = HealthStatus(
            source_name="TestSource",
            is_healthy=False,
            response_time=5000.0,
            success_rate=0.0,
            last_check=datetime.now(),
            error_message="Connection timeout"
        )

        assert status.is_healthy is False
        assert status.error_message == "Connection timeout"

    def test_to_dict(self):
        """Test converting HealthStatus to dictionary."""
        now = datetime.now()
        status = HealthStatus(
            source_name="TestSource",
            is_healthy=True,
            response_time=150.5,
            success_rate=0.95,
            last_check=now
        )

        result = status.to_dict()

        assert result['source_name'] == "TestSource"
        assert result['is_healthy'] is True
        assert 'response_time_ms' in result
        assert 'success_rate' in result
        assert result['last_check'] == now.isoformat()


class TestDataSourceHealthChecker:
    """Tests for DataSourceHealthChecker."""

    def test_check_healthy_source(self):
        """Test checking a healthy data source."""
        checker = DataSourceHealthChecker()
        source = MockDataSource("HealthySource")

        status = checker.check_source(source)

        assert status.is_healthy is True
        assert status.success_rate == 1.0
        assert status.response_time > 0
        assert status.error_message is None

    def test_check_failing_source(self):
        """Test checking a failing data source."""
        checker = DataSourceHealthChecker()
        source = MockDataSource("FailingSource", should_fail=True)

        status = checker.check_source(source)

        assert status.is_healthy is False
        assert status.success_rate == 0.0
        assert status.error_message is not None
        assert "Mock failure" in status.error_message

    def test_check_empty_data_source(self):
        """Test checking a source that returns empty data."""
        checker = DataSourceHealthChecker()
        source = MockDataSource("EmptySource", return_empty=True)

        status = checker.check_source(source)

        assert status.is_healthy is False
        assert status.success_rate == 0.0

    def test_health_status_stored(self):
        """Test that health status is stored in checker."""
        checker = DataSourceHealthChecker()
        source = MockDataSource("TestSource")

        checker.check_source(source)

        assert "TestSource" in checker.health_status
        assert checker.health_status["TestSource"].is_healthy is True

    def test_check_all_sources(self):
        """Test checking multiple sources."""
        checker = DataSourceHealthChecker()
        sources = [
            MockDataSource("Source1"),
            MockDataSource("Source2", should_fail=True),
            MockDataSource("Source3"),
        ]

        results = checker.check_all_sources(sources)

        assert len(results) == 3
        assert "Source1" in results
        assert "Source2" in results
        assert "Source3" in results
        assert results["Source1"].is_healthy is True
        assert results["Source2"].is_healthy is False
        assert results["Source3"].is_healthy is True

    def test_get_best_source_by_health(self):
        """Test getting the best (healthiest) source."""
        checker = DataSourceHealthChecker()

        # Create sources with different characteristics
        healthy_source = MockDataSource("HealthySource")
        failing_source = MockDataSource("FailingSource", should_fail=True)

        sources = [healthy_source, failing_source]

        # Check health first
        checker.check_all_sources(sources)

        # Get best source
        best = checker.get_best_source(sources)

        assert best is not None
        # Should be the healthy one
        assert best.should_fail is False

    def test_get_best_source_no_healthy(self):
        """Test getting best source when all are unhealthy."""
        checker = DataSourceHealthChecker()
        sources = [
            MockDataSource("Source1", should_fail=True),
            MockDataSource("Source2", should_fail=True),
        ]

        checker.check_all_sources(sources)
        best = checker.get_best_source(sources)

        assert best is None

    def test_get_best_source_with_market_filter(self):
        """Test getting best source with market requirement."""
        checker = DataSourceHealthChecker()
        source = MockDataSource("TestSource")

        checker.check_source(source)
        best = checker.get_best_source([source], required_market="US")

        assert best is not None

    def test_get_best_source_market_not_supported(self):
        """Test getting best source with unsupported market."""
        checker = DataSourceHealthChecker()
        source = MockDataSource("TestSource")

        checker.check_source(source)
        best = checker.get_best_source([source], required_market="UK")

        assert best is None

    def test_get_status_summary(self):
        """Test getting summary of all health statuses."""
        checker = DataSourceHealthChecker()
        sources = [
            MockDataSource("Source1"),
            MockDataSource("Source2", should_fail=True),
            MockDataSource("Source3"),
        ]

        checker.check_all_sources(sources)
        summary = checker.get_status_summary()

        assert 'total_sources' in summary
        assert 'healthy_sources' in summary
        assert 'unhealthy_sources' in summary
        assert 'sources' in summary
        assert summary['total_sources'] >= 1

    def test_custom_ticker_and_dates(self):
        """Test checking with custom ticker and dates."""
        checker = DataSourceHealthChecker()
        source = MockDataSource("TestSource")

        status = checker.check_source(
            source,
            ticker="GOOGL",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        assert status.is_healthy is True


class TestHealthCheckIntegration:
    """Integration tests for health checking."""

    def test_multiple_checks_update_status(self):
        """Test that multiple checks update the stored status."""
        checker = DataSourceHealthChecker()
        source = MockDataSource("TestSource")

        # First check - healthy
        status1 = checker.check_source(source)
        assert status1.is_healthy is True

        # Simulate source failure
        source.should_fail = True

        # Second check - unhealthy
        status2 = checker.check_source(source)
        assert status2.is_healthy is False

        # Verify stored status is updated
        assert checker.health_status["TestSource"].is_healthy is False

    def test_response_time_measured(self):
        """Test that response time is actually measured."""
        checker = DataSourceHealthChecker()
        source = MockDataSource("TestSource")

        status = checker.check_source(source)

        # Response time should be positive and reasonable
        assert status.response_time > 0
        assert status.response_time < 10000  # Less than 10 seconds
