# Autoresearch Runbook — Reproducibility & Operations

## Quick Reference

| Task | Command |
|------|---------|
| Run single sector eval | `poetry run python -m autoresearch.evaluate --params autoresearch.params_<sector>` |
| Run OOS check | `poetry run python -m autoresearch.evaluate --params autoresearch.params_<sector> --start 2025-08-01 --end 2026-03-07` |
| Run portfolio backtest | `poetry run python -m autoresearch.portfolio_backtest --weights oos` |
| Paper trading (execute) | `poetry run python -m autoresearch.paper_trading --execute --state-path .paper_broker_state.json` |
| Daily automation | `./autoresearch/run_daily.sh` |
| Performance log | `poetry run python -m autoresearch.performance_tracker log` |
| Sector correlation | `poetry run python -m autoresearch.sector_correlation` |
| Walk-forward validation | `poetry run python -m autoresearch.walk_forward` |
| OOS weights (regime) | `poetry run python -m autoresearch.refresh_oos_weights --regime` |
| Cache prices (sector) | `poetry run python -m autoresearch.cache_signals --tickers X,Y,Z --prices-only --prices-path prices_<sector>.json` |
| Cache signals (full) | `poetry run python -m autoresearch.cache_signals --tickers AAPL,NVDA,...` |
| Daily config | `autoresearch/daily_config.json` (refresh_prices, cost_bps, email, etc.) |
| Health check | `poetry run python -m autoresearch.health_check` or `--once` for JSON |
| HTML report | `poetry run python -m autoresearch.performance_tracker report --output-html report.html --attribution` |
| Autoresearch loop | `poetry run python -m autoresearch.run_autoresearch_loop --sector equipment --iterations 5` |

---

## 1. Full Reproducibility (from scratch)

```bash
# 1. Install
poetry install

# 2. Cache prices for all sectors (requires API key for price data)
# Each sector has its own tickers; run for each:
poetry run python -m autoresearch.cache_signals --tickers MU,WDC,STX --prices-only --prices-path prices_memory.json
poetry run python -m autoresearch.cache_signals --tickers LITE,COHR --prices-only --prices-path prices_photonics.json
poetry run python -m autoresearch.cache_signals --tickers AAPL,NVDA,MSFT,GOOGL,TSLA --prices-only --prices-path prices.json
# ... (see SECTOR_CONFIG in portfolio_backtest.py for full list)

# 3. Run sector evals
poetry run python -m autoresearch.evaluate --params autoresearch.params_memory
poetry run python -m autoresearch.evaluate --params autoresearch.params_tech
# ...

# 4. Run portfolio backtest
poetry run python -m autoresearch.portfolio_backtest --weights oos
```

---

## 2. Refresh Price Caches

Prices can go stale. Refresh before major runs:

```bash
# One-liner: refresh all sectors (run from project root)
./autoresearch/refresh_all_prices.sh

# Or manually:
poetry run python -m autoresearch.cache_signals --tickers MU,WDC,STX --prices-only --prices-path prices_memory.json

# Tech
poetry run python -m autoresearch.cache_signals --tickers AAPL,NVDA,MSFT,GOOGL,TSLA --prices-only --prices-path prices.json

# Equipment
poetry run python -m autoresearch.cache_signals --tickers AMAT,ASML,LRCX,KLAC,TEL --prices-only --prices-path prices_equipment.json

# Platform
poetry run python -m autoresearch.cache_signals --tickers MSFT,AMZN,GOOGL,META,ORCL,PLTR --prices-only --prices-path prices_platform.json

# Foundry
poetry run python -m autoresearch.cache_signals --tickers TSM,GFS,UMC --prices-only --prices-path prices_foundry.json

# Power infra
poetry run python -m autoresearch.cache_signals --tickers VRT,CEG,EQT --prices-only --prices-path prices_power_infra.json

# Energy
poetry run python -m autoresearch.cache_signals --tickers XOM,CVX,OXY,SLB,EOG --prices-only --prices-path prices_energy.json

# Networking
poetry run python -m autoresearch.cache_signals --tickers ANET,AVGO,MRVL --prices-only --prices-path prices_networking.json

# Tokenization
poetry run python -m autoresearch.cache_signals --tickers COIN,HOOD,CRCL --prices-only --prices-path prices_tokenization.json

# Healthcare
poetry run python -m autoresearch.cache_signals --tickers JNJ,UNH,PFE,ABBV,LLY --prices-only --prices-path prices_healthcare.json

# Photonics
poetry run python -m autoresearch.cache_signals --tickers LITE,COHR --prices-only --prices-path prices_photonics.json
```

