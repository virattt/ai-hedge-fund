"""Cache decorators for simplified caching."""

import hashlib
import json
import time
import logging
from functools import wraps
from typing import Callable, Any, Dict, Optional

logger = logging.getLogger(__name__)


class SimpleCacheStore:
    """Simple cache store for decorator use."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str, ttl: int) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key not in self._cache:
            return None

        entry = self._cache[key]
        if time.time() - entry['timestamp'] > ttl:
            del self._cache[key]
            return None

        return entry['value']

    def set(self, key: str, value: Any):
        """Set value in cache with timestamp."""
        self._cache[key] = {
            'value': value,
            'timestamp': time.time()
        }

    def clear(self):
        """Clear all cached values."""
        self._cache.clear()


# Global cache store for decorators
_decorator_cache = SimpleCacheStore()


def _generate_cache_key(prefix: str, func_name: str, args: tuple, kwargs: dict) -> str:
    """
    Generate a unique cache key from function arguments.

    Args:
        prefix: Key prefix
        func_name: Function name
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Cache key string
    """
    # Create a hashable representation of arguments
    key_parts = [prefix, func_name]

    # Add all args (they are regular arguments, not self)
    for arg in args:
        try:
            # Try to use str for simple types
            key_parts.append(str(arg))
        except Exception:
            try:
                key_parts.append(repr(arg))
            except Exception:
                # If all else fails, use id
                key_parts.append(str(id(arg)))

    # Add kwargs
    for k, v in sorted(kwargs.items()):
        try:
            key_parts.append(f"{k}={v}")
        except Exception:
            key_parts.append(f"{k}={repr(v)}")

    # Create a hash for long keys
    key_str = ":".join(key_parts)
    if len(key_str) > 200:
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return f"{prefix}{func_name}:{key_hash}"

    return key_str


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Cache decorator with TTL support.

    Args:
        ttl: Time-to-live in seconds (default: 300 = 5 minutes)
        key_prefix: Optional prefix for cache keys

    Returns:
        Decorated function

    Example:
        @cached(ttl=600, key_prefix="api:")
        def fetch_data(ticker: str):
            return expensive_api_call(ticker)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = _generate_cache_key(key_prefix, func.__name__, args, kwargs)

            # Try to get from cache
            cached_value = _decorator_cache.get(cache_key, ttl)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value

            # Cache miss - execute function
            logger.debug(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)

            # Cache the result
            _decorator_cache.set(cache_key, result)

            return result

        # Add cache management methods to the wrapper
        wrapper.cache_clear = _decorator_cache.clear
        wrapper.cache_key = lambda *args, **kwargs: _generate_cache_key(
            key_prefix, func.__name__, args, kwargs
        )

        return wrapper
    return decorator


def get_decorator_cache() -> SimpleCacheStore:
    """Get the global decorator cache store."""
    return _decorator_cache
