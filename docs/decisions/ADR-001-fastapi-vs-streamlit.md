# ADR-001 — FastAPI + React over Streamlit / Gradio / Next.js for the web UI

- **Status:** Accepted (2026-04-27)
- **Context:** Phase F1 of the frontend plan (`/Users/ltmas/.claude/plans/do-a-full-parsed-sparrow.md`).
- **Owners:** ltmas

## Problem

The hedge-fund system today is a Python CLI built on LangGraph (`src/main.py:53`, `src/backtester.py:29`). We want a web UI that exposes per-agent live progress, decision tables, backtest equity curves, and run history. Single-user to start, multi-user later.

## Options considered

| Option | Verdict |
|---|---|
| **FastAPI + React (Vite/TS)** | **Chosen.** Async-native, perfect for `LangGraph.astream(stream_mode="updates")`. Full UX control. Backend wraps the existing Python code 1:1 — `run_hedge_fund` and `Backtester` stay the source of truth. |
| Streamlit | Single-process; weak per-agent streaming; clunky multi-screen state; charts/tables fight the framework once we add real interactivity. |
| Gradio | Even more opinionated than Streamlit; equity-curve + backtest day-breakdown tables would be awkward; no shareable runs/replay. |
| Next.js full-stack | Forces re-implementing LangGraph orchestration in JS or shelling out to Python — Python is the source of truth, keep it that way. |

## Decision

FastAPI (uvicorn) wraps existing Python; React + Vite + TypeScript on the front; SSE streaming via `sse-starlette`; SQLite via SQLModel for run persistence.

## Consequences

- Two-process dev (uvicorn + vite dev server) — covered by `make dev` / `just dev` (B8).
- Codegen pipeline: `openapi-typescript` against FastAPI's `/openapi.json` becomes the single source of truth for client types.
- Pure backend can ship in F1 without any frontend code (the `/api/runs` sync endpoint is testable via `curl`).
- Streamlit "fast prototype" path is closed — but we never had a working Streamlit in the repo, so no migration cost.

## References

- `/Users/ltmas/.claude/plans/do-a-full-parsed-sparrow.md` §B1
- LangGraph streaming: https://langchain-ai.github.io/langgraph/concepts/streaming/
