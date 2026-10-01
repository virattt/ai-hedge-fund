# v2 — AI Hedge Fund core

> **Status: Work in progress.** A ground-up rebuild of the engine, developed
> alongside the shipped v1 app (`src/`, `app/`) but not yet wired into it.
> See [`../VISION.md`](../VISION.md) and [`../ROADMAP.md`](../ROADMAP.md) for
> where this is headed.

v2 rebuilds the fund as a persistent, point-in-time-honest system, mirroring a
real shop's hierarchy:

```
FUND      =  capital slices over STRATEGIES   (master risk on the netted book)
STRATEGY  =  a blend policy over MODELS       (a "pod")
MODEL     =  an alpha model → a Signal        (conviction in [-1,+1] + thesis)
```

A fund is the **desk**, not a watchlist: the mandate names no tickers. The
universe is fixed when you backtest or deploy the mandate (`--universe`, or
the app's ticker prompt) and recorded on every `SessionRecord` — so one
mandate can be pointed at anything, and every record remembers what it traded.

A fund runs two kinds of pods, like a real shop. **Discretionary** strategies
are staffed by **agents** — LLM investor personas (Warren Buffett, Charlie
Munger, Benjamin Graham, Peter Lynch, Stanley Druckenmiller) whose judgment
is the edge; blend them long-biased or market-neutral. **Systematic**
strategies are powered by quant models (post-earnings drift) — the model *is*
the strategy, no persona attached. Both kinds implement one interface and
plug into the same engine unchanged.

A fund runs in two modes, and both are the same verb, `advance(fund, state,
session, broker, data, universe)`, called once per completed session:

- **Backtest** — `advance` looped over history with an in-memory state and a
  simulated broker. Produces an equity curve against your benchmark and a
  `SessionRecord` for every session.
- **Paper** — a *deployed* fund: the mandate snapshotted into
  `~/.hedge-fund/paper/<name>/` with a universe, a broker book and an
  append-only, hash-chained ledger. `aihf paper tick` replays the ledger
  into state and advances exactly the next unrecorded session.

Same code path, so the backtest is honest by construction: stepping a paper
fund through the same sessions produces byte-identical records. A decision
made at session T's close is executed at T+1's close, in both modes.

## Quickstart

```bash
poetry install                          # dependencies

# .env needs (at repo root):
#   FINANCIAL_DATASETS_API_KEY=...      # market/fundamentals data
#   ANTHROPIC_API_KEY=...               # only for LLM agents (Buffett)

# THE command. No arguments: launch the interactive app (a Textual TUI).
# Two modes: paper trading (your funds — run the next session behind an
# approval step, see history, halt/resume, build a new fund) and
# backtesting (replay a fund over history).
poetry run aihf       # or, equivalently: python -m hedge_fund.tui

# Backtest a mandate over a window: `advance` looped over every benchmark
# session, full result JSON (every SessionRecord) on stdout, a copy saved to
# ~/.hedge-fund/research/. A mandate carries no tickers — --universe says
# what to point it at.
poetry run aihf backtest ~/.hedge-fund/mandates/example.yaml \
    --universe AAPL,MSFT,NVDA --start 2024-01-02 --end 2024-06-28

# Paper trade: deploy the mandate, then advance it one session per tick.
# tick is idempotent and never skips a session — a scheduler can call it
# after every close, and a week away takes a week of ticks to catch up.
poetry run aihf paper create alpha --mandate ~/.hedge-fund/mandates/example.yaml --universe AAPL,MSFT
poetry run aihf paper tick alpha
poetry run aihf paper tick alpha --again   # redo the latest session; the old record moves to ledger/superseded/
poetry run aihf paper status alpha
poetry run aihf paper list
poetry run aihf paper halt alpha --reason "..."     # the kill switch
poetry run aihf paper resume alpha

# Tests
poetry run pytest hedge_fund/
```

All API responses cache to disk (`~/.hedge-fund/cache/`), so reruns are fast,
free, and work offline once warmed.

### What lives where (`~/.hedge-fund/`)

```
mandates/<name>.yaml            a mandate: strategies, staff, risk, capital, cadence
research/<name>-<start>-<end>-<stamp>.json   one backtest result each
paper/<name>/
  fund.yaml                     the deployed fund: mandate snapshot + universe
  broker.json                   the paper broker's book (cash, shares)
  ledger/<session>.json         one SessionRecord per session, hash-chained
  control.json                  the kill switch (halted, reason, since)
  events.jsonl                  ticks, failures, halts, resumes
```

The ledger is the fund's memory. `tick` replays it into a `FundState`
(positions, cash, the pending decision) and reconciles that against
`broker.json` before anything trades; a mismatch raises `BookMismatch` rather
than being repaired. Any failure inside `advance` halts the fund, so a cron
job cannot keep trading into a broken book.

## Architecture

```
Data (point-in-time) → Alpha models → Portfolio → Risk → Execution → Ledger
```

| Module | What | Status |
|--------|------|--------|
| `data/` | `DataClient` protocol, Financial Datasets client, disk cache | ✅ |
| `signals/` | `AlphaModel` interface, PEAD, `LLMAgent` + 5 investor personas | ✅ |
| `llm/` | LLM provider protocol, Anthropic client, prompt cache | ✅ |
| `features/` | Point-in-time fundamentals snapshot (more features planned) | ◐ |
| `fund/` | `FundSpec`/`StrategySpec` — mandates as YAML data — and the `Fund` object | ✅ |
| `strategies/` | Strategy library (fundamental-ls, deep-value, inflections, earnings-drift) — add yours as a YAML | ✅ |
| `portfolio/` | View blending → target weights (conviction-weighted, optional market-neutral) | ✅ |
| `risk/` | Hard limits — per-position and gross-exposure clamps | ✅ |
| `brokers/` | `Broker` protocol + `SimBroker` (backtest) + `PaperBroker` (the same book, persisted to `broker.json`); live brokers planned | ◐ |
| `pipeline/` | `advance` — one session of the fund, the same code path in every mode — over the two stages in `stages.py` (`assess_fund` → `DecisionRecord`, `execute_decision` → `CycleRecord`); `SessionRecord`, `FundState` | ✅ |
| `paper/` | A deployed fund: `deploy`, the hash-chained `Ledger` (replay, halt/resume, events), `tick` | ✅ |
| `backtesting/` | `backtest_fund` — `advance` looped over history — plus the per-model engine | ✅ |
| `event_study/` | Market-model abnormal returns (CARs) | ✅ |
| `validation/` | Combinatorial purged CV (CPCV), backtest-overfitting prob (PBO) | ⬜ |
| `tui/` | The interactive app (Textual): backtest board, paper fund console, mandate builder | ✅ |

✅ built · ◐ partial · ⬜ planned

## Principles (non-negotiable)

- **Point-in-time by construction.** On any simulated date, only data actually
  filed by then is visible — the data layer filters on filing date, not report
  period. No lookahead, ever.
- **Fail loud.** Infrastructure failures raise; only genuine "no data" returns
  empty. A silent empty would poison a backtest as a fake "no signal."
- **The LLM never touches the trade.** Agents form *views* and *narrate*;
  deterministic code sizes and places orders; risk limits are hard gates.
- **One interface for every analyst.** Implement `AlphaModel.predict(ticker,
  date, data_client) -> Signal` and it plugs into the engine unchanged.
- **Decide at T, execute at T+1.** Nothing is ever assessed and executed
  against the same close. The rebalance rule (first session of each period)
  is computable on a live tick, so backtest and paper agree by construction.
- **The ledger is append-only.** Records are hash-chained; replay verifies
  the chain and refuses an altered record. State is derived, never edited.

## Data contracts (`models.py`)

- `Signal` — an alpha model's output: `value` in `[-1, +1]`, plus `reasoning`,
  `components`, and `metadata`.
- `QuantSignals` — all signals for a ticker on a date.

## Contributing

Two high-leverage contributions:

- **A new agent or quant model** (code): read `signals/base.py` for the
  `AlphaModel` interface, use `signals/buffett.py` (an agent is just a system
  prompt) or `signals/pead.py` (quant) as a template, register it, add a test.
- **A new strategy** (no code): drop a YAML in `strategies/` bundling existing
  models with a blend policy — the fund builder picks it up automatically.

See [`../ROADMAP.md`](../ROADMAP.md) for the open list.
