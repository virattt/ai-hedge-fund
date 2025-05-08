import asyncio
import ccxt.async_support as ccxt
import pandas as pd
from datetime import datetime, timedelta

# Add logging import and configuration
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def fetch_candles_parallel(exchange, symbol, timeframe, since, limit):
    # Calculate timeframe in milliseconds
    timeframe_ms = exchange.parse_timeframe(timeframe) * 1000
    # Build list of (since, until) windows
    windows = []
    current = since
    now_ms = exchange.milliseconds()
    while current < now_ms:
        windows.append(current)
        current += limit * timeframe_ms

    # Define coroutine for a single window
    async def fetch_window(start_ts):
        return await exchange.fetch_ohlcv(
            symbol, timeframe=timeframe, since=start_ts, limit=limit
        )

    results = []
    # Determine exchange rate limit in milliseconds (fallback to 1000 ms)
    rate_limit_ms = getattr(exchange, "rateLimit", 1000)
    for start_ts in windows:
        batch = await fetch_window(start_ts)
        results.append(batch)
        # Throttle to respect rate limit
        await asyncio.sleep(rate_limit_ms / 1000)
    # Flatten list of lists
    return [candle for batch in results for candle in batch]


# Initialize exchange (no API keys needed for public data)
exchange = ccxt.coinbase()

# Define symbol and timeframe
symbol = "BTC/USDT"
timeframe = "1m"

# Calculate timestamp for one year ago from now
one_year_ago = datetime.utcnow() - timedelta(days=365)
# Convert to milliseconds for API
since = int(one_year_ago.timestamp() * 1000)

# Fetch historical data in batches (Binance API allows 1000 candles per request)
batch_limit = 1000

# Log the start of data fetching
logging.info(
    f"Starting to fetch historical data for {symbol} from {one_year_ago.strftime('%Y-%m-%d')} to present."
)

# Use async fetch to populate all_candles
all_candles = asyncio.run(
    fetch_candles_parallel(exchange, symbol, timeframe, since, batch_limit)
)
logging.info(f"Completed fetching data. Total candles fetched: {len(all_candles)}.")

# Create DataFrame from candles
df = pd.DataFrame(
    all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"]
)
# Convert timestamp to datetime for readability (optional)
df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
df.set_index("datetime", inplace=True)
# Log before saving
logging.info("Saving fetched data to 'btc_data.csv'.")
df.to_csv("btc_data.csv", index=True)
# Log after saving
logging.info("Data successfully saved.")

# Close the async exchange client
asyncio.run(exchange.close())
