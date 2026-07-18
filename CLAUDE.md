# CLAUDE.md

Guidance for Claude Code when working in this repo.

## What this is

AI Hedge Fund — an educational proof-of-concept where multiple LLM "investor" agents
(Buffett, Munger, Burry, etc.) plus valuation/sentiment/fundamentals/technicals agents
feed a risk manager and portfolio manager to produce trading *signals*. It does **not**
place real trades. Educational/research use only.

The project is mid-rebuild: `src/` is the current v1 system; `v2/` is the in-progress
redesign (fund-as-entity, pluggable "alpha models"). See `VISION.md` and `ROADMAP.md`.

## Layout

- `src/` — v1 hedge fund. Entry points:
  - `src/main.py` — run the agents once for given tickers.
  - `src/backtester.py` — backtest over a date range.
  - `src/cli/input.py` — shared CLI arg parsing (`parse_cli_inputs`).
  - `src/agents/` — one file per investor agent.
  - `src/llm/models.py`, `src/llm/ollama_models.json` — model registry (cloud + local Ollama).
  - `src/utils/ollama.py` — Ollama install/model checks.
- `v2/` — next-gen redesign (signals, event studies, risk, data clients). Has its own tests.
- `app/` — full-stack web application (`app/backend` FastAPI, `app/frontend` React).
- `scripts/analyze.sh` — interactive launcher: prompts for tickers, offers local Ollama.

## Running

Uses Poetry (Python ^3.11).

```bash
poetry install
poetry run python src/main.py --ticker AAPL,MSFT,NVDA            # analyze
poetry run python src/main.py --ticker AAPL,MSFT,NVDA --ollama   # local LLM
poetry run python src/backtester.py --ticker AAPL,MSFT,NVDA      # backtest
```

Or the interactive wrapper (prompts for comma-separated tickers, then offers Ollama):

```bash
./scripts/analyze.sh
TICKERS=AAPL,MSFT ./scripts/analyze.sh --ollama --model gpt-oss:20b   # non-interactive
```

`--tickers` / `--ticker` are aliases (comma-separated). `--model <name>` skips the
interactive model picker; combine with `--ollama` to force a local model.

## Local Ollama

Local models must be registered in `src/llm/ollama_models.json` to appear in the picker
(matched by `model_name`). Requires the model to be pulled in Ollama first.

## Conventions

- Match surrounding code style; the CLI standardizes flags via `add_common_args` in
  `src/cli/input.py` — add new shared flags there rather than per-script.
- Commit only when asked. `.env` holds API keys (copy from `.env.example`); never commit it.
