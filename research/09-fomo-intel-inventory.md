# fomo-intel — repo inventory for perps reuse

Date: 2026-09-19. Read-only survey of `F:\GetMoney\fomo-intel` (remote
`Lazydayz137/fomo-intel`, branch `foundation-trim`, worktree as-is including
uncommitted/untracked files). Compiled for a team building a Hyperliquid-first
perps trading system evaluating what to reuse.

## VERDICT

This repo is a spot/memecoin wallet-intelligence research project on Solana
and BSC — it contains **zero perps, Hyperliquid, or builder-code work of any
kind**, and that is by explicit design (a same-repo note records the owner
splitting "perps/venue work" into a separate `C:\trading` project on purpose).
What IS reusable is narrow but real: a clean FOMO-app API client with working
auth-refresh and response banking (`src/fomo.py`), a well-designed SQLite
schema + cache/credit-governance layer for a paid data API
(`src/nansen_client.py`, `src/db.py`), and — the most interesting piece for a
new identity-mapping problem — a validated, if manual and low-volume,
heuristic for de-anonymizing a platform's *displayed* wallet to a user's
*real* execution wallet (`analysis/resolver/resolve_wallet.py`). The on-chain
watcher and signal-scoring engine described in the PRD (`src/watch.py`,
`src/signals.py`) are implemented and plausible but **unproven**: the live
database has zero rows in `grpc_trade_events` and zero in `pattern_signals`,
meaning the continuous watch/signal loop has never persisted a single
real-time trade or alert. Most of the actual live investigative work in the
last month happened outside the structured `src/` pipeline, in ad-hoc,
scratch-quality scripts under `analysis/` that log to flat files and were
explicitly run "only while a session is alive" with no deployment automation
found anywhere in the repo (no Dockerfile, no scheduler, no daemon — only two
GitHub Actions workflows for Claude Code PR review). Data is overwhelmingly a
**current-state snapshot store**, not a history: `trader_seeds` and
`token_positions` are upserted in place on every refetch, so no as-of-a-past-date
query is possible on the project's core tables; only `raw_payloads` (a
true append-only API-response bank) and the empty `grpc_trade_events` table
carry observation timestamps that would support one.

---

## 1. What it collects

**Sources, all verified in code:**

- **FOMO app** (`prod-api.fomo.family`) — `src/fomo.py`. Leaderboard
  (all-time, capped at 50 rows regardless of `limit`; and windowed
  `24h`/`7d`/`30d`, capped at 100, `src/fomo.py:386-400`), clans leaderboard +
  full member rosters (`src/fomo.py:402-421`), user-by-handle lookup
  (`src/fomo.py:423-428`), and per-user `/balances` (every open position,
  `src/fomo.py:430-435`). Auth is a Privy bearer token with a working
  auto-refresh path (`src/fomo.py:282-372`) that exchanges the stored refresh
  token via `auth.privy.io` and rewrites `.env` in place. Called manually /
  on-demand — no scheduler invokes it.
- **Nansen API** (`api.nansen.ai/api/v1`) — `src/nansen_client.py:33-46`. Six
  endpoints wired: `related-wallets` (1 credit), `pnl-summary` (1),
  `dex-trades` (1), `counterparties` (5), `pnl-leaderboard` (5),
  `who-bought-sold` (5). Every call is SHA-256 cache-keyed
  (`compute_cache_key`, `nansen_client.py:101-109`) against per-endpoint TTLs
  in `CACHE_TTL` (`src/db.py:207-214`, 1h–24h) before hitting the network.
- **Solana RPC** — `src/watch.py`. Polls `getSignaturesForAddress` +
  `getTransaction` (jsonParsed) at `poll_interval_s` (default 5s,
  `src/config.py:61`) against the public mainnet-beta endpoint by default.
- **BSC / EVM, free RPC** — not in `src/` at all; a family of standalone
  scripts in `analysis/` (`bsc_watch.py`, `operator_wallets.py`,
  `buy_scatter_watch.py`) that call `eth_getLogs`/`eth_getBlockByNumber`
  directly to find `multisendToken`/`multisendEther` gas-fanout and
  buy-then-scatter patterns (documented in `HANDOFF.md:65-149`).
