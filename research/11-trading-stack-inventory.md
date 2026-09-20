# Trading-Stack Code Inventory — `F:\GetMoney\trading` (Lazydayz137/trading-stack)

Date: 2026-09-19. Read-only pass over the working tree exactly as checked out (uncommitted/unpushed
included), HEAD `da13be1` on `feat/hl-picks-pipeline`. All claims below are `path:line` verified in
code unless marked **[DOC-ONLY, unverified]**. Two prior in-repo research docs already cover venue
economics in depth and are cited rather than re-derived: `VENUE_HL_VS_ASTER.md` and
`docs/HYPERLIQUID-EXPANSION-PLAN.md`.

## VERDICT

**This repo has no live Hyperliquid or Aster execution — no order placement, no signing, no
position management for perps on either venue.** What it has instead is (1) a genuinely rigorous
**research/backtest engine** for HL perp signals with a formal 8-gate validation battery and
byte-pinned reproducibility, whose honest conclusion so far is that every signal tested (TSMOM,
reversal, OI-inverse, crowding, taker-inverse) is **NOT VALIDATED**; (2) **read-only data collectors**
for HL and Aster funding/OI (HL collector was dead 22 days as of the 2026-08-22 doc, unknown current
status — not re-verified this pass); (3) a small **paper-only** LangGraph multi-agent "fund" wired to
Aster data, essentially a toy (3 logged trades total); (4) a separate, unrelated, and far more mature
**live execution system for a different venue entirely** — a Solana/Meteora DLMM LP copy-bot with a
real kill switch, hard-cap gating, and devnet-proven signing path — which is the best *pattern* to
copy for a future HL execution client, not reusable code for it; (5) a paper-only GMGN memecoin
smart-money-cluster engine with 33 logged trades. For a team building Hyperliquid-first perps, the
reusable assets are the backtest/validation harness and the risk-gating *pattern*; everything
HL-order-execution-shaped must be built from scratch, confirming the same gap `docs/HYPERLIQUID-EXPANSION-PLAN.md:130-137` already identified a month ago and which this pass found still open.

---

## 1. Venue adapters

### Hyperliquid — data only, no execution
- No HL order-placement, signing, or agent-wallet code exists anywhere in the tree. Grep for
  `sign_l1_action|eth_account|place_order|exchange\.order|ApproveBuilderFee` over all `.py`/`.ts`
  matched **zero HL files** (only two Aster scripts, see below).
- `perps/perps_collector.py:40-57` — `snap_hyperliquid()`, public unauthenticated
  `POST https://api.hyperliquid.xyz/info {"type":"metaAndAssetCtxs"}` every 15 min
  (`perps/perps_collector.py:26-27`). Captures funding_hr, oi_base/usd, mark, oracle, premium,
  day_ntl_vlm, max_lev per coin, written to `perps/data/hyperliquid/<date>.parquet`
  (`perps/perps_collector.py:74-84`, append-on-existing-file pattern). REST only, no WebSocket in
  this file. No rate-limit handling code (unauthenticated public endpoint, no backoff/retry logic
  visible). Collector's live/dead status as of 2026-08-22 was "DEAD 22 days" per
  `docs/HYPERLIQUID-EXPANSION-PLAN.md:198` — **not independently re-verified this pass** (out of
  scope: would require a network call).
- `hl_exec/` is a **backtest/research** tree (`combo/`, `walkforward.py`, `portfolio.py`,
  `expectancy.py`, `test_signals.py`), not an execution client — see §5.
