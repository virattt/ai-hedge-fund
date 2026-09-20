# FOMO Identity Graph — Can You Name the Flow, and Is It Worth Naming? — Adversarial Research Report

*All live checks in this report were performed on **2026-09-20**. Every endpoint described as "verified" was called from this session, unauthenticated, through the configured HTTPS proxy, with TLS verification on. Nothing here used credentials, defeated bot protection, or touched an authenticated surface. Where I could not reach something, I say so.*

## VERDICT

**The graph is buildable in three layers, and the layer the thesis depends on is the one you cannot legitimately have.** The anonymous flow layer is free, complete and legally clean — FOMO's Solana fee wallet, gas sponsor and Relay vault addresses are published in DeFiLlama's open-source adapter and I verified all three live on mainnet, and FOMO's Hyperliquid perp flow is available per-user, per-fill, with closed PnL, from Hyperliquid's own public `builder_fills` CSV dumps, which I downloaded and decoded today. You can have every FOMO trade, attributed to a wallet, for $0 and with nobody's permission needed. **The naming layer is the problem.** FOMO does not publish wallet addresses — that is the deliberate product gap the entire grey-market vendor ecosystem (fomoapi.io, fomoscan.sh, fomolens.app, getfomoapi.fun) exists to fill, and every one of those vendors is in direct violation of FOMO's Terms of Service, which prohibit "any automated tool, scraper, crawler, spider, or unauthorized third-party application to extract, collect, harvest, or compile data from the Services" *and* "manual processes to monitor or copy the Services' content without our express written permission." FOMO's `robots.txt`, which I fetched today, disallows exactly the paths you would need: `/profile/`, `/user`, `/u/`, `/token`, `/coin`. **There is no free handle→wallet resolver anywhere** — I tested four and all are gated or dead.

**The free-resolver plan is dead on arrival for a reason nobody in the thesis anticipated: FOMO wallets are freshly generated Privy embedded wallets, created at email/Apple signup, with no seed phrase.** They are not the user's pre-existing Phantom wallet. That means they carry no ENS, no `.sol`, no Farcaster verification, no Arkham entity, no Nansen label, and no funding history from a personal CEX withdrawal — the funder is FOMO's own on-ramp, which is identical for every user. I measured the best free resolver empirically today: a random sample of 200 Farcaster FIDs against the free Pinata hub shows **33.5% carry a cryptographically-signed Solana verification and 17.5% carry both that and an X handle** — a genuinely good resolver whose denominator is simply the wrong population. Farcaster resolves Farcaster users. It resolves approximately none of FOMO's 625,000 embedded wallets, because linking one would require a user to export their Privy key, import it into a Solana wallet, and sign a Farcaster verification. Nobody does that.

**And the adversarial question answers itself in a way that kills the trade even if you win the graph.** The best evidence (Merkley, Pacelli, Piorkowski & Williams, *Review of Accounting Studies* 2024) puts the influencer fade at **−7.9% over 30 days on non-top-100 tokens, −62.8% annualised**, worst for self-described experts with large followings. That is a real, large, signed effect — and it lives precisely in the asset class you cannot short. Non-top-100 tokens have no borrow and no perp listing. The fade signal and the executable universe are disjoint sets, which is the same structural trap report 02 flagged for memecoin signals generally. Naming the trader tells you which way to lean; it does not conjure an instrument to lean with.

**Recommendation: build the anonymous flow layer (2–3 days, $0/month). Do not build the identity graph. Do not buy the scraped dataset.** The one naming path I would permit is the trivially cheap and entirely clean one: FOMO's affiliate programme pays referrers 25% of referred trading fees, so promoting traders publish `fomo.family/r/{their-handle}` on X *themselves*. Harvesting self-published referral links from X gives you handle↔X-account links that the person deliberately broadcast, at roughly zero cost, touching FOMO's servers not at all. That covers the promoters — which, as it happens, is exactly the cohort the fade literature says to distrust.

---

## 1. WHAT FOMO ITSELF EXPOSES

### 1.1 There is no official API

Verified: `fomo.family/sitemap.xml` returns **146 URLs**, every one of them marketing or SEO content (`/answers/*`, `/blog/*`, `/affiliates`, `/terms`, `/privacy-policy`). No profile URLs, no leaderboard, no API docs. `fomo.com` 301s to `fomo.family`. FOMO publishes no developer portal, no OpenAPI spec, no SDK.

A caution on search results: queries for "fomo API" return `docs.usefomo.com`, `help.fomo.com` and `usefomo/fomo-python-sdk`. **These are a different company** — Fomo, the social-proof marketing widget. Do not confuse them. FOMO Labs Inc. (fomo.family) has no public API.

An independent API Evangelist profile of fomo exists at `github.com/api-evangelist/fomo` but it is an unenriched stub: *"This profile is a lead awaiting the enrichment pipeline."* No API surface documented.

### 1.2 robots.txt disallows exactly the paths that matter

Verified live, HTTP 200, 389 bytes:

