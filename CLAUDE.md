# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout

The repo is a Python 3.11 monorepo managed by a single root `pyproject.toml`/Poetry env. Three Python packages share that env:

- `src/` — CLI hedge-fund + backtester (the original engine).
- `app/backend/` — FastAPI service that exposes `src/` as REST/streaming endpoints, plus its own SQLAlchemy/Alembic persistence layer.
- `v2/` — **WIP, not integrated.** Standalone quantitative pipeline (signals → features → portfolio → risk → execution). Treat as a separate codebase; do not wire it into `src/` or `app/` unless explicitly asked.

Plus a Vite/React/TypeScript frontend in `app/frontend/` (separate npm package) and a Dockerized runner in `docker/`.

## Common Commands

All Python commands assume Poetry is installed and `poetry install` has been run from the repo root (this installs `src`, `v2`, and `app` as editable packages from one lockfile).

### CLI hedge fund / backtester (`src/`)

```bash
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --start-date 2024-01-01 --end-date 2024-03-01
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama         # use local Ollama models
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA            # same flags as main.py
poetry run backtester --ticker AAPL,MSFT,NVDA                          # same, via console script
```

`questionary` prompts for analyst selection and model choice are interactive — when running in non-TTY contexts pass `--analysts` / model flags explicitly via `src/cli/input.py`.

### Web app

Backend (FastAPI on `:8000`, with auto-reload):
```bash
cd app/backend && poetry run uvicorn main:app --reload
```

Frontend (Vite on `:5173`):
```bash
cd app/frontend
npm install
npm run dev      # dev server
npm run build    # tsc + vite build
npm run lint     # eslint, --max-warnings 0
```

One-shot setup (from repo root): `cd app && ./run.sh` (Mac/Linux) or `run.bat` (Windows). It installs deps and starts both services.

### Tests

```bash
poetry run pytest                                   # everything
poetry run pytest tests/backtesting                 # one suite
poetry run pytest tests/backtesting/test_metrics.py # one file
poetry run pytest tests/backtesting/test_metrics.py::test_name -v   # single test
```

Note: only `src/` has test coverage today (`tests/backtesting/`, `tests/test_api_rate_limiting.py`, `tests/test_cache.py`). `v2/` and `app/` have no tests in this repo.

### Formatting / linting

Configured in `pyproject.toml` but not wired to a hook: `poetry run black .`, `poetry run isort .`, `poetry run flake8`. Black `line-length = 420` is intentional — do not "fix" long lines reflexively.

### Docker

Use `docker/run.sh` (or `run.bat`) wrappers, not raw `docker compose` calls — they handle the `embedded-ollama` profile and `OLLAMA_BASE_URL` plumbing:

```bash
cd docker
./run.sh build
./run.sh --ticker AAPL,MSFT,NVDA main           # run hedge fund
./run.sh --ticker AAPL,MSFT,NVDA backtest       # run backtester
./run.sh --ticker AAPL,MSFT,NVDA --ollama main  # use bundled Ollama container
./run.sh --ticker AAPL --ollama --ollama-base-url http://host:11434 main  # external Ollama
```

## Architecture

### LangGraph workflow (`src/`)

The hedge fund is a `langgraph.StateGraph` over a shared `AgentState` (`src/graph/state.py`):

```
start_node → [selected analyst agents in parallel] → risk_management_agent → portfolio_manager → END
```

`AgentState` is a `TypedDict` with three reducer-merged fields: `messages` (list-append), `data` (dict-merge — holds `tickers`, `portfolio`, `start_date`, `end_date`, and the `analyst_signals` accumulator each analyst writes into), and `metadata` (dict-merge — `show_reasoning`, `model_name`, `model_provider`). Analysts read prior state, fetch data, and append their signal to `data["analyst_signals"]`. The risk manager reads all signals and writes per-ticker `remaining_position_limit` + `current_price`. The portfolio manager consumes both and emits the final JSON decision per ticker.

**`src/utils/analysts.py` is the single source of truth** for the analyst roster. `ANALYST_CONFIG` (a dict keyed by analyst slug) drives: workflow node creation in `main.py`, CLI questionary choices, and the `/agents` API response. Adding an analyst = add a module under `src/agents/`, then one entry in `ANALYST_CONFIG`. Don't register agents in multiple places.

