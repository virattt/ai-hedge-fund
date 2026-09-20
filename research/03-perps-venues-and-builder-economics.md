# Perps Infrastructure & Economics Review
**All live numbers pulled 2026-09-20 ~02:00 UTC (a Saturday night US — equity-perp volumes are weekend-depressed; open interest is not).** Anything I could not verify is flagged `[UNVERIFIED]`.

---

## VERDICT

**Build on Hyperliquid as the primary venue; treat Aster as a secondary route for gold/oil/USD1 RWA flow and as a hedge against single-venue risk.** Hyperliquid is roughly 3x Aster's live volume ($4.09B core + $0.34B HIP-3 vs Aster's $1.49B, weekend snapshot 2026-09-20) and ~6x its open interest ($12.2B core + $3.8B HIP-3 vs ~$1.9B). More importantly, the thesis the user is betting on — "one venue where equities, commodities, crypto and memecoins all trade" — is *only actually true on Hyperliquid*, and specifically inside the HIP-3 `xyz` DEX: 122 non-crypto markets with $3.79B of real open interest, versus Aster, whose US single-stock perps are functionally dead (NVDAUSDT did **$20,000** of volume across **35 trades** in 24h despite zero fees). Builder economics are near-identical on paper (both cap builder fees at 0.1% of notional on perps), but Hyperliquid's builder program is a proven revenue channel with public receipts — $63.5M+ cumulative to the top 10 builders as of 2026-05-25 — while Aster Code is newer and unproven. Aster's 0.04%/0.005%/0.009% taker fees are so low that a 0.05% builder fee would be 5–10x the exchange's own fee, which is a bad look and a hard sell; Hyperliquid's 0.045% base taker absorbs a 0.025–0.05% builder markup much more naturally. The decisive counterweight: Aster was delisted from DeFiLlama in October 2025 over wash-trading suspicions (near-1:1 volume correlation with Binance pairs) and has been relisted without the questions being resolved — you do not want your revenue model resting on volume you cannot independently verify. Build Hyperliquid-first, wrap Aster behind the same order-routing interface, and keep GMGN as a memecoin sidecar rather than a core venue.

---

## VENUE COMPARISON

| Dimension | **Hyperliquid** | **Aster** | **GMGN.ai** |
|---|---|---|---|
| Live 24h volume (2026-09-20, weekend) | $4.09B core + $0.34B HIP-3 | $1.49B (597 active symbols) | n/a (memecoin spot router) |
| Live open interest | $12.23B core + $3.79B `xyz` + ~$81M other HIP-3 | ~$1.9B (BTC $480M, ETH $257M, XAU $67M) | n/a |
| Max builder fee (perps) | **0.1% of notional** (10 bps), set per-order | **0.1%** (`maxFeeRate` cap 0.001) | Not a builder model — 10–30% rev-share of GMGN's 1% |
| Builder entry cost | 100 USDC in perps account | 100 $ASTER, maintained | Volume-gated approval, free |
| Base taker fee | 0.045% (tier 0), down to 0.024% at $7B/14d | 0.04% USDT-M / 0.005% USD1 / 0.009% RWA | 1% per side, flat |
| Base maker fee | 0.015% (tier 0), 0% at >$500M/14d | **0%** on all perps (since 2026-02-02) | n/a |
| Auth model | EIP-712, no API keys; agent wallets; `ApproveBuilderFee` from main wallet | EIP-712 for Aster Code; HMAC-SHA256 (`X-MBX-APIKEY`) for the Binance-clone REST | `x-route-key` header |
| API shape | Custom JSON `/info` + `/exchange`, WS; Python + TS SDKs | **Binance futures API clone** (`fapi.asterdex.com`) — enormous tooling reuse | 3 REST endpoints (quote/submit/status) |
| Rate limits | 1,200 wt/min per IP; **1 req per 1 USDC lifetime volume** per address (10k initial buffer); 1,000 WS subs, 10 conns | 2,400 wt/min, 1,200 orders/min per IP | **1 call per 5 seconds per key** |
| Equity/RWA perps | 122 markets on `xyz` (TradeXYZ), incl. licensed SP500; real OI | 11 USD1 RWA + ~dozen USDT stock perps; only XAU/CL/SKHYNIX/SPCX/SNDK/MU have real flow | None |
| Memecoins | Spot HIP-1 + some perps | Long tail of USDT perps | **Core competence** — Sol/ETH/Base/BSC |
| Self-listing | **Yes — HIP-3, 500k HYPE stake** | No | No |
| Privacy/hidden orders | No | **Yes** — hidden orders + hidden positions; Aster Chain privacy L1 | No |
| Multi-chain deposit | USDC on Arbitrum + native bridges; HyperEVM | BNB Chain, Ethereum, Arbitrum, Solana from one account | Sol/ETH/Base/BSC |
| Integrity risk | JELLY oracle attack (2025-03-26, $13.5M HLP hit); 37-min API outage 2025-07 | **DeFiLlama delisting over wash-trading, Oct 2025** — unresolved | Fee opacity; 1% is very high |

---

## 1. HYPERLIQUID

