# Enhanced Cache Usage Guide

## Overview

The enhanced cache system provides TTL (Time-To-Live) management, statistics tracking, thread safety, automatic cleanup, and convenient decorators.

## Features

1. **TTL Management**: Automatic expiration of cached data
2. **Statistics Tracking**: Monitor cache hit/miss rates
3. **Thread Safety**: Safe for concurrent access
4. **Automatic Cleanup**: Background thread for removing expired entries
5. **Decorators**: Simple caching with `@cached` decorator

## Basic Usage

### Using the Cache Class

```python
from src.data.cache import Cache

# Initialize cache with 5-minute TTL (default: 300 seconds)
cache = Cache(ttl=300)

# Store data
prices = [{"time": "2024-01-01", "price": 100.0}]
cache.set_prices("AAPL", prices)

# Retrieve data (returns None if expired or not found)
cached_prices = cache.get_prices("AAPL")

# Get cache statistics
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']}")
print(f"Total cache entries: {stats['prices_size']}")

# Manual cleanup of expired entries
removed_count = cache.cleanup_expired()

# Clear all caches
cache.clear()
```

### Using the Cache Decorator

```python
from src.data.cache_decorators import cached

# Basic usage
@cached(ttl=300)
def fetch_stock_data(ticker: str):
    # Expensive API call
    return api.get_data(ticker)

# With custom key prefix
@cached(ttl=600, key_prefix="api:")
def fetch_market_data(ticker: str, date: str):
    return api.get_market_data(ticker, date)

# Clear cache for decorated function
fetch_stock_data.cache_clear()
```

### Automatic Cache Cleanup

```python
from src.data.cache import Cache
from src.data.cache_cleaner import CacheCleaner

cache = Cache(ttl=300)

# Start background cleanup (runs every 60 seconds by default)
cleaner = CacheCleaner(cache, interval=60)
cleaner.start()

# Your application code here...

# Stop cleanup when done
cleaner.stop()

# Or use as context manager
with CacheCleaner(cache, interval=60) as cleaner:
    # Cleanup runs automatically
    # Your application code here...
    pass
# Cleanup stops automatically
```

## API Reference

### Cache Class

#### Constructor
```python
Cache(ttl: int = 300)
```
- `ttl`: Time-to-live in seconds (default: 300 = 5 minutes)

#### Methods

**Data Access Methods** (all support TTL and statistics):
- `get_prices(ticker: str) -> List[dict] | None`
- `set_prices(ticker: str, data: List[dict])`
- `get_financial_metrics(ticker: str) -> List[dict] | None`
- `set_financial_metrics(ticker: str, data: List[dict])`
- `get_line_items(ticker: str) -> List[dict] | None`
- `set_line_items(ticker: str, data: List[dict])`
- `get_insider_trades(ticker: str) -> List[dict] | None`
- `set_insider_trades(ticker: str, data: List[dict])`
- `get_company_news(ticker: str) -> List[dict] | None`
- `set_company_news(ticker: str, data: List[dict])`

**Management Methods**:
- `cleanup_expired() -> int`: Remove expired entries, returns count
- `get_stats() -> Dict[str, Any]`: Get cache statistics
- `clear()`: Clear all caches and reset statistics

#### Statistics Structure
```python
{
    'hits': int,
    'misses': int,
    'total': int,
    'hit_rate': str,  # e.g., "75.50%"
    'prices_size': int,
    'financial_metrics_size': int,
    'line_items_size': int,
    'insider_trades_size': int,
    'company_news_size': int,
    'ttl': int
}
```

### @cached Decorator

```python
@cached(ttl: int = 300, key_prefix: str = "")
```
- `ttl`: Time-to-live in seconds
- `key_prefix`: Optional prefix for cache keys

**Decorated Function Methods**:
- `function.cache_clear()`: Clear all cached values for this function
- `function.cache_key(*args, **kwargs)`: Get cache key for given arguments

### CacheCleaner Class

#### Constructor
```python
CacheCleaner(cache: Cache, interval: int = 60)
```
- `cache`: Cache instance to clean
- `interval`: Cleanup interval in seconds

#### Methods
- `start()`: Start cleanup thread
- `stop(timeout: float = 5.0)`: Stop cleanup thread
- `is_running() -> bool`: Check if running

## Examples

### Example 1: API Client with Cache

```python
from src.data.cache import get_cache
from src.data.cache_decorators import cached

class StockDataClient:
    def __init__(self):
        self.cache = get_cache()

    @cached(ttl=300, key_prefix="stock:")
    def get_stock_price(self, ticker: str):
        # This will be cached for 5 minutes
        return self._fetch_from_api(ticker)

    def get_cached_stats(self):
        return self.cache.get_stats()
```

### Example 2: Long-Running Service

```python
from src.data.cache import Cache
from src.data.cache_cleaner import CacheCleaner
import logging

logging.basicConfig(level=logging.INFO)

def main():
    # Initialize cache with 10-minute TTL
    cache = Cache(ttl=600)

    # Start automatic cleanup every 2 minutes
    cleaner = CacheCleaner(cache, interval=120)
    cleaner.start()

    try:
        # Your service code
        while True:
            process_data(cache)

            # Log cache stats periodically
            stats = cache.get_stats()
            logging.info(f"Cache stats: {stats}")
    finally:
        cleaner.stop()

if __name__ == "__main__":
    main()
```

### Example 3: Testing with Cache

```python
import pytest
from src.data.cache import Cache

@pytest.fixture
def cache():
    """Provide fresh cache for each test."""
    cache = Cache(ttl=10)
    yield cache
    cache.clear()

def test_cache_behavior(cache):
    test_data = [{"time": "2024-01-01", "price": 100.0}]
    cache.set_prices("AAPL", test_data)

    result = cache.get_prices("AAPL")
    assert result is not None
    assert len(result) == 1
```

## Performance Considerations

1. **TTL Selection**:
   - Longer TTL reduces API calls but may serve stale data
   - Shorter TTL ensures fresh data but increases API usage
   - Default 5 minutes (300s) works for most use cases

2. **Cleanup Interval**:
   - Default 60 seconds is suitable for most applications
   - Adjust based on cache size and memory constraints
   - More frequent cleanup = less memory, more CPU

3. **Thread Safety**:
   - All cache operations are thread-safe (use locks internally)
   - No need for external synchronization

4. **Memory Management**:
   - Cache grows until cleanup runs
   - Monitor cache sizes via `get_stats()`
   - Use `clear()` to free all memory if needed

## Migration from Old Cache

The enhanced cache is backward compatible. To migrate:

1. **No code changes needed** - existing code works as-is
2. **Optional enhancements** - add TTL parameter if desired
3. **Add cleanup** - optionally start CacheCleaner for automatic maintenance
4. **Monitor** - use `get_stats()` to track performance

```python
# Old code (still works)
from src.data.cache import get_cache
cache = get_cache()
cache.set_prices("AAPL", data)

# Enhanced usage (optional)
cache = Cache(ttl=600)  # 10-minute TTL
stats = cache.get_stats()  # Monitor performance
```

## Logging

The cache system logs at DEBUG and INFO levels:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Will show:
# - Cache hits/misses
# - Cache cleanup operations
# - Cleaner start/stop events
```

## Best Practices

1. **Set appropriate TTL** based on data volatility
2. **Monitor hit rates** to tune TTL
3. **Use CacheCleaner** for long-running applications
4. **Use decorators** for simple function caching
5. **Clear cache** in tests for isolation
6. **Log stats** periodically to track performance
