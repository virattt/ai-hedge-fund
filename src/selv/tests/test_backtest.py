"""
tests/test_backtest.py

These tests verify that `run_strategy_on_df`:

1. Produces a positive Sharpe ratio on a simple bullish trend.
2. Produces a *negative* Sharpe ratio on a simple bearish trend.
3. Produces zero Sharpe on a flat series – sanity check.
Each test doubles as documentation of what we expect from the
strategy under textbook price paths.
"""

import numpy as np
import pandas as pd

from src.selv.backtest import run_strategy_on_df


def _trend_df(start, end, n=120):  # helper
    idx = pd.date_range("2024-01-01", periods=n, freq="1min")
    return pd.DataFrame({"close": np.linspace(start, end, n)}, index=idx)


def test_sharpe_positive_on_uptrend():
    """
    Equity should grow on an up‑trend → Sharpe > 0.
    """
    df = _trend_df(100, 120)
    df["MACD_12_26_9"] = df["close"]
    df["MACDs_12_26_9"] = df["close"] - 1
    df["rsi"] = 60
    res = run_strategy_on_df(df)
    assert res["sharpe"] > 0


def test_sharpe_negative_on_downtrend():
    """
    Equity should fall on a down‑trend (shorts lose) → Sharpe < 0.
    """
    df = _trend_df(120, 100)
    # Setup for a losing (long) trade on a downtrend
    df["MACD_12_26_9"] = df["close"]  # MACD > Signal
    df["MACDs_12_26_9"] = df["close"] - 1
    df["rsi"] = 60  # RSI > 55
    res = run_strategy_on_df(df)
    assert res["sharpe"] < 0


def test_sharpe_zero_on_flat_series():
    """
    If price never moves, equity stays flat → Sharpe = 0.
    """
    df = _trend_df(100, 100)
    df["MACD_12_26_9"] = 0
    df["MACDs_12_26_9"] = 0
    df["rsi"] = 50
    res = run_strategy_on_df(df)
    assert res["sharpe"] == 0
