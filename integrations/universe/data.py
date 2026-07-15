"""Data access for universe selection.

``UniverseDataSource`` is a small protocol so the pipeline can be tested with
stub data. ``AlpacaUniverseDataSource`` is the production implementation:
asset list + bulk daily bars from Alpaca, fundamentals/facts/earnings from
the configured provider (composite Alpaca+Finnhub, or Financial Datasets).

Everything is keyed by an explicit ``as_of`` date and disk-cached under
``data/universe/cache/`` so repeated builds and historical (backtest) builds
don't re-hit the APIs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

import pandas as pd

from integrations.alpaca.rate_limit import RateLimiter
from integrations.data.config import DataConfig, load_data_config
from integrations.universe.cache import JsonDiskCache
from integrations.universe.config import UniverseConfig

logger = logging.getLogger(__name__)

_BAR_BATCH_SIZE = 200
_BAR_COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class AssetRecord:
    """One tradable asset from the broker's asset master."""

    symbol: str
    exchange: str
    name: str = ""
    shortable: bool = False
    easy_to_borrow: bool = False


class UniverseDataSource(Protocol):
    """Everything the universe pipeline needs from the outside world."""

    def list_assets(self) -> list[AssetRecord]: ...

    def get_bars(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]: ...

    def get_company_facts(self, ticker: str) -> dict[str, Any] | None: ...

    def get_fundamentals(self, ticker: str, as_of: str) -> dict[str, Any] | None: ...

    def get_earnings_events(self, ticker: str, as_of: str) -> list[dict[str, Any]]: ...

    def get_news_count(self, ticker: str, start_date: str, end_date: str) -> int | None: ...


# ---------------------------------------------------------------------------
# Bar (de)serialization helpers — shared with the disk cache
# ---------------------------------------------------------------------------

def bars_to_payload(df: pd.DataFrame) -> dict[str, list]:
    payload: dict[str, list] = {"dates": [d.strftime("%Y-%m-%d") for d in df.index]}
    for col in _BAR_COLUMNS:
        payload[col] = [float(v) for v in df[col].tolist()]
    return payload


def payload_to_bars(payload: dict[str, list]) -> pd.DataFrame:
    index = pd.to_datetime(payload["dates"])
    data = {col: payload[col] for col in _BAR_COLUMNS}
    return pd.DataFrame(data, index=index)


