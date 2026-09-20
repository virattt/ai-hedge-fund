# FOMO handle <-> wallet <-> ID resolvers, and the on-chain flow layer (Solana + EVM) -- 2026-09-19

*Agent report, condensed. "Tested" means the agent called it live on the date above; nothing here has been re-verified by the orchestrating session.*

## VERDICT

The earlier "no free resolver exists" conclusion was wrong and the known-five list undercounted by about 2x. Four resolvers are free and usable today without login (fomowalletfinder.com, fomolens.app web widget, fomoscan.sh web checker, the open-source YvesxDev/fomo-wallet-resolver), and **fomoapi.io's free tier (1,000 calls/month, no card, every endpoint) is the best free programmatic path.** On-chain: the Solana gas-sponsor address is confirmed byte-for-byte in DefiLlama's adapter source and tested live (~10.75 tx/s, ~929k tx/day on a 93-second sample). On EVM there is no FOMO-published paymaster address: EVM flow routes through Relay Protocol and settles to Solana; the one concrete EVM fingerprint found is a Relay app-fee-recipient Safe, from an unofficial source, corroborated live on Basescan.

## A. Resolvers beyond the known five

| Resource | Directions | Chains | Free? | Notes |
|---|---|---|---|---|
| **YvesxDev/fomo-wallet-resolver** (GitHub, MIT) | handle -> Solana wallet; -> EVM wallet when a verified Relay swap match exists | Solana + EVM | Fully free, self-hosted | Local Rust tool using the user's own logged-in session; builds an unsigned 2 USDC transfer via the profile API and decodes the destination token account. Never signs or submits. |
| **genie-fomo-api** (GitHub) | handle/wallet <-> profile, positions, trades, balance history | Robinhood Chain, ETH, BSC, Base, Solana | Free, optional key | 30 REST endpoints on Cloudflare Workers, 240 req/min. Covers only ~450 traders. v2 shipped 2026-09-17. |
| **fomo-robinhood-radar** (GitHub, MIT; fomoradar.app, Telegram bot, REST API) | Infers the real execution wallet from on-chain co-trade timing, without calling FOMO's API | Robinhood Chain primarily | "$0/month" | `eth_getLogs` on the RH swap router, 90-second co-trade window. Self-reported 101 agreements / 0 disagreements vs verified wallets (own test). States fomo.family's API is Cloudflare-blocked for non-browser clients. Tracks 302+ wallets, 109,669+ fills. |
| fomotags (api.fomotags.xyz) | wallet -> handle | ? | ? | Site exists; every endpoint guess 404'd. Unverified. |
| fomoapi.fun | ? | ? | ? | Title-only page. Thin. |
| Fomo-Card, FomoPocket, fomo-helper, fomoprofil | consumers/overlays, not resolvers | -- | free | Not independent lookup tools. |

## B. Known five, re-verified

| Resource | Free tier | Auth | Directions | Chains |
|---|---|---|---|---|
| **fomoapi.io** | 250,000 credits/mo = 1,000 calls, no card, all endpoints; free alerts stream degrades to 15s latency after 7 days | API key via signup | `GET /v2/users/{handle}` -> Solana + EVM wallets (+ id) | ETH, Base, BSC, Robinhood Chain, SOL, Monad |
| **fomolens.app** | Unlimited web lookups, 1 per 10s per visitor | none for web; API needs email + manual trial approval | bidirectional | Solana + EVM |
| **fomowalletfinder.com** | Free; no signup, no wallet connect | none | handle -> wallet | Solana + EVM |
| **fomoscan.sh** | Free web "Wallet checker"; API from $99/mo | none for web; Bearer key for API | bidirectional + by ID | Solana + EVM |
| getfomoapi.fun (Open-Fomo-API) | No free tier; $39.99/mo | API key | leaderboard, profile/wallet, swaps | Solana only |

Live-test limits: the three web widgets are client-rendered search boxes, so curl could not exercise them; `fomolens.app/api/v1/lookup/{handle}` returned 401 (route real, key-gated). End-to-end widget tests need browser automation. Public top-PnL handles usable for such a test are listed in a KuCoin KOL comparison article.

## C. Labels, Dune, Hyperliquid -- mostly negative