- Builder-code plumbing: **none in code.** `docs/HYPERLIQUID-EXPANSION-PLAN.md:58` and
  `VENUE_HL_VS_ASTER.md:26-33` document HL's builder-fee mechanics (0.1%/10bp perps cap, `{"b":
  builder,"f":fee}` order field, `ApproveBuilderFee` signature, activate at ≥100 USDC) as
  **[DOC-ONLY, unverified in code]** — pure research, nothing implements it.
- Spot vs perp: collector reads perp market data only (`metaAndAssetCtxs`); no spot-market code
  found for HL anywhere.

### Aster — read-only auth probes + public funding feed, no order execution
- `_aster_v3sign.py:1-49` and `_aster_pos.py:1-52` (repo root, one-off scripts) — the only code in
  the repo that **signs** anything for a perp venue. EIP-712 signing via `eth_account`
  (`_aster_v3sign.py:8,26-34`), reading creds (`user`, `signer`, `private_key`) from
  `aster_mcp.config.ConfigManager().get_account("main")` (`_aster_v3sign.py:9,12`) — an external
  package, not vendored in this repo; credential file location not found in this tree (likely
  outside it — **flagging only, not tracked to resolution here** since it's out of this repo's
  scope). Both scripts only call `GET /fapi/v3/balance` and `GET /fapi/v3/positionRisk`
  (`_aster_v3sign.py:47-48`) — **read-only account state, no order endpoints called anywhere.**
- `agent_fund/feeds/aster_funding.py:1-54` — public, unauthenticated
  `GET https://fapi.asterdex.com/fapi/v1/premiumIndex?symbol=...` (`aster_funding.py:20,30-31`),
  no keys, derives a crude long/short "bias" from funding sign (`aster_funding.py:41`). REST only.
- `perps/perps_collector.py:59-72` — `snap_aster()`, public `GET
  https://fapi.asterdex.com/fapi/v1/premiumIndex` (all symbols), written to
  `perps/data/aster/<date>.parquet`.
- No order types, no builder-code plumbing, no spot coverage found for Aster in code. Aster's
  "Aster Code" builder-fee program is documented only in `VENUE_HL_VS_ASTER.md:26-33`
  **[DOC-ONLY]**, cap explicitly flagged there as unverified ("NOT published in reachable docs").
- No WebSocket client for Aster found; all Aster code is REST polling. No explicit rate-limit
  handling code found (Aster's documented limits are cited in `VENUE_HL_VS_ASTER.md:19` as prose
  only).

### GMGN — paper-only Solana memecoin smart-money engine
- `smcf/smcf_engine.py:1-6` — docstring states explicitly: **"PAPER ONLY: no GMGN_PRIVATE_KEY, no
  swap calls anywhere in this file."** Confirmed by grep: no swap/order call in the file.
- Reads market/wallet data by shelling out to an external `gmgn-cli` binary
  (`smcf/smcf_engine.py:68-79`), with a local IP-ban backoff (`_gmgn_ban_until`, 360s pause on
  rate-limit, `smcf_engine.py:65-79`) — the only rate-limit handling found across all three venues.
  `gmgn-cli` itself is not vendored in this repo (external tool).
- Paper trade ledger at `smcf/trades.csv` — **33 rows** (header + 32 trades as of this pass,
  `wc -l` = 33), e.g. `smcf/trades.csv:2-3` shows a +1.3% smart-exit and a -29.5% stop. Live
  `smcf/positions.json` (1.4KB) and `smcf/state.json` track current paper book.
- No live GMGN execution path exists in this repo; the user's stated GMGN scope (memecoins) is
  covered here only as signal generation + paper simulation.

### Other venues touched (context, not in the requested venue set)
- **Solana Meteora DLMM** via `lp_copy_bot/` — real, separate live-capable system (Ed25519/SPL
  signing, not EIP-712), see §2 and §5.
- **IBKR (equities)** — `equities_collector/` and `docs/HYPERLIQUID-EXPANSION-PLAN.md:15` mention
  "IBKR is already wired for equities" **[DOC-ONLY, not verified this pass — out of scope]**.
- **Binance** — used only as a free data source in `hl_exec/combo/binance_oi_lib.py` and sibling
  `binance_*_score.py` files for cross-venue OI/taker research signals, not as a trading venue.

---

## 2. Execution and risk

**No perp execution/risk engine exists for HL, Aster, or GMGN.** What exists is split between
backtest-only risk modeling (HL) and a real, unrelated live-execution risk gate (Solana LP bot).

