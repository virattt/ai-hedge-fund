# Hyperliquid spot: builder-fee channel and tradeable surface -- 2026-09-19

*Agent report. Numbers marked CONFIRMED were pulled live by the agent from Hyperliquid's docs and public `info` endpoint on the date above; they have not been re-verified by the orchestrating session.*

## VERDICT
Spot adds a small, real trading surface (5 liquid pairs, ~$164M/day total spot volume, 77% concentrated in HYPE/UBTC/UETH/USOL/PURR) sitting on top of ~325 dead/decorative listings, plus a builder-fee channel with a *nominally* higher cap (1% vs 0.1%) but no evidence the market pays anywhere near that cap, and volume that is only 2-19% of the matching perp. It does NOT change the day-one build order: perps stays primary, spot is not worth a day-one adapter. Worth a backlog line: Portfolio Margin (spot collateralises a perp short -- the carry trade), real and documented but gated to $10k-$25M account value.

**Data-quality warning (load-bearing):** the public API's token `name` field is not a trustworthy identifier. The real, live-traded HYPE/USDC pair's underlying registry entry is named `"WOW"`; a separate entry actually named `"HYPE"` (fullName "Hyperliquid") is a near-dead decoy with ~$24 of 24h volume. Real pairs were identified by cross-checking price against the perp oracle and supply against known tokenomics, then confirmed against app.hyperliquid.xyz and CoinGecko. Tooling that resolves spot pairs by name alone will silently route to the wrong book.

## CONFIRMED

### 1. Builder fee caps -- spot vs perps

| | Perps | Spot |
|---|---|---|
| Max builder fee | 0.1% | 1% |
| Charged on | both sides | **sell side only** |
| Approval | `approveBuilderFee`, signed by main wallet (not agent wallet) | same mechanism; docs draw no distinction |
| Other | builder needs >=100 USDC perps account value; max 10 active approvals/user; fee unit = tenths of a bp | same |

Source: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes

Base exchange fees: perps taker 0.045% / maker 0.015%; spot taker 0.070% / maker 0.040%. Source: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees

Break-even: spot's cap is one-sided vs perps' two-sided, so the per-round-trip ceiling is 1% vs 0.2% -- 5x, not 10x. No data was found on what spot builder fees actually clear at. With matched-asset spot volume at 2-19% of perp volume, spot does not carry the break-even case; perps volume still has to. Any specific mixed-flow break-even figure is unverified until real spot builder rates are found.

### 2. Real spot liquidity vs decoration (live pull)

| Pair (verified real) | 24h spot notional | Same-asset 24h perp | Spot % of perp |
|---|---|---|---|
| HYPE/USDC | $65.3M | $340.8M | 19.2% |
| UBTC/USDC | $35.6M | $1,163.6M | 3.1% |
| UETH/USDC | $19.2M | $900.5M | 2.1% |
| USOL/USDC | $5.1M | $151.5M | 3.4% |
| PURR/USDC | $1.77M | n/a | -- |

- All ~330 listed spot pairs: $163.9M/24h. These five = $127.1M = 77.5%.
- Top-of-book depth: HYPE ~$14-15k per level; UBTC ~$8k-50k; UETH ~$2.6k-36k; USOL wide variance. Real quoted books for retail/mid-size clips.
- Decoration: USDT0/USDC $125.9k/24h, FEUSD/USDC $79.5k, XAUT0/USDC $44.4k, USDH-quoted pairs near zero.

### 3. Same-venue spot-perp margin

- Default accounts do NOT cross-margin spot against perps. Source: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margining
- **Portfolio Margin** unifies them and documents the carry trade explicitly (hold 1 BTC spot, short 1 BTC perp at 10x). Eligible collateral: USDC, USDT, HYPE, BTC (not ETH/SOL as of this check). Liquidation at portfolio margin ratio > 0.95. Source: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/portfolio-margin
- Gated: >$5M weighted volume OR account value >$10k to enable; must stay <$25M. Per-asset borrow caps are small (1M USDT, 50M USDC, 1M HYPE).

### 4. HIP-1 / HIP-2

- HIP-1: permissionless listing via a 31-hour Dutch auction for deploy gas (floor 500 HYPE). Token names max 6 characters, **no uniqueness constraint**.
- HIP-2 (Hyperliquidity): optional, deployer-opt-in, on-chain market-making; 0.3% spread quoted every 3 seconds on the native book.
- The no-uniqueness rule was hit empirically (the `HYPE` decoy above). New spot listings are a trap to monitor, not a surface to trade by ticker: anything watching new listings needs a price/supply verification step.

## UNVERIFIED / OPEN

1. Market-clearing spot builder fee rates -- none found.
2. Realised spot-perp basis/funding spread and who runs the PM carry at size -- no primary data found.
3. What is left after fees for a non-colocated carry participant -- depends on 2.
4. Legitimacy of mid-volume pairs: `QQQ/USDC` ($15.8M/24h), `GLD/USDC` ($2.87M), `RUB/USDC` ($2.09M), `WOULD/USDC` ($1.95M), `REI/USDC` ($939k). Could be genuine tokenised exposure or mimicry decoys; the price/supply cross-check was not run on them.
5. The remaining ~320 pairs (~$13M combined) were not individually verified.
6. What fraction of listings actually use HIP-2.

## Build-order recommendation

Unchanged: Hyperliquid perps first, Aster for gold/crude, GMGN sidecar. If a spot leg is built later, scope it to the five verified pairs, identify them by price/supply cross-check and the universe `index`, never by `name`. Portfolio Margin carry is a later-phase item, naturally sequenced after a working perps adapter.

## Sources
Hyperliquid docs (builder codes, fees, HIP-1, HIP-2, margining, portfolio margin + FAQ, spot info endpoint) -- fetched 2026-09-19. Live `POST https://api.hyperliquid.xyz/info` pulls: `spotMetaAndAssetCtxs`, `metaAndAssetCtxs`, `l2Book` for the five pairs. Cross-checks: app.hyperliquid.xyz, CoinGecko Hyperliquid spot page (~$64M HYPE/USDC 24h vs $65.3M from the API).
