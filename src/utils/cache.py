import time
import threading
from typing import Any, Optional, Dict, Tuple
from functools import wraps
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global debug flag
DEBUG = False

def set_debug(enabled: bool):
    """Enable or disable cache debugging"""
    global DEBUG
    DEBUG = enabled

class Cache:
    """Thread-safe cache implementation with TTL and LRU eviction."""
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        """
        Initialize cache with max size and TTL.
        
        Args:
            max_size: Maximum number of items in cache
            ttl: Time to live in seconds (default 5 minutes)
        """
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._max_size = max_size
        self._ttl = ttl
        self._lock = threading.Lock()
        
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache if it exists and is not expired."""
        with self._lock:
            if key not in self._cache:
                return None
                
            value, timestamp = self._cache[key]
            if time.time() - timestamp > self._ttl:
                del self._cache[key]
                return None
                
            return value
            
    def set(self, key: str, value: Any) -> None:
        """Set item in cache with current timestamp."""
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Remove oldest item (LRU)
                oldest_key = min(self._cache.items(), key=lambda x: x[1][1])[0]
                del self._cache[oldest_key]
                
            self._cache[key] = (value, time.time())
            
    def clear(self) -> None:
        """Clear all items from cache."""
        with self._lock:
            self._cache.clear()

# Global cache instance
_cache = Cache()

def cache_api_response(ttl: int = 300):
    """
    Decorator to cache API responses.
    
    Args:
        ttl: Time to live in seconds (default 5 minutes)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            try:
                # Try to get from cache first
                cached_value = _cache.get(key)
                if cached_value is not None:
                    if DEBUG:
                        logger.info(f"🎯 Cache HIT for {key}")
                    return cached_value
                    
                # If not in cache, call function and cache result
                result = func(*args, **kwargs)
                _cache.set(key, result)
                if DEBUG:
                    logger.info(f"💾 Cache MISS - stored new result for {key}")
                return result
                
            except Exception as e:
                logger.error(f"Cache error for {key}: {str(e)}")
                # On cache error, call function directly
                return func(*args, **kwargs)
                
        return wrapper
    return decorator