- Dune dashboards exist (impossiblefinance, fomoteam, socialgraphventures, mrnobody, ares2) but the one fetched in full carries aggregates only. DefiLlama's adapter pulls identity from a private Dune schema (`dune.tryfomo.*`).
- No FOMO-specific wallet labels found via search on GMGN, Axiom, Photon, BullX, Kolscan, Birdeye, Cielo, Arkham, Nansen or DexCheck (not checked inside logged-in UIs).
- No tool found that republishes FOMO's Hyperliquid builder-code fills per wallet.

## D. Solana flow layer -- confirmed and tested

From `DefiLlama/dimension-adapters` (`active-users/fomo.ts`, `dexs/fomo/index.ts`, `fees/fomo/index.ts`, raw source fetched):

```
FEE_WALLET   = R4rNJHaffSUotNmqSKNEfDcJE8A7zJUkaoM5Jkd7cYX   // fee recipient on native Solana swaps
GAS_SPONSOR  = AgmLJBMDCqWynYnQiPCuj9ewsNNsBJXyzoUhD9LJzN51  // fee payer on all user-initiated txs
RELAY_VAULT  = 7uTT8Xi5RWXzy7h9XL244GRgEycDYDhLjr3ZyNdXi8pZ  // owner of Relay Depository USDC account
```

- Live on public RPC: the 1,000 newest signatures spanned 93 seconds -> ~10.75 tx/s, ~929k tx/day (short sample; order-of-magnitude). Plain System-Program wallet, ~2,081 SOL; labelled "Fomo Co-signer" on Solscan per independent X posts.
- Enumeration (the adapter's own join logic, directly reusable): GAS_SPONSOR is fee payer on every sponsored tx. The user is the other party: for native swaps, the `from` of a USDC transfer to FEE_WALLET inside a sponsor-signed tx; for cross-chain buys, the `from` of a USDC transfer to RELAY_VAULT; for cross-chain sells, USDC transfers from Relay solver wallets to already-known user wallets (bootstrap from buys/swaps first).
- Free-tier feasibility: public RPC allows ~4 req/s per method. The full firehose needs ~11 req/s sustained -> a paid node or Geyser stream (~$99-999+/mo). Following a known set of ~1,000 wallets fits the free tier comfortably.

## E. EVM flow layer (Base, BSC, Robinhood Chain)

- FOMO's architecture post confirms ERC-4337 account abstraction with a paymaster on Base/BNB/Monad but publishes no paymaster address.
- EVM trades route through Relay Protocol; value settles on Solana.
- One concrete EVM address: Relay **app-fee recipient** `0x9fc4e320a181e88644a302d11f1f158ef0699e37`, from a community PR (ChainBench/OpenChainBench #2459) that derived it from Relay's public `/requests/v2` feed; FOMO's Relay referrer id is private. That PR's 500-request-per-chain snapshot: 354 Robinhood Chain, 221 BNB, 40 Base, 29 Ethereum -- **Robinhood Chain dominates the EVM side.** Basescan shows a live Safe created 2025-08-27 with balances on exactly Base, Robinhood Chain and BSC. Not officially published.
- Practical free method: query Relay's keyless `/requests/v2` feed filtered on that app-fee recipient and cross-reference the user field (**not tested by the agent**). EVM volume is low hundreds to low thousands of actions/day -- free-tier territory. `docs.robinhood.com/chain/protocol-contracts` was surfaced but not read.
- For the Robinhood-Chain leg specifically, fomo-robinhood-radar's router-log method is the most concrete free working approach found.

## Cheapest pipeline at top ~1,000 traders -- $0/month

1. Top handles from fomoapi.io leaderboard endpoints (or genie-fomo-api, capped ~450).
2. Handle -> wallets via fomoapi.io `GET /v2/users/{handle}`: ~1,000 calls = the monthly free budget. Faster refresh: $49/mo tier.
3. Solana: per known wallet, `getSignaturesForAddress`/`getTransaction` filtered to sponsor-co-signed txs; ~1,000-3,000 calls, under an hour on free RPC, repeatable daily.
4. EVM: Relay `/requests/v2` filtered on the app-fee recipient, joined on the same wallets' EVM addresses.

Full-firehose real-time capture is the point where a paid stream becomes necessary.

## Not reached

fomotags and fomoapi.fun endpoints; logged-in label UIs; Dune `tryfomo` schema; an official EVM paymaster/app-fee address; end-to-end tests of the three web widgets; Relay `/requests/v2` live test; Robinhood Chain protocol-contracts docs.
