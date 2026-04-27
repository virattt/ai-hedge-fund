# ADR-003 — SSE (server-sent events) over WebSocket for live agent / backtest streams

- **Status:** Accepted (2026-04-27)
- **Context:** Phase F2 — pick the wire protocol for streaming agent progress and backtest day events to the browser.
- **Owners:** ltmas

## Problem

The browser needs live updates as LangGraph nodes complete (`agent.completed`, `risk.computed`, `decision.final`) and as backtest days execute. Direction is server → client only; the client doesn't push events back during a run. We need replay, refresh-resume, and graceful failure handling.

## Options considered

| Option | Verdict |
|---|---|
| **SSE via `sse-starlette`** | **Chosen.** One-direction (server → client) matches our event flow exactly. Plain HTTP, works through proxies, automatic reconnect built into the EventSource API, easy to replay from persisted `run_events` rows by streaming them back as SSE. |
| WebSocket | Two-way overhead we don't need. More complex reconnection logic. Some homelab proxies need extra config to upgrade. Worth revisiting only if the UI ever sends mid-run "cancel" / "pause" signals — at which point WS becomes appropriate. |
| Long polling | Wasteful; ties up server workers. |
| gRPC-web | Over-engineered for this use case; non-trivial frontend tooling. |

## Decision

SSE for live and replay streams. `EventSource` on the client with `eventsource-parser` as a `fetch()`-stream fallback (some browsers don't allow EventSource POST; if we ever need POST-body SSE we can use `fetch + ReadableStream + eventsource-parser`).

LangGraph's `.astream(stream_mode="updates")` yields per-node deltas which map 1:1 to SSE events. Backtest events are server-side coalesced per business-day boundary (one batched envelope per day) to keep wire payload < 200 KB/run.

## Consequences

- **Cancellation requires a side channel.** When the UI wants to cancel a run, it issues `DELETE /runs/{id}` (REST), not a message on the SSE stream. The server signals cancel via an `asyncio.Event` watched by the streaming task. F4.
- **Refresh-resume is trivial.** On `GET /runs/{id}/events` the server replays persisted `run_events` rows as SSE (with a `replay: true` field on each event so the client can fast-forward animations).
- **Reconsider WS if** we add live multi-user collaboration features (cursors, comments) — those are out of scope until F5.

## References

- `/Users/ltmas/.claude/plans/do-a-full-parsed-sparrow.md` §B3
- `sse-starlette`: https://github.com/sysid/sse-starlette
