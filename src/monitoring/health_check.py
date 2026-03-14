"""Data source health checking utilities."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import logging
import time


@dataclass
class HealthStatus:
    """Health status for a data source.

    Attributes:
        source_name: Name of the data source
        is_healthy: Whether the source is healthy
        response_time: Response time in milliseconds
        success_rate: Success rate (0-1)
        last_check: Timestamp of last check
        error_message: Error message if unhealthy
    """

    source_name: str
    is_healthy: bool
    response_time: float
    success_rate: float
    last_check: datetime
    error_message: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'source_name': self.source_name,
            'is_healthy': self.is_healthy,
            'response_time_ms': f"{self.response_time:.2f}",
            'success_rate': f"{self.success_rate * 100:.1f}%",
            'last_check': self.last_check.isoformat(),
            'error_message': self.error_message
        }


class DataSourceHealthChecker:
    """Health checker for data sources.

    This class provides methods to check the health of data sources
    by attempting to fetch sample data and measuring response times.

    Example:
        >>> checker = DataSourceHealthChecker()
        >>> status = checker.check_source(my_source, ticker="AAPL")
        >>> if status.is_healthy:
        ...     print(f"Source {status.source_name} is healthy")
    """

    def __init__(self):
        """Initialize health checker."""
        self.health_status: Dict[str, HealthStatus] = {}
        self.logger = logging.getLogger(__name__)

    def check_source(
        self,
        source,
        ticker: str = "AAPL",
        start_date: str = "2024-01-01",
        end_date: str = "2024-01-02"
    ) -> HealthStatus:
        """Check health status of a single data source.

        Args:
            source: Data source instance (must have get_prices method)
            ticker: Test ticker symbol
            start_date: Test start date
            end_date: Test end date

        Returns:
            HealthStatus object with check results

        Example:
            >>> from src.markets.sources import AKShareSource
            >>> source = AKShareSource()
            >>> checker = DataSourceHealthChecker()
            >>> status = checker.check_source(source)
            >>> print(f"Healthy: {status.is_healthy}, Time: {status.response_time}ms")
        """
        start_time = time.time()
        # Try to get source name from instance, fallback to class name
        source_name = getattr(source, 'name', None) or source.__class__.__name__

        try:
            # Attempt to fetch data
            self.logger.debug(
                f"Checking health of {source_name} with ticker={ticker}, "
                f"dates={start_date} to {end_date}"
            )
            data = source.get_prices(ticker, start_date, end_date)
            response_time = (time.time() - start_time) * 1000

            # Consider healthy if we got some data
            is_healthy = len(data) > 0

            if is_healthy:
                self.logger.info(
                    f"{source_name} is healthy: {len(data)} records, "
                    f"{response_time:.2f}ms"
                )
            else:
                self.logger.warning(f"{source_name} returned no data")

            status = HealthStatus(
                source_name=source_name,
                is_healthy=is_healthy,
                response_time=response_time,
                success_rate=1.0 if is_healthy else 0.0,
                last_check=datetime.now()
            )

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.logger.error(f"Health check failed for {source_name}: {e}")

            status = HealthStatus(
                source_name=source_name,
                is_healthy=False,
                response_time=response_time,
                success_rate=0.0,
                last_check=datetime.now(),
                error_message=str(e)
            )

        # Store the status
        self.health_status[source_name] = status
        return status

    def check_all_sources(
        self,
        sources: List,
        ticker: str = "AAPL",
        start_date: str = "2024-01-01",
        end_date: str = "2024-01-02"
    ) -> Dict[str, HealthStatus]:
        """Check health of all data sources.

        Args:
            sources: List of data source instances
            ticker: Test ticker symbol
            start_date: Test start date
            end_date: Test end date

        Returns:
            Dictionary mapping source name to HealthStatus

        Example:
            >>> sources = [AKShareSource(), YFinanceSource()]
            >>> checker = DataSourceHealthChecker()
            >>> results = checker.check_all_sources(sources)
            >>> for name, status in results.items():
            ...     print(f"{name}: {'✓' if status.is_healthy else '✗'}")
        """
        self.logger.info(f"Checking health of {len(sources)} data sources")
        results = {}

        for source in sources:
            status = self.check_source(source, ticker, start_date, end_date)
            results[status.source_name] = status

        # Log summary
        healthy_count = sum(1 for s in results.values() if s.is_healthy)
        self.logger.info(
            f"Health check complete: {healthy_count}/{len(results)} sources healthy"
        )

        return results

    def get_best_source(
        self,
        sources: List,
        required_market: Optional[str] = None
    ) -> Optional:
        """Get the best (healthiest and fastest) data source.

        The best source is determined by:
        1. Health status (must be healthy)
        2. Response time (faster is better)

        Args:
            sources: List of data source instances
            required_market: Optional market requirement

        Returns:
            The best data source or None if all unhealthy

        Example:
            >>> sources = [AKShareSource(), YFinanceSource()]
            >>> checker = DataSourceHealthChecker()
            >>> checker.check_all_sources(sources)
            >>> best = checker.get_best_source(sources)
            >>> if best:
            ...     print(f"Best source: {best.__class__.__name__}")
        """
        # Filter by market if required
        if required_market:
            sources = [s for s in sources if s.supports_market(required_market)]

        if not sources:
            self.logger.warning("No sources available")
            return None

        # Get health status for all sources
        healthy_sources = []
        for source in sources:
            source_name = getattr(source, 'name', None) or source.__class__.__name__
            if source_name in self.health_status:
                status = self.health_status[source_name]
                if status.is_healthy:
                    healthy_sources.append((source, status))

        if not healthy_sources:
            self.logger.warning("No healthy sources available")
            return None

        # Sort by response time (ascending)
        healthy_sources.sort(key=lambda x: x[1].response_time)
        best_source, best_status = healthy_sources[0]

        self.logger.info(
            f"Best source: {best_status.source_name} "
            f"(response time: {best_status.response_time:.2f}ms)"
        )

        return best_source

    def get_status_summary(self) -> Dict:
        """Get summary of all health statuses.

        Returns:
            Dictionary with summary information

        Example:
            >>> checker = DataSourceHealthChecker()
            >>> summary = checker.get_status_summary()
            >>> print(f"Total sources: {summary['total_sources']}")
            >>> print(f"Healthy: {summary['healthy_sources']}")
        """
        total = len(self.health_status)
        healthy = sum(1 for s in self.health_status.values() if s.is_healthy)

        return {
            'total_sources': total,
            'healthy_sources': healthy,
            'unhealthy_sources': total - healthy,
            'sources': {
                name: status.to_dict()
                for name, status in self.health_status.items()
            }
        }
