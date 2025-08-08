import json
import os
from pathlib import Path
from typing import Any
from datetime import datetime, timedelta
import logging

import duckdb

from src.data.cache_interface import CacheInterface

# Configure logging
logger = logging.getLogger(__name__)


class DuckDBCache(CacheInterface):
    """DuckDB-based persistent cache implementation."""

    def __init__(self, db_path: str = "cache/data.db", ttl_seconds: int = None):
        """Initialize DuckDB cache with database file."""
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds

        # Create cache directory if it doesn't exist
        cache_dir = Path(db_path).parent
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize connection
        self.conn = duckdb.connect(str(db_path))
        self._create_tables()
        print(f"DuckDB cache initialized at {db_path}")
        if ttl_seconds:
            print(f"Cache TTL set to {ttl_seconds} seconds")

    def _merge_data(self, existing: list[dict] | None, new_data: list[dict], key_field: str) -> list[dict]:
        """Merge existing and new data, avoiding duplicates based on a key field."""
        if not existing:
            return new_data

        # Create a set of existing keys for O(1) lookup
        existing_keys = {item[key_field] for item in existing}

        # Only add items that don't exist yet
        merged = existing.copy()
        merged.extend([item for item in new_data if item[key_field] not in existing_keys])
        return merged

    def _create_tables(self) -> None:
        """Create cache tables if they don't exist."""
        tables = [
            ("prices", "cache_key VARCHAR PRIMARY KEY, data JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("financial_metrics", "cache_key VARCHAR PRIMARY KEY, data JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("line_items", "cache_key VARCHAR PRIMARY KEY, data JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("insider_trades", "cache_key VARCHAR PRIMARY KEY, data JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("company_news", "cache_key VARCHAR PRIMARY KEY, data JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("line_item_search", "cache_key VARCHAR PRIMARY KEY, data JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ]

        for table_name, schema in tables:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    {schema}
                )
            """)

    def _get_data(self, table_name: str, cache_key: str) -> list[dict[str, Any]] | None:
        """Generic method to get data from a table with TTL check."""
        try:
            # Check if expired first
            if self.is_expired(cache_key, table_name):
                # Remove expired entry
                self.conn.execute(
                    f"DELETE FROM {table_name} WHERE cache_key = ?",
                    [cache_key]
                )
                logger.debug(f"Removed expired cache entry: {table_name}:{cache_key}")
                return None

            result = self.conn.execute(
                f"SELECT data FROM {table_name} WHERE cache_key = ?",
                [cache_key]
            ).fetchone()

            if result:
                logger.debug(f"Cache hit for {table_name}:{cache_key}")
                return json.loads(result[0])
            else:
                logger.debug(f"Cache miss for {table_name}:{cache_key}")
                return None
        except Exception as e:
            logger.error(f"Error getting data from cache {table_name}:{cache_key}: {e}")
            return None

    def is_expired(self, cache_key: str, table_name: str) -> bool:
        """Check if a cache entry is expired."""
        if not self.ttl_seconds:
            return False

        try:
            result = self.conn.execute(
                f"SELECT created_at FROM {table_name} WHERE cache_key = ?",
                [cache_key]
            ).fetchone()

            if not result:
                return False

            # Handle both string and datetime formats
            created_at_str = result[0]
            if isinstance(created_at_str, str):
                # Parse ISO format datetime string
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            else:
                # Assume it's already a datetime object
                created_at = created_at_str

            return datetime.now() - created_at > timedelta(seconds=self.ttl_seconds)
        except Exception as e:
            logger.error(f"Error checking expiration for {table_name}:{cache_key}: {e}")
            return False

    def cleanup_expired(self) -> None:
        """Remove expired cache entries."""
        if not self.ttl_seconds:
            return

        try:
            cutoff_time = datetime.now() - timedelta(seconds=self.ttl_seconds)
            tables = ["prices", "financial_metrics", "line_items", "insider_trades", "company_news", "line_item_search"]

            for table in tables:
                # Use SQL datetime comparison instead of manual parsing
                result = self.conn.execute(
                    f"DELETE FROM {table} WHERE datetime(created_at) < datetime(?)",
                    [cutoff_time.isoformat()]
                )
                # Note: DuckDB doesn't return rowcount directly, so we can't easily get the count
                logger.debug(f"Cleaned up expired entries from {table}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def _set_data(self, table_name: str, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Generic method to set data in a table with merging support."""
        try:
            logger.debug(f"Caching data for {table_name} with key: {cache_key}")

            # Get existing data to merge with new data
            existing_data = self._get_data(table_name, cache_key)

            # Determine the key field for merging based on table type
            key_field_map = {
                "prices": "time",
                "financial_metrics": "report_period",
                "line_items": "report_period",
                "insider_trades": "filing_date",
                "company_news": "date",
                "line_item_search": None  # Line item search results don't need merging
            }

            key_field = key_field_map.get(table_name)
            if key_field and existing_data:
                # Merge data to avoid duplicates
                merged_data = self._merge_data(existing_data, data, key_field)
                json_data = json.dumps(merged_data)
                logger.debug(f"Merged {len(data)} new items with {len(existing_data)} existing items for {table_name}:{cache_key}")
            else:
                # No existing data or no key field, just store new data
                json_data = json.dumps(data)
                logger.debug(f"Stored {len(data)} new items for {table_name}:{cache_key}")

            self.conn.execute(
                f"INSERT OR REPLACE INTO {table_name} (cache_key, data) VALUES (?, ?)",
                [cache_key, json_data]
            )
        except Exception as e:
            logger.error(f"Error setting data in cache {table_name}:{cache_key}: {e}")
            raise

    def get_prices(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached price data if available."""
        return self._get_data("prices", cache_key)

    def set_prices(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache price data."""
        self._set_data("prices", cache_key, data)

    def get_financial_metrics(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached financial metrics if available."""
        return self._get_data("financial_metrics", cache_key)

    def set_financial_metrics(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache financial metrics."""
        self._set_data("financial_metrics", cache_key, data)

    def get_line_items(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached line items if available."""
        return self._get_data("line_items", cache_key)

    def set_line_items(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache line items."""
        self._set_data("line_items", cache_key, data)

    def get_insider_trades(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached insider trades if available."""
        return self._get_data("insider_trades", cache_key)

    def set_insider_trades(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache insider trades."""
        self._set_data("insider_trades", cache_key, data)

    def get_company_news(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached company news if available."""
        return self._get_data("company_news", cache_key)

    def set_company_news(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache company news."""
        self._set_data("company_news", cache_key, data)

    def get_line_item_search(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Get cached line item search results if available."""
        return self._get_data("line_item_search", cache_key)

    def set_line_item_search(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Cache line item search results."""
        self._set_data("line_item_search", cache_key, data)

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def __del__(self):
        """Ensure connection is closed when object is destroyed."""
        self.close()

    def clear_cache(self) -> None:
        """Clear all cached data (useful for testing)."""
        tables = ["prices", "financial_metrics", "line_items", "insider_trades", "company_news", "line_item_search"]
        for table in tables:
            self.conn.execute(f"DELETE FROM {table}")

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics for monitoring."""
        stats = {}
        tables = ["prices", "financial_metrics", "line_items", "insider_trades", "company_news", "line_item_search"]

        for table in tables:
            count = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[table] = count

        return stats
