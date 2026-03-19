# Milestone 8: iOS App (SwiftUI)

**Goal:** SwiftUI iPhone app that connects to the hosted backend (M7) to show portfolio state, agent signals, and run history on the go.

**Risk:** High
**Dependencies:** Requires M7 (needs a reachable backend to be useful beyond localhost)

## Key Decisions

- Read-only v1: view portfolio, signals, run history — no triggering runs from phone initially
- Consumes existing REST endpoints (`/hedge-fund/agents`, `/flows`, `/flows/{id}/runs`)
- SSE streaming for live run progress using `URLSession.bytes(for:)` (no external dependencies)
- Skip push notifications in v1 — Telegram (M6) covers passive alerts already
- Requires M7 (hosted backend) to be useful beyond localhost

## Tasks

- [ ] Create Xcode project at `ios/AIHedgeFund.xcodeproj`
- [ ] Create data models (AgentSignal, Flow, FlowRun, Portfolio) — Codable structs matching backend JSON
- [ ] Create `APIClient` service with configurable base URL, async/await
- [ ] Create `SSEClient` for live streaming of run progress
- [ ] Create `DashboardView` — main tab: portfolio overview + recent signals
- [ ] Create `FlowListView` — list of saved flows
- [ ] Create `RunDetailView` — per-run detail: agent signals, portfolio decisions
- [ ] Create `SettingsView` — server URL configuration
- [ ] Add `GET /hedge-fund/runs/{id}/result` endpoint in backend if needed for iOS consumption
- [ ] Write unit tests for `APIClient` and model decoding
- [ ] Integration test: connect to hosted backend, view data

## Files to Create

| File | Purpose |
|------|---------|
| `ios/AIHedgeFund.xcodeproj` | Xcode project |
| `ios/AIHedgeFund/App.swift` | App entry point |
| `ios/AIHedgeFund/Models/AgentSignal.swift` | Agent signal model |
| `ios/AIHedgeFund/Models/Flow.swift` | Flow model |
| `ios/AIHedgeFund/Models/FlowRun.swift` | Flow run model |
| `ios/AIHedgeFund/Models/Portfolio.swift` | Portfolio model |
| `ios/AIHedgeFund/Services/APIClient.swift` | REST client (async/await) |
| `ios/AIHedgeFund/Services/SSEClient.swift` | Server-Sent Events parser |
| `ios/AIHedgeFund/Views/DashboardView.swift` | Portfolio overview + signals |
| `ios/AIHedgeFund/Views/FlowListView.swift` | Saved flows list |
| `ios/AIHedgeFund/Views/RunDetailView.swift` | Run detail with agent signals |
| `ios/AIHedgeFund/Views/SettingsView.swift` | Server URL configuration |
| `ios/AIHedgeFundTests/` | Unit tests |

## Files to Modify

| File | Change |
|------|--------|
| `app/backend/routes/hedge_fund.py` | Add `GET /hedge-fund/runs/{id}/result` if needed |

## Verification

1. Build and run in Xcode Simulator
2. Configure server URL to point at hosted backend (M7)
3. View existing flows and past run results
4. Start a run from web app → see live SSE updates on iOS
