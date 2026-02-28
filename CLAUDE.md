# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Hedge Fund — an educational, proof-of-concept system that uses multiple LLM-powered agents (modeled after famous investors) to analyze stocks and make trading decisions. **Not for real trading.**

## Commands

```bash
# Install dependencies
poetry install

# Run the hedge fund (CLI)
poetry run python src/main.py --ticker AAPL,MSFT,NVDA
poetry run python src/main.py --ticker AAPL --start-date 2024-01-01 --end-date 2024-03-01
poetry run python src/main.py --ticker AAPL --ollama  # Use local LLMs

# Run backtester
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA

# Tests
pytest                                    # All tests
pytest tests/backtesting/                 # Unit tests only
pytest tests/backtesting/integration/     # Integration tests only
pytest tests/backtesting/test_metrics.py  # Single test file

# Formatting & linting
black .                    # Format (line-length=420, Python 3.11)
isort .                    # Sort imports (black-compatible profile)
flake8                     # Lint

# Web app (from repo root)
./app/run.sh               # Starts backend (FastAPI) + frontend (React/Vite)
```

## Architecture

### Agent Pipeline (LangGraph)

```
CLI Input / Web UI
       ↓
  ┌─ Analyst Agents (parallel) ─────────────────────┐
  │  Warren Buffett, Ben Graham, Cathie Wood,        │
  │  Michael Burry, Peter Lynch, Fundamentals,       │
  │  Technicals, Sentiment, Valuation, Growth, ...   │
  └──────────────────────────────────────────────────┘
       ↓
  Risk Manager → Portfolio Manager → Trading Output
```

All agents run in parallel via LangGraph's `StateGraph`. Each agent writes signals into the shared `AgentState.data["analyst_signals"]` dict. The Risk Manager and Portfolio Manager run sequentially after all analysts complete.

### Key State: `AgentState` (`src/graph/state.py`)

```python
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]   # append-only
    data: Annotated[dict, merge_dicts]                         # shallow merge
    metadata: Annotated[dict, merge_dicts]                     # shallow merge
```

`merge_dicts` does a shallow `{**a, **b}` merge — nested keys are overwritten, not deep-merged.

### Agent Registry: `src/utils/analysts.py`

Single source of truth for all analyst agents. The `ANALYST_CONFIG` dict maps agent keys to display names, descriptions, agent functions, and ordering. When adding a new agent:
1. Create the agent module in `src/agents/`
2. Register it in `ANALYST_CONFIG` in `src/utils/analysts.py`
3. The workflow builder in `src/main.py` (`create_workflow`) picks it up automatically

### Backtesting Engine (`src/backtesting/`)

Modular design with separated concerns:
- `engine.py` — orchestrates the day-by-day backtest loop
- `controller.py` — runs agents for each time step
- `trader.py` — executes simulated trades
- `portfolio.py` — tracks positions and cash
- `metrics.py` — calculates Sharpe, max drawdown, etc.
- `valuation.py` — portfolio NAV calculation

### LLM Provider Support (`src/llm/`)

Multi-provider via LangChain integrations: OpenAI, Anthropic, DeepSeek, Groq, Google Gemini, xAI, GigaChat, Azure OpenAI, OpenRouter, Ollama. Model lists in `src/llm/api_models.json` and `src/llm/ollama_models.json`.

### Financial Data (`src/data/`)

Uses FinancialDatasets.ai API. Free data for AAPL, GOOGL, MSFT, NVDA, TSLA — other tickers require `FINANCIAL_DATASETS_API_KEY`. In-memory caching layer in `src/data/cache.py`.

### Web App (`app/`)

- **Backend**: FastAPI + SQLAlchemy + Alembic (`app/backend/`)
- **Frontend**: React + Vite + TypeScript + Tailwind CSS + Radix UI (`app/frontend/`)
- Backend serves on default FastAPI port, frontend on Vite's `:5173`

## Environment Variables

Copy `.env.example` to `.env`. At minimum, set one LLM provider key (e.g., `OPENAI_API_KEY`). See `.env.example` for all available keys.