- **GMGN** (`gmgn-cli`, npm, `GMGN_API_KEY`) — per-holder
  bought-vs-received split (`STATUS.md:768-773`), used from `analysis/`
  scripts, not `src/`.
- **External, read-only, not collected by this repo** — a Supabase database
  owned by a sibling project (`C:\trading`) is joined on `token_mint`:
  `launches` (890,195 rows, deployer_wallet), `launch_features` (882,695),
  `enrichments` (2,967,387 rows, price/mcap by token age) — `STATUS.md:744-758`.
  Coverage is only 180/2,075 FOMO tokens (8.7%), Solana-launchpad-only.

**Where it lands:** SQLite at `~/.fomo/trader_intel.db` (path
`src/config.py:19,41-44`), schema in `src/db.py:46-197` — 7 tables:
`trader_seeds`, `nansen_telemetry_logs` (request-hash-keyed cache),
`cluster_members`, `grpc_trade_events`, `token_positions`, `pattern_signals`,
`raw_payloads` (append-only bank of every raw API response). **Measured live
on disk** (file is 44,146,688 bytes, last write 2026-08-20 10:03 — i.e. no
write in the ~4 weeks since):

| table | rows | notes |
|---|---|---|
| `trader_seeds` | 1,840 rows / **920 distinct traders** | 920 solana + 920 evm rows (one FOMO account, two chain addresses) |
| `token_positions` | 6,421 | 819 distinct users, 2,075 distinct tokens |
| `cluster_members` | 292 | 292 distinct `cluster_id` — i.e. average cluster size ~1, clustering has not produced meaningful groups in the live data |
| `nansen_telemetry_logs` | 124 | cache rows, 2026-08-20 08:22–14:03 |
| `raw_payloads` | 1,376 | all `source='fomo'` — Nansen raw payloads from ad-hoc scripts (e.g. the resolver) are banked as loose JSON files under `analysis/`, not in this table |
| `grpc_trade_events` | **0** | the on-chain watcher has never persisted a trade |
| `pattern_signals` | **0** | the RSI signal engine has never fired |

Cohort breakdown of the 1,840 seed rows: `other` 1,280, `repeat` 334,
`unknown` 200, `one_hit` 26 (`src/fomo.py:152-194` for the classifier).

Beyond the DB, `analysis/` holds dozens of loose JSON/CSV/log files from
one-off research runs (BSC sybil scans, cohort watches, resolver banks) —
flat files, not part of the structured schema, many git-untracked.

## 2. What is genuinely working and reusable

| Piece | Entry point | Dependencies | Assessment |
|---|---|---|---|
| FOMO API client, auth-refresh, response banking | `src/fomo.py` (`FomoClient`) | `httpx`, `src/config.py`, optionally `src/db.py` | Solid. Handles the edge-gate headers, retries once on 401 via a real Privy refresh, banks every non-error response by default. The pattern (not the FOMO specifics) is reusable for any bearer-token vendor API. |
| Cached, credit-governed API wrapper | `src/nansen_client.py` (`NansenClient`) | `httpx`, `src/config.py`, `src/db.py` | Reusable pattern for a paid-per-call API: SHA-256 request caching, TTL by endpoint, credit-header telemetry persisted to `nansen_telemetry_logs`, budget guard (`set_credit_budget`). Nansen-specific bits (header name `apiKey`, endpoint paths) would need swapping for a different vendor. |
| SQLite schema + migrations + analytical SQL | `src/db.py` (`Database`) | stdlib `sqlite3` | The strongest reusable asset. Idempotent schema init, a live in-place composite-PK migration (`_migrate_positions_pk`, `db.py:302-339`), and non-trivial working queries: `co_accumulation`, `repeat_coentry`, and `coentry_groups` (maximal cliques via Bron-Kerbosch, `db.py:1072-1132`, `ponytail`-flagged O(3^(n/3)) at small scale) — general "which wallets moved together" logic, chain-agnostic. |
| On-chain trade watcher | `src/watch.py` (`Watcher`, `parse_transaction`) | `httpx`, Solana JSON-RPC | Implemented, has real edge-case handling (versioned-tx address-lookup tables, fee-payer lamport delta, cursor-only-advances-on-success). Explicitly a placeholder for a gRPC/Yellowstone subscriber behind the same `poll_once()` contract (`watch.py:7-10`). **Not proven live** — 0 rows in `grpc_trade_events`. |
| Lead-score / Ride-Along signal scoring | `src/signals.py` (`compute_lead_scores`, `compute_rsi`, `evaluate_trade`) | `src/db.py` | Implements the PRD's math cleanly, with a documented bug fix for one-member-cluster false triggers (`signals.py:178-186`). **Never triggered** in the live DB (`pattern_signals` empty) — unproven against real trade flow. |
| FOMO-handle → real-wallet resolver | `analysis/resolver/resolve_wallet.py` | `httpx`, `src/fomo.py`, `src/config.py` (standalone script, not integrated into `src/db.py`) | The most novel piece — see §4. Working, validated against one ground-truth case, but manual/per-handle and low-volume. |
| BSC gas-fanout / buy-then-scatter detectors | `analysis/bsc_watch.py`, `analysis/operator_wallets.py`, `analysis/buy_scatter_watch.py` | free BSC RPC, `gmgn-cli` | Live-measured findings (5-minute lead time on one case, `HANDOFF.md:76-90`), but scratch-quality: underscore-prefixed throwaway variants, `.err`/`.log` files at repo root, no tests. Reference/prior-art quality, not production code. |

