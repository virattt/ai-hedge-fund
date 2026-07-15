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
poetry run alpaca-fund --ticker AAPL,MSFT,NVDA --analysts-all --model gpt-5.5
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
poetry run alpaca-fund --ticker AAPL,MSFT,NVDA --broker alpaca --analysts-all --model gpt-5.5
```

### Enable paper order execution (per-run)

```bash
poetry run alpaca-fund --ticker AAPL --broker alpaca --execute --analysts-all --model gpt-5.5
```

### Data-driven universe (instead of --ticker)

Build a ranked universe once, then trade it. See `integrations/universe/README.md`.

```bash
poetry run alpaca-fund universe build            # writes data/universe/YYYY-MM-DD.json
poetry run alpaca-fund universe show
poetry run alpaca-fund run --universe latest --broker alpaca --analysts-all --model gpt-5.5
poetry run alpaca-fund daemon --universe latest --broker alpaca
poetry run alpaca-fund universe backtest         # ranked vs legacy list vs top dollar volume
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

The daemon runs an **infinite watch loop** during the session. Each iteration is cheap; LLM and Finnhub only run when escalated.

| Layer | Interval | Data | LLM |
|-------|----------|------|-----|
| **Watch** | Every 60s (configurable) | Batched Alpaca snapshots | No |
| **Light** | Every 5m or on watch signal | Rule-based analysts + Finnhub | No |
| **Heavy** | At open + on major signal | Full analyst panel | Yes |
| **Triggered heavy** | Price/SPY/news threshold | Same as heavy | Yes |

Light cycles trade toward a **conviction-scaled target position** (signal
strength × the name's risk limit) and only order the delta, so a persistent
signal converges on a stable position instead of stacking new orders every
few minutes. Votes below 0.5 conviction and adds smaller than 5% of the
limit are skipped.

Position sizing sees the broker's real **equity and buying power** (Alpaca's
raw "cash" includes short-sale proceeds and overstates capacity). When the
account is at its Reg-T limit, new buys/shorts size to zero and only
position-closing trades pass; a broker-rejected order becomes a failed
execution result instead of aborting the cycle.

### Lazy universe rotation

Analysis cycles never run the full universe at once — important with a large
`--universe` (e.g. 127 names), which would blow past Finnhub rate limits and
take forever at the open:

- **Held positions are analyzed in every cycle.** They're merged into every
  run automatically, so your actual portfolio is always covered.
- **Speculative (non-held) tickers rotate in batches** of
  `SCHEDULER_BATCH_SIZE` (default 10). The open heavy cycle takes holdings +
  one batch; each light cycle advances to the next batch, cycling through
  the whole universe over the day. Alert-driven light cycles give alerting
  symbols up to half the batch and fill the rest from the rotation, so
  rotation keeps progressing even when something is always alerting.
- **Triggered cycles are scoped to what fired.** A heavy trigger (vs-open
  price swing, news headline) re-analyzes only the symbols whose heavy signal
  fired, capped at `SCHEDULER_BATCH_SIZE`, plus holdings. Light-level tick
  moves never ride along into an LLM cycle — they go to the (capped) light
  focus list instead. A market-wide alert (SPY move) re-analyzes holdings
  only.
- **The watch loop still covers everything** — price snapshots for the full
  universe come from one batched Alpaca call, so any name can raise an alert
  at any time. Tickers not yet analyzed get their first watch price as the
  vs-open reference.
- **Failed open cycles back off.** If the heavy open crashes (e.g. a
  provider 429), the daemon waits `SCHEDULER_HEAVY_OPEN_RETRY_MIN`
  (default 10) before retrying instead of hammering the API every 30s.

**Watch signals (algorithmic, no LLM):**

- Move vs session open reference (→ heavy)
- Move vs last watch tick (→ light)
- Short momentum over last N ticks (→ light)
- SPY move vs open (→ heavy)
- New headlines on news check interval (→ heavy)

```bash
# Paper account, read-only (no orders)
poetry run alpaca-fund daemon --ticker AAPL,MSFT,NVDA --broker alpaca -v
```

Session state: `data/scheduler/YYYY-MM-DD.json`. Ledger: `cycle_kind` = `heavy`, `light`, `triggered_heavy`.

### Scheduler environment variables

