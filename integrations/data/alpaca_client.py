"""Alpaca market data client — prices and news."""

from __future__ import annotations

import logging
from datetime import datetime

from integrations.data.config import DataConfig
from integrations.data.errors import DataClientError

logger = logging.getLogger(__name__)


class AlpacaDataClient:
    """Fetch OHLCV bars and Benzinga news from Alpaca Market Data API."""

    def __init__(self, config: DataConfig) -> None:
        self._config = config
        self._stock_client = None
        self._news_client = None

    def _get_stock_client(self):
        if self._stock_client is None:
            try:
                from alpaca.data.historical import StockHistoricalDataClient
            except ImportError as exc:
                raise ImportError(
                    "alpaca-py is required. Install with: poetry install --with alpaca"
                ) from exc
            self._stock_client = StockHistoricalDataClient(
                api_key=self._config.alpaca_api_key,
                secret_key=self._config.alpaca_secret_key,
            )
        return self._stock_client

    def _get_news_client(self):
        if self._news_client is None:
            try:
                from alpaca.data.historical import NewsClient
            except ImportError as exc:
                raise ImportError(
                    "alpaca-py is required. Install with: poetry install --with alpaca"
                ) from exc
            self._news_client = NewsClient(
                api_key=self._config.alpaca_api_key,
                secret_key=self._config.alpaca_secret_key,
            )
        return self._news_client

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        **kwargs,
    ) -> list:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        from v2.data.models import Price

        try:
            request = StockBarsRequest(
                symbol_or_symbols=ticker.upper(),
                timeframe=TimeFrame.Day,
                start=datetime.strptime(start_date[:10], "%Y-%m-%d"),
                end=datetime.strptime(end_date[:10], "%Y-%m-%d"),
            )
            bars = self._get_stock_client().get_stock_bars(request)
        except Exception as exc:
            raise DataClientError(f"Alpaca get_stock_bars failed for {ticker}: {exc}") from exc

        ticker_bars = bars.data.get(ticker.upper(), [])
        return [
            Price(
                open=float(bar.open),
                high=float(bar.high),
                low=float(bar.low),
                close=float(bar.close),
                volume=int(bar.volume),
                time=bar.timestamp.isoformat(),
            )
            for bar in ticker_bars
        ]

    def get_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list:
        from alpaca.data.requests import NewsRequest

        from v2.data.models import CompanyNews

        params: dict = {
            "symbols": ticker.upper(),
            "limit": min(limit, 50),
            "sort": "desc",
        }
        if start_date:
            params["start"] = datetime.strptime(start_date[:10], "%Y-%m-%d")
        if end_date:
            params["end"] = datetime.strptime(end_date[:10], "%Y-%m-%d")

        try:
            request = NewsRequest(**params)
            articles = self._get_news_client().get_news(request)
        except Exception as exc:
            raise DataClientError(f"Alpaca get_news failed for {ticker}: {exc}") from exc

        if articles is None:
            return []

        results: list[CompanyNews] = []
        for article in articles:
            symbols = getattr(article, "symbols", None) or []
            symbol = symbols[0] if symbols else ticker.upper()
            created = getattr(article, "created_at", None)
            results.append(
                CompanyNews(
                    ticker=str(symbol).upper(),
                    title=str(getattr(article, "headline", "") or ""),
                    source=str(getattr(article, "source", "benzinga") or "benzinga"),
                    date=created.isoformat() if created else end_date,
                    url=getattr(article, "url", None),
                )
            )
        return results[:limit]
