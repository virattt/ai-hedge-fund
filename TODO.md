# TODO — Operationalizing the Next-Level AI Hedge Fund Stack

This file tracks the concrete work to turn the new data layer, factor overlays, and Dexter → AIHF second-opinion loop into something you run regularly in practice.

---

## 1. Sanity-check what “more data” means for a name (AMAT, ASML)

**Goal:** Be explicit about how much data a *single* online committee run is using vs what lives in the long-lived `autoresearch` caches, using AMAT/ASML as the working example.

- **1.1 Understand the two data paths**
  - `src/main.py` (what you just ran with `--tickers AMAT,ASML --analysts-all --show-reasoning`):
    - Uses `src/tools/api.get_*` via `DataRouter` → Financial Datasets / yfinance / AlphaVantage.
    - Pulls **prices + fundamentals + insider trades + valuation models** on demand and stores them in `src/data/cache` (not `autoresearch/cache`).
    - That’s why the terminal output includes PEG, ROE/margins, DCF/FCF valuations, insider stats (e.g. “2 buys vs 48 sells, 715 trades, 602 bearish”).
  - `autoresearch/*` (fast backtests, autoresearch loops):
    - Only reads from the explicit JSON caches under `autoresearch/cache/`:
      - `prices_*.json` for OHLCV.
      - `financial_metrics_*.json`, `insider_trades_*.json`, `news_*.json` for factors/events.
      - `macro_rates.json`, `crypto_prices_*.json` for overlays.
    - Never calls the external APIs directly; it relies entirely on what you’ve pre-fetched.

- **1.2 Decide what “more data” should mean for AMAT/ASML**
  - For **one-off analysis** in the terminal:
    - “More data” means “agents can see fundamentals/events/valuations” → already true for AMAT/ASML via `src/main.py` and `DataRouter`.
  - For **systematic backtesting/autoresearch**:
    - “More data” means:
      - Multi-year **prices** for AMAT/ASML in `prices_tastytrade_sleeve_long.json`.
      - Multi-year **fundamental metrics** in `financial_metrics_tastytrade_sleeve_long.json`.
      - Multi-year **insider trades + news** in `insider_trades_tastytrade_sleeve_long.json` and `news_tastytrade_sleeve_long.json`.
      - Shared **macro/crypto** history covering the same window.
    - This is what unlocks “we pay FD once for deep history, then run thousands of experiments for free” for those names.

---

## 2. Make the data layer “green” for both sleeves

**Goal:** For both the tastytrade and Hyperliquid sleeves, ensure all required caches exist, cover the full backtest window, and have non-empty data for every critical ticker.

- **1.1 Confirm universes and filenames**
  - Universes:
    - `tastytrade_sleeve_long`
    - `hl_hip3_sleeve_long`
  - Expected cache files under `autoresearch/cache/`:
    - `prices_tastytrade_sleeve_long.json`
    - `prices_hl_hip3_sleeve_long.json`
    - `financial_metrics_tastytrade_sleeve_long.json`
    - `financial_metrics_hl_hip3_sleeve_long.json`
    - `insider_trades_tastytrade_sleeve_long.json`
    - `insider_trades_hl_hip3_sleeve_long.json`
    - `news_tastytrade_sleeve_long.json`
    - `news_hl_hip3_sleeve_long.json`
    - `macro_rates.json`
    - `crypto_prices_core_crypto.json` (or similar, as per `DATA.md`)

- **1.2 Run cache validation**
  - From repo root:
    ```bash
    poetry run python -m autoresearch.validate_cache \
      --universes tastytrade_sleeve_long,hl_hip3_sleeve_long \
      --start 2018-01-01 \
      --end 2026-03-07
    ```
  - Inspect output:
    - Failures: missing `prices_*.json` or zero coverage → must be fixed.
    - Warnings: empty per-ticker arrays, missing fundamentals/events/macro/crypto → should be fixed before serious backtests.

- **1.3 Patch gaps using cache scripts**
  - For prices (per-universe or per-ticker), use `cache_signals.py` in `--prices-only` mode (see `DATA.md` for exact commands).
  - For fundamentals:
    - `poetry run python -m autoresearch.cache_fundamentals --tickers ... --end 2026-03-07 --output-prefix tastytrade_sleeve_long`
    - Likewise for HL sleeve.
  - For events:
    - `poetry run python -m autoresearch.cache_events --tickers ... --start 2018-01-01 --end 2026-03-07 --output-prefix tastytrade_sleeve_long`
  - For macro:
    - `poetry run python -m autoresearch.cache_macro --start 2018-01-01 --end 2026-03-07`
  - For crypto:
    - `poetry run python -m autoresearch.cache_crypto --symbols BTC,ETH --start 2018-01-01 --end 2026-03-07 --output-prefix core_crypto`
  - Re-run `validate_cache.py` until both universes pass.

---

## 3. Evaluate fundamentals + tiers in backtests

**Goal:** Prove (or falsify) that the new factor overlays and tier-aware sizing actually improve robustness (Sharpe/OOS, drawdowns) instead of just adding complexity.

