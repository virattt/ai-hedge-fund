import numpy as np
import pandas as pd


def run_strategy_on_df(df: pd.DataFrame) -> dict:
    long_entry = (df["MACD_12_26_9"] > df["MACDs_12_26_9"]) & (df["rsi"] > 55)
    short_entry = (df["MACD_12_26_9"] < df["MACDs_12_26_9"]) & (df["rsi"] < 45)

    position = 0
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
            hit_tp = move >= 0.02 if position == 1 else move <= -0.02
            hit_sl = move <= -0.01 if position == 1 else move >= 0.01
            timed_out = minutes_held >= 1440
            if hit_tp or hit_sl or timed_out:
                equity *= 1 + move * position
                peak = max(peak, equity)
                dds.append(1 - equity / peak)
                position = 0
        equity_ts.append(equity)
    equity_series = pd.Series(equity_ts, index=df.index)
    returns = np.log(equity_series).diff().dropna()
    sharpe = (
        returns.mean() / returns.std() * np.sqrt(365 * 24 * 60)
        if len(returns) > 1
        else 0
    )
    return {"equity": equity, "sharpe": sharpe, "max_dd": max(dds) if dds else 0}
