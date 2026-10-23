"""ARF Data Provider — connects ai-hedge-fund to ARF's DuckDB and market feeds.

Satisfies the DataClient protocol without requiring a paid Financial Datasets API.
- Ticker daily prices are read directly from ARF's local DuckDB (data/arf.db: daily_prices).
- Benchmark symbols (e.g. SPY, QQQ) or missing tickers are fetched via yfinance with disk caching.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from hedge_fund.data.models import (
    CompanyFacts,
    CompanyNews,
    Earnings,
    EarningsRecord,
    FinancialMetrics,
    InsiderTrade,
    Price,
    PriceSnapshot,
)

logger = logging.getLogger(__name__)

DEFAULT_ARF_DB_PATH = Path(os.getenv("ARF_DB_PATH", "data/arf.db"))


class ARFDataClient:
    """Zero-cost DataClient backed by ARF's DuckDB and cached market data.

    Set ``ARF_DB_PATH`` (or pass ``db_path``) to point at the ARF database. A
    caller that already holds an open DuckDB connection — the ARF webapp keeps
    one read-write for its lifetime — can pass it as ``connection``; DuckDB
    refuses to open a second connection to the same file with a different
    configuration, so sharing the connection is the only in-process option.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        cache_dir: str | Path | None = None,
        connection: duckdb.DuckDBPyConnection | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_ARF_DB_PATH
        self.cache_dir = Path(cache_dir) if cache_dir is not None else Path.home() / ".hedge-fund" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._connection = connection
        self._owns_connection = False
        self._price_cache: dict[str, pd.DataFrame] = {}
        self._yf_cache: dict[str, pd.DataFrame] = {}

    def __enter__(self) -> ARFDataClient:
        return self

    def __exit__(self, *args: Any) -> None:
        if self._owns_connection and self._connection is not None:
            self._connection.close()
        self._connection = None
        self._owns_connection = False

    def _con(self) -> duckdb.DuckDBPyConnection:
        """The DuckDB connection, opened read-only once and reused."""
        if self._connection is None:
            if not self.db_path.exists():
                raise FileNotFoundError(f"ARF database not found at {self.db_path}")
            self._connection = duckdb.connect(str(self.db_path), read_only=True)
            self._owns_connection = True
        return self._connection

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "day",
        interval_multiplier: int = 1,
        **kwargs: Any,
    ) -> list[Price]:
        """Fetch daily OHLCV bars between start_date and end_date."""
        ticker_clean = ticker.strip().upper()
        if interval != "day":
            # ARF stores daily bars only; a minute fund must use another client.
            return []

        # 1. First attempt to read from ARF DuckDB daily_prices table
        prices_from_db = self._get_prices_from_db(ticker_clean, start_date, end_date)
        if prices_from_db:
            return prices_from_db

        # 2. Fallback to yfinance (for benchmark ETFs like SPY, QQQ or unseeded tickers)
        return self._get_prices_from_yfinance(ticker_clean, start_date, end_date)

    def get_snapshot(self, ticker: str) -> PriceSnapshot | None:
        """Fetch latest quote for ticker."""
        prices = self.get_prices(ticker, (date.today() - timedelta(days=5)).isoformat(), date.today().isoformat())
        if not prices:
            return None
        last = prices[-1]
        return PriceSnapshot(
            ticker=ticker.strip().upper(),
            price=last.close,
            time=last.time,
        )

    def get_financial_metrics(
        self,
        ticker: str,
        end_date: str,
        period: str = "ttm",
        limit: int = 10,
    ) -> list[FinancialMetrics]:
        return []

    def get_news(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[CompanyNews]:
        return []

    def get_insider_trades(
        self,
        ticker: str,
        end_date: str,
        start_date: str | None = None,
        limit: int = 1000,
    ) -> list[InsiderTrade]:
        return []

    def get_company_facts(self, ticker: str) -> CompanyFacts | None:
        return None

    def get_earnings(self, ticker: str) -> Earnings | None:
        return None

    def get_earnings_history(
        self,
        ticker: str,
        limit: int = 12,
    ) -> list[EarningsRecord]:
        return []

    def get_market_cap(self, ticker: str, end_date: str) -> float | None:
        return None

    # ------------------------------------------------------------------
    # Private storage helpers
    # ------------------------------------------------------------------

    def _load_history(self, ticker: str) -> pd.DataFrame:
        """All daily bars for *ticker*, loaded once and kept for this client.

        A backtest asks for a rolling window on every session; re-querying the
        full history per session turns a 36-name replay into thousands of
        DuckDB round-trips. One query per ticker instead.
        """
        if ticker in self._price_cache:
            return self._price_cache[ticker]
        query = """
            SELECT date, open, high, low, close, volume
            FROM daily_prices
            WHERE ticker = ?
            ORDER BY date ASC
        """
        frame = self._con().execute(query, [ticker]).df()
        self._price_cache[ticker] = frame
        return frame

    def _get_prices_from_db(
        self, ticker: str, start_date: str, end_date: str
    ) -> list[Price]:
        # Missing database / missing table is a genuine "no data" here only
        # when the universe simply isn't in ARF; a connection failure must
        # propagate (the DataClient contract forbids silent empty results).
        frame = self._load_history(ticker)
        if frame.empty:
            return []

        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
        dates = pd.to_datetime(frame["date"])
        window = frame.loc[(dates >= start) & (dates <= end)]
        if window.empty:
            return []

        prices: list[Price] = []
        for row in window.itertuples(index=False):
            close = row.close
            if close is None or pd.isna(close) or close <= 0:
                continue
            prices.append(
                Price(
                    time=f"{pd.Timestamp(row.date).strftime('%Y-%m-%d')}T20:00:00Z",
                    open=float(row.open if pd.notna(row.open) else close),
                    high=float(row.high if pd.notna(row.high) else close),
                    low=float(row.low if pd.notna(row.low) else close),
                    close=float(close),
                    volume=int(row.volume or 0),
                )
            )
        return prices

    def _get_prices_from_yfinance(
        self, ticker: str, start_date: str, end_date: str
    ) -> list[Price]:
        try:
            import yfinance as yf
        except ImportError:
            logger.error("yfinance is not installed in the current environment")
            return []

        if ticker not in self._yf_cache:
            # Lookback buffer of 14 days before start to satisfy clock lookbacks
            lookback_start = (date.fromisoformat(start_date) - timedelta(days=14)).isoformat()
            # yfinance's `end` is exclusive; ask for the day after so the
            # requested end_date bar is included.
            exclusive_end = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()
            cache_file = self.cache_dir / f"{ticker}_yf.parquet"
            df = pd.DataFrame()
            if cache_file.exists():
                try:
                    df = pd.read_parquet(cache_file)
                except Exception:
                    df = pd.DataFrame()

            cached_through = (
                pd.Timestamp(df.index.max()).strftime("%Y-%m-%d")
                if not df.empty and isinstance(df.index, pd.DatetimeIndex)
                else ""
            )
            if df.empty or cached_through < end_date:
                df = self._download_yfinance(yf, ticker, lookback_start, exclusive_end)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                if not df.empty:
                    try:
                        df.to_parquet(cache_file)
                    except Exception as exc:  # cache is an optimisation, never fatal
                        logger.warning("Could not cache %s prices: %s", ticker, exc)
            self._yf_cache[ticker] = df

        df = self._yf_cache.get(ticker, pd.DataFrame())
        if df.empty:
            return []

        sub = df.loc[start_date:end_date]
        prices = []
        for idx, row in sub.iterrows():
            d_str = idx.strftime("%Y-%m-%d")
            close_val = float(row.get("Close", 0.0))
            if close_val <= 0 or pd.isna(close_val):
                continue
            prices.append(
                Price(
                    time=f"{d_str}T20:00:00Z",
                    open=float(self._value_or(row, "Open", close_val)),
                    high=float(self._value_or(row, "High", close_val)),
                    low=float(self._value_or(row, "Low", close_val)),
                    close=close_val,
                    volume=int(self._value_or(row, "Volume", 0) or 0),
                )
            )
        return prices

    @staticmethod
    def _value_or(row: pd.Series, column: str, default: float) -> float:
        value = row.get(column, default)
        return default if value is None or pd.isna(value) else value

    @staticmethod
    def _download_yfinance(yf: Any, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Download with a small exponential backoff; raise if every try fails."""
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                frame = yf.download(ticker, start=start, end=end, progress=False)
                if not frame.empty:
                    return frame
                last_error = RuntimeError(f"yfinance returned no bars for {ticker}")
            except Exception as exc:  # noqa: BLE001 — retried below, then raised
                last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)
        raise RuntimeError(f"yfinance failed for {ticker}: {last_error}") from last_error
