import json
from pathlib import Path
from urllib.parse import quote


class Cache:
    """File-based cache for API responses stored in .cache directory."""

    def __init__(self, cache_dir: str = ".cache"):
        """
        Initialize the cache with a base directory.
        
        Args:
            cache_dir: Base directory for cache files (default: ".cache")
        """
        # Cache type to subdirectory mapping
        self._cache_types = {
            "prices": "prices",
            "financial_metrics": "financial_metrics",
            "line_items": "line_items",
            "insider_trades": "insider_trades",
            "company_news": "company_news",
            "market_cap": "market_cap",
        }
        
        self.cache_dir = Path(cache_dir)
        self._ensure_cache_dirs()
        
        # Statistics file path
        self.stats_file = self.cache_dir / "cache_stats.json"
        self.stats = self._load_stats()
        
        

    def _ensure_cache_dirs(self):
        """Ensure all cache subdirectories exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        for subdir in self._cache_types.values():
            (self.cache_dir / subdir).mkdir(parents=True, exist_ok=True)

    def _load_stats(self) -> dict:
        """Load cache statistics from file."""
        if not self.stats_file.exists():
            return {
                "total_hits": 0,
                "total_api_calls": 0,
                "by_type": {
                    "prices": 0,
                    "financial_metrics": 0,
                    "line_items": 0,
                    "insider_trades": 0,
                    "company_news": 0,
                    "market_cap": 0,
                },
                "api_calls_by_type": {
                    "prices": 0,
                    "financial_metrics": 0,
                    "line_items": 0,
                    "insider_trades": 0,
                    "company_news": 0,
                    "market_cap": 0,
                }
            }
        
        try:
            with open(self.stats_file, "r", encoding="utf-8") as f:
                stats = json.load(f)
                # Ensure all cache types are present
                if "by_type" not in stats:
                    stats["by_type"] = {}
                if "api_calls_by_type" not in stats:
                    stats["api_calls_by_type"] = {}
                for cache_type in self._cache_types.keys():
                    if cache_type not in stats["by_type"]:
                        stats["by_type"][cache_type] = 0
                    if cache_type not in stats["api_calls_by_type"]:
                        stats["api_calls_by_type"][cache_type] = 0
                if "total_hits" not in stats:
                    stats["total_hits"] = 0
                if "total_api_calls" not in stats:
                    stats["total_api_calls"] = 0
                return stats
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load cache stats: {e}")
            return {
                "total_hits": 0,
                "total_api_calls": 0,
                "by_type": {cache_type: 0 for cache_type in self._cache_types.keys()},
                "api_calls_by_type": {cache_type: 0 for cache_type in self._cache_types.keys()}
            }

    def _save_stats(self):
        """Save cache statistics to file."""
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Warning: Failed to save cache stats: {e}")

    def record_cache_hit(self, cache_type: str):
        """Record a cache hit for the given cache type."""
        if cache_type in self._cache_types:
            self.stats["total_hits"] = self.stats.get("total_hits", 0) + 1
            self.stats["by_type"][cache_type] = self.stats["by_type"].get(cache_type, 0) + 1
            self._save_stats()

    def record_api_call(self, cache_type: str):
        """Record an API call for the given cache type (cache miss)."""
        if cache_type in self._cache_types:
            self.stats["total_api_calls"] = self.stats.get("total_api_calls", 0) + 1
            if "api_calls_by_type" not in self.stats:
                self.stats["api_calls_by_type"] = {}
            self.stats["api_calls_by_type"][cache_type] = self.stats["api_calls_by_type"].get(cache_type, 0) + 1
            self._save_stats()

    def _ticker_to_filename(self, ticker: str) -> str:
        """Convert ticker to a safe filename by encoding special characters."""
        # Replace common special characters with safe alternatives
        # Use URL encoding for safety
        safe_ticker = quote(ticker, safe="")
        return f"{safe_ticker}.json"

    def _get_cache_path(self, cache_type: str, ticker: str) -> Path:
        """Get the file path for a specific cache entry."""
        subdir = self._cache_types.get(cache_type)
        if not subdir:
            raise ValueError(f"Unknown cache type: {cache_type}")
        filename = self._ticker_to_filename(ticker)
        return self.cache_dir / subdir / filename

    def _get_metadata_path(self, cache_type: str, ticker: str) -> Path:
        """Get the file path for cache metadata (last_updated date)."""
        subdir = self._cache_types.get(cache_type)
        if not subdir:
            raise ValueError(f"Unknown cache type: {cache_type}")
        filename = self._ticker_to_filename(ticker)
        # Metadata file has .meta.json extension
        return self.cache_dir / subdir / f"{filename}.meta.json"

    def _load_from_file(self, cache_type: str, ticker: str) -> list[dict[str, any]] | None:
        """Load cached data from file."""
        cache_path = self._get_cache_path(cache_type, ticker)
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else None
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load cache from {cache_path}: {e}")
            return None

    def _save_to_file(self, cache_type: str, ticker: str, data: list[dict[str, any]]):
        """Save cached data to file."""
        cache_path = self._get_cache_path(cache_type, ticker)
        try:
            # Ensure parent directory exists
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Warning: Failed to save cache to {cache_path}: {e}")

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

    def get_prices(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached price data if available."""
        return self._load_from_file("prices", ticker)

    def set_prices(self, ticker: str, data: list[dict[str, any]]):
        """Append new price data to cache."""
        existing = self.get_prices(ticker)
        merged = self._merge_data(existing, data, key_field="time")
        self._save_to_file("prices", ticker, merged)

    def get_financial_metrics(self, ticker: str, period: str = "ttm") -> list[dict[str, any]] | None:
        """Get cached financial metrics if available."""
        cache_key = f"{ticker}_{period}"
        return self._load_from_file("financial_metrics", cache_key)

    def set_financial_metrics(self, ticker: str, period: str, data: list[dict[str, any]], update_date: str = None):
        """Update financial metrics cache with new data."""
        cache_key = f"{ticker}_{period}"
        existing = self.get_financial_metrics(ticker, period)
        merged = self._merge_data(existing, data, key_field="report_period")
        # Sort by report_period descending (newest first)
        merged.sort(key=lambda x: x.get("report_period", ""), reverse=True)
        self._save_to_file("financial_metrics", cache_key, merged)
        # Update last_updated date if provided
        if update_date:
            self.set_last_updated_date("financial_metrics", cache_key, update_date)

    def get_last_updated_date(self, cache_type: str, ticker: str) -> str | None:
        """Get the last updated date (query date) for a cache entry."""
        metadata_path = self._get_metadata_path(cache_type, ticker)
        if not metadata_path.exists():
            return None
        
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                return metadata.get("last_updated")
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load metadata from {metadata_path}: {e}")
            return None

    def set_last_updated_date(self, cache_type: str, ticker: str, date: str):
        """Set the last updated date (query date) for a cache entry."""
        metadata_path = self._get_metadata_path(cache_type, ticker)
        try:
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump({"last_updated": date}, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Warning: Failed to save metadata to {metadata_path}: {e}")

    def get_line_items(self, ticker: str, period: str = "ttm") -> list[dict[str, any]] | None:
        """Get cached line items if available."""
        cache_key = f"{ticker}_{period}"
        return self._load_from_file("line_items", cache_key)

    def set_line_items(self, ticker: str, period: str, data: list[dict[str, any]], update_date: str = None):
        """Update line items cache with new data."""
        cache_key = f"{ticker}_{period}"
        existing = self.get_line_items(ticker, period)
        merged = self._merge_data(existing, data, key_field="report_period")
        # Sort by report_period descending (newest first)
        merged.sort(key=lambda x: x.get("report_period", ""), reverse=True)
        self._save_to_file("line_items", cache_key, merged)
        # Update last_updated date if provided
        if update_date:
            self.set_last_updated_date("line_items", cache_key, update_date)

    def get_insider_trades(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached insider trades if available."""
        return self._load_from_file("insider_trades", ticker)

    def set_insider_trades(self, ticker: str, data: list[dict[str, any]], update_date: str = None):
        """Update insider trades cache with new data."""
        existing = self.get_insider_trades(ticker)
        merged = self._merge_data(existing, data, key_field="filing_date")
        # Sort by filing_date descending (newest first)
        merged.sort(key=lambda x: x.get("filing_date", ""), reverse=True)
        self._save_to_file("insider_trades", ticker, merged)
        # Update last_updated date if provided
        if update_date:
            self.set_last_updated_date("insider_trades", ticker, update_date)

    def get_company_news(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached company news if available."""
        return self._load_from_file("company_news", ticker)

    def set_company_news(self, ticker: str, data: list[dict[str, any]], update_date: str = None):
        """Update company news cache with new data."""
        existing = self.get_company_news(ticker)
        merged = self._merge_data(existing, data, key_field="date")
        # Sort by date descending (newest first)
        merged.sort(key=lambda x: x.get("date", ""), reverse=True)
        self._save_to_file("company_news", ticker, merged)
        # Update last_updated date if provided
        if update_date:
            self.set_last_updated_date("company_news", ticker, update_date)

    def get_market_cap(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached market cap data if available."""
        return self._load_from_file("market_cap", ticker)

    def set_market_cap(self, ticker: str, data: list[dict[str, any]]):
        """Update market cap cache with new data."""
        existing = self.get_market_cap(ticker)
        merged = self._merge_data(existing, data, key_field="date")
        # Sort by date descending (newest first)
        merged.sort(key=lambda x: x.get("date", ""), reverse=True)
        self._save_to_file("market_cap", ticker, merged)

    def get_market_cap_by_date(self, ticker: str, date: str) -> float | None:
        """Get market cap for a specific date from cache."""
        cached_data = self.get_market_cap(ticker)
        if not cached_data:
            return None
        
        # Find the entry with matching date
        for entry in cached_data:
            if entry.get("date") == date:
                return entry.get("market_cap")
        
        return None

    def get_latest_market_cap_date(self, ticker: str) -> str | None:
        """Get the latest date in market cap cache."""
        cached_data = self.get_market_cap(ticker)
        if not cached_data:
            return None
        
        # Data should be sorted by date descending, so first entry is latest
        if cached_data:
            return cached_data[0].get("date")
        
        return None

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self.stats.copy()

    def print_cache_stats(self):
        """Print cache statistics in a user-friendly format."""
        stats = self.get_cache_stats()
        total_hits = stats.get("total_hits", 0)
        total_api_calls = stats.get("total_api_calls", 0)
        by_type = stats.get("by_type", {})
        api_calls_by_type = stats.get("api_calls_by_type", {})
        
        print("\n" + "=" * 70)
        print("Cache Statistics")
        print("=" * 70)
        print(f"Total Cache Hits (API calls avoided): {total_hits:,}")
        print(f"Total API Calls: {total_api_calls:,}")
        if total_hits + total_api_calls > 0:
            cache_hit_rate = (total_hits / (total_hits + total_api_calls)) * 100
            print(f"Cache Hit Rate: {cache_hit_rate:.1f}%")
        print("\nBy Type:")
        print("-" * 70)
        
        # Cache type display names
        type_names = {
            "prices": "Prices",
            "financial_metrics": "Financial Metrics",
            "line_items": "Line Items",
            "insider_trades": "Insider Trades",
            "company_news": "Company News",
            "market_cap": "Market Cap",
        }
        
        # Print cache hits
        print("Cache Hits (API calls avoided):")
        for cache_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            name = type_names.get(cache_type, cache_type)
            percentage = (count / total_hits * 100) if total_hits > 0 else 0
            print(f"  {name:35s}: {count:6,} ({percentage:5.1f}%)")
        
        print("\nAPI Calls:")
        for cache_type, count in sorted(api_calls_by_type.items(), key=lambda x: x[1], reverse=True):
            name = type_names.get(cache_type, cache_type)
            percentage = (count / total_api_calls * 100) if total_api_calls > 0 else 0
            print(f"  {name:35s}: {count:6,} ({percentage:5.1f}%)")
        
        print("=" * 70 + "\n")


# Global cache instance
_cache = Cache()


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache
