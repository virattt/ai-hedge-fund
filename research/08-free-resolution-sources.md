# Free Resolution Sources — Where FOMO's Flow Actually Lives, Chain by Chain

*Second pass, correcting report 07. All live checks performed **2026-09-20**, unauthenticated, through the configured HTTPS proxy, TLS verification on. No credentials used, no bot protection defeated, `fomo.family` not scraped. Where a check failed or I could not verify something, it is marked **UNVERIFIED** rather than dropped.*

*Scope note: the legal/GDPR analysis from report 07 is withdrawn at the user's direction and is not replaced. The one operating rule that stands was established elsewhere: **regulatory exposure arrives when you route a second user's flow, not your own.** Nothing in this report is a per-source licence or ToS evaluation. Sources are judged on whether they work.*

---

## VERDICT

**I found FOMO's Hyperliquid builder address, and it was booby-trapped.** There are **two** builders with "fomo" in the name in DeFiLlama's registry and the obvious one is wrong. The correct address is **`0x2a2b6b093a9813fbd8cddae800c3d17d46460d17`** (`fomo-social-trading-perps`, start `2026-06-05`). The decoy is `0xb838e4d1c8bcf71fa8e63299d5aa3258c83d6adb` (`fomo-perps`), which is **onfomo.com, a different company**. Both return HTTP 200 from Hyperliquid's public dumps. The wrong one gives you 626 rows/day; the right one gives you 16,803. Building against the decoy yields, in the fomo-flow repo's phrase, "a plausible, useless dataset." **From three sampled days I pulled 56,373 fills across 3,789 distinct FOMO traders, each with per-fill price, size, counterparty and `closed_pnl`, for $0 and no key.**

**The "gas sponsor" generalises, but not the way the brief assumed — and the real answer is better.** There is no FOMO ERC-4337 paymaster carrying trade flow on EVM, because FOMO does not execute user trades from per-user EVM accounts: DeFiLlama's own adapter states fees "occur on Relay (EVM chains) [and] are counted on Solana, **where user balances are held**." What I found instead is stronger and was not in the brief: **every FOMO EVM wallet carries an EIP-7702 delegation to the same singleton contract, `0xe6Cae83BdE06E4c305530e199D7217f42808555B`, at the identical address with byte-identical code on Ethereum, Base, Arbitrum and Robinhood Chain.** That is a free, instant, `eth_getCode` membership test on any EVM chain. **Robinhood Chain is real and FOMO is on it** — chain ID 4663 (`0x1237`), verified live; 49 of the top 50 FOMO perp traders have a delegation there.

**The realistic coverage number is a tale of two questions.** Pseudonymous coverage — every trade attributed to a stable address, ranked, with PnL — is **~100%, free, today**. Named coverage using free automated resolvers is **~0%, and I measured it rather than assuming it**: ENS reverse-resolution over the top 60 FOMO perp traders returned **0/60**. Farcaster's free reverse index no longer exists (the public endpoint now requires auth; the hub has no reverse lookup and is 669 GB to self-host). **73.5% of these addresses have a nonce of exactly 1 on Base — meaning the only thing they have ever done is accept their delegation.** There is no prior history to resolve because there is no prior. The one naming channel that works is self-published referral links, and that is a manual harvest, not a resolver.

**Recommendation: build the per-chain enumeration layer described in §2. It is complete, free, and needs nobody's cooperation. Do not build a naming layer — not for legal reasons, but because the free resolvers measurably return zero on this population.**

---

## 1. FOMO'S HYPERLIQUID BUILDER ADDRESS — FOUND, VERIFIED, AND THE TRAP AROUND IT

### 1.1 The address

Primary source: DeFiLlama `dimension-adapters`, `factory/hyperliquid.ts` (fetched live, HTTP 200, 47,176 bytes; repo HEAD `014adca`, 2026-09-18). The file contains 136 builder addresses. Two match "fomo":

```ts
// line 271
"fomo-perps": { addresses: ["0xb838e4d1c8bcf71fa8e63299d5aa3258c83d6adb"] },

// line 674
"fomo-social-trading-perps": {
  addresses: ["0x2a2b6b093a9813fbd8cddae800c3d17d46460d17"],
  start: "2026-06-05",
  methodology: { Fees: "Builder code revenue from Hyperliquid Perps Trades.", ... },
  breakdownFees: true,
},
```

**`0x2a2b6b093a9813fbd8cddae800c3d17d46460d17` is fomo.family.** The `start` date of `2026-06-05` matches FOMO's June 2026 perps launch, and I confirmed it: the dump for `20260605` contains exactly **12 fills from 3 users** — a launch-day fingerprint.

The independent third-party repo `github.com/synsur/fomo-flow` reaches the same conclusion and flags the trap explicitly: *"Their daily files differ 20–50× in size. Building against the wrong one gives you a plausible, useless dataset."* Two independent sources agreeing is why I am confident.

**`0xb838e4d1…` is onfomo.com.** I confirmed this is a separate product: `docs.onfomo.com` describes a Hyperliquid-only "non-custodial liquidity layer... built for modular multi-DEX expansion," with no reference to fomo.family, social trading, or Solana. Its dumps contain `xyz:SOFTBANK` and other Trade.xyz equity perps.

### 1.2 Live verification, with a control

| Builder | 2026-09-15 | 2026-09-17 | 2026-09-18 | Verdict |
|---|---|---|---|---|
| `0x2a2b6b09…` **fomo.family** | 359,199 B → 9,156 fills / 1,296 users | 1,133,449 B → 30,414 fills / 2,275 users | 618,687 B → 16,803 fills / 1,620 users | **Correct** |
| `0xb838e4d1…` onfomo.com | 15,220 B → 303 fills | 46,294 B → 1,129 fills | 26,826 B → 626 fills | Different product |
| `0x0000…0001` (control) | — | — | **HTTP 403** | — |
| `0xdeadbeef…` (control) | — | — | **HTTP 403** | — |
| `0x2a2b…d170` (correct addr, 1 char changed) | — | — | **HTTP 403** | — |

**The control test is what makes this a verification rather than a guess.** Hyperliquid returns **403 for a non-builder address**, so a 200 with parseable LZ4 content is positive evidence that the address is a live builder. I ran the control precisely because report 07 got burned by accepting plausible-looking on-chain output without one.

### 1.3 What a query returns

Endpoint: `https://stats-data.hyperliquid.xyz/Mainnet/builder_fills/0x2a2b6b093a9813fbd8cddae800c3d17d46460d17/{YYYYMMDD}.csv.lz4` — lowercase address, case-sensitive, LZ4 frame format, no auth, no key, no rate limit encountered.

```
time,user,coin,side,px,sz,crossed,special_trade_type,tif,is_trigger,counterparty,closed_pnl,twap_id,builder_fee
2026-09-18T00:00:08Z,0xc3be5e9b509facaff8fac229a5ae10345d4ac6dd,ZEC,Ask,1466,0.73,true,Na,FrontendMarket,false,0xb46ae034d8ee4e9b40c42c0f5ecc99b0054fbe2d,0,0,0.53509
```

Aggregating my three sampled days: **3,789 distinct traders, 56,373 fills.** Top coins by fill count on 2026-09-18: BTC (1,807), NEAR (1,444), HYPE (1,340), UNI (1,311), PURR (1,031), SOL (779). Top trader by notional over the window ran $5.47M across 1,266 fills for **−$8,317** closed PnL; the best of the top 25 made **+$97,376** on $3.41M. That is a ranked, risk-attributable roster on day one, free.

**Freshness:** daily files, available the following day. **Availability risk: very low** — this is Hyperliquid publishing its own chain's data about its own builder programme; it is not scraper-backed and has no incentive to disappear.

---

## 2. PER-CHAIN ENUMERATION TABLE

The brief's hypothesis was that FOMO's Solana gas sponsor has a per-chain twin. It half-holds. Here is what is actually there.

| Chain | Enumerating address / contract | Mechanism | How verified (2026-09-20) | What a query returns |
|---|---|---|---|---|
| **Solana** | `AgmLJBMDCqWynYnQiPCuj9ewsNNsBJXyzoUhD9LJzN51` | **Gas sponsor / fee payer on every user tx** | Live RPC: balance **2,079.87 SOL**; fee payer on 5/5 sampled fee-wallet txs | Every FOMO Solana tx, via `signer = GAS_SPONSOR` predicate |
| **Solana** | `R4rNJHaffSUotNmqSKNEfDcJE8A7zJUkaoM5Jkd7cYX` | Fee recipient, native spot swaps | Live RPC: signatures seconds old (slot 448604447) | Every native Solana swap (USDC fee transfer) |
| **Solana** | `7uTT8Xi5RWXzy7h9XL244GRgEycDYDhLjr3ZyNdXi8pZ` | **Relay Depository vault** — cross-chain leg | Live RPC: balance 116.95 SOL | Every cross-chain buy (sponsored USDC deposit) |
| **Solana** | `proVF4pMXVaYqmy4NjniPh4pqKNfMmsihgd4wdkCX3u` | **Spot router program** | Live RPC: `executable: true`, owner `BPFLoaderUpgradeab1e…` | Every FOMO spot trade routes through it |
| **Hyperliquid L1** | `0x2a2b6b093a9813fbd8cddae800c3d17d46460d17` | **Builder code** | Public dumps 200 + 403 control (§1.2) | Per-user, per-fill, with `closed_pnl` |
| **Ethereum** (1) | `0xe6Cae83BdE06E4c305530e199D7217f42808555B` | **EIP-7702 delegate** (`Simple7702Account`) | `eth_getCode` = `0xef0100e6cae…`, 34/50 top traders | Membership test per address |
| **Base** (8453) | same | same | 46/50 top traders; delegate bytecode 7,280 chars | Membership test per address |
| **Arbitrum** (42161) | same | same | Delegate deployed (identical bytecode); only **3/50** traders delegated | Membership test; near-zero FOMO footprint |
| **Robinhood Chain** (4663) | same | same | Chain ID `0x1237` live; **49/50** top traders delegated | Membership test per address |
| **HyperEVM** (999) | — | — | `eth_chainId` = `0x3e7` live; **0/50** traders present | **No FOMO footprint** |
| **EVM generally** | *no FOMO paymaster found* | — | Base EntryPoint v0.7 scan, 400 blocks, 2,630 UserOps: top paymasters `0x7777…834c` (491), `0x2cc0…b633` (253); **none attributable to FOMO** | **UNVERIFIED that one exists; evidence suggests it does not** |

### 2.1 Why there is no EVM paymaster — and why that is the correct answer, not a gap

DeFiLlama's `dexs/fomo/index.ts` and `fees/fomo/index.ts` (both fetched live) state the architecture plainly:

> *"USDC trading fees on native Solana swaps plus trading fees on cross-chain trades via Relay. **Fees that occur on Relay (EVM chains) are counted on Solana, where user balances are held.**"*

FOMO holds user balances on Solana. EVM exposure is delivered by bridging through the **Relay Depository vault**, not by executing from a per-user EVM account. So there is no stream of FOMO UserOperations on Base or Ethereum to enumerate — and the on-chain data agrees: **73.5% of the top 200 FOMO traders have a Base nonce of exactly 1.**

That "1" is the tell. Under EIP-7702, accepting a delegation **increments the authority's nonce by one even when a sponsor pays the gas**. A nonce of exactly 1 plus a `0xef0100…` code value means: *this wallet was provisioned and delegated, and has never sent a transaction of its own.* These are dormant provisioned wallets, not trading accounts.

**Nonce distribution, top 200 FOMO Hyperliquid traders by notional:**

| Chain | n | nonce 0 (never touched) | nonce 1 (delegation only) | nonce 2–9 | nonce 10+ | **any independent activity** |
|---|---|---|---|---|---|---|
| Ethereum | 200 | 75 | 113 | 10 | 2 | **12 (6.0%)** |
| Base | 200 | 36 | 147 | 13 | 4 | **17 (8.5%)** |
| Robinhood Chain | 100 | 9 | 76 | 9 | 6 | **15 (15.0%)** |

