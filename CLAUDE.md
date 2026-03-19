# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered hedge fund proof of concept for educational purposes. Multiple AI analyst agents analyze stocks in parallel, feed signals to a risk manager, then a portfolio manager makes final trading decisions. Uses LangGraph for agent orchestration and LangChain for LLM integration.

## Common Commands

```bash
# Install dependencies
poetry install

# Run the hedge fund (CLI)
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
poetry run python src/main.py --ticker AAPL --start-date 2024-01-01 --end-date 2024-03-01
poetry run python src/main.py --ticker AAPL --ollama  # use local LLMs

# Run the backtester
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA

# Run tests
poetry run pytest
poetry run pytest tests/backtesting/test_metrics.py        # single test file
poetry run pytest tests/backtesting/test_metrics.py::test_name -v  # single test

# Linting/formatting
poetry run black .
poetry run isort .
poetry run flake8

# Web app - backend (from repo root)
poetry run uvicorn app.backend.main:app --reload  # http://localhost:8000

# Web app - frontend
cd app/frontend && npm install && npm run dev     # http://localhost:5173
```

## Architecture

### Core Pipeline (LangGraph)

The system is a LangGraph `StateGraph` defined in `src/main.py:create_workflow()`. The flow is:

```
start_node → [analyst agents in parallel] → risk_management_agent → portfolio_manager → END
```

**State** (`src/graph/state.py`): `AgentState` is a TypedDict with `messages`, `data`, and `metadata` fields. The `data` dict carries tickers, portfolio, date range, and `analyst_signals`. The `metadata` dict carries `show_reasoning`, `model_name`, and `model_provider`.

### Agent Pattern

All analyst agents in `src/agents/` follow the same pattern:
1. Receive `AgentState`, extract tickers and date range
2. Fetch financial data via `src/tools/api.py` (which caches responses via `src/data/cache.py`)
3. Analyze data and call LLM via `src/utils/llm.py:call_llm()` with a Pydantic output model
4. Return a signal (bullish/bearish/neutral) with confidence score and reasoning
5. Store results in `state["data"]["analyst_signals"]`

The analyst registry lives in `src/utils/analysts.py:ANALYST_CONFIG` — this is the single source of truth for adding/removing analysts.

### Key Modules

- `src/tools/api.py` — Financial data API client (prices, metrics, line items, insider trades, news). Uses `src/data/cache.py` for in-memory caching and `src/data/models.py` for Pydantic response models.
- `src/llm/models.py` — LLM provider configuration. Supports OpenAI, Anthropic, DeepSeek, Google, Groq, Ollama, OpenRouter, xAI, GigaChat, Azure OpenAI. Model lists loaded from `src/llm/api_models.json` and `src/llm/ollama_models.json`.
- `src/utils/llm.py:call_llm()` — Unified LLM invocation with structured output, retry logic, and fallback defaults.
- `src/backtesting/` — Backtesting engine (`engine.py`), metrics calculation (`metrics.py`), trade execution (`trader.py`).

### Web App

- **Backend**: FastAPI app in `app/backend/`. Routes in `app/backend/routes/`, services in `app/backend/services/`. SQLite database with Alembic migrations in `app/backend/alembic/`. The graph service (`app/backend/services/graph.py`) wraps the core pipeline for web use.
- **Frontend**: React + Vite + TypeScript app in `app/frontend/`. Uses React Flow for visualization, shadcn/ui components, Tailwind CSS.

## Code Style

- Python 3.11+, managed with Poetry
- Black formatter with line length 420 (see `pyproject.toml`)
- isort with black profile
- Type hints use `X | None` syntax (not `Optional[X]`)
