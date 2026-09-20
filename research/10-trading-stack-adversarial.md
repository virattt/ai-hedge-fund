# Adversarial review — trading-stack as a base for a Hyperliquid-first perp system

Date: 2026-09-19
Scope: `F:\GetMoney\trading`, working tree as checked out (branch `feat/hl-picks-pipeline`, includes uncommitted/unpushed changes). Read-only: Read/Grep/Glob + read-only git only. No code run, no orders, no wallets touched, no paid APIs called.

## VERDICT

**Not close to safe to trade live, and the gap is not the order-path bugs you'd expect to find — it's that a live Hyperliquid order path barely exists yet, and the one piece of risk-control code built for it is sitting on a branch that was never merged into the branch this pipeline actually runs on.** The research/backtest layer (hundreds of scripts under `hl_exec/combo/`) is unusually careful for what it is — real lookahead self-checks, disclosed survivorship bias, disclosed liquidation-model gaps, active multiple-comparison hygiene (signals get demoted to NOT_VALIDATED in recent commits). The risk is concentrated in two places: (1) the authorized safety gate is orphaned off the live branch, and (2) two backtest cost assumptions (funding = median not mean; liquidation = no-gap) quietly understate the tail losses a crowded, leveraged momentum book would actually eat. No hardcoded secrets were found in tracked files.

## Findings, ranked by damage

### 1. [CRITICAL] The authorized risk/safety gate exists but is not on the branch this pipeline runs on — zero risk controls are reachable from the live checkout

