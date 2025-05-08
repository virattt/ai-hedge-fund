# tests/test_backtest.py
import pandas as pd
import numpy as np
from ..backtest import run_strategy_on_df


def test_sharpe_not_zero_on_trending_path():
    # create 100‑min monotonically rising close prices
    idx = pd.date_range("2024-01-01", periods=100, freq="1min")
    df = pd.DataFrame({"close": np.linspace(100, 120, 100)}, index=idx)
    # add dummy indicator columns so the strategy is "flat"
    df["MACD_12_26_9"] = df["close"]
    df["MACDs_12_26_9"] = df["close"] - 1
    df["rsi"] = 60
    res = run_strategy_on_df(df)
    assert res["sharpe"] != 0, "Sharpe should not be zero on trending data"
