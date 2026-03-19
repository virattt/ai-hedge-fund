# AI Hedge Fund — Enhancement Milestones

## Overview

8 milestones to add richer data sources, smarter tools, notifications, cloud hosting, and a mobile app to the AI hedge fund system.

- **M1-M5**: Data & analysis improvements
- **M6**: Telegram bot for push notifications
- **M7**: Docker-based cloud deployment
- **M8**: SwiftUI iOS app for mobile portfolio access

## Dependency Graph

```
M1 (Web Scraping) ─── optional ──→ M2 (FinBERT)
                                         │
M3 (13F Tracker) ── independent ─────────┤
                                         │
                                    M4 (Execution)
                                         │
                                    M5 (Framework Layer)

M6 (Telegram) ── independent (can start anytime)
M7 (Hosting)  ── independent (can start anytime)
M8 (iOS App)  ── requires M7 (needs hosted backend)
```

M1 and M3 can be done in parallel. M2 benefits from M1 but works without it. M4 and M5 are independent of each other.
M6 and M7 are standalone. M8 depends on M7. Recommended order for new milestones: M6 → M7 → M8.

## Milestones

| # | Milestone | Status | Risk | Details |
|---|-----------|--------|------|---------|
| 1 | Web Scraping for Full-Text News | Not Started | Low | [milestone-1-web-scraping.md](milestone-1-web-scraping.md) |
| 2 | FinBERT Financial Sentiment Agent | Not Started | Low-Med | [milestone-2-finbert.md](milestone-2-finbert.md) |
| 3 | SEC 13F Institutional Holdings Tracker | Not Started | Medium | [milestone-3-sec-13f.md](milestone-3-sec-13f.md) |
| 4 | Execution & Risk Improvements | Not Started | Low | [milestone-4-execution.md](milestone-4-execution.md) |
| 5 | External Framework Integration Layer | Not Started | Medium | [milestone-5-external-frameworks.md](milestone-5-external-frameworks.md) |
| 6 | Telegram Bot Notifications | Not Started | Low | [milestone-6-telegram.md](milestone-6-telegram.md) |
| 7 | Cloud Deployment (Docker) | Not Started | Medium | [milestone-7-deployment.md](milestone-7-deployment.md) |
| 8 | iOS App (SwiftUI) | Not Started | High | [milestone-8-ios-app.md](milestone-8-ios-app.md) |

## Key Design Decisions

- All new agents follow the existing pattern in `src/agents/` (receive AgentState, analyze, return signal)
- New data sources get their own cache in `src/data/cache.py` (same pattern as existing 5 caches)
- New agents register in `src/utils/analysts.py:ANALYST_CONFIG` (single source of truth)
- Feature flags via env vars for optional/expensive features (e.g., `SCRAPE_FULL_TEXT`)
- Graceful degradation: agents return neutral signals when data sources are unavailable
- Notifications are pluggable (Telegram first, easy to add Discord/Slack later)
- Cloud deployment uses Docker Compose with nginx reverse proxy; SQLite with volume mount
- iOS app is read-only v1, consuming existing REST endpoints
