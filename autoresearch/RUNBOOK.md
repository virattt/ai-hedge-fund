# Autoresearch Runbook — Reproducibility & Operations

## Quick Reference

| Task | Command |
|------|---------|
| Run single sector eval | `poetry run python -m autoresearch.evaluate --params autoresearch.params_<sector>` |
| Run OOS check | `poetry run python -m autoresearch.evaluate --params autoresearch.params_<sector> --start 2025-08-01 --end 2026-03-07` |
| Run portfolio backtest | `poetry run python -m autoresearch.portfolio_backtest --weights oos` |
| Cache prices (sector) | `poetry run python -m autoresearch.cache_signals --tickers X,Y,Z --prices-only --prices-path prices_<sector>.json` |
| Cache signals (full) | `poetry run python -m autoresearch.cache_signals --tickers AAPL,NVDA,...` |

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

## 6. Paper Trading (Dry Run)

```bash
# What would we do today? (uses cached prices)
poetry run python -m autoresearch.paper_trading

# Specific date
poetry run python -m autoresearch.paper_trading --date 2026-03-07

# Equal weight instead of OOS
poetry run python -m autoresearch.paper_trading --weights equal
```

Outputs suggested BUY/SHORT orders per ticker. For live execution, integrate with `src/execution/paper_broker.py` (TODO).

---

## 7. File Layout

| File | Purpose |
|------|---------|
| `params_<sector>.py` | Sector-specific params (only file to edit during tuning) |
| `evaluate.py` | Runs one backtest, prints val_sharpe |
| `fast_backtest.py` | Deterministic backtester |
| `portfolio_backtest.py` | Combines sector returns |
| `cache_signals.py` | Fetches prices + optional LLM signals |
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
