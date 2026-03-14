"""Automatic cache cleaning background task."""

import threading
import time
import logging
from typing import Optional

from src.data.cache import Cache

logger = logging.getLogger(__name__)


class CacheCleaner:
    """Background thread for periodic cache cleanup."""

    def __init__(self, cache: Cache, interval: int = 60):
        """
        Initialize cache cleaner.

        Args:
            cache: Cache instance to clean
            interval: Cleanup interval in seconds (default: 60)
        """
        self.cache = cache
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        logger.info(f"CacheCleaner initialized with interval={interval}s")

    def _cleanup_loop(self):
        """Main cleanup loop running in background thread."""
        logger.info("Cache cleanup thread started")
        while not self._stop_event.is_set():
            try:
                # Wait for interval or stop event
                if self._stop_event.wait(self.interval):
                    break

                # Perform cleanup
                removed = self.cache.cleanup_expired()
                if removed > 0:
                    logger.info(f"Cleaned up {removed} expired cache entries")
                else:
                    logger.debug("No expired cache entries to clean")

            except Exception as e:
                logger.error(f"Error in cache cleanup loop: {e}", exc_info=True)

        logger.info("Cache cleanup thread stopped")

    def start(self):
        """Start the cleanup thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Cache cleaner already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._thread.start()
        logger.info("Cache cleaner started")

    def stop(self, timeout: float = 5.0):
        """
        Stop the cleanup thread.

        Args:
            timeout: Maximum time to wait for thread to stop (default: 5.0 seconds)
        """
        if self._thread is None or not self._thread.is_alive():
            logger.warning("Cache cleaner not running")
            return

        logger.info("Stopping cache cleaner...")
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(f"Cache cleaner thread did not stop within {timeout}s")
            else:
                logger.info("Cache cleaner stopped successfully")
                self._thread = None

    def is_running(self) -> bool:
        """Check if cleanup thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
