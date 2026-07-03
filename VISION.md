# Vision

> **Educational use only.** This project explores AI/quant techniques for trading
> research. It is not investment advice and is not intended for real trading.

## The idea in one sentence

An **AI hedge fund you can run as a persistent system** — an entity whose analysts
are AI, that finds and tests its own strategies, trades on a schedule, and explains
every decision it makes. Backtest today; paper-trade; and, opt-in, trade live.

Most "AI trading" projects are one-shot scripts: run it, get a signal, exit. We're
building the opposite — a **fund as a first-class, living thing**. You give it a
mandate, staff it with analysts, and it runs continuously, keeping a complete book of
everything it has done. (Much of this is aspirational — see [ROADMAP.md](./ROADMAP.md)
for what's built today versus planned.)

## Think of it like a real hedge fund

The org chart is unchanged from a real fund. We just swapped the humans for AI.

```
 FUND  "Alpha One"                    capital · mandate · always-on
 │
 ├─ CIO  →  capital allocator         decides how much each strategy gets
 │
 ├── STRATEGY: Value                  a "pod" — its own team + capital slice
 │     analysts → portfolio manager → value sleeve
 │
 ├── STRATEGY: Event                  another pod
 │     analysts → portfolio manager → event sleeve
 │
 └── STRATEGY: Macro ...
            │
   all sleeves net together ▼
   MASTER RISK  →  EXECUTION (broker)  →  THE BOOKS (persistent ledger)
```

| Real fund | Here |
|-----------|------|
| Research analysts | **Alpha models** — LLM investor agents *and* quant models |
| A strategy / pod | **Strategy** — a bundle of analysts + a portfolio policy + capital |
| Portfolio manager | **Portfolio construction** — turns views into target positions |
| CIO / capital allocation | **Allocator** — distributes capital across strategies |
| Chief risk officer | **Risk model** — hard limits the analysts cannot override |
| Trading desk | **Execution** — places orders through a broker |
| Back office / books | **Ledger** — positions, P&L, and every decision, forever |

## Everything is pluggable

The whole system is built from swappable parts. Three nested layers, and you can
mix and match at every one:

```
   FUND      =  an allocator (CIO)  over  STRATEGIES
   STRATEGY  =  a portfolio policy  over  ANALYSTS
   ANALYST   =  an alpha model  →  a Signal (conviction + written thesis)
```

- **Analysts** come in two flavors that share one interface: **LLM investor agents**
  (Warren Buffett, Charlie Munger, Peter Lynch, Stanley Druckenmiller, …) that reason
  in a famous investor's voice, and **quant models** (post-earnings drift, regime
  detection, momentum, …) that are pure math. Both output the same thing: a
  conviction in `[-1, +1]` plus a thesis. (The investor agents are *stylized
  approximations* of these investors' public philosophies — not the actual
  individuals, and not endorsements.)
- **Strategies** bundle analysts together with a policy for blending their views.
- **The allocator (CIO)** is *also* pluggable — start with a human-set dial, then
  drop in a dynamic allocator (risk-parity, a Millennium-style "feed the winners /
  cut the drawdowns" model, or even an LLM CIO that reasons about market regime and
  each pod's track record).

Every layer is a place the community can contribute a new model.

## One engine, three modes

There is a single pipeline (`run_cycle`) — `data → analysts → portfolio → risk →
execution → ledger`. It runs in three modes, and **the only thing that changes is the
clock and the broker:**

```
  BACKTEST   =  historical clock  +  simulated broker   (the past, fake money)
  PAPER      =  live clock        +  paper broker        (right now, fake money)
  LIVE       =  live clock        +  real broker         (right now, real money)
```

Because it's **one code path by design**, what you backtest is what trades — no
separate "research" implementation that quietly diverges from production. (Today the
backtester is a separate harness; converging it onto `run_cycle` is a core roadmap
item.)

### One cycle

A "cycle" is one tick — one trading day in a backtest, or one scheduled run when live:

```
  point-in-time data        only what was actually filed by this date — no peeking
        │                   at the future
        ▼
  analysts emit Signals     Buffett +0.7 "durable moat, fair price"
        │                   PEAD    -1.0 "missed earnings"
        ▼
  portfolio construction    blend views → target weights
        ▼
  risk model                hard caps clamp or veto (conviction requests, risk disposes)
        ▼
  execution                 target vs. broker reality → the orders to place
        ▼
  ledger                    persist the decision, the thesis, the fills, the new NAV
```

## A fund and a research lab, side by side

A real shop trades its book *and* researches new ideas at the same time. So does this:

```
 PRODUCTION  (always-on)              RESEARCH LAB  (anytime)
 ┌──────────────────────────┐        ┌────────────────────────────┐
 │ FUND trading every tick  │        │ backtest a candidate:      │
 │   Value  40% ███         │        │  "add Munger, drop PEAD,   │
 │   Event  25% ██          │        │   tilt the allocator 70/30"│
 │   Macro  20% ██          │        │ run it over years of history│
 │   Growth 15% █           │        └─────────────┬──────────────┘
 └────────────┬─────────────┘    promote if it wins │
              └──────────◄─────────────────────────-┘
                  the live fund hot-swaps to the better mandate
```

You don't "graduate" from backtest to live. The fund runs continuously while the lab
explores new analysts, new strategies, and new allocation policies — and the winners
get promoted into the running fund. The lab operates at two levels:

- **Level 1 — you run the lab.** You propose the candidates ("add Munger, drop PEAD,
  tilt the allocator 70/30"), backtest them over history, and promote the winners
  yourself. This is the loop the system is built around today.
- **Level 2 — the fund runs its own lab** *(aspirational)*. Give it a mandate → it
  finds strategies → backtests them → promotes the winners. A research agent composes
  candidate strategies from the building blocks the community contributes — analysts
  × portfolio policies × parameters — tests them in the same lab, and graduates
  winners through the validation gate. Same loop, same lab; the researcher is now
  also AI. This is where the project is headed, not what ships today.

## What we will not compromise on

These principles are the difference between a toy and a system you can actually
reason about:

- **Point-in-time honesty.** On any simulated date, the fund may only use data that
  was actually public by then. No lookahead, ever. This is what makes a backtest mean
  something.
- **The backtest is the live system.** Same pipeline, same code. If it can't be
  expressed honestly in a backtest, it doesn't ship.
- **The LLM never touches the trade.** Language models form *views* and *narrate*
  decisions. Deterministic code sizes positions and places orders, and risk limits are
  hard gates an agent cannot exceed.
- **Self-improvement is gated.** The fund may invent and test its own strategies, but
  nothing it invents gets capital without passing the validation gate (overfitting
  checks like CPCV/PBO) — and promotion into a live book stays human-approved by
  default.
- **Paper before real, always.** Live trading is opt-in and off by default.
- **Open and forkable.** Every layer is a documented interface. The fund explains
  itself — each decision keeps the analyst's written thesis — and you can fork the
  explanation.

## The goal

Build, in the open, an AI hedge fund that genuinely tries to **outperform the market** —
and that is honest enough about its own performance to tell you when it doesn't.

See [ROADMAP.md](./ROADMAP.md) for what's built, what's next, and where you can help.
