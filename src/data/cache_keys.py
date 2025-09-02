"""Cache key generation utilities for consistent caching."""

import hashlib
from typing import Any, List, Dict, Optional


def normalize_parameters(params: Dict[str, Any]) -> str:
    """Normalize parameters for consistent cache key generation."""
    # Sort parameters and handle None values consistently
    normalized = {}
    for key, value in sorted(params.items()):
        if value is None:
            normalized[key] = "none"
        elif isinstance(value, list):
            # Sort list items for consistency
            normalized[key] = ",".join(sorted(str(v) for v in value))
        else:
            normalized[key] = str(value)

    # Create deterministic string representation
    parts = [f"{k}={v}" for k, v in normalized.items()]
    return "&".join(parts)


def generate_cache_key(base_key: str, **params) -> str:
    """Generate a consistent cache key from base key and parameters."""
    if not params:
        return base_key

    param_string = normalize_parameters(params)
    return f"{base_key}_{param_string}"


def generate_hash_key(data: str, max_length: int = 250) -> str:
    """Generate a hash-based cache key for very long parameter strings."""
    if len(data) <= max_length:
        return data

    # Use SHA256 hash for very long keys
    hash_obj = hashlib.sha256(data.encode())
    return f"{data[:100]}_{hash_obj.hexdigest()[:16]}"


def create_prices_cache_key(ticker: str, start_date: str, end_date: str) -> str:
    """Create a cache key for price data."""
    return generate_cache_key("prices",
                             ticker=ticker,
                             start_date=start_date,
                             end_date=end_date)


def create_financial_metrics_cache_key(ticker: str, end_date: str,
                                     period: str = "ttm", limit: int = 10) -> str:
    """Create a cache key for financial metrics."""
    return generate_cache_key("financial_metrics",
                             ticker=ticker,
                             end_date=end_date,
                             period=period,
                             limit=limit)


def create_line_items_cache_key(ticker: str, end_date: str,
                               period: str = "ttm", limit: int = 10) -> str:
    """Create a cache key for line items."""
    return generate_cache_key("line_items",
                             ticker=ticker,
                             end_date=end_date,
                             period=period,
                             limit=limit)


def create_insider_trades_cache_key(ticker: str, end_date: str,
                                   start_date: Optional[str] = None,
                                   limit: int = 1000) -> str:
    """Create a cache key for insider trades."""
    return generate_cache_key("insider_trades",
                             ticker=ticker,
                             start_date=start_date,
                             end_date=end_date,
                             limit=limit)


def create_company_news_cache_key(ticker: str, end_date: str,
                                 start_date: Optional[str] = None,
                                 limit: int = 1000) -> str:
    """Create a cache key for company news."""
    return generate_cache_key("company_news",
                             ticker=ticker,
                             start_date=start_date,
                             end_date=end_date,
                             limit=limit)


def create_line_item_search_cache_key(ticker: str, line_items: List[str],
                                     end_date: str, period: str = "ttm",
                                     limit: int = 10) -> str:
    """Create a cache key for line item search."""
    # Sort line items for consistent key generation
    sorted_items = sorted(line_items)
    key = generate_cache_key("line_item_search",
                           ticker=ticker,
                           line_items=sorted_items,
                           end_date=end_date,
                           period=period,
                           limit=limit)

    # Use hash if key is too long
    return generate_hash_key(key)


def validate_cache_key(cache_key: str) -> bool:
    """Validate that a cache key is properly formatted."""
    if not cache_key:
        return False

    # Check for reasonable length
    if len(cache_key) > 500:
        return False

    # Check for invalid characters
    invalid_chars = ['\n', '\r', '\t', '\0']
    for char in invalid_chars:
        if char in cache_key:
            return False

    return True