```env
# Heavy cycle (LLM)
SCHEDULER_HEAVY_MODEL=gpt-5.5
SCHEDULER_HEAVY_PROVIDER=OpenAI
SCHEDULER_HEAVY_ANALYSTS=warren_buffett,charlie_munger,aswath_damodaran,michael_burry,valuation_analyst,fundamentals_analyst,technical_analyst

# Light cycle (no LLM)
SCHEDULER_LIGHT_ANALYSTS=technical_analyst,fundamentals_analyst,valuation_analyst,growth_analyst,sentiment_analyst

# Watch loop (live price tracking)
SCHEDULER_WATCH_INTERVAL_SEC=60
SCHEDULER_WATCH_TICK_MOVE_PCT=0.75    # % since last poll → light
SCHEDULER_WATCH_MOMENTUM_PCT=1.5
SCHEDULER_WATCH_MOMENTUM_TICKS=5

# Timing
SCHEDULER_OPEN_DELAY_MIN=5
SCHEDULER_LIGHT_INTERVAL_MIN=5
SCHEDULER_LIGHT_COOLDOWN_MIN=3
SCHEDULER_NEWS_CHECK_INTERVAL_MIN=5

# Escalation thresholds
SCHEDULER_PRICE_SWING_PCT=2.0         # vs open → heavy
SCHEDULER_SPY_MOVE_PCT=1.0
SCHEDULER_TRIGGER_COOLDOWN_MIN=30

# Lazy universe rotation
SCHEDULER_BATCH_SIZE=10               # speculative tickers per analysis cycle
SCHEDULER_HEAVY_OPEN_RETRY_MIN=10     # backoff after a failed open cycle

# API rate limits (rolling per minute)
SCHEDULER_ALPACA_CALLS_PER_MIN=100
SCHEDULER_NEWS_CALLS_PER_MIN=30
FINNHUB_CALLS_PER_MIN=50              # global gate on all Finnhub calls (free tier = 60)

# End-of-day reports
SCHEDULER_EOD_REPORTS=true            # daily/weekly/monthly/yearly reports after close

# Risk governor (hard execution guardrails; reductions always pass)
RISK_GOVERNOR_ENABLED=true
RISK_MAX_TURNOVER_X=1.0               # daily submitted notional cap, x equity
RISK_MAX_FILLS_PER_DAY=40             # risk-increasing orders per day
RISK_SYMBOL_COOLDOWN_MIN=60           # no re-entry/resize of a symbol within N minutes
RISK_MAX_OPEN_POSITIONS=15            # new names blocked above this count
RISK_MAX_INTRADAY_DRAWDOWN_PCT=0.5    # below day-open equity => reductions only
RISK_MIN_TRIGGERED_CONFIDENCE=70      # min conviction for triggered-heavy entries
```

## Risk governor

Every order passes through `integrations/alpaca/risk_governor.py` before
submission (Alpaca broker only). Risk-reducing orders — selling an existing
long or covering an existing short — are never vetoed. Risk-increasing orders
are blocked when any of these trip:

- **Turnover cap** — total submitted notional for the day would exceed
  `RISK_MAX_TURNOVER_X` × equity.
- **Fill cap** — more than `RISK_MAX_FILLS_PER_DAY` orders submitted today.
- **Symbol cooldown** — the symbol traded within the last
  `RISK_SYMBOL_COOLDOWN_MIN` minutes (stops same-day whipsaw round trips).
- **Position count** — opening a *new* name when `RISK_MAX_OPEN_POSITIONS`
  positions are already open (resizing held names still allowed).
- **Drawdown breaker** — equity is `RISK_MAX_INTRADAY_DRAWDOWN_PCT`% below
  the day's opening equity; only reductions pass until recovery.
- **Conviction gate** — triggered-heavy entries below
  `RISK_MIN_TRIGGERED_CONFIDENCE`% confidence are dropped.

Vetoed orders appear in the console and ledger as
`Risk governor: <reason>`. Budgets persist in
`data/scheduler/risk-YYYY-MM-DD.json`, so daemon restarts and manual
`alpaca-fund run` invocations share the same daily limits.

Stop with `Ctrl+C`. Respect `TRADING_KILL_SWITCH` and `MAX_ORDER_NOTIONAL` as in single-run mode.

## Performance reports

After the close, the daemon automatically generates performance reports from
Alpaca fills, positions, and the day's cycle ledgers (once per trading day,
tracked in the session file):

- **Daily** — every trading day: P&L, turnover, realized P&L per symbol
  (average-cost method), win/loss counts, open positions, cycle counts, and
  the per-cycle equity curve.
- **Weekly / monthly / yearly** — generated on the last trading day of each
  period by aggregating the stored daily reports.

Reports are saved to `data/reports/<period>/<end-date>.json` (machine-readable)
and `.md` (human-readable). Each report ends with an **upgrade advisory**: a
two-paragraph prompt written by the heavy LLM that diagnoses the most costly
behaviors in the numbers and prescribes concrete code changes — paste it into
Cursor to drive the next iteration of the system. If the LLM is unreachable, a
rule-based fallback advisory is used.

Manual generation:

```bash
# Today's daily report (+ weekly/monthly/yearly if the period ends today)
poetry run alpaca-fund report --period all

# A specific period / date
poetry run alpaca-fund report --period weekly --date 2026-07-10
poetry run alpaca-fund report --period daily --no-advisory
```