```
User-agent: *
Allow: /
Disallow: /export-key
Disallow: /download
Disallow: /verify-token
Disallow: /tiktok
Disallow: /instagram
Disallow: /r/
Disallow: /ref/
Disallow: /uk-risk-summary
Disallow: /token
Disallow: /profile/
Disallow: /user
Disallow: /u/
Disallow: /coin
Disallow: /prices/
Disallow: /charting_library/
User-agent: Twitterbot
Allow: /
```

`/profile/`, `/user`, `/u/`, `/token`, `/coin` are the identity-graph paths. They are all disallowed. The only user-agent granted broader access is `Twitterbot`, so that link previews render.

### 1.3 The Terms of Service prohibit this outright

From `fomo.family/terms`, §16 Prohibited Uses, quoted exactly as retrieved:

> Attempt to access or search the Services or download content from the Services using any unauthorized or automated means, such as bots, crawlers, or data mining tools; Use automated scripts, bots, software, or any other automated means to create accounts, send messages, post content, execute trades, or otherwise control or interact with account activity on the Services; **Use any automated tool, scraper, crawler, spider, or unauthorized third-party application to extract, collect, harvest, or compile data from the Services, including but not limited to user-generated content, transaction data, pricing information, or account information; Use manual processes to monitor or copy the Services' content without our express written permission**

That second-to-last clause names "transaction data" and "account information" specifically. The final clause closes the manual-collection loophole. There is no reading of this under which crawling FOMO profiles is permitted. **This is a constraint, not a design problem. I have not designed around it and the build recommendation in §7 does not.**

Disputes are subject to binding arbitration with a 60-day good-faith negotiation precondition (`support@fomo.family`). If you wanted a licensed feed, that email is the route — FOMO is a $550M-valuation, Index/USV-backed company that may well license data commercially. **Asking is the only clean way to get the naming layer.**

### 1.4 What a public profile actually carries

Profiles live inside the mobile app (every web page I fetched renders a "Login" affordance). But `https://fomo.family/profile/{handle}` returns HTTP 200 with server-rendered Open Graph metadata:

```
<title>@test on fomo</title>
og:title      = "@test on fomo"
og:description = "Follow @test's trades and portfolio on fomo, the social crypto trading app."
og:image      = "https://image-renderer.fomo.cloud/og/profile/test/card.png"
```

I fetched that card once. It renders **live profile data**: avatar, `@test`, "31 trades | 4.2K followers". The `image-renderer.fomo.cloud` host's `robots.txt` is 24 lines of pure Cloudflare content-signals boilerplate with **no `User-agent` or `Disallow` directives and no signals actually set** — it neither grants nor restricts. That is a configuration oversight on a subdomain, not a grant of permission. **The ToS still governs, and the ToS says no.** I am flagging this because it is the kind of gap that a build would be tempted to route through, and it should be named and rejected explicitly rather than quietly discovered later.

