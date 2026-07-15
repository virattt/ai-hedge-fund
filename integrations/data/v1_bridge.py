"""Bridge composite data client to v1 src.data.models types."""

from __future__ import annotations

from integrations.data.composite import CompositeDataClient
from integrations.data.config import load_data_config, validate_composite_config
from src.data.models import (
    CompanyFacts,
    CompanyNews,
    FinancialMetrics,
    InsiderTrade,
    LineItem,
    Price,
)


class V1DataAPI:
    """Drop-in data backend for src/tools/api.py using Alpaca + Finnhub."""

    def __init__(self) -> None:
        config = load_data_config()
        validate_composite_config(config)
        self._client = CompositeDataClient(config)

    def get_prices(self, ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
        rows = self._client.get_prices(ticker, start_date, end_date)
        return [
            Price(
                open=p.open,
                close=p.close,
                high=p.high,
                low=p.low,
                volume=p.volume,
                time=p.time,
            )
            for p in rows
        ]

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        api_key: str = None,
    ) -> list[FinancialMetrics]:
        rows = self._client.get_financial_metrics(ticker, end_date, period, limit)
        return [FinancialMetrics(**r.model_dump()) for r in rows]

    def search_line_items(
        self,
        ticker: str,
        line_items: list[str],
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        api_key: str = None,
    ) -> list[LineItem]:
        rows = self._client.search_line_items(ticker, line_items, end_date, period, limit)
        return [LineItem(**row) for row in rows]

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        api_key: str = None,
    ) -> list[InsiderTrade]:
        rows = self._client.get_insider_trades(ticker, end_date, start_date, limit)
        return [InsiderTrade(**r.model_dump()) for r in rows]

    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        api_key: str = None,
    ) -> list[CompanyNews]:
        rows = self._client.get_news(ticker, end_date, start_date, limit)
        return [
            CompanyNews(
                ticker=n.ticker,
                title=n.title,
                source=n.source,
                date=n.date or end_date,
                url=n.url or "",
            )
            for n in rows
        ]

    def get_market_cap(self, ticker: str, end_date: str, api_key: str = None) -> float | None:
        return self._client.get_market_cap(ticker, end_date)


_v1_api: V1DataAPI | None = None


def get_v1_api() -> V1DataAPI:
    global _v1_api
    if _v1_api is None:
        _v1_api = V1DataAPI()
    return _v1_api
