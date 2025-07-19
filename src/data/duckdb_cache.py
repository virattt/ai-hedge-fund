import json
import os
from pathlib import Path
from typing import Any

import duckdb

from src.data.cache_interface import CacheInterface


class DuckDBCache(CacheInterface):
    """DuckDB-based persistent cache implementation."""

    def __init__(self, db_path: str = "cache/financial_data.db"):
        """Initialize DuckDB cache with database file."""
        self.db_path = db_path

        # Create cache directory if it doesn't exist
        cache_dir = Path(db_path).parent
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize connection
        self.conn = duckdb.connect(str(db_path))
        self._create_tables()
        print(f"DuckDB cache initialized at {db_path}")

    def _create_tables(self) -> None:
        """Create cache tables if they don't exist."""
        tables = [
            ("prices", "cache_key VARCHAR PRIMARY KEY, data JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("financial_metrics", "cache_key VARCHAR PRIMARY KEY, data JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("line_items", "cache_key VARCHAR PRIMARY KEY, data JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("insider_trades", "cache_key VARCHAR PRIMARY KEY, data JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("company_news", "cache_key VARCHAR PRIMARY KEY, data JSON, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ]

        for table_name, schema in tables:
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    {schema}
                )
            """)

    def _get_data(self, table_name: str, cache_key: str) -> list[dict[str, Any]] | None:
        """Generic method to get data from a table."""
        result = self.conn.execute(
            f"SELECT data FROM {table_name} WHERE cache_key = ?",
            [cache_key]
        ).fetchone()

        if result:
            return json.loads(result[0])
        return None

    def _set_data(self, table_name: str, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Generic method to set data in a table."""
        json_data = json.dumps(data)
        self.conn.execute(
            f"INSERT OR REPLACE INTO {table_name} (cache_key, data) VALUES (?, ?)",
            [cache_key, json_data]
        )

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

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def __del__(self):
        """Ensure connection is closed when object is destroyed."""
        self.close()

    def clear_cache(self) -> None:
        """Clear all cached data (useful for testing)."""
        tables = ["prices", "financial_metrics", "line_items", "insider_trades", "company_news"]
        for table in tables:
            self.conn.execute(f"DELETE FROM {table}")

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics for monitoring."""
        stats = {}
        tables = ["prices", "financial_metrics", "line_items", "insider_trades", "company_news"]

        for table in tables:
            count = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[table] = count

        return stats
