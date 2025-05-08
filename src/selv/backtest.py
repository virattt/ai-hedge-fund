import pandas as pd
from indicators import add_indicators

df = pd.read_csv("btc_data.csv", parse_dates=["datetime"], index_col="datetime")
df = add_indicators(df)

# entry conditions
long_entry  = (df["MACD_12_26_9"] > df["MACDs_12_26_9"]) & (df["rsi"] > 55)
short_entry = (df["MACD_12_26_9"] < df["MACDs_12_26_9"]) & (df["rsi"] < 45)

# exit on TP/SL/timeout: simplest way – iterate
trades = []
position = 0
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
            trades.append({"entry": entry_time, "exit": ts, 
                           "dir": position, "entry_price": entry_price, "exit_price": price,
                           "pnl_pct": (price - entry_price) / entry_price * position})
            position = 0

# print trades
for trade in trades:
    print(f"{trade['entry']} - {trade['exit']}: {trade['dir']} @ {trade['entry_price']} -> {trade['exit_price']}: {trade['pnl_pct']:.2%}")
# print summary
total_pnl = sum([trade["pnl_pct"] for trade in trades])
total_trades = len(trades)
total_winning = len([trade for trade in trades if trade["pnl_pct"] > 0])
total_losing = len([trade for trade in trades if trade["pnl_pct"] < 0])
total_winning_pct = total_winning / total_trades * 100 if total_trades > 0 else 0
total_losing_pct = total_losing / total_trades * 100 if total_trades > 0 else 0
print(f"Total PnL: {total_pnl:.2%} ({total_trades} trades, {total_winning} winning, {total_losing} losing)")