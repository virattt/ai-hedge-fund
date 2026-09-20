# Perps Venues & Builder Economics — Infrastructure and Commercial Review

**Perps sections: live numbers pulled 2026-09-20 ~02:00 UTC.**
**Spot extension (§8): live numbers pulled 2026-09-20 ~02:20 UTC.**
Both snapshots are a Saturday night US — equity-perp and spot volumes are weekend-depressed; open interest is not. Anything unverified is flagged `[UNVERIFIED]`.

---

## VERDICT

**Build on Hyperliquid as the primary venue; treat Aster as a secondary route for gold/oil/USD1 RWA flow and as a hedge against single-venue risk.** Hyperliquid is roughly 3x Aster's live volume ($4.09B core + $0.34B HIP-3 vs Aster's $1.49B) and ~6x its open interest ($12.2B core + $3.8B HIP-3 vs ~$1.9B). More importantly, the thesis the user is betting on — "one venue where equities, commodities, crypto and memecoins all trade" — is *only actually true on Hyperliquid*, and specifically inside the HIP-3 `xyz` DEX: 122 non-crypto markets with $3.79B of real open interest, versus Aster, whose US single-stock perps are functionally dead (NVDAUSDT did **$20,000** of volume across **35 trades** in 24h despite zero fees). Builder economics are near-identical on paper (both cap perp builder fees at 0.1% of notional), but Hyperliquid's builder program is a proven revenue channel with public receipts — $63.5M+ cumulative to the top 10 builders as of 2026-05-25 — while Aster Code is newer and unproven. Aster's 0.04%/0.005%/0.009% taker fees are so low that a 0.05% builder fee would be 5–10x the exchange's own fee, which is a hard sell; Hyperliquid's 0.045% base taker absorbs a 0.025–0.05% builder markup much more naturally. The decisive counterweight: Aster was delisted from DeFiLlama in October 2025 over wash-trading suspicions (near-1:1 volume correlation with Binance pairs) and has been relisted without the questions being resolved. Build Hyperliquid-first, wrap Aster behind the same order-routing interface, and keep GMGN as a memecoin sidecar rather than a core venue.

**Spot addendum (see §8): the verdict does not change, but one day-one design decision does.** Hyperliquid's spot builder fee cap is genuinely 10x the perps cap (1% vs 0.1%) — verified in docs and SDK — but spot is only ~4% of Hyperliquid's perp volume and builder fees accrue on the **sell side only**. Net effect on break-even is about −15%, not −90%. The one thing spot forces on day one is the size of the `maxFeeRate` you ask for in the single shared approval, because raising it later costs another main-wallet signature.

---

## VENUE COMPARISON

| Dimension | **Hyperliquid** | **Aster** | **GMGN.ai** |
|---|---|---|---|
| Live 24h volume (2026-09-20, weekend) | $4.09B core perp + $0.34B HIP-3 + $0.16B spot | $1.49B (597 active symbols) | n/a (memecoin spot router) |
| Live open interest | $12.23B core + $3.79B `xyz` + ~$81M other HIP-3 | ~$1.9B (BTC $480M, ETH $257M, XAU $67M) | n/a |
| Max builder fee — perps | **0.1%** of notional, both sides, set per-order | **0.1%** (`maxFeeRate` cap 0.001) | — |
| Max builder fee — spot | **1.0%**, **sell side only** | n/a (no spot builder program found) | 10–30% rev-share of GMGN's 1% |
| Builder entry cost | 100 USDC in perps account | 100 $ASTER, maintained | Volume-gated approval, free |
| Base taker fee — perps | 0.045% (tier 0) → 0.024% at >$7B/14d | 0.04% USDT-M / 0.005% USD1 / 0.009% RWA | — |
| Base maker fee — perps | 0.015% (tier 0) → 0.000% at >$500M/14d | **0%** on all perps (since 2026-02-02) | — |
| Base fees — spot | 0.070% taker / 0.040% maker (tier 0) | — | 1% per side, flat |
| Auth model | EIP-712, no API keys; agent wallets; `ApproveBuilderFee` from main wallet | EIP-712 for Aster Code; HMAC-SHA256 for the Binance-clone REST | `x-route-key` header |
| API shape | Custom JSON `/info` + `/exchange`, WS; Python + TS SDKs | **Binance futures API clone** — enormous tooling reuse | 3 REST endpoints |
| Rate limits | 1,200 wt/min per IP; **1 req per 1 USDC lifetime volume** per address; 1,000 WS subs, 10 conns | 2,400 wt/min, 1,200 orders/min per IP | **1 call / 5 seconds** |
| Equity/RWA perps | 122 markets on `xyz` (TradeXYZ), incl. licensed SP500 | 11 USD1 RWA + stock perps; only XAU/CL/SKHYNIX/SPCX/SNDK/MU have real flow | None |
| Memecoins | Spot HIP-1/HIP-2 + some perps | Long tail of USDT perps | **Core competence** |
| Self-listing | **Yes — HIP-3 perps (500k HYPE); HIP-1 spot (Dutch auction from 500 HYPE)** | No | No |
| Spot↔perp margin netting | **Yes — portfolio margin, live since ~Dec 2025** | No | n/a |
| Privacy/hidden orders | No | **Yes** — hidden orders + positions; Aster Chain L1 | No |
| Integrity risk | JELLY oracle attack (2025-03-26, $13.5M HLP); 37-min API outage 2025-07 | **DeFiLlama delisting over wash-trading, Oct 2025** — unresolved | Fee opacity; 1% is very high |

---

## 1. HYPERLIQUID

### Builder codes — how they actually work
- A builder attaches `{"b": "0x...", "f": <tenths of a bp>}` to each order action. `f: 10` = 1 bp. Per-order, so you can vary the rate by market or user tier.
- **Cap: 0.1% on perps, 1% on spot.** Perps charge **both sides**; spot charges the **sell side only** ("builder codes do not apply to the buying side of spot trades" — fees are only collected in the quote/collateral asset).
- User signs `ApproveBuilderFee` **with their main wallet, not an agent wallet** — a real UX speed bump. It is a **single EIP-712 struct** (`hyperliquidChain`, `maxFeeRate`, `builder`, `nonce`) with **no asset-class or venue field**: one approval covers perps, spot and HIP-3 for that builder address.
- Max **10 active builder approvals per user**, revocable any time. Query with `{"type":"maxBuilderFee","user":"0x…","builder":"0x…"}`.
- Builder must hold **≥100 USDC perps account value** and be in **`standard` account-abstraction mode** — which means your fee-collection address cannot itself use unified account or portfolio margin.
- Fees accrue to the builder's referral balance, claimed via the normal referral-reward flow. Per-fill CSVs at `https://stats-data.hyperliquid.xyz/Mainnet/builder_fills/{lowercase_builder_addr}/{YYYYMMDD}.csv.lz4`.
- Stacks independently with the referral program: referrer earns 10% of referred users' fees (first $1B of their volume); referee gets 4% off (first $25M).

**What a builder earns per unit of flow:** flat. `builder_fee_bps × notional`, both sides on perps, sell side only on spot. At 5 bps that's **$500 per $1M of one-way perp notional**.

**Observed market rates** (CoinGecko/HyperTracker snapshot 2026-05-25, cumulative since inception):

| Builder | Revenue | Rate | Volume | Users |
|---|---|---|---|---|
| Phantom | $20.6M | 0.05% | $39.4B | 137,496 |
| Based | $15.1M | 0.025% | $44.0B | 42,579 |
| PVP | $7.9M | 0.038% | $16.9B | 28,189 |
| MetaMask | $6.5M | **0.1%** | $7.46B | 43,761 |
| Insilico | $3.3M | 0.01% | $32.2B | 2,962 |

