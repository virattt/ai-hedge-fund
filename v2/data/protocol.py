"""Data provider protocol — the interface all data sources implement.

Any class with these methods can be used as a data provider throughout
the v2 pipeline. No inheritance required — Python's structural typing
handles the rest.

Example::

    class YFinanceClient:
        def get_prices(self, ticker, start_date, end_date, **kwargs):
            # fetch from yfinance, return list[Price]
            ...

    # Works anywhere the pipeline expects a DataClient
    client: DataClient = YFinanceClient()
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from v2.data.models import (
    CompanyFacts,
    CompanyNews,
    Earnings,
    EarningsRecord,
    FinancialMetrics,
    InsiderTrade,
    Price,
)


@runtime_checkable
class DataClient(Protocol):
    """Protocol that all data providers must satisfy.

    Contract: empty list / None means the data genuinely doesn't exist.
    Infrastructure failures (auth, rate limits, network, server errors)
    must RAISE — a provider that silently returns empty on failure poisons
    backtests, because missing data is indistinguishable from "no signal".

    get_financial_metrics must be point-in-time: return only data that was
    publicly filed by *end_date*, not data whose fiscal period ended by then.
    """

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        **kwargs,
    ) -> list[Price]: ...

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
    ) -> list[FinancialMetrics]: ...

    def get_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[CompanyNews]: ...

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[InsiderTrade]: ...

    def get_company_facts(self, ticker: str) -> CompanyFacts | None: ...

    def get_earnings(self, ticker: str) -> Earnings | None: ...

    def get_earnings_history(
        self,
        ticker: str,
        limit: int = 12,
    ) -> list[EarningsRecord]: ...

    def get_market_cap(self, ticker: str, end_date: str) -> float | None: ...
