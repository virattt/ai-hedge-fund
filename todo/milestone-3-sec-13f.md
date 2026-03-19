# Milestone 3: SEC 13F Institutional Holdings Tracker

**Goal:** Track "smart money" via SEC 13F filings using `edgartools`. Detect when major institutions (Berkshire, Bridgewater, Renaissance) are buying or selling.

**Risk:** Medium — depends on external SEC EDGAR API availability. Must handle gracefully when unreachable.

## Tasks

- [ ] Add `edgartools` to `pyproject.toml`
- [ ] Add Pydantic models to `src/data/models.py`
  - `InstitutionalHolding` — fields: `filer_name`, `ticker`, `shares`, `value`, `date`, `change_pct`
  - `InstitutionalHoldingResponse` — wraps list of holdings
- [ ] Add institutional holdings cache to `src/data/cache.py`
  - Add `_institutional_holdings_cache` dict
  - Add `get_institutional_holdings()` / `set_institutional_holdings()` methods
- [ ] Create `src/tools/sec.py`
  - `NOTABLE_FILERS` list (Berkshire Hathaway, Bridgewater, Renaissance Technologies, etc.)
  - `get_13f_holdings(ticker, end_date, top_n=20) -> list[InstitutionalHolding]`
  - `get_top_institutional_changes(ticker, end_date, lookback_quarters=2) -> dict`
  - Uses edgartools for SEC EDGAR access
  - Caches results via `src/data/cache.py`
  - Returns empty list on EDGAR failure
- [ ] Create `src/agents/institutional_tracker.py`
  - `institutional_tracker_agent(state)` following standard agent pattern
  - Fetch 13F data via `src/tools/sec.py`
  - Analyze net buying/selling across institutions
  - Weight notable filers more heavily
  - Use `call_llm()` to synthesize signal
  - Standard `{signal, confidence, reasoning}` output
  - Returns neutral gracefully if SEC EDGAR unreachable
- [ ] Register in `src/utils/analysts.py` `ANALYST_CONFIG` with `order: 18`
- [ ] Write tests in `tests/test_sec.py`
  - Mock edgartools responses
  - Test caching behavior
  - Test graceful failure on EDGAR unavailability
- [ ] Write tests in `tests/test_institutional_tracker.py`
  - Mock data from sec.py
  - Verify agent signals for bullish/bearish/neutral scenarios
- [ ] Integration test: run with institutional tracker agent
  - Should identify top holders and position changes
  - Returns neutral gracefully if SEC EDGAR unreachable

## Files

| Action | File |
|--------|------|
| Create | `src/tools/sec.py` |
| Create | `src/agents/institutional_tracker.py` |
| Create | `tests/test_sec.py` |
| Create | `tests/test_institutional_tracker.py` |
| Modify | `pyproject.toml` |
| Modify | `src/data/models.py` |
| Modify | `src/data/cache.py` |
| Modify | `src/utils/analysts.py` |
