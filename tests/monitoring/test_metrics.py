"""Tests for metrics collection module."""

import pytest
from src.monitoring.metrics import DataSourceMetrics, MetricsCollector


class TestDataSourceMetrics:
    """Tests for DataSourceMetrics dataclass."""

    def test_metrics_initialization(self):
        """Test creating DataSourceMetrics instance."""
        metrics = DataSourceMetrics(source_name="TestSource")

        assert metrics.source_name == "TestSource"
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.total_latency == 0.0
        assert len(metrics.latencies) == 0

    def test_success_rate_no_requests(self):
        """Test success rate with no requests."""
        metrics = DataSourceMetrics(source_name="TestSource")
        assert metrics.success_rate == 0.0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        metrics = DataSourceMetrics(
            source_name="TestSource",
            total_requests=100,
            successful_requests=95,
            failed_requests=5
        )
        assert metrics.success_rate == 0.95

    def test_avg_latency_no_requests(self):
        """Test average latency with no requests."""
        metrics = DataSourceMetrics(source_name="TestSource")
        assert metrics.avg_latency == 0.0

    def test_avg_latency_calculation(self):
        """Test average latency calculation."""
        metrics = DataSourceMetrics(
            source_name="TestSource",
            total_requests=4,
            total_latency=400.0
        )
        assert metrics.avg_latency == 100.0

    def test_p50_latency(self):
        """Test 50th percentile latency."""
        metrics = DataSourceMetrics(
            source_name="TestSource",
            latencies=[100, 200, 300, 400, 500]
        )
        assert metrics.p50_latency == 300

    def test_p95_latency(self):
        """Test 95th percentile latency."""
        metrics = DataSourceMetrics(
            source_name="TestSource",
            latencies=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        )
        # 95th percentile of 10 items is index 9
        assert metrics.p95_latency == 100

    def test_p99_latency(self):
        """Test 99th percentile latency."""
        latencies = list(range(1, 101))  # 1 to 100
        metrics = DataSourceMetrics(
            source_name="TestSource",
            latencies=latencies
        )
        # 99th percentile should be high
        assert metrics.p99_latency >= 99

    def test_percentiles_empty_latencies(self):
        """Test percentile calculations with no data."""
        metrics = DataSourceMetrics(source_name="TestSource")
        assert metrics.p50_latency == 0.0
        assert metrics.p95_latency == 0.0
        assert metrics.p99_latency == 0.0

    def test_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = DataSourceMetrics(
            source_name="TestSource",
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            total_latency=10000.0,
            latencies=[100, 150, 200]
        )

        result = metrics.to_dict()

        assert result['source_name'] == "TestSource"
        assert result['total_requests'] == 100
        assert result['successful_requests'] == 95
        assert result['failed_requests'] == 5
        assert 'success_rate' in result
        assert 'avg_latency_ms' in result
        assert 'p95_latency_ms' in result


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_collector_initialization(self):
        """Test creating MetricsCollector instance."""
        collector = MetricsCollector()
        assert len(collector.metrics) == 0

    def test_record_successful_request(self):
        """Test recording a successful request."""
        collector = MetricsCollector()
        collector.record_request("TestSource", success=True, latency=100.0)

        assert "TestSource" in collector.metrics
        metric = collector.metrics["TestSource"]
        assert metric.total_requests == 1
        assert metric.successful_requests == 1
        assert metric.failed_requests == 0
        assert metric.total_latency == 100.0
        assert len(metric.latencies) == 1

    def test_record_failed_request(self):
        """Test recording a failed request."""
        collector = MetricsCollector()
        collector.record_request("TestSource", success=False, latency=5000.0)

        metric = collector.metrics["TestSource"]
        assert metric.total_requests == 1
        assert metric.successful_requests == 0
        assert metric.failed_requests == 1

    def test_record_multiple_requests(self):
        """Test recording multiple requests."""
        collector = MetricsCollector()

        collector.record_request("TestSource", True, 100.0)
        collector.record_request("TestSource", True, 150.0)
        collector.record_request("TestSource", False, 5000.0)

        metric = collector.metrics["TestSource"]
        assert metric.total_requests == 3
        assert metric.successful_requests == 2
        assert metric.failed_requests == 1
        assert metric.total_latency == 5250.0

    def test_latency_history_limit(self):
        """Test that latency history is limited to 1000 entries."""
        collector = MetricsCollector()

        # Record 1500 requests
        for i in range(1500):
            collector.record_request("TestSource", True, float(i))

        metric = collector.metrics["TestSource"]
        assert len(metric.latencies) == 1000
        # Should keep the most recent ones
        assert metric.latencies[-1] == 1499.0

    def test_get_metrics_specific_source(self):
        """Test getting metrics for a specific source."""
        collector = MetricsCollector()
        collector.record_request("Source1", True, 100.0)
        collector.record_request("Source2", True, 200.0)

        metrics = collector.get_metrics("Source1")

        assert metrics['source_name'] == "Source1"
        assert 'total_requests' in metrics

    def test_get_metrics_all_sources(self):
        """Test getting metrics for all sources."""
        collector = MetricsCollector()
        collector.record_request("Source1", True, 100.0)
        collector.record_request("Source2", True, 200.0)

        metrics = collector.get_metrics()

        assert len(metrics) == 2
        assert "Source1" in metrics
        assert "Source2" in metrics

    def test_get_metrics_nonexistent_source(self):
        """Test getting metrics for non-existent source."""
        collector = MetricsCollector()
        metrics = collector.get_metrics("NonExistent")
        assert metrics == {}

    def test_get_summary(self):
        """Test getting metrics summary."""
        collector = MetricsCollector()
        collector.record_request("Source1", True, 100.0)
        collector.record_request("Source1", True, 150.0)
        collector.record_request("Source2", False, 5000.0)

        summary = collector.get_summary()

        assert summary['total_sources'] == 2
        assert 'sources' in summary
        assert 'Source1' in summary['sources']
        assert 'Source2' in summary['sources']

    def test_reset_metrics_specific_source(self):
        """Test resetting metrics for a specific source."""
        collector = MetricsCollector()
        collector.record_request("Source1", True, 100.0)
        collector.record_request("Source2", True, 200.0)

        collector.reset_metrics("Source1")

        # Source1 should be reset
        assert collector.metrics["Source1"].total_requests == 0
        # Source2 should still have data
        assert collector.metrics["Source2"].total_requests == 1

    def test_reset_metrics_all_sources(self):
        """Test resetting metrics for all sources."""
        collector = MetricsCollector()
        collector.record_request("Source1", True, 100.0)
        collector.record_request("Source2", True, 200.0)

        collector.reset_metrics()

        assert len(collector.metrics) == 0

    def test_get_top_sources_by_success_rate(self):
        """Test getting top sources by success rate."""
        collector = MetricsCollector()

        # Source1: 100% success
        collector.record_request("Source1", True, 100.0)
        collector.record_request("Source1", True, 110.0)

        # Source2: 50% success
        collector.record_request("Source2", True, 100.0)
        collector.record_request("Source2", False, 5000.0)

        # Source3: 0% success
        collector.record_request("Source3", False, 5000.0)

        top = collector.get_top_sources(n=2, by="success_rate")

        assert len(top) == 2
        assert top[0]['source_name'] == "Source1"
        assert top[1]['source_name'] == "Source2"

    def test_get_top_sources_by_latency(self):
        """Test getting top sources by average latency."""
        collector = MetricsCollector()

        collector.record_request("FastSource", True, 50.0)
        collector.record_request("MediumSource", True, 150.0)
        collector.record_request("SlowSource", True, 500.0)

        top = collector.get_top_sources(n=2, by="avg_latency")

        assert len(top) == 2
        # Should be sorted by latency (ascending)
        assert top[0]['source_name'] == "FastSource"
        assert top[1]['source_name'] == "MediumSource"

    def test_get_top_sources_by_total_requests(self):
        """Test getting top sources by total requests."""
        collector = MetricsCollector()

        # Source1: 5 requests
        for _ in range(5):
            collector.record_request("Source1", True, 100.0)

        # Source2: 3 requests
        for _ in range(3):
            collector.record_request("Source2", True, 100.0)

        # Source3: 10 requests
        for _ in range(10):
            collector.record_request("Source3", True, 100.0)

        top = collector.get_top_sources(n=2, by="total_requests")

        assert len(top) == 2
        assert top[0]['source_name'] == "Source3"
        assert top[1]['source_name'] == "Source1"

    def test_get_top_sources_empty(self):
        """Test getting top sources with no data."""
        collector = MetricsCollector()
        top = collector.get_top_sources(n=5)
        assert len(top) == 0


