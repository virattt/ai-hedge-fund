# ADR-004 — Zustand + TanStack Query over Redux Toolkit for client state

- **Status:** Accepted (2026-04-27)
- **Context:** Phase F2 — pick a client state management library.
- **Owners:** ltmas

## Problem

Frontend has two distinct kinds of state:

1. **Server cache** — analyst list, model list, ticker data, completed runs. Mostly cacheable, sometimes refetchable.
2. **Per-run timeline** — live SSE events accumulating into per-agent cards, plus form draft state and UI flags. Local, transient, frequently updated.

We want type-safe slices, minimal boilerplate, and easy testability.

## Options considered

| Option | Verdict |
|---|---|
| **Zustand + TanStack Query** | **Chosen.** TanStack Query owns server cache (caching, retries, suspense). Zustand owns per-run timeline slices and form draft state. Zero boilerplate, slice-based code splitting, native devtools. |
| Redux Toolkit + RTK Query | Same shape as the chosen option but more boilerplate (slices, reducers, actions, selectors). RTK Query is solid but doesn't give us anything TanStack Query doesn't, and we're already pulling TanStack Table + TanStack Virtual — staying in the TanStack ecosystem reduces vendor count. |
| Jotai / Recoil | Atom-based works fine but the per-run timeline is naturally a slice with derived computed selectors — Zustand's `(set, get) =>` API matches the shape better. |
| Plain React context | OK for tiny apps; the timeline updates many times per second during a backtest, and re-rendering every consumer would tank perf. Rejected. |

## Decision

- **Server state**: TanStack Query v5 (default). Hooks like `useAnalysts()`, `useModels()`, `useRun(id)`.
- **Per-run timeline**: Zustand store keyed by `run_id`. Slice contains: `agents: Record<string, AgentCardState>`, `decisions: Decision[]`, `metrics: BacktestMetrics`, plus actions (`onSseEvent`, `reset`, `replay`).
- **Form draft state**: react-hook-form (separate from Zustand — its own ref-based store).

## Consequences

- Two store mechanisms in the codebase — but they serve different purposes and never overlap.
- Zustand stores are vanilla JS — easily unit-testable without React.
- If we ever need time-travel debugging, RTK is a simple pivot (Zustand's API surface is small).

## References

- `/Users/ltmas/.claude/plans/do-a-full-parsed-sparrow.md` §B6
