from datetime import datetime
from enum import Enum
from typing import Any

import pandas as pd
from pydantic import BaseModel

from data.cache import MemoryCache
from data.models import (
    CompanyNews,
    CompanyNewsResponse,
    FinancialMetrics,
    FinancialMetricsResponse,
    InsiderTrade,
    InsiderTradeResponse,
    LineItem,
    LineItemResponse,
    Price,
    PriceResponse,
)

from .base import BaseAPIClient
from .config import FinancialDatasetAPIConfig


class Period(str, Enum):
    """Enumeration of valid reporting periods."""

    TTM = "ttm"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class FinancialDatasetAPI(BaseAPIClient):
    """Client for accessing financial dataset API endpoints with caching."""

    def __init__(self, config: FinancialDatasetAPIConfig | None = None):
        self.config = config or FinancialDatasetAPIConfig.from_env()
        self.cache = MemoryCache()
        super().__init__(self.config)

    def _get_headers(self) -> dict[str, str]:
        return {"X-API-KEY": self.config.api_key}

    def _fetch_with_pagination(
        self,
        endpoint: str,
        params: dict,
        response_model: BaseModel,
        data_field: str,
        start_date: str | None = None,
        date_field: str = "date",
        limit: int = 1000,
    ) -> list[Any]:
        all_data = []
        current_end_date = params.get("end_date")

        while True:
            response = self._make_request(
                endpoint=endpoint, params=params, response_model=response_model
            )

            batch_data = self._get_data_or_raise(
                response, data_field, f"No {data_field} found"
            )
            all_data.extend(batch_data)

            if not start_date or len(batch_data) < limit:
                break

            current_end_date = min(
                getattr(item, date_field) for item in batch_data
            ).split("T")[0]

            if current_end_date <= start_date:
                break

            params["end_date"] = current_end_date

        return all_data

    @staticmethod
    def _process_price_data(prices: list[dict[str, Any]]) -> pd.DataFrame:
        df = pd.DataFrame(prices)
        df["Date"] = pd.to_datetime(df["time"])
        df.set_index("Date", inplace=True)

        numeric_cols = ["open", "close", "high", "low", "volume"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df.sort_index()

    def search_line_items(
        self,
        ticker: str,
        line_items: list[str],
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
    ) -> list[LineItem]:
        """
        Search for specific line items in financial statements.
        """
        cache_key = f"line_items:{ticker}_{period}_{'-'.join(sorted(line_items))}"

        if cached_data := self.cache.get(cache_key):
            filtered_data = [
                LineItem(**item)
                for item in cached_data
                if item["report_period"] <= end_date
            ]
            if filtered_data:
                return sorted(
                    filtered_data, key=lambda x: x.report_period, reverse=True
                )[:limit]

        body = {
            "tickers": [ticker],
            "line_items": line_items,
            "end_date": end_date,
            "period": period,
            "limit": limit,
        }

        response = self._make_request(
            endpoint="/financials/search/line-items",
            method="POST",
            json_data=body,
            response_model=LineItemResponse,
        )

        search_results = self._get_data_or_raise(
            response, "search_results", "No line items found"
        )

        if search_results:
            self.cache.set(cache_key, [item.model_dump() for item in search_results])

        return search_results[:limit]

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[InsiderTrade]:
        """
        Fetch insider trades for a company within a date range.
        """
        cache_key = f"insider_trades:{ticker}"

        if cached_data := self.cache.get(cache_key):
            filtered_data = [
                InsiderTrade(**trade)
                for trade in cached_data
                if (
                    not start_date
                    or (trade.get("transaction_date") or trade["filing_date"])
                    >= start_date
                )
                and (trade.get("transaction_date") or trade["filing_date"]) <= end_date
            ]
            if filtered_data:
                return sorted(
                    filtered_data,
                    key=lambda x: x.transaction_date or x.filing_date,
                    reverse=True,
                )

        params = {"ticker": ticker, "filing_date_lte": end_date, "limit": limit}
        if start_date:
            params["filing_date_gte"] = start_date

        trades = self._fetch_with_pagination(
            endpoint="/insider-trades/",
            params=params,
            response_model=InsiderTradeResponse,
            data_field="insider_trades",
            start_date=start_date,
            date_field="filing_date",
        )

        if trades:
            self.cache.set(cache_key, [trade.model_dump() for trade in trades])

        return trades

    def get_financial_metrics(
        self,
        ticker: str,
        report_period: str | datetime,
        period: Period | str = Period.TTM,
        limit: int = 1,
    ) -> list[FinancialMetrics]:
        """
        Fetch financial metrics for a company.
        """
        cache_key = f"financial_metrics:{ticker}_{period}"

        if cached_data := self.cache.get(cache_key):
            filtered_data = [
                FinancialMetrics(**metric)
                for metric in cached_data
                if metric["report_period"] <= str(report_period)
            ]
            if filtered_data:
                return sorted(
                    filtered_data, key=lambda x: x.report_period, reverse=True
                )[:limit]

        params = {
            "ticker": ticker,
            "report_period_lte": report_period,
            "limit": limit,
            "period": period,
        }

        response = self._make_request(
            endpoint="/financial-metrics/",
            params=params,
            response_model=FinancialMetricsResponse,
        )

        metrics = self._get_data_or_raise(
            response, "financial_metrics", "No financial metrics found"
        )
        self.cache.set(cache_key, [m.model_dump() for m in metrics])
        return metrics

    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[CompanyNews]:
        """
        Fetch company news within a date range.
        """
        cache_key = f"company_news:{ticker}"

        if cached_data := self.cache.get(cache_key):
            filtered_data = [
                CompanyNews(**news)
                for news in cached_data
                if (not start_date or news["date"] >= start_date)
                and news["date"] <= end_date
            ]
            if filtered_data:
                return sorted(filtered_data, key=lambda x: x.date, reverse=True)

        params = {"ticker": ticker, "end_date": end_date, "limit": limit}
        if start_date:
            params["start_date"] = start_date

        news_items = self._fetch_with_pagination(
            endpoint="/news/",
            params=params,
            response_model=CompanyNewsResponse,
            data_field="news",
            start_date=start_date,
        )

        self.cache.set(cache_key, [news.model_dump() for news in news_items])
        return news_items

    def get_prices(
        self,
        ticker: str,
        start_date: str | datetime,
        end_date: str | datetime,
        interval_multiplier: int = 1,
    ) -> pd.DataFrame:
        """
        Fetch price data for a company within a date range.
        """
        cache_key = f"prices:{ticker}"

        if cached_data := self.cache.get(cache_key):
            filtered_data = [
                Price(**price)
                for price in cached_data
                if start_date <= price["time"] <= end_date
            ]
            if filtered_data:
                return self._process_price_data(
                    [price.model_dump() for price in filtered_data]
                )

        params = {
            "ticker": ticker,
            "interval": "day",
            "interval_multiplier": interval_multiplier,
            "start_date": start_date,
            "end_date": end_date,
        }

        response = self._make_request(
            endpoint="/prices/", params=params, response_model=PriceResponse
        )

        prices = self._get_data_or_raise(response, "prices", "No price data found")
        self.cache.set(cache_key, [p.model_dump() for p in prices])

        return self._process_price_data([p.model_dump() for p in prices])

    def get_market_cap(self, ticker: str, end_date: str | datetime) -> float:
        """
        Fetch the market capitalization for a company.
        """
        financial_metrics = self.get_financial_metrics(ticker, end_date)
        market_cap = financial_metrics[0].market_cap

        return market_cap if market_cap else None
