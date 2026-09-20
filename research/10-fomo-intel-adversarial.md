# fomo-intel — Adversarial Data/Signal Integrity Review

Date: 2026-09-19. Scope: `F:\GetMoney\fomo-intel` working tree as it sits right now
(branch `foundation-trim`, includes uncommitted/unpushed changes). Read-only —
nothing in the repo was modified, run, or installed to produce this report.

## VERDICT

**Do not build a perp-futures system on this repo's current outputs without
first adding point-in-time history and re-validating "smart money" wallets on
a schedule.** The core engineering (error handling, cache keys, upsert
guards, self-tests) is unusually careful — most of the classic silent-failure
bugs are already caught and documented in `STATUS.md`. But the two things a
trading system actually needs — "was this wallet smart *at the time* it
traded" and "is the live detector pipeline actually running" — are both
currently false. The Ride-Along Signal Index's flagship term (Lead Wallet
Score, 40% of the weight) is permanently zero in production. The cohort
label that gates what gets watched is a single mutable field with no
history, so every signal is scored against *today's* classification of a
wallet, not what was known about it when it traded. And every live on-chain
detector process (buy-scatter, cohort-watch, solana-cohort-watch,
operator-wallets) stopped producing new output 12 days before this review
with no alarm anywhere in the repo.

---

## 1. Lead Wallet Score is dead code — the signal formula silently runs at 60% weight, not 100%

**Evidence:** `src/signals.py:181-186` (comment, verified against the actual
code), `src/db.py:601-606` (`update_lead_score` defined), and a repo-wide
grep confirming `update_lead_score` has exactly one reference — its own
definition. `compute_lead_scores` (`src/signals.py:43`) is likewise never
called from `src/run.py` or any `analysis/` script; its only callers are unit
tests (`tests/test_integration.py:817-840`). `evaluate_trade`
(`src/signals.py:169-171`) reads `lead_wallet_score` off `cluster_members`,
whose schema default is `0.0` (`src/db.py:94`) and which nothing in the
runtime path ever updates.

**Failure scenario:** `compute_rsi` (`src/signals.py:115-139`) is
`R = 0.40·L + 0.35·participation + 0.25·recency`. With `L` pinned at 0.0 for
every wallet forever, the maximum achievable `R` is 0.60 (participation=1.0
AND recency=1.0 simultaneously — i.e. every cluster member already bought
the token at the exact instant being scored). `SIGNAL_THRESHOLD = 0.55`
(`src/signals.py:28`) is only reachable in the narrow band where nearly the
whole cluster has already piled in and the trade is essentially
simultaneous. The PRD (`PRD.md:160-172`, `PRD.md:280`) specifies Lead Wallet
Score as a core input precisely so that a wallet with a track record of
*leading* the cluster into tokens gets weighted more than a follower. None of
that discrimination is happening — every wallet in a cluster is currently
scored as an equally-unproven follower. A perp system consuming `R ≥ 0.55` as
"a proven lead wallet just moved" would be consuming "most of the cluster
happened to buy within the same few minutes," which is a much weaker and
differently-timed signal than advertised.

**Verified by reading code**, not inferred — confirmed the absence of any
caller via grep across `src/` and `analysis/`.

---

## 2. Cohort/"smart money" labels have no point-in-time history — signals are scored against today's label, not the label at trade time

**Evidence:** `src/db.py:344-407` (`insert_seed`, `ON CONFLICT ... DO
UPDATE`) and `src/db.py:717-741` (`upsert_position`, `ON CONFLICT ... DO
UPDATE`) both overwrite `trader_seeds.cohort` / `token_positions.*` in place.
There is no versioned or append-only table for either — `raw_payloads`
(`src/db.py:145-152`) *does* bank every raw API response append-only, but no
query in the codebase (`co_accumulation`, `repeat_coentry`, `price_dispersion`,
`backfill_cohorts` — all in `src/db.py:743-1132`) reads from it; they all
read the current mutable snapshot in `trader_seeds`/`token_positions`.

**Failure scenario:** A wallet trades today while its FOMO track record is
thin (`cohort='unknown'` or `'other'`). Two weeks later a fresh
`fomo-seeds --deep` run reclassifies it `'repeat'` because it has since
racked up wins. `backfill_cohorts` (`src/db.py:743-815`) then overwrites
`trader_seeds.cohort` in place — there is no way, from this database, to
recover what the wallet's cohort *was* two weeks ago. Any retrospective
"did our smart-money cohort call this token before it pumped" analysis, or
any backtest that joins `grpc_trade_events`/`token_positions` against
`trader_seeds.cohort`, is silently using look-ahead information: it is
asking "would today's label have looked good on that old trade" rather than
"was this a smart-money trade when it happened." This is the textbook
point-in-time-integrity failure the review was asked to check for, and it
sits directly under the signal the PRD calls the qualification gate.

