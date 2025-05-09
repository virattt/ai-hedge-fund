import pandas as pd
import pandas_ta as ta  # noqa: F401
from typing import Callable
import numpy as np


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators to the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data.

    Returns
    -------
    pd.DataFrame
        DataFrame with added indicator columns.
    """
    df.ta.macd(close="close", fast=12, slow=26, signal=9, append=True)
    df.ta.rsi(close="close", length=14, append=True, col_names=("rsi",))
    df.ta.ema(close="close", length=10, append=True)  # EMA_10
    df.ta.ema(close="close", length=30, append=True)  # EMA_30
    df.ta.sma(close="close", length=50, append=True)  # SMA_50
    df.ta.sma(close="close", length=200, append=True)  # SMA_200
    df.dropna(inplace=True)
    return df

def run_strategy_on_df(
    df: pd.DataFrame,
    *,
    long_entry_fun: Callable[[pd.DataFrame], pd.Series] | None = None,
    short_entry_fun: Callable[[pd.DataFrame], pd.Series] | None = None,
    tp: float = 0.02,
    sl: float = 0.01,
    max_minutes: int = 1440,
) -> dict:
    """Back‑test a long/short strategy on an OHLCV‑plus‑indicators DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must already contain all columns referenced by the entry lambdas.
    long_entry_fun / short_entry_fun : Callable[[df], pd.Series], optional
        Functions that return Boolean Series indicating entry bars.  If either
        is omitted, a default MACD‑RSI crossover rule is used.
    tp : float
        Take‑profit expressed as fractional return (e.g. 0.02 → +2 %).
    sl : float
        Stop‑loss expressed as fractional return (e.g. 0.01 → −1 % for longs).
    max_minutes : int
        Maximum holding period before a position is force‑closed.

    Returns
    -------
    dict
        {'equity', 'sharpe', 'max_dd'}
    """

    # -------- default rules -------------------------------------------------
    def _default_long_entry(d: pd.DataFrame) -> pd.Series:
        """Default long entry rule: MACD crossover and RSI > 55."""
        return (d["MACD_12_26_9"] > d["MACDs_12_26_9"]) & (d["rsi"] > 55)

    def _default_short_entry(d: pd.DataFrame) -> pd.Series:
        """Default short entry rule: MACD crossunder and RSI < 45."""
        return (d["MACD_12_26_9"] < d["MACDs_12_26_9"]) & (d["rsi"] < 45)

    if long_entry_fun is None:
        long_entry_fun = _default_long_entry
    if short_entry_fun is None:
        short_entry_fun = _default_short_entry

    long_entry = long_entry_fun(df)
    short_entry = short_entry_fun(df)

    position = 0  # +1 long, −1 short, 0 flat
    equity = 1.0
    peak = 1.0
    dds = []
    equity_ts = []
    entry_price = entry_time = None

    for ts, row in df.iterrows():
        price = row["close"]

        if position == 0:
            if long_entry.loc[ts]:
                position, entry_price, entry_time = 1, price, ts
            elif short_entry.loc[ts]:
                position, entry_price, entry_time = -1, price, ts
        else:
            move = (price - entry_price) / entry_price
            minutes_held = (ts - entry_time).total_seconds() / 60

            if position == 1:  # long
                hit_tp = move >= tp
                hit_sl = move <= -sl
            else:  # short
                hit_tp = move <= -tp
                hit_sl = move >= sl

            timed_out = minutes_held >= max_minutes

            if hit_tp or hit_sl or timed_out:
                equity *= 1 + move * position
                peak = max(peak, equity)
                dds.append(1 - equity / peak)
                position = 0

        equity_ts.append(equity)

    equity_series = pd.Series(equity_ts, index=df.index)
    returns = np.log(equity_series).diff().dropna()

    if len(returns) > 1:
        std_dev = returns.std()
        sharpe = (
            0.0 if std_dev == 0 else returns.mean() / std_dev * np.sqrt(365 * 24 * 60)
        )
    else:
        sharpe = 0.0

    return {
        "equity": equity,
        "sharpe": sharpe,
        "max_dd": max(dds) if dds else 0,
    }



def strategy_buy_sell_strategy(
    df: pd.DataFrame,
    *,
    long_entry_fun: Callable[[pd.DataFrame], pd.Series] | None = None,
    sell_entry_fun: Callable[[pd.DataFrame], pd.Series] | None = None,
    tp: float = 0.02,
    sl: float = 0.01,
    max_minutes: int = 1440,
) -> dict:
    """Back‑test a long/short strategy on an OHLCV‑plus‑indicators DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must already contain all columns referenced by the entry lambdas.
    long_entry_fun / sell_entry_fun : Callable[[df], pd.Series], optional
        Functions that return Boolean Series indicating entry bars.  If either
        is omitted, a default MACD‑RSI crossover rule is used.
    tp : float
        Take‑profit expressed as fractional return (e.g. 0.02 → +2 %).
    sl : float
        Stop‑loss expressed as fractional return (e.g. 0.01 → −1 % for longs).
    max_minutes : int
        Maximum holding period before a position is force‑closed.

    Returns
    -------
    dict
        {'equity', 'sharpe', 'max_dd'}
    """

    # -------- default rules -------------------------------------------------
    def _default_long_entry(d: pd.DataFrame) -> pd.Series:
        """Default long entry rule: MACD crossover and RSI > 55."""
        return (d["MACD_12_26_9"] > d["MACDs_12_26_9"]) & (d["rsi"] > 55)

    def _default_short_entry(d: pd.DataFrame) -> pd.Series:
        """Default short entry rule: MACD crossunder and RSI < 45."""
        return (d["MACD_12_26_9"] < d["MACDs_12_26_9"]) & (d["rsi"] < 45)

    if long_entry_fun is None:
        long_entry_fun = _default_long_entry
    if sell_entry_fun is None:
        sell_entry_fun = _default_short_entry

    long_entry = long_entry_fun(df)
    # 'short_entry' will now be interpreted as an **exit** trigger (sell/flat),
    # not as opening a new short position.
    exit_signal = sell_entry_fun(df)

    position = 0  # +1 long, 0 flat
    equity = 1.0
    peak = 1.0
    dds = []
    equity_ts = []
    entry_price = entry_time = None

    for ts, row in df.iterrows():
        price = row["close"]

        if position == 0:
            # Flat ➜ open a LONG when long_entry is True
            if long_entry.loc[ts]:
                position, entry_price, entry_time = 1, price, ts
        else:
            # Currently LONG ➜ check for take‑profit / stop‑loss / timeout / explicit exit signal
            move = (price - entry_price) / entry_price
            minutes_held = (ts - entry_time).total_seconds() / 60

            hit_tp   = move >= tp
            hit_sl   = move <= -sl
            timed_out = minutes_held >= max_minutes
            hit_exit = exit_signal.loc[ts]  # MACD‑RSI bearish crossover

            if hit_tp or hit_sl or timed_out or hit_exit:
                equity *= 1 + move  # position is +1
                peak = max(peak, equity)
                dds.append(1 - equity / peak)
                position = 0

        equity_ts.append(equity)

    equity_series = pd.Series(equity_ts, index=df.index)
    returns = np.log(equity_series).diff().dropna()

    if len(returns) > 1:
        std_dev = returns.std()
        sharpe = (
            0.0 if std_dev == 0 else returns.mean() / std_dev * np.sqrt(365 * 24 * 60)
        )
    else:
        sharpe = 0.0

    return {
        "equity": equity,
        "sharpe": sharpe,
        "max_dd": max(dds) if dds else 0,
    }
