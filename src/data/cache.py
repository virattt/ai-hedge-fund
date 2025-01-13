class Cache:
    """In-memory cache for API responses."""
    def __init__(self):
        self._prices_cache: dict[str, list[dict[str, any]]] = {}
        self._financial_metrics_cache: dict[str, list[dict[str, any]]] = {}
        self._line_items_cache: dict[str, list[dict[str, any]]] = {}
        self._insider_trades_cache: dict[str, list[dict[str, any]]] = {}
    
    def get_prices(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached price data if available."""
        return self._prices_cache.get(ticker)
    
    def set_prices(self, ticker: str, data: list[dict[str, any]]):
        """Cache price data."""
        self._prices_cache[ticker] = data
    
    def get_financial_metrics(self, ticker: str) -> list[dict[str, any]]:
        """Get cached financial metrics if available."""
        return self._financial_metrics_cache.get(ticker)
    
    def set_financial_metrics(self, ticker: str, data: list[dict[str, any]]):
        """Cache financial metrics data."""
        self._financial_metrics_cache[ticker] = data
    
    def get_line_items(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached line items if available."""
        return self._line_items_cache.get(ticker)
    
    def set_line_items(self, ticker: str, data: list[dict[str, any]]):
        """Cache line items data."""
        self._line_items_cache[ticker] = data
    
    def get_insider_trades(self, ticker: str) -> list[dict[str, any]] | None:
        """Get cached insider trades if available."""
        return self._insider_trades_cache.get(ticker)
    
    def set_insider_trades(self, ticker: str, data: list[dict[str, any]]):
        """Cache insider trades data."""
        self._insider_trades_cache[ticker] = data

# Global cache instance
_cache = Cache()

def get_cache() -> Cache:
    """Get the global cache instance."""
    return _cache 