- **Backtest liquidation/margin model (HL, research only):**
  `reports/picks/RESULT-TSMOM-LIQMODEL.md:1-22` documents a real bug-fix: the old backtest used a
  "simultaneous worst-case" liquidation model that overstated liquidation incidence 10–18x; the
  corrected model is bar-by-bar, per-asset maintenance-margin (`mm_j = 1/(2*maxlev_j)`, asset-
  specific, not target-leverage-specific — `RESULT-TSMOM-LIQMODEL.md:19`). This is simulation code
  in `hl_exec/combo/` (the commit `04afc6d fix(combo): correct the TSMOM portfolio liquidation
  model, bar-by-bar + per-asset margin`), not a live account margin checker.
- **Backtest position sizing (HL, research only):** `hl_exec/portfolio.py:48-68` implements
  equal/inverse-vol/rank-proportional weighting across a top-N ranked universe with a
  non-overlapping rebalance grid; `hl_exec/portfolio.py:27` charges 4.5bp taker cost per unit of
  turnover. No leverage cap logic here beyond what `combo/core.py` enforces at the market level
  (`hl_exec/combo/core.py:20-22`: 25 of 102 markets cap at 3x, 43 at 5x, "68 of 102 cannot reach
  10x at all" — markets ineligible at a target leverage are dropped from the simulation rather than
  scored as tradeable, `core.py:22`).