*Robinhood Chain sample is n=100, not 200 — one RPC batch returned short and I did not re-run it. Reported as measured.*

**Control:** 50 deterministic never-used addresses returned nonce 0 on **all** chains (0/50 on Ethereum, Base, Arbitrum, Robinhood). The signal is real.

### 2.2 The EIP-7702 discovery

Every delegated FOMO address returns the same `eth_getCode` value on every chain:

```
0xef0100 e6cae83bde06e4c305530e199d7217f42808555b
└─7702─┘ └────────── delegate contract ──────────┘
```

`0xe6Cae83BdE06E4c305530e199D7217f42808555B` is the **ERC-4337 `Simple7702Account` singleton**, which Privy uses for embedded-wallet delegation. I verified the delegate contract itself is deployed with **byte-identical 7,280-character bytecode at the identical address on Ethereum, Base, Arbitrum and Robinhood Chain** — deterministic cross-chain deployment.

**Honest limitation, and it matters:** this contract is *generic Privy/4337 infrastructure*, not FOMO-specific. A `0xef0100e6cae…` code value proves "Privy embedded wallet with a 7702 smart account." It does **not** by itself prove "FOMO user." It is **necessary but not sufficient**. The way you make it sufficient is to seed from the Hyperliquid builder dump — which gives you a *confirmed* FOMO roster — and then use `eth_getCode` to test those addresses cross-chain. That is exactly what I did, and it is the correct direction of inference. Running it the other way (enumerate all 7702 delegations, call them FOMO users) would sweep in every Privy-backed app on the chain.

### 2.3 The generalisable lesson

**A product that abstracts away gas or routing must pay for it from an address, and that address is public.** FOMO cannot sponsor Solana gas without a funded sponsor account; it cannot earn builder fees on Hyperliquid without a registered builder address; it cannot give users smart-account UX without an on-chain delegation pointer. Each convenience the product sells its users is a public index it hands its observers. The abstraction layer *is* the enumeration handle.

Two corollaries worth keeping:

1. **The venue publishes what the app conceals.** FOMO deliberately does not show wallet addresses. Hyperliquid publishes every FOMO fill with the user's address and realised PnL, because *Hyperliquid's* builder programme needs to be auditable. Go up a level to the venue, not sideways to a vendor.
2. **Any competitor doing the same is equally enumerable.** DeFiLlama's `factory/hyperliquid.ts` is a directory of **136** builder addresses. Every one is a perp front-end whose entire per-user flow is downloadable on the same URL pattern, with the same control test to confirm it. This work is not FOMO-specific and should not be built FOMO-specifically.

---

## 3. THE FREE RESOLVER STACK, RANKED BY WHETHER IT WORKS

### Tier 1 — works, free, no key, build on these

| Source | Returns | Coverage | Freshness | Rate limit / cost | 6-month risk |
|---|---|---|---|---|---|
| **Hyperliquid `builder_fills`** | Per-user, per-fill: price, size, side, counterparty, `closed_pnl`, `builder_fee` | **100% of FOMO perp flow** | Daily (T+1) | None encountered; free | **Very low** — venue's own data |
| **Public Solana RPC** (`api.mainnet-beta.solana.com`) | Balances, signatures, parsed txs | 100% of Solana flow | Real-time (slot 448604447 live) | Public-node throttling | **Very low** |
| **Public EVM RPC** (publicnode, Robinhood official) | `eth_getCode` 7702 membership, nonce, balance | 100% membership test on a known roster | Real-time | 50-call JSON-RPC batches worked; archive queries refused | **Low** |
| **DeFiLlama `dimension-adapters`** (raw.githubusercontent) | All FOMO addresses + the exact SQL predicate | Authoritative | Repo HEAD 2026-09-18 | Free, unauthenticated | **Very low** — open source |
| **Hyperliquid `/info` API** | `perpDexs`, `clearinghouseState`, `maxBuilderFee` | Per-address live state | Real-time | Free POST | **Very low** |