In multi-run/web contexts, agents are instantiated with suffixed IDs (`portfolio_manager_<suffix>` / `risk_management_agent_<suffix>`) so concurrent flows don't collide; the portfolio manager looks up its peer risk manager by stripping that suffix (see `src/agents/portfolio_manager.py:40`). Preserve that convention if you change either.

### LLM dispatch (`src/llm/`, `src/utils/llm.py`)

Providers are enumerated in `src/llm/models.py::ModelProvider`; available models live in `src/llm/api_models.json` and `src/llm/ollama_models.json`. `LLMModel.has_json_mode()` encodes per-provider JSON-mode quirks (DeepSeek/Gemini = no JSON mode; only `llama3` and `neural-chat` Ollama models support it). `src/utils/llm.call_llm` is the single call site — route new agents through it so retries, JSON parsing, and structured-output handling stay consistent.

DeepSeek output is non-strict; `extract_json_from_response` in `src/utils/llm.py` handles its leading/trailing prose (see fix in commit `0210109` for context).

### Backend (`app/backend/`)

FastAPI app in `app/backend/main.py` mounts routers from `app/backend/routes/__init__.py` (`hedge_fund`, `flows`, `flow_runs`, `language_models`, `ollama`, `api_keys`, `storage`, `health`). Layered structure:

- `routes/` — HTTP handlers, thin.
- `services/` — orchestration (e.g. `agent_service.py` wraps `src/` agents with per-run IDs via `functools.partial`; `graph.py` builds per-request workflows; `backtest_service.py` drives the backtester; `ollama_service.py` manages the local Ollama lifecycle).
- `repositories/` + `database/` — SQLAlchemy models and persistence. DB tables auto-create on startup via `Base.metadata.create_all`; schema migrations live in `app/backend/alembic/versions/`. CORS is hardcoded to `http://localhost:5173`.

When adding endpoints, prefer extending an existing router and a service over inlining business logic in the route. Re-use `src/`; don't duplicate agent code into `app/`.

### Data / API (`src/tools/api.py`, `src/data/`)

All financial data flows through `src/tools/api.py` (Financial Datasets API + retry/backoff for 429s) and is cached in-process via `src/data/cache.Cache` (a singleton from `get_cache()`). Cache merges by stable key per data type (e.g. prices by `time`, financials by `report_period`). If you add a new data endpoint, plumb it through `_make_api_request` and add a cache slot — do not call `requests` directly from agents.

Free tickers (no FD key needed): AAPL, GOOGL, MSFT, NVDA, TSLA. Anything else requires `FINANCIAL_DATASETS_API_KEY`.

### Frontend (`app/frontend/`)

Vite + React 18 + TypeScript + Tailwind + shadcn/ui + `@xyflow/react` (the flow editor is the main UI). Path alias `@/` is configured in `tsconfig.json` / `vite.config.ts`. `npm run build` runs `tsc` first, so type errors block the build.

### v2 (`v2/`)

Independent quantitative pipeline. Architecture: `data/` → `signals/` → `features/` → `portfolio/` → `risk/` → `pipeline/`, with `validation/` (CPCV, PBO) and `backtesting/` orthogonal to the flow. Data contracts live in `v2/models.py` (`SignalResult` constrained to `[-1, +1]`, `QuantSignals`, `PortfolioTarget`, `TradeOrder`, `ExecutionResult`). New signals subclass `v2/signals/base.BaseSignal`. Do not import from `src/` into `v2/` or vice-versa — they are intentionally separate.

## Conventions

- Python target is **3.11** (Poetry constraint `^3.11`); 3.13 has known compatibility issues per `app/README.md`.
- Black line length is `420` and isort uses `force_alphabetical_sort_within_sections = true` — keep imports alphabetized within their section.
- Agents are stateless functions taking `(state: AgentState, agent_id: str = "...")` and returning a dict patch to merge into state. Match that signature when writing new ones.
- Pydantic v2 models for all structured LLM outputs (see `PortfolioDecision` in `src/agents/portfolio_manager.py`); never parse free-form LLM text by regex.
- The system explicitly does not execute real trades. Don't add brokerage integrations.
