"""Example usage of configuration management and monitoring system.

This example demonstrates how to use the centralized configuration management
and data source monitoring features.
"""

import logging
import time
from src.config import settings, validate_and_raise
from src.monitoring import (
    DataSourceHealthChecker,
    metrics_collector,
    monitor_request,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_settings():
    """Print current configuration settings."""
    logger.info("=" * 60)
    logger.info("Configuration Settings")
    logger.info("=" * 60)
    logger.info(f"Data Source Weights: {settings.data_source.source_weights}")
    logger.info(f"Price Deviation Threshold: {settings.data_source.price_deviation_threshold}")
    logger.info(f"Request Timeout: {settings.data_source.request_timeout}s")
    logger.info(f"Max Retries: {settings.data_source.max_retries}")
    logger.info(f"Cache TTL: {settings.cache.ttl}s")
    logger.info(f"Cache Max Size: {settings.cache.max_size}")
    logger.info(f"Monitoring Enabled: {settings.monitoring.enabled}")
    logger.info("=" * 60)
    logger.info("")


def validate_configuration():
    """Validate configuration and handle errors."""
    logger.info("Validating configuration...")
    try:
        validate_and_raise(settings)
        logger.info("✓ Configuration is valid")
    except ValueError as e:
        logger.error(f"✗ Configuration validation failed: {e}")
        raise
    logger.info("")


class ExampleDataSource:
    """Example data source for demonstration."""

    def __init__(self, name: str, failure_rate: float = 0.0):
        """
        Initialize example data source.

        Args:
            name: Name of the data source
            failure_rate: Probability of failure (0-1)
        """
        self.name = name
        self.failure_rate = failure_rate
        self._call_count = 0

    @monitor_request("ExampleSource")
    def get_prices(self, ticker: str, start_date: str, end_date: str):
        """
        Fetch prices with monitoring.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date
            end_date: End date

        Returns:
            List of price data
        """
        self._call_count += 1

        # Simulate latency
        time.sleep(0.05 + (self._call_count % 3) * 0.01)

        # Simulate occasional failures
        import random
        if random.random() < self.failure_rate:
            raise ConnectionError(f"Failed to fetch {ticker} data")

        return [
            {
                'open': 100,
                'close': 105,
                'high': 106,
                'low': 99,
                'volume': 1000000,
                'time': start_date
            }
        ]

    def supports_market(self, market: str) -> bool:
        """Check if market is supported."""
        return market in ["US", "CN"]


def demonstrate_monitoring():
    """Demonstrate monitoring functionality."""
    logger.info("=" * 60)
    logger.info("Monitoring Demo")
    logger.info("=" * 60)

    # Create example data sources
    sources = [
        ExampleDataSource("FastSource", failure_rate=0.0),
        ExampleDataSource("MediumSource", failure_rate=0.1),
        ExampleDataSource("SlowSource", failure_rate=0.2),
    ]

    # Make some requests
    logger.info("Making 20 requests to each source...")
    for i in range(20):
        for source in sources:
            try:
                source.get_prices("AAPL", "2024-01-01", "2024-01-02")
            except ConnectionError:
                pass

    # Display metrics
    logger.info("\nMetrics Summary:")
    summary = metrics_collector.get_summary()
    logger.info(f"Total sources monitored: {summary['total_sources']}")

    for source_name, stats in summary['sources'].items():
        logger.info(f"\n{source_name}:")
        logger.info(f"  Success Rate: {stats['success_rate']}")
        logger.info(f"  Avg Latency: {stats['avg_latency']}")
        logger.info(f"  P95 Latency: {stats['p95_latency']}")
        logger.info(f"  P99 Latency: {stats['p99_latency']}")
        logger.info(f"  Total Requests: {stats['total_requests']}")

    # Show top sources
    logger.info("\nTop Sources by Success Rate:")
    top_sources = metrics_collector.get_top_sources(n=3, by="success_rate")
    for i, source_metrics in enumerate(top_sources, 1):
        logger.info(f"  {i}. {source_metrics['source_name']}: {source_metrics['success_rate']}")

    logger.info("")


def demonstrate_health_check():
    """Demonstrate health checking functionality."""
    logger.info("=" * 60)
    logger.info("Health Check Demo")
    logger.info("=" * 60)

    # Create example data sources
    sources = [
        ExampleDataSource("HealthySource", failure_rate=0.0),
        ExampleDataSource("UnstableSource", failure_rate=0.5),
        ExampleDataSource("FailingSource", failure_rate=1.0),
    ]

    # Initialize health checker
    checker = DataSourceHealthChecker()

    # Check all sources
    logger.info("Checking health of all sources...")
    results = checker.check_all_sources(sources)

    logger.info("\nHealth Check Results:")
    for source_name, status in results.items():
        health_icon = "✓" if status.is_healthy else "✗"
        logger.info(f"{health_icon} {source_name}:")
        logger.info(f"    Healthy: {status.is_healthy}")
        logger.info(f"    Response Time: {status.response_time:.2f}ms")
        logger.info(f"    Success Rate: {status.success_rate * 100:.1f}%")
        if status.error_message:
            logger.info(f"    Error: {status.error_message}")

    # Get best source
    best = checker.get_best_source(sources)
    if best:
        logger.info(f"\nBest source: {best.name}")
    else:
        logger.info("\nNo healthy sources available")

    # Get status summary
    logger.info("\nStatus Summary:")
    summary = checker.get_status_summary()
    logger.info(f"  Total sources: {summary['total_sources']}")
    logger.info(f"  Healthy sources: {summary['healthy_sources']}")
    logger.info(f"  Unhealthy sources: {summary['unhealthy_sources']}")

    logger.info("")


def main():
    """Run all demonstrations."""
    try:
        # 1. Show configuration
        print_settings()

        # 2. Validate configuration
        validate_configuration()

        # 3. Demonstrate monitoring
        demonstrate_monitoring()

        # 4. Demonstrate health checking
        demonstrate_health_check()

        logger.info("=" * 60)
        logger.info("Demo completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