---

## 3. Refresh Signal Cache (Mode 2 / full-signal)

**Note:** Sectors use technical-only by default. Full-signal mode requires `signals.json`.

```bash
# Expensive: runs LLM agents for each business day
poetry run python -m autoresearch.cache_signals \
  --tickers AAPL,NVDA,MSFT,GOOGL,TSLA,MU,WDC,STX,AMAT,ASML,LRCX,KLAC,TEL \
  --start 2025-01-02 \
  --end 2026-03-07
```

Requires `OPENROUTER_API_KEY` or similar. See `autoresearch/cache_signals.py` for options.

---

## 4. Sector Tuning Loop

1. Edit `autoresearch/params_<sector>.py` (one param at a time)
2. Run `poetry run python -m autoresearch.evaluate --params autoresearch.params_<sector>`
3. If Sharpe improves: `git add autoresearch/params_<sector>.py autoresearch/results_<sector>.tsv && git commit -m "autoresearch[<sector>]: ..."`
4. If worse: `git checkout autoresearch/params_<sector>.py`
5. Every ~10 commits: run OOS check (`--start 2025-08-01 --end 2026-03-07`)

---

## 5. Portfolio Backtest Options

```bash
# Equal weight
poetry run python -m autoresearch.portfolio_backtest --weights equal

# Sharpe-weighted (tilt to high-Sharpe sectors)
poetry run python -m autoresearch.portfolio_backtest --weights sharpe

# OOS-weighted (recommended)
poetry run python -m autoresearch.portfolio_backtest --weights oos

# Exclude networking (OOS -0.09)
poetry run python -m autoresearch.portfolio_backtest --weights equal --exclude networking

# OOS validation window
poetry run python -m autoresearch.portfolio_backtest --weights oos --start 2025-08-01 --end 2026-03-07

# With transaction costs (see --cost-bps in portfolio_backtest)
poetry run python -m autoresearch.portfolio_backtest --weights oos --cost-bps 10
```

---

## 6. Paper Trading

```bash
# Dry run: what would we do today? (uses cached prices)
poetry run python -m autoresearch.paper_trading

# Execute: submit BUY/SELL orders to PaperBroker (rebalances to target; shorts skipped)
poetry run python -m autoresearch.paper_trading --execute --state-path .paper_broker_state.json

# With transaction costs (10 bps)
poetry run python -m autoresearch.paper_trading --execute --cost-bps 10

# Disable regime-adaptive scaling
poetry run python -m autoresearch.paper_trading --no-regime

# Lookback for signals (default 10 days)
poetry run python -m autoresearch.paper_trading --lookback-days 15

# Cap single-ticker weight (default 15%%)
poetry run python -m autoresearch.paper_trading --max-ticker-weight 0.10

# Specific date
poetry run python -m autoresearch.paper_trading --date 2026-03-07

# Equal weight instead of OOS
poetry run python -m autoresearch.paper_trading --weights equal
```

State is saved to `.paper_broker_state.json`. Use `performance_tracker log` to record daily portfolio value. Regime-adaptive scaling (bull=1.0, bear=0.5, sideways=0.75) reduces size in non-bull regimes.

---

## 6b. Daily Automation & Performance Tracking

```bash
# Cron-friendly daily run (refreshes prices by default, paper trade + log)
./autoresearch/run_daily.sh

# Skip price refresh (faster, uses cached prices):
REFRESH_PRICES=0 ./autoresearch/run_daily.sh

# Dry run (no --execute, for testing):
DRY_RUN=1 ./autoresearch/run_daily.sh

# Slack alerting (set DAILY_ALERT_URL to Slack webhook):
DAILY_ALERT_URL=https://hooks.slack.com/... ./autoresearch/run_daily.sh

# Example crontab (4pm ET weekdays):
# 0 16 * * 1-5 cd /path/to/ai-hedge-fund && ./autoresearch/run_daily.sh >> autoresearch/logs/daily.log 2>&1

# Log today's portfolio value
poetry run python -m autoresearch.performance_tracker log

# Rolling Sharpe and recent performance (vs SPY if prices_benchmark.json exists)
poetry run python -m autoresearch.performance_tracker report --days 60

# Export metrics to JSON
poetry run python -m autoresearch.performance_tracker report --output-json autoresearch/logs/metrics.json

# Compare live vs backtest returns
poetry run python -m autoresearch.performance_tracker compare --days 60
```