- **Kill switch / daily loss halt exist, but only for the Solana LP bot, not any perp venue:**
  `lp_copy_bot/src/exec/liveGate.ts:9-22` — compiled-in hard caps
  (`HARD_CAP_POSITION_SOL=1.0`, `HARD_CAP_TOTAL_DEPLOYED_SOL=1.05`,
  `HARD_CAP_MIN_RESERVE_SOL=0.05`, `DAILY_LOSS_HALT_SOL=0.3`, `liveGate.ts:39-44`),
  abort-not-clamp design (`liveGate.ts:15-16`), LIVE defaults false. `docs/runbooks/go-live-checklist.md:65-69`
  documents a working `scripts/kill.ts` that disarms the executor and closes all open positions
  within ~2s, verified live per that runbook. **This is the strongest reusable risk-gating pattern
  in the repo** (three independent gates: feature flag, executor arm, funded wallet —
  `docs/runbooks/go-live-checklist.md:3-5`) but it is Solana/SPL-signing specific and would need a
  from-scratch HL/EIP-712 port, exactly as `docs/HYPERLIQUID-EXPANSION-PLAN.md:125,137` already
  concluded ("directly portable in pattern, not in code" / "HL-specific M1/M2 gate with its own
  caps and CI grep" must be built).
- **Toy deterministic risk cap (Aster-wired paper fund):** `agent_fund/agents/risk_manager.py:1-24`
  — a non-LLM node computing `cap_usd = portfolio_value * max_risk_fraction * vol_scalar` off a
  **stubbed** volatility input (`risk_manager.py:9-13`: "Inputs (synthetic)"), default portfolio
  $10,000, default max risk fraction 20%, vol reference 2% (`risk_manager.py:31-38`). Not fed by
  any real position/margin data — this is a demo of the *shape* of a hard-cap risk node, not a
  working risk system. `agent_fund/paper_track.jsonl` has **3 lines total** — e.g. a short ZEC at
  $504.15, $80 notional, dated 2026-06-16 (`paper_track.jsonl` last line) — essentially unused.
- **Funding-cost accounting:** present only inside the HL backtest (`hl_exec/combo/core.py:18-22`
  computes `FUNDING_HR_MEDIAN` from the archive, used as a cost drag in simulation). No live
  funding accrual/accounting code for any venue.
- **Reconciliation of intended vs. achieved fills:** exists only for the Solana LP bot
  (`exits_record.jsonl` written only from real confirmed closes, per
  `docs/runbooks/go-live-checklist.md:94`). No equivalent for HL/Aster/GMGN — there is nothing live
  to reconcile against.
- **Liquidation-distance / margin checks on a live account:** not found for any perp venue. The
  read-only Aster probes (`_aster_pos.py:49-51`) print `liquidationPrice` from Aster's own API
  response for informational display only — not used in any automated check.

---

## 3. Strategies and signals

All HL strategy work lives under `hl_exec/` and `reports/picks/`, and is **research-stage, not
live** — every tested hypothesis in the pinned corpus currently reads NOT VALIDATED:

| Signal | Horizon/cadence | Inputs | Status | Evidence |
|---|---|---|---|---|
| TSMOM / cross-sectional momentum (`volmom_24h`, `breakout_168h`, `breakout_72h`) | k=1–72h rebalance grid, 4h bars, 833-day window | OHLCV panel, RSI/MACD/ADX/Supertrend/ATR/Bollinger/Donchian features from `hl_exec/combo/core.py` | **NOT VALIDATED** — primary cell 4h-833d expectancy **−2.91% on margin**, day-clustered 95% CI entirely below zero, 6/8 gates fail | `reports/picks/RESULT-4h-833d.md:9-14` |
| TSMOM (corrected liq model) | k=72h | same panel | **NOT VALIDATED** — momentum flips from −1.65%/day to +0.076%/day (statistically indistinguishable from zero) after the liquidation-model fix; 4/8 gates pass | `reports/picks/RESULT-TSMOM-LIQMODEL.md:1-9,25-33` |
| Reversal (inverse of TSMOM) | k=72h | same panel | **NOT VALIDATED** — −0.257%/day, never crosses zero | `reports/picks/RESULT-TSMOM-LIQMODEL.md:1-9` |
| Binance OI-inverse / crowding-inverse / taker-inverse | various | Binance OI, taker-buy/sell ratio (cross-venue proxy) | **NOT VALIDATED / DRIFT, not signal** (per commit `0a55843`) | `reports/picks/RESULT-BINANCE-OI-INVERSE.md`, `RESULT-BINANCE-CROWDING-INVERSE.md`, `RESULT-BINANCE-TAKER-INVERSE.md` (titles read; full text not re-parsed this pass) |
| Discretionary "PICKS" (ETH/GOLD/SOL/AAVE/BTC/NVDA-complex/SPCX/CL-BRENTOIL/ZEC longs/shorts) | 12–48h | Nansen leaderboard consensus, real HL OHLCV, same TA feature library, live trade history via Nansen profiler | **Manual, discretionary, human-read — not automated, no backtest attached.** Explicitly notes "No copy-trade/execution path exists in the Nansen CLI for Hyperliquid perps" | `reports/picks/PICKS.md:1-11,84` |
| SMCF (Smart-Money Cluster Front-Run, GMGN/Solana memecoins) | ~30s cycle, 15-min cluster window | GMGN wallet feeds + "own roster" of PnL-qualified wallets + token-side trench scan | **Paper only**, 33 logged trades, bankroll $200 (`smcf_engine.py:31`) | `smcf/smcf_engine.py:1-6,31`, `smcf/trades.csv` |
| Aster-wired LangGraph paper fund (bull/bear debate, funding/flow/technical/quant analysts) | undated | Aster funding feed, Nansen flow, synthetic technicals | **Paper only, 3 trades total, essentially inactive** | `agent_fund/paper_track.jsonl`, `agent_fund/graph.py:1-21` |
| Meteora DLMM LP copy strategy (Solana, separate venue) | continuous, geyser-driven | leader-wallet consensus via geyser | **Live-capable**, gated behind three flags, at least one real mainnet open→close proven per runbook | `docs/runbooks/go-live-checklist.md:44-72` — **[runbook claim, live execution state not independently re-verified this pass]** |

Method rigor worth flagging as reusable: `reports/picks/RESULT-4h-833d.md:1-8` and
`RESULT-TSMOM-LIQMODEL.md` show a genuine **8-gate validation battery** (sample size, block
breadth, expectancy, day-clustered bootstrap CI, noise-baseline comparison, liquidity split,
backward-pin stability, funding-sensitivity stress) plus **byte-level pin/verify reproducibility**
(`data_sha`, `code_sha`, `core_sha256` in `RESULT-4h-833d.md:8-13`, verified via `hl_exec/combo/_s4h/pin.py --verify`). This is the single most reusable piece of engineering in the repo for a team that wants disciplined signal validation before risking capital.

---

## 4. Data

- **HL perp market data:** `perps/perps_collector.py:74-84` writes one parquet per venue per day
  (`perps/data/<venue>/<YYYY-MM-DD>.parquet`), append-by-concat-on-existing-file
  (`write()`, `perps_collector.py:74-83`: reads existing file, `pd.concat`, rewrites whole file —
  **not a true append-only format**; each snapshot cycle rewrites the day's file). Row schema:
  `ts, venue, coin, funding_hr, oi_base, oi_usd, mark, oracle, premium, day_ntl_vlm, max_lev`
  (`perps_collector.py:47-54`). `ts` is `int(time.time())` at snapshot time
  (`perps_collector.py:87`) — this is an observation timestamp, not an event timestamp; no
  as-of/point-in-time distinction beyond that single field.
- **HL candle history (backtest corpus):** `hl_exec/data/` contains `candles/`, `candles_15m/`,
  `candles_4h/`, `candles_90d_backup/`, `candles_delisted/`, `funding/`, `oi/`, `venue/`, plus a
  `MANIFEST.json`/`MANIFEST.tsv` integrity ledger. Manifest carries `as_of_ms`, `as_of_iso`, `host`,
  `file_count` (711), `total_final_bars` (5,608,971), and three sha256 hashes (`roll_up_sha`,
  `code_sha`, `script_sha256`) — `hl_exec/data/MANIFEST.json:1-9`. This is a genuinely disciplined,
  hash-pinned data corpus, the best-instrumented data asset in the repo.
- **OI is NOT backfillable** (no HL historical endpoint) — confirmed in
  `docs/HYPERLIQUID-EXPANSION-PLAN.md:108,177,200`: "OI for those 22 days is permanently lost. Not
  recoverable by any endpoint." **[DOC claim — matches HL API's documented shape, not
  independently re-verified against a live call this pass, per the read-only/no-paid-API
  constraint on this task]**. Funding **is** backfillable to venue inception
  (`fundingHistory`, `HYPERLIQUID-EXPANSION-PLAN.md:177`).
- **Aster:** same collector pattern, `perps/data/aster/<date>.parquet`, schema
  `ts, venue, coin, funding_8h, mark, index, premium, next_funding`
  (`perps/perps_collector.py:66-71`).
- **GMGN/smcf paper state:** `smcf/trades.csv` (CSV, append via external write not verified as
  atomic), `smcf/positions.json` and `smcf/state.json` (whole-file JSON, overwritten each cycle —
  not append-only by construction).
- **Book/trade tape/liquidations:** **not collected at all for HL** as of the 2026-08-22 doc —
  `docs/HYPERLIQUID-EXPANSION-PLAN.md:104-112` states L2 book, trade tape, and liquidations have no
  historical endpoint and nothing in the repo records them live (WS listener explicitly listed as
  "must be built from scratch," `HYPERLIQUID-EXPANSION-PLAN.md:134`). **Not re-verified this pass
  whether a WS recorder was since built** — no WS client code was found in this session's greps of
  the main tree, so the gap most likely still stands, but that is an absence-of-evidence read, not
  a direct negative confirmation.

---

## 5. Backtesting / paper-trading machinery, and fidelity to the live path

- **`hl_exec/combo/core.py`** is the shared backtest library (`core.py:1-6`: "Every search agent
  imports THIS. One panel loader, one feature set, one simulator, one evaluator, one noise
  generator, one search harness"). Enforces **causality** via a self-check that recomputes every
  feature on a truncated series and asserts the value at the current row is unchanged
  (`core.py:12-14`). Costs are calibrated to venue reality: `COST = 0.0009` round-trip
  (`core.py:18-19`), independently checked against HL's published fee schedule in
  `RESULT-4h-833d.md:16-27`, which also flags a **known, honestly-disclosed inaccuracy**: HL raised
  taker fees from 0.035%→0.045% on 2025-04-30, so the frozen constant overcharges roughly the first
  42% of the pinned 833-day window (`RESULT-4h-833d.md:26-31`) — direction of the error is
  conservative (can't manufacture a false positive).
- **Fidelity gap vs. a live path:** the simulator has **no slippage/depth model**
  (`hl_exec/portfolio.py:20`: "No slippage/depth: fills assumed at the close, at the taker fee"),
  **no funding in the ranking-study path** (`portfolio.py:19`), and market eligibility is
  leverage-gated at the venue's actual per-asset cap (`core.py:20-22`) rather than assumed uniform.
  There is **no live order-execution path for HL to compare the simulator against at all** — so
  "how closely the simulated path matches the live path" is currently a non-question for HL: there
  is no live path yet. For the Solana LP bot, the closest thing to a paper/live fidelity check is
  `scripts/dryrun-open.ts --live` (`docs/runbooks/go-live-checklist.md:13-27`), which replays the
  latest real consensus signal through the actual SDK call
  (`initializePositionAndAddLiquidityByStrategy`) as an unsigned, simulated transaction against
  live on-chain state — a genuine paper/live fidelity check, but for a different venue.
- **SMCF paper engine** (`smcf/smcf_engine.py`) simulates a $200 bankroll against live GMGN feed
  data with real entry/exit logic (`trades.csv` shows real stop-outs and smart-exits) but no swap
  execution — closest thing to a live-fidelity paper loop for the GMGN venue, unvalidated by any
  formal statistical gate (unlike the HL corpus).
- **agent_fund** debate graph (`agent_fund/graph.py:1-21`) is a LangGraph pipeline
  (funding→flow→technical→quant analysts → bull/bear debate → risk_manager → portfolio_manager)
  that writes to `paper_track.jsonl`, but with only 3 logged trades and a stubbed volatility input
  to its risk cap (§2), it reads as a scaffold/demo rather than an operating paper-trading system.

---

## 6. Nansen / smart-money / FOMO integrations

- **`agent_fund/feeds/nansen_flow.py`** — present, referenced by `funding_analyst.py`,
  `quant_analyst.py`, `technical_analyst.py` (all under `agent_fund/agents/`), and a
  `flow_snapshot.json` / `_sample_flow_snapshot.json` fixture pair exists alongside it
  (`agent_fund/feeds/`). Content of `nansen_flow.py` not read in full this pass (23 files repo-wide
  reference "nansen" — time-boxed; the file's existence and wiring into three agent modules is
  confirmed by grep/`ls`, its internals were not line-verified).
- **`reports/picks/PICKS.md`** — the clearest live Nansen usage in the repo: leaderboard
  consensus (19 wallets after filtering), per-token screener at multiple `--days` windows, and
  `profiler perp-trades` on top holders (`PICKS.md:5,9`). Explicitly notes a real API-surface limit
  found by direct inspection: **"No copy-trade/execution path exists in the Nansen CLI for
  Hyperliquid perps"** (`PICKS.md:84`).
- **`docs/HYPERLIQUID-EXPANSION-PLAN.md:46-71`** documents (as research, not code) that Nansen's
  own HL trading endpoints are credit-free but carry a **1–8bp builder-fee markup** stacked on HL's
  base fee, and recommends **HL direct execution, Nansen for signal only** — a recommendation with
  no corresponding code yet since no HL execution exists.
- **`nansen.env`** exists at `lp_copy_bot/.secrets/nansen.env` (path only, not opened — per task
  instruction on secrets).
- **GMGN "smart money"** is the vendor-native concept behind `smcf/smcf_engine.py` (Smart-Money
  Cluster Front-Run) — see §1/§3. This is the repo's most mature "smart-money flow" *strategy*
  implementation (real paper P&L, real quality-wallet gating logic per
  `smcf_engine.py:292` referencing "GMGN smart counts are CUMULATIVE... verify quality wallets
  STILL HOLD"), even though it targets GMGN/Solana memecoins rather than HL perps.
- No standalone "FOMO" scoring/integration module was found searching the main tree this pass
  (out of scope beyond a grep check; not exhaustively investigated — a prior doc in this same
  research series, `07-fomo-intel-inventory.md`, may already cover this ground more fully and
  wasn't re-read here to stay in budget).

---

## 7. How it is run and deployed

**[Everything in this section is docs/config-derived except where a running process/systemd unit
file is directly cited; code cannot confirm a doc's claim about current live state without a
network/host check, which this read-only, no-paid-API task explicitly excludes.]**

- **Perps collector placement:** `perps/perps-collector.service` (systemd unit file present in the
  repo) — `perps/perps_collector.py:24-26` reads `PERPS_DATA_ROOT` from env, described as
  "env-driven so the same file runs on any host (the VM unit sets `PERPS_DATA_ROOT`)." Commit
  `ce26a4e feat(perps): migrate perps collector to VM, env-driven data root (#82)` shows this
  migration happened. **Current live/dead status of the collector was not re-verified this
  pass** (would require a live host check, out of scope).
- **Solana LP bot:** `docs/runbooks/go-live-checklist.md:8-9` names a specific box (`ssh -i
  ~/.ssh/meteora_ch lazydayz137@100.90.151.72`), repo path `~/trading-stack/lp_copy_bot`, systemd
  user unit `lp-warm-standby.service`, and a specific hot wallet address. Deployment discipline is
  git-based (`docs/runbooks/box-deployment-state.md:52-59`: fetch/reset-hard + surgical config
  restore, replacing an earlier scp-based deploy pattern that had drifted). **[DOC, 2026-06-26
  dated — staleness relative to today, 2026-09-19, not re-verified]**.
- **SMCF dashboard/cockpit:** `web/package.json` names the project `smcf-mirror`, a Vercel-deployed
  (`web/vercel.json` present) Node API (`api/public-feed.js`, `api/cockpit.js`, `api/lp.js`,
  `api/state.js`, `api/command.js`, `api/ops.js`, `api/waitlist.js`, `api/checkout.js`) with a
  Postgres dependency (`web/package.json:12-14`) — reads as a commercial/public-facing mirror of
  the SMCF paper-trading engine's state, separate concern from the research pipeline.
  `smcf/cockpit_push_box.py` and `smcf/r2_sync.py`/`smcf/rep_sync.py` suggest a push/sync path from
  the paper engine to this dashboard, not independently traced this pass.
- **Secrets** are file-based, `.env`-pattern, gitignored (paths only, not opened): `.env`,
  `.env.helius2`, `.env.hotwallet-key`, `.secrets/ibkr.env`, `.secrets/poweredge.env`,
  `lp_copy_bot/.secrets/{alchemy,drpc,erpc,helius,hotwallet,lpagent,nansen}.env`, `web/.env.local`.
- **CLAUDE.md** (repo root) is a generic LLM-coding-discipline document (simplicity-first,
  surgical changes, evidence-before-assertion) — not deployment-specific; no venue/host details in
  it beyond behavioral rules.

---

## What's genuinely reusable for a Hyperliquid-first perp system

1. **`hl_exec/combo/core.py` + the pin/verify/8-gate battery** (`reports/picks/RESULT-*.md`) — a
   causality-enforced, hash-pinned, cost-calibrated backtest and validation harness. This is the
   strongest asset in the repo and directly reusable regardless of which strategies eventually pass.
2. **`lp_copy_bot/src/exec/liveGate.ts` + `docs/runbooks/go-live-checklist.md` pattern** —
   compiled-in hard caps, abort-not-clamp, three-gate arming sequence, proven kill switch. Not
   reusable as code (Solana signing, not EIP-712) but directly reusable as an architecture to port.
3. **`hl_exec/data/MANIFEST.json` hash-pinning convention + `perps/perps_collector.py`'s
   parquet-per-day pattern** — a reasonable starting schema/discipline for a new HL data pipeline,
   though the collector itself needs a WS book/tape recorder added (never built, per §4) and its
   day-file write pattern is whole-file-rewrite, not true append-only.

**Biggest gap:** there is no HL (or Aster) order-execution client of any kind — no signing, no
agent-wallet handling, no builder-code order field, no WS fills stream, no per-account margin
reader. Every signal that has been rigorously tested against real HL data has failed validation.
Anyone building a live Hyperliquid-first system starts execution from zero and should not assume
any of the currently-tested signals are ready to trade.