def make_bars_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a canonical bars DataFrame from row dicts with a ``date`` key."""
    if not rows:
        return pd.DataFrame(columns=list(_BAR_COLUMNS))
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"].astype(str).str[:10])
    frame = frame.drop_duplicates(subset="date").set_index("date").sort_index()
    return frame[list(_BAR_COLUMNS)].astype(float)


class AlpacaUniverseDataSource:
    """Production data source: Alpaca for assets/bars/news, provider for fundamentals."""

    def __init__(
        self,
        config: UniverseConfig,
        *,
        data_config: DataConfig | None = None,
    ) -> None:
        self._config = config
        self._data_config = data_config or load_data_config()
        self._cache = JsonDiskCache(config.cache_dir)
        self._trading_client = None
        self._stock_client = None
        self._fund_client = None
        self._alpaca_limiter = RateLimiter(100)
        self._fund_limiter = RateLimiter(55)

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def list_assets(self) -> list[AssetRecord]:
        client = self._ensure_trading_client()
        from alpaca.trading.enums import AssetClass, AssetStatus
        from alpaca.trading.requests import GetAssetsRequest

        request = GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY)
        self._alpaca_limiter.wait()
        assets = client.get_all_assets(request)

        records: list[AssetRecord] = []
        for asset in assets:
            if not getattr(asset, "tradable", False):
                continue
            exchange = getattr(asset, "exchange", None)
            exchange_name = getattr(exchange, "value", str(exchange or "")).upper()
            records.append(
                AssetRecord(
                    symbol=str(asset.symbol).upper(),
                    exchange=exchange_name,
                    name=str(getattr(asset, "name", "") or ""),
                    shortable=bool(getattr(asset, "shortable", False)),
                    easy_to_borrow=bool(getattr(asset, "easy_to_borrow", False)),
                )
            )
        return records

    # ------------------------------------------------------------------
    # Bars
    # ------------------------------------------------------------------

    def get_bars(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        missing: list[str] = []
        for symbol in symbols:
            cached = self._cache.get("bars", f"{symbol}_{start_date}_{end_date}")
            if cached is not None:
                out[symbol] = payload_to_bars(cached)
            else:
                missing.append(symbol)

        for start in range(0, len(missing), _BAR_BATCH_SIZE):
            batch = missing[start : start + _BAR_BATCH_SIZE]
            fetched = self._fetch_bars_batch(batch, start_date, end_date)
            if fetched is None:
                # Request failed — don't poison the cache with empties.
                continue
            for symbol in batch:
                df = fetched.get(symbol, pd.DataFrame(columns=list(_BAR_COLUMNS)))
                self._cache.set("bars", f"{symbol}_{start_date}_{end_date}", bars_to_payload(df))
                out[symbol] = df
        return out

    def _fetch_bars_batch(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame] | None:
        """Fetch one batch of daily bars. Returns None on request failure."""
        if not symbols:
            return {}
        client = self._ensure_stock_client()
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        # Free Alpaca data plans reject queries touching the last ~15 minutes
        # of SIP data, so cap the window; today's partial bar is useless anyway.
        end = min(
            datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1),
            datetime.utcnow() - timedelta(minutes=16),
        )
        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=datetime.strptime(start_date, "%Y-%m-%d"),
            end=end,
        )
        self._alpaca_limiter.wait()
        try:
            response = client.get_stock_bars(request)
        except Exception as exc:
            logger.warning("Bulk bars fetch failed for %d symbols: %s", len(symbols), exc)
            return None

        out: dict[str, pd.DataFrame] = {}
        for symbol, bars in (getattr(response, "data", None) or {}).items():
            rows = [
                {
                    "date": bar.timestamp.strftime("%Y-%m-%d"),
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": float(bar.volume),
                }
                for bar in bars
            ]
            out[str(symbol).upper()] = make_bars_frame(rows)
        return out

    # ------------------------------------------------------------------
    # Fundamentals / facts / earnings / news (provider-backed, cached)
    # ------------------------------------------------------------------

    def get_company_facts(self, ticker: str) -> dict[str, Any] | None:
        cached = self._cache.get("facts", ticker)
        if cached is not None:
            return cached or None
        client = self._ensure_fund_client()
        try:
            self._fund_limiter.wait()
            facts = client.get_company_facts(ticker)
        except Exception as exc:
            logger.debug("Company facts failed for %s: %s", ticker, exc)
            return None
        payload = facts.model_dump() if facts is not None else {}
        self._cache.set("facts", ticker, payload)
        return payload or None

    def get_fundamentals(self, ticker: str, as_of: str) -> dict[str, Any] | None:
        key = f"{ticker}_{as_of}"
        cached = self._cache.get("fundamentals", key)
        if cached is not None:
            return cached or None
        client = self._ensure_fund_client()
        try:
            self._fund_limiter.wait()
            metrics = client.get_financial_metrics(ticker, as_of, limit=1)
        except Exception as exc:
            logger.debug("Fundamentals failed for %s: %s", ticker, exc)
            return None
        payload = metrics[0].model_dump() if metrics else {}
        self._cache.set("fundamentals", key, payload)
        return payload or None

    def get_earnings_events(self, ticker: str, as_of: str) -> list[dict[str, Any]]:
        key = f"{ticker}_{as_of}"
        cached = self._cache.get("earnings", key)
        if cached is not None:
            return cached
        client = self._ensure_fund_client()
        try:
            self._fund_limiter.wait()
            records = client.get_earnings_history(ticker, limit=12)
        except Exception as exc:
            logger.debug("Earnings history failed for %s: %s", ticker, exc)
            return []
        events = [
            {"filing_date": r.filing_date, "report_period": r.report_period}
            for r in records
            if getattr(r, "filing_date", None) and r.filing_date <= as_of
        ]
        self._cache.set("earnings", key, events)
        return events

    def get_news_count(self, ticker: str, start_date: str, end_date: str) -> int | None:
        key = f"{ticker}_{start_date}_{end_date}"
        cached = self._cache.get("news_count", key)
        if cached is not None:
            return int(cached)
        client = self._ensure_fund_client()
        get_news = getattr(client, "get_news", None)
        if get_news is None:
            return None
        try:
            self._fund_limiter.wait()
            articles = get_news(ticker, end_date, start_date=start_date, limit=50)
        except Exception as exc:
            logger.debug("News count failed for %s: %s", ticker, exc)
            return None
        count = len(articles)
        self._cache.set("news_count", key, count)
        return count

    # ------------------------------------------------------------------
    # Lazy clients
    # ------------------------------------------------------------------

    def _ensure_trading_client(self):
        if self._trading_client is None:
            try:
                from alpaca.trading.client import TradingClient
            except ImportError as exc:
                raise ImportError(
                    "alpaca-py is required. Install with: poetry install --with alpaca"
                ) from exc
            if not self._data_config.alpaca_api_key or not self._data_config.alpaca_secret_key:
                raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set for universe builds.")
            self._trading_client = TradingClient(
                api_key=self._data_config.alpaca_api_key,
                secret_key=self._data_config.alpaca_secret_key,
                paper=True,
            )
        return self._trading_client

    def _ensure_stock_client(self):
        if self._stock_client is None:
            try:
                from alpaca.data.historical import StockHistoricalDataClient
            except ImportError as exc:
                raise ImportError(
                    "alpaca-py is required. Install with: poetry install --with alpaca"
                ) from exc
            self._stock_client = StockHistoricalDataClient(
                api_key=self._data_config.alpaca_api_key,
                secret_key=self._data_config.alpaca_secret_key,
            )
        return self._stock_client

    def _ensure_fund_client(self):
        """Fundamentals client: composite (Alpaca+Finnhub) or Financial Datasets."""
        if self._fund_client is None:
            if self._data_config.provider == "composite":
                from integrations.data import get_data_client

                self._fund_client = get_data_client()
            else:
                from v2.data.client import FDClient

                self._fund_client = FDClient()
        return self._fund_client