Logs go to `autoresearch/logs/performance.csv` and `autoresearch/logs/daily_YYYY-MM-DD.log`. Daily logs are rotated (keep last 30 days).

---

## 6c. Sector Correlation Analysis

```bash
# Compute correlation matrix of sector daily returns
poetry run python -m autoresearch.sector_correlation

# Save to CSV
poetry run python -m autoresearch.sector_correlation --output autoresearch/logs/sector_corr.csv

# OOS window
poetry run python -m autoresearch.sector_correlation --start 2025-08-01 --end 2026-03-07
```

---

## 6d. OOS Weight Refresh

Recompute sector OOS Sharpe and output updated `SECTOR_OOS_SHARPE` dict:

```bash
poetry run python -m autoresearch.refresh_oos_weights

# Custom window
poetry run python -m autoresearch.refresh_oos_weights --start 2025-08-01 --end 2026-03-07
```

Paste the output into `portfolio_backtest.py` to update weights. Use `--regime` for separate bull vs bear/sideways weights.

---

## 6e. Walk-Forward Validation

Rolling OOS validation to detect strategy decay:

```bash
poetry run python -m autoresearch.walk_forward

# 3-month windows, 1-month step
poetry run python -m autoresearch.walk_forward --window-months 3 --step-months 1

# Save to CSV
poetry run python -m autoresearch.walk_forward --output autoresearch/logs/walk_forward.csv
```

---

## 7. File Layout

| File | Purpose |
|------|---------|
| `params_<sector>.py` | Sector-specific params (only file to edit during tuning) |
| `evaluate.py` | Runs one backtest, prints val_sharpe |
| `fast_backtest.py` | Deterministic backtester |
| `portfolio_backtest.py` | Combines sector returns |
| `cache_signals.py` | Fetches prices + optional LLM signals |
| `paper_trading.py` | Paper trading; `--execute` submits to PaperBroker |
| `run_daily.sh` | Daily automation script (cron) |
| `performance_tracker.py` | Log portfolio value, rolling Sharpe |
| `sector_correlation.py` | Sector return correlation matrix |
| `refresh_oos_weights.py` | Recompute OOS Sharpe for sector weights |
| `walk_forward.py` | Rolling OOS validation |
| `cache/prices_benchmark.json` | SPY for regime detection |
| `cache/prices_<sector>.json` | Cached price data (gitignored) |
| `cache/signals.json` | Cached LLM signals (gitignored) |
| `results_<sector>.tsv` | Experiment log |
| `program_<sector>.md` | Tuning instructions |
| `ARR.md` | Master results doc |

---

## 8. Regime Robustness

Strategy is tuned for 2025 bull. For bear/sideways regimes:

- **RSI tuning:** Try RSI_OVERSOLD 30, RSI_OVERBOUGHT 70 (or 25/75) in params when market shifts
- **Regime detector:** `autoresearch/regime.py` provides `get_regime(close_series, lookback=20)` → "bull" | "bear" | "sideways"
- **Position scaling:** Use `regime_scale(regime)` to reduce size in bear (e.g. 0.5x)
- **Future:** Add SPY to cache, use as benchmark for regime filter in paper trading

---

## 9. Environment

- `POLYGON_API_KEY` or similar for price data (see `src/tools/api.py`)
- `OPENROUTER_API_KEY` for full-signal cache (optional)

---

## 10. Date Conventions (RUNBOOK)

### Lookback

- **Paper trading lookback** (`--lookback-days`, default 10): Number of calendar days before `--date` used for backtest signal generation. E.g. `--date 2026-03-10 --lookback-days 10` → backtest runs from 2026-02-28 to 2026-03-10.
- **Regime lookback** (`regime.py`, default 20): Trading days of benchmark (SPY) used for bull/bear/sideways classification.

### Cache Ranges

- **Price caches** (`prices_*.json`): Contain OHLCV by date. `refresh_all_prices.sh` fetches up to the most recent market close. Dates are `YYYY-MM-DD`.
- **Signal cache** (`signals.json`): LLM-generated signals per ticker per date. `--start`/`--end` in `cache_signals` define the range.

### Market Hours

- Daily run is intended for **after market close** (e.g. 4pm ET). Prices used are previous close.
- Paper trading `--date` is the "as-of" date: we use closing prices from that day (or latest in cache).

### Summary

| Concept | Default | Meaning |
|---------|---------|---------|
| `--date` | today | As-of date for paper trading |
| `--lookback-days` | 10 | Days of history for signal backtest |
| Regime lookback | 20 | Days of SPY for regime |
| Cache dates | — | Last close in each `prices_*.json` |
