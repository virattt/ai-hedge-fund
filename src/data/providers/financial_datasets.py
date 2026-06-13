import datetime
import os
import time

import requests

from src.data.cache import get_cache
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
from src.data.providers.base import FinancialDataProvider

_cache = get_cache()


def _make_api_request(url: str, headers: dict, method: str = "GET", json_data: dict | None = None, max_retries: int = 3) -> requests.Response:
    """
    Make an API request with rate-limit handling and moderate backoff.
    """
    for attempt in range(max_retries + 1):
        if method.upper() == "POST":
            response = requests.post(url, headers=headers, json=json_data)
        else:
            response = requests.get(url, headers=headers)

        if response.status_code == 429 and attempt < max_retries:
            delay = 60 + (30 * attempt)
            print(f"Rate limited (429). Attempt {attempt + 1}/{max_retries + 1}. Waiting {delay}s before retrying...")
            time.sleep(delay)
            continue

        return response

    return response


class FinancialDatasetsProvider(FinancialDataProvider):
    name = "financialdatasets"

    def _headers(self, api_key: str | None = None) -> dict:
        headers = {}
        financial_api_key = api_key or os.environ.get("FINANCIAL_DATASETS_API_KEY")
        if financial_api_key:
            headers["X-API-KEY"] = financial_api_key
        return headers

    def get_prices(self, ticker: str, start_date: str, end_date: str, api_key: str | None = None) -> list[Price]:
        cache_key = f"{self.name}:{ticker}_{start_date}_{end_date}"

        if cached_data := _cache.get_prices(cache_key):
            return [Price(**price) for price in cached_data]

        url = f"https://api.financialdatasets.ai/prices/?ticker={ticker}&interval=day&interval_multiplier=1&start_date={start_date}&end_date={end_date}"
        response = _make_api_request(url, self._headers(api_key))
        if response.status_code != 200:
            return []

        try:
            prices = PriceResponse(**response.json()).prices
        except Exception:
            return []

        if not prices:
            return []

        _cache.set_prices(cache_key, [p.model_dump() for p in prices])
        return prices

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        api_key: str | None = None,
    ) -> list[FinancialMetrics]:
        cache_key = f"{self.name}:{ticker}_{period}_{end_date}_{limit}"

        if cached_data := _cache.get_financial_metrics(cache_key):
            return [FinancialMetrics(**metric) for metric in cached_data]

        url = f"https://api.financialdatasets.ai/financial-metrics/?ticker={ticker}&report_period_lte={end_date}&limit={limit}&period={period}"
        response = _make_api_request(url, self._headers(api_key))
        if response.status_code != 200:
            return []

        try:
            financial_metrics = FinancialMetricsResponse(**response.json()).financial_metrics
        except Exception:
            return []

        if not financial_metrics:
            return []

        _cache.set_financial_metrics(cache_key, [m.model_dump() for m in financial_metrics])
        return financial_metrics

    def search_line_items(
        self,
        ticker: str,
        line_items: list[str],
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
        api_key: str | None = None,
    ) -> list[LineItem]:
        url = "https://api.financialdatasets.ai/financials/search/line-items"
        body = {
            "tickers": [ticker],
            "line_items": line_items,
            "end_date": end_date,
            "period": period,
            "limit": limit,
        }
        response = _make_api_request(url, self._headers(api_key), method="POST", json_data=body)
        if response.status_code != 200:
            return []

        try:
            search_results = LineItemResponse(**response.json()).search_results
        except Exception:
            return []

        if not search_results:
            return []

        return search_results[:limit]

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        api_key: str | None = None,
    ) -> list[InsiderTrade]:
        cache_key = f"{self.name}:{ticker}_{start_date or 'none'}_{end_date}_{limit}"

        if cached_data := _cache.get_insider_trades(cache_key):
            return [InsiderTrade(**trade) for trade in cached_data]

        all_trades = []
        current_end_date = end_date

        while True:
            url = f"https://api.financialdatasets.ai/insider-trades/?ticker={ticker}&filing_date_lte={current_end_date}"
            if start_date:
                url += f"&filing_date_gte={start_date}"
            url += f"&limit={limit}"

            response = _make_api_request(url, self._headers(api_key))
            if response.status_code != 200:
                break

            try:
                insider_trades = InsiderTradeResponse(**response.json()).insider_trades
            except Exception:
                break

            if not insider_trades:
                break

            all_trades.extend(insider_trades)

            if not start_date or len(insider_trades) < limit:
                break

            current_end_date = min(trade.filing_date for trade in insider_trades).split("T")[0]
            if current_end_date <= start_date:
                break

        if not all_trades:
            return []

        _cache.set_insider_trades(cache_key, [trade.model_dump() for trade in all_trades])
        return all_trades

    def get_company_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
        api_key: str | None = None,
    ) -> list[CompanyNews]:
        cache_key = f"{self.name}:{ticker}_{start_date or 'none'}_{end_date}_{limit}"

        if cached_data := _cache.get_company_news(cache_key):
            return [CompanyNews(**news) for news in cached_data]

        all_news = []
        current_end_date = end_date

        while True:
            url = f"https://api.financialdatasets.ai/news/?ticker={ticker}&end_date={current_end_date}"
            if start_date:
                url += f"&start_date={start_date}"
            url += f"&limit={limit}"

            response = _make_api_request(url, self._headers(api_key))
            if response.status_code != 200:
                break

            try:
                company_news = CompanyNewsResponse(**response.json()).news
            except Exception:
                break

            if not company_news:
                break

            all_news.extend(company_news)

            if not start_date or len(company_news) < limit:
                break

            current_end_date = min(news.date for news in company_news).split("T")[0]
            if current_end_date <= start_date:
                break

        if not all_news:
            return []

        _cache.set_company_news(cache_key, [news.model_dump() for news in all_news])
        return all_news

    def get_market_cap(self, ticker: str, end_date: str, api_key: str | None = None) -> float | None:
        if end_date == datetime.datetime.now().strftime("%Y-%m-%d"):
            url = f"https://api.financialdatasets.ai/company/facts/?ticker={ticker}"
            response = _make_api_request(url, self._headers(api_key))
            if response.status_code != 200:
                print(f"Error fetching company facts: {ticker} - {response.status_code}")
                return None

            try:
                return CompanyFactsResponse(**response.json()).company_facts.market_cap
            except Exception:
                return None

        financial_metrics = self.get_financial_metrics(ticker, end_date, api_key=api_key)
        if not financial_metrics:
            return None

        return financial_metrics[0].market_cap
