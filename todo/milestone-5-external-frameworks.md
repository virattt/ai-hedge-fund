# Milestone 5: External Framework Integration Layer

**Goal:** Create adapter pattern for consuming signals from FinRL, FinGPT, Trading-R1 when installed.

**Risk:** Medium — most open-ended milestone. Depends on external framework output formats. Designed to degrade gracefully.

## Tasks

- [ ] Create `src/tools/external_models.py`
  - `ExternalModelAdapter` ABC with:
    - `is_available() -> bool` — checks if framework is installed/configured
    - `get_signal(ticker, start_date, end_date) -> dict` — returns `{signal, confidence, reasoning}`
  - `FinRLAdapter` — reads signal from file path set by `FINRL_SIGNAL_PATH` env var
  - `FinGPTAdapter` — reads signal from file path set by `FINGPT_SIGNAL_PATH` env var
  - `TradingR1Adapter` — reads signal from file path set by `TRADING_R1_SIGNAL_PATH` env var
  - Each adapter parses JSON signal files with expected schema
- [ ] Create `src/agents/research_agent.py`
  - `research_agent(state)` following standard agent pattern
  - Query all available adapters via `is_available()`
  - Collect signals from available adapters
  - Use `call_llm()` to synthesize aggregated signal
  - Returns neutral if no external models configured
- [ ] Register in `src/utils/analysts.py` `ANALYST_CONFIG` with `order: 19`
- [ ] Write tests in `tests/test_external_models.py`
  - Test each adapter with mock signal files
  - Test `is_available()` when env var not set
  - Test `is_available()` when env var set but file missing
  - Test research agent with 0, 1, and multiple adapters available
- [ ] Create `docs/external-frameworks.md`
  - Setup instructions for each framework (FinRL, FinGPT, Trading-R1)
  - Expected JSON signal file format
  - Environment variable configuration
  - Example workflow
- [ ] Integration test: with and without external frameworks
  - No frameworks configured → neutral signal
  - Set mock output file + env var → verify it reads and uses that signal

## Files

| Action | File |
|--------|------|
| Create | `src/tools/external_models.py` |
| Create | `src/agents/research_agent.py` |
| Create | `tests/test_external_models.py` |
| Create | `docs/external-frameworks.md` |
| Modify | `src/utils/analysts.py` |