### Tier 2 — works, but does not solve naming

| Source | Live result | Verdict |
|---|---|---|
| **Dune Spellbook** (`duneanalytics/spellbook`) | **Cloned, HEAD `014adca`.** 198 label SQL models. Categories: airdrop, bridge, dao, dex, infrastructure, institution, nft, social | **Report 07 was wrong that this is unreachable — it is fully available.** But: CEX labels cover 8 chains, **none of them Solana**; the only Solana label model is `labels_validators_solana.sql`. Social labels are ENS + Lens, **EVM only**. Useful for EVM counterparty labelling, useless for FOMO's population |
| **Farcaster hub** (`hub.pinata.cloud`) | HTTP 200, 825,996,209 messages, 1,683,068 FIDs, 669 GB | Alive and free, but **no reverse index**. Address→FID requires enumerating all FIDs (669 GB) or Neynar (key) |
| **OpenLabelsInitiative** | HTTP 200 (raw GitHub) | Open label schema; EVM-oriented |
| **`api.ensideas.com`** | HTTP 200, correct on `vitalik.eth` | Works perfectly. Returns nothing for this population — see §4 |

### Tier 3 — dead, gated, or does not contain what it advertises

| Source | Live result | Note |
|---|---|---|
| `api.farcaster.xyz/v2/user-by-verification` | `{"errors":[{"message":"Authentication required"}]}` | **Regression** — this was the free reverse resolver. It is gone |
| **Solana Tracker** `/leaderboard/fomo` | HTTP 200, 105,864 B — **zero Solana addresses in the HTML** | Client-rendered; `data.solanatracker.io` returns **401**. Advertises "top Solana wallets trading on FOMO" but the page ships no wallets |
| `sns-api.bonfida.com` | `/v2/user/domains/{addr}` → HTTP 200 `{}`; other paths 404/500 | Alive but empty for tested addresses |
| `sns-sdk-proxy.bonfida.workers.dev` | 404 | Still effectively dead |
| `pro-api.solscan.io` | **401** | Key required |
| `public-api.solscan.io` | **404** | Retired |
| `api.solana.fm` | **502** | Down |
| `api.solanabeach.io` | **522** | Down |
| `api.step.finance` | Proxy `502` (policy denial) | **UNVERIFIED** |
| Arkham entity page | **403** | Bot-protected; not worked around |
| Robinhood Chain Blockscout | **403** Cloudflare challenge | Bot-protected; not worked around. **UNVERIFIED** |
| `api.routescan.io` | **400** on tested path | **UNVERIFIED** — may work with correct params |
| GitHub REST API | **403** (session scope) | Worked around legitimately via `raw.githubusercontent.com` + `git clone` |

### 3.1 FOMO-adjacent third-party sources

The brief asked me to find sites independently republishing FOMO data. Reachable, HTTP 200, but **none exposed a handle→wallet mapping in what I could verify unauthenticated**:

- `dune.com/impossiblefinance/fomo-dashboard` — 200, 80,704 B (Dune dashboards render client-side; underlying queries are free to fork with a Dune account)
- `blockworks.com/analytics/fomo/fomo-perps-volume-on-hyperliquid` — 200, 352,945 B
- `app.coinmarketman.com/hypertracker/builder/0x2a2b…` — 200, 15,604 B (HyperTracker indexes builders by address; **this is how I first surfaced a FOMO builder candidate**)
- `github.com/synsur/fomo-flow` — open-source, independently derived the same addresses, cites the two-builder trap

**`dune.tryfomo.*` is worth one line.** DeFiLlama's fees adapter queries `dune.tryfomo.fomo_relay_fees` with columns `fee_period`, `platform_fees`, `referral_fees`, `synced_at`. That namespace is **FOMO's own Dune team uploading its own data** — a first-party published dataset, not a scrape. I did not query it (no Dune account in this session) — **UNVERIFIED**, but it is the single most promising unexplored lead in this report and costs nothing to check with a free Dune account.

---

## 4. THE COVERAGE NUMBER

**Two numbers, and conflating them is what went wrong last time.**

