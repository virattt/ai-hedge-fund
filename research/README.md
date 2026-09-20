# Research dossier

Six independent agent reports, run 2026-09-19/20, plus the synthesis across them.
Each report was written by an agent that did not see the others. Where they agree,
they agree *independently* — that is the only reason the agreements below are worth
anything.

| # | Report | Question it was given |
|---|---|---|
| [01](01-agent-trading-framework-landscape.md) | Agent trading framework landscape | What exists in public OSS? What should we fork, steal, or avoid? |
| [02](02-signal-evidence-review.md) | Signal evidence review | Which of these signal families actually has evidence behind it? |
| [03](03-perps-venues-and-builder-economics.md) | Perp venues & builder economics | Hyperliquid vs Aster vs GMGN — what's real, what does it cost, what does it earn? |
| [04](04-architecture-review-a.md) | Architecture review A | Adversarial review of this repo's *premise* |
| [05](05-architecture-review-b.md) | Architecture review B | Internal audit of this repo's *implementation* |
| [06](06-architecture-review-c.md) | Architecture review C | Outside view: how does this compare to standard practice? |
| [07](07-fomo-identity-graph.md) | FOMO identity graph | Can FOMO's social flow be resolved to named wallets, and is it worth it? |

Numbers in the reports were pulled live on the dates stated in each. Nothing here is
illustrative or simulated; where an agent could not verify a claim it says so.

---

## The synthesis

### 1. One failure mode shows up in four unrelated places

This is the highest-confidence finding in the dossier, because four agents found it
without coordinating, in four different subsystems:

| Where | The bug |
|---|---|
| `signals/pead.py` (review B, reproduced) | Fired on filings dated the cycle date itself — bought the drift at a price that printed before the announcement |
| `ledger.latest_run` (review B, reproduced) | Ordered receipts by file mtime, so a historical run could resume a *future* book |
| Nansen smart-money labels (reports 01 and 02, independently) | `smart-money/*` resolves against a continuously recomputed set. Backtesting today's label set against last year's trades follows wallets selected for having been right |
| The perp universe itself (report 02) | "Tokens that have a perp listing" is a survivorship-selected set — the bias re-enters through the venue rather than the data |

