"""
Run agents on TSM with synthetic price data at $342.20 and NVDA with real data.
Outputs raw JSON for further synthesis.
"""
import json
import math
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from src.data.cache import get_cache
from src.data.models import Price
from src.main import run_hedge_fund

# ---------- Generate synthetic TSM price history around $342.20 ----------
cache = get_cache()
end_date = datetime(2026, 3, 24)
start_date = end_date - timedelta(days=365)

np.random.seed(42)
prices = []
price = 342.20
# Walk backwards to generate 252 trading days
dates = []
d = end_date
while d >= start_date:
    if d.weekday() < 5:  # weekdays only
        dates.append(d)
    d -= timedelta(days=1)
dates.reverse()

# Forward walk with realistic vol (~35% annualized → ~2.2% daily)
daily_vol = 0.35 / math.sqrt(252)
price = 342.20 / math.exp(sum(np.random.normal(0, daily_vol) for _ in range(len(dates) - 1)))
for d in dates:
    ret = np.random.normal(0.0003, daily_vol)  # slight drift
    price *= math.exp(ret)
    high = price * (1 + abs(np.random.normal(0, 0.008)))
    low = price * (1 - abs(np.random.normal(0, 0.008)))
    vol = int(np.random.lognormal(16, 0.5))
    prices.append(Price(
        time=d.strftime("%Y-%m-%d"),
        open=round(price * (1 + np.random.normal(0, 0.002)), 2),
        close=round(price, 2),
        high=round(high, 2),
        low=round(low, 2),
        volume=vol,
    ))

# Final price should be ~342.20
scale = 342.20 / prices[-1].close
for p in prices:
    p.open = round(p.open * scale, 2)
    p.close = round(p.close * scale, 2)
    p.high = round(p.high * scale, 2)
    p.low = round(p.low * scale, 2)

# Cache the prices
cache_key = f"TSM_{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}"
cache.set_prices(cache_key, [p.model_dump() for p in prices])

# Also cache for the agent's own date range lookups
for months_back in [3, 6, 12]:
    alt_start = (end_date - timedelta(days=30 * months_back)).strftime("%Y-%m-%d")
    alt_key = f"TSM_{alt_start}_{end_date.strftime('%Y-%m-%d')}"
    subset = [p.model_dump() for p in prices if p.time >= alt_start]
    if subset:
        cache.set_prices(alt_key, subset)

print(f"Cached {len(prices)} TSM price points, final close: ${prices[-1].close}")

# ---------- Run the agents ----------
tickers = ["TSM", "NVDA"]
portfolio = {
    "cash": 100000.0,
    "margin_requirement": 0.0,
    "margin_used": 0.0,
    "positions": {t: {"long": 0, "short": 0, "long_cost_basis": 0.0, "short_cost_basis": 0.0, "short_margin_used": 0.0} for t in tickers},
    "realized_gains": {t: {"long": 0.0, "short": 0.0} for t in tickers},
}

result = run_hedge_fund(
    tickers=tickers,
    start_date=start_date.strftime("%Y-%m-%d"),
    end_date=end_date.strftime("%Y-%m-%d"),
    portfolio=portfolio,
    show_reasoning=True,
    selected_analysts=["rentec", "michael_burry", "stanley_druckenmiller", "technical_analyst", "sentiment_analyst"],
    model_name="claude-sonnet-4-5-20250929",
    model_provider="Anthropic",
)

# Output raw results as JSON
print("\n\n===== RAW RESULTS JSON =====")
print(json.dumps(result, indent=2, default=str))
