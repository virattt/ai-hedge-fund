"""Composite data client — Alpaca prices/news + Finnhub fundamentals."""

from __future__ import annotations

from integrations.data.alpaca_client import AlpacaDataClient
from integrations.data.config import DataConfig, validate_composite_config
from integrations.data.finnhub_client import FinnhubDataClient
from v2.data.models import (
    CompanyFacts,
    CompanyNews,
    Earnings,
    EarningsRecord,
    FinancialMetrics,
    InsiderTrade,
    Price,
)


class CompositeDataClient:
    """v2 DataClient backed by Alpaca (market data) and Finnhub (fundamentals)."""

    def __init__(self, config: DataConfig) -> None:
        validate_composite_config(config)
        self._config = config
        self._alpaca = AlpacaDataClient(config)
        self._finnhub = FinnhubDataClient(config)

    def close(self) -> None:
        self._finnhub.close()

    def __enter__(self) -> CompositeDataClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        **kwargs,
    ) -> list[Price]:
        return self._alpaca.get_prices(ticker, start_date, end_date, **kwargs)

    def get_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[CompanyNews]:
        return self._alpaca.get_news(ticker, end_date, start_date, limit)

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
    ) -> list[FinancialMetrics]:
        return self._finnhub.get_financial_metrics(ticker, end_date, period, limit)

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[InsiderTrade]:
        return self._finnhub.get_insider_trades(ticker, end_date, start_date, limit)

    def get_company_facts(self, ticker: str) -> CompanyFacts | None:
        return self._finnhub.get_company_facts(ticker)

    def get_earnings(self, ticker: str) -> Earnings | None:
        return self._finnhub.get_earnings(ticker)

    def get_earnings_history(self, ticker: str, limit: int = 12) -> list[EarningsRecord]:
        return self._finnhub.get_earnings_history(ticker, limit)

    def get_market_cap(self, ticker: str, end_date: str) -> float | None:
        return self._finnhub.get_market_cap(ticker, end_date)

    def search_line_items(
        self,
        ticker: str,
        line_items: list[str],
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
    ) -> list[dict]:
        return self._finnhub.search_line_items(ticker, line_items, end_date, period, limit)
