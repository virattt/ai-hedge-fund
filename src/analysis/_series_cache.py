"""Tiny in-memory cache of raw price/volume/SPX series per ticker.

`generate_snapshot()` pulls 5 years of yfinance history. We keep the
DataFrames warm here so the interactive backtest endpoint can compute
arbitrary as-of dates without a fresh network round-trip.
"""

from __future__ import annotations

import time
from typing import Optional

import pandas as pd

_TTL = 600  # seconds — same as snapshot cache, plus headroom
_CACHE: dict[str, tuple[float, pd.Series, pd.Series, pd.Series]] = {}


def put(ticker: str, close: pd.Series, volume: pd.Series, spx_close: pd.Series) -> None:
    _CACHE[ticker.upper()] = (time.time(), close, volume, spx_close)


def get(ticker: str) -> Optional[tuple[pd.Series, pd.Series, pd.Series]]:
    entry = _CACHE.get(ticker.upper())
    if not entry:
        return None
    ts, c, v, s = entry
    if time.time() - ts > _TTL:
        return None
    return c, v, s