### Pseudonymous coverage: ~100%

| Layer | Coverage | Measured? |
|---|---|---|
| Perp trades → address, with realised PnL | **100%** of builder-routed flow | **Yes** — 56,373 fills, 3,789 traders, 3 days |
| Solana spot trades → address | **~100%** via `signer = GAS_SPONSOR` | **Yes** — fee payer matched on 5/5 sampled txs |
| Cross-chain membership per address | **100%** via `eth_getCode` on a seeded roster | **Yes** — 4 chains, control-tested |

### Named coverage: ~0% from free automated resolvers

| Resolver | Result on the real FOMO population | Confidence |
|---|---|---|
| **ENS reverse** (`api.ensideas.com`) | **0 / 60** top traders resolved | **High — measured, 0 request failures** |
| **Farcaster reverse** | No free reverse index exists any more | High |
| **Dune Spellbook social labels** | ENS + Lens only, EVM; no Solana | High |
| **SNS / `.sol`** | N/A for EVM perp addresses; empty for tested Solana addresses | Medium |
| Self-published `fomo.family/r/{handle}` links | Not re-measured this pass | **Inherited estimate, 15–25%, UNVERIFIED** |

**Headline: of FOMO's top traders you can rank, risk-adjust and follow 100% of them today for $0; you can automatically attach a name to approximately none of them.** The 0/60 ENS result is the number to quote, because it is measured on the actual population rather than extrapolated from a general one.

The structural reason, now proven rather than asserted: **73.5% of these addresses have done exactly one thing ever — accept a delegation.** Report 07 inferred "no prior identity" from FOMO's Privy architecture; this pass confirms it from the chain, and gives the fingerprint (`nonce == 1 && code == 0xef0100e6cae…`) that makes it checkable.

### 4.1 Where report 07's dead end was genuinely wrong

The brief asked me to re-examine "Privy wallets have no prior identity" as a finding rather than a dead end. Results:

- **"Do FOMO wallets have cross-chain presence?"** — **Yes, and report 07 missed it entirely.** 49/50 on Robinhood Chain, 46/50 on Base. But it is provisioning, not behaviour.
- **"Is there a deterministic derivation or on-chain registry?"** — **Yes.** The EIP-7702 delegation to a single singleton address, identical across chains. This is a real, free, cross-chain linkage primitive and it is the most useful thing in this report after the builder address.
- **"Do funding edges exist?"** — For the **6–15% with nonce ≥ 2**, yes in principle, and that is the cohort to investigate. I did **not** trace their funding sources this pass — **UNVERIFIED and the clearest remaining lead.** Note the honest framing: 8.5% of 200 is 17 addresses. Even a perfect funding-edge trace on all of them moves named coverage from ~0% to single digits.
- **"Do users move funds out to identity-bearing wallets?"** — **UNVERIFIED.** Not tested.

### 4.2 One warning that survives from report 07, reconfirmed

