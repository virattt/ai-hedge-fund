"""
tests/test_indicators.py

These tests cover the *indicator layer*.  They serve a dual purpose:

1. **Functional verification** – we make sure that both the
   vectorised helper (`add_indicators`) and the streaming helper
   (`StrategyState`) behave as expected on simple, deterministic input.

2. **Living documentation** – each assertion is preceded by a short
   comment that explains *why* we expect the behaviour.  Treat the file
   as a guided tour of the indicator mechanics.
"""

import numpy as np
import pandas as pd

from src.selv.indicators import add_indicators


def test_add_indicators_columns_exist():
    """`add_indicators` must append RSI and MACD columns to the DataFrame."""
    # Need enough data points for MACD (e.g., slow_ema=26 + signal_ema=9 -> ~35, use 50)
    df = pd.DataFrame({"close": np.linspace(100, 110, 50)})
    out = add_indicators(df)
    expected_cols = {"rsi", "MACD_12_26_9", "MACDs_12_26_9", "MACDh_12_26_9"}
    assert expected_cols.issubset(
        out.columns
    ), f"Missing columns: {expected_cols - set(out.columns)}"


def test_add_indicators_simple_monotonic_rsi():
    """
    If the price is strictly increasing, RSI should be high (> 50).

    We don't pin an exact value because different libraries round
    differently, but the trend must be upward.
    """
    df = pd.DataFrame({"close": np.arange(1, 100)})
    out = add_indicators(df)
    # take the last RSI value (fully rolled‑in window)
    rsi_last = out["rsi"].iloc[-1]
    assert (
        rsi_last > 60
    ), f"Expected RSI to signal strong momentum on increasing series, got {rsi_last}"
