# data_download.py
import asyncio, logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import ccxt.async_support as ccxt
import pandas as pd

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)s  %(message)s")

async def _fetch_candles_parallel(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    since_ms: int,
    limit: int = 1_000,
) -> list[list]:
    """Download all OHLCV candles from `since_ms` up to *now* (async, rate‑limit‑aware)."""
    tf_ms = exchange.parse_timeframe(timeframe) * 1_000
    windows = list(range(since_ms, exchange.milliseconds(), limit * tf_ms))

    async def fetch_window(start):
        return await exchange.fetch_ohlcv(symbol, timeframe, since=start, limit=limit)

    rate_limit = getattr(exchange, "rateLimit", 1_000) / 1_000
    results = []
    for start in windows:
        results.extend(await fetch_window(start))
        await asyncio.sleep(rate_limit)
    return results


def download_ohlcv(
    symbol: str,
    timeframe: str = "1m",
    days: int = 365,
    *,
    exchange_id: str = "coinbase",
    outfile: Optional[Path | str] = None,
) -> pd.DataFrame:
    """
    Fetch historical candles and return a DataFrame.

    Parameters
    ----------
    symbol       e.g. "BTC/USDT"
    timeframe    e.g. "1m", "5m", "1h"
    days         how many days back from now
    exchange_id  any ccxt exchange id that supports the symbol
    outfile      optional CSV path – if given, data is saved to disk
    """
    async def _worker():
        ex = getattr(ccxt, exchange_id)()
        since_ms = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1_000)
        logging.info("Downloading %s %s for %s days via %s",
                     symbol, timeframe, days, exchange_id)
        candles = await _fetch_candles_parallel(ex, symbol, timeframe, since_ms)
        await ex.close()
        return candles

    candles = asyncio.run(_worker())
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low",
                                        "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("datetime", inplace=True)

    if outfile:
        outfile = Path(outfile)
        outfile.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(outfile)
        logging.info("Saved %d rows ➜ %s", len(df), outfile)

    return df

# Download Five years of data
# download_ohlcv("BTC/USDT", timeframe="1m", days=1825, exchange_id="coinbase", outfile="btc_1m_5yr.csv")