class TestMetricsIntegration:
    """Integration tests for metrics collection."""

    def test_realistic_scenario(self):
        """Test a realistic usage scenario."""
        collector = MetricsCollector()

        # Simulate requests from multiple sources
        sources = ["AKShare", "YFinance", "Sina"]

        for source in sources:
            # Each source gets different patterns
            if source == "AKShare":
                # Fast and reliable
                for _ in range(100):
                    collector.record_request(source, True, 80.0)
            elif source == "YFinance":
                # Slower but reliable
                for _ in range(100):
                    collector.record_request(source, True, 150.0)
            else:
                # Fast but less reliable
                for _ in range(80):
                    collector.record_request(source, True, 70.0)
                for _ in range(20):
                    collector.record_request(source, False, 5000.0)

        # Get summary
        summary = collector.get_summary()

        assert summary['total_sources'] == 3

        # Check success rates
        akshare_metrics = collector.get_metrics("AKShare")
        assert "100.00%" in akshare_metrics['success_rate']

        sina_metrics = collector.get_metrics("Sina")
        assert "80.00%" in sina_metrics['success_rate']

    def test_percentile_accuracy(self):
        """Test that percentile calculations are accurate."""
        collector = MetricsCollector()

        # Record 100 requests with known latencies
        for i in range(100):
            collector.record_request("TestSource", True, float(i + 1))

        metric = collector.metrics["TestSource"]

        # P50 should be around 50
        assert 49 <= metric.p50_latency <= 51

        # P95 should be around 95
        assert 94 <= metric.p95_latency <= 96

        # P99 should be around 99
        assert 98 <= metric.p99_latency <= 100
