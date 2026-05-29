# Financial Data Providers

Open Hedge fetches prices, fundamentals, news, and related inputs through a pluggable data layer. You can run the simulator **without** a [Financial Datasets](https://financialdatasets.ai/) API key by using the free **Yahoo Finance** integration via the modern, feature-rich [`yfinance-rs`](https://github.com/gramistella/yfinance-rs) library.

For endpoint-level differences, fallbacks, and backtest caveats, see [Yahoo Finance vs. Financial Datasets — Capabilities and Limitations](yahoo_finance_limitations.md).

---

## How the active provider is chosen

Resolution order (first match wins):

1. **Explicit CLI override** — `--data-provider financial-datasets` or `--data-provider yahoo-finance` (also accepts `financial_datasets` / `yahoo_finance`).
2. **Environment** — if `FINANCIAL_DATASETS_API_KEY` is set to a non-empty, non-placeholder value, use Financial Datasets.
3. **Default** — Yahoo Finance (no paid market-data key required).

The resolved provider is stored for the process via `configure_provider` in `src/data/provider.rs` and surfaced in workflow metadata as `data_provider`.

---

## Quickstart (no market-data API key)

1. Copy `.env.example` to `.env` and set **at least one LLM** API key (for example `OPENAI_API_KEY`).
2. Leave `FINANCIAL_DATASETS_API_KEY` unset or at the placeholder value.
3. Run a backtest:

```bash
cargo run --bin backtester -- --ticker AAPL,MSFT,NVDA --start-date 2026-01-01 --end-date 2026-02-01
```

You should see a log line indicating Yahoo Finance as the data provider.

---

## CLI: `--data-provider`

The flag is defined on the shared CLI (`src/cli/input.rs`) and is wired on the **backtester** binary:

```bash
# Force free Yahoo Finance even if FINANCIAL_DATASETS_API_KEY is set
cargo run --bin backtester -- --ticker AAPL --data-provider yahoo-finance

# Force Financial Datasets (requires a valid FINANCIAL_DATASETS_API_KEY)
cargo run --bin backtester -- --ticker AAPL --data-provider financial-datasets
```

---

## Environment: Financial Datasets (premium)

To use institutional-grade data from Financial Datasets:

1. Obtain an API key from [financialdatasets.ai](https://financialdatasets.ai/).
2. Set it in `.env`:

```bash
FINANCIAL_DATASETS_API_KEY=your-actual-key-here
```

With a valid key and no `--data-provider` override, Open Hedge selects **financial-datasets** automatically.

Placeholder values in `.env.example` (`your-financial-datasets-api-key`) are ignored and treated as unset.

---

## Web dashboard

The Axum backend (`app-backend`) calls the same `resolve_data_provider` logic on each run and backtest: it reads `FINANCIAL_DATASETS_API_KEY` from the environment (including keys saved through the dashboard). There is **no provider toggle in the UI yet**; configure the key in `.env` or the dashboard settings to switch sources.

---

## Scope at a glance

| Area | Yahoo Finance (free) | Financial Datasets (paid) |
| :--- | :--- | :--- |
| Historical daily prices | Yes | Yes |
| Rich SEC line items & ratios | Limited; derived fallbacks + quarterly depth | Full |
| Insider trades | `holders()` insider transactions (signed buy/sell) | Full history |
| News sentiment | Headlines; neutral default; LLM in news agent | Scored sentiment |
| Point-in-time fundamentals | Cutoff by date; no true as-filed history | Strict PIT |
| Analyst consensus / price targets | Available in crate; not wired to agents | N/A |

See the [limitations doc](yahoo_finance_limitations.md) for the full matrix and fallback behavior.
