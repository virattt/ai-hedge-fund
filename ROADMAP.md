# Roadmap

Where the project is headed and where you can help. This is a living list — open a
PR to add an item, claim one, or update status. For the bigger picture behind it,
read [VISION.md](./VISION.md).

> **Educational use only.** Not investment advice; not intended for real trading.

## Status legend

✅ Shipped · 🚧 In progress · ⬜ Planned

**Current focus:** point-in-time data correctness → first LLM analyst (Buffett) →
the `run_cycle` engine. The tables below are a capability map, not a strict order;
where items depend on each other, the dependency is noted.

## The engine

The core: a **fund** as a persistent object, and one pipeline (`run_cycle`) that runs
it in backtest, paper, or live mode (see [VISION.md](./VISION.md)).

| Item | Status |
|------|--------|
| `AlphaModel` / `Signal` interface — the contract every analyst implements | ✅ |
| Backtesting engine — run an alpha model over history; report return / Sharpe / drawdown | ✅ (to be rebuilt onto `run_cycle`) |
| Event-study engine — market-model abnormal returns (CARs) | ✅ |
| `run_cycle` — one pipeline (data → analysts → portfolio → risk → execution → ledger), three modes | ⬜ |
| Fund object — persistent mandate, staff, capital, books | ⬜ |
| Persistent ledger — positions, every decision + thesis, orders, fills, NAV history | ⬜ |
| Point-in-time data correctness — as-of / filing-date queries, no lookahead | 🚧 |
| Validation gate — CPCV, probability of backtest overfitting (PBO) | ⬜ |

## Analysts (alpha models) — the main contribution surface

Implement the `AlphaModel` interface, return a `Signal`, and it plugs straight into
the engine. Two flavors:

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

**LLM investor agents** (reason over fundamentals in a famous investor's voice, emit
a conviction + thesis). Porting these personas to the alpha-model interface — so each
can be backtested and combined — is a great first contribution:

| Agent | Status |
|-------|--------|
| Warren Buffett | ✅ |
| Charlie Munger · Benjamin Graham · Peter Lynch · Stanley Druckenmiller | ⬜ |
| Cathie Wood · Michael Burry · Bill Ackman · Aswath Damodaran | ⬜ |
| Phil Fisher · Mohnish Pabrai · Nassim Taleb · Rakesh Jhunjhunwala | ⬜ |
| *Your agent here* | ⬜ |

## Strategies & allocation

| Item | Status |
|------|--------|
| Strategy — bundle analysts + a portfolio policy + capital slice (a "pod") | ⬜ |
| Portfolio construction — blend analyst views → target weights | ⬜ |
| Multi-strategy fund — many pods running at once, netted into one book | ⬜ |
| Allocator (CIO) — pluggable capital allocation across strategies | ⬜ |
| ↳ Static (human-set dial) | ⬜ |
| ↳ Risk-parity / inverse-vol | ⬜ |
| ↳ Dynamic — feed winners, cut drawdowns (Millennium-style) | ⬜ |
| ↳ LLM CIO — reasons over regime + each pod's track record | ⬜ |

## Risk & execution

| Item | Status |
|------|--------|
| Risk model — hard caps (pod-level budgets + fund-level limits) | ⬜ |
| Broker protocol — pluggable, mirrors the `DataClient` pattern | ⬜ |
| ↳ Simulated broker (backtest) | ⬜ |
| ↳ Paper broker | ⬜ |
| ↳ Live broker (Interactive Brokers / Alpaca) — opt-in plugin, off by default | ⬜ |

## Autonomy

| Item | Status |
|------|--------|
| Scheduler / daemon — market-calendar cron, idempotent ticks, kill-switch | ⬜ |
| Observability — per-cycle events, notifications, heartbeat | ⬜ |
| Research lab — backtest candidate strategies/allocators alongside the live fund | ⬜ |
| Strategy generator — composes candidate strategies from the building blocks (analysts × policies × parameters), driven by the fund's mandate | ⬜ |
| Auto-promotion — winners graduate into the live fund through the validation gate (CPCV/PBO), human-approved by default (depends: research lab, validation gate) | ⬜ |

## Interfaces

Thin clients over the engine — pick the surface, the core stays the same.

| Item | Status |
|------|--------|
| CLI | ✅ (to become a thin client over the engine) |
| Web dashboard — replayable, time-scrubbable reasoning ledger | 🚧 (frontend scaffold exists) |
| TUI "cockpit" — streaming agent reasoning + watch mode | ⬜ |
| Conversational control plane — operate the fund in natural language | ⬜ |

## Data

| Item | Status |
|------|--------|
| Data layer — pluggable `DataClient` protocol + provider client | ✅ |
| Alternative data connectors — satellite imagery, web & social-media search, app-download trends, shipping data, etc. | ⬜ |

## Contributing

The easiest ways to make an impact:

1. **Add an analyst (alpha model).** Pick an unchecked row above (or invent one),
   implement the `AlphaModel` interface so `predict(...)` returns a `Signal`, and add
   a test. The engine runs it without any other changes.
2. **Add a strategy or an allocator.** Bundle analysts into a strategy, or contribute
   a new capital-allocation policy (CIO). Every analyst, strategy, and allocator also
   becomes a building block the strategy generator can compose — contributions
   compound.
3. **Add an alternative data source.** [Financial Datasets](https://financialdatasets.ai)
   provides the core market, fundamentals, and earnings data. Analysts get more
   powerful with *complementary* datasets — satellite imagery, web & social-media
   search, app-download trends, shipping data, and the like. Add a connector that brings a new,
   unique signal into the mix.
4. **Build out a planned component** (portfolio construction, risk, brokers, scheduler,
   validation, an interface).

Before starting something large, open an issue to claim it so work isn't duplicated.
PRs that update this roadmap's status are encouraged.