The first two are fixed (PR #10, PR #9). The second two are not fixable by a code
change — they are fixable only by **recording data now that cannot be reconstructed
later.** See §5.

### 2. The LLM-persona layer is the weakest part of this system, and all three architecture reviewers said so

Review A: personas are "most likely theater" on this architecture. Review B: the
`validation/` directory is a 122-byte stub while `tui/app.py` shows in-sample
backtest returns as a leaderboard on the landing screen. Review C: the genre's own
flagship (TradingAgents, 107.6k★) spent its entire 2026 release cycle patching
look-ahead bugs it shipped with.

The reviewers **disagreed on contamination severity** — A called it unbounded and
critical, B and C put it in the benign regime — and that disagreement resolves in a
useful way. The personas are *price-blind*: `features/snapshot.py` passes 14
accounting ratios and no prices, verified in code. So the contamination channel is
narrower than A assumed. But A is right that no model with a pre-test cutoff is
reachable, which means the channel cannot be *measured* either way.

An alpha source you cannot measure is not an alpha source. All three reviewers
converge on the same exit: **keep the LLM, change its job.** Microsoft's RD-Agent
pattern — LLM proposes hypotheses and writes factor code, a deterministic engine
evaluates it, the LLM never sees prices — structurally removes the contamination
channel instead of arguing about its size.

### 3. Only two signal families survive the evidence review, and neither is the one the tooling points at

Report 02's verdict, in order of how much evidence backs it:

- **Perp-structural** (funding/basis carry, cross-sectional funding, time-series
  momentum on liquid perps) — peer-reviewed, replicated, achievable at Python
  latency. The only family that clears the bar. The headline "Sharpe 6.45" for carry
  is a fiction: an 8%-mean / 0.8%-vol stream that periodically eats a −25%
  open-interest cascade.
- **Slow whale flow** — real but 6–24h horizon and large-cap only. Tradeable, barely.
- **Social** — net *negative* as a buy signal. The best study (36,000 tweets, 180
  influencers) finds positive initial returns followed by significantly negative
  longer-horizon returns. The signal reliably identifies where you are the exit
  liquidity.
- **Memecoin microstructure** — the trap. >50% of pump.fun tokens are same-block
  sniped; graduation rate 0.198%. The number to remember: a pre-registered survival
  model scored **AUROC 0.8594 in development and 0.4642 in validation** — out of
  sample, worse than a coin flip.

The uncomfortable implication: the FOMO social data and the GMGN memecoin route point
at the two weakest families. They are research datasets, not trading inputs, until
they clear a walk-forward bar set in advance.

### 4. Hyperliquid, not Aster — and the builder code is a business, not a strategy

Report 03, from live API pulls on 2026-09-20:

- Hyperliquid $4.09B core + $0.34B HIP-3 24h volume vs Aster $1.49B. OI $12.2B +
  $3.79B vs ~$1.9B.
- **Aster's US single-stock perps are dead.** NVDAUSDT did $20,000 across 35 trades
  in 24h with *zero fees* and a $613 top-of-book bid. Aster's real RWA business is
  gold ($184M/day) and crude ($66M/day) in USD1 — route those there, not equities.
- **HIP-3 is concentrated**: 6 of 10 DEXs have zero OI; `xyz` (TradeXYZ) is >90%.
  `vntl:SPACEX` and `flx:NVDA` order books are empty.
- Weekend/overnight equity oracles are **EMAs of the perp's own price** — reflexive
  by construction. Monday-open gap risk is structural, not a tail.
- HLP does **not** backstop HIP-3 markets.

On builder codes, reports 01 and 03 disagree and 03 is right. 01 frames routed flow
as a moat; 03's line is the correct one: *"the builder-code mechanism is free money
per unit of flow and offers no mechanism whatsoever for generating flow. Do not
confuse having the pipe with having the water."* Market-clearing retail rate is
**2.5–5 bps**; break-even on infrastructure is **~$478k/day routed notional** at a
96/4 perps/spot mix — or ~$287k/day against the infrastructure floor alone, before
any LLM spend. (Report 03 originally said $500k–1M/day; on re-examination that was
its *with-LLM-cost* row quoted as if it were the floor, and the spot leg then moved
it ~14%. Both corrections are the report's own.)

**Spot is a real second channel, and it carries the one decision that must be made
before anything is signed.** The builder fee cap is 1% on spot against 0.1% on perps
— ten times — but two facts cut it down: builder codes **do not apply to the buying
side of spot**, and HL spot is only **4.03% of core perp volume** ($163M vs $4.04B).
Per $1M of user round-trip that is $600 on perps at 3bp versus $3,000 on spot at
30bp: 5x on a base a twenty-fifth the size.

The decision: **the builder-fee approval is a single shared grant.** Reading the SDK
source, `HyperliquidTransaction:ApproveBuilderFee` carries exactly four fields —
`hyperliquidChain`, `maxFeeRate`, `builder`, `nonce`. **There is no venue field.**
One signature covers perps, spot and every HIP-3 market at one ceiling. Onboard at
`"0.05%"` because it reads as cheap on perps and spot is permanently capped at 5bp
too, until every user signs again from their main wallet. The protocol caps perps at
0.1% independently, so a higher ceiling cannot over-charge them there. **Approve at
0.3%.** This costs nothing to get right now and cannot be fixed unilaterally later.

And the regulatory point that decides the shape of the whole thing: the CFTC fined
Falcon Labs $1.7M for *facilitating* — routing, not operating. IP geoblocking was
held insufficient. **If you route only your own capital, this section largely
evaporates. The exposure arrives with the second user.**

### 5. Three things have a clock on them

Everything else in this dossier can be done later. These cannot:

1. **Nansen label snapshots.** The labels are restated. Every day without a snapshot
   is a day of point-in-time history that no amount of money buys back later. There
   is no vendor selling it.
2. **HIP-3 basis history.** Nobody is recording it — report 01 found *zero* OSS
   projects trading HIP-3 basis, which also means zero projects archiving it. The
   cleanest unexploited structural trade the venue access enables, and it needs
   history that only starts accumulating once something starts writing it down.
3. **Builder code registration.** $100 USDC on Hyperliquid. Cheap, but routed-flow
   data only exists from the moment the code does.

### 6. What the best version of this system looks like

**Keep** (all three reviewers named these as worth protecting):
one `run_cycle` path, the deterministic `SimBroker`, `filing_date`-based PIT in the
data layer, abstain-≠-neutral in `blend_signals`, clamps recorded as events, and the
ledger's as-of-date ordering — that last instinct is precisely the discipline the
rest of the genre lacks.

**Cut or demote:** persona debate as an alpha source; the in-sample backtest
leaderboard on the TUI landing screen; the ~1,449 LOC of parallel simulation
(legacy `BacktestEngine` + `event_study/`) that produces performance numbers by a
second path, which quietly falsifies the "one code path" claim.

**Build, in this order:**

1. **PIT feature store with versioned labels.** Immutable snapshots keyed by
   observation timestamp; every backtest reads as-of the simulated date. Joins
   funding/OI/basis, HL node microstructure, Nansen positioning *as of snapshot*, and
   own routed flow. Report 01: nothing in open source does this. Qlib does PIT for
   equities; nobody does PIT for perps and nobody at all does PIT for on-chain labels.
2. **The validation layer that is currently a 122-byte stub.** Report 02's six-point
   bar, adopted verbatim: pre-registered strategy with logged trial count and
   Deflated Sharpe > 0 at that count; positive net-of-full-cost performance in an
   unlooked-at forward window ≥ 3× holding period and ≥ 60 days; survives injected
   execution lag and volume-capped fills; survivorship-free universe with dead
   instruments marked to terminal value; ≥ 30 days paper-traded live logging intended
   vs achieved fill on every order; only then risk money whose total loss is
   irrelevant.
3. **Perp-structural strategies** — funding/basis carry, cross-sectional funding,
   TSMOM. Self-flow only, Hyperliquid first.
4. **HIP-3 basis**, once §5.2 has produced enough history to test on.
   Spot–perp carry on the same venue is the cleaner cousin and is *real* but
   *small*. Portfolio margin (live ~Dec 2025) does net the two legs into one
   collateral pool with PnL offset and stablecoin borrow at 0.05% APY below 80%
   utilization. Funding a short actually collected over the 4,320 hours to
   2026-09-20: **HYPE +9.41% annualized, ETH +6.11%, BTC +5.52%, SOL +2.49%**,
   negative 10.8–32.1% of hours. An all-taker round trip costs 0.23% — fifteen days
   of BTC carry just to clear fees. The binding constraint is the spot leg's depth
   (UBTC $655k within 10bp, HYPE $151k, $163M/day total turnover), so this tops out
   in the low single-digit millions. It is yield on inventory you already hold, not
   a strategy. Do it on HYPE, not SOL.
   **One architectural constraint:** builder-code addresses must run in `standard`
   mode, which is exactly the mode that does *not* net. The fee address cannot be
   the carry address.
5. **The LLM, re-roled** to the RD-Agent pattern.

**Fork, don't write:** Nautilus Trader (LGPL-3.0 — link it, keep strategies
proprietary) for backtest/live parity. Hyperliquid's own Python SDK for venue access.
Avoid vectorbt (Commons Clause forbids selling derived value) and Freqtrade (GPL-3.0)
unless you intend to publish the whole stack.

### 7. The two things nobody else has

Stated plainly because they are the only parts of this that are not replicable:

- **FOMO's social data and the perp venue are the same value chain.** FOMO added
  perps in June 2026 routed through Hyperliquid + Trade.xyz, and Trade.xyz is the
  dominant HIP-3 builder. That reframes FOMO from "memecoin sentiment" — a family the
  evidence review rates net-negative — to *leading indicator of order flow into the
  exact HIP-3 markets you can trade.*

  **Report 07 tested the obvious next step — attaching names to that flow — and it
  does not survive.** See §8. The flow itself does, and it is free.
- **Builder-routed flow as consented private data.** Report 01 found no public
  write-up of anyone treating it this way. It needs an explicit, written line on
  trading against your own users' flow, decided deliberately rather than discovered
  later — and per §4, it does not exist at all until there is a second user, which is
  also the moment the regulatory exposure starts.

---

### 8. The identity graph: don't build it, and you don't need it

Report 07 was commissioned to test whether FOMO's public profiles could be resolved
to named wallets — the idea being that a *named* social signal is tradeable where an
anonymous one is noise. Four findings kill it, and a fifth makes it moot.

1. **FOMO wallets are freshly-generated Privy embedded wallets** (email or Apple
   signup, no seed phrase). Every resolver in the brief — ENS, SNS, Farcaster,
   Arkham, Nansen, CEX-funding heuristics — resolves *prior* identity. These
   addresses have none. Farcaster coverage of FOMO wallets is approximately **zero**.
2. **FOMO does not publish wallet addresses at all.** The wallet is the withheld
   part, which is precisely the gap grey-market vendors sell into. So this was never
   "reading a profile that already says I am @handle" — it is inference, and that
   moves the ethical boundary materially rather than marginally.
3. **`fomo.family/robots.txt` disallows the profile paths, and ToS §16 forbids
   automated *and manual* collection.** Not designed around. Noted and stopped.
4. **The fade isn't executable.** The negative-return finding (Merkley et al., RAS
   2024: −7.9%/30d, −62.8% annualised, worst for large-following self-described
   experts) is concentrated in **non-top-100 tokens** — no borrow, no perp listing.
   The fade signal and the executable universe are disjoint sets. This was the
   adversarial question the brief posed, and the answer is no.