For the full profile schema I relied on the keyless metadata document published by one of the grey-market vendors at `api.fomoapi.io/v1` (HTTP 200, ~21KB, no key required — the vendor's own public self-description, read as documentation, not used to pull user data). Per that document, a FOMO profile object carries:

`userId, userHandle, displayName, description, avatar/profilePictureLink/thumbhash, coverPhotoLink, verified, followers, following, numTrades, swapCount, totalVolume, averageHoldTimeSeconds, createdAt/accountAgeDays, clan{id,name,icon,role}, isReferred` — plus positions, per-window PnL (`24h/7d/30d/all`), holdings, `livePerpPnl` and `hyperliquidPerps`.

Three things about that list matter enormously:

1. **Wallet addresses are not in it.** The vendor charges 2,500 credits (10× a normal call) for "handle→wallet resolution", returns `wallets:{status:"resolving"}` while it works, and can fail (billed at 250 for a miss). That asynchronous, expensive, failable behaviour is the signature of *inference*, not retrieval. **FOMO does not publish the wallet. The vendors derive it** — almost certainly by correlating FOMO's published trade events against on-chain/Relay data. So the wallet↔handle edge is an **inferred** link dressed up in the word "verified".
2. **A `twitter` field does exist** — it appears in the `/followers` and `/following` payload shapes (`handle, displayName, followers, trades, volumeUsd, pnl24h, twitter, clan, verified, account age`). I could not measure its fill rate without a key, and I found no evidence anywhere that FOMO verifies it via OAuth. Treat it as a **claimed** link: a string a user typed. The vendors themselves warn that handle squatting is common and that FOMO's `verified` badge attests the wallet belongs to the account, not who owns the account.
3. **FOMO's own pagination caps are hard limits on any graph you build.** Per the same document, measured against FOMO: leaderboards cap at **150** entries (24h/7d/30d) and **100** (all-time); `followers` and `following` cap at **200 per trader with no cursor past them**; the activity feed serves at most **100 items (~10 minutes) with no cursor behind it**. **You cannot build a complete follower graph.** The social graph is truncated at 200 by the source. Anything you compute on it is a sample of unknown bias.

### 1.5 Visibility is public by default

FOMO's own materials describe profiles and leaderboards as public and make no mention of a private-profile setting. From `fomo.family/answers/what-are-crypto-trading-leaderboards`: *"Detailed profiles - Tap on any trader to see their full trade history, holdings, and performance breakdown."* I searched for an opt-out and found none documented. **Thin evidence flag: I could not confirm from a primary source whether a private-profile toggle exists.** Not finding it is not the same as it not existing. If this matters to the boundary question in §6, it should be confirmed in-app before relying on "they opted in".

### 1.6 The grey market, priced

| Vendor | Status today | Free tier | Notes |
|---|---|---|---|
| `api.fomoapi.io` | Live, keyless `/v1` metadata; all data endpoints 401 | 250,000 credits/mo = 1,000 calls = **100 wallet resolutions/mo** | Starter $49.99 (1,000 resolutions), Growth $599, Scale $1,500. Solana USDC payment, no KYC |
| `getfomoapi.fun` | Live, `/api/health` 200, leaderboard 401 | Google OAuth, 5 req/s | Open-sourced as `abstradeapi/Open-Fomo-API` |
| `fomolens.app` | Site live, no working public API path found | — | Advertises "free FOMO wallet lookup"; I could not reach an endpoint |
| `fomowalletfinder.com` | Site live, API 404 | — | — |
| `api.fomotags.xyz` | **Dead** — `{"message":"Application not found"}` | — | — |

**No free handle→wallet resolution exists.** All four are gated, dead, or unreachable.

`api.fomoapi.io/v1` also carries this, verbatim:

> THE COMPLETE FOMO DATASET — every fomo.family username mapped to its verified Solana + EVM wallet — is available to license as a one-off, separate from the API plans. Enterprise-grade and priced accordingly. Serious buyers only. Inquire on Telegram.

That is an open offer to sell a bulk-scraped dataset whose collection FOMO's ToS forbids, brokered over Telegram with no counterparty identity. **Do not buy it.** Beyond the obvious, you would be taking a dependency that can vanish the day FOMO sends a letter, on data you cannot audit, from a seller you cannot identify.

---

## 2. EXISTING RESOLVERS, TESTED

All probed live today, unauthenticated.

| Resolver | Result | Cost | Verdict for this problem |
|---|---|---|---|
| **Farcaster free hub** (`hub.pinata.cloud`) | **HTTP 200.** 825,994,366 messages, 1,683,053 FID registrations | **Free, no key** | **Best free resolver found.** Cryptographic. Wrong population — see §2.1 |
| Neynar (Farcaster, hosted) | Not called (needs key) | Starter 300 RPM; credit-metered | Only source of a free-ish *reverse* (address→FID) index; self-hosting the hub is 669GB |
| ENS (`api.ensideas.com`) | HTTP 200, resolved `vitalik.eth` correctly | Free | EVM only. Irrelevant to Solana-native FOMO; marginally relevant to Hyperliquid perp addresses |
| SNS / `.sol` (`sns-api.bonfida.com`) | HTTP 200 but empty for test address | Free | Alive. `sns-sdk-proxy.bonfida.workers.dev` is **dead** (Cloudflare 1042) |
| SNS X-handle registry | Not directly queried | ~0.01 SOL to register | Real proof mechanism (tweet the address, then sign with it) but effectively abandoned since ~2022. Negligible coverage |
| **Arkham** | **HTTP 400** — `"invalid timestamp format, please sign up for an api key :)"` | Free Intel UI; API premium via ARKM token, no fiat tier | Entity labels are AI clustering over *historical* activity. Fresh wallets have none |
| **Zerion** | **HTTP 402 Payment Required** | Paid | — |
| **DeBank** | **HTTP 429** (unofficial endpoint anyway) | — | — |
| Nansen | Not called | Free 100 credits; Pro $49–69/mo; pay-per-use $0.01–0.05/call | Report 02 already established the label-restatement look-ahead problem. Same objection applies |
| Dune Spellbook wallet labels | Repo not reachable from this session (GitHub access scoped) | Free tier queries | Community labels skew to EVM whales and protocol contracts |

### 2.1 I measured the best one

Rather than guess at Farcaster coverage, I sampled **200 random FIDs** (seeded, range 1–1,100,000) against the free Pinata hub and pulled `verificationsByFid` and `userDataByFid` for each. All 200 responded. Results:

| Property | Count / 200 | Share of sample | Share of the 145 with a real profile |
|---|---|---|---|
| Has a username (active profile) | 145 | 72.5% | — |
| ≥1 **Ethereum** verification (signed) | 102 | **51.0%** | 64.1% |
| ≥1 **Solana** verification (signed) | 67 | **33.5%** | 41.4% |
| `USER_DATA_TYPE_TWITTER` set | 52 | 26.0% | 34.5% |
| **Solana verification AND X handle** | 35 | **17.5%** | **24.1%** |

Confirmed shape of a Solana verification, from `fid=3`:

```json
{"type":"MESSAGE_TYPE_VERIFICATION_ADD_ETH_ADDRESS","fid":3,
 "verificationAddAddressBody":{
   "address":"ExAqci8uUVKtqHqFW58fmwgMMY9PATfRGGyv6837j9Lx",
   "claimSignature":"q0M9yzw+mHiVI/bnT60HKjISvbJJ+cUBfoJuuzarad6L2npSKNlNk2dgBkIpxfTe/0w3aehoxiets/y8ZgpRCw==",
   "protocol":"PROTOCOL_SOLANA"}}
```

That `claimSignature` is the real thing: the address signed a claim to the FID. **This is the one high-confidence link type available for free, and the thesis is right to single it out.**

**But there is a sharp caveat on the X half that the thesis blurs.** The address↔FID edge is *self-verifying* — you can check the signature yourself. The FID↔X edge is **not**. `USER_DATA_TYPE_TWITTER` is an ordinary UserData message that any signer authorised for that FID can write. Warpcast performs an OAuth check before writing one and only displays its own attestations *"since they can be spoofed"* (Farcaster protocol discussion #199, FIP-19). So a raw hub read gives you a value that is **attested by a third party if and only if you also check which app signer wrote it** — and is otherwise merely claimed. Any pipeline that reads `USER_DATA_TYPE_TWITTER` off a hub and calls the result "cryptographically verified" is wrong.

---

## 3. THE SELF-ROLLED ALTERNATIVE — AND WHY IT SPLITS IN TWO

### 3.1 The anonymous flow layer is free, complete, and clean. Build this.

**DeFiLlama's open-source fee/DEX adapters for FOMO publish the platform's own Solana infrastructure addresses.** From `DefiLlama/dimension-adapters`, `dexs/fomo/index.ts`, retrieved today, with DeFiLlama's own comments:

```ts
const FEE_WALLET  = 'R4rNJHaffSUotNmqSKNEfDcJE8A7zJUkaoM5Jkd7cYX';   // FOMO fee recipient on native Solana swaps
const GAS_SPONSOR = 'AgmLJBMDCqWynYnQiPCuj9ewsNNsBJXyzoUhD9LJzN51';  // FOMO fee payer on all user-initiated txs
const RELAY_VAULT = '7uTT8Xi5RWXzy7h9XL244GRgEycDYDhLjr3ZyNdXi8pZ';  // owner of Relay Depository USDC account (Solana)
```

I verified all three live against the public Solana RPC. `GAS_SPONSOR` returned five signatures **three of which landed in the same slot (448594905)** — this address is signing continuously at high throughput. `FEE_WALLET` returned finalized signatures seconds old.

**`GAS_SPONSOR` is the key.** FOMO sponsors gas on *every* user-initiated transaction, which means **every FOMO trade on Solana carries FOMO's fee payer as a signer**. That is a perfect, free, on-chain platform fingerprint. You can enumerate 100% of FOMO's Solana flow — wallet by wallet, trade by trade — without touching FOMO's servers, without violating anything, and at the cost of an RPC subscription you already have. The adapter even hands you the correct query: candidate transfers are USDC `spl_token_transfer` rows where `to_address IN (FEE_WALLET, RELAY_VAULT)` and `signer = GAS_SPONSOR`.

**A caution earned the hard way.** I tried to shortcut this from raw RPC and failed twice. Extracting "the other signer" from fee-paying transactions returns market makers, not users. Extracting the USDC transfer authority returns addresses with **8,000 transactions in under a day** — DFlow solvers and MMs, not retail. Nine of nine candidates from my second attempt were contaminated. **Do not try to do this from raw `getTransaction` parsing.** Use the indexed path (Dune or Allium, per the adapter) where transfers resolve at the token-account-*owner* level. Budget a day for the query, not an afternoon.

One clean observation survived: wallet `7xcnsACqLXAnPiRATiTz3sroy5oTzJRSLS2HuvPr3Es` had **its very first on-chain transaction ever signed by FOMO's gas sponsor**, then ran 4,190 transactions over 134 days. That is a FOMO-native wallet, born inside the app, and it demonstrates that "first tx signed by `GAS_SPONSOR`" is a workable birth-certificate test.

### 3.2 The perps layer is even better, and it comes from Hyperliquid, not FOMO

FOMO's perps route through Hyperliquid (DeFiLlama lists `fomo Perps`, slug `fomo-perps`, category `Interface`, parent `parent#fomo`, chain **Hyperliquid L1**) and Trade.xyz. I confirmed the Trade.xyz builder-deployed perp dex live via `POST https://api.hyperliquid.xyz/info {"type":"perpDexs"}`:

```json
{"name":"xyz","fullName":"XYZ","deployer":"0x88806a71d74ad0a510b350545c9ae490912f0888",
 "feeRecipient":"0x83ffcfb1f2ad843c474b2e28df86c721cb869d3a",
 "assetToStreamingOiCap":[["xyz:AAPL","200000000.0"],["xyz:NVDA",...],["xyz:BRENTOIL","750000000.0"],["xyz:SPX",...]]}
```

— equities, commodities and indices, matching FOMO's advertised perp menu.

**Hyperliquid publishes per-builder fill dumps.** Per the official docs: *"The trades that use a particular builder code are uploaded in compressed LZ4 format to `https://stats-data.hyperliquid.xyz/Mainnet/builder_fills/{builder_address}/{YYYYMMDD}.csv.lz4`"* (lowercase address, case-sensitive).

I downloaded and decoded one today (HTTP 200, 5,711 bytes, 94 rows) and the schema is:

```
time,user,coin,side,px,sz,crossed,special_trade_type,tif,is_trigger,counterparty,closed_pnl,twap_id,builder_fee
2026-09-18T00:03:40Z,0x53bbf2c0b745fd5cada06ddb4a3fb5e955f6efb3,ZEC,Ask,1469.6,0.11,true,Na,FrontendMarket,false,0x7fda...,0,0,0.080828
```

**Per-user address, per-fill, timestamped, priced, sized, with closed PnL and counterparty.** Free, no auth, no rate limit, no ToS problem — this is Hyperliquid's own published data about its own chain. Per-user state is equally open: `{"type":"clearinghouseState","user":"0x…"}` returned a live margin summary and position array for an arbitrary address, and `{"type":"maxBuilderFee","user":"0x…","builder":"0x…"}` lets you verify a user's builder approval, so **FOMO membership is externally provable per address**.

**Gap I could not close: I did not find FOMO's own builder address from a primary source.** I checked DeFiLlama's adapters (`fees/fomo-perps`, `dexs/fomo-perps` — both 404; `fomo Perps` uses `module: dummy.js`), HypeBasis's builder-fee page (no builder directory), and Blockworks' FOMO analytics page (navigation shell only). It is recoverable in minutes by anyone with a FOMO perp account — approve a perp trade and read back `maxBuilderFee` for your own address — or from a Dune builder-codes dashboard with an API key. **Treat this as a known open item, not a blocker.**

### 3.3 The naming layer: why the on-chain heuristics do not transfer

The thesis asks what actually transfers from UTXO-chain clustering to Solana. Honestly: **very little, and less than usual here.**

- **Common-input-ownership does not exist on Solana.** There are no UTXOs. Multiple signers on one transaction means co-signing, not co-ownership — which is exactly the error that contaminated both of my extraction attempts in §3.1. On FOMO specifically it is worse than useless: *every* user transaction is co-signed by FOMO's gas sponsor, so naive co-signing clustering collapses all 625,000 users into one entity.
- **Funding-source clustering is neutered by design.** FOMO users fund with debit card, Apple Pay, or crypto into a unified USD balance, and cross-chain flow moves through the shared Relay vault. The funder is FOMO for everyone. There is no personal-CEX-withdrawal fingerprint because there usually is no personal CEX withdrawal.
- **CEX-deposit-address reuse requires a pre-existing CEX relationship that these wallets do not have.**
- **No prior history to label.** This is the crux. FOMO issues a **Privy embedded wallet at signup**, created from an email or Apple ID login, with **no seed phrase** and key material split by Shamir's Secret Sharing (exportable — hence the `/export-key` path in robots.txt). A wallet born at signup has no ENS, no `.sol`, no Farcaster verification, no Arkham entity, no Nansen label, and no history for anything to cluster on. **Every resolver in §2 resolves prior identity. These addresses have none.**

What is left:

- **Twitter bios and pinned posts containing addresses.** Works for the handful of whales who publish an address. But a KOL's published address is their *personal* wallet, not their FOMO Privy wallet — so it resolves the wrong address and gives you a false edge if you are not careful.
- **Farcaster verified-address proofs.** Cryptographic, free, correct — and, as established, ~0% coverage of the relevant population.
- **Self-published referral links.** *This is the one that works.* FOMO's affiliate programme pays referrers **25% of referred users' trading fees**, and the referral link is `fomo.family/r/{username}` — **the username *is* the referral code**. Promoting traders therefore broadcast their own FOMO handle on X, in their own voice, for their own money. Harvesting `fomo.family/r/` from X gives you X-handle↔FOMO-handle edges that the subject deliberately published, at near-zero cost, without touching FOMO. It is the cleanest edge in this whole report — and note what it selects for.

---

## 4. HOW GOOD DOES THE GRAPH GET?

**The report must not blur link types, so here they are separated.** These are estimates with a stated basis, not measurements; I flag which is which.

| Link | Type | Basis | Est. coverage of FOMO top-150 by volume | Confidence |
|---|---|---|---|---|
| FOMO handle → FOMO trade history/PnL | **Published** by FOMO | Leaderboard/profile, in-app | ~100% (capped at 150) | High |
| Wallet → FOMO platform membership | **Proven**, on-chain | `GAS_SPONSOR` signer (Solana); `maxBuilderFee` (HL) | ~100% | **High — verified live** |
| Wallet → trade history | **Proven**, on-chain | Chain / HL `builder_fills` | ~100% | **High — verified live** |
| FOMO handle ↔ wallet | **Inferred** (vendor), not published | Vendor correlation, 2,500 credits, can fail | ~100% of top-150, ~$0.05/identity | Medium — and **ToS-violating** |
| FOMO handle → X handle (profile `twitter` field) | **Claimed** — user-typed, no OAuth evidence found | Vendor payload shape | **Unmeasured** | Low |
| FOMO handle → X handle (self-published `/r/` link) | **Self-published** by the subject | X search | ~15–25% of top-150 (estimate) | Medium-high per edge |
| FOMO handle → X handle (string collision) | **Inferred**, weak | Handle match | High apparent, low real — squatting | **Low. Do not use alone** |
| Wallet → X handle (Farcaster) | **Proven** (address↔FID) + **attested** (FID↔X) | Free hub; 33.5%/17.5% measured | **~0% for FOMO wallets** | High confidence in the ~0% |

**Headline number: of FOMO's top 150 traders by volume, I estimate 15–30% could be resolved to a named X identity with defensible confidence, and under 5% with anything resembling cryptographic proof.** The 15–30% comes almost entirely from self-published referral links plus corroborated handle collisions. The near-100% figure the vendors imply is a *wallet* resolution — pseudonymous, and ToS-violating — not a *name*.

**Two things make even that estimate optimistic.** First, the follower/following graph is capped at 200 per trader with no cursor, so the relational evidence you would use to corroborate a weak identity edge is itself a truncated sample. Second, FOMO's coordinated-flow board (`/v2/tokens/activity`) reportedly **stopped publishing on 2026-08-23** — the platform is not a stable data partner even for the vendors who scrape it.

---

## 5. DOES THE NAMED LAYER ADD SIGNAL? — THE ADVERSARIAL SECTION

### 5.1 No, and the reason is structural, not statistical

The prior review (report 02) established the direction. The magnitude is what matters here, and it is large: per **Merkley, Pacelli, Piorkowski & Williams, *Review of Accounting Studies* 29 (2024)** — ~36,000 tweets, 180 influencers, 1,600+ assets — $1,000 invested in **non-top-100** tokens on the tweet date and held 30 days loses **$79 (−7.9%), an annualised −62.8%**. Returns are modestly positive for ~2 days, turn negative around day 5, reach −2.2% by day 10 and −6.5% by day 30. The effect is **more negative when the influencer self-describes as an expert, and more negative still for experts with larger followings.** The authors' own conclusion: you can only profit *"by exiting the position shortly after the initial tweet, a strategy that may not always be viable, due to illiquid crypto markets."*

**Read as a fade thesis, this is the trap.** The effect is concentrated in non-top-100 tokens. Non-top-100 tokens have no borrow and no perp listing. **You cannot short them.** Perps exist for roughly the top ~100 names — and "has a perp listing" is itself a survivorship-selected set, the exact bias report 02 flagged. The fade signal and the executable universe barely intersect. Attribution does make fading *conceivable*; it does not make it *executable*, and the report should not let the first be mistaken for the second.

The residual honest use is **avoidance, not alpha**: naming lets you *decline* to be on the other side of a large-following self-described expert's small-cap entry. That is worth something. It is worth much less than a strategy.

### 5.2 The strongest counter-evidence, stated fairly

The best case for a named layer comes from an adjacent market. **"Wisdom of the Few" (Yale SOM / prediction markets, covered by CoinDesk 2026-04-26): 1.72 million accounts, 98,906 events, 210,322 markets, $13.76 billion in volume over two years.** Findings:

- **3% of accounts qualify as "skilled"** — statistically significant positive returns not explainable by chance.
- **44% of those classified skilled in the first half stay skilled in the second half** — versus ~10% persistence for mutual fund managers. Skill is real and it persists.
- But **69% of profits went to "lucky winners" with no statistically discernible skill**; skilled traders plus market makers, under 3.5% of accounts, capture just over 30% of gains.

So a persistent, identifiable skilled cohort *does* exist in at least one crypto-adjacent market, and that is the honest strongest form of the thesis. **The catch is the classifier.** Identifying the 3% required two years and ~99,000 resolved events, done retrospectively against randomised benchmarks. **FOMO ranks on 24h / 7d / 30d PnL.** A 24-hour PnL leaderboard over 625,000 users is a near-pure draw from the 69% lucky-winner pool. Corroborating vendor-sourced figures — fewer than 15% of top monthly performers hold their ranking the following month — point the same way, though that number comes from a trading-platform academy page and is **vendor-sourced; treat it as illustrative, not evidence.**

If you wanted to find FOMO's 3%, you would need months of per-wallet history, hundreds of closed positions per trader, and a risk-adjusted classifier validated out of sample. **You can build exactly that from the free anonymous layer in §3.** You do not need anyone's name to do it. **Which is the whole argument: the discriminating variable is trade count and risk-adjusted persistence, not identity.**

### 5.3 What does not exist

**I found no study — none — evaluating whether attributing on-chain flow to named identities improves signal quality.** Not for copy-trading platforms, not for FOMO, not for Nansen-style labels. The copy-trading literature is adjacent and unflattering (Apesteguia, Oechssler & Weidenholzer in *Management Science* find copy trading causes **excessive risk-taking**; eToro studies find more than half of sampled traders underperform) but none of it isolates the *naming* variable. **The evidence for the core claim of this thesis does not exist. I am not going to manufacture a conclusion from its absence** — but note the asymmetry: the claim is unsupported, while the nearest well-identified effect (the influencer fade) points the other way.

---

## 6. THE BOUNDARY

**Recommendation.** Draw the line at **what the subject published about themselves**. Reading a FOMO profile that displays a handle, and reading an X account where that person posted their own `fomo.family/r/{handle}` referral link, is reading two things a person deliberately broadcast — that is legitimate, and the affiliate economics mean they broadcast it *to be found*. **Everything past that is a different activity.** Deriving a wallet address that FOMO deliberately withholds — which is precisely what "handle resolution" is, whether you do it or a vendor does it for you — takes a pseudonymous identity and attaches a permanent, complete financial record to it that the person did not publish and probably assumes is private. That is deanonymisation. It does not become something else because the derivation was statistical, or because a vendor sold it to you. **Never store: wallet↔identity mappings you derived rather than read; any real-world identifier (legal name, employer, location, email) however obtained; and any vendor-supplied handle↔wallet table.** Store platform-level flow keyed by address, and store self-published handle↔handle edges with a provenance field recording the URL the subject published it at. If an edge cannot name the public artefact it came from, it does not go in the database.

**GDPR/CCPA, briefly.** FOMO Labs Inc. is US-domiciled; its privacy policy has a California/CCPA section and a Shine-the-Light clause, and I found **no GDPR, EEA or UK section** in the policy text I extracted — yet `robots.txt` disallows `/uk-risk-summary`, so they are serving UK users, and the perps product is explicitly non-US. If any of your subjects are in the EEA or UK, a wallet address linked to a person is **personal data** (pseudonymous data remains personal data under Recital 26), and building an identity graph over it is **profiling** under Art. 4(4). You would be relying on legitimate interests (Art. 6(1)(f)), which requires a documented balancing test you would probably lose against a retail trader's reasonable expectation of privacy, plus Art. 14 notice obligations for data not collected from the subject — impossible to discharge at scale against pseudonymous people. Under CCPA/CPRA, publicly-available information is exempt, but *derived* linkage is not obviously public, and CPRA's sensitive-personal-information category is a live question for financial data. **This is a note for you to decide on, not a refusal.** The §7 build avoids all of it by not storing derived identity.

---

## 7. BUILD RECOMMENDATION

### BUILD — anonymous FOMO flow. 2–3 days. $0/month.

1. **Solana spot flow.** Dune or Allium query keyed on the DeFiLlama adapter's logic: USDC `spl_token_transfer` rows where `to_address IN (R4rNJ…, 7uTT8…)` and `signer = AgmLJ…`, joined to `solana.dex.trades` on `txn_id`. Yields per-wallet FOMO trades. **~1 day.** Do not attempt this from raw RPC — see §3.1.
2. **Hyperliquid perp flow.** Recover FOMO's builder address (approve a perp trade and read back `maxBuilderFee`, or use a Dune builder-codes dashboard), then pull `stats-data.hyperliquid.xyz/Mainnet/builder_fills/{addr}/{YYYYMMDD}.csv.lz4` daily. Per-user fills with closed PnL, free, forever. **~half a day.**
3. **Cohort classifier.** Rank wallets by *risk-adjusted, trade-count-weighted* performance over ≥90 days, not by PnL over 24h. Freeze the roster point-in-time daily — the same discipline report 02 mandated for Nansen labels, for the same look-ahead reason. **~1 day.**
4. **Use it as a slow overlay on perp-listed assets at a 6–48h horizon**, per report 02's conclusion for wallet-cohort flow. Not as a copy-trade executor.

### BUILD (optional, cheap) — self-published handle edges. ~half a day. $0.

Harvest `fomo.family/r/` links from X. Store with provenance. Use to *label cohorts you already found*, never to find them. Expect it to surface promoters — and weight them **down**, per §5.1.

### DON'T — the identity graph.

**Do not scrape FOMO.** The ToS forbids it in terms that name transaction data and account information explicitly, and `robots.txt` disallows every path you would need. **Do not route around it via `image-renderer.fomo.cloud`** — the missing robots rules there are an oversight, not consent. **Do not buy the vendor dataset**, which is the same violation with a Telegram invoice attached and a dependency that dies the day FOMO notices. **Do not build free-resolver enrichment** — Farcaster, ENS, SNS, Arkham and Nansen all resolve *prior* identity, and FOMO's Privy wallets are born at signup with none. **And do not build it even if it were free and permitted**, because the one well-identified effect in the literature says named high-following experts predict −7.9%/30d in an asset class you cannot short, and the one study showing persistent identifiable skill needed two years and 99,000 events to find 3% — a classifier you can build, better, from the free anonymous layer, without anyone's name.

**If you want the naming layer legitimately, there is exactly one route: email `support@fomo.family` and ask to license it.** FOMO is a funded company with a data asset and no public API; a commercial conversation is the only version of this that is both clean and durable. Given §5, I would not spend much on the answer.

---

## APPENDIX — WHAT WAS VERIFIED LIVE (2026-09-20)

| Check | Result |
|---|---|
| `fomo.family/robots.txt` | 200, 389B — disallows `/profile/`, `/user`, `/u/`, `/token`, `/coin`, `/r/`, `/ref/` |
| `fomo.com/robots.txt` | 301 → `fomo.family` |
| `fomo.family/terms` | 200 — §16 anti-scraping clause quoted verbatim in §1.3 |
| `fomo.family/sitemap.xml` | 200 — 146 URLs, all marketing; no profiles, no leaderboard |
| `fomo.family/profile/test` | 200 — OG `@test on fomo` + `image-renderer.fomo.cloud` card URL |
| `image-renderer.fomo.cloud/og/profile/test/card.png` | 200, PNG 1200×630 — renders live data (31 trades, 4.2K followers) |
| `image-renderer.fomo.cloud/robots.txt` | 200 — 24 lines, **all comments**, no rules, no signals set |
| Solana RPC `getSignaturesForAddress` on `AgmLJ…` (gas sponsor) | 5 sigs, 3 in slot 448594905 — high-throughput, active |
| Solana RPC on `R4rNJ…` (fee wallet) | Finalized sigs seconds old |
| Wallet `7xcnsACq…` provenance | First-ever tx signed by FOMO gas sponsor; 4,190 txs / 134 days |
| DeFiLlama `dexs/fomo/index.ts`, `fees/fomo/index.ts` | 200 — three FOMO Solana addresses + full user-enumeration query |
| HL `POST /info {"type":"perpDexs"}` | 200 — Trade.xyz `xyz` dex, deployer + feeRecipient + equity/commodity caps |
| HL `POST /info {"type":"clearinghouseState"}` | 200 — live per-address margin + positions, no auth |
| HL `builder_fills/{addr}/20260918.csv.lz4` | 200, 5,711B → **94 rows decoded**, 14-column per-user fill schema |
| `hub.pinata.cloud/v1/info` | 200 — 825,994,366 messages, 1,683,053 FIDs |
| Farcaster 200-FID random sample | 51.0% ETH-verified, 33.5% SOL-verified, 26.0% twitter, 17.5% both |
| `api.ensideas.com` ENS resolve | 200 — correct |
| `api.arkm.com` | 400 — API key required |
| `api.zerion.io` | 402 Payment Required |
| `api.debank.com` | 429 |
| `sns-sdk-proxy.bonfida.workers.dev` | **Dead** — Cloudflare 1042 |
| `api.fomoapi.io/v1` | 200, ~21KB keyless metadata — endpoints, pricing, dataset-licensing offer |
| `getfomoapi.fun/api/leaderboard/24h` | 401 — key required |
| `fomolens.app`, `fomowalletfinder.com` API paths | 404 |
| `api.fomotags.xyz` | 404 — `{"message":"Application not found"}` |
| **Could not reach** | FOMO's Hyperliquid builder address (no primary source); Dune Spellbook repo (GitHub scope); ACM CHI 2026 crypto-KOL paper (403); DeFiLlama web UI (403) |

### Sources

- [fomo Terms of Service](https://fomo.family/terms) · [Privacy Policy](https://fomo.family/privacy-policy) · [robots.txt](https://fomo.family/robots.txt) · [Leaderboards](https://fomo.family/answers/what-are-crypto-trading-leaderboards) · [Social features](https://fomo.family/blog/learn/leveraging-fomos-social-features) · [Wallet architecture](https://fomo.family/blog/learn/fomo-security-wallet-architecture)
- [Hyperliquid builder codes docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes) · [DeFiLlama dimension-adapters](https://github.com/DefiLlama/dimension-adapters) · [DeFiLlama: fomo](https://defillama.com/protocol/fomo)
- [Neynar: user bulk-by-address](https://docs.neynar.com/reference/user-bulk-by-address) · [FIP-19 Social Attestations](https://github.com/farcasterxyz/protocol/discussions/199) · [SNS X handle registration](https://docs.bonfida.org/collection/x-former-twitter/solana-name-service-twitter)
- [Merkley et al., "Crypto-influencers," *Review of Accounting Studies*](https://link.springer.com/article/10.1007/s11142-024-09838-4) · [Kelley School summary](https://blog.kelley.iu.edu/2024/11/21/research-be-cautious-in-following-crypto-influencers-investment-advice-most-gains-disappear-within-days/)
- ["Wisdom of the Few," Yale SOM](https://insights.som.yale.edu/insights/wisdom-of-the-few-prediction-markets-are-driven-by-small-number-of-skilled-traders) · [CoinDesk coverage](https://www.coindesk.com/markets/2026/04/26/only-3-of-traders-drive-prediction-markets-accuracy-not-the-crowd-study-finds) · [Apesteguia, Oechssler & Weidenholzer, "Copy Trading," *Management Science*](https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3508)
- Grey-market vendors (documented, not endorsed): [fomoapi.io](https://fomoapi.io/) · [Open-Fomo-API](https://github.com/abstradeapi/Open-Fomo-API) · [fomoscan.sh](https://www.fomoscan.sh/) · [fomolens.app](https://fomolens.app/)
