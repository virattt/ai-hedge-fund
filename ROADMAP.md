# Roadmap

This document tracks where the project is headed and where you can help. It's
a living list — open a PR to add an item, claim one, or update status.

> **Educational use only.** This project explores AI/quant techniques for
> trading research. It is not investment advice and is not intended for real
> trading.

## How the project is structured

The project is being rebuilt (under `v2/`) around a modular, testable
architecture borrowed from how systematic funds actually operate
(Rishi Narang's *Inside the Black Box*). Five components:

```
        ┌─────────────┐
data ─▶ │ alpha models│ ─▶ portfolio ─▶ risk ─▶ execution ─▶ orders
        │ (the edge)  │    construction   model    (broker)
        └─────────────┘
              ▲
   backtesting + validation
   (prove a model before trusting it)
```

- **Alpha models** form a *view* on what to hold — a conviction score (and, for
  LLM agents, a written thesis). Both quantitative models and LLM "investor
  agents" implement the same interface, so they're combined and compared the
  same way. **This is the main place to contribute.**
- **Portfolio construction** turns views into target positions (sizing, weights).
- **Risk model** constrains exposure.
- **Execution** places orders through a (pluggable) broker.
- **Backtesting + validation** measure whether a model actually has an edge
  before it's trusted with capital.

## Status legend

✅ Shipped · 🚧 In progress · ⬜ Planned

## Infrastructure

| Item | Status |
|------|--------|
| Data layer — pluggable `DataClient` protocol + provider client | ✅ |
| Event study engine — market-model abnormal returns (CARs) | ✅ |
| Backtesting engine — simulate an alpha model over history, report return / Sharpe / drawdown | ✅ |
| Validation — combinatorial purged cross-validation (CPCV), probability of backtest overfitting (PBO) | ⬜ |
| Feature pipeline — reusable inputs for alpha models (e.g. market-regime detection) | ⬜ |

## Alpha models

The biggest contribution surface. Implement the `AlphaModel` interface, return a
`Signal`, and it plugs straight into the backtester. Two flavors:

**Quantitative models** (pure math/data):

| Model | Status |
|-------|--------|
| Post-Earnings Announcement Drift (PEAD) | ✅ |
| Market-regime detection (HMM / regime-switching) | ⬜ |
| Momentum | ⬜ |
| Mean reversion | ⬜ |
| Value / quality factors | ⬜ |
| Statistical arbitrage | ⬜ |
| *Your model here* | ⬜ |

**LLM investor agents** (reason over fundamentals, emit a conviction + thesis).
Porting these classic personas to the alpha-model interface — so each can be
backtested and combined — is a great first contribution:

| Agent | Status |
|-------|--------|
| Warren Buffett | 🚧 |
| Charlie Munger | ⬜ |
| Benjamin Graham | ⬜ |
| Peter Lynch | ⬜ |
| Stanley Druckenmiller | ⬜ |
| Cathie Wood | ⬜ |
| Michael Burry | ⬜ |
| Bill Ackman | ⬜ |
| Aswath Damodaran | ⬜ |
| Phil Fisher | ⬜ |
| Mohnish Pabrai | ⬜ |
| Nassim Taleb | ⬜ |
| Rakesh Jhunjhunwala | ⬜ |
| *Your agent here* | ⬜ |

## Portfolio, risk & execution

| Item | Status |
|------|--------|
| Portfolio construction — combine signals into target weights | ⬜ |
| Risk model — exposure limits, position sizing | ⬜ |
| Execution — pluggable broker layer for live/paper trading (e.g. Interactive Brokers) | ⬜ |

## Contributing

The easiest way to make an impact:

1. **Add an alpha model.** Pick an unchecked row above (or invent one),
   implement the `AlphaModel` interface so `predict(...)` returns a `Signal`,
   and add a test. The backtester will run it without any other changes.
2. **Add an alternative data source.** We already have core market, fundamentals, and earnings data. Alpha models get
   more powerful with alternative datasets — satellite imagery, web & social
   (X) search, payment trends trends, macro data, shipping data, and the like. Add a connector
   that brings a new, unique signal into the mix.
3. **Build out a planned component** (validation, portfolio construction, risk,
   execution).

Before starting something large, open an issue to claim it so work isn't
duplicated. PRs that update this roadmap's status are encouraged.
