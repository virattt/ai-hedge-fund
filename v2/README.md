# v2 — AI Hedge Fund core

> **Status: Work in progress.** A ground-up rebuild of the engine, developed
> alongside the shipped v1 app (`src/`, `app/`) but not yet wired into it.
> See [`../VISION.md`](../VISION.md) and [`../ROADMAP.md`](../ROADMAP.md) for
> where this is headed.

v2 rebuilds the fund as a persistent, point-in-time-honest system. Its central
abstraction is the **alpha model**: anything that forms a view on a ticker and
returns a `Signal` (a conviction in `[-1, +1]` plus a written thesis). Two
flavors share one interface —

- **LLM investor agents** (e.g. Warren Buffett) that reason over fundamentals
  in a persona's voice, and
- **quant models** (e.g. post-earnings drift) that are pure math.

Both plug into the same backtester and, eventually, the same live engine.

## Quickstart

```bash
poetry install                          # dependencies

# .env needs (at repo root):
#   FINANCIAL_DATASETS_API_KEY=...      # market/fundamentals data
#   ANTHROPIC_API_KEY=...               # only for LLM agents (Buffett)

# Backtest demo — PEAD across 25 stocks, live terminal dashboard (~20s)
poetry run python -m v2.demo.backtest
poetry run python -m v2.demo.backtest --refresh   # rebuild the data cache

# Ask an analyst for a point-in-time view on a ticker
poetry run python -m v2.analyze NVDA
poetry run python -m v2.analyze NVDA --date 2024-06-01   # as-of a past date
poetry run python -m v2.analyze AAPL --agent pead

# Run one cycle of a fund from a YAML mandate (data → analysts → portfolio
# → risk → execution), printing the full CycleRecord as JSON
poetry run python -m v2.cycle v2/funds/example.yaml --date 2025-06-03

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
| `signals/` | `AlphaModel`/`QuantModel` interface, PEAD, `LLMAgent`, Buffett | ✅ |
| `llm/` | LLM provider protocol, Anthropic client, prompt cache | ✅ |
| `features/` | Point-in-time fundamentals snapshot (more features planned) | ◐ |
| `fund/` | `FundSpec` — a fund's mandate as YAML data — and the `Fund` object | ✅ |
| `portfolio/` | View blending → target weights (conviction-weighted) | ✅ |
| `risk/` | Hard limits — per-position and gross-exposure clamps | ✅ |
| `brokers/` | `Broker` protocol + `SimBroker` (paper/live brokers planned) | ◐ |
| `pipeline/` | `run_cycle` — one code path for backtest/paper/live; `CycleRecord` | ✅ |
| `backtesting/` | Backtest engine over an alpha model's views (to be rebuilt onto `run_cycle`) | ✅ |
| `event_study/` | Market-model abnormal returns (CARs) | ✅ |
| `demo/` | Presentation showcases over the real engine | ✅ |
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

The highest-leverage contribution is a new analyst. Read `signals/base.py` for
the `AlphaModel` interface, look at `signals/pead.py` (quant) or
`signals/buffett.py` (LLM persona) as templates, add a test, and it runs in the
backtester with no other changes. See [`../ROADMAP.md`](../ROADMAP.md) for the
open list.
