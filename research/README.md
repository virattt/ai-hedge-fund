# Research dossier

---

## ⭐ THE SINGLE MOST IMPORTANT FINDING IN THIS DOSSIER

> ### **FOMO sponsors gas on every user transaction.**
>
> ### **The gas-sponsor address is `AgmLJBMDCqWynYnQiPCuj9ewsNNsBJXyzoUhD9LJzN51`** — published in DeFiLlama's open-source adapter, **confirmed live on Solana mainnet RPC, 2026-09-20.**
>
> ### **Therefore: every FOMO Solana trade is enumerable on-chain.**
>
> **The entire flow layer. Free. Complete. Historical. Without touching FOMO's own
> website, API, or profiles at all** — so none of FOMO's robots.txt or ToS
> restrictions apply to it, because it is not FOMO's data. It is Solana's.
>
> Alongside it, the second one: **Hyperliquid publishes per-builder fill dumps** at
> `stats-data.hyperliquid.xyz/Mainnet/builder_fills/{addr}/{YYYYMMDD}.csv.lz4` —
> downloaded and decoded, schema carries per-user fills with `closed_pnl` and
> `builder_fee`. Free, historical, **for any builder**. The dossier elsewhere calls
> routed order flow a private data asset; it is already public for everyone who has
> one.
>
> **Neither of these needs permission, a key, a vendor, or a subscription. They need
> a query.**
>
> ---
>
> ### **FOMO's Hyperliquid builder address is `0x2a2b6b093a9813fbd8cddae800c3d17d46460d17`**
>
> (`fomo-social-trading-perps`, start 2026-06-05, from DeFiLlama's
> `factory/hyperliquid.ts`.) Three sampled days of its public fill dumps carry
> **56,373 fills across 3,789 distinct traders**, each with price, size,
> counterparty and `closed_pnl`.
>
> **⚠️ There are two "fomo" builders and the obvious one is the wrong company.**
> `0xb838e4d1c8bcf71fa8e63299d5aa3258c83d6adb` (`fomo-perps`) is **onfomo.com**, an
> unrelated business. Both return HTTP 200. Wrong one: 626 fills/day. Right one:
> 16,803. Verified by control — three invalid addresses all return 403, so a 200 is
> positive evidence — and by launch day, where 20260605 has exactly 12 fills across
> 3 users, matching the declared start.
>
> ### **And the pattern generalises past FOMO entirely.**
>
> `factory/hyperliquid.ts` is a public directory of **136 builders**. Every one of
> them is enumerable by exactly this method. **A product that abstracts away gas or
> routing has to pay for it from a public address — so the abstraction layer is the
> enumeration handle.**

Also settled, and stated here because an earlier draft of this file got it wrong:
**following pseudonymous wallets is not a GDPR problem.** Watching on-chain
addresses, clustering their behaviour, ranking them, and trading their flow is
public blockchain data and is what every on-chain analytics product does. The
narrow exposure is *deriving a natural person's real-world identity from a wallet
they did not themselves publish* — a much smaller activity, and one the recommended
build does not perform. Report 08 sets the line properly.

---

Seventeen independent agent reports plus the synthesis across them. Each was written
by an agent that did not see the others, in two waves from two parallel sessions.
Where they agree, they agree *independently* — that is the only reason the agreements
below are worth anything. **Where they disagree, §10 says so and says which one won.**

Numbering is by wave, not by importance: 01–08 are the first session's, 09–17 the
second's. Two files originally collided on 07 and 08; the second wave was renumbered,
and nothing else references them.

| # | Report | Question it was given |
|---|---|---|
| **Wave 1** | *run 2026-09-19/20 from this session* | |
| [01](01-agent-trading-framework-landscape.md) | Agent trading framework landscape | What exists in public OSS? What should we fork, steal, or avoid? |
| [02](02-signal-evidence-review.md) | Signal evidence review | Which of these signal families actually has evidence behind it? |
| [03](03-perps-venues-and-builder-economics.md) | Perp venues & builder economics | Hyperliquid vs Aster vs GMGN — what's real, what does it cost, what does it earn? (§8 of it extends to spot) |
| [04](04-architecture-review-a.md) | Architecture review A | Adversarial review of this repo's *premise* |
| [05](05-architecture-review-b.md) | Architecture review B | Internal audit of this repo's *implementation* |
| [06](06-architecture-review-c.md) | Architecture review C | Outside view: how does this compare to standard practice? |
| [07](07-fomo-identity-graph.md) | FOMO identity graph | Can FOMO's social flow be resolved to named wallets, and is it worth it? |
| [08](08-free-resolution-sources.md) | Free resolution sources | Second pass: the free resolver stack, and the per-chain enumeration handles |
| **Wave 2** | *run 2026-09-19 from a parallel session* | |
| [09](09-fomo-intel-inventory.md) | fomo-intel inventory | What in the `fomo-intel` repo is reusable for perps? |
| [10](10-fomo-intel-adversarial.md) | fomo-intel adversarial | Is its data/signal integrity good enough to build on? |
| [11](11-trading-stack-inventory.md) | trading-stack inventory | What in the `trading-stack` repo is reusable? |
| [12](12-trading-stack-adversarial.md) | trading-stack adversarial | Is it safe to trade live? |
| [13](13-fomo-identity-resolution.md) | FOMO identity resolution | Same question as 07, answered independently — **and it disagrees** |
| [14](14-hyperliquid-spot-and-builder-fees.md) | Hyperliquid spot & builder fees | Same ground as 03 §8, answered independently |
| [15](15-ml-methods.md) | ML & agentic methods | Which model families are worth it at this horizon and capital? |
| [16](16-fomo-resolvers-and-flow-layer.md) | FOMO resolvers & flow layer | Third pass on resolvers — **it overturns 08** |
| [17](17-alchemy-payg.md) | Alchemy pay-as-you-go | What does the node/RPC tier actually cost? |

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
rosters, risk-adjusted persistence rather than 24h PnL.

