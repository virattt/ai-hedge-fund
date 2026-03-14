"""Metrics collection for data sources."""

from dataclasses import dataclass, field
from typing import Dict, List
import logging


@dataclass
class DataSourceMetrics:
    """Metrics for a single data source.

    Attributes:
        source_name: Name of the data source
        total_requests: Total number of requests
        successful_requests: Number of successful requests
        failed_requests: Number of failed requests
        total_latency: Sum of all latencies in milliseconds
        latencies: List of recent latencies (last 1000)
    """

    source_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency: float = 0.0
    latencies: List[float] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0-1).

        Returns:
            Success rate as a float between 0 and 1
        """
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency(self) -> float:
        """Calculate average latency in milliseconds.

        Returns:
            Average latency or 0 if no requests
        """
        if self.total_requests == 0:
            return 0.0
        return self.total_latency / self.total_requests

    @property
    def p50_latency(self) -> float:
        """Calculate 50th percentile (median) latency.

        Returns:
            50th percentile latency or 0 if no data
        """
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.50)
        return sorted_latencies[index]

    @property
    def p95_latency(self) -> float:
        """Calculate 95th percentile latency.

        Returns:
            95th percentile latency or 0 if no data
        """
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[index]

    @property
    def p99_latency(self) -> float:
        """Calculate 99th percentile latency.

        Returns:
            99th percentile latency or 0 if no data
        """
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[index]

    def to_dict(self) -> Dict:
        """Convert metrics to dictionary.

        Returns:
            Dictionary representation of metrics
        """
        return {
            'source_name': self.source_name,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': f"{self.success_rate * 100:.2f}%",
            'avg_latency_ms': f"{self.avg_latency:.2f}",
            'p50_latency_ms': f"{self.p50_latency:.2f}",
            'p95_latency_ms': f"{self.p95_latency:.2f}",
            'p99_latency_ms': f"{self.p99_latency:.2f}",
        }


class MetricsCollector:
    """Collector for data source metrics.

    This class collects and aggregates metrics from data source operations,
    including success rates and latency percentiles.

    Example:
        >>> collector = MetricsCollector()
        >>> collector.record_request("AKShareSource", success=True, latency=150.5)
        >>> metrics = collector.get_metrics("AKShareSource")
        >>> print(f"Success rate: {metrics.success_rate * 100:.1f}%")
    """

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: Dict[str, DataSourceMetrics] = {}
        self.logger = logging.getLogger(__name__)
        self._max_latency_history = 1000  # Keep last 1000 latencies

    def record_request(self, source_name: str, success: bool, latency: float) -> None:
        """Record a request and its outcome.

        Args:
            source_name: Name of the data source
            success: Whether the request was successful
            latency: Request latency in milliseconds

        Example:
            >>> collector = MetricsCollector()
            >>> collector.record_request("AKShareSource", True, 125.3)
            >>> collector.record_request("AKShareSource", False, 5000.0)
        """
        if source_name not in self.metrics:
            self.metrics[source_name] = DataSourceMetrics(source_name=source_name)

        metric = self.metrics[source_name]
        metric.total_requests += 1

        if success:
            metric.successful_requests += 1
        else:
            metric.failed_requests += 1

        metric.total_latency += latency
        metric.latencies.append(latency)

        # Keep only recent latencies to prevent memory growth
        if len(metric.latencies) > self._max_latency_history:
            metric.latencies = metric.latencies[-self._max_latency_history:]

        self.logger.debug(
            f"Recorded request for {source_name}: "
            f"success={success}, latency={latency:.2f}ms"
        )

    def get_metrics(self, source_name: str = None) -> Dict:
        """Get metrics for a specific source or all sources.

        Args:
            source_name: Optional source name to filter by

        Returns:
            Dictionary of metrics (single source or all sources)

        Example:
            >>> collector = MetricsCollector()
            >>> # Get metrics for specific source
            >>> metrics = collector.get_metrics("AKShareSource")
            >>> # Get all metrics
            >>> all_metrics = collector.get_metrics()
        """
        if source_name:
            metric = self.metrics.get(source_name)
            return metric.to_dict() if metric else {}

        return {name: metric.to_dict() for name, metric in self.metrics.items()}

    def get_summary(self) -> Dict:
        """Get summary of all metrics.

        Returns:
            Dictionary with aggregated metrics summary

        Example:
            >>> collector = MetricsCollector()
            >>> summary = collector.get_summary()
            >>> print(f"Total sources: {summary['total_sources']}")
            >>> for name, stats in summary['sources'].items():
            ...     print(f"{name}: {stats['success_rate']}")
        """
        return {
            'total_sources': len(self.metrics),
            'sources': {
                name: {
                    'success_rate': f"{metric.success_rate * 100:.2f}%",
                    'avg_latency': f"{metric.avg_latency:.2f}ms",
                    'p95_latency': f"{metric.p95_latency:.2f}ms",
                    'p99_latency': f"{metric.p99_latency:.2f}ms",
                    'total_requests': metric.total_requests
                }
                for name, metric in self.metrics.items()
            }
        }

    def reset_metrics(self, source_name: str = None) -> None:
        """Reset metrics for a source or all sources.

        Args:
            source_name: Optional source name to reset (resets all if None)

        Example:
            >>> collector = MetricsCollector()
            >>> # Reset specific source
            >>> collector.reset_metrics("AKShareSource")
            >>> # Reset all
            >>> collector.reset_metrics()
        """
        if source_name:
            if source_name in self.metrics:
                self.metrics[source_name] = DataSourceMetrics(source_name=source_name)
                self.logger.info(f"Reset metrics for {source_name}")
        else:
            self.metrics.clear()
            self.logger.info("Reset all metrics")

    def get_top_sources(self, n: int = 5, by: str = "success_rate") -> List[Dict]:
        """Get top N sources by a specific metric.

        Args:
            n: Number of top sources to return
            by: Metric to sort by ('success_rate', 'avg_latency', 'total_requests')

        Returns:
            List of source metrics sorted by the specified metric

        Example:
            >>> collector = MetricsCollector()
            >>> # Get top 3 by success rate
            >>> top = collector.get_top_sources(3, by="success_rate")
            >>> # Get fastest sources
            >>> fastest = collector.get_top_sources(5, by="avg_latency")
        """
        if not self.metrics:
            return []

        metrics_list = list(self.metrics.values())

        # Sort by specified metric
        if by == "success_rate":
            metrics_list.sort(key=lambda m: m.success_rate, reverse=True)
        elif by == "avg_latency":
            metrics_list.sort(key=lambda m: m.avg_latency)
        elif by == "total_requests":
            metrics_list.sort(key=lambda m: m.total_requests, reverse=True)
        else:
            self.logger.warning(f"Unknown metric: {by}, using success_rate")
            metrics_list.sort(key=lambda m: m.success_rate, reverse=True)

        return [m.to_dict() for m in metrics_list[:n]]


# Global metrics collector instance
metrics_collector = MetricsCollector()
