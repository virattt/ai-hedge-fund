from typing import Protocol

from src.data.models import CompanyNews, FinancialMetrics, InsiderTrade, LineItem, Price


class FinancialDataProvider(Protocol):
    """Common contract for market/fundamental data providers."""

    name: str

    def get_prices(self, ticker: str, start_date: str, end_date: str, api_key: str | None = None) -> list[Price]:
        ...

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        api_key: str | None = None,
    ) -> list[FinancialMetrics]:
        ...

    def search_line_items(
        self,
        ticker: str,
        line_items: list[str],
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        api_key: str | None = None,
    ) -> list[LineItem]:
        ...

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        api_key: str | None = None,
    ) -> list[InsiderTrade]:
        ...

    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        api_key: str | None = None,
    ) -> list[CompanyNews]:
        ...

    def get_market_cap(self, ticker: str, end_date: str, api_key: str | None = None) -> float | None:
        ...
