"""Financial Datasets API provider (api.financialdatasets.ai)."""

import os
import time

import requests

from src.data.models import (
    CompanyFactsResponse,
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

from .base import DataProvider


def _make_request(
    url: str,
    headers: dict,
    method: str = "GET",
    json_data: dict | None = None,
    max_retries: int = 3,
) -> requests.Response:
    for attempt in range(max_retries + 1):
        if method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        else:
            response = requests.get(url, headers=headers)

        if response.status_code == 429 and attempt < max_retries:
            delay = 60 + (30 * attempt)
            time.sleep(delay)
            continue
        return response
    return response


class FinancialDatasetsProvider(DataProvider):
    """Provider using Financial Datasets API. Supports all data types including line items."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY", "")
        self._headers = {}
        if self._api_key:
            self._headers["X-API-KEY"] = self._api_key

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        **kwargs: object,
    ) -> list[Price]:
        url = (
            f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day"
            f"&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
        )
        response = _make_request(url, self._headers)
        if response.status_code != 200:
            return []
        try:
            price_response = PriceResponse(**response.json())
            return price_response.prices or []
        except Exception:
            return []

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        **kwargs: object,
    ) -> list[FinancialMetrics]:
        url = (
            f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}"
            f"&report_period_lte={end_date}&limit={limit}&period={period}"
        )
        response = _make_request(url, self._headers)
        if response.status_code != 200:
            return []
        try:
            metrics_response = FinancialMetricsResponse(**response.json())
            return metrics_response.financial_metrics or []
        except Exception:
            return []

    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        **kwargs: object,
    ) -> list[CompanyNews]:
        all_news: list[CompanyNews] = []
        current_end = end_date
        while True:
            url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end}&limit={limit}"
            if start_date:
                url += f"&start_date={start_date}"
            response = _make_request(url, self._headers)
            if response.status_code != 200:
                break
            try:
                data = response.json()
                resp = CompanyNewsResponse(**data)
                news = resp.news or []
            except Exception:
                break
            if not news:
                break
            all_news.extend(news)
            if not start_date or len(news) < limit:
                break
            current_end = min(n.date for n in news).split("T")[0]
            if current_end <= start_date:
                break
        return all_news

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        **kwargs: object,
    ) -> list[InsiderTrade]:
        all_trades: list[InsiderTrade] = []
        current_end = end_date
        while True:
            url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end}&limit={limit}"
            if start_date:
                url += f"&filing_date_gte={start_date}"
            response = _make_request(url, self._headers)
            if response.status_code != 200:
                break
            try:
                data = response.json()
                resp = InsiderTradeResponse(**data)
                trades = resp.insider_trades or []
            except Exception:
                break
            if not trades:
                break
            all_trades.extend(trades)
            if not start_date or len(trades) < limit:
                break
            current_end = min(t.filing_date for t in trades).split("T")[0]
            if start_date and current_end <= start_date:
                break
        return all_trades

    def get_market_cap(
        self,
        ticker: str,
        end_date: str,
        **kwargs: object,
    ) -> float | None:
        import datetime

        if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
            url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
            response = _make_request(url, self._headers)
            if response.status_code == 200:
                try:
                    data = response.json()
                    resp = CompanyFactsResponse(**data)
                    return resp.company_facts.market_cap
                except Exception:
                    pass
        return super().get_market_cap(ticker, end_date, **kwargs)

    def search_line_items(
        self,
        ticker: str,
        line_items: list[str],
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        **kwargs: object,
    ) -> list[LineItem]:
        url = "https://api.financialdatasets.ai/financials/search/line-items"
        body = {
            "tickers": [ticker],
            "line_items": line_items,
            "end_date": end_date,
            "period": period,
            "limit": limit,
        }
        response = _make_request(url, self._headers, method="POST", json_data=body)
        if response.status_code != 200:
            return []
        try:
            data = response.json()
            resp = LineItemResponse(**data)
            return (resp.search_results or [])[:limit]
        except Exception:
            return []
