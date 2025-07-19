import os
from enum import Enum
from typing import Optional

DEFAULT_CACHE_DB_PATH = "cache/data.db"

from src.data.cache_interface import CacheInterface
from src.data.memory_cache import MemoryCache


class CacheType(Enum):
    """Available cache backend types."""
    MEMORY = "memory"
    DUCKDB = "duckdb"


class CacheFactory:
    """Factory for creating cache instances based on configuration."""

    _instance: Optional[CacheInterface] = None

    @classmethod
    def get_cache(cls, cache_type: Optional[CacheType] = None, **kwargs) -> CacheInterface:
        """Get or create a cache instance."""
        print(f"Requesting cache instance with type: {cache_type}")
        if cls._instance is None:
            cls._instance = cls.create_cache(cache_type, **kwargs)
        return cls._instance

    @classmethod
    def create_cache(cls, cache_type: Optional[CacheType] = None, **kwargs) -> CacheInterface:
        """Create a new cache instance."""
        if cache_type is None:
            cache_type = cls._get_cache_type_from_env()

        if cache_type == CacheType.MEMORY:
            return MemoryCache()
        elif cache_type == CacheType.DUCKDB:
            try:
                from src.data.duckdb_cache import DuckDBCache
                db_path = kwargs.get("db_path", os.environ.get("CACHE_DB_PATH", DEFAULT_CACHE_DB_PATH))
                return DuckDBCache(db_path=db_path)
            except ImportError:
                print("DuckDB not available, falling back to memory cache")
                return MemoryCache()
        else:
            raise ValueError(f"Unknown cache type: {cache_type}")

    @classmethod
    def _get_cache_type_from_env(cls) -> CacheType:
        """Get cache type from environment variables."""
        cache_type_str = os.environ.get("CACHE_TYPE", "memory").lower()
        print(f"Cache type from environment: {cache_type_str}")

        try:
            return CacheType(cache_type_str)
        except ValueError:
            print(f"Unknown cache type '{cache_type_str}', defaulting to memory")
            return CacheType.MEMORY

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance (useful for testing)."""
        if cls._instance:
            cls._instance.close()
        cls._instance = None


# Convenience function to get the current cache instance
def get_cache() -> CacheInterface:
    """Get the global cache instance."""
    return CacheFactory.get_cache()


# Configuration class for more advanced cache settings
class CacheConfig:
    """Configuration for cache settings."""

    def __init__(
        self,
        cache_type: CacheType = CacheType.MEMORY,
        db_path: str = DEFAULT_CACHE_DB_PATH,
        ttl_seconds: Optional[int] = None,
    ):
        self.cache_type = cache_type
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds

    @classmethod
    def from_env(cls) -> "CacheConfig":
        """Create configuration from environment variables."""
        cache_type_str = os.environ.get("CACHE_TYPE", "memory").lower()
        try:
            cache_type = CacheType(cache_type_str)
        except ValueError:
            print(f"Unknown cache type '{cache_type_str}', defaulting to memory")
            cache_type = CacheType.MEMORY

        db_path = os.environ.get("CACHE_DB_PATH", DEFAULT_CACHE_DB_PATH)
        ttl_seconds = None
        if ttl_str := os.environ.get("CACHE_TTL_SECONDS"):
            try:
                ttl_seconds = int(ttl_str)
            except ValueError:
                print(f"Invalid TTL value '{ttl_str}', ignoring")

        return cls(
            cache_type=cache_type,
            db_path=db_path,
            ttl_seconds=ttl_seconds,
        )

    def create_cache(self) -> CacheInterface:
        """Create a cache instance from this configuration."""
        return CacheFactory.create_cache(
            cache_type=self.cache_type,
            db_path=self.db_path,
            ttl_seconds=self.ttl_seconds,
        )