### Builder codes — how they actually work
- A builder attaches `{"b": "0x...", "f": <tenths of a bp>}` to each order action. `f: 10` = 1 bp. Per-order, so you can vary the rate by market or user tier.
- **Cap: 0.1% (100 tenths-of-bp) on perps, 1% on spot.** Applies to **both sides** of a perp trade; on spot only the sell side (fees are only collected in the quote/collateral asset).
- User signs `ApproveBuilderFee` **with their main wallet, not an agent wallet** — this is a real UX speed bump you must design around (it's a separate signature from agent-wallet approval, and you get one shot at it in onboarding).
- Max **10 active builder approvals per user**, revocable any time. Query with `{"type":"maxBuilderFee","user":"0x…","builder":"0x…"}`.
- Builder must hold **≥100 USDC perps account value** and use `standard` account-abstraction mode.
- Fees accrue to the builder's referral balance and are claimed through the normal referral-reward claim flow. Per-fill CSVs at `https://stats-data.hyperliquid.xyz/Mainnet/builder_fills/{lowercase_builder_addr}/{YYYYMMDD}.csv.lz4`.
- Stacks with the referral program independently: referrer earns 10% of referred users' fees (first $1B of their volume); referee gets a 4% discount (first $25M).

**What a builder earns per unit of flow:** flat. `builder_fee_bps × notional × 2 sides`. At 5 bps that's **$500 per $1M of one-way notional**, $1,000 per $1M round-tripped. No volume tiers, no decay, no cap other than the 10 bps ceiling.

**Observed market rates** (CoinGecko/HyperTracker snapshot 2026-05-25, cumulative since inception):

| Builder | Revenue | Rate | Volume | Users |
|---|---|---|---|---|
| Phantom | $20.6M | 0.05% | $39.4B | 137,496 |
| Based | $15.1M | 0.025% | $44.0B | 42,579 |
| PVP | $7.9M | 0.038% | $16.9B | 28,189 |
| MetaMask | $6.5M | **0.1%** | $7.46B | 43,761 |
| Insilico | $3.3M | 0.01% | $32.2B | 2,962 |

Read that table carefully: **2.5–5 bps is the market-clearing retail rate.** MetaMask charges the full 10 bps and gets 1/5th the volume of Based at 2.5 bps. Insilico at 1 bp is clearly algo/professional flow. Your rate choice segments your user base more than it scales your revenue.

### API surface
- `POST /info` (read) and `POST /exchange` (write), plus WebSocket. No API keys — **EIP-712 signatures** from your wallet or an approved agent wallet. Agent wallets are the right pattern for a terminal: one signer per user, private key held server-side.
- Official [Python SDK](https://github.com/hyperliquid-dex/hyperliquid-python-sdk) with `examples/basic_builder_fee.py`, `approve.py`, and `hip3_order.py` (HIP-3 order on `xyz:SILVER`).
- **Order types:** market, limit, post-only/ALO, reduce-only, IOC/GTC/FOK, stop-market, stop-limit, trigger, TWAP (min 30s sub-order interval, 3% max slippage per sub-order), scale/ladder.
- **Stops trigger on the oracle mark price** (median of external venue prices), not last trade — materially harder to stop-hunt than a CEX, and worth surfacing in your UI.
- Sub-accounts and vaults both exposed in the SDK. **Sub-accounts are separate users for rate-limiting purposes** — which is how you scale past the address-based limit.

### Rate limits (the one that will bite you)
- IP: 1,200 weight/min aggregated across `/info` + `/exchange`; info endpoint weights range 2–60; 10 concurrent WS connections, 1,000 total subscriptions **per IP** (10 connections does *not* give you 10,000 subs), 2,000 WS messages/min, 100 in-flight posts, 30 new connections/min, max 10 unique users across user-specific WS subscriptions.
- **Address-based: 1 request per 1 USDC of cumulative lifetime volume, with a 10,000-request starting buffer.** A brand-new user account gets 10,000 actions and then throttles to one request per 10 seconds until they trade. This is the single biggest architectural constraint for an LLM-driven terminal that polls or retries — budget requests per user, not globally.
- Cancels get a larger allowance: `min(limit + 100,000, limit × 2)`. Open orders: 1,000 + 1 per $5M volume, capped at 5,000.
- Batched orders count as 1 for IP limits but *n* for address limits.

### HIP-3 — yes, it's live, and it's the interesting part
Live on mainnet **2025-10-13**. Anyone staking **500,000 HYPE** (~$46M at HYPE $91.71 today; was ~$25M at launch) can deploy their own perp DEX on HyperCore with their own markets, oracle, leverage limits, fee schedule and front-end.

- Stake locked minimum **183 days**; excess above the current requirement is unstakeable. Threshold expected to fall over time.
- First 3 assets free; beyond that, Dutch auction shared across all perp DEXs. Deployers get `7 + 0.2 × n_auction_deployments` reserve deployments at the current auction price.
- **Deployer keeps up to 50% of trading fees.** Configurable additional fee share 0–300% (0–100% in growth mode); above 100% the protocol fee scales up to match. Growth mode cuts all-in fees, rebates and volume contribution by **≥90%** to bootstrap liquidity.
- **Slashing:** stake-weighted validator vote. Up to 100% for invalid state transitions or prolonged downtime, 50% for brief downtime, 20% for degradation. Applies during the 7-day unstake queue. Slashed stake is **burned, not paid to users** — so a slashing event does *not* make harmed traders whole.
- `haltTrading` lets the deployer cancel all orders and settle positions to mark. Cross-margin enablement is **permanently irreversible**.

**Live HIP-3 DEXs (API `{"type":"perpDexs"}`, 2026-09-20) — 10 exist, 4 have any flow at all:**

| DEX | Deployer | Markets | Live OI | 24h Vol |
|---|---|---|---|---|
| `xyz` (TradeXYZ) | Hyperunit team | 122 | **$3,790M** | $337M |
| `io` (EntropyIO) | — | 8 | $56.8M | $11.4M |
| `para` (Paragon) | — | 27 | $16.1M | $4.2M |
| `mkts` (Markets by Kinetiq) | — | 4 | $7.8M | $5.4M |
| `flx` (Felix), `vntl` (Ventuals), `hyna` (HyENA), `km`, `cash` (dreamcash), `abcd` | — | 0–24 each | **$0 / empty books** | $0 |

I checked `vntl:SPACEX` and `flx:NVDA` order books directly: **both empty.** Ventuals — the pre-IPO name everyone cites — has zero live open interest and no book. If pre-IPO exposure matters, the live venue is `xyz:SPCX` ($154.7M OI) and `io:ANTH` / `io:OAI` ($35.1M / $7.5M OI), not Ventuals.

**Verdict on deploying your own HIP-3 market: no.** 500k HYPE (~$46M) plus slashing exposure plus running an oracle relayer is not a fit for this project. The economics of builder codes (zero capital, 10 bps) are strictly better for the user's position.

---

## 2. ASTER

### Aster Code (builder program)
Structurally a clone of Hyperliquid builder codes, launched during 2026 H1:
- Deposit and maintain **100 $ASTER** in your perp account.
- Per-user **agent/API wallet** (`signer` address + key held on your backend).
- User signs `POST /fapi/v3/approveAgent` and `POST /fapi/v3/approveBuilder` (can be combined in one request — a genuine UX advantage over Hyperliquid's separate main-wallet signature).
- `maxFeeRate` capped at **0.001 (0.1%)**. Orders via `POST /fapi/v3/order` with `builder` + `feeRate`; the venue validates `feeRate ≤ approved max`.
- Endpoints: create/update/delete/get Agent; approve/update/delete/get Builder; place order with builder code. All EIP-712 with anti-replay nonces.
- **ADL and liquidation fills are excluded** from builder fees.
- Fees recorded daily, tracked in a "Builder Center." `[UNVERIFIED]` — the docs never state the claim mechanism or settlement asset; get this in writing before building.

Separately, Aster's referral program pays a default **10% commission**, splittable with the referee; approved affiliates get 20% from VIP1 referrals, 10% from VIP2+. On a 0.04% taker fee that's 0.004% of notional — **25x less than a 0.1% builder fee.** Use Aster Code, not referrals.

### Fees and the structural problem
- USDT-M perps: **0% maker / 0.04% taker**. USD1-margined: 0% / **0.005%**. RWA: 0% / **0.009%**. Maker fees went to zero 2026-02-02. 5% discount paying fees in $ASTER.
- This is the problem: a 5 bp builder fee on a USD1 RWA perp is **10x the exchange's own taker fee**. Your markup becomes the dominant cost and is trivially visible to any user who reads the fee page. On Hyperliquid, 5 bps on a 4.5 bp base roughly doubles cost — annoying but defensible. On Aster it's indefensible. If you route Aster, charge 1–2 bps there, not 5.

### API surface
Base `https://fapi.asterdex.com`, WS `wss://fstream.asterdex.com`. **It is a near-exact Binance USD-M futures clone** — same endpoint paths, same `X-MBX-APIKEY` header, HMAC-SHA256, `recvWindow`, `X-MBX-USED-WEIGHT` headers, 418 IP-ban escalation from 2 min to 3 days. Order types: LIMIT, MARKET, STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET, TRAILING_STOP_MARKET; GTC/IOC/FOK/GTX. WS connections expire at 24h.

**This is Aster's single biggest engineering advantage**: every Binance-futures library, backtester and bot framework works with a base-URL change. Building the Aster adapter is probably a day; the Hyperliquid adapter is a week.

### What's actually listed and actually traded (live, 2026-09-20)
602 symbols, 581 TRADING, 16 SETTLING, 5 PENDING. 597 with non-zero 24h volume, totalling **$1.49B**.

| Symbol | 24h Vol | Trades | OI | Top-5 spread |
|---|---|---|---|---|
| BTCUSDT | $390.9M | 73,420 | $479.5M | 0.0 bp |
| ETHUSDT | $298.2M | — | $257.1M | — |
| **XAUUSD1** (gold) | **$184.4M** | 58,150 | $67.5M | 0.0 bp |
| **CLUSD1** (crude) | $66.0M | — | $25.8M | — |
| SKHYNIXUSD1 | $28.7M | — | — | — |
| **SPCXUSD1** (SpaceX) | $24.1M | 10,462 | $18.1M | 0.7 bp |
| SNDKUSD1 / MUUSD1 | $20.9M / $20.5M | — | — | — |
| **NVDAUSDT** | **$0.02M** | **35** | $0.48M | 0.5 bp, $613 on the bid |
| TSLAUSDT / AAPLUSDT / MSFTUSDT | $0.02M / $0.01M / $0.03M | 57 / 54 / 50 | — | — |

**Aster's "24/7 zero-fee US stock perps" are marketing.** Seven mega-cap tickers combined did roughly **$130,000** of volume in 24 hours across ~350 trades, with a $613 top-of-book bid on NVDA. Zero fees did not create liquidity. Where Aster genuinely works as an RWA venue is **gold ($184M/day) and crude ($66M/day) in USD1**, plus a handful of Korean/memory semiconductor names.

### Other Aster features
- **Hidden orders / hidden positions** — limit orders invisible to the public book, and the resulting position is suppressed from public feeds. Genuinely differentiated; nothing equivalent on Hyperliquid. Relevant if your terminal's users care about not being front-run by the copy-trading crowd.
- **Multi-chain**: deposit USDT/USDC/ETH/SOL on BNB Chain, Ethereum, Solana or Arbitrum into a single account with no explicit bridge step.
- **Aster Chain**, a privacy-focused L1 for derivatives, launched genesis phase March 2026.
- Up to 1001x leverage on some pairs (a liability, not a feature, for a terminal you operate).
- 99% of daily protocol fees TWAP into $ASTER buybacks for veASTER stakers (announced 2026-06-17) — note this means Aster's fee revenue goes to token holders, not to a war chest that could backstop a bad day.

---

## 3. GMGN.ai

**What it is:** a memecoin trading router and terminal, not a perp venue. Fits as a sidecar for the long-tail discovery/degen flow, not as anything in the perps thesis.

- **Fee: 1% per trade, charged on both buy and sell.** No volume tiers, no built-in rebates. This is 20x Hyperliquid's taker fee and it is the single most important fact about GMGN.
- **Referral: 10–30% of that 1%**, scaling with referred volume; higher tiers require a Google-form application. Payout appears to be in SOL, monthly. `[UNVERIFIED]` — exact tier thresholds are not published; you must apply to learn them. At 20%, you earn 20 bps per side, ~40 bps round trip — **4–8x what a Hyperliquid builder code pays**, because the underlying fee is so much fatter.
- **Trading API:** three endpoints — `GET /defi/router/v1/sol/tx/get_swap_route` (returns unsigned tx + routing), `POST /txproxy/v1/send_transaction` (signed base64), `GET /defi/router/v1/sol/tx/get_transaction_status`. There's an optional `partner` parameter for attribution. Access is **volume-gated** (you must already be doing size on GMGN), granted via Google form, ~24h review, key delivered by email as `x-route-key`.
- **Rate limit: one call per 5 seconds per key.** That is not a trading API in any serious sense — it's a retail convenience wrapper. You cannot build responsive execution on it.
- **Chains:** the trading endpoints document **Solana only** ("only support sol so far") despite marketing claiming SOL/BSC/Base/ETH. `[UNVERIFIED]` whether the EVM endpoints are generally available.
- **Embeddable chart:** `https://www.gmgn.cc/kline/{chain}/{token_CA}`, chains sol/eth/bsc, params `?theme=light|dark` and `?interval=1S|1|5|15|60|240|720|1D`. Docs say "feel free to integrate" with **no stated licence, cost, attribution requirement or SLA.** That is a liability, not a gift — an unversioned iframe with no contract can change or disappear. Do not put it on a critical path.
- Data-crawling access requires IP whitelisting via a separate application.

**Where it fits:** GMGN's commission economics are genuinely better per dollar of volume than perp builder codes, but the flow is smaller, the API is unusable for automation at 1 call / 5s, the fee is high enough that sophisticated users will route elsewhere, and none of it touches equities or commodities. Use it to capture memecoin flow the perp venues can't serve, behind a clear disclosure that the fee is 1%.

---

## 4. TOKENIZED EQUITIES & RWA AS PERPS — IS IT REAL?

**Partly. The honest answer is: index and commodity perps are real; single-stock perps are thin; pre-IPO is concentrated in two or three names; and almost all of it lives on one deployer.**

### What's genuinely tradeable (live OI, 2026-09-20)

| Market | Venue | Open Interest | 24h Vol (weekend) | Top-5 book | Spread |
|---|---|---|---|---|---|
| `xyz:SP500` (S&P licensed) | HL/TradeXYZ | **$422.6M** | $28.0M | $74k bid / $141k ask | 0.1 bp |
| `xyz:GOLD` | HL/TradeXYZ | $296.4M | $4.6M | $25k bid / $214k ask | 0.2 bp |
| `xyz:XYZ100` (Nasdaq synth) | HL/TradeXYZ | $185.9M | $26.6M | — | — |
| `xyz:CL` (crude) | HL/TradeXYZ | $177.5M | $53.6M | — | — |
| `xyz:SILVER` | HL/TradeXYZ | $163.2M | $6.6M | — | — |
| `xyz:SPCX` (SpaceX) | HL/TradeXYZ | $154.7M | $7.8M | — | — |
| `xyz:NVDA` | HL/TradeXYZ | $141.7M | $2.9M | **$53k bid / $41k ask** | 0.5 bp |
| `xyz:GOOGL` | HL/TradeXYZ | $98.5M | $3.0M | — | — |
| `xyz:AAPL` | HL/TradeXYZ | $85.7M | $2.1M | — | — |
| `XAUUSD1` (gold) | Aster | $67.5M | $184.4M | $76k / $33k | 0.0 bp |
| `io:ANTH` (Anthropic pre-IPO) | HL/EntropyIO | $35.1M | $3.4M | — | — |
| `SPCXUSD1` | Aster | $18.1M | $24.1M | $52k / $76k | 0.7 bp |
| `NVDAUSDT` | Aster | $0.48M | **$0.02M** | **$613 bid** | 0.5 bp |
| `vntl:SPACEX`, `flx:NVDA` | HL/Ventuals, Felix | **$0** | $0 | **empty** | — |

### The skeptical read
1. **Spreads are tight (0.1–0.7 bp) but books are shallow.** $40–75k in the top five levels on NVDA. You can move a mega-cap equity perp 20+ bps with a $500k market order on a weekend. Tight spread ≠ depth; do not let a UI imply otherwise.
2. **Volume/OI ratio is telling.** `xyz:GOLD` has $296M OI against $4.6M of weekend turnover — that's positional carry, not an active market. `xyz:CL` at $53.6M vol on $177M OI is the healthiest non-index RWA on either venue.
3. **Concentration risk is total.** TradeXYZ is >90% of HIP-3 open interest. Six of the ten HIP-3 DEXs have literally zero. Your "tokenized equities" product is a bet on one team's oracle relayer and listing decisions.
4. **The oracle is the whole product, and it's weakest exactly when you'd most want the market.** During US session, `xyz` oracles pull real exchange feeds via TradeXYZ relayers updating roughly every 3 seconds. **When TradFi markets close, the oracle switches to a continuously-calculated exponential moving average** of the perp's own price, reanchoring to spot when markets reopen. Overnight and weekends, the "price of NVDA" is substantially Hyperliquid's own order book talking to itself. Gap risk at Monday open is structural, not hypothetical.
5. **HLP does not backstop HIP-3.** Hyperliquid's protocol vault provides liquidity to native BTC/ETH perps only. `xyz` liquidity is entirely voluntary external market makers who can and will step away.
6. **Aster's single-stock perps are not a market.** $10–30k/day, 35–60 trades, zero fees. Don't build UI for them.
7. **Neither venue gives you equity ownership, dividends, or voting.** These are synthetic cash-settled exposures with a funding leg. Anyone coming from equities will assume otherwise unless you say it loudly.

**Bottom line: "trade tokenized stocks as perps" is ~60% real.** Real for S&P/Nasdaq indices, gold, silver, crude, and a top-10 list of mega-caps in US hours. Marketing for the long tail, for weekends, and for almost every venue that isn't TradeXYZ.

---

## 5. NANSEN API

**Pricing:** ~$10 per 10,000 credits purchased. Pro plan $49/mo (annual) or $69/mo includes 2,000 credits, restored to a 2,000 floor on the 1st UTC (not additive — unused credits don't roll). Purchased credits expire 1 year out; soonest-expiring batch consumed first; included credits are spent before purchased ones. Free plan burns 10x the credits for identical calls.

**Rate limits:** Free 15 req/s, 300/min. Pro (all paid tiers) **75 req/s, 1,500/min**. Endpoint-specific overrides: TGM perp trades 60/min, **profiler perp trades 5/min**, web search/fetch 15/min, token-sector search 60/min. 429s carry `X-Nansen-RateLimit-Scope` and `Retry-After`.

**What credits buy (per call):**
- **Smart Money (5 cr):** netflows, holdings, historical-holdings, `dex-trades`, jupiter-dcas, **`perp-trades`**
- **Profiler (1 cr base):** address balances, transactions, **perp positions**, related-wallets, pnl-summary; counterparties 5; **perp-leaderboard 5**; address labels **100 common / 500 premium**
- **Token God Mode (1–5 cr):** screener, flow-intelligence, holders, **perp-positions**, flows, who-bought-sold, trades, transfers, leaderboards, token-information, indicators, ohlcv. **+150 cr if `premium_labels=true`** (Smart Money / Fund labels)
- **Prediction Markets (1–5 cr):** screener, orderbook, ohlcv, trades, pnl, top-holders
- **Backtesting (5–25 cr):** historical dex-trades, who-bought-sold, token-flow-summary (5); historical top-holders, pnl-leaderboard, **token-quant-scores (25)**
- **Agent (200 / 750 cr):** fast / expert

**Latency and depth:** DEX-trades latency is "often within seconds, depending on chain," but **only the trailing 24 hours of DEX trades is queryable** on the live endpoint. Smart Money Historical Holdings is a **daily EOD snapshot** — completed-day processing starts 05:00 UTC, typically available by 07:00 UTC, with today's row as live partial data. **4-year rolling window**, oldest date advancing daily. 25+ chains (ETH, Solana, Base, BNB, Arbitrum, Polygon, Optimism, Avalanche, Linea, Blast, Mantle, zkSync, etc.). **No WebSocket / streaming** documented — it's poll-only REST.

**Usable as live signal:**
- ✅ Smart-money DEX trades and netflows on a 30–60s poll for fresh-token / rotation detection
- ✅ TGM flow-intelligence and who-bought-sold for confirming a thesis before sizing
- ✅ Perp-positions / perp-leaderboard for crowding and squeeze setups — genuinely useful for the perps pivot
- ✅ Backtesting endpoints (token-quant-scores at 25 cr) for offline strategy validation

**Not usable as live signal:**
- ❌ Anything sub-second or execution-triggering. No streaming, poll-only, seconds of latency at best, 75 req/s ceiling.
- ❌ Historical holdings as intraday signal — it's a daily EOD snapshot with a 2-hour processing lag.
- ❌ Premium labels in a hot loop. At 500 credits (~$0.50) per profiler premium-label call, a 200-wallet watchlist refreshed hourly is **$2,400/day.** Cache labels for days or weeks; they barely move.
- ❌ Profiler perp trades at **5 requests/minute** — that's a research tool, not a monitor.

**Practical budget:** a 60-second poll of one 5-credit smart-money endpoint is 5 × 1,440 = 7,200 credits/day ≈ **$7.20/day, ~$220/month**. Two or three such loops plus cached labels lands around $500–900/month. That is the real number, and it dwarfs the $49 subscription.

---

## 6. WHAT THIS ACTUALLY EARNS AND WHAT IT ACTUALLY COSTS

### Revenue: linear in volume, no leverage, no tiers

Builder fee is `bps × notional`, charged both sides on perps. At Hyperliquid's market-clearing retail rate of **3 bps**:

| Daily routed notional (one-way) | Monthly | @1 bp | @3 bps | @5 bps | @10 bps |
|---|---|---|---|---|---|
| $100k | $3M | $300 | $900 | $1,500 | $3,000 |
| $500k | $15M | $1,500 | $4,500 | $7,500 | $15,000 |
| $1M | $30M | $3,000 | $9,000 | $15,000 | $30,000 |
| $5M | $150M | $15,000 | $45,000 | $75,000 | $150,000 |
| $20M | $600M | $60,000 | $180,000 | $300,000 | $600,000 |
| $100M | $3B | $300,000 | $900,000 | $1.5M | $3M |

Calibration from real builders: Phantom took **4 years' worth of wallet distribution and 137k users** to reach $39.4B cumulative volume and $20.6M. Based needed 42,579 users for $44B. **A terminal with 100 active users doing $10k/day each is $1M/day = $30M/month = $9,000/month at 3 bps.** That is the realistic first-year ceiling for a good product with no distribution advantage, and it is roughly one senior engineer's salary before costs.

### The fee stack the user actually pays (Hyperliquid, tier 0, no staking)
- Taker in: 4.5 bps + 3 bps builder = **7.5 bps**
- Taker out: 4.5 + 3 = **7.5 bps**
- **Round trip: 15 bps of notional.** At 10x leverage that is **1.5% of posted margin per round trip** — before funding, before slippage.
- Add funding: baseline interest component is **0.01%/8h = 11.6% APR paid by longs to shorts**, hourly settlement, premium clamped ±0.05%, total capped at 4%/hour.
- HIP-3 `xyz` markets run at roughly 2x core rates: **0.03% maker / 0.09% taker**, because deployer and protocol split the fee 50/50. A 3 bp builder fee on top makes a round-trip equity perp trade **~24 bps**. Growth mode can cut the venue side by ≥90% on a given asset — check `xyz` per-asset status before quoting anything to users.
- Discounts available: HYPE staking gives 5%/10%/15%/20%/30%/40% off at >10/100/1k/10k/100k/500k HYPE. Referral gives the referee 4% off first $25M. Maker rebates kick in at -1/-2/-3 bps for >0.5%/1.5%/3.0% of maker volume.

**At small size, the fee tier that matters is tier 0 and it will stay tier 0.** Tier 1 requires $5M of 14-day volume *per trading account* — that's the user's volume, not yours. Your builder code does not aggregate users into a better tier. Every user you onboard pays 4.5 bps taker forever unless they individually trade $5M/14d or stake HYPE. **The only fee lever you control for your users is HYPE staking on their behalf (you can't) or choosing a lower builder fee (you can).**

### Infrastructure costs (monthly, realistic)

| Item | Cost | Note |
|---|---|---|
| Hyperliquid non-validating node | **$300–700** | 16 cores / 128 GB RAM / 500 GB SSD, Ubuntu 24.04, ports 4001–4002 open, **Tokyo colocation** (validator set concentrates there). Bare-metal, not cloud, if latency matters. |
| Sentry peering (better gossip) | $0–1,500 | `[UNVERIFIED]` — QuickNode sells this; a node is only as good as its peers. Optional at first. |
| Nansen credits | **$220–900** | See §5. The $49 subscription is noise; the credits are the cost. |
| Aster / GMGN API | $0 + 100 ASTER (~$76) + 100 USDC | Trivial |
| App hosting, DB, WS fanout | $200–800 | Scales with concurrent users |
| LLM inference | $500–5,000+ | Wholly dependent on your agent design — likely your largest variable cost |
| Market data (TradFi reference prices for equity perps) | $0–2,000 | You will want an independent price to sanity-check TradeXYZ's oracle. `[UNVERIFIED]` pricing. |
| Legal (see §7) | $10k–50k one-time | Non-optional if you take US flow |
| **Run-rate floor** | **~$1,500–3,000/mo** | Excluding LLM, legal, and any salary |

### The blunt conclusion
**Break-even on infrastructure alone is ~$500k–1M/day of routed notional at 3 bps.** Below that you are paying to operate. The gap between "infrastructure break-even" (~$1M/day) and "this is a business" (~$20M/day, $180k/mo) is a factor of twenty, and that factor is entirely **distribution** — which is why Phantom and MetaMask lead the table and clever terminals don't. The builder-code mechanism is free money per unit of flow and offers **no mechanism whatsoever for generating flow**. Do not confuse having the pipe with having the water.

Secondary earner worth noting: the Hyperliquid **referral** program (10% of referred users' fees, first $1B of their volume) stacks on top of builder codes and costs nothing to enable. At 4.5 bps taker that's 0.45 bps of extra revenue per unit of flow — a ~15% uplift on a 3 bp builder fee. Turn it on.

---

## 7. THE RISK SURFACE NOBODY MENTIONS

### Funding — the silent P&L leak
- Hyperliquid pays funding **hourly**, computed as `premium + clamp(interest_rate − premium, −0.0005, 0.0005)`, where the interest component is **0.01% per 8h = 11.6% APR structurally paid by longs to shorts.** A flat long carried for a month bleeds ~1% with no price move. Equities people who think of futures as roll-cost-free will not see this coming.
- **The rate is capped at 4%/hour.** Not 4% annualised — 4% *per hour*. In a squeeze that is 96% of notional per day. This is not theoretical; it is the mechanism by which a "hedged" position becomes a total loss.
- Funding is charged on **oracle price × position size**, not mark price.
- HIP-3 perps use a more reactive premium formula: `0.5 × (impact_bid + impact_ask) / oracle − 1`. In a thin equity book that responds violently to small orders — and equity perp books are thin (see §4).
- Live today on `xyz:CL`: 0.0099%/hr ≈ **8.7% APR**; `xyz:GOOGL` 0.0017%/hr. On Aster, `CLUSD1` last funding 0.0267%. These are real, current, and compounding.

### Liquidation cascades and ADL
- **October 10, 2025** remains the reference event: $19B liquidated, 1.6M traders, perp OI across major venues down 43% ($217B → $123B) in a day. **Hyperliquid's OI fell 57%, $14B → $6B.** USDe depegged to $0.65 on Binance. dYdX was down 8 hours; Lighter 4.5 hours; Binance had API failures and deposit delays. Traders who could not add collateral were liquidated on positions that would otherwise have survived.
- **Auto-deleveraging (ADL) means a winning position can be force-closed.** Hyperliquid ADL'd shorts during 10/10. Your users will interpret this as the venue stealing their profits, and explaining it after the fact does not work. Surface ADL rank in the UI.
- Hyperliquid triggers stops on **oracle mark price**, which protects against wick-hunting but means a stop can fail to fire when your local book prints through it. Different failure mode, not an absent one.

### Oracle manipulation — the specific, demonstrated attack
- **JELLY, 2025-03-26:** attacker opened a $6–8M short on the JELLYJELLY perp, then bought the thin spot token across DEXs, taking its market cap from $10M to $50M+ in under an hour. Forced liquidation pushed the position into the HLP vault, producing a **$13.5M unrealised loss** for protocol LPs. Fund pooling inside HLP prevented ADL from recognising the liquidator strategy's loss as critical. Hyperliquid delisted the market and tightened liquidator limits.
- **This class of attack is exactly what HIP-3 multiplies.** Each deployer runs their own oracle. Hyperliquid's own docs warn that "most price indices are unsuitable as perp oracle sources" and that cross-margin assets must be excluded if they move >50% daily more than monthly. Slashing (up to 100%, stake-weighted validator vote) is the only deterrent — and **slashed stake is burned, not distributed to harmed users.** You have no recovery path.
- Weekend/overnight equity oracles are EMAs of the perp's own price (§4). During those windows the oracle is reflexive by construction: push the book, push the oracle, push funding, push liquidations. Your terminal will be routing into this. Consider hard-disabling or size-capping equity perps outside cash-session hours.

### Venue insolvency, downtime and counterparty concentration
- Hyperliquid, 2025-07: **37-minute frontend outage, ~27 minutes where orders could not be sent** (14:20–14:47 UTC), caused by a traffic spike. Positions could not be liquidated or managed. Hyperliquid issued automated refunds — voluntarily, with no obligation to. There was also a scheduled ~10-minute upgrade on 2026-09-05.
- **HLP does not backstop HIP-3 markets.** If a TradeXYZ market blows up, there is no protocol vault absorbing it — only ADL against profitable counterparties, i.e. possibly your users.
- **Aster's volume integrity is an open question.** DeFiLlama delisted Aster's perp data in October 2025 after 0xngmi showed near-1:1 correlation between Aster's XRP/USDT and ETH/USDT volumes and Binance's, with no granular maker/taker data to verify. Aster's CEO attributed it to airdrop-farming API traders. Aster has been relisted; the question has not been answered. If you build revenue projections on Aster's reported volume, you are building on unaudited numbers.
- **Aster routes 99% of protocol fees into $ASTER buybacks** for veASTER stakers. That is a distribution policy, not a reserve policy — there is no visible insurance fund accumulating for a bad day.
- **You hold user funds in nothing, but you hold user agent keys in everything.** A terminal with per-user agent wallets on both venues is a single compromise away from an exchange-scale incident. Agent wallets on Hyperliquid cannot withdraw, which limits blast radius to "an attacker can trade your users' accounts to zero" — still catastrophic. Aster's `approveAgent` supports IP whitelisting and expiry; **use both.** Hyperliquid agent wallets should be short-lived and rotated.

### Regulatory — the part that can end the project
This is the sharpest risk and it is not primarily about the venues; **it is about you, because you are the one taking a fee to route someone else's order.**

- **The enforcement precedent is directly on point.** The CFTC fined **Falcon Labs $1.7M** for acting as an unregistered Futures Commission Merchant by *facilitating* digital-asset derivatives trades for US customers — i.e. routing, not operating a venue. In the 2023 DeFi trifecta (Opyn, ZeroEx, Deridex) the CFTC held that **blocking US IP addresses was "not sufficient"** because users could reach the protocol by other paths. Taking a fee on the order is the thing that makes you an intermediary.
- **2026 has brought real onshore clarity, and it does not obviously help you.** In late May 2026 the CFTC approved **KalshiEX's BTCPERP**, the first US-listed perpetual future, and determined perps referencing digital commodities with deep spot markets may be treated as futures rather than swaps. Separately, the **CFM Letter** gave Coinbase Financial Markets — a *registered FCM* — no-action relief to offer offshore perps to US customers under conditions. The framework's message is: there is now a legitimate path for US flow to reach offshore perps, and **it runs through a registered FCM.** You are not one.
- **The SEC's April 13, 2026 staff statement on "Covered User Interface Providers"** (Division of Trading and Markets) says staff will not object to certain crypto front-ends operating without broker-dealer registration under §15(a). But: it addresses **crypto asset securities**, not derivatives; the conditions require no solicitation, user-customisable parameters, educational material, no routing discretion, no custody, no PFOF, and — critically — **"neutral compensation": fixed charges that are product-, route-, venue- and counterparty-agnostic.** A builder fee that varies by venue or market arguably fails that condition. The relief is withdrawn **April 13, 2031** absent permanent rulemaking. `[Secondary sources characterise this as excluding derivatives/perps outright; the SEC statement itself is the controlling text and should be read by counsel — I have not read it in full.]`
- **Practical posture for a terminal that routes others' flow:**
  1. Assume that charging a builder fee on US persons' perp orders is an unregistered-intermediary exposure. Get an opinion before launch, not after.
  2. IP geoblocking alone is documented as insufficient. Wallet screening, OFAC lists, ToS attestation, and blocking known VPN ranges are the minimum, and still may not suffice.
  3. If you route your **own** capital only, this entire section largely evaporates. The regulatory risk arrives with the *second* user. That is the actual product decision.
  4. Equity perps compound it: you are offering leveraged synthetic exposure to US-listed securities to retail, 24/7, with no registration. The SEC CUI relief was written for spot DeFi interfaces, not this.
  5. FinCEN MSB registration and state money-transmitter analysis are separate questions if you ever touch fiat on/off ramps.
- **The regulatory asymmetry is the strongest argument for Hyperliquid-first, self-flow-first**: prove the strategy with your own capital where the legal surface is near-zero, then decide whether the ~$9k/month that 100 users would generate is worth the compliance build.

---

## Recommended build order
1. **Hyperliquid adapter** (Python SDK, agent wallets, builder code at 2–3 bps), self-flow only. Node optional at first; add the Tokyo non-validating node when latency or WS subscription limits bite.
2. **Aster adapter** second — it's a Binance-futures clone, so it's cheap. Route gold/crude/USD1 RWA there at 1–2 bps, not 5.
3. **Nansen** as a research and pre-trade layer with aggressive caching, budgeted at ~$500/mo. Never in the execution path.
4. **GMGN** last and behind a wall, with the 1% fee disclosed. Its 1-call-per-5-seconds limit makes it a manual-trade convenience, not an automated route.
5. **Do not deploy a HIP-3 market.** 500k HYPE ≈ $46M plus slashing plus oracle operations, versus $100 USDC for a builder code that pays the same 10 bps ceiling.
6. **Do not onboard third-party users until counsel signs off.** The mechanism that earns the money is the same mechanism that creates the exposure.

---

## Sources

**Hyperliquid**
- [Builder codes — Hyperliquid Docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes)
- [Fees — Hyperliquid Docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
- [Funding — Hyperliquid Docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding)
- [Rate limits and user limits — Hyperliquid Docs](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits)
- [HIP-3: Builder-deployed perpetuals — Hyperliquid Docs](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals)
- [Referrals — Hyperliquid Docs](https://hyperliquid.gitbook.io/hyperliquid-docs/referrals)
- [Order types — Hyperliquid Docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/order-types)
- [Foundation non-validating node — Hyperliquid Docs](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/nodes/foundation-non-validating-node)
- [hyperliquid-python-sdk](https://github.com/hyperliquid-dex/hyperliquid-python-sdk)
- Live API: `POST https://api.hyperliquid.xyz/info` — `perpDexs`, `metaAndAssetCtxs`, `l2Book` (pulled 2026-09-20 ~02:00 UTC)

**Builder economics**
- [Top Hyperliquid Builders — CoinGecko Research](https://www.coingecko.com/research/publications/top-hyperliquid-builders) (snapshot 2026-05-25)
- [Hyperliquid Builder Codes: Earning Millions — Dwellir](https://www.dwellir.com/blog/hyperliquid-builder-codes)
- [Hyperliquid Builder Codes — Blockworks Analytics](https://blockworks.com/analytics/hyperliquid/hyperliquid-builder-codes/hyperliquid-builder-codes-trading-builder-fees)
- [Hyperliquid Builder Program Tops $64M — The Currency Analytics](https://thecurrencyanalytics.com/altcoins/hyperliquid-builder-program-tops-64m-as-phantom-and-based-lead-revenue-race-261485)

**HIP-3 / equity perps**
- [HIP-3 Data & Analytics — Loris Tools](https://loris.tools/hip3) (as of 2026-09-19: $61.39B 30d volume, $1.88B OI, 107,577 traders, $3.62M fees)
- [What Is HIP-3? — Nansen](https://nansen.ai/post/what-is-hip-3-hyperliquid)
- [Equity Perps on Hyperliquid via trade.xyz — Hyperliquid Guide](https://hyperliquidguide.com/guides/trading/equity-perps-guide)
- [trade[XYZ] Docs — Perp Mechanics](https://docs.trade.xyz/perp-mechanics/overview)
- [Hyperliquid's HIP-3 & HIP-4 — CoinGecko](https://www.coingecko.com/learn/hyperliquid-hip3-hip4-tokenized-stocks-and-prediction-markets)
- [The Transformational Potential of HIP-3 — FalconX](https://www.falconx.io/newsroom/the-transformational-potential-of-hyperliquids-hip-3)

**Aster**
- [Aster Code — Aster Docs](https://docs.asterdex.com/program-and-rewards/aster-code)
- [Aster Code endpoints / integration flow — Aster API Docs](https://asterdex.github.io/aster-api-website/asterCode/integration-flow/)
- [Perpetual Fees — Aster Docs](https://docs.asterdex.com/trading/perpetuals/fees-and-specs/fees)
- [Hidden Order & Hidden Position — Aster Docs](https://docs.asterdex.com/trading/perpetuals/order-types/hidden-order-and-hidden-position)
- [API Documentation — Aster Docs](https://docs.asterdex.com/for-developers/aster-api/api-documentation)
- [Referral Program — Aster Docs](https://docs.asterdex.com/program-and-rewards/referral-program)
- [Aster Launches 24/7 Stock Perpetual Contracts — CryptoSlate](https://cryptoslate.com/press-releases/aster-launches-24-7-stock-perpetual-contracts-trading-with-exposure-to-u-s-equities/)
- [Aster DEX Review — Datawallet](https://www.datawallet.com/crypto/aster-dex-review)
- [DeFiLlama Delists Aster Over Wash Trading Suspicions — CryptoPotato](https://cryptopotato.com/defillama-delists-asters-perpetual-futures-data-following-wash-trading-suspicions/)
- [Aster Back on DeFiLlama, Wash-Trading Fallout Unresolved — CCN](https://www.ccn.com/news/crypto/aster-defillama-washtrading-fallout/)
- Live API: `https://fapi.asterdex.com/fapi/v1/` — `exchangeInfo`, `ticker/24hr`, `depth`, `openInterest`, `premiumIndex` (pulled 2026-09-20 ~02:00 UTC)

**GMGN**
- [Integrate GMGN Solana Trading API — GMGN Docs](https://docs.gmgn.ai/index/cooperation-api-integrate-gmgn-solana-trading-api)
- [Integrate GMGN price chart — GMGN Docs](https://docs.gmgn.ai/index/cooperation-api-integrate-gmgn-price-chart)
- [Referral Link — GMGN Docs](https://docs.gmgn.ai/index/referral-link)
- [Refer friends to earn 30% rebates — GMGN Docs](https://docs.gmgn.ai/index/cooperation-referral-refer-friends-to-earn-rebate-30-rebates-easily-earn-over-usd8000-monthly)
- [GMGN Fees & Review 2026 — uwuu.ai](https://uwuu.ai/blog/gmgn-review)

**Nansen**
- [Credits & Pricing Guide — Nansen API Docs](https://docs.nansen.ai/getting-started/credits)
- [Rate Limits — Nansen API Docs](https://docs.nansen.ai/getting-started/rate-limits)
- [Endpoints Overview — Nansen API Docs](https://docs.nansen.ai/api/overview)
- [Data Methodology & Technical Reference — Nansen API Docs](https://docs.nansen.ai/guides/data-methodology-and-technical-reference)
- [DEX Trades — Nansen API Docs](https://docs.nansen.ai/api/smart-money/dex-trades)

**Risk & regulatory**
- [What Is October 10th? Crypto's 10/10 Liquidation Event — CoinGecko](https://www.coingecko.com/learn/october-10-crypto-crash-explained)
- [Market Spotlight: Inside Crypto's $19B Liquidation Event — CoinDesk](https://www.coindesk.com/research/market-spotlight-the-19-billion-liquidation-that-shook-crypto)
- [Hyperliquid and the JELLY attack — OAK Research](https://oakresearch.io/en/analyses/investigations/hyperliquid-jelly-attack-context-vulnerability-team-solution)
- [Hyperliquid API outage caused by traffic spike — The Block](https://www.theblock.co/post/364798/hyperliquid-outage-api-traffic-spike-not-hack-vulnerability-exploit)
- [CFTC Takes Historic Steps to Bring Digital Asset Perpetual Contracts Onshore — Dechert](https://www.dechert.com/knowledge/onpoint/2026/6/cftc-takes-historic-steps-to-bring-digital-asset-perpetual-contr.html)
- [Opening the Door to "Perps" — Proskauer](https://www.proskauer.com/alert/opening-the-door-to-perps-the-cftc-approves-us-listed-perpetual-futures)
- [SEC Staff Statement: Broker-Dealer Registration of Certain User Interfaces (2026-04-13)](https://www.sec.gov/newsroom/speeches-statements/staff-statement-regarding-broker-dealer-registration-certain-user-interfaces-utilized-prepare-staff-statement-regarding-broker-dealer-registration-certain-user-interfaces-utilized)
- [SEC Staff Issues Broker-Dealer Registration Guidance for Certain User Interfaces — WilmerHale](https://www.wilmerhale.com/en/insights/client-alerts/20260417-sec-staff-issues-broker-dealer-registration-guidance-for-certain-user-interfaces)
- [CFTC Orders Against Three DeFi Protocols — CFTC Release 8774-23](https://www.cftc.gov/PressRoom/PressReleases/8774-23)
- [CFTC's Message to DeFi Platforms — Morgan Lewis](https://www.morganlewis.com/pubs/2023/09/cftcs-message-to-defi-platforms-register-with-the-cftc-or-leave-the-us-market-or-risk-enforcement)

**Adjacent (FOMO / Robinhood Chain)**
- [FOMO API — Social Trading Data API](https://fomoapi.io/)
- [Robinhood Chain goes live on mainnet — The Block (2026-07-01)](https://www.theblock.co/news/business/2026-07-01-robinhood-chain-goes-live-mainnet-alongside-24-7-tokenized-stocks-lighter-perps-planned-crypto-agentic-trading-406918)
- [Robinhood Chain mainnet — Arbitrum Blog](https://blog.arbitrum.io/robinhood-chain-mainnet/)

---

**Items I could not verify and that need confirmation before you design against them:**
1. Aster Code fee **claim/withdrawal mechanism** and settlement asset — documented nowhere I could find.
2. Whether Hyperliquid builder codes are **fully supported on HIP-3 sub-DEX orders** — the `builder` field is on the order action and `hip3_order.py` exists, but no doc explicitly confirms builder fees accrue on `xyz:` fills. **Test on testnet before assuming your equity-perp flow monetises.**
3. GMGN referral tier thresholds and whether **API/partner integrations** qualify for the 10–30% share (application-gated, not published).
4. Whether GMGN's ETH/Base/BSC trading endpoints are generally available (docs say Solana only).
5. Exact scope of the SEC CUI statement with respect to derivatives and fee-taking interfaces — read the primary SEC text with counsel.
6. QuickNode-style Hyperliquid sentry peering pricing.
7. Per-DEX HIP-3 fee rates and deployer fee-share settings (loris.tools has a per-DEX table I could not extract from the static page).