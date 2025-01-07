import time
import threading
from typing import Any, Optional, Dict, Tuple
from functools import wraps
import logging
from datetime import datetime

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

def normalize_cache_key_args(*args, **kwargs) -> str:
    """Normalize arguments for consistent cache keys."""
    # Convert args to a list for modification
    args_list = list(args)
    
    # Normalize date strings to YYYY-MM-DD format
    for i, arg in enumerate(args_list):
        if isinstance(arg, str) and len(arg) == 10 and arg[4] == '-':
            try:
                date = datetime.strptime(arg, "%Y-%m-%d")
                args_list[i] = date.strftime("%Y-%m-%d")
            except ValueError:
                pass
    
    # Sort kwargs by key for consistent ordering
    sorted_kwargs = dict(sorted(kwargs.items()))
    
    # Normalize date strings in kwargs
    for key, value in sorted_kwargs.items():
        if isinstance(value, str) and len(value) == 10 and value[4] == '-':
            try:
                date = datetime.strptime(value, "%Y-%m-%d")
                sorted_kwargs[key] = date.strftime("%Y-%m-%d")
            except ValueError:
                pass
                
    return f"{tuple(args_list)}:{sorted_kwargs}"

def cache_api_response(ttl: int = 300):
    """
    Decorator to cache API responses.
    
    Args:
        ttl: Time to live in seconds (default 5 minutes)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create normalized cache key
            normalized_args = normalize_cache_key_args(*args, **kwargs)
            key = f"{func.__name__}:{normalized_args}"
            
            try:
                # Try to get from cache first
                cached_value = _cache.get(key)
                if cached_value is not None:
                    if DEBUG:
                        logger.info(f"🎯 Cache HIT for {func.__name__} with args {normalized_args}")
                    return cached_value
                    
                # If not in cache, call function and cache result
                result = func(*args, **kwargs)
                _cache.set(key, result)
                if DEBUG:
                    logger.info(f"💾 Cache MISS - stored new result for {func.__name__} with args {normalized_args}")
                return result
                
            except Exception as e:
                logger.error(f"Cache error for {func.__name__} with args {normalized_args}: {str(e)}")
                # On cache error, call function directly
                return func(*args, **kwargs)
                
        return wrapper
    return decorator
