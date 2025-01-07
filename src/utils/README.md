# Cache Utilities

This module provides caching functionality for API responses to improve performance and reduce API calls.

## Features

- TTL-based caching (Time To Live)
- Debug logging for cache hits/misses
- Thread-safe implementation
- Automatic key generation from function arguments

## Usage

### Basic Usage

The `@cache_api_response` decorator can be applied to any function to cache its results:

```python
from utils.cache import cache_api_response

@cache_api_response(ttl=3600)  # Cache for 1 hour
def get_data(param1, param2):
    # ... make API call ...
    return result
```

### Debug Mode

To enable debug logging for cache hits/misses:

```python
# In your code
from utils.cache import set_debug
set_debug(True)
```

Or use the `--debug-cache` flag when running the application:

```bash
poetry run python src/main.py --ticker AAPL --debug-cache
```

Debug output looks like:
```
INFO:utils.cache:💾 Cache MISS - stored new result for get_financial_metrics
INFO:utils.cache:🎯 Cache HIT for get_prices
```

### Cache Keys

Cache keys are automatically generated from function arguments using `normalize_cache_key_args()`. 
The function handles various argument types including:
- Positional and keyword arguments
- Nested dictionaries and lists
- Date objects
