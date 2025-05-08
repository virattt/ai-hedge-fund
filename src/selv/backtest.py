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
    if len(returns) > 1:
        std_dev = returns.std()
        if std_dev == 0:
            # If std is 0, Sharpe is 0 if mean is also 0 (e.g. no trades / flat equity).
            # If mean is non-zero with 0 std (perfectly consistent returns), Sharpe is undefined or infinite.
            # For backtesting, 0 is a reasonable value if equity doesn't change.
            sharpe = 0.0
        else:
            sharpe = returns.mean() / std_dev * np.sqrt(365 * 24 * 60)
    else:
        sharpe = 0.0
    return {"equity": equity, "sharpe": sharpe, "max_dd": max(dds) if dds else 0}