Tests: `tests/test_fomo_refresh.py` (12 tests, covers `FomoClient.refresh()`
edge cases) is the only real test file; `tests/test_integration.py` and
`tests/conftest.py` are present but empty in this working tree. `CLAUDE.md:85`
states "Tests use synthetic fixtures, never the live DB."

## 3. Point-in-time properties of stored data

Mixed, and mostly **not** point-in-time-queryable:

- **`raw_payloads`** — true append-only. `save_raw_payload` is a plain
  `INSERT`, no upsert, no eviction/TTL (`src/db.py:493-499`, schema comment
  `db.py:141-144`). Each row carries `fetched_at`. This is the one table that
  could answer "what did the API say as of date X" — if the caller queries by
  `fetched_at` rather than `get_raw_payload`'s "most recent" default
  (`db.py:501-517`).
- **`nansen_telemetry_logs`** — a cache, not a log: `INSERT OR REPLACE`
  keyed on `request_hash` (`db.py:518-536`). A later identical request
  silently overwrites the earlier response.
- **`trader_seeds`** — upserted: `ON CONFLICT(primary_address) DO UPDATE`
  overwrites PnL, win-rate, cohort, etc. on every re-ingest
  (`db.py:344-407`). `created_at` is set once and never touched, but every
  other field reflects only the *latest* scrape — no history of what the
  trader's stats were on a past date.
- **`token_positions`** — also upserted (`ON CONFLICT(user_id, token_address,
  network_id) DO UPDATE`, `db.py:717-741`), `fetched_at` reset to "now" on
  every refresh. Pure current-state snapshot. `STATUS.md:530` documents that
  the project's actual method for detecting change is manual
  "snapshot-and-diff" between separate pulls — i.e. the team already knows
  this table has no built-in history and works around it externally.
- **`grpc_trade_events`** — genuinely append-only (`INSERT OR IGNORE` on
  `(signature, trader_address)`, `db.py:677-712`), carries chain-observed
  `block_timestamp`. Would support proper as-of queries. Currently empty.
- **`cluster_members`** — membership rows are insert-only
  (`INSERT OR IGNORE`, `first_seen_at` set once), but `lead_wallet_score` is
  mutated in place via a separate `UPDATE` (`update_lead_score`,
  `db.py:601-606`) with no history of prior scores.

**Net: no observed-at discipline across the board.** Only `raw_payloads` and
the (empty) `grpc_trade_events` are real observation logs; everything a
perps system would actually query for "trader state" is overwritten on
refresh with no versioning table.

## 4. Identity mapping (FOMO handle/profile → wallet)

**FOMO's own displayed profile address is frequently NOT the execution
wallet.** This is the repo's single most load-bearing finding
(`STATUS.md:26-56`, `STATUS.md:905-938`): for the one account with an
independently-known real wallet (owner exported the Privy key), FOMO's
profile page displayed a Solana address with **zero on-chain transactions
ever**, while the real trading wallet (`4xRPaczHCUXkm4Exv1MN8rAdnr9a56mn62siYRwKGiYX`)
had 1,782 DEX trades in 30 days. So there is no reliable "displayed address =
wallet" mapping to reuse as-is.

