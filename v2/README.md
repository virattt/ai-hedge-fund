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

A fund runs two kinds of pods, like a real shop. **Discretionary** strategies
are staffed by **agents** — LLM investor personas (Warren Buffett, Charlie
Munger, Benjamin Graham, Peter Lynch, Stanley Druckenmiller) whose judgment
is the edge; blend them long-biased or market-neutral. **Systematic**
strategies are powered by quant models (post-earnings drift) — the model *is*
the strategy, no persona attached. Both kinds implement one interface and
plug into the same engine unchanged.

Run a fund two ways: **one cycle** (today's data → today's target book) or a
**backtest** — the same cycle looped over history at the mandate's rebalance
cadence, producing an equity curve against your benchmark and a full
`CycleRecord` for every tick. Same code path, so a backtest is honest by
construction: it's the fund, replayed, not a separate simulator.

## Quickstart

```bash
poetry install                          # dependencies

# .env needs (at repo root):
#   FINANCIAL_DATASETS_API_KEY=...      # market/fundamentals data
#   ANTHROPIC_API_KEY=...               # only for LLM agents (Buffett)

# THE command. No arguments: build a fund interactively — pick stocks,
# strategies, rebalance cadence — and watch it run its first cycle; or
# backtest a saved fund through the last 18 months, equity curve vs its
# benchmark.
poetry run python -m v2.run

# With a mandate: run one cycle non-interactively (data → strategies →
# netting → risk → execution), full CycleRecord as JSON on stdout.
poetry run python -m v2.run v2/funds/example.yaml

# Backtest a mandate: the same run_cycle looped over history at the
# mandate's rebalance cadence, full result JSON (every CycleRecord) on stdout.
poetry run python -m v2.run v2/funds/example.yaml --backtest

# Tests
poetry run pytest v2/
```

All API responses cache to disk (`.v2_cache/`, gitignored), so reruns are fast,
free, and work offline once warmed.

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
| `brokers/` | `Broker` protocol + `SimBroker` (paper/live brokers planned) | ◐ |
| `pipeline/` | `run_cycle` — one code path for backtest/paper/live; `CycleRecord` | ✅ |
| `backtesting/` | `backtest_fund` — the whole fund over history on `run_cycle` — plus the per-model engine | ✅ |
| `event_study/` | Market-model abnormal returns (CARs) | ✅ |
| `validation/` | Combinatorial purged CV (CPCV), backtest-overfitting prob (PBO) | ⬜ |

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