**Compounding, separately verified:** `cluster_members` membership is
additive only. `insert_cluster_member` (`src/db.py:582-599`) is `INSERT OR
IGNORE` and nothing in the codebase ever deletes a row from
`cluster_members`. `run.py:255-260` adds a wallet as a watched seed the
moment it is `qualified` in a `fomo-seeds` run; if a later run reclassifies
that same wallet as unqualified, it is never removed — `get_all_member_addresses`
(`src/db.py:647-672`) has no cohort filter at all, only the infra-hub filter.
**Net effect: a wallet that qualified as smart money once stays on the live
watch list forever, with no re-validation, while the label used to justify
having added it can silently change underneath it with no trace of what it
was at add-time.** A perp system driven by this watch list would be
following wallets whose edge may have long since decayed, with the repo
itself unable to tell you when or whether that happened.

**Verified by reading code** (schema, upsert SQL, and the one call site in
`run.py` that gates membership on `qualified`).

---

## 3. Every live on-chain detector has been silently dead for 12 days as of this review

**Evidence (live filesystem state, read-only):** `analysis/buy_scatter_state.json`,
`analysis/cohorts.jsonl`, `analysis/cohort_watch_state.json`,
`analysis/solana_cohort_watch_state.json`, `analysis/solana_cohorts.jsonl` all
last-modified **2026-09-07**, and `analysis/operator_wallets_raw.jsonl` last
modified **2026-09-07** as well — today is 2026-09-19, so that is 12 days of
silence. `buy_scatter_watch.py` polls every `POLL_S=15` seconds
(`analysis/buy_scatter_watch.py:87`) when running, so a 12-day gap is not
"between polls," it is "not running." The four `.err` files at repo root
(`buy_scatter_watch.err`, `cohort_watch.err`, `operator_wallets.err`,
`solana_cohort_watch.err`) are all **0 bytes** and were last touched
**2026-08-20** — over a month before this review — which means even while the
state files were still updating through Sep 7, nothing was landing in the
error stream at all; the process either restarted without that redirect or
the mtime is stale for another reason not verifiable from the filesystem
alone.

**Failure scenario:** These four scripts are exactly the mechanisms
described in the repo's own docs as "the earliest signal on the chain"
(`analysis/cohort_watch.py:1-8`) and the buy-then-scatter pre-pump tell
(`analysis/buy_scatter_watch.py:1-13`). If a trading system is wired to treat
"no recent alert" as "no coordinated activity right now," it is currently
indistinguishable from "the detector silently stopped 12 days ago." Nothing
in the repo pages anyone or writes a liveness heartbeat when this happens —
`run()` in `buy_scatter_watch.py:435-523` retries RPC failures internally but
there is no external dead-man's-switch, and none of the code checked in this
review writes a "last successful poll" timestamp anywhere a caller could
alert on.

**Verified by reading live file mtimes**, not inferred from any doc or
handoff note.

---

## 4. Selection effect baked into the whole seed universe: FOMO leaderboard + clan membership is a survivorship-biased population by construction

**Evidence:** `_fomo_seeds` (`src/run.py:165-284`) seeds exclusively from
`client.leaderboard()` (all-time top-50, `src/fomo.py:386-400`), the three
windowed leaderboards (24h/7d/30d, capped at 100 rows each,
`src/fomo.py:392-395`), and clan rosters (`src/fomo.py:402-421`). Every one
of these is "who is currently ranked/currently in a clan on one specific
app" — i.e. wallets that have already been profitable enough, recently
enough, to be visible. `classify_cohort` (`src/fomo.py:152-194`) then
separates `repeat` from `one_hit` *within* that population, which correctly
guards against one flavor of survivorship (the single lucky trade) but does
nothing about the outer one: the entire candidate pool is conditioned on
current, app-visible success.

**Failure scenario:** A signal-quality claim like "wallets we follow
outperform" cannot be validated against this seed set without a
survivorship correction, because the sampling procedure itself guarantees
the tracked population looks skilled up to the observation date — a wallet
that traded well for months and then blew up is never seeded (it fell off
the leaderboard before `fomo-seeds` ran), while one that is still riding a
hot streak always is. This is inherent to the data source (FOMO only exposes
current-state leaderboards) and is not something the codebase currently
corrects for or even flags as a caveat anywhere in `PRD.md`/`STATUS.md`.

**Inferred from architecture**, not a bug in any one function — this is a
structural property of building on a leaderboard API.

---

## 5. Wallet identity resolution is explicitly probabilistic and NOT wired into the pipeline that feeds `trader_seeds`/`cluster_members` — keep it that way

**Evidence:** `analysis/resolver/resolve_wallet.py` resolves a FOMO display
handle to an execution wallet via a points-based scoring system (timestamp
proximity to `holdingSince`, amount matching within 5% tolerance —
`resolve_wallet.py:242-322`), with an explicit `verdict()` gate
(`resolve_wallet.py:347-361`) that refuses to call a match "resolved" unless
it clears a margin. This is well-designed and self-aware — it documents its
own past false-positive (`resolve_wallet.py:350-354`, Pixel_ case) and
refuses to over-claim. Confirmed by grep: this script has **no** call to
`get_db()`, `insert_seed`, or `insert_cluster_member` — it is a standalone
research tool, not wired into `src/run.py`'s ingestion path.

