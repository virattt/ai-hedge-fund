"""Cache monitoring and management utilities."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from src.data.cache_factory import get_cache

logger = logging.getLogger(__name__)


class CacheMonitor:
    """Monitor and manage cache performance and health."""

    def __init__(self):
        self.cache = get_cache()
        self._hit_count = 0
        self._miss_count = 0
        self._last_cleanup = datetime.now()

    def record_hit(self):
        """Record a cache hit."""
        self._hit_count += 1

    def record_miss(self):
        """Record a cache miss."""
        self._miss_count += 1

    def get_hit_rate(self) -> float:
        """Get the cache hit rate as a percentage."""
        total = self._hit_count + self._miss_count
        return (self._hit_count / total * 100) if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        stats = {
            "hits": self._hit_count,
            "misses": self._miss_count,
            "hit_rate": self.get_hit_rate(),
            "last_cleanup": self._last_cleanup.isoformat()
        }

        # Add cache-specific stats if available
        if hasattr(self.cache, 'get_cache_stats'):
            cache_stats = self.cache.get_cache_stats()
            stats.update(cache_stats)

        return stats

    def cleanup_if_needed(self, force: bool = False) -> None:
        """Cleanup expired entries if needed."""
        now = datetime.now()

        # Run cleanup every hour or when forced
        if force or (now - self._last_cleanup) > timedelta(hours=1):
            logger.info("Running cache cleanup...")

            if hasattr(self.cache, 'cleanup_expired'):
                self.cache.cleanup_expired()

            self._last_cleanup = now
            logger.info("Cache cleanup completed")

    def reset_stats(self):
        """Reset monitoring statistics."""
        self._hit_count = 0
        self._miss_count = 0
        logger.info("Cache monitoring stats reset")

    def check_cache_health(self) -> Dict[str, Any]:
        """Check overall cache health and performance."""
        stats = self.get_stats()
        health = {
            "status": "healthy",
            "issues": [],
            "recommendations": []
        }

        # Check hit rate
        hit_rate = stats.get("hit_rate", 0)
        if hit_rate < 30:
            health["issues"].append(f"Low cache hit rate: {hit_rate:.1f}%")
            health["recommendations"].append("Consider increasing cache TTL or warming cache")

        # Check cache size (if available)
        total_entries = sum(v for k, v in stats.items() if k.endswith("_cache") or k in ["prices", "financial_metrics", "line_items", "insider_trades", "company_news", "line_item_search"])
        if total_entries > 10000:
            health["issues"].append(f"Large cache size: {total_entries} entries")
            health["recommendations"].append("Consider implementing cache size limits or more aggressive cleanup")

        if health["issues"]:
            health["status"] = "warning"

        return health


# Global cache monitor instance
_monitor = None


def get_cache_monitor() -> CacheMonitor:
    """Get the global cache monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = CacheMonitor()
    return _monitor