`hl_exec/hl_gate.py` — "Hyperliquid perps safety gate," leverage cap (5x), per-position/total notional cap ($150), daily-loss halt ($15/24h), liquidation-distance floor (15%), HIP-3 isolated-margin enforcement, master `CAPS_AUTHORIZED` interlock — was built and Robert-authorized on 2026-08-22 (see the docstring's cap table and its cited quote). Verified via `git log --all --oneline -- hl_exec/hl_gate.py`:
```
bae2783 fix(hl_gate): fail closed on asset_max_leverage<1, fix stale comment
f557f31 feat(hl_exec): asset-dynamic sizing - blocks now report max viable leverage
b58292f feat(hl_exec): arm gate with Robert-authorized caps for a $50 stake
fcc0a81 feat(hl_exec): Hyperliquid perps safety gate + M1/M2 boundary test
```
This history lives on branch `feat/hl-safety-gate` (and ~20 downstream doc/worktree branches) — **not** on `feat/hl-picks-pipeline`, the branch currently checked out and the one the picks/research work is being merged into. Confirmed two ways:
- `find . -iname hl_gate.py` returns the file only under `.claude/worktrees/*` (other branches' checkouts) — it does not exist anywhere in the current working tree outside those worktrees.
- `grep -rn "hl_gate" --include=*.py .` (excluding worktrees/`__pycache__`) returns **zero** matches anywhere in the current tree — nothing imports it, references it, or is even aware of it.

Damage scenario: if execution code gets built on top of `feat/hl-picks-pipeline` (the branch that's actually moving, per recent commits like `fix(combo): correct the TSMOM portfolio liquidation model`), there is currently no leverage cap, no notional cap, no daily-loss halt, and no liquidation-distance floor anywhere reachable from that code — the gate's own docstring says the failure mode is "flipping [CAPS_AUTHORIZED] without real caps behind it"; the actual failure mode here is worse — the caps exist and are authorized, but the branch that matters can't see them at all. This is a merge/process gap, not a code defect, but it is the single highest-damage finding: it's the difference between "a kill switch nobody calls" and "no kill switch is even importable."

### 2. [HIGH] No live Hyperliquid order-submission code exists anywhere in the repo — the order path is unwritten, not just unreviewed

Searched the whole tree for `hyperliquid` SDK `Exchange(`, `bulk_orders`, `OrderRequest`, `place_order`, EIP-712/agent-wallet signing tied to Hyperliquid specifically: nothing. Everything under `hl_exec/` is backtest/research (candle fetch, feature computation, combo search, walk-forward, reports) or read-only info-API polling (`perps/perps_collector.py` hits `api.hyperliquid.xyz/info`, GET only). The only *live-signing* code in the repo at all is for a different venue, Aster (`_aster_v3sign.py`, `_aster_pos.py`, `_aster_diag.py`, `_aster_setup.py` at repo root), and even those are read-only (`/fapi/v3/balance`, `/fapi/v3/positionRisk`) — no order-placement call was found for Aster either.

This means every item the task asked about under "order path correctness" — sign/side handling, tick/lot rounding, reduce-only and flip handling, partial fills, double-submit-safe retries, idempotency, nonce handling, stale-price protection — has **no code to review**, because it hasn't been written. State this plainly rather than as a defect: the risk is that this fact gets lost by the time an order path is added under time pressure, and it ships without the gate from Finding 1 wired in from day one.

### 3. [MEDIUM-HIGH] Backtest funding cost uses the median of historical funding, while the code itself documents the mean is an order of magnitude worse and opposite-signed — exactly the tail a crowded momentum book eats

`hl_exec/combo/core.py:19-22` (docstring) and `:51`:
```
FUNDING_HR_MEDIAN            median 48h funding on firings was +0.0551% of
                             notional -> 1.148e-5/hr. The MEAN has the opposite
                             sign (-0.1936%) and is tail-driven by a handful of
                             squeezes; the median is the honest scalar.
...
FUNDING_HR_MEDIAN = 0.000551 / 48.0     # 1.1479e-5 per hour, fraction of notional
```
This constant feeds `simulate()` and `evaluate()` (`core.py:549-618`, `:633-`) as the default funding cost for every reported cell. The mean being negative and ~17x larger in magnitude than the median, "tail-driven by a handful of squeezes," is not noise to discard — funding squeezes are the systematic cost of being on the crowded, consensus side of a leveraged momentum trade, which is precisely the side these strategies are on by construction. Using the median discards exactly the adverse-selection cost a live momentum book would be most exposed to. Separately, `hl_exec/portfolio.py:17-21` (the position-count/cadence scan) charges **zero** funding at all — explicitly disclosed ("No funding... A 24h/48h hold is materially exposed to it") — so every `ann%` figure that script prints excludes even the median cost, let alone the tail. This is disclosed in-code, which is good practice, but the disclosure needs to travel with any number that reaches a go/no-go decision, and I did not have time to verify it survives into every downstream report file.

### 4. [MEDIUM] Liquidation model has a disclosed, unmodelled gap-through case, quantified only on the same in-sample data used to validate the strategy

`hl_exec/combo/core.py:552-577` (`simulate()`, "the corrected model") walks bar-by-bar high/low; it has no bar-open data (`paths` carries no opens), so it cannot detect a bar that gaps straight through both the stop and the liquidation level. The code quantifies this honestly: "1 of 652 such bars (0.15%) at -4%/10x, and 0 of 88 at -6%/5x, 0 of 190 at -8%/5x" defeat the stop via a gap. But that 0.15% is measured on the same historical window the strategy is being validated against — it says nothing about a de-peg, an exchange outage, or a cascade liquidation event, which is exactly the tail scenario this omission is blind to and exactly the scenario that produces real liquidations. The code is explicit that "every bit of tight-stop liquidation risk rests on the no-gap assumption" — that's an accurate self-assessment, but it means the reported liquidation rate is a floor, not an estimate.

### 5. [LOW-MEDIUM] Data collector silently swallows per-row parse failures with no logging of which coin/field failed

`perps/perps_collector.py:44-56` (`snap_hyperliquid`) wraps each coin's row-build in `try: ... except Exception: pass` with no logging of the coin or the error. A field change or bad value from the venue would silently drop that coin from the day's parquet with zero alarm. Given how much of the research layer already reasons carefully about universe coverage and survivorship (`test_signals.py`'s explicit coverage filter, `combo/survivorship_bias.py`), a silent per-coin collection gap could get misread downstream as "this market doesn't have data for that day" rather than "the collector choked on it," quietly corrupting a coverage-sensitive analysis. Same file, lines 96-99, also contains dead/no-op code (`pd.DataFrame(snap_hyperliquid(ts)) if False else None` wrapped in its own bare `except: pass`) — harmless as written, but the kind of leftover-looking debug stub that invites confusion about whether something is actually checked. This is read-only market data collection, not an execution risk, so ranked lowest, but worth a one-line fix (log the coin + exception) given the amount of research weight resting on exact coverage.

## Areas checked and found clean

- **Secrets/keys in tracked files:** clean. `git grep -InE "0x[0-9a-fA-F]{64}"` over the tracked tree returned nothing; `.gitignore` covers `.env`, `.env.*`, `*.key`, `**/.secrets/`; `git ls-files | grep -i secret` returns only a docs checklist and a test filename, no actual key material. The Aster live-signing scripts pull the private key from an external `aster_mcp.config.ConfigManager`, outside this repo, at call time — not stored in-repo.
- **Lookahead in signal construction:** clean, verified by reading, not inferred. `hl_exec/test_signals.py` signals index only `c[:i+1]`; `hl_exec/combo/core.py` states and enforces ("Enforced by the causality self-check in `__main__`") that a feature at row i may use rows ≤ i only. `comp_lib.zscores()` is explicitly noted as causal-trailing, "never a full-sample mean/std."
- **Survivorship bias:** disclosed, not hidden. `test_signals.py` states outright: "No survivorship correction: the universe is today's liquid markets, which excludes anything that died. That biases results OPTIMISTIC." A dedicated `hl_exec/combo/survivorship_bias.py` exists and recent commits (`survivorship_blocks.py`, block-boundary freezing) are actively working this problem.
- **Overfitting / multiple-comparison hygiene:** better than typical. Recent commits on this exact branch downgrade a previously-promising signal to NOT_VALIDATED after running noise/drift controls (`0a55843 research(picks): OI-inverse short is DRIFT not signal -- five controls, verdict NOT VALIDATED`), and `reports/picks/TV-COMBINATIONS.md` is explicitly labeled "No script here has been backtested; these are candidate hypotheses, not results" — it is a research harvest document, not a results document, so it does not itself create false confidence.
- **Fee schedule:** the 0.045%/0.09% round-trip taker figure used throughout (`COST = 0.0009`, `ONE_WAY = 0.00045`) is stated as "verified against the venue in phase 1," a real, checkable HL base-tier taker rate, not an invented number.

## What I verified vs. inferred

Verified by reading code and running read-only git (`git log --all`, `git branch --contains`, `grep`/`git grep`): Findings 1, 2, 3, 4, and the "clean" items above. Finding 5 verified by reading the file in full. I did **not** exhaustively read every one of the ~150+ scripts under `hl_exec/combo/` (time-capped) — the funding/liquidation caveats in Findings 3-4 are confirmed present at the engine level (`core.py`); whether every downstream report/pick surface still carries those caveats forward is inferred as likely but not individually checked file-by-file.
