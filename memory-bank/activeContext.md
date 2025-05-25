# Active Context: AI Hedge Fund

## Current Work Focus
- **Branch:** `graceful-rate-limiting`
- **Objective:** Initial setup of the Memory Bank for the 'ai-hedge-fund' project. Establishing foundational documentation to guide development.
- **Primary Task:** Implement graceful rate limiting for external API interactions.

## Recent Changes & Decisions
- **(This document - In Progress)**
- **5/25/2025:**
    - Initialized the Memory Bank by creating all core files.
    - Read `ai-hedge-fund/README.md`, `ai-hedge-fund/pyproject.toml`, `ai-hedge-fund/package.json`, `ai-hedge-fund/Dockerfile`, and `ai-hedge-fund/docker-compose.yml` to gather initial project information.
    - Updated `projectbrief.md`, `productContext.md`, `systemPatterns.md`, and `techContext.md` with information extracted from these files.
    - Updated `activeContext.md` (this file) and `progress.md`.

## Next Immediate Steps
1.  Implement graceful rate limiting in `src/tools/api.py` for FinancialDatasets.ai API calls.
2.  Write unit tests or simulate 429 responses to validate retry logic for `get_prices`, `get_financial_metrics`, and `search_line_items`.
3.  Monitor and adjust retry parameters (max_retries, backoff) as needed.

## Active Questions & Considerations
- What are the specific external APIs the project interacts with?
- What are their respective rate limits (requests per second/minute/hour, concurrent requests, etc.)?
- What is the desired behavior when a rate limit is hit (e.g., exponential backoff, queue requests, drop requests, notify user)?
- Are there existing mechanisms or libraries in the project for API interaction that need to be adapted?

## Initial State
- This document was created on 5/25/2025.
- Current development focus: 'graceful-rate-limiting' branch.
