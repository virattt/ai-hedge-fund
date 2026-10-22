"""ARF Data Provider — connects ai-hedge-fund to ARF's DuckDB and market feeds.

Satisfies the DataClient protocol without requiring a paid Financial Datasets API.
- Ticker daily prices are read directly from ARF's local DuckDB (data/arf.db: daily_prices).
- Benchmark symbols (e.g. SPY, QQQ) or missing tickers are fetched via yfinance with disk caching.
"""

from __future__ import annotations

import logging
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

DEFAULT_ARF_DB_PATH = Path("/Users/sheng/Developer/ARF/data/arf.db")


class ARFDataClient:
    """Zero-cost DataClient backed by ARF's DuckDB and cached market data."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_ARF_DB_PATH
        self.cache_dir = Path(cache_dir) if cache_dir is not None else Path.home() / ".hedge-fund" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._yf_cache: dict[str, pd.DataFrame] = {}

    def __enter__(self) -> ARFDataClient:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def get_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        **kwargs: Any,
    ) -> list[Price]:
        """Fetch daily OHLCV bars between start_date and end_date."""
        ticker_clean = ticker.strip().upper()

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

    def _get_prices_from_db(
        self, ticker: str, start_date: str, end_date: str
    ) -> list[Price]:
        if not self.db_path.exists():
            return []
        try:
            con = duckdb.connect(str(self.db_path), read_only=True)
            query = """
                SELECT date, open, high, low, close, volume 
                FROM daily_prices 
                WHERE ticker = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
            """
            rows = con.execute(query, [ticker, start_date, end_date]).fetchall()
            con.close()
            if not rows:
                return []

            return [
                Price(
                    time=f"{row[0].strftime('%Y-%m-%d')}T20:00:00Z",
                    open=float(row[1] if row[1] is not None else row[4]),
                    high=float(row[2] if row[2] is not None else row[4]),
                    low=float(row[3] if row[3] is not None else row[4]),
                    close=float(row[4]),
                    volume=int(row[5] or 0),
                )
                for row in rows
                if row[4] is not None and row[4] > 0
            ]
        except Exception as exc:
            logger.warning("Error reading daily_prices for %s from %s: %s", ticker, self.db_path, exc)
            return []

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
            cache_file = self.cache_dir / f"{ticker}_yf.parquet"
            if cache_file.exists():
                try:
                    df = pd.read_parquet(cache_file)
                    self._yf_cache[ticker] = df
                except Exception:
                    df = pd.DataFrame()
            else:
                df = pd.DataFrame()

            if df.empty or df.index.max().strftime("%Y-%m-%d") < end_date:
                df = yf.download(ticker, start=lookback_start, end=end_date, progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                if not df.empty:
                    df.to_parquet(cache_file)
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
                    open=float(row.get("Open", close_val)),
                    high=float(row.get("High", close_val)),
                    low=float(row.get("Low", close_val)),
                    close=close_val,
                    volume=int(row.get("Volume", 0)),
                )
            )
        return prices