**On the legal line — report 07 overstated this and it is corrected here.** It
treated "identity graph" as one thing and attached a GDPR objection to all of it.
There are three activities and they are not alike:

| | Activity | Position |
|---|---|---|
| **(a)** | Following pseudonymous wallets — clustering, ranking, trading their flow | **Fine.** Public chain data. What every on-chain analytics product does. |
| **(b)** | Using links the person published themselves — own wallet posted on X, own `fomo.family/r/{handle}` referral link, signed Farcaster verification, ENS/SNS they control | **Fine.** Reading what someone published about themselves is not deanonymisation. |
| **(c)** | Inferring a real-world identity from a wallet the person did not publish | **This is the narrow one with the actual problem**, and it is the only one the GDPR argument was ever about. |

Only (c) needs the personal-data-plus-profiling analysis, and the recommended build
does not perform (c). Report 08 was originally commissioned to work that line against
the EDPB's 2025 blockchain guidance; that section was **cut before it shipped**, on
the instruction that the legal fine print is not worth tokens while the system is
trading its own capital only. The table above is the whole of the position.

What **does** still stand: don't scrape `fomo.family` itself (robots.txt and ToS §16
cover its own surfaces), and don't buy the vendor dataset openly offered over Telegram
as "every fomo.family username mapped to its verified Solana + EVM wallet" — not
because following wallets is wrong, but because that dataset was assembled by
violating the ToS the seller is advertising around. Third-party sources that
independently publish the same facts are a different matter entirely, and report 08
goes and finds them.

---

### 9. Where the data actually is — measured, 2026-09-20

Report 08 was a second pass correcting report 07. It settles the coverage question
with numbers rather than argument.

**Two coverage numbers, and conflating them is what went wrong the first time:**

| | Coverage | Cost | Status |
|---|---|---|---|
| **Pseudonymous** — every trade attributed to a stable address with realised PnL | **~100%** | $0 | Available today |
| **Named** via *generic* web3 resolvers (ENS/SNS/Farcaster) | **~0%** | $0 | Measured — and see §10, this is not the whole question |
| **Handle↔wallet** via *FOMO-specific* resolvers | **usable today** | $0 | Report 16; overturns what §8 implied |

The ~0% is now a *measurement*: ENS reverse resolution returned **0 of 60** on the
real top-trader population, with zero request failures. And the structural reason is
proven from chain rather than inferred — **73.5% of the top 200 have a Base nonce of
exactly 1.** Accepting their wallet delegation is the only thing those addresses have
ever done. Only 6–15% have any independent EVM activity at all. There is nothing to
resolve because there is no prior history to resolve *to*.