- **2.1 Baseline backtest without fundamentals/tiers**
  - In `autoresearch/params.py`:
    - Leave `FACTOR_CACHE_PREFIX = None`.
    - Ensure `USE_VALUE_FILTER`, `USE_QUALITY_FILTER`, `USE_INSIDER_FILTER` are all `False`.
  - Run:
    ```bash
    poetry run python -m autoresearch.evaluate \
      --params autoresearch.params \
      --prices-path prices_tastytrade_sleeve_long.json
    ```
  - Record metrics:
    - `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `total_return_pct`.

- **2.2 Turn on fundamentals for a single sleeve**
  - In `autoresearch/params.py`:
    ```python
    FACTOR_CACHE_PREFIX = "tastytrade_sleeve_long"

    USE_VALUE_FILTER = True
    USE_QUALITY_FILTER = True
    USE_INSIDER_FILTER = True

    MIN_VALUE_SCORE = 0.3
    MIN_QUALITY_SCORE = 0.4
    INSIDER_NET_SELL_THRESHOLD = 0.0
    INSIDER_SIZE_MULTIPLIER = 0.5
    ```
  - Re-run the same backtest:
    ```bash
    poetry run python -m autoresearch.evaluate \
      --params autoresearch.params \
      --prices-path prices_tastytrade_sleeve_long.json
    ```
  - Compare metrics vs baseline:
    - If Sharpe/Sortino improve and drawdowns don’t explode, this config becomes a candidate default for a future `params_tastytrade_sleeve.py`.

- **2.3 Check tier-aware live sizing behavior**
  - `autoresearch/tiers.py` encodes tier + sleeve per ticker and tier/regime multipliers.
  - `autoresearch/paper_trading.py` now adjusts live/paper sizing by tier:
    ```bash
    poetry run python -m autoresearch.paper_trading \
      --date 2026-03-07 \
      --initial-cash 100000 \
      --weights oos
    ```
  - Inspect output:
    - Tier A names (core choke points) should get larger scaled positions than Tier C satellites/ballast.
    - Behavior should align with the regime overlays described in `SOUL.md` (bull vs bear vs indecisive).

- **2.4 Decide on defaults per sleeve/params module**
  - For any configuration that clearly improves robustness:
    - Promote those toggles and thresholds into a sleeve-specific params module (e.g. `autoresearch/params_tastytrade_sleeve.py`) and/or sector params.
  - Otherwise:
    - Keep fundamentals/tier rules as experiment flags (left off by default) and only flip them on when specifically testing hypotheses.

---

## 4. Exercise the Dexter → AIHF second-opinion loop end-to-end

**Goal:** Prove that Dexter can hand a sleeve to AI Hedge Fund over HTTP, get a result back, and see a clear agreement/disagreement view without manual glue.

- **3.1 Start the FastAPI backend**
  - From the repo root, run the backend (see `app/backend/README.md` or app docs), for example:
    ```bash
    uvicorn app.backend.main:app --reload
    ```
  - Confirm `/api/v1/second-opinion/runs` is reachable (e.g. with curl or a browser).

- **3.2 Prepare a PortfolioDraft JSON for one sleeve**
  - From Dexter (or by hand for a first smoke test), write a file like:
    ```json
    {
      "sleeve": "tastytrade",
      "assets": [
        { "symbol": "ASML", "target_weight_pct": 8.0 },
        { "symbol": "AMAT", "target_weight_pct": 6.0 }
      ],
      "graph_nodes": [...],
      "graph_edges": [...],
      "margin_requirement": 0.5,
      "portfolio_positions": [],
      "model_name": "gpt-4.1",
      "model_provider": "openai"
    }
    ```
  - Sleeve shape and fields should match the `PortfolioDraft` idea in `docs/PRD-NORTH-STAR-DEXTER-SECOND-OPINION-SUBSTACK.md`.

- **3.3 Submit and poll via the helper client**
  - Use the helper script to drive the async API:
    ```bash
    python scripts/dexter_second_opinion_client.py \
      --draft path/to/portfolio_draft_tastytrade.json \
      --base-url http://localhost:8000 \
      --output-dir ./second_opinion_runs \
      --run-report
    ```
  - Expected behavior:
    - `POST /api/v1/second-opinion/runs` returns a `run_id`.
    - `GET /api/v1/second-opinion/runs/{run_id}` transitions status through `IN_PROGRESS` to `COMPLETE` or `ERROR`.
    - `GET /api/v1/second-opinion/runs/{run_id}/result` returns the final decisions/analyst_signals/current_prices payload.

- **3.4 Inspect the comparison / narrative layer**
  - The helper will call `autoresearch.second_opinion_report` and print buckets:
    - **Strong agree**: thesis and committee both like (or both dislike) the position at meaningful weight.
    - **Mild disagree**: small positions where stance and weight are at odds.
    - **Hard disagree**: large positions where thesis and committee strongly diverge.
  - Sanity-check that output against your intuition for at least one sleeve.
  - If desired, persist `SecondOpinionSummary[]` (from `app/backend/models/second_opinion.py`) as an intermediate artifact for Dexter’s Substack essay synthesis.

- **3.5 Wire Dexter directly once stable**
  - Once the helper flow is proven:
    - Embed the same HTTP calls in Dexter:
      - `POST /api/v1/second-opinion/runs`
      - `GET /api/v1/second-opinion/runs/{run_id}`
      - `GET /api/v1/second-opinion/runs/{run_id}/result`
    - Optionally:
      - Import or reimplement `SecondOpinionSummary` to build a machine-readable comparison.
      - Drive Substack essay drafts off that comparison, as outlined in `docs/PRD-NORTH-STAR-DEXTER-SECOND-OPINION-SUBSTACK.md`.

---

## 5. Optional polish and follow-ups

- **4.1 Docs and runbooks**
  - Keep `README.md` aligned with:
    - The existence of `validate_cache.py`, `factors.py`, `tiers.py`.
    - The `/api/v1/second-opinion/runs` endpoints.
    - The helper client and disagreement report.
  - Append any recurring issues (timeouts, missing keys, cache mismatches) to `ISSUE.md` with fixes/runbooks.

- **4.2 Observability**
  - Add lightweight logging/metrics around second-opinion runs, in the spirit of `docs/PRD-DEXTER-AI-HEDGE-FUND-INTEGRATION.md`:
    - Count of runs by status.
    - Latency from submit → complete.
    - Basic error distribution.
  - Optional: small admin CLI or HTTP endpoint listing recent runs and outcomes for quick inspection.

---

## DONE — What’s already implemented in code

- **Data caches + validator are green and ergonomic**
  - Macro and crypto cache scripts are fixed to match Financial Datasets’ expectations:
    - `cache_macro.py` now passes the required `bank` parameter (e.g. `FED`) so interest-rate history actually fills `macro_rates.json`.
    - `cache_crypto.py` now calls the crypto prices endpoint with `ticker=BTC-USD` / `ETH-USD` (not `symbol=BTC`) so `crypto_prices_*.json` is populated instead of returning 400s.
  - `autoresearch/validate_cache.py`:
    - Verifies that `prices_*.json` exist and have non-empty coverage for each universe.
    - Checks for the presence of fundamentals/events/macro/crypto caches.
    - Treats coverage-start/end mismatches as **soft warnings** so a one-day shortfall (e.g. ending on `2026-03-06` vs target `2026-03-07`) no longer causes a hard `FAIL`.

- **Factor overlays and tier-aware sizing are wired into the engines**
  - `autoresearch/factors.py` loads cached fundamentals/events and computes simple value/quality/insider factor snapshots.
  - `autoresearch/params.py` exposes:
    - `FACTOR_CACHE_PREFIX` and toggles for `USE_VALUE_FILTER`, `USE_QUALITY_FILTER`, `USE_INSIDER_FILTER`, plus thresholds/multipliers.
  - `autoresearch/fast_backtest.py`:
    - Optionally calls `compute_factor_snapshot` / `apply_fundamental_rules` per ticker/date and:
      - Skips trades when filters say “no”.
      - Scales `position_limit` by the returned `size_mult` when filters allow but want smaller sizing.
  - `autoresearch/tiers.py` encodes sleeve + tier (A/B/C) per ticker plus regime multipliers.
  - `autoresearch/paper_trading.py`:
    - Incorporates `TIER_BASE_MULTIPLIER` and `REGIME_TIER_MULTIPLIER` into the sizing `scale`, so Tier A choke points run larger than Tier C ballast, consistent with `SOUL.md`.

- **Dexter → AIHF second-opinion loop is implemented end-to-end**
  - FastAPI backend:
    - `app/backend/routes/second_opinion.py` exposes:
      - `POST /api/v1/second-opinion/runs` to submit a PortfolioDraft and create a `HedgeFundFlowRun`.
      - `GET /api/v1/second-opinion/runs/{run_id}` to poll run status.
      - `GET /api/v1/second-opinion/runs/{run_id}/result` to fetch the final decisions + signals payload.
    - Background task `_execute_second_opinion_run` wires the request into `create_graph` / `run_graph` and persists results back onto the flow run.
    - `app/backend/routes/__init__.py` mounts the new router on the main `api_router`.
  - Comparison / narrative layer:
    - `app/backend/models/second_opinion.py` defines `SecondOpinionSummary` plus `summarize_second_opinion(...)` (raw decisions → per-symbol summary objects).
    - `autoresearch/second_opinion_report.py` takes a PortfolioDraft + run result and prints **Strong agree / Mild disagree / Hard disagree** buckets for human review / Substack drafting.
  - Dexter helper:
    - `scripts/dexter_second_opinion_client.py`:
      - Submits drafts to `/api/v1/second-opinion/runs`.
      - Polls status until complete.
      - Fetches and saves results.
      - Optionally calls `second_opinion_report` to print the disagreement view.

