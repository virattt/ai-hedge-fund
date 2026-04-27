# ADR-005 — Defer the LangChain 1.x / LangGraph 1.x migration past Phase F1

- **Status:** Proposed (2026-04-27) — pending user decision
- **Context:** PyPI scan during Phase F1 scaffolding revealed `langchain` 1.2.15 and `langgraph` 1.1.10 as current stable. The repo currently pins `langchain = "0.3.0"` (`pyproject.toml:12`) and `langgraph = "0.2.56"` (`pyproject.toml:17`).
- **Owners:** ltmas

## Problem

`run_hedge_fund` (`src/main.py:53`), `create_workflow` (`src/main.py:110`), and every analyst agent under `src/agents/` are written against LangChain 0.3 / LangGraph 0.2 APIs. LangChain 1.x reorganized:

- `ChatPromptTemplate` and structured-output APIs (`with_structured_output(method="json_mode")` ergonomics changed)
- Tool calling and message schemas (`HumanMessage` / `AIMessage` shape)
- `LangGraph` `StateGraph` builder ergonomics — `add_edge` / `set_entry_point` retained but stream-mode semantics evolved
- Provider packages (`langchain-openai`, `langchain-anthropic`, etc.) follow their own version cadence and may not all be 1.x-compatible at the same moment

A migration touches **every file in `src/agents/`** plus `src/utils/llm.py` and `src/main.py`.

## Options considered

| Option | Verdict |
|---|---|
| **Stay on 0.3 / 0.2 for F1, plan a dedicated migration in F1.5** | **Recommended.** Keeps F1 deliverable shape minimal (FastAPI wraps the existing function 1:1). Migration becomes its own well-scoped issue with full agent test coverage as the green-light criterion. |
| Migrate during F1 | Couples a UX deliverable with a deep refactor. F1 ships later; risk of subtle decision-quality regressions across 11 agents. |
| Skip the migration indefinitely | Locks the repo to a sunset version line; eventually security and provider compatibility issues bite. Not acceptable past F2. |

## Decision (pending)

Hold `langchain ^0.3` and `langgraph ^0.2` in `pyproject.toml` for F1. Schedule the 1.x migration as **Phase F1.5**, gated on:

1. Smoke tests for every agent (mock LLM + mock financialdatasets) — to be written in F1 anyway as part of resolving A4.
2. A side-by-side run on the same `(tickers, start_date, end_date, model, analysts)` showing decisions match between 0.3 and 1.x within an acceptable similarity threshold (signals identical, confidences within ±5%, decisions identical).
3. All langchain provider packages we use (`langchain-openai`, `langchain-anthropic`, `langchain-groq`, `langchain-deepseek`, `langchain-google-genai`) on 1.x-compatible releases.

## Consequences

- F1 ships against current pins; F1.5 ships the upgrade.
- If item 3 above (provider compat) fails for any provider we currently support, we either drop that provider or pin it to a transition release.
- Downstream consumers (the FastAPI server) only depend on `run_hedge_fund`'s and `Backtester`'s public Python interfaces — so the API surface is invariant across the migration.

## References

- LangChain 1.x release notes: https://python.langchain.com/docs/versions/v1/
- `/Users/ltmas/.claude/plans/do-a-full-parsed-sparrow.md` §B9 #11 (Python target — separately confirmed as 3.13)