**The EVM side works differently than expected, and the finding is better than the
one it replaces.** There is no FOMO EVM paymaster, and that is correct rather than a
gap: DeFiLlama's adapter states EVM fees "occur on Relay… counted on Solana, **where
user balances are held**." FOMO does not trade from per-user EVM accounts. What
exists instead is a free membership test — **every FOMO EVM wallet carries an EIP-7702
delegation to `0xe6Cae83BdE06E4c305530e199D7217f42808555B`** (ERC-4337
`Simple7702Account`, Privy's singleton), byte-identical at the same address across
chains. One `eth_getCode` call answers "is this a FOMO wallet."

| Chain | Top-50 traders delegated | Virgin-address control |
|---|---|---|
| **Robinhood Chain** (ID 4663, verified live) | 49/50 | 0/50 |
| Base | 46/50 | 0/50 |
| Ethereum | 34/50 | 0/50 |
| Arbitrum | 3/50 | 0/50 |
| HyperEVM | 0/50 | 0/50 |

**Caveat stated plainly:** the delegate is generic Privy infrastructure, so it is
necessary but not sufficient. **Seed from the builder dump and test outward; never
enumerate inward from the delegate.**

**Ranked free stack.** Tier 1, works with no key: Hyperliquid `builder_fills`; public
Solana RPC; public EVM RPC for the 7702 test; DeFiLlama adapters via
raw.githubusercontent; HL `/info`. Tier 2, works but names nobody: Dune Spellbook —
**report 07 was wrong that it is unreachable; it was cloned** (HEAD 014adca, 198 label
models) but carries no Solana CEX or social labels; Farcaster hubs are alive but have
no reverse index. Tier 3, dead or newly gated: `api.farcaster.xyz/v2/user-by-verification`
is **now auth-required**, a regression since report 07; Solana Tracker's FOMO
leaderboard is client-rendered with zero addresses in the HTML; Solscan, SolanaFM and
SolanaBeach all failed.

**Unexplored lead, flagged unverified:** `dune.tryfomo.fomo_relay_fees` — FOMO's *own*
Dune namespace, referenced by DeFiLlama's fees adapter. First-party published data,
not a scrape. A free Dune account settles it.

**One operational warning.** Naive Solana RPC extraction still fails: token-owner
parsing returned 9–11 owners per transaction with a router among them in 5 of 5
samples. Use the indexed path (Allium/Dune) for Solana. Hyperliquid needs no such
care — its dumps are already per-user.

---

### 10. Where the two waves disagree

Wave 2 was run independently and did not see wave 1. Three places it collides, and
one place it independently confirms.

**16 overturns 08 — and the earlier relay of 08 was misleading.** Report 08 measured
ENS reverse resolution at 0 of 60 on the real top-trader population and concluded
named coverage was ~0%. That measurement stands, but it answers a narrower question
than the summary implied: *generic* web3 identity infrastructure does not resolve
freshly-minted Privy wallets, because those wallets have no prior history to resolve
to. Report 16 asked the question that was actually on the table — are there
**FOMO-specific** resolvers — and the answer is yes:

> "The earlier 'no free resolver exists' conclusion was wrong and the known-five list
> undercounted by about 2x. Four resolvers are free and usable today without login
> (fomowalletfinder.com, fomolens.app, fomoscan.sh, the open-source
> YvesxDev/fomo-wallet-resolver), and **fomoapi.io's free tier (1,000 calls/month, no
> card, every endpoint) is the best free programmatic path.**"

These give handle↔wallet, not wallet↔real-world-person, so they do not contradict
08's finding about generic infrastructure — but "there is nothing free out there" was
the wrong takeaway, and it was the takeaway. The correct one: *generic identity infra
is useless here, purpose-built FOMO resolvers are free and work.*

**13 and 08 disagree on the builder-code count, and this is unresolved.** Report 08
found one FOMO builder (`0x2a2b6b09…`) and identified `0xb838e4d1…` as a *different
company*, onfomo.com, verified against docs.onfomo.com and by a 26x fill-volume gap.
Report 13 says FOMO's perps flow through **two** builder codes. Both were live-tested.
Until someone reconciles them, treat the second address as unconfirmed rather than
picking a side — and note that getting this wrong means archiving another company's
order flow and calling it yours.

**14 independently confirms 03's name trap, which makes it much stronger.** Both
found, separately, that Hyperliquid's spot token `name` field is not a usable
identifier. Report 14 puts it concretely: the real, live HYPE/USDC pair's registry
entry is named `"WOW"`, while a separate entry actually named `"HYPE"` is a near-dead
decoy doing about **$24** of 24h volume. Wave 1's venue agent hit the same thing as
its own join bug and reported it. Two independent discoveries of the same trap is the
strongest evidence in this dossier for a single operational rule: **key spot pairs on
token ID or pair index, never on name.**

### 11. What wave 2 found in your own two repos

These are the repos handed over mid-session; reports 09–12 are the team that reviewed
them.

- **`fomo-intel`** — "a spot/memecoin wallet-intelligence research project on Solana
  and BSC — it contains **zero perps, Hyperliquid, or builder-code work**." Its
  adversarial pass: do not build a perp system on its outputs without first adding
  point-in-time history and re-validating "smart money" wallets on a schedule. The
  same restatement problem this dossier opens with, in your own codebase.
- **`trading-stack`** — no live Hyperliquid or Aster execution: no order placement, no
  signing. And the finding to read first, rated CRITICAL: **the authorized risk/safety
  gate exists but is not on the branch the pipeline runs on**, so zero risk controls
  are reachable from the live checkout. Its research layer is rated "unusually careful
  for what it is" — real lookahead self-checks, disclosed survivorship bias, signals
  actively demoted to NOT_VALIDATED — but two backtest cost assumptions (funding =
  median not mean; liquidation = no-gap) understate the tail a crowded leveraged
  momentum book would eat.

---

## What the dossier does not answer

- Whether the equity fund in this repo should continue at all, or be wound down into
  a test bed for the validation layer. Reviews A and C imply the latter; none of them
  was asked directly.
- The consent and ethics boundary on routed flow (§7). That is a decision, not a
  research finding.
- Whether HIP-3 basis is *tradeable* after costs. It cannot be answered without the
  history that §5.2 would start accumulating.
