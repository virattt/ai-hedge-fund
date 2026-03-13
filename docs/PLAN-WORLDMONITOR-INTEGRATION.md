# World Monitor Integration Plan (API vs Fork)

Status: Proposed  
Owner: AIHF Engineering  
Branch: `feat/worldmonitor-integration-plan`

## 1) Goal

Integrate World Monitor signals as an additional macro/geopolitical indicator for AI Hedge Fund with:

- Minimal disruption to existing second-opinion and autoresearch pipelines.
- Strong reliability guarantees (fallbacks, caching, stale handling).
- Quantifiable impact via backtests before production weighting.

Primary target use cases:

- Improve drawdown and tail-risk handling through exogenous event/regime indicators.
- Add contextual overlays to second-opinion outputs and optional portfolio sizing/risk constraints.

## 2) Current AIHF Surfaces to Extend

This plan aligns with existing code paths:

- Async second-opinion run APIs (`app/backend/routes/second_opinion.py` and related models/services).
- Portfolio/risk mechanics (`app/backend/services/portfolio.py`, `autoresearch/risk_controls.py`).
- Factor snapshots and rule application (`autoresearch/factors.py`).
- Backtesting and walk-forward modules (`autoresearch/backtest_*`, `autoresearch/walk_forward.py`, `src/backtesting/*`).

## 3) Integration Options

### Option A: API Consumer (Recommended Default)

Use World Monitor hosted API endpoints (e.g., `api.worldmonitor.app`) and ingest normalized signals into AIHF.

Pros:

- Fastest time-to-value.
- No need to run and maintain a large additional stack.
- Lower operational complexity for initial experiments.
- Easier to keep pace with upstream improvements.

Cons:

- External dependency and rate/availability risk.
- Less control over upstream schema evolution.
- Potential cost/ToS constraints for production-scale usage.

### Option B: Fork/Self-Host World Monitor

Fork World Monitor and run your own API/data plane.

Pros:

- Full control over schema, retention, and latency budget.
- Better reproducibility for research if datasets are fully archived.
- Can harden and customize scoring specifically for strategy needs.

Cons:

- Significant maintenance burden (large codebase, many services).
- Higher infra complexity and engineering overhead.
- Risk of long integration cycle before alpha impact is known.

## 4) Decision Framework: API vs Fork

Use this gate after Phase 1 and Phase 2 experiments:

- Stay API-first if all are true:
  - p95 API latency under agreed threshold in trading windows.
  - <1% hard failures over 30-day pilot.
  - Signal schema stable enough with adapter versioning.
  - Strategy uplift is measurable (or risk reduction is measurable).
- Move to fork/self-host if any are true:
  - Frequent availability incidents materially affect decisions.
  - Required signals are missing or too delayed for your use case.
  - You need deterministic historical reconstruction unavailable via API.
  - Compliance/data residency requires internal hosting.

## 5) Architecture (API-First)

### 5.1 New Components in AIHF

1. Provider client:
   - `src/data/worldmonitor_client.py` (HTTP client, retries, timeouts, auth header).
2. Normalization and feature mapper:
   - `src/data/worldmonitor_features.py` (map raw payloads to canonical feature schema).
3. Cache layer:
   - `autoresearch/cache_worldmonitor.py` (write/read local snapshots with TTL and as-of metadata).
4. Feature integration points:
   - `autoresearch/factors.py` extension for macro/geopolitical fields.
   - `autoresearch/risk_controls.py` extension for event/regime gating.
5. Optional API exposure:
   - `app/backend/routes/worldmonitor.py` for diagnostics and latest-signal visibility.

### 5.2 Canonical Feature Schema (v1)

Feature group (daily + intraday refresh):

- `wm_global_risk_score` (0-100 normalized)
- `wm_macro_regime` (enum: risk_on, neutral, risk_off)
- `wm_country_risk[ISO]` (0-100 for key exposure countries)
- `wm_supply_chain_stress` (0-100)
- `wm_conflict_escalation` (0-100)
- `wm_cb_policy_bias` (enum/score)
- `wm_data_freshness_seconds`
- `wm_source_version`

Each feature record must include:

- `as_of_utc`
- `ttl_seconds`
- `source_endpoint`
- `mapping_version`

### 5.3 Safety/Fallback Rules

- On API timeout/error: use last-known-good value if within max staleness.
- On stale/missing data beyond max staleness: neutralize indicator (do not hard-stop unless explicitly configured).
- All WM-derived constraints are soft in Phase 1 (sizing multipliers), not hard bans.

## 6) Rollout Plan

### Phase 0: Contract and Feasibility (2-3 days)

Deliverables:

- Signal contract doc (endpoint list, payload fields, refresh cadence, rate limits).
- Feature mapping spec v1 (raw -> canonical).
- Baseline observability KPIs (latency, failure rate, staleness rate).

Acceptance criteria:

- Clear list of required endpoints and fields.
- Prototype pull succeeds for at least 5 consecutive days in paper mode.

### Phase 1: API Ingestion + Offline Research (1 week)

Deliverables:

- Implement `worldmonitor_client.py` and feature mapper.
- Persist daily/intraday snapshots to local cache (`autoresearch/cache`).
- Add research notebook/script for exploratory correlation:
  - WM features vs portfolio returns, drawdowns, realized volatility.

Acceptance criteria:

- >=95% successful fetches in scheduled runs.
- Feature files reproducible and versioned.
- Preliminary evidence of risk explanatory power in at least one stress window.

### Phase 2: Backtest Integration (1 week)

Deliverables:

- Extend factor/risk modules:
  - Add optional WM multipliers in `autoresearch/factors.py`.
  - Add optional WM guardrails in `autoresearch/risk_controls.py`.
- Add config flags and thresholds (all default OFF):
  - `USE_WM_FILTER`
  - `WM_RISK_OFF_SCALE`
  - `WM_MAX_STALENESS_MINUTES`
  - `WM_COUNTRY_RISK_CAP`
- Backtest matrix:
  - baseline
  - WM sizing only
  - WM sizing + risk guards

Acceptance criteria:

- No regression in core pipeline stability.
- Evidence of one of:
  - reduced max drawdown, or
  - improved Sharpe/Sortino with acceptable turnover increase.

### Phase 3: Second-Opinion Overlay (3-5 days)

Deliverables:

- Inject WM context into second-opinion run summaries (non-blocking).
- Extend summary model to include `macro_context` and `geopolitical_notes` where available.
- Surface WM diagnostics in run artifacts for auditability.

Acceptance criteria:

- Second-opinion API remains backward-compatible.
- New WM context present only when data exists; no hard dependency.

### Phase 4: Paper Trading Pilot (2 weeks)

Deliverables:

- Enable WM filters in paper mode with conservative multipliers.
- Add daily health checks and anomaly alerts (missing/stale signal).
- Compare pilot vs control portfolio.

Acceptance criteria:

- Stable operation across full pilot window.
- Risk metrics improve or remain neutral with lower tail-risk profile.

### Phase 5: Production Decision + API vs Fork Gate

Deliverables:

- Formal go/no-go memo using decision framework in Section 4.
- If API retained: lock SLA assumptions and fallback policy.
- If fork chosen: execute Fork Program (Section 7).

Acceptance criteria:

- Explicit choice documented with operational owner and budget.

## 7) Fork Program (Only If Triggered)

If API does not satisfy reliability/control requirements:

1. Fork and pin upstream commit.
2. Stand up self-hosted minimal domain subset first (do not mirror all services):
   - macro
   - geopolitical risk
   - market regime
3. Build ingestion audit trail:
   - raw payload archive
   - transformed feature archive
4. Define upgrade cadence:
   - monthly upstream rebase window
   - compatibility tests before merge
5. Add license/commercial compliance review before deployment.

Exit criteria for fork:

- Reproducible historical reconstruction for all WM features used in models.
- On-call and maintenance ownership assigned.

## 8) API vs Fork Recommendation (Now)

Recommended immediate path:

- Start API-first for Phases 0-4.
- Defer fork decision until objective evidence from backtests + pilot is available.
- Keep integration modular so swapping data source (hosted API -> self-hosted fork) is a provider config change, not a strategy rewrite.

## 9) Testing Strategy

- Unit tests:
  - response parsing
  - feature normalization
  - stale fallback behavior
- Integration tests:
  - mock World Monitor API responses (healthy, partial, failure)
  - end-to-end second-opinion run with WM context enabled
- Backtest regression:
  - verify no accidental lookahead bias
  - verify identical outputs when `USE_WM_FILTER=False`

## 10) Risks and Mitigations

- Schema drift:
  - Mitigation: adapter layer + mapping version + strict validation.
- Data freshness gaps:
  - Mitigation: max-staleness guard + neutral fallback.
- Overfitting to geopolitical events:
  - Mitigation: out-of-sample walk-forward and conservative weights.
- Operational dependency concentration:
  - Mitigation: cache, retry budget, and optional fork path.

## 11) Work Breakdown (Suggested Tickets)

1. Create WM API client + settings + retries.
2. Create feature schema + mapper + persistence.
3. Add WM cache refresh job and logs.
4. Add WM flags/params and wire into factors/risk controls.
5. Add backtest experiments and report template.
6. Extend second-opinion summary with WM context.
7. Add monitoring endpoints and health checks.
8. Write deployment runbook and rollback playbook.

## 12) Success Metrics

- Reliability:
  - API fetch success rate
  - staleness incidence
  - p95 feature availability latency
- Strategy:
  - max drawdown
  - Sharpe/Sortino
  - hit rate by regime
  - turnover/slippage changes
- Ops:
  - on-call incidents from WM dependency
  - mean time to recover signal pipeline

