# Keyless data client: Yahoo, SEC EDGAR and Alpha Vantage

A `DataClient` for v2 that needs no Financial Datasets key and no wallet.

| Method | Source |
|---|---|
| prices, market cap | Yahoo Finance (daily bars) |
| financial metrics, company facts | SEC EDGAR company facts, as filed: each row is the twelve months to a filing, computed as of the day before the next one |
| insider trades | SEC Form 4 filings, by filing date (open-market buys and sells) |
| news, earnings history and estimates | Alpha Vantage (`ALPHA_VANTAGE_API_KEY`; news by date range needs a premium key) |

It follows the contract in `hedge_fund/data/protocol.py`: only what was public by `end_date`, and a failed
request raises. Minute bars are not provided, and metrics these sources lack (inventory turnover,
EV/EBITDA, interest coverage) are `None`.

`run_backtest.py` is `aihf backtest` with this client, and with OpenAI model ids outside the registry's
short list (for example `gpt-6-luna`) routed to OpenAI instead of falling through to Anthropic. It also
expires the cache's date-less answers after a day, which works around #724 (earnings history never
refreshes when the client is not live).

```bash
export OPENAI_API_KEY=... ALPHA_VANTAGE_API_KEY=...
python contrib/alpha_glue/run_backtest.py ~/.hedge-fund/mandates/example.yaml \
    --universe AAPL,NVDA,MSFT --start 2026-07-06 --end 2026-10-26 --model gpt-6-luna
```

Needs `pip install yfinance requests` next to the package's own dependencies. Backtest only: `aihf paper`
still builds its own Financial Datasets client.

Tests: `python -m unittest test_alpha_client` from this folder. They are offline and cover the as-filed arithmetic and the Form 4 parser.
