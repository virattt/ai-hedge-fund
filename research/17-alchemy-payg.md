# Alchemy Pay-As-You-Go: pricing and fit for five workloads -- 2026-09-19

*Agent report, condensed. "Confirmed" means the agent fetched the primary Alchemy page on the date above; nothing here has been re-verified by the orchestrating session. The fetch tool summarises pages, so figures are cross-checked numbers, not verbatim quotes.*

## VERDICT

PAYG is the right tier and covers all five workloads for an estimated **~$15-100/month total**. The range is driven almost entirely by one unmeasured number: bytes per Solana gRPC transaction update. The dominant decision is the Solana fee-payer firehose: **Yellowstone-compatible gRPC, filtered server-side to the fee-payer account, at $75 per TERABYTE** is roughly 14-300x cheaper than polling `getTransaction` (~$630/month at ~1M calls/day). gRPC cannot deep-backfill (replay covers only the last ~6,000 slots, under ~70 minutes), so pair it with occasional bounded `getSignaturesForAddress` + `getTransaction` backfill, never continuous polling.

## Confirmed

### PAYG mechanics
- **$0.525 per 1M compute units (CU), flat, no volume breaks.** Replaced a tiered structure ($0.45/M to 300M, $0.40/M above) in a docs change merged 2026-09-11 (alchemy.com/pricing, docs/reference/pricing-plans, PAYG FAQ, cross-checked against github.com/alchemyplatform/docs PR #1615).
- Free tier: 30M CU/month, ~300 CU/s, 5 apps, 5 webhooks.
- PAYG included throughput: 10,000 CU/s (~300 RPS), 30 apps, 100 webhooks. Extra throughput: +5,000 CU/s = $160/month; self-serve caps at 30,000 CU/s.
- Enterprise: "1,000 RPS+", custom pricing; Alchemy publishes no dollar floor.
- **Token, NFT, Transfers, Portfolio, Prices, Smart WebSockets and full archive data are included on ALL tiers including Free.** PAYG-minimum: Debug API, Trace API, gas-optimised transactions. What PAYG actually buys is uncapped CU volume and higher throughput/app/webhook ceilings.
- Spending controls: a **Usage Limit** (CU or $) in Billing settings caps/stops service with no overage billed. A separate "Max On-Demand Spend Limit" plus threshold alerts is described as applying only when Auto-scale is enabled (single source).
- Overage: exceeding CU/s -> HTTP 429; exceeding a configured cap -> access throttled/off until next cycle. Not a surprise bill (single source).

### CU cost table (docs/reference/compute-unit-costs)
- Solana: `getTransaction` 40, `getSignaturesForAddress` 40, `getBlock` 40, `getAccountInfo` 10, `getBalance` 10.
- EVM: `eth_getLogs` 60, `eth_call` 26, `eth_blockNumber` 10, `eth_getBlockByNumber` 20.
- NFT API: `getNFTMetadata`/`getFloorPrice` 80, `getContractMetadata` 160, `getNFTsForOwner`/`getOwnersForContract` 480.
- Transfers API: `alchemy_getAssetTransfers` 120. Token API: `getTokenMetadata` 10, `getTokenBalances`/`getTokenAllowance` 20.
- **WebSockets/webhooks are billed by bytes from the same CU pool: 0.04 CU per byte** (~40 CU for a ~1,000-byte event). Distinct from gRPC's flat $/TB.

### Solana gRPC
- **$75 per terabyte ($0.075/GB), usage-billed, no monthly minimum, no plan prerequisite.** Server-side filters by account, program, owner or signature; account-data slicing by offset (alchemy.com/solana-grpc).
- Reconnect replay limited to the last 6,000 slots via `from_slot` -- gap recovery only, not history.
- Solana Account Archive: historical `getAccountInfo` back to ~July 2025, account state only -- not a substitute for transaction capture.

### Chain coverage
- Base, BNB Smart Chain, Ethereum, Monad and **Robinhood Chain** are all live with RPC + WebSocket endpoints.
- Robinhood Chain: full stack (Bundler, Gas Manager, Token, Transfers, Debug, NFT APIs, webhooks, mainnet + testnet) -- via search summary.
- Monad: RPC + WebSocket live; enhanced Data APIs on Monad not confirmed.

### Hyperliquid
- HyperEVM: RPC + WebSocket live, archive on all plans, standard EVM CU pricing.
- HyperCore (order book, fills, funding): only a paginated Info-endpoint proxy (500-element page cap) is live on Alchemy; streaming/order-book/fills data and validator infrastructure are stated as "coming soon".
- Hyperliquid's own Info endpoint + WebSocket feed is free.

### Special APIs
- Token API: balances, metadata, allowances only -- no trade/swap history.
- Prices API: current + historical prices, by symbol (top 1,000+) or by address (10K+ tokens, DEX-only), 15+ chains.
- Portfolio API: multi-chain wallet balances, NFTs and transactions in one call -- closest match to per-wallet history.
- Transfers API: paginated address-level transfer history, EVM.
- **No product named "Trades API" was found.** Closest real products: Prices + Portfolio + Transfers.

## Workload economics (agent arithmetic)

| # | Workload | Product | Est. monthly cost |
|---|---|---|---|
| 1 | Solana fee-payer firehose (~1M tx/day, ~12 tx/s) | gRPC filtered to the account + bounded backfill for gaps | 1-20 KB/tx (UNVERIFIED) x 1M/day = 30-600 GB/mo x $75/TB = **~$2-45**. Continuous polling instead: 1M x 40 CU/day = 1.2B CU/mo x $0.525/M = **$630**. 480 CU/s is well under the included 10,000 CU/s either way. |
| 2 | ~1,000 known wallets, few thousand calls/day | standard RPC polling | 5,000 x ~40 CU/day = 6M CU/mo = **~$3** (fits the Free tier) |
| 3 | Base/BNB/Ethereum/Monad/Robinhood `eth_getLogs`, low-thousands events/day | `eth_getLogs` (60 CU) | ~1,000 calls/day/chain = 1.8M CU/mo = ~$1/chain, **~$5 total**; ~$47 total at 10,000 calls/day/chain |
| 4 | Hyperliquid reads | Hyperliquid's own free API for HyperCore; Alchemy HyperEVM only if wanted | **$0** (+ ~$0-5 for HyperEVM) |
| 5 | Special APIs at low volume | Prices + Portfolio + Transfers ad hoc | low tens of dollars at most |

Cheapest single configuration: one PAYG account, no extra throughput purchase, gRPC for the Solana steady state with bounded backfill, RPC polling for the wallet watchlist, `eth_getLogs` across the five EVM chains, HyperCore from Hyperliquid directly.

Self-hosting: not justified on cost for any of these workloads at these volumes. A self-hosted Solana Geyser node is heavy infrastructure against a ~$2-45 bill. Geth or a Hyperliquid node are reasonable for independence, not for savings.

## Day-one account settings
1. Set a Usage Limit so the account stops rather than bills open-ended.
2. Set spend alerts (e.g. 50/80/100%).
3. Check whether Auto-scale is on; the on-demand spend limit applies only when it is.
4. Buy no extra throughput until 429s are actually observed.
5. Confirm the gRPC subscription's server-side account filter is applied before going live -- a mis-scoped stream is capped by nothing except the Usage Limit.

## Unverified / open
1. **Bytes per Solana gRPC transaction update** -- not published by Alchemy. The 1-20 KB range is industry-typical, not Alchemy-sourced. Measure on a live connection.
2. Whether $75/TB is billed on bytes after server-side filtering or before -- strongly implied after, not stated.
3. Portfolio API per-call CU cost and chain list (Solana included?).
4. Whether a product branded "Trades API" exists -- not found under that name.
5. Monad enhanced Data API availability.
6. Solana Account Archive plan-gating -- from a PR title only.
7. Relationship between "Usage Limit" and "Max On-Demand Spend Limit" -- same control or two.
8. Any gRPC-specific connection or rate ceiling.
9. Whether Alchemy's Solana `logsSubscribe` supports a mentions filter.

## Sources
alchemy.com/pricing; docs/reference: pay-as-you-go-pricing-faq, compute-unit-costs, pricing-plans, yellowstone-grpc-overview, node-supported-chains, token-api-overview, portfolio-apis; github.com/alchemyplatform/docs PR #1615; alchemy.com/solana-grpc; blog: solana-account-archive, how-alchemy-built-the-fastest-archival-methods-on-solana, alchemy-going-all-in-on-hyperliquid; support: how-are-websockets-priced, how-can-i-set-alerts-and-max-on-demand-spend-limits; docs/node/hyperliquid/hyperliquid-info-endpoint -- all fetched 200 OK. Via search summary only: Robinhood Chain overview, Monad FAQ, nft-api, transfers-api-quickstart, prices-api-faq.
