import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, TypedDict


class CacheConfig(TypedDict, total=False):
    """Configuration options for the SQLite cache."""
    db_path: str  # Path to SQLite database file
    default_ttl: Optional[int]  # Default TTL in seconds


class SQLiteCache:
    """SQLite-based persistent cache for API responses."""

    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize the SQLite cache.
        
        Args:
            config: Optional configuration dictionary
        """
        self._lock = threading.RLock()
        self._config = config or {}
        self._db_path = self._config.get("db_path", "financial_data_cache.db")
        self._default_ttl = self._config.get("default_ttl", 86400)  # Default: 1 day in seconds
        
        # Ensure database directory exists
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database tables
        self._init_db()

    def _init_db(self):
        """Initialize database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create a table for each data type
            for table_name in ["prices", "financial_metrics", "line_items", "insider_trades", "company_news"]:
                cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    ticker TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    key_field TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER,
                    last_accessed INTEGER NOT NULL,
                    PRIMARY KEY (ticker)
                )
                """)
            
            conn.commit()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _cleanup_expired(self, table_name: str):
        """Remove expired entries from a table."""
        now = int(datetime.now().timestamp())
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {table_name} WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))
                conn.commit()
    
    def _merge_data(self, existing_json: Optional[str], new_data: List[Dict[str, Any]], 
                   key_field: str) -> List[Dict[str, Any]]:
        """Merge existing and new data, avoiding duplicates based on a key field."""
        if not existing_json:
            return new_data

        try:
            existing = json.loads(existing_json)
            
            # Create a set of existing keys for O(1) lookup
            existing_keys = {item.get(key_field) for item in existing if key_field in item}
            
            # Only add items that don't exist yet
            merged = existing.copy()
            merged.extend([item for item in new_data if key_field in item and item[key_field] not in existing_keys])
            return merged
        except json.JSONDecodeError:
            # If existing data is corrupt, just return new data
            return new_data
    
    def _get_from_cache(self, table_name: str, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Common method to retrieve and update data from a specific cache table."""
        with self._lock:
            # First clean up expired entries
            self._cleanup_expired(table_name)
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT data_json FROM {table_name} WHERE ticker = ?", 
                    (ticker,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                # Update last accessed time
                now = int(datetime.now().timestamp())
                cursor.execute(
                    f"UPDATE {table_name} SET last_accessed = ? WHERE ticker = ?",
                    (now, ticker)
                )
                conn.commit()
                
                try:
                    return json.loads(row['data_json'])
                except json.JSONDecodeError:
                    # If data is corrupt, remove it
                    cursor.execute(f"DELETE FROM {table_name} WHERE ticker = ?", (ticker,))
                    conn.commit()
                    return None
    
    def _set_to_cache(self, table_name: str, ticker: str, data: List[Dict[str, Any]], 
                     key_field: str, ttl: Optional[int] = None) -> None:
        """Common method to set data in a specific cache table."""
        if not data:
            return
            
        with self._lock:
            now = int(datetime.now().timestamp())
            
            # Calculate expiry time
            expires_at = None
            if ttl is not None:
                expires_at = now + ttl
            elif self._default_ttl is not None:
                expires_at = now + self._default_ttl
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # First check if entry exists
                cursor.execute(
                    f"SELECT data_json FROM {table_name} WHERE ticker = ?", 
                    (ticker,)
                )
                row = cursor.fetchone()
                
                existing_json = row['data_json'] if row else None
                merged_data = self._merge_data(existing_json, data, key_field)
                
                # Convert merged data back to JSON
                data_json = json.dumps(merged_data)
                
                # Insert or replace
                cursor.execute(
                    f"""
                    INSERT OR REPLACE INTO {table_name} 
                    (ticker, data_json, key_field, created_at, expires_at, last_accessed)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (ticker, data_json, key_field, now, expires_at, now)
                )
                conn.commit()
    
    # Price data methods
    def get_prices(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached price data if available."""
        return self._get_from_cache("prices", ticker)
    
    def set_prices(self, ticker: str, data: List[Dict[str, Any]], ttl: Optional[int] = None) -> None:
        """Cache price data with optional TTL in seconds."""
        self._set_to_cache("prices", ticker, data, "time", ttl)
    
    # Financial metrics methods
    def get_financial_metrics(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached financial metrics if available."""
        return self._get_from_cache("financial_metrics", ticker)
    
    def set_financial_metrics(self, ticker: str, data: List[Dict[str, Any]], ttl: Optional[int] = None) -> None:
        """Cache financial metrics with optional TTL in seconds."""
        self._set_to_cache("financial_metrics", ticker, data, "report_period", ttl)
    
    # Line items methods
    def get_line_items(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached line items if available."""
        return self._get_from_cache("line_items", ticker)
    
    def set_line_items(self, ticker: str, data: List[Dict[str, Any]], ttl: Optional[int] = None) -> None:
        """Cache line items with optional TTL in seconds."""
        self._set_to_cache("line_items", ticker, data, "report_period", ttl)
    
    # Insider trades methods
    def get_insider_trades(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached insider trades if available."""
        return self._get_from_cache("insider_trades", ticker)
    
    def set_insider_trades(self, ticker: str, data: List[Dict[str, Any]], ttl: Optional[int] = None) -> None:
        """Cache insider trades with optional TTL in seconds."""
        self._set_to_cache("insider_trades", ticker, data, "filing_date", ttl)
    
    # Company news methods
    def get_company_news(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached company news if available."""
        return self._get_from_cache("company_news", ticker)
    
    def set_company_news(self, ticker: str, data: List[Dict[str, Any]], ttl: Optional[int] = None) -> None:
        """Cache company news with optional TTL in seconds."""
        self._set_to_cache("company_news", ticker, data, "date", ttl)
    
    def clear(self, ticker: Optional[str] = None, table_name: Optional[str] = None) -> None:
        """
        Clear cache entries.
        
        Args:
            ticker: If provided, clear only entries for this ticker
            table_name: If provided, clear only entries in this table
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Determine which tables to clear
                tables = ["prices", "financial_metrics", "line_items", "insider_trades", "company_news"]
                if table_name and table_name in tables:
                    tables = [table_name]
                
                # Clear specific ticker or all
                for table in tables:
                    if ticker:
                        cursor.execute(f"DELETE FROM {table} WHERE ticker = ?", (ticker,))
                    else:
                        cursor.execute(f"DELETE FROM {table}")
                
                conn.commit()
    
    def vacuum(self) -> None:
        """Run VACUUM command to optimize the database."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("VACUUM")


# Global cache instance with default settings
_cache = SQLiteCache()


def get_cache() -> SQLiteCache:
    """Get the global cache instance."""
    return _cache


def create_cache(config: CacheConfig) -> SQLiteCache:
    """Create a new cache instance with custom settings."""
    return SQLiteCache(config)


# Function to convert timedelta to seconds for TTL
def ttl_seconds(td: timedelta) -> int:
    """Convert timedelta to seconds for TTL."""
    return int(td.total_seconds())