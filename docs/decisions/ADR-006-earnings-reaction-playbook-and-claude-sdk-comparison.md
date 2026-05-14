# ADR-006 — Earnings Reaction Playbook: fixed-sequence LangGraph workflow + checkpointing, and the case for Claude Agent SDK elsewhere

**Date:** 2026-05-14
**Status:** Accepted
**Decision-makers:** Thulani Maseko
**Phase reference:** AI Agent Portfolio Phase 2 (see `~/.claude/plans/create-a-comprehensive-plan-buzzing-backus.md`)

## Context

Phase 2 of the AI Agent Portfolio plan called for "adding LangGraph orchestration to ai-hedge-fund." On inspection, **LangGraph is already the orchestration backbone of this repo** (`langgraph==0.2.56` in `pyproject.toml:19`, `StateGraph(AgentState)` in `src/main.py:104`). The 17 investor-persona analysts, the risk manager, and the portfolio manager all run as nodes in a dynamically-assembled `StateGraph`.

What the codebase does NOT currently have:

1. A **named, fixed workflow** that captures a specific business scenario end-to-end. The graph is reassembled per request based on user-selected analysts. There's no "playbook" concept.
2. **Checkpointed state.** Each `invoke()` is transient. A crash mid-run loses everything; the run cannot be resumed; we cannot replay the state at step N for debugging or audit.
3. A **demonstration of when LangGraph is the right tool vs. when something lighter (Claude Agent SDK) is.** The sales conversation needs this nuance.

Phase 2 of the AI Agent Portfolio sells "Agent Loops" as a Prudentia capability. The demo runs live in booked client sessions on `prudentiadigital.co.za/ai/`. The demo must:

- Run unattended through a multi-step workflow (the deliverable)
- Survive a restart and resume cleanly (production credibility)
- Demonstrate the architectural choice clearly to a technical buyer

## Decision

### 1. Add a fixed-sequence "Earnings Reaction Playbook" workflow

New module `src/workflows/earnings_reaction.py` defines a fixed `StateGraph` that the user does not configure. The workflow is:

```
start_node
    │
    ├──► fundamentals_analyst    (financial statement delta around the print)
    ├──► sentiment_analyst       (post-earnings news / social sentiment)
    ├──► technical_analyst       (price-action confirmation)
    ├──► valuation_analyst       (re-rating model output)
    ├──► warren_buffett_agent    (long-term holder POV)
    └──► michael_burry_agent     (contrarian / short-side POV)
              │
              ▼
        risk_management_agent
              │
              ▼
       portfolio_manager
              │
              ▼
             END
```

Six analysts run in parallel after `start_node`. Risk and portfolio nodes consolidate. The graph is identical to the dynamic builder's shape but with a curated, opinionated analyst selection that maps to one business scenario: "a company just reported earnings; what's the right position?"

This is a *workflow*, not a *capability*: it picks a useful subset of the 17 existing agents and wires them as a named, repeatable run.

### 2. Add `SqliteSaver` checkpointing

The compiled workflow takes an optional checkpointer. Two checkpointer modes:

- **`MemorySaver` (default):** in-process, zero-config, used by tests and quick local runs.
- **`SqliteSaver`:** activated when `EARNINGS_REACTION_CHECKPOINT_DB` env var is set to a file path. State persists across process restarts; runs can resume from the last checkpoint.

Sqlite is chosen over Postgres because (a) the rest of the project already uses SQLite (`src/llm/`, upstream `app/backend/database/`), (b) demo systems don't need a separate database server, and (c) `langgraph-checkpoint-sqlite` is the native fit for `langgraph==0.2.56`.

### 3. LangGraph stays the orchestrator for this workflow. Claude Agent SDK gets its own example elsewhere.

This is the decision the sales conversation needs to articulate cleanly:

**LangGraph is the right tool when:**
- The workflow has a fixed shape (DAG / state machine) known up front.
- Multiple agents need to share structured state via reducers.
- Checkpoint, replay, time-travel debugging, and state inspection matter (production / audit).
- The workflow is the product — durability and observability outrank tool-loop flexibility.

**Claude Agent SDK is the right tool when:**
- The agent picks its own tools dynamically per request (no fixed DAG).
- The shape of the work isn't known up front; the agent decides.
- The conversation is the deliverable (chat-style) rather than a workflow finishing unattended.
- You're building inside a Claude-native experience (Claude Desktop, Claude Code, API tool-use).

The Earnings Reaction Playbook fits the first column squarely: known shape, shared state, persistence matters, the workflow itself is the product. LangGraph wins. A separate Phase-2-follow-up will add a small Claude Agent SDK example in `examples/claude_agent_sdk/` to show the comparison concretely; it is **not** intended to replace this workflow, only to illustrate where the SDK is the natural choice (e.g., a chatty financial-data exploration agent that the user drives one question at a time).

## Rejected alternatives

- **"Add LangGraph from scratch."** Plan framing. Rejected because LangGraph is already the backbone — this would be redundant.
- **Add SqliteSaver as the only option, no MemorySaver fallback.** Rejected because tests should not write to disk, and the dev path benefits from a zero-config default.
- **Use Postgres / SQLModel for checkpointing.** Rejected because the project's existing SQLite usage and the official `langgraph-checkpoint-sqlite` package give a cleaner path; Postgres can come later if multi-tenant pilots demand it.
- **Make the workflow user-configurable.** Rejected because the value proposition is "we curated this playbook so you don't have to" — configurability undermines the offer.
- **Rebuild on Claude Agent SDK.** Rejected because the workflow does not need dynamic tool selection; LangGraph's state-machine model fits better and the codebase is already there.

## Consequences

- New module `src/workflows/` that other named playbooks can join later (e.g., "Macro Regime Shift Playbook", "Insider-Trading-Pattern Playbook")
- Sales demos for the Agent Loops capability anchor on this workflow
- A new dependency: `langgraph-checkpoint-sqlite>=2.0.0,<3.0.0` (pinned to the 2.x band compatible with LangGraph 0.2.x). Will bump in lockstep with ADR-005's LangChain/LangGraph migration.
- The existing dynamic `/hedge-fund/run` route in `app/backend/routes/hedge_fund.py` is **not modified**. FastAPI wiring for the new fixed workflow is deferred to a follow-up commit so it doesn't collide with Thulani's in-flight `F2.5/F3/F4` server work on `server/`.
- A `docs/sales-demo.md` and `docs/pre-demo-checklist.md` ship alongside this ADR to keep the demo system rehearsed and operationally honest.

## Implementation references

- Workflow module: `src/workflows/earnings_reaction.py`
- Tests: `tests/workflows/test_earnings_reaction.py`
- Sales demo: `docs/sales-demo.md`
- Pre-demo checklist: `docs/pre-demo-checklist.md`
- Compatible dep: `langgraph-checkpoint-sqlite>=2.0.0,<3.0.0` in `pyproject.toml`