**Failure scenario (if this ever gets wired in):** the `cluster_members`
schema (`src/db.py:90-101`) has no confidence/score column — only free-text
`relation`/`label`. If `resolve_wallet.py`'s scored, sometimes-ambiguous
output is ever piped into `insert_cluster_member` without carrying its score
forward, a probabilistic identity link becomes indistinguishable from
Nansen's `related-wallets` links (which are transaction-evidenced, not
scored) or from a manually-seeded address. **Currently this is not
happening** — flagging it only because it is the obvious next integration
step and the schema has no place to put the confidence if someone adds it
without also adding the column.

**Verified by reading code** — confirmed the absence of any DB write from
this file.

---

## 6. No fabricated or simulated PnL/backtest numbers exist in this repo — clean

Searched for `slippage`, `sharpe`, `backtest result`, `win rate`, `hypothetical
return`, `simulated fill` across all `.py`/`.md` files. The only "backtest"
scripts (`analysis/_bsc_backtest_aug18.py` and friends) are forensic
on-chain reconstructions of one specific buy→scatter event (block numbers,
tx hashes, on-chain reads) — they produce no PnL, no win rate, no cost/
slippage/fill-assumption number anywhere. `analysis/robert_wallet/RECONCILIATION.md:126`
is the only place a win rate appears outside `src/fomo.py`'s doc comments,
and it is a measured, cited figure (77 tokens, 1782 trades) against a real
wallet's own on-chain reconciliation, not a hypothetical strategy return.
**There is nothing in this repo that could be mistaken for a validated
trading edge — which also means there is no backtested basis yet for sizing
a perp position off any of these signals.**

---

## 7. Silent-failure handling is, on balance, unusually good — one narrow gap

`FomoClient.get()` (`src/fomo.py:236-280`) correctly distinguishes an error
envelope from real data before banking (`is_data_response`,
`src/fomo.py:73-87`) after a documented, costly past failure (242/625
`/balances` payloads banked as empty portfolios — `STATUS.md:308-314`).
`get_logs()` in the on-chain scripts (`analysis/buy_scatter_watch.py:248-271`)
returns an explicit `ok` flag and callers hold their cursor back on any
chunk failure rather than silently skipping blocks
(`analysis/buy_scatter_watch.py:512-518`). `pct_of_supply`
(`analysis/buy_scatter_watch.py:296-310`) explicitly refuses to report a
percentage when the Transfer-log total exceeds the token's own `totalSupply`
(a real, measured spam-contract shape) rather than emitting a nonsense 723%.

One narrow gap, low severity: `NansenClient._parse_credit_header`
(`src/nansen_client.py:409-420`) falls back to `endpoint.cost` (the *static*
per-endpoint price) when the `x-nansen-credits-cost` response header is
missing or unparseable, and that fallback value is what gets written to
`nansen_telemetry_logs.credits_cost` (`src/nansen_client.py:251,269`). A
credit-budget calculation built on this table would be trusting an assumed
price on any call where the header was absent, indistinguishable in the
data from a call where the header was actually read. Low blast radius — this
affects Nansen spend accounting, not trade signal correctness.

---

## Findings NOT ranked (out of scope / already fixed and documented)

- The `holdingSince` FIFO-lot-walk issue, the RSI-recency-measured-from-newest
  bug, the `grpc_trade_events` dedup-key collision, the EVM/Solana
  double-counting bug, and the `insert_seed` `INSERT OR IGNORE` data-loss bug
  are all real historical bugs but are already fixed in current code and
  documented with before/after evidence in `STATUS.md:280-322`. Re-verified
  spot-checks (the `ON CONFLICT` guard logic in `src/db.py:372-395`, the
  `token_activity` join against `cluster_members` rather than the trade's own
  stored `cluster_id` in `src/db.py:1171-1194`) confirm the fixes are present
  in the working tree as described.
- No secrets found in tracked files. `.env` is correctly gitignored
  (`.gitignore:2`) and not present in `git ls-files`; only `.env.example` is
  tracked. The only string literals matching a secret-shaped grep are Solana
  addresses and test placeholder tokens (`tests/test_fomo_refresh.py`), not
  real credentials.

---

## Summary for a team building on top of this

| # | Finding | Damage if unaddressed |
|---|---|---|
| 1 | Lead Wallet Score always 0 — 40% of signal weight is dead | Signal is actually "cluster piled in fast," not "a proven leader moved" |
| 2 | Cohort/watch-list have no point-in-time history, and watch-list is append-only | Any backtest joining trades to cohort has look-ahead bias; stale wallets never get dropped |
| 3 | All four live detectors dead 12 days, no heartbeat/alarm | "No signal" is indistinguishable from "pipeline is down" |
| 4 | Seed universe is a leaderboard survivorship sample | Any "our wallets outperform" claim is unvalidated by construction |
| 5 | Wallet-identity resolver is probabilistic, currently unwired | Fine today; a future integration needs a confidence column, not a bare address |
| 6 | No fabricated backtest numbers exist | Clean, but also means there is no validated edge to size a position on yet |
| 7 | Error handling is generally careful; one credit-accounting fallback is soft | Low severity, spend-accounting only |
