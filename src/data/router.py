"""Data router: fallback chain across providers with optional file cache."""

from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    InsiderTrade,
    LineItem,
    Price,
)

from src.data.providers.base import DataProvider
from src.data.providers.financial_datasets import FinancialDatasetsProvider
from src.data.providers.alpha_vantage_provider import AlphaVantageProvider

try:
    from src.data.providers.yfinance_provider import YFinanceProvider
    _HAS_YFINANCE = True
except ImportError:
    _HAS_YFINANCE = False


class DataRouter:
    """
    Tries providers in order; first non-empty result is returned and cached.
    Priority: FinancialDatasets -> yfinance -> AlphaVantage.
    """

    def __init__(
        self,
        cache=None,
        api_key: str | None = None,
    ):
        self._cache = cache
        self._api_key = api_key
        self._providers: list[DataProvider] = [
            FinancialDatasetsProvider(api_key=api_key),
        ]
        if _HAS_YFINANCE:
            self._providers.append(YFinanceProvider())
        self._providers.append(AlphaVantageProvider())

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        api_key: str | None = None,
    ) -> list[Price]:
        cache_key = f"{ticker}_{start_date}_{end_date}"
        if self._cache:
            cached = self._cache.get_prices(cache_key)
            if cached:
                return [Price(**d) for d in cached]
        key = api_key or self._api_key
        for p in self._providers:
            try:
                out = p.get_prices(ticker, start_date, end_date, api_key=key)
                if out:
                    if self._cache:
                        self._cache.set_prices(cache_key, [x.model_dump() for x in out])
                    return out
            except Exception:
                continue
        return []

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        api_key: str | None = None,
    ) -> list[FinancialMetrics]:
        cache_key = f"{ticker}_{period}_{end_date}_{limit}"
        if self._cache:
            cached = self._cache.get_financial_metrics(cache_key)
            if cached:
                return [FinancialMetrics(**d) for d in cached]
        key = api_key or self._api_key
        for p in self._providers:
            try:
                out = p.get_financial_metrics(
                    ticker, end_date, period=period, limit=limit, api_key=key
                )
                if out:
                    if self._cache:
                        self._cache.set_financial_metrics(
                            cache_key, [x.model_dump() for x in out]
                        )
                    return out
            except Exception:
                continue
        return []

    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        api_key: str | None = None,
    ) -> list[CompanyNews]:
        cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
        if self._cache:
            cached = self._cache.get_company_news(cache_key)
            if cached:
                return [CompanyNews(**d) for d in cached]
        key = api_key or self._api_key
        for p in self._providers:
            try:
                out = p.get_company_news(
                    ticker, end_date, start_date=start_date, limit=limit, api_key=key
                )
                if out:
                    if self._cache:
                        self._cache.set_company_news(
                            cache_key, [x.model_dump() for x in out]
                        )
                    return out
            except Exception:
                continue
        return []

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        api_key: str | None = None,
    ) -> list[InsiderTrade]:
        cache_key = f"{ticker}_{start_date or 'none'}_{end_date}_{limit}"
        if self._cache:
            cached = self._cache.get_insider_trades(cache_key)
            if cached:
                return [InsiderTrade(**d) for d in cached]
        key = api_key or self._api_key
        for p in self._providers:
            try:
                out = p.get_insider_trades(
                    ticker, end_date, start_date=start_date, limit=limit, api_key=key
                )
                if out:
                    if self._cache:
                        self._cache.set_insider_trades(
                            cache_key, [x.model_dump() for x in out]
                        )
                    return out
            except Exception:
                continue
        return []

    def get_market_cap(
        self,
        ticker: str,
        end_date: str,
        api_key: str | None = None,
    ) -> float | None:
        key = api_key or self._api_key
        for p in self._providers:
            try:
                v = p.get_market_cap(ticker, end_date, api_key=key)
                if v is not None:
                    return v
            except Exception:
                continue
        return None

    def search_line_items(
        self,
        ticker: str,
        line_items: list[str],
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        api_key: str | None = None,
    ) -> list[LineItem]:
        cache_key = f"{ticker}_{','.join(sorted(line_items))}_{end_date}_{period}_{limit}"
        if self._cache:
            cached = self._cache.get_line_items(cache_key)
            if cached:
                return [LineItem(**d) for d in cached]
        key = api_key or self._api_key
        for p in self._providers:
            try:
                out = p.search_line_items(
                    ticker, line_items, end_date, period=period, limit=limit, api_key=key
                )
                if out:
                    if self._cache:
                        self._cache.set_line_items(
                            cache_key, [x.model_dump() for x in out]
                        )
                    return out
            except Exception:
                continue
        return []