**The actual mapping tool** is `analysis/resolver/resolve_wallet.py` (not
part of `src/`, not wired into the SQLite schema — writes its own
`analysis/resolver/<handle>.json` + a banked-raw-payload folder per handle).
Method: pull a handle's FOMO `/balances`, pick 2-3 low-transfer positions,
query Nansen `dex-trades` in a tight (±2-10s) window around FOMO's
`holdingSince`/`activeTrade.createdAt` timestamps, score every wallet that
bought in that window (tight-anchor timing + cumulative-amount match), then
auto-confirm the top candidate by checking whether its own 90-day
`pnl-summary` top tokens overlap the handle's balance sheet
(`resolve_wallet.py:242-322`, `364-374`).

**Confidence and volume, measured, not estimated:** four handles were ever
run through it. Final (v1) verdicts: `PoorGoat_` — resolved and confirmed;
`DumbCrayonEater` — resolved and confirmed; `Pixel_` — unresolved (single
position, no margin); `stacking_bands` — unresolved (regressed between runs
because FOMO's own `holdingSince` field went null on a live position,
`REPORT.md:170-180`). So **2 of 4 attempted identities are resolved with
corroboration**, against a DB of 920 distinct traders — this is a validated
proof-of-concept, not a pipeline, and it is not backfilled into
`trader_seeds` or any address-identity table. No Twitter/X-handle mapping is
wired into the schema (a file `analysis/fomo_x_launches.py` exists by name
but was not inspected for this survey; no `nansen_x_handle` or similar
column exists anywhere in `src/db.py`'s schema).

## 5. Perps / Hyperliquid / builder codes

**Nothing.** A repo-wide grep for `hyperliquid|perp|perpetual|builder code`
across `.py`/`.md` returns exactly one file:
`INBOX-FROM-TRADING-2026-08-22.md`. That file is explicitly a cross-project
note *routing wallet-tracing ideas from the perps project into this one* — it
states the owner's perps/venue work happens in a separate `C:\trading` repo
("trading larger-cap perps (SOL/BTC/ETH/JTO, down to roughly $30M-cap
names)... that's a completely different game") and that this repo's scope is
influencer/insider wallet attribution for spot memecoins, kept deliberately
separate. There is no Hyperliquid SDK usage, no builder-code logic, no perps
execution/venue code anywhere in `fomo-intel`.

## 6. How it is run and deployed

**Verified from code/config:** entry points are `python -m src.run <cmd>`
(`src/run.py:394-467`, subcommands `seed`/`expand`/`watch`/`fomo-seeds`/
`coaccum`/`repeat-coentry`/`groups`/`backfill-cohorts`/`status`/`fomo`) for
the structured pipeline, and direct `py -3 analysis/<script>.py` invocation
for the ad-hoc BSC/Solana watchers. Config is `.env`-driven via
`pydantic-settings` (`src/config.py`); `.env.example` documents
`NANSEN_API_KEY`, `SOLANA_RPC_URL`, `POLL_INTERVAL_S`, `DATABASE_PATH`,
`LOG_LEVEL` (does not list `FOMO_AUTH_TOKEN`/`FOMO_REFRESH_TOKEN`, which
`src/config.py:49-50` reads but `.env.example` omits — a real `.env` file
exists in the repo root, gitignored; not read, only its presence confirmed).
No `Dockerfile`, no process manager config, and the only `.github/workflows`
present are `claude-code-review.yml` and `claude.yml` (Claude Code PR-review
automation, per commit log) — **no CI test/build/deploy pipeline found**.

**Claimed in docs, unverified from code — flagged as such:**
`HANDOFF.md:10-38` (dated 2026-08-15) states the two BSC/operator watchers
"run only while a session is alive" and must be manually restarted after any
session/context clear, i.e. this project has been operated as
manually-launched foreground/background processes during interactive
sessions on a Windows dev box, not as a deployed/scheduled service. This is
consistent with what's observable from disk (the live SQLite DB's last write
is 2026-08-20, about a month before this survey's date, with nothing written
since — matching "dies when the session ends" rather than a running daemon)
but the "session-based, no deployment" claim itself is doc-sourced, not
directly verified.
