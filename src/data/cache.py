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
                "by_type": {
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
                for cache_type in self._cache_types.keys():
                    if cache_type not in stats["by_type"]:
                        stats["by_type"][cache_type] = 0
                if "total_hits" not in stats:
                    stats["total_hits"] = 0
                return stats
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load cache stats: {e}")
            return {
                "total_hits": 0,
                "by_type": {cache_type: 0 for cache_type in self._cache_types.keys()}
            }

    def _save_stats(self):
        """Save cache statistics to file."""
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Warning: Failed to save cache stats: {e}")

    def _record_cache_hit(self, cache_type: str):
        """Record a cache hit for the given cache type."""
        if cache_type in self._cache_types:
            self.stats["total_hits"] = self.stats.get("total_hits", 0) + 1
            self.stats["by_type"][cache_type] = self.stats["by_type"].get(cache_type, 0) + 1
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
        data = self._load_from_file("prices", ticker)
        if data is not None:
            self._record_cache_hit("prices")
        return data

    def set_prices(self, ticker: str, data: list[dict[str, any]]):
        """Append new price data to cache."""
        existing = self.get_prices(ticker)
        merged = self._merge_data(existing, data, key_field="time")
        self._save_to_file("prices", ticker, merged)

    def get_financial_metrics(self, ticker: str, period: str = "ttm") -> list[dict[str, any]] | None:
        """Get cached financial metrics if available."""
        cache_key = f"{ticker}_{period}"
        data = self._load_from_file("financial_metrics", cache_key)
        if data is not None:
            self._record_cache_hit("financial_metrics")
        return data

    def set_financial_metrics(self, ticker: str, period: str, data: list[dict[str, any]]):
        """Update financial metrics cache with new data."""
        cache_key = f"{ticker}_{period}"
        existing = self.get_financial_metrics(ticker, period)
        merged = self._merge_data(existing, data, key_field="report_period")
        # Sort by report_period descending (newest first)
        merged.sort(key=lambda x: x.get("report_period", ""), reverse=True)
        self._save_to_file("financial_metrics", cache_key, merged)

    def get_latest_financial_metrics_date(self, ticker: str, period: str = "ttm") -> str | None:
        """Get the latest report_period in financial metrics cache."""
        cached_data = self.get_financial_metrics(ticker, period)
        if not cached_data:
            return None
        
        # Data should be sorted by report_period descending, so first entry is latest
        if cached_data:
            return cached_data[0].get("report_period")
        
        return None

    def get_line_items(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached line items if available."""
        data = self._load_from_file("line_items", ticker)
        if data is not None:
            self._record_cache_hit("line_items")
        return data

    def set_line_items(self, ticker: str, data: list[dict[str, any]]):
        """Append new line items to cache."""
        existing = self.get_line_items(ticker)
        merged = self._merge_data(existing, data, key_field="report_period")
        self._save_to_file("line_items", ticker, merged)

    def get_insider_trades(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached insider trades if available."""
        data = self._load_from_file("insider_trades", ticker)
        if data is not None:
            self._record_cache_hit("insider_trades")
        return data

    def set_insider_trades(self, ticker: str, data: list[dict[str, any]]):
        """Update insider trades cache with new data."""
        existing = self.get_insider_trades(ticker)
        merged = self._merge_data(existing, data, key_field="filing_date")
        # Sort by filing_date descending (newest first)
        merged.sort(key=lambda x: x.get("filing_date", ""), reverse=True)
        self._save_to_file("insider_trades", ticker, merged)

    def get_latest_insider_trade_date(self, ticker: str) -> str | None:
        """Get the latest filing_date in insider trades cache."""
        cached_data = self.get_insider_trades(ticker)
        if not cached_data:
            return None
        
        # Data should be sorted by filing_date descending, so first entry is latest
        if cached_data:
            return cached_data[0].get("filing_date")
        
        return None

    def get_company_news(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached company news if available."""
        data = self._load_from_file("company_news", ticker)
        if data is not None:
            self._record_cache_hit("company_news")
        return data

    def set_company_news(self, ticker: str, data: list[dict[str, any]]):
        """Update company news cache with new data."""
        existing = self.get_company_news(ticker)
        merged = self._merge_data(existing, data, key_field="date")
        # Sort by date descending (newest first)
        merged.sort(key=lambda x: x.get("date", ""), reverse=True)
        self._save_to_file("company_news", ticker, merged)

    def get_latest_company_news_date(self, ticker: str) -> str | None:
        """Get the latest date in company news cache."""
        cached_data = self.get_company_news(ticker)
        if not cached_data:
            return None
        
        # Data should be sorted by date descending, so first entry is latest
        if cached_data:
            return cached_data[0].get("date")
        
        return None

    def get_market_cap(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached market cap data if available."""
        data = self._load_from_file("market_cap", ticker)
        if data is not None:
            self._record_cache_hit("market_cap")
        return data

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
        by_type = stats.get("by_type", {})
        
        print("\n" + "=" * 50)
        print("缓存命中统计 (Cache Hit Statistics)")
        print("=" * 50)
        print(f"总命中次数 (Total Hits): {total_hits:,}")
        print("\n按类型统计 (By Type):")
        print("-" * 50)
        
        # Cache type display names
        type_names = {
            "prices": "价格数据 (Prices)",
            "financial_metrics": "财务指标 (Financial Metrics)",
            "line_items": "财务项目 (Line Items)",
            "insider_trades": "内部交易 (Insider Trades)",
            "company_news": "公司新闻 (Company News)",
            "market_cap": "市值 (Market Cap)",
        }
        
        for cache_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            name = type_names.get(cache_type, cache_type)
            percentage = (count / total_hits * 100) if total_hits > 0 else 0
            print(f"  {name:35s}: {count:6,} ({percentage:5.1f}%)")
        
        print("=" * 50 + "\n")


# Global cache instance
_cache = Cache()


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache
