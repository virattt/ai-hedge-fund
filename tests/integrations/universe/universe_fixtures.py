"""Shared fixtures for universe selection tests: synthetic prices + stub data source."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from integrations.universe.config import UniverseConfig
from integrations.universe.data import AssetRecord
from integrations.universe.factors.base import FactorContext


def trading_calendar(n_days: int = 504, end: str = "2026-06-30") -> pd.DatetimeIndex:
    return pd.bdate_range(end=end, periods=n_days)


def make_prices(
    *,
    n_days: int = 504,
    start_price: float = 100.0,
    daily_vol: float = 0.015,
    drift: float = 0.0002,
    ar1: float = 0.0,
    volume: float = 1_000_000.0,
    seed: int = 7,
    end: str = "2026-06-30",
) -> pd.DataFrame:
    """Synthetic daily bars: AR(1) log returns with configurable structure."""
    rng = np.random.default_rng(seed)
    shocks = rng.normal(drift, daily_vol, n_days)
    returns = np.zeros(n_days)
    for i in range(1, n_days):
        returns[i] = ar1 * returns[i - 1] + shocks[i]
    closes = start_price * np.exp(np.cumsum(returns))
    opens = closes * (1 + rng.normal(0, daily_vol / 4, n_days))
    highs = np.maximum(opens, closes) * (1 + np.abs(rng.normal(0, daily_vol / 3, n_days)))
    lows = np.minimum(opens, closes) * (1 - np.abs(rng.normal(0, daily_vol / 3, n_days)))
    volumes = np.full(n_days, volume) * (1 + rng.uniform(-0.2, 0.2, n_days))
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=trading_calendar(n_days, end),
    )


def make_context(
    ticker: str = "TEST",
    prices: pd.DataFrame | None = None,
    config: UniverseConfig | None = None,
    **overrides: Any,
) -> FactorContext:
    return FactorContext(
        ticker=ticker,
        as_of="2026-06-30",
        config=config or UniverseConfig(),
        prices=prices if prices is not None else make_prices(),
        **overrides,
    )


class StubUniverseDataSource:
    """In-memory UniverseDataSource for pipeline tests (no network)."""

    def __init__(
        self,
        assets: list[AssetRecord],
        bars: dict[str, pd.DataFrame],
        facts: dict[str, dict] | None = None,
        fundamentals: dict[str, dict] | None = None,
        earnings: dict[str, list[dict]] | None = None,
        news_counts: dict[str, int] | None = None,
    ) -> None:
        self._assets = assets
        self._bars = bars
        self._facts = facts or {}
        self._fundamentals = fundamentals or {}
        self._earnings = earnings or {}
        self._news_counts = news_counts or {}

    def list_assets(self) -> list[AssetRecord]:
        return list(self._assets)

    def get_bars(self, symbols, start_date, end_date):
        cutoff = pd.Timestamp(end_date)
        out = {}
        for symbol in symbols:
            frame = self._bars.get(symbol)
            if frame is not None:
                out[symbol] = frame.loc[frame.index <= cutoff]
        return out

    def get_company_facts(self, ticker):
        return self._facts.get(ticker)

    def get_fundamentals(self, ticker, as_of):
        return self._fundamentals.get(ticker)

    def get_earnings_events(self, ticker, as_of):
        return self._earnings.get(ticker, [])

    def get_news_count(self, ticker, start_date, end_date):
        return self._news_counts.get(ticker)
