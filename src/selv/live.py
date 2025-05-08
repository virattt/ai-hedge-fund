# live.py
import asyncio, ccxt.pro as ccxtpro
from indicators import StrategyState

async def run_live():
    ex = ccxtpro.okx()             # CCXT‑Pro websocket client
    state = StrategyState()
    await ex.load_markets()
    await ex.watch_ticker('BTC/USDT')  # prime connection

    while True:
        candle = await ex.watch_ohlcv('BTC/USDT', timeframe='1m')
        # watch_ohlcv returns a list; grab the latest bar
        bar = candle[-1]
        ohlcv = dict(timestamp=bar[0], open=bar[1], high=bar[2],
                     low=bar[3], close=bar[4], volume=bar[5])
        sig = state.update(ohlcv)
        if sig:
            print(sig)                 # -> {"timestamp": ..., "price": ..., "signal": "LONG"/"SHORT"/"EXIT"}
            # here place orders via ex.create_order(...)
asyncio.run(run_live())