5. **Identity is not the discriminating variable anyway.** Yale's Polymarket study
   (1.72M accounts, $13.76B) finds 3% skilled traders with 44% persistence — but
   **69% of profits went to lucky winners**, and separating them took two years and
   99k events. FOMO ranks on 24h PnL, which is the lucky-winner metric. A
   risk-adjusted persistence classifier answers the same question from the anonymous
   layer, without anyone's name.

No study exists evaluating whether naming on-chain flow improves signal. The report
says so rather than inventing a conclusion.

**What it found instead — two live, free, no-ToS-issue sources that are not FOMO's
data:**

- **FOMO's Solana addresses are published in DeFiLlama's open-source adapter**,
  including the **gas sponsor** (`AgmLJBMDCqWynYnQiPCuj9ewsNNsBJXyzoUhD9LJzN51`),
  confirmed live on mainnet RPC. FOMO sponsors gas on every user transaction, which
  makes **every FOMO Solana trade enumerable on-chain** — the whole flow layer,
  anonymous, complete, free.
- **Hyperliquid publishes per-builder fill dumps** at
  `stats-data.hyperliquid.xyz/Mainnet/builder_fills/{addr}/{YYYYMMDD}.csv.lz4` —
  downloaded and decoded, schema carries per-user fills with `closed_pnl` and
  `builder_fee`. Free, historical, for *any* builder. This generalises well past
  FOMO: it is the routed-flow dataset §7 calls a private asset, already public for
  everyone who has one.

**Build:** the anonymous flow layer — 2–3 days, $0/month, point-in-time frozen
rosters, risk-adjusted persistence rather than 24h PnL. **Don't** build the identity
graph and **don't** buy the vendor dataset (openly offered over Telegram as "every
fomo.family username mapped to its verified Solana + EVM wallet"). The recommended
build stores no derived identity, which also disposes of the GDPR exposure: derived
wallet↔person linkage is personal data plus profiling, on a legitimate-interests
balancing you would likely lose, with an Art. 14 notice obligation that cannot be
discharged at scale.

---

## What the dossier does not answer

- Whether the equity fund in this repo should continue at all, or be wound down into
  a test bed for the validation layer. Reviews A and C imply the latter; none of them
  was asked directly.
- The consent and ethics boundary on routed flow (§7). That is a decision, not a
  research finding.
- Whether HIP-3 basis is *tradeable* after costs. It cannot be answered without the
  history that §5.2 would start accumulating.
