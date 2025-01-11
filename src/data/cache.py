from typing import Dict, Any, List, Optional

class Cache:
    """In-memory cache for API responses."""
    def __init__(self):
        self._prices_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._financial_metrics_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._line_items_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._insider_trades_cache: Dict[str, List[Dict[str, Any]]] = {}
    
    def get_prices(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached price data if available."""
        return self._prices_cache.get(ticker)
    
    def set_prices(self, ticker: str, data: List[Dict[str, Any]]):
        """Cache price data."""
        self._prices_cache[ticker] = data
    
    def get_financial_metrics(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached financial metrics if available."""
        return self._financial_metrics_cache.get(ticker)
    
    def set_financial_metrics(self, ticker: str, data: List[Dict[str, Any]]):
        """Cache financial metrics data."""
        self._financial_metrics_cache[ticker] = data
    
    def get_line_items(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached line items if available."""
        return self._line_items_cache.get(ticker)
    
    def set_line_items(self, ticker: str, data: List[Dict[str, Any]]):
        """Cache line items data."""
        self._line_items_cache[ticker] = data
    
    def get_insider_trades(self, ticker: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached insider trades if available."""
        return self._insider_trades_cache.get(ticker)
    
    def set_insider_trades(self, ticker: str, data: List[Dict[str, Any]]):
        """Cache insider trades data."""
        self._insider_trades_cache[ticker] = data

# Global cache instance
_cache = Cache()

def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache 