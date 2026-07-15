# AI Hedge Fund (personal fork)

A personal project built on [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund): multiple LLM “investor” agents analyze equities, a risk manager sizes positions, and a portfolio manager emits trade decisions. This fork adds **Alpaca paper/live execution**, a **composite data stack** (Alpaca + Finnhub), and a **US market-hours trading daemon** with a two-tier LLM strategy.

**Educational / research only.** Paper trading is supported; live money is opt-in and your responsibility.

Upstream vision and roadmap: [VISION.md](VISION.md), [ROADMAP.md](ROADMAP.md).

## What’s different in this fork

Custom code lives under `integrations/` so we can `git fetch upstream` without constant merge conflicts.

| Area | Location | Summary |
|------|----------|---------|
| **Alpaca broker & CLI** | `integrations/alpaca/` | `alpaca-fund` — sync portfolio, run agents, execute orders, **daemon** |
| **Composite data** | `integrations/data/` | `DATA_PROVIDER=composite` — Alpaca prices/news + Finnhub fundamentals |
| **Broker abstraction** | `integrations/broker/` | Pluggable `BrokerClient` (`noop`, Alpaca) |
| **Trading daemon** | `integrations/alpaca/scheduler.py` | Watch loop (live prices) → light/heavy escalation |
| **Cycle ledger** | `data/ledger/` | JSON log per run (`heavy` / `light` / `triggered_heavy`) |
| **Scheduler state** | `data/scheduler/` | Per-day session file for idempotency and triggers |
| **v2 quant stack** | `v2/` | PEAD signals, backtesting (upstream; not wired to daemon yet) |

Branch: `jason/alpaca` · Upstream remote: `upstream` → `virattt/ai-hedge-fund`

## Agents (upstream `src/`)

Persona agents (LLM), rule-based analysts (no LLM), risk manager (rules), portfolio manager (LLM):

- **LLM personas:** Warren Buffett, Charlie Munger, Michael Burry, Aswath Damodaran, and others
- **Rule-based:** technical, fundamentals, valuation, growth, sentiment
- **Always-on:** risk manager → portfolio manager

See the [upstream agent list](https://github.com/virattt/ai-hedge-fund) for the full roster.

## Disclaimer

- Not investment advice
- No guarantees; author assumes no liability for losses
- Past performance does not predict future results
- Use paper trading until you trust the system

## Table of contents

- [Install](#install)
- [Environment](#environment)
- [Quick start](#quick-start)
- [Alpaca CLI (`alpaca-fund`)](#alpaca-cli-alpaca-fund)
- [Trading daemon](#trading-daemon)
- [Backtesting](#backtesting)
- [Local LLMs (Ollama)](#local-llms-ollama)
- [Project layout](#project-layout)
- [Syncing upstream](#syncing-upstream)
- [Tests](#tests)
- [Web app (upstream)](#web-app-upstream)
- [License](#license)

## Install

```bash
git clone <your-repo-url> ai-hedge-fund
cd ai-hedge-fund

# Poetry (Python 3.11+)
poetry install --with alpaca
```

Copy env template and add keys:

```bash
cp .env.example .env   # if present; otherwise create .env in repo root
```

You need **at least one LLM provider** (OpenAI, Anthropic, Groq, or Ollama) and **market data** (composite or Financial Datasets).

## Environment

### Composite data (recommended)

```env
DATA_PROVIDER=composite

# Alpaca — prices, news, trading
ALPACA_API_KEY=your-paper-key
ALPACA_SECRET_KEY=your-paper-secret
ALPACA_PAPER=true

# Finnhub — fundamentals, insider, line items
FINNHUB_API_KEY=your-finnhub-key
```

Details: [integrations/data/README.md](integrations/data/README.md)

### LLM (pick one or more)

```env
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
# Or use Ollama locally — see below
```

### Trading safety gates

```env
LIVE_TRADING_ENABLED=false    # must be true (or --execute) to send orders
TRADING_KILL_SWITCH=false     # emergency stop for execution
MAX_ORDER_NOTIONAL=5000
ALLOWED_TICKERS=AAPL,MSFT,NVDA
MARGIN_REQUIREMENT=0.5
```

### Daemon / scheduler (optional)

```env
SCHEDULER_HEAVY_MODEL=gpt-5.5
SCHEDULER_HEAVY_PROVIDER=OpenAI
SCHEDULER_HEAVY_ANALYSTS=warren_buffett,charlie_munger,aswath_damodaran,michael_burry,valuation_analyst,fundamentals_analyst,technical_analyst
SCHEDULER_LIGHT_ANALYSTS=technical_analyst,fundamentals_analyst,valuation_analyst,growth_analyst,sentiment_analyst
SCHEDULER_OPEN_DELAY_MIN=5
SCHEDULER_LIGHT_INTERVAL_MIN=5
SCHEDULER_PRICE_SWING_PCT=2.0
SCHEDULER_SPY_MOVE_PCT=1.0
SCHEDULER_TRIGGER_COOLDOWN_MIN=30
```

## Quick start

**1. Check Alpaca connection**

```bash
poetry run alpaca-fund status
```

**2. Dry run (simulated $100k, no Alpaca account required)**

```bash
poetry run alpaca-fund --ticker AAPL --analysts warren_buffett --model gpt-5.5
```

**3. Paper sync (real account state, no orders)**

```bash
poetry run alpaca-fund --ticker AAPL,MSFT,NVDA --broker alpaca --analysts warren_buffett,valuation_analyst --model gpt-5.5
```

## Alpaca CLI (`alpaca-fund`)

Entry point: `integrations/alpaca/cli.py` · Full docs: [integrations/alpaca/README.md](integrations/alpaca/README.md)

| Command | Purpose |
|---------|---------|
| `alpaca-fund status` | Account, positions, market clock |
| `alpaca-fund --ticker …` | Single trading cycle |
| `alpaca-fund daemon --ticker …` | Market-hours scheduler |

**Useful flags**

```bash
--broker alpaca          # sync from Alpaca (default: noop dry run)
--execute                # submit orders (paper if ALPACA_PAPER=true)
--analysts warren_buffett,valuation_analyst
--analysts-all           # all agents (slow; many API calls)
--model gpt-5.5
--ollama                 # local LLM picker
--show-reasoning
--no-ledger              # skip data/ledger/ write
-v                       # debug logging
```

**Paper execution (one cycle)**

```bash
poetry run alpaca-fund --ticker AAPL --broker alpaca --execute --analysts warren_buffett --model gpt-5.5
```

**Upstream-style single run (no Alpaca integration)**

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --analysts warren_buffett --model gpt-5.5
```

## Trading daemon

Runs an **infinite watch loop** during US session (9:30–16:00 ET). Each ~60s tick fetches batched live prices (no LLM, no Finnhub fundamentals), runs algorithmic signals, and escalates only when needed:

| Layer | When | LLM? |
|-------|------|------|
| **Watch** | Every 60s | No — live price + momentum signals |
| **Light** | Every 5m or on watch alert | No — rule-based analysts |
| **Heavy** | At open + major moves/news | Yes |

**Test the daemon (read-only, safe)**

```bash
poetry run alpaca-fund daemon --ticker AAPL,MSFT,NVDA --broker alpaca -v
```

You'll see `--- WATCH ---` lines with prices, % moves, and escalation level. If the market is closed, it waits for the next open. Stop with `Ctrl+C`.

**Paper execution**

```bash
poetry run alpaca-fund daemon --ticker AAPL,MSFT --broker alpaca --execute -v
```

**Tune in `.env`:** `SCHEDULER_WATCH_INTERVAL_SEC`, `SCHEDULER_WATCH_TICK_MOVE_PCT`, `SCHEDULER_ALPACA_CALLS_PER_MIN`. Full list: [integrations/alpaca/README.md](integrations/alpaca/README.md).

Outputs:

- `data/ledger/` — decisions and fills per cycle (`cycle_kind`: `heavy`, `light`, `triggered_heavy`)
- `data/scheduler/YYYY-MM-DD.json` — open reference prices, last run times, news keys seen

## Backtesting

Simulates **one agent pipeline per business day** over a date range (upstream harness):

```bash
poetry run backtester --ticker AAPL --start-date 2025-06-01 --end-date 2025-06-15 --analysts warren_buffett --model gpt-5.5
```

Or:

```bash
poetry run python src/backtester.py --ticker AAPL,MSFT --ollama --analysts warren_buffett
```

Start with a **short window and few analysts** — each day is a full LLM run.

**v2 PEAD backtest** (quant, no LLM; expects Financial Datasets):

```bash
poetry run python -m v2.backtesting
```

## Local LLMs (Ollama)

```bash
poetry run alpaca-fund --ticker AAPL --ollama --analysts warren_buffett
poetry run python src/main.py --ticker AAPL --ollama
```

Use the exact model name from `ollama list` (e.g. `qwen3.6:latest`). Ollama must be running at `http://localhost:11434`.

## Project layout

```
integrations/
  alpaca/     # broker, run_cycle, scheduler, CLI, ledger
  broker/     # protocol, noop broker
  data/       # Alpaca + Finnhub composite → v1 API bridge
src/          # upstream agents, graph, backtester
v2/           # quant signals, backtesting (WIP)
data/
  ledger/     # cycle JSON (gitignored)
  scheduler/  # daemon session state (gitignored)
```

## Syncing upstream

```bash
git fetch upstream
git merge upstream/main
# resolve conflicts; integrations/ should stay mostly untouched
```

## Tests

```bash
poetry run pytest tests/integrations/ -q
poetry run pytest v2/ -q
```

## Web app (upstream)

The React/FastAPI UI in `app/` is from upstream. This fork’s day-to-day workflow is the **`alpaca-fund` CLI and daemon**. Web app setup: [app/README](app/) (if present) or [upstream docs](https://github.com/virattt/ai-hedge-fund/tree/main/app).

## License

MIT — see [LICENSE](LICENSE). Original project by [virattt](https://github.com/virattt/ai-hedge-fund).
