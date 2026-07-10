# Composite Data Provider (Option A)

Replace Financial Datasets with **Alpaca** (prices, news) + **Finnhub** (fundamentals).

## Setup

Add to your `.env`:

```env
DATA_PROVIDER=composite

# Alpaca (prices + news + trading)
ALPACA_API_KEY=your-paper-key
ALPACA_SECRET_KEY=your-paper-secret

# Finnhub (fundamentals, earnings, insider trades)
FINNHUB_API_KEY=your-finnhub-key
```

Get a free Finnhub key at https://finnhub.io/register (60 API calls/min).

Install with Alpaca SDK:

```bash
poetry install --with alpaca
```

## What routes where

| Data | Provider |
|------|----------|
| OHLCV prices | Alpaca Market Data |
| Company news | Alpaca (Benzinga) |
| Financial metrics | Finnhub |
| Line items / statements | Finnhub (SEC XBRL) |
| Earnings history (PEAD) | Finnhub |
| Insider trades | Finnhub |
| Company profile / market cap | Finnhub |
| Order execution | Alpaca Trading API |

## Usage

Once `DATA_PROVIDER=composite` is set, **no code changes needed** — v1 agents and the CLI automatically use the composite backend via `src/tools/api.py`.

```bash
poetry run alpaca-fund --ticker AAPL,MSFT,NVDA --broker alpaca --analysts-all --model gpt-4.1
```

For v2 directly:

```python
from integrations.data import get_data_client

with get_data_client() as client:
    prices = client.get_prices("AAPL", "2024-01-01", "2024-12-31")
```

## Switching back to Financial Datasets

```env
DATA_PROVIDER=financialdatasets
FINANCIAL_DATASETS_API_KEY=your-key
```

## Known limitations vs Financial Datasets

- **Earnings filing dates** — Finnhub uses announcement dates from the earnings calendar; SEC filing metadata (8-K vs 10-Q) is approximated.
- **Line items** — Mapped from US-GAAP XBRL concepts; some FD field names may return empty if the concept isn't in the filing.
- **Historical market cap** — Finnhub provides current market cap; historical point-in-time cap is approximate.
- **Rate limits** — Finnhub free tier: 60 calls/min. Agent runs on many tickers may need caching (built into `src/tools/api.py`).
