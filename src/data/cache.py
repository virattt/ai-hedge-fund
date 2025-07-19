# DEPRECATED: This file is kept for backward compatibility
# Use src.data.cache_factory.get_cache() instead

from src.data.cache_factory import get_cache as get_cache_new
from src.data.memory_cache import MemoryCache


class Cache(MemoryCache):
    """Legacy cache class - use CacheFactory instead."""
    
    def __init__(self):
        super().__init__()
        import warnings
        warnings.warn(
            "Cache class is deprecated. Use CacheFactory.get_cache() instead.",
            DeprecationWarning,
            stacklevel=2
        )


# Global cache instance - deprecated
_cache = None


def get_cache():
    """Get the global cache instance - now uses the new factory system."""
    return get_cache_new()
