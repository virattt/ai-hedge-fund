"""Tests for monitoring decorators."""

import pytest
import time
from src.monitoring.decorators import monitor_request, retry_with_monitoring
from src.monitoring.metrics import metrics_collector


class TestMonitorRequest:
    """Tests for monitor_request decorator."""

    def test_monitor_successful_request(self):
        """Test monitoring a successful request."""
        metrics_collector.reset_metrics()

        @monitor_request("TestSource")
        def fetch_data():
            return "data"

        result = fetch_data()

        assert result == "data"
        metrics = metrics_collector.get_metrics("TestSource")
        assert metrics['total_requests'] == 1
        assert metrics['successful_requests'] == 1

    def test_monitor_failed_request(self):
        """Test monitoring a failed request."""
        metrics_collector.reset_metrics()

        @monitor_request("TestSource")
        def fetch_data():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            fetch_data()

        metrics = metrics_collector.get_metrics("TestSource")
        assert metrics['total_requests'] == 1
        assert metrics['failed_requests'] == 1

    def test_monitor_latency_recorded(self):
        """Test that latency is recorded."""
        metrics_collector.reset_metrics()

        @monitor_request("TestSource")
        def fetch_data():
            time.sleep(0.01)  # Sleep 10ms
            return "data"

        fetch_data()

        metric = metrics_collector.metrics["TestSource"]
        # Should have recorded some latency > 10ms
        assert metric.avg_latency >= 10.0

    def test_monitor_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""
        @monitor_request("TestSource")
        def fetch_data():
            """Fetch some data."""
            return "data"

        assert fetch_data.__name__ == "fetch_data"
        assert "Fetch some data" in fetch_data.__doc__

    def test_monitor_with_arguments(self):
        """Test monitoring function with arguments."""
        metrics_collector.reset_metrics()

        @monitor_request("TestSource")
        def fetch_data(ticker, start_date, end_date):
            return f"data for {ticker}"

        result = fetch_data("AAPL", "2024-01-01", "2024-12-31")

        assert "AAPL" in result
        metrics = metrics_collector.get_metrics("TestSource")
        assert metrics['total_requests'] == 1

    def test_monitor_multiple_calls(self):
        """Test monitoring multiple calls."""
        metrics_collector.reset_metrics()

        @monitor_request("TestSource")
        def fetch_data():
            return "data"

        for _ in range(5):
            fetch_data()

        metrics = metrics_collector.get_metrics("TestSource")
        assert metrics['total_requests'] == 5
        assert metrics['successful_requests'] == 5


class TestRetryWithMonitoring:
    """Tests for retry_with_monitoring decorator."""

    def test_retry_successful_first_attempt(self):
        """Test that successful requests don't retry."""
        metrics_collector.reset_metrics()

        call_count = [0]

        @retry_with_monitoring("TestSource", max_retries=3, backoff_factor=0.01)
        def fetch_data():
            call_count[0] += 1
            return "data"

        result = fetch_data()

        assert result == "data"
        assert call_count[0] == 1
        metrics = metrics_collector.get_metrics("TestSource")
        assert metrics['total_requests'] == 1

    def test_retry_eventual_success(self):
        """Test that function retries until success."""
        metrics_collector.reset_metrics()

        call_count = [0]

        @retry_with_monitoring("TestSource", max_retries=3, backoff_factor=0.01)
        def fetch_data():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("Not ready yet")
            return "data"

        result = fetch_data()

        assert result == "data"
        assert call_count[0] == 3
        # Should have recorded 2 failures and 1 success
        metrics = metrics_collector.get_metrics("TestSource")
        assert metrics['total_requests'] == 3
        assert metrics['successful_requests'] == 1
        assert metrics['failed_requests'] == 2

    def test_retry_max_retries_exceeded(self):
        """Test that function fails after max retries."""
        metrics_collector.reset_metrics()

        call_count = [0]

        @retry_with_monitoring("TestSource", max_retries=2, backoff_factor=0.01)
        def fetch_data():
            call_count[0] += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            fetch_data()

        assert call_count[0] == 3  # Initial + 2 retries
        metrics = metrics_collector.get_metrics("TestSource")
        assert metrics['total_requests'] == 3
        assert metrics['failed_requests'] == 3

    def test_retry_backoff_timing(self):
        """Test that backoff delay increases exponentially."""
        metrics_collector.reset_metrics()

        call_times = []

        @retry_with_monitoring("TestSource", max_retries=2, backoff_factor=0.1)
        def fetch_data():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("Not ready")
            return "data"

        fetch_data()

        # Check that delays increase
        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            # First delay should be ~0.1s (backoff_factor * 2^0)
            assert 0.08 <= delay1 <= 0.3

        if len(call_times) >= 3:
            delay2 = call_times[2] - call_times[1]
            # Second delay should be ~0.2s (backoff_factor * 2^1)
            assert 0.15 <= delay2 <= 0.5

    def test_retry_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""
        @retry_with_monitoring("TestSource", max_retries=3)
        def fetch_data():
            """Fetch some data."""
            return "data"

        assert fetch_data.__name__ == "fetch_data"
        assert "Fetch some data" in fetch_data.__doc__


class TestDecoratorIntegration:
    """Integration tests for decorators."""

    def test_combined_decorators(self):
        """Test using multiple decorators together."""
        metrics_collector.reset_metrics()

        @monitor_request("TestSource")
        def fetch_data(should_fail=False):
            if should_fail:
                raise ValueError("Failed")
            return "data"

        # Successful call
        result = fetch_data(should_fail=False)
        assert result == "data"

        # Failed call
        with pytest.raises(ValueError):
            fetch_data(should_fail=True)

        metrics = metrics_collector.get_metrics("TestSource")
        assert metrics['total_requests'] == 2
        assert metrics['successful_requests'] == 1
        assert metrics['failed_requests'] == 1

    def test_realistic_data_source_scenario(self):
        """Test a realistic data source usage scenario."""
        metrics_collector.reset_metrics()

        class DataSource:
            def __init__(self):
                self.call_count = 0

            @monitor_request("RealisticSource")
            def get_prices(self, ticker, start_date, end_date):
                self.call_count += 1
                # Simulate occasional failures
                if self.call_count % 10 == 0:
                    raise ConnectionError("Network timeout")
                return [{'price': 100}]

        source = DataSource()

        # Make multiple calls
        for i in range(15):
            try:
                source.get_prices("AAPL", "2024-01-01", "2024-12-31")
            except ConnectionError:
                pass

        metrics = metrics_collector.get_metrics("RealisticSource")
        assert metrics['total_requests'] == 15
        # Should have 1 failure (at call 10)
        assert metrics['failed_requests'] == 1
        assert metrics['successful_requests'] == 14
