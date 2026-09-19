# Reconciliation: the Phase 1–3 review vs. the current tree

This note settles what happens to the work produced in an earlier review session
(branch `claude/repo-status-review-011CUKiA3XbjFf3M93T5Jd2z`, three commits,
45 files, 6,347 insertions) that was never opened as a pull request.

Short version: that branch targets a codebase that no longer exists. Most of it
cannot be merged; most of what it asked for, this tree already does another way.
Three items remain genuinely open, and one real bug it did not cover is fixed here.

## Why nothing merged

The fork carries two unrelated histories:

| Ref | Root commit | Shape |
|-----|-------------|-------|
| `main` (before this change) | `337b3d3` | v1: `src/agents/`, `app/backend/`, React frontend |
| upstream `virattt/ai-hedge-fund` @ `154a8b2` | `8082984` | v2.3.0: `hedge_fund/` package, Textual TUI, broker protocol |

`git merge-base` between them is empty — upstream replaced the project rather
than evolving it. The review branch sits on the v1 root, so its diff touches
`app/backend/database/`, `app/backend/services/`, `src/utils/` and `tests/`,
none of which exist in v2. There is no rebase that lands it.

The v1 history is not lost: it stays reachable at
`origin/claude/repo-status-review-011CUKiA3XbjFf3M93T5Jd2z`.

## Verdict on each finding

### Structurally dead — cannot be merged

These target deleted directories. Re-creating them against `hedge_fund/` would be
a rewrite, not a port, and would replace v2's receipt ledger with a database the
[ROADMAP](./ROADMAP.md) does not call for.

| Finding | Where it lived |
|---|---|
| 10 SQLAlchemy models (portfolios, positions, trades, realized_gains, decisions, agent_signals, portfolio_decisions, performance_snapshots, system_logs, settings) | `app/backend/database/models/` |
| 4 repository classes + generic base repository | `app/backend/database/repositories/` |
| Alembic migration `001_initial_database_schema` + `alembic.ini` | `alembic/` |
| `TradingService` (trade execution, position management, snapshots) | `app/backend/services/trading_service.py` |
| 70 repository unit tests + `conftest.py` + `pytest.ini` | `tests/unit/` |
| PostgreSQL 15 in docker-compose, `scripts/init_db.py`, `scripts/startup.sh` | `docker/`, `scripts/` |
| `DATABASE.md`, `DEPLOYMENT.md`, `IMPLEMENTATION_STATUS.md`, `COMPLETE.md` | repo root |

A framing note worth recording: that branch described itself as making the
project "production-ready for real money trading." This repository states the
opposite — the ROADMAP's header is "Educational use only. Not investment advice;
not intended for real trading." The persistence design follows from that.

### Already solved in v2, in a different idiom — nothing to port

| Finding | How v2 does it |
|---|---|
| Retry with exponential backoff | `hedge_fund/data/client.py` retries on HTTP 429; `hedge_fund/llm/client.py` honors `Retry-After` (delta-seconds and HTTP-date) and refuses a delay that exceeds the timeout |
| Custom exception hierarchy | `FDClientError` (`data/client.py`), `LLMCallError` / `LLMParseError` (`llm/client.py`), `JevContractError` (`llm/contract.py`), `InsufficientData` (`features/snapshot.py`) |
| Structured logging | stdlib per-module loggers in `backtesting/engine.py`, `signals/llm_agent.py`, `event_study/engine.py`, `data/client.py`; the `__main__` entry points tune log levels per module |
| Test suite with fixtures | 20 test modules co-located with the code they test, plus `hedge_fund/conftest.py` — 395 passing, 38 skipped |
| Position-concentration limits | `hedge_fund/risk/limits.py`: `max_position_pct` and `max_gross_exposure`, applied as non-negotiable clamps after portfolio construction, each clamp recorded as a `ClampEvent` |
| Persisting decisions, signals and NAV | every run and backtest writes a full `CycleRecord` receipt under `~/.hedge-fund/` (`hedge_fund/paths.py`, `run.py`, `tui/app.py`); the TUI browses that history |

### Still genuinely open

Real gaps, all consistent with v2's design and already visible on the roadmap.
Left unimplemented here by decision — this change is scoped to the reconciliation
plus the test fix.

| Gap | Current state |
|---|---|
| Cash-reserve floor | `RiskLimits` caps per-position and gross exposure but has no minimum-cash constraint. The review proposed `min_cash_reserve_pct = 0.10`. |
| Cost basis, realized gains, commissions | `SimBroker` tracks signed shares and cash only. Its docstring already declares slippage and costs a future addition inside `place_order`. |
| CI | `.github/` holds two issue templates and no workflow; nothing runs the suite on push. |

## What this change does

1. **Fixes 5 tests broken on a clean checkout.** Upstream `154a8b2` ("Update the
   models") edited `hedge_fund/llm/api_models.json` without updating the tests
   that assert against it: `gpt-5.5` became `gpt-5.6`, and the Jev display name
   `"Jev — TypeSafe"` became `"Jev"`. Three assertions in
   `hedge_fund/llm/test_client.py` and `hedge_fund/tui/test_app.py` were updated
   to match the registry. Suite goes from 5 failures to green.
2. **Records this reconciliation**, so the review branch can be left where it is
   instead of being re-litigated.
