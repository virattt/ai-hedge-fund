# Alpaca Integration

Connect the AI hedge fund to [Alpaca](https://alpaca.markets/) for portfolio sync and (optionally) order execution.

## Setup

1. Create a free Alpaca account and generate **paper** API keys at https://app.alpaca.markets/
2. Add keys to your root `.env` file:

```env
# Alpaca (paper trading by default)
ALPACA_API_KEY=your-paper-api-key
ALPACA_SECRET_KEY=your-paper-secret-key
ALPACA_PAPER=true

# Safety gates — execution is OFF by default
LIVE_TRADING_ENABLED=false
TRADING_KILL_SWITCH=false
MAX_ORDER_NOTIONAL=5000
ALLOWED_TICKERS=AAPL,MSFT,NVDA
```

3. Install dependencies (including Alpaca SDK):

```bash
poetry install --with alpaca
```

## Usage

### No-op broker (default — safe, no Alpaca needed)

Runs agents against a simulated $100k portfolio. Logs what would be traded.

```bash
poetry run alpaca-fund --ticker AAPL,MSFT,NVDA --analysts-all --model gpt-4.1
```

Results are saved to `data/ledger/` after each run.

### Check Alpaca connection

Verify API keys and view account state without running agents:

```bash
poetry run alpaca-fund status
```

### Alpaca read-only sync

Pulls your real Alpaca account state, runs agents, prints decisions. **Does not submit orders.**

```bash
poetry run alpaca-fund --ticker AAPL,MSFT,NVDA --broker alpaca --analysts-all --model gpt-4.1
```

### Enable paper order execution (per-run)

```bash
poetry run alpaca-fund --ticker AAPL --broker alpaca --execute --analysts-all --model gpt-4.1
```

Or set in `.env` for all runs:

```env
LIVE_TRADING_ENABLED=true
ALPACA_PAPER=true
```

## Safety

| Variable | Default | Purpose |
|----------|---------|---------|
| `ALPACA_PAPER` | `true` | Use paper trading endpoint |
| `LIVE_TRADING_ENABLED` | `false` | Must be `true` (or use `--execute`) to submit orders |
| `TRADING_KILL_SWITCH` | `false` | Blocks all execution when `true` |
| `MAX_ORDER_NOTIONAL` | `5000` | Max dollar value per order |
| `ALLOWED_TICKERS` | (empty) | Whitelist; empty = all allowed |

**Never set `ALPACA_PAPER=false` and `LIVE_TRADING_ENABLED=true` until you have validated paper trading thoroughly.**

## Architecture

```
agents (upstream src/) → decisions → executor → broker protocol → AlpacaBroker
```

See `integrations/broker/protocol.py` for the broker interface.

## Trading daemon (US market hours)

Runs a **two-tier strategy** to limit costly LLM usage:

| Cycle | When | Analysts | LLM |
|-------|------|----------|-----|
| **Heavy** | Once at open (default 9:35 ET) | Configurable panel (LLM personas + anchors) | Yes |
| **Light** | Every 5 minutes during session | Rule-based only | No |
| **Triggered heavy** | On price swing, SPY move, or new news | Same as heavy | Yes |

```bash
# Paper account, read-only (no orders)
poetry run alpaca-fund daemon --ticker AAPL,MSFT,NVDA --broker alpaca

# Paper execution enabled
poetry run alpaca-fund daemon --ticker AAPL,MSFT --broker alpaca --execute
```

Session state is stored in `data/scheduler/YYYY-MM-DD.json`. Ledger entries include `cycle_kind` (`heavy`, `light`, `triggered_heavy`).

### Scheduler environment variables

```env
# Heavy cycle (LLM)
SCHEDULER_HEAVY_MODEL=gpt-4.1
SCHEDULER_HEAVY_PROVIDER=OpenAI
SCHEDULER_HEAVY_ANALYSTS=warren_buffett,charlie_munger,aswath_damodaran,michael_burry,valuation_analyst,fundamentals_analyst,technical_analyst

# Light cycle (no LLM)
SCHEDULER_LIGHT_ANALYSTS=technical_analyst,fundamentals_analyst,valuation_analyst,growth_analyst,sentiment_analyst

# Timing
SCHEDULER_OPEN_DELAY_MIN=5          # minutes after 9:30 ET
SCHEDULER_LIGHT_INTERVAL_MIN=5

# Triggers for promoted heavy re-analysis
SCHEDULER_PRICE_SWING_PCT=2.0       # vs open reference price
SCHEDULER_SPY_MOVE_PCT=1.0
SCHEDULER_TRIGGER_COOLDOWN_MIN=30   # min gap between triggered heavies
SCHEDULER_NEWS_LOOKBACK_HOURS=24
```

Stop with `Ctrl+C`. Respect `TRADING_KILL_SWITCH` and `MAX_ORDER_NOTIONAL` as in single-run mode.
