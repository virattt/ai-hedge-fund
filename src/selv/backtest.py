import numpy as np
import pandas as pd
from typing import Callable


def run_strategy_on_df(
    df: pd.DataFrame,
    *,
    long_entry_fun: Callable[[pd.DataFrame], pd.Series] | None = None,
    short_entry_fun: Callable[[pd.DataFrame], pd.Series] | None = None,
    tp: float = 0.02,
    sl: float = 0.01,
    max_minutes: int = 1440,
    initial_capital: float = 10_000.0,        # ⬅ NEW
) -> dict:
    """
    Back‑test a long/short strategy and return both:
      • equity_ratio : growth factor vs. start (= 1.0 at t=0)
      • cash         : account value in currency units (starts at initial_capital)
    Sharpe & drawdown are still computed on the *equity_ratio* curve.
    """
    # ---------- default entry rules (unchanged) -----------------------------
    def _default_long_entry(d: pd.DataFrame) -> pd.Series:
        return (d["MACD_12_26_9"] > d["MACDs_12_26_9"]) & (d["rsi"] > 55)

    def _default_short_entry(d: pd.DataFrame) -> pd.Series:
        return (d["MACD_12_26_9"] < d["MACDs_12_26_9"]) & (d["rsi"] < 45)

    long_entry_fun = long_entry_fun or _default_long_entry
    short_entry_fun = short_entry_fun or _default_short_entry

    long_entry = long_entry_fun(df)
    short_entry = short_entry_fun(df)

    # -------- state variables ----------------------------------------------
    position = 0
    equity = 1.0                     # cumulative return factor
    cash = initial_capital           # actual currency balance
    peak = 1.0
    dds = []
    equity_ts = []
    entry_price = entry_time = None

    # -------- main loop ----------------------------------------------------
    for ts, row in df.iterrows():
        price = row["close"]

        if position == 0:                                # flat → look for entry
            if long_entry.loc[ts]:
                position, entry_price, entry_time = 1, price, ts
            elif short_entry.loc[ts]:
                position, entry_price, entry_time = -1, price, ts
        else:                                            # in‑position → check exit
            move = (price - entry_price) / entry_price
            minutes_held = (ts - entry_time).total_seconds() / 60
            hit_tp = (move >= tp) if position == 1 else (move <= -tp)
            hit_sl = (move <= -sl) if position == 1 else (move >= sl)
            timed_out = minutes_held >= max_minutes

            if hit_tp or hit_sl or timed_out:
                equity *= 1 + move * position          # update growth factor
                cash = equity * initial_capital        # translate to currency
                peak = max(peak, equity)
                dds.append(1 - equity / peak)
                position = 0

        equity_ts.append(equity)

    # -------- risk metrics --------------------------------------------------
    equity_series = pd.Series(equity_ts, index=df.index)
    returns = np.log(equity_series).diff().dropna()

    if len(returns) > 1 and returns.std() != 0:
        sharpe = returns.mean() / returns.std() * np.sqrt(365 * 24 * 60)
    else:
        sharpe = 0.0

    return {
        "equity_ratio": equity,           # dimensionless growth factor
        "cash": cash,                     # currency value
        "sharpe": sharpe,
        "max_dd": max(dds) if dds else 0,
    }