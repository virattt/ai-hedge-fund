# v2 — Quantitative Trading Stack

> **Status: Work in Progress** — This module is under active development and is not yet integrated into the main application.

v2 is a ground-up rebuild of the AI hedge fund's core engine, replacing personality-based agents with a principled quantitative pipeline.

## Architecture

```
Data (FD API) → Signals → Features → Portfolio Construction → Risk Management → Execution
```

| Module | Description |
|--------|-------------|
| `data/` | Financial Datasets API client and caching layer |
| `event_study/` | Event study framework — CARs, market model, significance testing |
| `signals/` | Quantitative signal generation (`BaseSignal` ABC with `[-1, +1]` output) |
| `features/` | Feature engineering — earnings surprise, KPI momentum, cross-sector lead-lag |
| `validation/` | Combinatorial Purged Cross-Validation (CPCV), Probability of Backtest Overfitting (PBO) |
| `backtesting/` | Vectorized backtester with point-in-time constraints and transaction cost modeling |
| `portfolio/` | Portfolio optimization — mean-variance, Black-Litterman, risk parity, covariance cleaning |
| `risk/` | Risk management — drawdown controls, position sizing, correlation monitoring, stress testing |
| `pipeline/` | Execution simulation — market impact (Almgren-Chriss), fill probability, capacity analysis |

## Key Design Decisions

- **Methodology over personality.** Agents are structured around quantitative methods (momentum, fundamental, risk), not famous investor personas.
- **Costs from day one.** Every backtest includes a transaction cost model. No frictionless fantasies.
- **Validation built in.** CPCV and PBO are first-class citizens, not afterthoughts. If a signal can't survive combinatorial purged validation, it doesn't ship.
- **Point-in-time by construction.** The data layer enforces that no future information leaks into historical analysis.
- **Daily frequency.** Built for daily-bar strategies on US equities using [Financial Datasets](https://financialdatasets.ai) as the sole data provider.

## Data Models

The core data contracts live in `models.py`:

- `SignalResult` — output of any quantitative signal (`value` in `[-1, +1]`)
- `QuantSignals` — all signals for a ticker on a given date
- `PortfolioTarget` — target portfolio weights from the optimizer
- `TradeOrder` — a single trade instruction
- `ExecutionResult` — batch of trades with estimated costs

## Contributing

v2 is in early development. If you'd like to contribute, start by reading `signals/base.py` to understand the signal interface, then check open issues tagged `v2`.
