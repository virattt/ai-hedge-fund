# Yahoo Finance vs. Financial Datasets API — Capabilities and Limitations

This document maps differences between the premium **Financial Datasets API** ([financialdatasets.ai](https://financialdatasets.ai/)) and the free **Yahoo Finance** integration via the modern [`yfinance-rs`](https://github.com/gramistella/yfinance-rs) library (Rust crate name; imported as `yfinance`). It explains how **Open Hedge** handles gaps using derived metrics, Yahoo modules, and safe defaults.

**Related:** [Financial Data Providers](data_providers.md) (defaults, CLI `--data-provider`, environment variables).

---

## 1. Capability matrix (yfinance-style API vs Open Hedge)

The Python `yfinance` surface is largely mirrored by `yfinance-rs`. The table below lists **gaps for agents/backtests**, not every method the crate exposes.

| Limitation | Current workaround | Yahoo endpoint / crate method | Priority |
| :--- | :--- | :--- | :--- |
| **Insider trading log** | ~~Empty list, neutral sentiment~~ **Implemented:** `holders()` → `insider_transactions`, signed buy/sell shares | `Ticker::holders()` | **High** — fixed |
| **Pre-computed news sentiment** | Headlines via `news()`; default `neutral`; LLM classifies in `news_sentiment` agent | `Ticker::news()` | **High** — partial (no Yahoo scores) |
| **Point-in-time fundamentals** | TTM/quarterly snapshots with `end_date` cutoff; no true as-filed history; backtests use latest available rows ≤ date | `quarterly_*`, `earnings()`, `calendar()` | **High** — documented only |
| **Growth rates on metrics rows** | Derived YoY (4+ quarters) or PoP; tiered growth-agent scoring | `quarterly_income_stmt` + `earnings()` supplement | **High** — improved |
| **Quarterly history depth** | Request `limit.max(8)` for quarterly/TTM; merge `earnings()` for missing EPS/revenue | `quarterly_*`, `earnings()` | **High** — improved |
| **Rich SEC line-item search** | Map ~30 fields from fundamentals timeseries; derive working capital, equity, book value/share | `quarterly_income_stmt`, `quarterly_balance_sheet`, `quarterly_cashflow` | **High** — partial |
| **Enterprise value / EV ratios** | Often `None`; agents skip EV-based signals | `info()` / `financialData` | **Medium** |
| **ROIC, turnover, DSO, quick ratio** | `None` unless computable from sparse Yahoo keys | `info()`, fundamentals | **Medium** |
| **Analyst recommendations / price targets** | Not wired to agents; available from crate | `recommendations_summary()`, `price_target()` | **Medium** — open |
| **Earnings calendar / ex-div dates** | Not used in backtest engine | `calendar()` | **Medium** — open |
| **Historical shares outstanding series** | Single period from balance sheet | `shares()`, `quarterly_shares()` | **Low** |
| **Institutional / fund holders** | Not used by agents | `holders()` institutional / mutual_fund lists | **Low** |
| **Options chains** | Not implemented (out of scope) | `options()`, `option_chain()` | **Low** — N/A |
| **WebSocket quotes** | Not implemented (out of scope) | `stream()` | **Low** — N/A |
| **ISIN lookup** | Not implemented (out of scope) | `isin()` | **Low** — N/A |
| **ESG / sustainability** | Not implemented (out of scope) | `sustainability()` | **Low** — N/A |

---

## 2. What Open Hedge implements today (`src/tools/fallback.rs`)

| Agent / backtest need | Yahoo source | Notes |
| :--- | :--- | :--- |
| Daily OHLCV | `history()` via `get_prices_yfinance` | Adjusted prices |
| Financial metrics | `info()` + `quarterly_*` + `earnings()` | Derived margins, growth, ratios |
| Line items | `quarterly_*` | Filtered by requested field names |
| Insider trades | `holders().insider_transactions` | Buy/sell sign from transaction text |
| Company news | `news()` | Neutral default sentiment |
| Market cap | `info().market_cap` | `get_market_cap` in `api.rs` |

**Not wired:** `recommendations_summary`, `price_target`, `upgrades_downgrades`, `earnings_trend`, `calendar`, `shares`, options, stream, ISIN, ESG.

---

## 3. Point-in-time integrity (backtests)

- **Financial Datasets:** Strict point-in-time — data as known on each simulation date.
- **Yahoo Finance:** Public APIs expose **current** or **latest filed** fundamentals, not historical quoteSummary as-of a past date. Open Hedge:
  - Filters rows with `report_period <= end_date` (and news/insider by filing/transaction date).
  - Does **not** apply a fixed 45-day publication lag automatically; agents may still see lookahead if Yahoo has already published a quarter early.
  - **Honest limit:** Historical backtests on Yahoo are suitable for price-driven simulation; fundamental signals should be treated as approximate unless you add explicit lag logic or use Financial Datasets.

`calendar().earnings_dates` can inform future work (event-aware lag) but is not used in the engine yet.

---

## 4. Safe derived calculations (heuristics)

When SEC line items are missing:

1. **Working capital** = Current Assets − Current Liabilities  
2. **Shareholders' equity** = Total Assets − Total Liabilities (if equity missing)  
3. **Book value per share** = Shareholders' equity ÷ ordinary shares (line items)  
4. **Growth rates** — YoY when 5+ quarterly rows exist, else period-over-period on revenue, EPS, FCF, operating income  
5. **Insider activity** — Signed shares from transaction description (`Sale` → negative, `Purchase` → positive)  
6. **News sentiment** — `neutral` until the news sentiment agent runs LLM classification  

---

## 5. Crate coverage reference (not all used by Open Hedge)

| yfinance-style API | `yfinance-rs` | Used in Open Hedge |
| :--- | :---: | :---: |
| `history()` | Yes | Yes |
| `quote()` / `fast_info()` | Yes | Partial (`info`) |
| `info()` | Yes | Yes |
| `income_stmt` / `balance_sheet` / `cashflow` + quarterly | Yes | Yes |
| `earnings()` | Yes | Yes (supplement) |
| `calendar()` | Yes | No |
| `shares()` / `quarterly_shares()` | Yes | No |
| `recommendations*`, `price_target`, `earnings_trend` | Yes | No |
| `sustainability()` | Yes | No |
| `holders()` | Yes | Yes (insider txs) |
| `options()` / `option_chain()` | Yes | No |
| `news()` | Yes | Yes |
| `profile()` / `isin()` / `stream()` | Yes | No |

---

## See also

- [Financial Data Providers](data_providers.md) — defaults and configuration  
- [README](../README.md#financial-data-providers) — project quickstart  
