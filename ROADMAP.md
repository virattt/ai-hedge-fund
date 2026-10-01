# Roadmap

Where the project is headed and where you can help. This is a living list — open a
PR to add an item, claim one, or update status. For the bigger picture behind it,
read [VISION.md](./VISION.md).

> **Educational use only.** Not investment advice; not intended for real trading.

## Status legend

✅ Shipped · 🚧 In progress · ⬜ Planned

**Current focus:** running paper funds for real. The fund now has two modes,
backtest and paper, on one verb (`advance`), and a paper fund carries its book
between sessions in a hash-chained ledger with a kill switch. `aihf paper tick` is
idempotent and cron-safe, so the next step is the scheduler itself (market-calendar
timing, notifications, a heartbeat) and observability over the event log. In
parallel: retiring the v1 CLI, which needs Ollama (the free, local, no-key path) and
the remaining investor personas ported.

The tables below are a capability map, not a strict order; where items depend on
each other, the dependency is noted.

## The engine

The core: a **fund** as a persistent object, and one verb (`advance`) that moves it
through one session in backtest or paper mode, live later (see [VISION.md](./VISION.md)).

| Item | Status |
|------|--------|
| `AlphaModel` / `Signal` interface — the contract every analyst implements | ✅ |
| Backtesting engine — `backtest_fund`: `advance` looped over history, equity curve vs the mandate's benchmark (plus the per-model harness) | ✅ |
| Event-study engine — market-model abnormal returns (CARs) | ✅ |
| `advance` — one session (reconcile → execute the pending decision → mark → assess), the same code path in every mode; decide at T, execute at T+1 | ✅ (backtest and paper ship; live is the broker away) |
| Fund object — persistent mandate, staff, capital, books | ✅ (mandates carry no tickers; a *deployed* paper fund fixes the universe and carries its book in `~/.hedge-fund/paper/<name>/`) |
| Persistent ledger — positions, every decision + thesis, orders, fills, NAV history | ✅ (append-only `SessionRecord`s, hash-chained; replay verifies the chain and rebuilds state; the broker book is reconciled against it before every tick) |
| Kill switch — halt/resume a paper fund; any failure inside a tick halts it | ✅ |
| LLM provider layer — one client factory (`make_llm`) routed by the model registry: Anthropic · OpenAI · DeepSeek · Google · xAI · Kimi | ✅ (Ollama next — the free local path, and the last blocker v1 holds over v2) |
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
| Charlie Munger · Benjamin Graham · Peter Lynch · Stanley Druckenmiller | ✅ |
| Cathie Wood · Michael Burry · Bill Ackman · Aswath Damodaran | ⬜ |
| Phil Fisher · Mohnish Pabrai · Nassim Taleb · Rakesh Jhunjhunwala | ⬜ |
| *Your agent here* | ⬜ |

## Strategies & allocation

| Item | Status |
|------|--------|
| Strategy — bundle models + a blend policy + capital slice (a "pod") | ✅ (`StrategySpec` + library: fundamental-ls, deep-value, inflections, earnings-drift) |
| Portfolio construction — blend model views → target weights | ✅ (conviction-weighted; optional market-neutral sleeves) |
| Multi-strategy fund — many pods running at once, netted into one book | ✅ (`assess_fund` nets every sleeve into one target book, then master risk clamps it) |
| Allocator (CIO) — pluggable capital allocation across strategies | 🚧 (static slices ship; the pluggable interface is next) |
| ↳ Static (human-set dial) | ✅ (capital slices in the mandate) |
| ↳ Risk-parity / inverse-vol | ⬜ |
| ↳ Dynamic — feed winners, cut drawdowns (Millennium-style) | ⬜ |
| ↳ LLM CIO — reasons over regime + each pod's track record | ⬜ |

## Risk & execution

| Item | Status |
|------|--------|
| Risk model — hard caps (pod-level budgets + fund-level limits) | 🚧 (fund-level position + gross caps ship; pod budgets with pods) |
| Broker protocol — pluggable, mirrors the `DataClient` pattern | ✅ |
| ↳ Simulated broker (backtest) | ✅ |
| ↳ Paper broker — the simulated book, persisted to `broker.json` | ✅ |
| ↳ Live broker (Interactive Brokers / Alpaca) — opt-in plugin, off by default | ⬜ |

## Autonomy

| Item | Status |
|------|--------|
| Scheduler / daemon — market-calendar cron, idempotent ticks, kill-switch | 🚧 (`aihf paper tick` is idempotent, never skips a session, and honours the kill switch — point any cron at it; the built-in calendar-aware daemon is next) |
| Observability — per-cycle events, notifications, heartbeat | 🚧 (`events.jsonl` records every tick, failure, halt and resume; notifications and a heartbeat are next) |
| Research lab — backtest candidate strategies/allocators alongside the live fund | ⬜ |
| Strategy generator — composes candidate strategies from the building blocks (analysts × policies × parameters), driven by the fund's mandate | ⬜ |
| Auto-promotion — winners graduate into the live fund through the validation gate (CPCV/PBO), human-approved by default (depends: research lab, validation gate) | ⬜ |

## Interfaces

Thin clients over the engine — pick the surface, the core stays the same.

| Item | Status |
|------|--------|
| TUI — the main interface (Textual): backtest a mandate, paper trade one (deploy, advance a session with the analysts' live board, halt/resume, browse every session's report), build a mandate, model picker, in-app API-key setup | 🚧 (ships and is the default `aihf`; watch mode remains) |
| CLI — thin machine client over the engine: `aihf backtest mandate.yaml --universe …` and `aihf paper create\|tick\|status\|list\|halt\|resume`, JSON on stdout | ✅ |
| Web dashboard — replayable, time-scrubbable reasoning ledger | 🚧 (frontend scaffold exists; still runs on the v1 engine) |
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
