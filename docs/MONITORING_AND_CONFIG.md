# Configuration Management and Monitoring Guide

This guide explains how to use the centralized configuration management and data source monitoring features.

## Table of Contents

- [Configuration Management](#configuration-management)
- [Health Checking](#health-checking)
- [Metrics Collection](#metrics-collection)
- [Decorators](#decorators)
- [Examples](#examples)

## Configuration Management

### Basic Usage

```python
from src.config import settings

# Access configuration
print(f"Request timeout: {settings.data_source.request_timeout}")
print(f"Cache TTL: {settings.cache.ttl}")
print(f"Monitoring enabled: {settings.monitoring.enabled}")
```

### Configuration Sections

#### Data Source Settings

```python
settings.data_source.source_weights  # Weight for each data source
settings.data_source.price_deviation_threshold  # Price deviation threshold (2%)
settings.data_source.volume_deviation_threshold  # Volume deviation threshold (10%)
settings.data_source.request_timeout  # Request timeout in seconds
settings.data_source.max_retries  # Maximum number of retries
```

#### Cache Settings

```python
settings.cache.ttl  # Time to live in seconds (300)
settings.cache.cleanup_interval  # Cleanup interval in seconds (60)
settings.cache.max_size  # Maximum cache entries (10000)
```

#### Monitoring Settings

```python
settings.monitoring.enabled  # Enable/disable monitoring (True)
settings.monitoring.metrics_interval  # Metrics collection interval (60s)
settings.monitoring.health_check_interval  # Health check interval (300s)
```

### Environment Variables

Override settings using environment variables with appropriate prefixes:

```bash
# Data source settings
export DATA_SOURCE_REQUEST_TIMEOUT=60
export DATA_SOURCE_MAX_RETRIES=5

# Cache settings
export CACHE_TTL=600
export CACHE_MAX_SIZE=20000

# Monitoring settings
export MONITORING_ENABLED=true
export MONITORING_METRICS_INTERVAL=120
```

### Configuration Validation

```python
from src.config import settings, validate_settings, validate_and_raise

# Validate and get errors
errors = validate_settings(settings)
if errors:
    print("Configuration errors:", errors)

# Validate and raise exception if invalid
try:
    validate_and_raise(settings)
    print("Configuration is valid")
except ValueError as e:
    print(f"Invalid configuration: {e}")
```

## Health Checking

### Basic Health Check

```python
from src.monitoring import DataSourceHealthChecker

# Create checker
checker = DataSourceHealthChecker()

# Check single source
status = checker.check_source(my_source, ticker="AAPL")
print(f"Healthy: {status.is_healthy}")
print(f"Response time: {status.response_time}ms")
print(f"Success rate: {status.success_rate * 100}%")
```

### Check Multiple Sources

```python
# Check all sources
sources = [source1, source2, source3]
results = checker.check_all_sources(sources)

# Print results
for name, status in results.items():
    print(f"{name}: {'✓' if status.is_healthy else '✗'}")
```

### Get Best Source

```python
# Get the best (healthiest and fastest) source
best = checker.get_best_source(sources)
if best:
    print(f"Best source: {best.name}")

# Filter by market
best_cn = checker.get_best_source(sources, required_market="CN")
```

### Health Status Summary

```python
summary = checker.get_status_summary()
print(f"Total sources: {summary['total_sources']}")
print(f"Healthy: {summary['healthy_sources']}")
print(f"Unhealthy: {summary['unhealthy_sources']}")

# Detailed status for each source
for name, status_dict in summary['sources'].items():
    print(f"{name}: {status_dict}")
```

## Metrics Collection

### Recording Metrics

Metrics are automatically collected when using the `@monitor_request` decorator:

```python
from src.monitoring import monitor_request

class MyDataSource:
    @monitor_request("MyDataSource")
    def get_prices(self, ticker, start_date, end_date):
        # Your implementation
        return data
```

### Accessing Metrics

```python
from src.monitoring import metrics_collector

# Get metrics for specific source
metrics = metrics_collector.get_metrics("MyDataSource")
print(f"Total requests: {metrics['total_requests']}")
print(f"Success rate: {metrics['success_rate']}")
print(f"Avg latency: {metrics['avg_latency_ms']}")

# Get all metrics
all_metrics = metrics_collector.get_metrics()

# Get summary
summary = metrics_collector.get_summary()
```

### Top Sources

```python
# Top sources by success rate
top_reliable = metrics_collector.get_top_sources(n=5, by="success_rate")

# Top sources by speed (lowest latency)
top_fast = metrics_collector.get_top_sources(n=5, by="avg_latency")

# Top sources by usage
top_used = metrics_collector.get_top_sources(n=5, by="total_requests")
```

### Reset Metrics

```python
# Reset specific source
metrics_collector.reset_metrics("MyDataSource")

# Reset all metrics
metrics_collector.reset_metrics()
```

## Decorators

### @monitor_request

Automatically monitor function calls:

```python
from src.monitoring import monitor_request

@monitor_request("MySource")
def fetch_data(ticker):
    # This function is automatically monitored
    return data
```

### @retry_with_monitoring

Add retry logic with monitoring:

```python
from src.monitoring import retry_with_monitoring

@retry_with_monitoring("MySource", max_retries=3, backoff_factor=2.0)
def fetch_data(ticker):
    # Will retry up to 3 times with exponential backoff
    return data
```

### @monitor_class_methods

Monitor all public methods of a class:

```python
from src.monitoring import monitor_class_methods

@monitor_class_methods("MySource")
class MyDataSource:
    def get_prices(self, ticker):
        return []

    def get_metrics(self, ticker):
        return {}

    # All public methods are automatically monitored
```

## Examples

### Complete Usage Example

```python
from src.config import settings, validate_and_raise
from src.monitoring import (
    DataSourceHealthChecker,
    metrics_collector,
    monitor_request,
)

# 1. Validate configuration
validate_and_raise(settings)

# 2. Create monitored data source
class MyDataSource:
    def __init__(self, name):
        self.name = name

    @monitor_request("MyDataSource")
    def get_prices(self, ticker, start_date, end_date):
        # Your implementation
        return data

    def supports_market(self, market):
        return market in ["US", "CN"]

# 3. Use the data source
source = MyDataSource("MySource")
data = source.get_prices("AAPL", "2024-01-01", "2024-12-31")

# 4. Check health
checker = DataSourceHealthChecker()
status = checker.check_source(source)
print(f"Health: {status.is_healthy}")

# 5. View metrics
metrics = metrics_collector.get_metrics("MyDataSource")
print(f"Success rate: {metrics['success_rate']}")
print(f"Avg latency: {metrics['avg_latency_ms']}")
```

### Running the Example

```bash
# Run the monitoring example
poetry run python examples/monitoring_example.py
```

## Best Practices

1. **Configuration**
   - Use environment variables for deployment-specific settings
   - Validate configuration at startup
   - Keep sensitive data in `.env` files (not committed)

2. **Health Checking**
   - Check health periodically, not on every request
   - Use health status to select the best data source
   - Handle unhealthy sources gracefully

3. **Metrics Collection**
   - Reset metrics periodically to prevent memory growth
   - Monitor P95/P99 latencies, not just averages
   - Track success rates to detect issues early

4. **Decorators**
   - Use `@monitor_request` for all external API calls
   - Consider `@retry_with_monitoring` for unreliable sources
   - Keep decorator overhead in mind for high-frequency calls

## Monitoring Dashboard (Future)

The metrics collected can be exported to monitoring systems:

- Prometheus
- Grafana
- DataDog
- CloudWatch

Example metrics to track:
- Request success rate by source
- P95/P99 latencies
- Health status changes
- Error rates and types

## Troubleshooting

### Configuration Not Loading

```python
# Check if .env file exists
import os
print(os.path.exists('.env'))

# Print loaded settings
from src.config import settings
print(settings.model_dump())
```

### Metrics Not Recording

```python
# Verify monitoring is enabled
from src.config import settings
print(f"Monitoring enabled: {settings.monitoring.enabled}")

# Check if decorator is applied
import inspect
print(inspect.getsource(my_function))
```

### Health Check Failing

```python
# Check source availability manually
try:
    data = source.get_prices("AAPL", "2024-01-01", "2024-01-02")
    print(f"Got {len(data)} records")
except Exception as e:
    print(f"Error: {e}")
```

## API Reference

### Settings Classes

- `DataSourceSettings`: Data source configuration
- `CacheSettings`: Cache configuration
- `MonitoringSettings`: Monitoring configuration
- `Settings`: Global settings container

### Health Check Classes

- `HealthStatus`: Health status dataclass
- `DataSourceHealthChecker`: Health checking utility

### Metrics Classes

- `DataSourceMetrics`: Metrics dataclass
- `MetricsCollector`: Metrics collection utility

### Functions

- `validate_settings(settings)`: Validate and return errors
- `validate_and_raise(settings)`: Validate and raise if invalid

## Testing

```bash
# Run all tests
poetry run pytest tests/config/ tests/monitoring/ -v

# Run specific test file
poetry run pytest tests/config/test_settings.py -v

# Run with coverage
poetry run pytest tests/config/ tests/monitoring/ --cov=src.config --cov=src.monitoring
```