**2.5–5 bps is the market-clearing retail rate.** MetaMask charges the full 10 bps and gets 1/5th the volume of Based at 2.5 bps.

### API surface
- `POST /info` (read), `POST /exchange` (write), plus WebSocket. No API keys — **EIP-712 signatures**. Agent wallets are the right pattern for a terminal: one signer per user, key held server-side.
- Official [Python SDK](https://github.com/hyperliquid-dex/hyperliquid-python-sdk) with `basic_builder_fee.py`, `approve.py`, `hip3_order.py`, `basic_order_with_builder_deployed_dex.py`.
- **Order types:** market, limit, post-only/ALO, reduce-only, IOC/GTC/FOK, stop-market, stop-limit, trigger, TWAP (min 30s sub-order interval, 3% max slippage per sub-order), scale/ladder.
- **Stops trigger on the oracle mark price**, not last trade — harder to stop-hunt than a CEX.
- Sub-accounts and vaults exposed in the SDK. **Sub-accounts are separate users for rate-limiting** — that is how you scale past the address-based limit.
- Asset index spaces: spot assets and builder-deployed perp DEXs occupy distinct ranges (`info.py`: "builder-deployed perp dexs start at 110000"). Your order-routing layer needs an explicit venue→index resolver from day one.

### Rate limits (the one that will bite you)
- IP: 1,200 weight/min across `/info` + `/exchange`; info weights 2–60; 10 concurrent WS connections, 1,000 total subscriptions **per IP**, 2,000 WS messages/min, 100 in-flight posts, 30 new connections/min, max 10 unique users across user-specific WS subs.
- **Address-based: 1 request per 1 USDC of cumulative lifetime volume, with a 10,000-request starting buffer.** A new user gets 10,000 actions then throttles to one request per 10 seconds until they trade. Budget requests per user, not globally.
- Cancels: `min(limit + 100,000, limit × 2)`. Open orders: 1,000 + 1 per $5M volume, cap 5,000.
- Unified account and portfolio margin users face a **50,000 daily action limit**; standard mode has none.

### HIP-3 — live, and the interesting part
Mainnet **2025-10-13**. **500,000 HYPE** stake (~$46M at HYPE $91.71 today) to deploy your own perp DEX on HyperCore with your own markets, oracle, leverage limits, fees and front-end.

- Stake locked ≥**183 days**; excess above current requirement unstakeable. First 3 assets free, then Dutch auction shared across all perp DEXs; deployers get `7 + 0.2 × n_auction_deployments` reserve deployments.
- **Deployer keeps up to 50% of trading fees.** Configurable share 0–300% (0–100% in growth mode); above 100% the protocol fee scales to match. Growth mode cuts all-in fees, rebates and volume contribution **≥90%**.
- **Slashing:** stake-weighted validator vote. Up to 100% for invalid state transitions or prolonged downtime, 50% brief downtime, 20% degradation. Applies during the 7-day unstake queue. **Slashed stake is burned, not paid to users.**
- `haltTrading` cancels all orders and settles to mark. Cross-margin enablement is **permanently irreversible**.

**Live HIP-3 DEXs (`{"type":"perpDexs"}`, 2026-09-20) — 10 exist, 4 have any flow:**

| DEX | Markets | Live OI | 24h Vol |
|---|---|---|---|
| `xyz` (TradeXYZ) | 122 | **$3,790M** | $337M |
| `io` (EntropyIO) | 8 | $56.8M | $11.4M |
| `para` (Paragon) | 27 | $16.1M | $4.2M |
| `mkts` (Markets by Kinetiq) | 4 | $7.8M | $5.4M |
| `flx`, `vntl`, `hyna`, `km`, `cash`, `abcd` | 0–24 each | **$0 / empty books** | $0 |

`vntl:SPACEX` and `flx:NVDA` order books are both **empty**. Ventuals — the pre-IPO name everyone cites — has zero live OI. Live pre-IPO is `xyz:SPCX` ($154.7M OI) and `io:ANTH` / `io:OAI` ($35.1M / $7.5M).

**Verdict on deploying your own HIP-3 market: no.** 500k HYPE plus slashing plus oracle operations is not a fit. Builder codes give the same 10 bps ceiling for $100.

---

## 2. ASTER

### Aster Code (builder program)
Structurally a clone of Hyperliquid builder codes, launched 2026 H1:
- Maintain **100 $ASTER** in your perp account.
- Per-user **agent/API wallet** (`signer` address + key on your backend).
- `POST /fapi/v3/approveAgent` and `POST /fapi/v3/approveBuilder`, combinable in one request — a genuine UX advantage over Hyperliquid's separate main-wallet signature.
- `maxFeeRate` capped at **0.001 (0.1%)**. Orders via `POST /fapi/v3/order` with `builder` + `feeRate`.
- **ADL and liquidation fills excluded** from builder fees.
- Fees recorded daily, tracked in a "Builder Center." `[UNVERIFIED]` — docs never state the claim mechanism or settlement asset. Get this in writing.

The referral program pays **10%** (20% for approved affiliates on VIP1 referrals). On a 0.04% taker fee that is 0.004% of notional — **25x less than a 0.1% builder fee**. Use Aster Code, not referrals.

### Fees and the structural problem
- USDT-M perps: **0% maker / 0.04% taker**. USD1-margined: 0% / **0.005%**. RWA: 0% / **0.009%**. Maker went to zero 2026-02-02. 5% discount paying in $ASTER.
- A 5 bp builder fee on a USD1 RWA perp is **10x the exchange's own taker fee**. Your markup becomes the dominant cost and is trivially visible. Charge 1–2 bps on Aster, not 5.

### API surface
Base `https://fapi.asterdex.com`, WS `wss://fstream.asterdex.com`. **A near-exact Binance USD-M futures clone** — same paths, `X-MBX-APIKEY`, HMAC-SHA256, `recvWindow`, `X-MBX-USED-WEIGHT`, 418 IP-ban escalation 2 min → 3 days. Order types: LIMIT, MARKET, STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET, TRAILING_STOP_MARKET; GTC/IOC/FOK/GTX. WS connections expire at 24h.

**Aster's biggest engineering advantage**: every Binance-futures library works with a base-URL change. The Aster adapter is a day; the Hyperliquid adapter is a week.

### What's actually listed and actually traded (live, 2026-09-20)
602 symbols, 581 TRADING. 597 with non-zero 24h volume, totalling **$1.49B**.

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

**Aster's "24/7 zero-fee US stock perps" are marketing.** Seven mega-caps combined did roughly **$130,000** in 24 hours across ~350 trades, with a $613 top-of-book bid on NVDA. Zero fees did not create liquidity. Where Aster works as an RWA venue is **gold ($184M/day) and crude ($66M/day) in USD1**.

### Other features
**Hidden orders / hidden positions** (genuinely differentiated; nothing equivalent on HL). **Multi-chain deposit** from BNB Chain, Ethereum, Solana, Arbitrum into one account. **Aster Chain**, a privacy L1, genesis March 2026. Up to 1001x leverage (a liability). 99% of daily protocol fees TWAP into $ASTER buybacks (announced 2026-06-17) — fee revenue goes to token holders, not to a reserve that could backstop a bad day.

---

## 3. GMGN.ai

A memecoin router and terminal, not a perp venue. Sidecar, not core.

- **Fee: 1% per trade, both buy and sell.** No volume tiers, no built-in rebates. 20x Hyperliquid's taker fee.
- **Referral: 10–30% of that 1%**, scaling with referred volume; higher tiers via Google-form application. Payout appears to be SOL, monthly. `[UNVERIFIED]` — exact thresholds unpublished. At 20% you earn 20 bps per side — **4–8x what a Hyperliquid builder code pays**, because the underlying fee is so much fatter.
- **Trading API:** `GET /defi/router/v1/sol/tx/get_swap_route`, `POST /txproxy/v1/send_transaction`, `GET /defi/router/v1/sol/tx/get_transaction_status`. Optional `partner` attribution param. Access **volume-gated**, Google form, ~24h review, `x-route-key` header.
- **Rate limit: one call per 5 seconds per key.** Not a trading API in any serious sense.
- **Chains:** trading endpoints document **Solana only** despite marketing claiming SOL/BSC/Base/ETH. `[UNVERIFIED]`.
- **Embeddable chart:** `https://www.gmgn.cc/kline/{chain}/{token_CA}`, chains sol/eth/bsc, `?theme=` and `?interval=`. **No stated licence, cost, attribution requirement or SLA.** An unversioned iframe with no contract — do not put it on a critical path.

---

## 4. TOKENIZED EQUITIES & RWA AS PERPS — IS IT REAL?

**Partly. Index and commodity perps are real; single-stock perps are thin; pre-IPO is two or three names; and almost all of it lives on one deployer.**

| Market | Venue | Open Interest | 24h Vol (weekend) | Top-5 book | Spread |
|---|---|---|---|---|---|
| `xyz:SP500` (S&P licensed) | HL/TradeXYZ | **$422.6M** | $28.0M | $74k / $141k | 0.1 bp |
| `xyz:GOLD` | HL/TradeXYZ | $296.4M | $4.6M | $25k / $214k | 0.2 bp |
| `xyz:XYZ100` (Nasdaq synth) | HL/TradeXYZ | $185.9M | $26.6M | — | — |
| `xyz:CL` (crude) | HL/TradeXYZ | $177.5M | $53.6M | — | — |
| `xyz:SILVER` | HL/TradeXYZ | $163.2M | $6.6M | — | — |
| `xyz:SPCX` (SpaceX) | HL/TradeXYZ | $154.7M | $7.8M | — | — |
| `xyz:NVDA` | HL/TradeXYZ | $141.7M | $2.9M | **$53k / $41k** | 0.5 bp |
| `xyz:GOOGL` | HL/TradeXYZ | $98.5M | $3.0M | — | — |
| `xyz:AAPL` | HL/TradeXYZ | $85.7M | $2.1M | — | — |
| `XAUUSD1` (gold) | Aster | $67.5M | $184.4M | $76k / $33k | 0.0 bp |
| `io:ANTH` (Anthropic pre-IPO) | HL/EntropyIO | $35.1M | $3.4M | — | — |
| `SPCXUSD1` | Aster | $18.1M | $24.1M | $52k / $76k | 0.7 bp |
| `NVDAUSDT` | Aster | $0.48M | **$0.02M** | **$613 bid** | 0.5 bp |
| `vntl:SPACEX`, `flx:NVDA` | HL/Ventuals, Felix | **$0** | $0 | **empty** | — |

### The skeptical read
1. **Spreads are tight (0.1–0.7 bp) but books are shallow** — $40–75k in the top five levels on NVDA. You can move a mega-cap equity perp 20+ bps with a $500k market order on a weekend. Tight spread ≠ depth.
2. **Volume/OI ratio is telling.** `xyz:GOLD`: $296M OI against $4.6M weekend turnover — positional carry, not an active market.
3. **Concentration is total.** TradeXYZ is >90% of HIP-3 OI. Six of ten HIP-3 DEXs have literally zero.
4. **The oracle is weakest exactly when you'd want the market.** During US session, `xyz` oracles pull real exchange feeds via TradeXYZ relayers updating ~every 3 seconds. **When TradFi closes, the oracle switches to a continuously-calculated EMA** of the perp's own price, reanchoring on reopen. Overnight and weekends, "the price of NVDA" is substantially Hyperliquid's own book talking to itself. Monday gap risk is structural.
5. **HLP does not backstop HIP-3.** `xyz` liquidity is entirely voluntary external market makers.
6. **Aster's single-stock perps are not a market.** Don't build UI for them.
7. **Neither venue gives equity ownership, dividends or voting.** Say this loudly to anyone arriving from equities.

**Bottom line: ~60% real.** Real for S&P/Nasdaq indices, gold, silver, crude and a top-10 mega-cap list in US hours. Marketing for the long tail, for weekends, and for every venue that isn't TradeXYZ.

---

## 5. NANSEN API

**Pricing:** ~$10 per 10,000 credits. Pro $49/mo annual or $69/mo includes 2,000 credits, restored to a 2,000 floor on the 1st UTC (not additive). Purchased credits expire 1 year out; soonest-expiring consumed first; included credits spent before purchased. Free plan burns 10x credits for identical calls.

**Rate limits:** Free 15 req/s, 300/min. Pro **75 req/s, 1,500/min**. Overrides: TGM perp trades 60/min, **profiler perp trades 5/min**, web search/fetch 15/min. 429s carry `X-Nansen-RateLimit-Scope` and `Retry-After`.

**What credits buy (per call):**
- **Smart Money (5 cr):** netflows, holdings, historical-holdings, `dex-trades`, jupiter-dcas, **`perp-trades`**
- **Profiler (1 cr base):** balances, transactions, **perp positions**, related-wallets, pnl-summary; counterparties 5; **perp-leaderboard 5**; address labels **100 common / 500 premium**
- **Token God Mode (1–5 cr):** screener, flow-intelligence, holders, **perp-positions**, flows, who-bought-sold, trades, transfers, leaderboards, token-information, indicators, ohlcv. **+150 cr if `premium_labels=true`**
- **Prediction Markets (1–5 cr):** screener, orderbook, ohlcv, trades, pnl, top-holders
- **Backtesting (5–25 cr):** historical dex-trades, who-bought-sold, token-flow-summary (5); historical top-holders, pnl-leaderboard, **token-quant-scores (25)**
- **Agent (200 / 750 cr):** fast / expert

**Latency and depth:** DEX-trades latency "often within seconds," but **only the trailing 24 hours of DEX trades is queryable**. Smart Money Historical Holdings is a **daily EOD snapshot** — processing starts 05:00 UTC, available ~07:00 UTC, **4-year rolling window**. 25+ chains. **No WebSocket/streaming** — poll-only REST.

**Usable as live signal:** smart-money DEX trades and netflows on 30–60s poll; TGM flow-intelligence and who-bought-sold for thesis confirmation; perp-positions / perp-leaderboard for crowding and squeeze setups; backtesting endpoints offline.

**Not usable:** anything sub-second or execution-triggering; historical holdings as intraday signal; premium labels in a hot loop (500 cr ≈ $0.50/call — a 200-wallet watchlist refreshed hourly is **$2,400/day**); profiler perp trades at **5 req/min**.

**Practical budget:** a 60s poll of one 5-credit endpoint is 7,200 credits/day ≈ **$7.20/day, ~$220/month**. Two or three loops plus cached labels lands **$500–900/month** — which dwarfs the $49 subscription.

---

## 6. WHAT THIS ACTUALLY EARNS AND WHAT IT ACTUALLY COSTS

### Revenue: linear in volume, no leverage, no tiers

Perp builder fee is `bps × notional`, charged **both sides**. At the market-clearing retail rate of **3 bps**:

| Daily routed perp notional (fills) | Monthly | @1 bp | @3 bps | @5 bps | @10 bps |
|---|---|---|---|---|---|
| $100k | $3M | $300 | $900 | $1,500 | $3,000 |
| $500k | $15M | $1,500 | $4,500 | $7,500 | $15,000 |
| $1M | $30M | $3,000 | $9,000 | $15,000 | $30,000 |
| $5M | $150M | $15,000 | $45,000 | $75,000 | $150,000 |
| $20M | $600M | $60,000 | $180,000 | $300,000 | $600,000 |
| $100M | $3B | $300,000 | $900,000 | $1.5M | $3M |

Calibration: Phantom needed **137k users** to reach $39.4B cumulative volume and $20.6M. Based needed 42,579 users for $44B. **A terminal with 100 active users doing $10k/day each is $1M/day = $9,000/month at 3 bps.** That is the realistic first-year ceiling with no distribution advantage.

### The fee stack the user actually pays (Hyperliquid, tier 0, no staking)
- Perp taker in: 4.5 bps + 3 bps builder = **7.5 bps**; out: same. **Round trip 15 bps of notional** = **1.5% of posted margin at 10x**, before funding and slippage.
- Funding: interest component **0.01%/8h = 10.95% APR** structurally paid by longs to shorts, hourly settlement, premium clamped ±0.05%, total capped at **4%/hour**.
- HIP-3 `xyz` runs ~2x core: **0.03% maker / 0.09% taker** (deployer/protocol split 50/50). A 3 bp builder fee makes an equity-perp round trip **~24 bps**. Growth mode can cut the venue side ≥90% per asset — check status before quoting.
- Spot: **0.070% taker / 0.040% maker** at tier 0, ~1.56x the perp taker.
- Discounts: HYPE staking 5/10/15/20/30/40% off at >10/100/1k/10k/100k/500k HYPE. Referral 4% off first $25M. Maker rebates −1/−2/−3 bps at >0.5%/1.5%/3.0% maker share.

**At small size the fee tier that matters is tier 0 and it stays tier 0.** Tier 1 needs $5M of 14-day volume **per trading account** — the user's volume, not yours. Your builder code does not aggregate users into a better tier.

### Infrastructure costs (monthly, realistic)

| Item | Cost | Note |
|---|---|---|
| Hyperliquid non-validating node | **$300–700** | 16 cores / 128 GB RAM / 500 GB SSD, Ubuntu 24.04, ports 4001–4002, **Tokyo** colocation. Bare metal. |
| Sentry peering | $0–1,500 | `[UNVERIFIED]` pricing. Optional at first. |
| Nansen credits | **$220–900** | See §5. |
| Aster / GMGN API | ~$76 + $100 | 100 ASTER + 100 USDC, trivial |
| App hosting, DB, WS fanout | $200–800 | Scales with concurrent users |
| LLM inference | $500–5,000+ | Likely your largest variable cost |
| TradFi reference prices (oracle sanity check) | $0–2,000 | `[UNVERIFIED]` |
| Legal (see §7) | $10k–50k one-time | Non-optional if you take US flow |
| **Run-rate floor** | **~$1,500–3,000/mo** | Excluding LLM, legal, salary |

### Break-even (revised 2026-09-20 — original figure was too conservative)

| Cost base | Monthly cost | Break-even at 3 bps, perps only | With spot at 4% of flow / 30 bps (see §8) |
|---|---|---|---|
| Infra floor only | $3,000 | $10M/mo fills = **$333k/day** | $8.6M/mo = **$287k/day** |
| + modest LLM ($2,000) | $5,000 | $16.7M/mo = **$555k/day** | $14.4M/mo = **$478k/day** |
| + one engineer ($15,000) | $20,000 | $66.7M/mo = **$2.2M/day** | $57M/mo = **$1.9M/day** |

My original "$500k–1M/day" was the middle row and should have been stated with its assumption. **Adding spot moves break-even down by ~14%, not by an order of magnitude** — see §8 for why the 10x cap differential does not translate into 10x revenue.

### The blunt conclusion
The gap between "infrastructure break-even" (~$300–550k/day) and "this is a business" (~$20M/day, $180k/mo) is a factor of forty, and that factor is entirely **distribution**. The builder-code mechanism is free money per unit of flow and offers **no mechanism whatsoever for generating flow**. Do not confuse having the pipe with having the water.

Secondary earner: the Hyperliquid **referral** program (10% of referred users' fees, first $1B of their volume) stacks on builder codes and costs nothing. At 4.5 bps taker that's 0.45 bps extra — a ~15% uplift on a 3 bp builder fee. Turn it on.

---

## 7. THE RISK SURFACE NOBODY MENTIONS

### Funding — the silent P&L leak
- Hyperliquid pays funding **hourly**: `premium + clamp(interest_rate − premium, −0.0005, 0.0005)`, interest component **0.01%/8h = 10.95% APR** structurally paid by longs to shorts. A flat long carried a month bleeds ~0.9% with no price move.
- **The rate is capped at 4% per hour** — not annualised. That is 96% of notional per day in a squeeze.
- Funding is charged on **oracle price × position size**, not mark.
- HIP-3 perps use a more reactive premium: `0.5 × (impact_bid + impact_ask) / oracle − 1`. In a thin equity book that responds violently to small orders.
- Live today: `xyz:CL` 0.0099%/hr ≈ 8.7% APR; Aster `CLUSD1` last funding 0.0267%.
- **Measured 180-day reality (2026-03-24 → 2026-09-20, from `fundingHistory`):** a perpetual short collected **+2.72% on BTC (5.52% annualized)**, **+3.01% ETH (6.11%)**, **+4.64% HYPE (9.41%)**, **+1.23% SOL (2.49%)**. Funding was **negative 20.2% of hours on BTC, 17.8% ETH, 10.8% HYPE, 32.1% SOL**. Worst single hours: −38% APR (BTC), −84.7% APR (SOL).

### Liquidation cascades and ADL
- **October 10, 2025:** $19B liquidated, 1.6M traders, perp OI down 43% ($217B → $123B) in a day. **Hyperliquid's OI fell 57%, $14B → $6B.** USDe depegged to $0.65 on Binance. dYdX down 8 hours; Lighter 4.5 hours; Binance API failures and deposit delays.
- **ADL means a winning position can be force-closed.** Hyperliquid ADL'd shorts during 10/10. Users will read this as the venue stealing their profits. Surface ADL rank in the UI.
- Stops trigger on **oracle mark price** — protects against wick-hunting but means a stop can fail to fire when your local book prints through it.

### Oracle manipulation — the demonstrated attack
- **JELLY, 2025-03-26:** attacker shorted $6–8M of the JELLYJELLY perp, then bought the thin spot token across DEXs, taking market cap $10M → $50M+ in under an hour. Forced liquidation pushed the position into HLP for a **$13.5M unrealised loss**. Fund pooling inside HLP prevented ADL from recognising the liquidator strategy's loss as critical.
- **HIP-3 multiplies this class of attack.** Each deployer runs their own oracle. Hyperliquid's docs warn that "most price indices are unsuitable as perp oracle sources" and that cross-margin assets must be excluded if they move >50% daily more than monthly. Slashing is the only deterrent — and **slashed stake is burned, not distributed to harmed users.**
- Weekend/overnight equity oracles are EMAs of the perp's own price. During those windows the oracle is reflexive by construction. Consider hard-disabling or size-capping equity perps outside cash-session hours.

### Venue insolvency, downtime, concentration
- Hyperliquid 2025-07: **37-minute frontend outage, ~27 minutes where orders could not be sent** (14:20–14:47 UTC), caused by a traffic spike. Positions could not be managed or liquidated. Hyperliquid refunded — voluntarily, with no obligation. Scheduled ~10-min upgrade 2026-09-05.
- **HLP does not backstop HIP-3.** If a TradeXYZ market blows up there is no protocol vault absorbing it — only ADL against profitable counterparties.
- **Aster's volume integrity is an open question.** DeFiLlama delisted Aster's perp data in Oct 2025 after 0xngmi showed near-1:1 correlation with Binance's perp volumes and no granular maker/taker data. Relisted; question unanswered.
- **Aster routes 99% of protocol fees into $ASTER buybacks.** A distribution policy, not a reserve policy.
- **You hold user agent keys.** Hyperliquid agent wallets cannot withdraw — blast radius is "an attacker can trade your users' accounts to zero," still catastrophic. Aster's `approveAgent` supports IP whitelisting and expiry; **use both.** Rotate HL agent wallets.

### Regulatory — the part that can end the project
- **The enforcement precedent is on point.** The CFTC fined **Falcon Labs $1.7M** for acting as an unregistered FCM by *facilitating* digital-asset derivatives trades for US customers — routing, not operating a venue. In the 2023 DeFi trifecta (Opyn, ZeroEx, Deridex) the CFTC held **blocking US IPs was "not sufficient."** Taking a fee on the order is what makes you an intermediary.
- **2026 clarity does not obviously help you.** May 2026: CFTC approved **KalshiEX's BTCPERP**, the first US-listed perpetual future, and determined perps on digital commodities with deep spot markets may be futures not swaps. The **CFM Letter** gave Coinbase Financial Markets — a *registered FCM* — no-action relief to offer offshore perps to US customers. The path for US flow to offshore perps runs through a registered FCM. You are not one.
- **SEC staff statement, 2026-04-13, "Covered User Interface Providers"** (Division of Trading and Markets): staff will not object to certain crypto front-ends operating without broker-dealer registration under §15(a). But it addresses **crypto asset securities**, not derivatives; conditions require no solicitation, user-customisable parameters, educational material, no routing discretion, no custody, no PFOF, and **"neutral compensation": fixed charges that are product-, route-, venue- and counterparty-agnostic.** A builder fee that varies by venue or market arguably fails that. Relief withdrawn **2031-04-13**. `[Secondary sources say it excludes derivatives outright; read the SEC text with counsel.]`
- **Practical posture:** assume charging a builder fee on US persons' perp orders is unregistered-intermediary exposure. IP geoblocking alone is documented as insufficient. **If you route your own capital only, this section largely evaporates. The regulatory risk arrives with the second user.** That is the actual product decision. FinCEN MSB and state money-transmitter analysis are separate if you ever touch fiat ramps.

---

## 8. HYPERLIQUID SPOT (extension — live data 2026-09-20 ~02:20 UTC)

### Verdict

**The 10x builder-fee cap differential is real and verified — 1% on spot vs 0.1% on perps — but it is worth far less than it looks, and it does not change the Hyperliquid-first call or make spot a day-one build.** Three things gut the arithmetic: spot builder fees accrue on the **sell side only** (perps charge both sides), Hyperliquid spot is only **4.03% of core perp volume** ($163M vs $4.04B on 2026-09-20), and no one will pay anything close to 100 bps when GMGN's 1%-per-side is already considered extortionate. At a realistic 30 bps sell-side spot fee and a venue-matching 4% spot mix, spot lifts revenue about **16%** and pulls break-even from ~$555k/day to ~$478k/day. That is a useful trim, not a new business. **The spot–perp basis trade, by contrast, is genuinely more interesting than the cross-venue basis I flagged earlier** — portfolio margin has been live since roughly December 2025 and does properly net a spot long against a perp short in one collateral pool, with borrow at 0.05% APY below 80% utilization. But the measured carry is only 2.5–9.4% annualized over the last 180 days and spot book depth caps you at low single-digit millions, so it is a way to earn yield on inventory you already hold, not a strategy you can scale. **Build spot in phase two; make exactly one day-one decision now — the `maxFeeRate` you ask for.**

### 8.1 Builder fee caps, spot vs perps — verified

| | Perps | Spot |
|---|---|---|
| **Protocol cap** | **0.1%** (100 tenths-of-bp) | **1.0%** (1000 tenths-of-bp) |
| **Sides charged** | **Both** | **Sell side only** |
| Denomination | tenths of a basis point (`f: 10` = 1 bp) | same |
| Approval action | `ApproveBuilderFee` | **same action, same approval** |
| Venue/asset-class field in approval | **none** | **none** |

Confirmed from the docs verbatim: *"Builder fees charged can be at most 0.1% on perps and 1% on spot."* and *"Builder codes do not apply to the buying side of spot trades but apply to both sides of perp trades."* and *"Builder codes only apply to fees that are collected in the quote or collateral asset."*

Confirmed from the SDK source (`hyperliquid/utils/signing.py:427`, `hyperliquid/exchange.py:659`): the EIP-712 struct `HyperliquidTransaction:ApproveBuilderFee` has exactly four fields — `hyperliquidChain`, `maxFeeRate` (string, e.g. `"0.001%"`), `builder` (address), `nonce` (uint64). **There is no asset-class, venue or DEX parameter.**

**Three consequences you must design for:**

1. **One approval covers everything.** A single `approveBuilderFee` from the user's main wallet authorises you across core perps, spot, and every HIP-3 DEX. You do not need to re-onboard a user to add spot later.
2. **But the approved `maxFeeRate` is a single ceiling.** If you onboard users at `"0.05%"` to look cheap on perps, you have permanently capped your spot fee at 5 bps too — one-twentieth of the spot cap. Raising it later costs **another main-wallet signature**, which in practice means a re-onboarding flow most users never complete. **This is the one decision spot forces on day one.** The protocol independently caps perps at 0.1% regardless of what was approved, so approving a higher rate does not expose the user to a higher perp fee — but they will see "approve up to X%" in their wallet, and a 1% number looks alarming. My recommendation: approve at **0.3%**, charge 2–3 bps on perps and 20–30 bps on spot, and say so plainly in the UI.
3. **Sell-side-only halves the naive spot advantage.** Per $1M of user round-trip activity: perps at 3 bps = $1M in + $1M out × 3 bps = **$600**. Spot at 30 bps = $1M buy (free) + $1M sell × 30 bps = **$3,000**. So spot pays 5x per round-trip dollar at 30 bps, 16.7x at the 100 bps cap — not 10x and not 33x.

`[UNVERIFIED]` — whether the spot 1% cap is enforced per-fill or per-order, and whether it interacts with the HIP-1 `deployerTradingFeeShare` (below). Test on testnet before pricing.

### 8.2 Recomputed break-even for mixed perps + spot flow

Assume your flow mixes in the same proportion as the venue: **96% perps / 4% spot**, perps at 3 bps both sides, spot at 30 bps sell-side only (so half the spot fill volume is billable).

On $30M/month of total routed fills:
- Perps: $28.8M × 3 bps = **$8,640**
- Spot: $1.2M fills → ~$600k billable sells × 30 bps = **$1,800**
- **Total $10,440** vs $9,000 perps-only → **+16%**

| Cost base | Monthly cost | Perps-only break-even | Mixed break-even | Δ |
|---|---|---|---|---|
| Infra floor | $3,000 | $333k/day | **$287k/day** | −14% |
| + modest LLM | $5,000 | $555k/day | **$478k/day** | −14% |
| + one engineer | $20,000 | $2.2M/day | **$1.9M/day** | −14% |

At the full 1% spot cap the mix would contribute $6,000 on the same flow (+63% total revenue, break-even → ~$340k/day) — but charging 100 bps puts you level with GMGN, which is the most-criticised fee in the space.

**Verdict on the caps question: yes, they differ by 10x; no, it does not move break-even by 10x. Plan on −14%.**

### 8.3 What is actually liquid on Hyperliquid spot

**Total spot 24h volume: $162.74M across 868 tradeable pairs; only 364 had any volume at all.** (Note: `spotMetaAndAssetCtxs` returns 868 contexts against a 329-entry `universe` — you **must** join on the `coin` field, not by array position, or every number you compute will be wrong. I hit this and corrected it.)

| Pair | Coin ID | 24h Vol | Spread | ±10bp bid | ±10bp ask |
|---|---|---|---|---|---|
| **HYPE/USDC** | `@107` | **$64.87M** | 0.11 bp | $151,412 | $88,692 |
| **UBTC/USDC** | `@142` | $35.32M | 0.12 bp | $654,800 | $568,647 |
| **UETH/USDC** | `@151` | $18.96M | 0.38 bp | $287,406 | $374,957 |
| **UZEC/USDC** | `@272` | $15.73M | 0.68 bp | $4,046 | $59,724 |
| DRV/USDC | `@700` | $7.07M | — | — | — |
| **USOL/USDC** | `@156` | $5.13M | 0.91 bp | $141,907 | $130,954 |
| XMR1/USDC | `@260` | $2.90M | — | — | — |
| USDT0/USDC | `@166` | $2.09M | — | — | — |
| UPUMP/USDC | `@188` | $1.94M | — | — | — |
| **PURR/USDC** | `PURR/USDC` | $1.77M | **29.58 bp** | **$0** | **$0** |

**Concentration is extreme:** top 1 pair = 39.9% of all spot volume, top 3 = 73.2%, top 5 = **87.2%**, top 10 = 95.7%, top 50 = 99.3%.

**Real books:** HYPE/USDC, UBTC/USDC, UETH/USDC, USOL/USDC — sub-1bp spreads and $100k–650k within 10 bp. UZEC has a real ask side but a nearly empty bid ($4k within 10 bp) — one-sided and dangerous.

**Decoration:** everything else, including **PURR**, the mascot token everyone names. PURR/USDC quotes **29.6 bp wide with literally nothing inside 10 bp** despite $1.77M of daily volume — that volume is crossing a wide spread, which is exactly what a HIP-2 book does (§8.5). 504 of 868 pairs have zero volume.

**Spot vs perp on the same asset (24h, 2026-09-20):**

| Asset | Spot | Perp | Spot as % of perp |
|---|---|---|---|
| HYPE | $64.99M | $339.34M | **19.2%** |
| BTC | $35.36M | $1,158.31M | 3.1% |
| ETH | $19.09M | $897.27M | 2.1% |
| ZEC | $15.73M | $404.39M | 3.9% |
| SOL | $5.14M | $150.65M | 3.4% |
| PUMP | $1.94M | $35.64M | 5.4% |
| ENA | $0.94M | $78.13M | 1.2% |
| PURR | $1.77M | $1.84M | 96.2% |
| FARTCOIN | $0.13M | $14.72M | 0.9% |
| **All spot vs all core perp** | **$163.05M** | **$4.04B** | **4.03%** |

**HYPE is the only asset where spot is a meaningful fraction of perp flow (19%)** — unsurprising, since people actually want to hold HYPE for fee discounts and staking. For BTC/ETH/SOL, spot is 2–3% of the perp book: Hyperliquid spot is not where anyone goes to buy crypto. It exists to (a) hold HYPE, (b) hold Unit-bridged assets as portfolio-margin collateral, (c) trade HIP-1 launches.

### 8.4 The spot–perp basis trade

**Does the margin system actually net the legs? Yes — this is the key finding and it is better than I assumed in the perps-only version.**

Hyperliquid has three account-abstraction modes:
- **Standard/manual** — separate perp and spot balances, cross-margin applied per DEX independently. **Required for builder-code addresses to accrue fees.**
- **Unified account** (recommended default) — one balance per asset collateralises cross-margin perp positions *and* serves as spot balance. USDC backs core perps, HIP-3 perps and USDC-quoted spot simultaneously; no spot→perp transfer.
- **Portfolio margin** (most capital-efficient) — consolidates eligible assets (HYPE, BTC, USDC, USDT) into one collateral pool. Live since roughly December 2025; still beta with raised limits as of 2026.

Portfolio margin explicitly documents the carry trade: hold 1 BTC spot, short 1 BTC perp, and **spot and perp PnL offset each other**, with the system auto-borrowing USDC against the spot BTC up to its LTV to maintain the hedge. **There is no trading cost to rebalance within wide price ranges.** So the answer to "are they margined separately or netted" is: **netted, if you opt into unified or portfolio margin.**

**Terms:**
- Eligibility: **>$5M weighted volume OR account value >$10k**, and account value must stay **under $25M**.
- Collateral: HYPE and BTC at **LTV 0.5** (as of July 2026); USDC/USDT also eligible.
- Liquidation threshold on spot collateral: `0.5 + 0.5 × LTV`, so BTC = 0.75, and 0.825 at LTV 0.65.
- Stablecoin borrow rate: `0.05 + 4.75 × max(0, utilization − 0.8)` APY, continuously compounded. **Below 80% utilization the borrow cost is 0.05% APY — effectively free.**
- Global and per-user borrow caps (e.g. 50M USDC per user). Liquidation triggers at portfolio margin ratio >0.95, and the **liquidation sequence is not deterministic** — the backstop liquidator may act unpredictably depending on oracle updates.
- **Unified/portfolio users face a 50,000 daily action limit.**

**Is the basis wide enough often enough? Honestly: marginally, and only on some assets.**

Live basis right now (spot mid vs perp mid, 2026-09-20 ~02:20 UTC): HYPE **+4.4 bp**, UBTC **+6.0 bp**, UETH **+4.6 bp**, USOL **+5.5 bp**, UZEC **+7.5 bp**. Tiny — these are not dislocations, they are the funding rate discounted into the price.

The return is the funding, not the basis. **Measured from `fundingHistory` over 4,320 hours (2026-03-24 → 2026-09-20), what a perp short actually collected:**

| Asset | Collected over 180d | Annualized | % hours negative | Worst hour |
|---|---|---|---|---|
| **HYPE** | **+4.64%** | **+9.41%** | 10.8% | −83.0% APR |
| ETH | +3.01% | +6.11% | 17.8% | −40.6% APR |
| BTC | +2.72% | +5.52% | 20.2% | −38.4% APR |
| SOL | +1.23% | +2.49% | 32.1% | −84.7% APR |

**Costs against that:** round-trip all-taker = spot 0.070% × 2 + perp 0.045% × 2 = **0.23%**. All-maker = 0.040% × 2 + 0.015% × 2 = **0.11%**. Plus 0.05% APY borrow if you lever the collateral.

**So:**
- On BTC at 5.52% APR, an all-taker round trip costs 0.23% = **15 days of carry just to break even on fees**. A 3-month hold nets ~1.15% gross.
- On HYPE at 9.41% APR, fees are ~9 days of carry; a 3-month hold nets ~2.1%.
- On SOL at 2.49% APR with funding negative a third of the time, an all-taker round trip is **34 days of carry** and the trade is not worth doing.

**Size ceiling:** the binding constraint is the spot leg. UBTC has $655k bid / $569k ask within 10 bp; HYPE has $151k / $89k. You can put on perhaps **$500k–1M in BTC** and **$150k in HYPE** without moving the spot side materially, and total Hyperliquid spot turnover is $163M/day. **You cannot run $50M of carry here.** Exiting in a stressed market is worse — the spot book is the thin leg and it is the leg you must cross.

**Is anyone doing it at size?** Hyperliquid built portfolio margin explicitly for this and markets the carry trade in its own docs; the beta limit sits at $25M account value, which tells you the intended participant size. `[UNVERIFIED]` — I found no public data identifying specific desks running HL spot–perp carry at size, and the $25M account cap plus $163M/day spot turnover suggests nobody can be running it very large.

**Verdict:** the trade is **real, genuinely capital-efficient thanks to portfolio margin, and structurally cleaner than the cross-venue HIP-3 basis I flagged earlier** — one margin system, one liquidation engine, no transfer latency, no second counterparty. But at 2.5–9.4% APR with 11–32% of hours paying negative, it is **barely above risk-free for the operational and liquidation risk**, and the spot book caps it at low single-digit millions. Do it on **HYPE** (best carry, fewest negative hours, and you likely want HYPE anyway for the fee discount), not SOL. Treat it as **yield on inventory you already hold, not as a strategy**.

**Operational gotcha nobody mentions:** builder-code addresses **must be in standard mode** to accrue builder fees, and standard mode is precisely the mode that does *not* net spot against perps. **Your fee-collection address cannot be your carry-book address.** You need two, and the accounting between them is yours to build.

### 8.5 HIP-1 / HIP-2 — surface or trap?

**HIP-1 (native token standard):**
- Deployment gas via a **31-hour Dutch auction**, price decaying linearly to a **500 HYPE** floor; the next auction opens at **double the last clearing price** (or 500 HYPE if the previous failed).
- Token names are **max 6 characters with no protocol-level uniqueness**. The on-chain ticker is the identifier; front-ends may display whatever they like.
- `szDecimals + 5 <= weiDecimals`. Genesis balances configurable, including proportional distribution to existing holders.
- **Base-token deployers receive fees collected in their token, 100% by default**, adjustable downward but never upward. Uncollected fees are burned. Quote-token deployer fees go to the Assistance Fund.
- Live confirmation from `spotMeta`: of 502 tokens, **290 carry `deployerTradingFeeShare: 1.0`** and 203 carry `0.0`. Every top pair except HYPE, USDT0 and PURR shows 1.0 — UBTC, UETH, UZEC, USOL, UPUMP are all 100% deployer-fee-share (the Unit bridge team).
- **Stuck deployments cannot be refunded** — the docs explicitly tell you to rehearse on testnet.

**HIP-2 (Hyperliquidity):** a consensus-level automated market maker for HIP-1 tokens. Price levels spaced `px_i = round(px_{i-1} × 1.003)`, i.e. **0.3% apart**, refreshed **every 3 seconds**. It "guarantees a 0.3% spread every 3 seconds." The deployer seeds USDC for the bid side and token inventory for the ask side.

**Verdict: watch as a signal surface, treat as a trap as a trading surface.**
- A HIP-2 book will always quote you **30 bps wide**. That is worse than a Solana DEX on a mid-cap memecoin and far worse than the sub-1bp top-5 spot pairs. PURR — the canonical HIP-2 token — quotes 29.6 bp with nothing inside 10 bp. That is the mechanism working as designed, not a malfunction.
- **Non-unique 6-character tickers are a live impersonation risk.** My first pass at the spot data mis-joined arrays and produced a table showing "WOW/USDC" trading at exactly HYPE's price with $66M of volume. That was my bug — but it is precisely the failure a user experiences if your UI trusts token names. **Your terminal must key on `tokenId` / pair index (`@107`), and display them, not just the name.** This is not optional.
- 504 of 868 pairs have zero volume; the top 5 are 87% of turnover. New HIP-1 listings are overwhelmingly noise.
- The one genuinely interesting signal: the **HIP-1 Dutch auction clearing price** is a clean, public, on-chain measure of how much people will pay to list a token on Hyperliquid — a decent proxy for speculative appetite, and cheap to poll. Worth a chart; not worth a trading surface.

### 8.6 Does spot change the verdict or the build order?

**Verdict: unchanged.** Hyperliquid-first. If anything spot reinforces it — Aster has no comparable spot builder program, and Hyperliquid's portfolio margin (spot as perp collateral) is a real capability neither Aster nor GMGN offers.

**Build order: spot is phase two, with one day-one carve-out.**

| Phase | Work | Why |
|---|---|---|
| **Day one** | Set the `maxFeeRate` in `approveBuilderFee` to **0.3%**, not 0.05% | Single shared approval; raising it later needs another main-wallet signature most users won't complete. This is the only spot decision that cannot wait. |
| **Day one** | Build the venue→asset-index resolver properly (core perps, spot, HIP-3 at 110000+) | You need it for HIP-3 anyway; spot slots in free later. |
| **Day one** | Key all token references on `tokenId` / pair index, never on name | Non-unique 6-char tickers. Cheap now, a security incident later. |
| **Phase two** | Spot order placement, sell-side fee logic, spot balance display | 4% of volume; sell-side-only revenue; not worth delaying perps launch. |
| **Phase two** | Account-mode awareness (standard vs unified vs portfolio margin) | Affects collateral display and liquidation math. Note the **50,000 daily action limit** on unified/PM accounts. |
| **Phase two** | Separate standard-mode fee-collection address from any carry-book address | Builder codes require standard mode; carry requires portfolio margin. |
| **Never** | HIP-2 long-tail spot as a headline trading surface | 30 bp guaranteed spread; 504 of 868 pairs dead. |

The honest framing: spot is a **~16% revenue uplift and a capital-efficiency unlock for your own book**, not a second business. Ship perps, then add it.

---

## Sources

**Hyperliquid — docs**
- [Builder codes](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes)
- [Fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)
- [Funding](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding)
- [Rate limits and user limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits)
- [HIP-1: Native token standard](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-1-native-token-standard)
- [HIP-2: Hyperliquidity](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-2-hyperliquidity)
- [HIP-3: Builder-deployed perpetuals](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals)
- [Portfolio margin](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/portfolio-margin)
- [Account abstraction modes](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/account-abstraction-modes)
- [Referrals](https://hyperliquid.gitbook.io/hyperliquid-docs/referrals)
- [Order types](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/order-types)
- [Foundation non-validating node](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/nodes/foundation-non-validating-node)
- [hyperliquid-python-sdk](https://github.com/hyperliquid-dex/hyperliquid-python-sdk) — `signing.py:427` `sign_approve_builder_fee`, `exchange.py:659` `approve_builder_fee`, `types.py:184` `BuilderInfo`
- [Portfolio margin product update, Dec 2025](https://hyperliquid.xyz/article/portfolio-margin)

**Hyperliquid — live API (pulled 2026-09-20)**
- `POST https://api.hyperliquid.xyz/info` — `perpDexs`, `metaAndAssetCtxs`, `spotMeta`, `spotMetaAndAssetCtxs`, `l2Book`, `fundingHistory`

**Builder economics**
- [Top Hyperliquid Builders — CoinGecko Research](https://www.coingecko.com/research/publications/top-hyperliquid-builders) (snapshot 2026-05-25)
- [Hyperliquid Builder Codes: Earning Millions — Dwellir](https://www.dwellir.com/blog/hyperliquid-builder-codes)
- [Hyperliquid Builder Codes — Blockworks Analytics](https://blockworks.com/analytics/hyperliquid/hyperliquid-builder-codes/hyperliquid-builder-codes-trading-builder-fees)

**HIP-3 / equity perps**
- [HIP-3 Data & Analytics — Loris Tools](https://loris.tools/hip3) (2026-09-19: $61.39B 30d volume, $1.88B OI, 107,577 traders, $3.62M fees)
- [What Is HIP-3? — Nansen](https://nansen.ai/post/what-is-hip-3-hyperliquid)
- [Equity Perps on Hyperliquid via trade.xyz — Hyperliquid Guide](https://hyperliquidguide.com/guides/trading/equity-perps-guide)
- [trade[XYZ] Docs — Perp Mechanics](https://docs.trade.xyz/perp-mechanics/overview)
- [Hyperliquid's HIP-3 & HIP-4 — CoinGecko](https://www.coingecko.com/learn/hyperliquid-hip3-hip4-tokenized-stocks-and-prediction-markets)
- [The Transformational Potential of HIP-3 — FalconX](https://www.falconx.io/newsroom/the-transformational-potential-of-hyperliquids-hip-3)

**Hyperliquid unified accounts / portfolio margin (secondary)**
- [Hyperliquid Unified Account Guide — Hyperliquid Guide](https://hyperliquidguide.com/guides/trading/unified-accounts-guide)
- [Hyperliquid Portfolio Margin Explained — Buildix](https://www.buildix.trade/blog/hyperliquid-portfolio-margin-explained-2026)
- [Hyperliquid's next upgrade… — CoinDesk, 2026-03-10](https://www.coindesk.com/markets/2026/03/10/hyperliquid-s-new-upgrade-to-let-traders-take-bigger-bets-with-less-capital)
- [HyperBFT, Sub-Accounts, and Spot vs Perp — Chainstack](https://chainstack.com/hyperliquid-hyperbft-sub-accounts-spot-perp-accounting/)

**Aster**
- [Aster Code](https://docs.asterdex.com/program-and-rewards/aster-code)
- [Aster Code integration flow](https://asterdex.github.io/aster-api-website/asterCode/integration-flow/)
- [Perpetual Fees](https://docs.asterdex.com/trading/perpetuals/fees-and-specs/fees)
- [Hidden Order & Hidden Position](https://docs.asterdex.com/trading/perpetuals/order-types/hidden-order-and-hidden-position)
- [API Documentation](https://docs.asterdex.com/for-developers/aster-api/api-documentation)
- [Referral Program](https://docs.asterdex.com/program-and-rewards/referral-program)
- [Aster Launches 24/7 Stock Perpetual Contracts — CryptoSlate](https://cryptoslate.com/press-releases/aster-launches-24-7-stock-perpetual-contracts-trading-with-exposure-to-u-s-equities/)
- [DeFiLlama Delists Aster Over Wash Trading Suspicions — CryptoPotato](https://cryptopotato.com/defillama-delists-asters-perpetual-futures-data-following-wash-trading-suspicions/)
- [Aster Back on DeFiLlama, Fallout Unresolved — CCN](https://www.ccn.com/news/crypto/aster-defillama-washtrading-fallout/)
- Live API: `https://fapi.asterdex.com/fapi/v1/` — `exchangeInfo`, `ticker/24hr`, `depth`, `openInterest`, `premiumIndex`

**GMGN**
- [Integrate GMGN Solana Trading API](https://docs.gmgn.ai/index/cooperation-api-integrate-gmgn-solana-trading-api)
- [Integrate GMGN price chart](https://docs.gmgn.ai/index/cooperation-api-integrate-gmgn-price-chart)
- [Referral Link](https://docs.gmgn.ai/index/referral-link)
- [Refer friends to earn 30% rebates](https://docs.gmgn.ai/index/cooperation-referral-refer-friends-to-earn-rebate-30-rebates-easily-earn-over-usd8000-monthly)
- [GMGN Fees & Review 2026 — uwuu.ai](https://uwuu.ai/blog/gmgn-review)

**Nansen**
- [Credits & Pricing Guide](https://docs.nansen.ai/getting-started/credits)
- [Rate Limits](https://docs.nansen.ai/getting-started/rate-limits)
- [Endpoints Overview](https://docs.nansen.ai/api/overview)
- [Data Methodology & Technical Reference](https://docs.nansen.ai/guides/data-methodology-and-technical-reference)
- [DEX Trades](https://docs.nansen.ai/api/smart-money/dex-trades)

**Risk & regulatory**
- [What Is October 10th? — CoinGecko](https://www.coingecko.com/learn/october-10-crypto-crash-explained)
- [Inside Crypto's $19B Liquidation Event — CoinDesk](https://www.coindesk.com/research/market-spotlight-the-19-billion-liquidation-that-shook-crypto)
- [Hyperliquid and the JELLY attack — OAK Research](https://oakresearch.io/en/analyses/investigations/hyperliquid-jelly-attack-context-vulnerability-team-solution)
- [Hyperliquid API outage caused by traffic spike — The Block](https://www.theblock.co/post/364798/hyperliquid-outage-api-traffic-spike-not-hack-vulnerability-exploit)
- [CFTC Brings Digital Asset Perpetual Contracts Onshore — Dechert](https://www.dechert.com/knowledge/onpoint/2026/6/cftc-takes-historic-steps-to-bring-digital-asset-perpetual-contr.html)
- [Opening the Door to "Perps" — Proskauer](https://www.proskauer.com/alert/opening-the-door-to-perps-the-cftc-approves-us-listed-perpetual-futures)
- [SEC Staff Statement: Broker-Dealer Registration of Certain User Interfaces (2026-04-13)](https://www.sec.gov/newsroom/speeches-statements/staff-statement-regarding-broker-dealer-registration-certain-user-interfaces-utilized-prepare-staff-statement-regarding-broker-dealer-registration-certain-user-interfaces-utilized)
- [SEC Staff Issues Broker-Dealer Guidance — WilmerHale](https://www.wilmerhale.com/en/insights/client-alerts/20260417-sec-staff-issues-broker-dealer-registration-guidance-for-certain-user-interfaces)
- [CFTC Orders Against Three DeFi Protocols — CFTC 8774-23](https://www.cftc.gov/PressRoom/PressReleases/8774-23)
- [CFTC's Message to DeFi Platforms — Morgan Lewis](https://www.morganlewis.com/pubs/2023/09/cftcs-message-to-defi-platforms-register-with-the-cftc-or-leave-the-us-market-or-risk-enforcement)

**Adjacent**
- [FOMO API](https://fomoapi.io/)
- [Robinhood Chain goes live on mainnet — The Block, 2026-07-01](https://www.theblock.co/news/business/2026-07-01-robinhood-chain-goes-live-mainnet-alongside-24-7-tokenized-stocks-lighter-perps-planned-crypto-agentic-trading-406918)
- [Robinhood Chain mainnet — Arbitrum Blog](https://blog.arbitrum.io/robinhood-chain-mainnet/)

---

## Unverified items requiring confirmation before design

1. Aster Code fee **claim/withdrawal mechanism** and settlement asset — documented nowhere.
2. Whether Hyperliquid builder codes are **fully supported on HIP-3 sub-DEX orders**. The `builder` field is on the order action and `basic_order_with_builder_deployed_dex.py` exists, but no doc confirms builder fees accrue on `xyz:` fills. **Test on testnet.**
3. Whether the **spot 1% builder cap is enforced per-fill or per-order**, and how it interacts with HIP-1 `deployerTradingFeeShare`.
4. GMGN referral tier thresholds and whether **API/partner integrations** qualify for the 10–30% share.
5. Whether GMGN's ETH/Base/BSC trading endpoints are generally available (docs say Solana only).
6. Exact scope of the SEC CUI statement re: derivatives and fee-taking interfaces — read the primary SEC text with counsel.
7. QuickNode-style Hyperliquid sentry peering pricing.
8. Per-DEX HIP-3 fee rates and deployer fee-share settings (loris.tools has a per-DEX table I could not extract).
9. Whether any desk runs Hyperliquid spot–perp carry at meaningful size — no public data found.