Naive Solana RPC extraction still does not work. Parsing token-balance owners out of FOMO fee transactions returned **9–11 owners per transaction**, with `ARu4n5mFdZogZAravu7CcizaojWnS6oqka37gdLT5SZn` appearing in **5 of 5** sampled transactions — a router or pool, not a user. **Use the indexed path** (Allium or Dune, with the adapter's exact `to_address IN (FEE_WALLET, RELAY_VAULT) AND signer = GAS_SPONSOR AND transfer_type = 'spl_token_transfer'` predicate, resolved at token-account-*owner* level). The Hyperliquid side needs no such care — it arrives clean.

---

## APPENDIX — LIVE VERIFICATION LOG (2026-09-20)

| Check | Result |
|---|---|
| DeFiLlama `factory/hyperliquid.ts` | 200, 47,176 B — 136 builders; both FOMO entries located |
| DeFiLlama `dexs/fomo/index.ts` | 200, 4,752 B — 4 Solana addresses + full Allium query |
| DeFiLlama `fees/fomo/index.ts` | 200, 3,861 B — Relay architecture + `dune.tryfomo.fomo_relay_fees` |
| HL dump `0x2a2b…d17` ×3 days | 200 — 9,156 / 30,414 / 16,803 fills; 3,789 distinct users |
| HL dump `0x2a2b…d17` 20260605 | 200 — 12 fills / 3 users (launch day, matches declared `start`) |
| HL dump `0xb838e4d1…` ×3 days | 200 — 303 / 1,129 / 626 fills (onfomo.com) |
| HL dump, 3 invalid addresses | **403** — control establishes 200 is positive evidence |
| HL `POST /info {"type":"perpDexs"}` | 200 — Trade.xyz `xyz` dex, deployer + feeRecipient |
| Solana RPC `AgmLJ…` (gas sponsor) | 200 — **2,079.87 SOL** |
| Solana RPC `R4rNJ…` (fee wallet) | 200 — signatures at slot 448604447, seconds old |
| Solana RPC `7uTT8…` (Relay vault) | 200 — 116.95 SOL |
| Solana RPC `proVF4pMX…` | 200 — **`executable: true`**, BPFLoaderUpgradeable |
| Solana fee-wallet tx sample (n=5) | Gas sponsor was fee payer on **5/5**; 9–11 token owners/tx (contaminated) |
| `eth_chainId` ×5 chains | ETH `0x1`, Base `0x2105`, Arbitrum `0xa4b1`, **Robinhood `0x1237`**, HyperEVM `0x3e7` |
| `eth_getCode` top-50 traders | ETH 34/50, Base 46/50, **Robinhood 49/50**, all `0xef0100e6cae83b…` |
| Delegate contract, 4 chains | 7,280-char **byte-identical** bytecode at same address |
| Nonce distribution, top 200 | Base: 147 at nonce 1 (73.5%), 17 with nonce ≥2 (8.5%) |
| Virgin-address control, 4 chains | **0/50 on every chain** |
| Base EntryPoint v0.7, 400 blocks | 2,630 UserOperationEvents; **no FOMO-attributable paymaster** |
| ENS reverse, top 60 traders | **0/60**, 0 failures |
| `hub.pinata.cloud/v1/info` | 200 — 825,996,209 messages, 1,683,068 FIDs, 669 GB |
| `api.farcaster.xyz/v2/user-by-verification` | **Authentication required** (regression vs report 07) |
| Dune Spellbook clone | HEAD `014adca` — 198 label models; no Solana CEX/social labels |
| Solana Tracker `/leaderboard/fomo` | 200, 105,864 B, **0 addresses**; API 401 |
| **Could not verify** | `api.step.finance` (proxy 502); Robinhood Blockscout (403 CF); Arkham (403); `api.routescan.io` (400); `dune.tryfomo.*` (no Dune account); funding-source traces for the nonce≥2 cohort |

### Sources

- [DeFiLlama dimension-adapters](https://github.com/DefiLlama/dimension-adapters) — `factory/hyperliquid.ts`, `dexs/fomo/index.ts`, `fees/fomo/index.ts`
- [Hyperliquid builder codes docs](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes) · [HyperTracker builder profile](https://app.coinmarketman.com/hypertracker/builder/0x2a2b6b093a9813fbd8cddae800c3d17d46460d17)
- [synsur/fomo-flow](https://github.com/synsur/fomo-flow) — independent corroboration of the two-builder trap
- [EIP-7702](https://ethereum.org/roadmap/pectra/7702/) · [Privy EIP-7702 integration](https://docs.privy.io/recipes/react/eip-7702) · [pimlicolabs/permissionless-privy-7702](https://github.com/pimlicolabs/permissionless-privy-7702) — `Simple7702Account` singleton
- [Robinhood Chain docs](https://docs.robinhood.com/chain/connecting) · [robinhood-chain-kit](https://github.com/mkrz-x/robinhood-chain-kit) — chain ID 4663
- [duneanalytics/spellbook](https://github.com/duneanalytics/spellbook) · [docs.onfomo.com](https://docs.onfomo.com/) (the decoy) · [Solana Tracker FOMO leaderboard](https://www.solanatracker.io/leaderboard/fomo)
