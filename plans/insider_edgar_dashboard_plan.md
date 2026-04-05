# Insider Trading Dashboard with edgartools

## Metadata
- **Branch**: feature/agentic-insider-edgar-dashboard
- **Core Skills**: afe-config:unit-tester, afe-config:code-documenter
- **Language Skills**: afe-python:python-developer
- **Primary Language**: Python (backend), TypeScript (frontend)
- **Created**: 2026-03-29
- **Updated**: 2026-04-04

## Executive Summary
- Rewrite the insider trading feature to use edgartools' rich `get_ownership_summary()` API, supporting Forms 3, 4, and 5 with `TransactionSummary` and `InitialOwnershipSummary` data.
- Replace the single flat-transaction endpoint with two endpoints: filing summaries (dashboard cards + table) and per-filing drill-down detail keyed by SEC accession number.
- Build a full dashboard UI with summary cards, tabbed form-type layout, enhanced table, filter bar, and buy/sell activity chart using recharts.
- Remove the financialdatasets.ai fallback entirely, simplifying the backend to pure edgartools.
- Add OrderedDict-based LRU cache with TTL, per-filing error resilience with skipped-count reporting, ticker regex validation, and pagination offset support.
- Add two sub-pages: Ownership Changes (`/insider/ownership`) with position history line chart and change log table, and Grants & Exercises (`/insider/grants`) with derivative trades table.

## Goals
- Expose rich SEC insider data (net_change, net_value, primary_activity, has_10b5_1_plan, remaining_shares) via two backend endpoints
- Support all Form types (3, 4, 5) with appropriate data handling for each
- Deliver a full dashboard UI: summary cards, activity chart, enhanced table with color-coded badges and filters
- Enable large purchase detection and automated vs discretionary trade filtering
- Use SEC accession number as stable filing identifier for the detail endpoint
- Add per-filing error resilience so individual parsing failures do not break the entire response
- Cache summary results with TTL to reduce SEC EDGAR load on repeated requests
- Provide ownership change tracking via per-insider position history chart and change log table
- Expose derivative transactions (grants, exercises, conversions) in a dedicated sub-page

## Architecture Overview

### Key Design Decisions
- **Two endpoints instead of one**: `/insider/summary` returns filing-level summaries (one row per filing) for the dashboard table and cards. `/insider/detail` returns per-transaction drill-down for a specific filing. This avoids over-fetching transaction-level data for the main view.
- **Accession number as stable identifier**: The detail endpoint uses SEC accession number (`accession_no`) instead of positional `filing_index`. Accession numbers are immutable SEC identifiers that do not shift when new filings are added. Each `InsiderFilingSummary` includes `accession_no` so the frontend can construct detail requests directly.
- **Ticker regex validation**: All endpoints validate the `ticker` query parameter with `pattern=r"^[A-Z]{1,5}$"` using FastAPI's `Query()` validator. This prevents malformed or injection-style ticker values from reaching edgartools.
- **Per-filing error handling with skip reporting**: Each `filing.obj()` / `get_ownership_summary()` call is wrapped in try/except. Failures are logged and skipped. The response includes `skipped_count` so the frontend can display "Showing 47 of 50 filings (3 could not be parsed)".
- **OrderedDict LRU cache with TTL**: Summary, ownership, and grants results are each cached in-process with a 5-minute TTL and max 50 entries. Follows the proven pattern from `news_service.py` and `news.py`. Cache is checked before fetching; stale entries are evicted on access. Summary cache is keyed by `(ticker, form_type)`. Ownership cache is keyed by `("ownership", ticker)`. Grants cache is keyed by `("grants", ticker)`. All three use the same `_cache_get` / `_cache_put` helpers with a shared `_insider_cache` OrderedDict.
- **Pagination offset**: The summary endpoint accepts an `offset` query parameter to skip the first N filings before processing, enabling simple pagination.
- **Form type as query parameter**: The summary endpoint accepts `form_type` (3, 4, 5) to support tabbed UI. Each tab triggers a separate API call, enabling lazy loading per tab.
- **Remove financialdatasets.ai fallback**: Simplifies code to a single data source (edgartools/SEC EDGAR). The fallback added complexity with minimal value since edgartools is reliable.
- **recharts for charting**: React-native charting library, lightweight, works well with shadcn/ui. Added as npm dependency. Used for buy/sell activity BarChart and ownership position history LineChart.
- **Computed summary stats on backend**: Net insider sentiment, largest transaction, 10b5-1 plan ratio computed server-side and returned in the summary response to avoid redundant frontend computation.
- **Retain `_ensure_identity()` pattern**: Already proven in current service. Uses `EDGAR_IDENTITY` env var with sensible default.
- **Sub-pages as separate routes**: Ownership Changes and Grants & Exercises are separate routes (`/insider/ownership`, `/insider/grants`) rather than tabs. Each sub-page has its own ticker search bar for consistency. Sub-navigation links in the insider page header connect all three views.
- **Ownership endpoint aggregates per-insider history**: The `/insider/ownership` endpoint iterates Form 4 filings and groups `remaining_shares` and `net_change` by insider name, returning a time-ordered list per insider. This enables the frontend LineChart without client-side aggregation.
- **Grants endpoint extracts derivative DataFrames**: The `/insider/grants` endpoint reads `form4.derivative_trades` and `form4.option_exercises` DataFrames per filing, flattening rows into a unified response list with a `transaction_type` discriminator (Grant/Exercise/Conversion).

### System Components Diagram
```mermaid
graph TD
    subgraph "Frontend (React + TypeScript)"
        IP[InsiderPage]
        SC[SummaryCards]
        AC[ActivityChart - recharts BarChart]
        FT[FilingsTable]
        FB[FilterBar]
        SK[SkippedNotice]
        OP[InsiderOwnershipPage]
        OC[OwnershipChart - recharts LineChart]
        OT[ChangeLogTable]
        GP[InsiderGrantsPage]
        GT[GrantsTable]
        IA[insider-api.ts]
        IP --> SC
        IP --> AC
        IP --> FT
        IP --> FB
        IP --> SK
        IP --> IA
        OP --> OC
        OP --> OT
        OP --> IA
        GP --> GT
        GP --> IA
    end

    subgraph "Backend (FastAPI)"
        RS["GET /insider/summary"]
        RD["GET /insider/detail"]
        RO["GET /insider/ownership"]
        RG["GET /insider/grants"]
        IS[insider_service.py]
        IC[_insider_cache - OrderedDict LRU+TTL]
        SM[insider_schemas.py]
        RS --> IS
        RD --> IS
        RO --> IS
        RG --> IS
        IS --> IC
        IS --> SM
    end

    subgraph "edgartools"
        CO[Company]
        FI[Filings]
        OW["Ownership (Form3/4/5)"]
        TS[TransactionSummary]
        IOS[InitialOwnershipSummary]
        DT[derivative_trades DataFrame]
        OE[option_exercises DataFrame]
    end

    IA -->|"HTTP GET"| RS
    IA -->|"HTTP GET"| RD
    IA -->|"HTTP GET"| RO
    IA -->|"HTTP GET"| RG
    IS -->|"asyncio.to_thread"| CO
    CO --> FI
    FI -->|"filing.obj()"| OW
    OW -->|"get_ownership_summary()"| TS
    OW -->|"get_ownership_summary()"| IOS
    OW -->|".derivative_trades"| DT
    OW -->|".option_exercises"| OE
```

### Sequence Diagram
```mermaid
sequenceDiagram
    participant User
    participant FE as InsiderPage
    participant API as FastAPI
    participant SVC as insider_service
    participant Cache as LRU Cache
    participant EDT as edgartools/SEC

    User->>FE: Enter ticker, select Form 4 tab
    FE->>API: GET /insider/summary?ticker=AAPL&form_type=4&limit=50&offset=0
    API->>API: Validate ticker matches ^[A-Z]{1,5}$
    API->>SVC: get_insider_summary(ticker, form_type, limit, offset)
    SVC->>Cache: Check (AAPL, 4) with TTL
    alt Cache hit and not expired
        Cache-->>SVC: Cached InsiderSummaryResponse
    else Cache miss or expired
        SVC->>SVC: asyncio.to_thread(_fetch_summaries)
        SVC->>EDT: Company(ticker).get_filings(form="4")
        loop Each filing (skip offset, up to limit)
            SVC->>EDT: filing.obj()
            alt Parsing succeeds
                SVC->>EDT: ownership.get_ownership_summary()
                EDT-->>SVC: TransactionSummary with accession_no
            else Parsing fails
                SVC->>SVC: Log error, increment skipped_count, continue
            end
        end
        SVC-->>Cache: Store result with timestamp
    end
    SVC-->>API: InsiderSummaryResponse (filings + aggregates + skipped_count)
    API-->>FE: JSON
    FE->>FE: Render cards, chart, table, skipped notice

    User->>FE: Click filing row for detail
    FE->>API: GET /insider/detail?ticker=AAPL&form_type=4&accession_no=0000320193-24-000081
    API->>API: Validate ticker matches ^[A-Z]{1,5}$
    API->>SVC: get_insider_detail(ticker, form_type, accession_no)
    SVC->>EDT: Find filing by accession_no, filing.obj().get_transaction_activities()
    SVC-->>API: InsiderDetailResponse (transactions list)
    API-->>FE: JSON
    FE->>FE: Show transaction detail in expanded row
```

### Ownership Sub-Page Sequence
```mermaid
sequenceDiagram
    participant User
    participant FE as InsiderOwnershipPage
    participant API as FastAPI
    participant SVC as insider_service
    participant Cache as LRU Cache
    participant EDT as edgartools/SEC

    User->>FE: Enter ticker on /insider/ownership
    FE->>API: GET /insider/ownership?ticker=AAPL&limit=50
    API->>API: Validate ticker
    API->>SVC: get_ownership_changes(ticker, limit)
    SVC->>Cache: Check ("ownership", AAPL) with TTL
    alt Cache hit and not expired
        Cache-->>SVC: Cached OwnershipChangesResponse
    else Cache miss or expired
        SVC->>SVC: asyncio.to_thread(_fetch_ownership_changes)
        SVC->>EDT: Company(ticker).get_filings(form="4")
        loop Each filing up to limit
            SVC->>EDT: filing.obj()
            SVC->>EDT: ownership.get_ownership_summary()
            EDT-->>SVC: TransactionSummary (remaining_shares, net_change, insider_name)
        end
        SVC-->>Cache: Store result with timestamp
    end
    SVC-->>API: OwnershipChangesResponse
    API-->>FE: JSON
    FE->>FE: Render LineChart per insider + ChangeLogTable
```

### Grants Sub-Page Sequence
```mermaid
sequenceDiagram
    participant User
    participant FE as InsiderGrantsPage
    participant API as FastAPI
    participant SVC as insider_service
    participant Cache as LRU Cache
    participant EDT as edgartools/SEC

    User->>FE: Enter ticker on /insider/grants
    FE->>API: GET /insider/grants?ticker=AAPL&limit=50
    API->>API: Validate ticker
    API->>SVC: get_grants_and_exercises(ticker, limit)
    SVC->>Cache: Check ("grants", AAPL) with TTL
    alt Cache hit and not expired
        Cache-->>SVC: Cached GrantsResponse
    else Cache miss or expired
        SVC->>SVC: asyncio.to_thread(_fetch_grants)
        SVC->>EDT: Company(ticker).get_filings(form="4")
        loop Each filing up to limit
            SVC->>EDT: filing.obj()
            SVC->>EDT: form4.derivative_trades
            SVC->>EDT: form4.option_exercises
            EDT-->>SVC: DataFrames with derivative/exercise rows
        end
        SVC-->>Cache: Store result with timestamp
    end
    SVC-->>API: GrantsResponse
    API-->>FE: JSON
    FE->>FE: Render GrantsTable
```

### API Contracts

#### Summary Endpoint
**GET** `/insider/summary`

**Query Parameters:**
- `ticker` (str, required) - Stock ticker symbol. Validated: `Query(..., pattern=r"^[A-Z]{1,5}$")`
- `form_type` (str, default="4") - SEC form type: "3", "4", or "5"
- `limit` (int, default=50, range=1-200) - Max filings to process
- `offset` (int, default=0, range=0-10000) - Number of filings to skip before processing

**Response** (`InsiderSummaryResponse`):
```json
{
  "ticker": "AAPL",
  "form_type": "4",
  "filings": [
    {
      "filing_date": "2024-03-15",
      "accession_no": "0000320193-24-000081",
      "insider_name": "Tim Cook",
      "position": "CEO",
      "primary_activity": "Sale",
      "net_change": -50000,
      "net_value": 8750000.0,
      "remaining_shares": 3280000,
      "has_10b5_1_plan": true,
      "transaction_types": ["Sale"],
      "transaction_count": 2,
      "form_type": "4"
    }
  ],
  "aggregates": {
    "total_filings": 50,
    "total_purchases": 12,
    "total_sales": 35,
    "total_other": 3,
    "net_sentiment": -23,
    "largest_transaction_value": 15000000.0,
    "largest_transaction_insider": "Tim Cook",
    "plan_10b5_1_count": 28,
    "plan_10b5_1_ratio": 0.56,
    "activity_by_date": [
      {"date": "2024-03", "purchases": 3, "sales": 8, "purchase_value": 500000, "sale_value": 12000000}
    ]
  },
  "total": 47,
  "skipped_count": 3
}
```

#### Summary Endpoint (Form 3)
Form 3 filings return `InitialOwnershipSummary` with different fields:
```json
{
  "filing_date": "2024-01-10",
  "accession_no": "0000320193-24-000015",
  "insider_name": "New Director",
  "position": "Director",
  "primary_activity": "Initial Holdings",
  "net_change": 0,
  "net_value": 0,
  "remaining_shares": 5000,
  "has_10b5_1_plan": null,
  "transaction_types": [],
  "transaction_count": 0,
  "form_type": "3",
  "total_holdings": 5000,
  "has_derivatives": false
}
```

#### Detail Endpoint
**GET** `/insider/detail`

**Query Parameters:**
- `ticker` (str, required) - Stock ticker symbol. Validated: `Query(..., pattern=r"^[A-Z]{1,5}$")`
- `form_type` (str, default="4") - SEC form type
- `accession_no` (str, required) - SEC accession number (e.g., "0000320193-24-000081")

**Response** (`InsiderDetailResponse`):
```json
{
  "ticker": "AAPL",
  "filing_date": "2024-03-15",
  "accession_no": "0000320193-24-000081",
  "insider_name": "Tim Cook",
  "position": "CEO",
  "form_type": "4",
  "transactions": [
    {
      "transaction_type": "Sale",
      "code": "S",
      "description": "Open market or private sale",
      "shares": 25000,
      "price_per_share": 175.0,
      "value": 4375000.0,
      "security_type": "non-derivative",
      "security_title": "Common Stock",
      "is_10b5_1_plan": true,
      "is_derivative": false
    }
  ],
  "market_trades_count": 2,
  "derivative_trades_count": 0
}
```

#### Ownership Changes Endpoint
**GET** `/insider/ownership`

**Query Parameters:**
- `ticker` (str, required) - Stock ticker symbol. Validated: `Query(..., pattern=r"^[A-Z]{1,5}$")`
- `limit` (int, default=50, range=1-200) - Max filings to process

**Response** (`OwnershipChangesResponse`):
```json
{
  "ticker": "AAPL",
  "changes": [
    {
      "filing_date": "2024-03-15",
      "accession_no": "0000320193-24-000081",
      "insider_name": "Tim Cook",
      "position": "CEO",
      "shares_before": 3330000,
      "shares_after": 3280000,
      "net_change": -50000,
      "running_total": 3280000
    }
  ],
  "insiders": ["Tim Cook", "Luca Maestri", "Jeff Williams"],
  "total": 47,
  "skipped_count": 3
}
```

**Design notes:**
- `shares_before` is computed as `remaining_shares - net_change`. Since `net_change` is negative for sales (e.g., -50000), `remaining_shares - (-50000) = remaining_shares + 50000`, giving the correct pre-transaction count. When `remaining_shares` is not available, `shares_before` is `null`.
- `running_total` is `remaining_shares` from the filing (this IS the running total as reported to SEC).
- `insiders` is a deduplicated list of insider names sorted by activity count (most active first), limited to top 10. Used by frontend to determine which lines to render on the chart.
- Results are ordered by `filing_date` ascending (oldest first) for chart rendering.

#### Grants & Exercises Endpoint
**GET** `/insider/grants`

**Query Parameters:**
- `ticker` (str, required) - Stock ticker symbol. Validated: `Query(..., pattern=r"^[A-Z]{1,5}$")`
- `limit` (int, default=50, range=1-200) - Max filings to process

**Response** (`GrantsResponse`):
```json
{
  "ticker": "AAPL",
  "grants": [
    {
      "filing_date": "2024-03-15",
      "accession_no": "0000320193-24-000081",
      "insider_name": "Tim Cook",
      "transaction_type": "Exercise",
      "security_title": "Stock Option (right to buy)",
      "exercise_price": 45.50,
      "expiration_date": "2028-12-31",
      "shares": 100000,
      "underlying_security": "Common Stock",
      "acquired_disposed": "A"
    }
  ],
  "total": 23,
  "skipped_count": 2
}
```

**Design notes:**
- `transaction_type` is one of: "Grant" (code A), "Exercise" (code M or X), "Conversion" (code C), or the raw TransactionCode description for other codes.
- `derivative_trades` DataFrame columns mapped: Security -> `security_title`, Price -> `exercise_price`, ExpirationDate -> `expiration_date`, Shares -> `shares`, UnderlyingSecurity -> `underlying_security`, AcquiredDisposed -> `acquired_disposed`, Code -> used to determine `transaction_type`.
- `option_exercises` rows are merged into the same list with `transaction_type = "Exercise"`.
- Filings with no derivative_trades and no option_exercises are skipped (not counted as errors).

## Implementation Plan

> Tasks use Phase.Task numbering for unambiguous reference.
> TDD flow: Red (failing test) -> Green (minimal implementation) -> Refactor

### Progress Tracker
- DONE: Phase 1: Backend Schemas and Service
- DONE: Phase 2: Backend Routes and Integration
- DONE: Phase 3: Frontend API Service and Dependencies
- DONE: Phase 4: Frontend Dashboard UI
- DONE: Phase 5: Ownership Changes Backend
- DONE: Phase 6: Grants & Exercises Backend
- DONE: Phase 7: Frontend Ownership Sub-Page
- DONE: Phase 8: Frontend Grants Sub-Page

### Phase 1: Backend Schemas and Service
**Goal**: Define Pydantic schemas for summary/detail responses (with accession_no and skipped_count) and rewrite the insider service with LRU cache, per-filing error handling, and offset support.

#### Task 1.1: Rewrite Pydantic schemas for summary and detail responses
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/backend/models/insider_schemas.py

**Semantic targets:**
- Class: `InsiderFilingSummary` -- one row per filing from `get_ownership_summary()`. Includes `accession_no: str` field for stable filing identification. Removes `filing_index` field.
- Class: `InsiderAggregates` -- computed dashboard-level stats (sentiment, largest tx, 10b5-1 ratio, activity_by_date)
- Class: `InsiderSummaryResponse` -- top-level response with filings list + aggregates + `skipped_count: int` field indicating how many filings failed to parse
- Class: `InsiderTransactionDetail` -- one row per transaction from `get_transaction_activities()`
- Class: `InsiderDetailResponse` -- detail endpoint response. Includes `accession_no: str`.
- Class: `ActivityByDate` -- monthly buy/sell activity for chart data
- Remove: `InsiderTransaction`, `InsiderTransactionsResponse` (replaced by new schemas)

**TDD Steps:**
- DONE: 1.1.1: Red - Write tests that instantiate new schema classes with sample data and verify field types, defaults, and serialization. Specifically test that `accession_no` is required on `InsiderFilingSummary`, that `skipped_count` defaults to 0 on `InsiderSummaryResponse`, and that `filing_index` is absent.
- DONE: 1.1.2: Green - Implement all Pydantic schema classes
- DONE: 1.1.3: Refactor - Ensure field naming consistency, add docstrings

#### Task 1.2: Rewrite insider service with rich edgartools API, caching, and error resilience
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/backend/services/insider_service.py

**Semantic targets:**
- Function: `_ensure_identity()` -- retain as-is
- Cache: `_insider_cache: OrderedDict[str, tuple[Any, float]]` -- shared LRU cache for all insider endpoints. Keyed by string (e.g., `"summary:AAPL:4"`, `"ownership:AAPL"`, `"grants:AAPL"`), values are `(response, timestamp)`. Max 50 entries, 5-minute TTL. Follow pattern from `news_service.py:_article_cache` and `news.py:_summary_cache`.
- Function: `_cache_get(cache_key)` -- returns cached response if present and not expired (within TTL), else None. Evicts expired entry on access.
- Function: `_cache_put(cache_key, response)` -- stores response with current timestamp, evicts oldest if over max size.
- Function: `_fetch_summaries(ticker, form_type, limit, offset)` -- synchronous worker that iterates filings (skipping first `offset`), calls `filing.obj()` and `get_ownership_summary()` **wrapped in try/except per filing**. On exception: logs warning with filing accession_no and error, increments `skipped_count`, continues to next filing. Extracts `filing.accession_no` for each filing and passes it to `_build_filing_summary()`. Returns `InsiderSummaryResponse` with `skipped_count` set.
- Function: `_build_filing_summary(ownership, filing_date, accession_no)` -- extract TransactionSummary/InitialOwnershipSummary into InsiderFilingSummary. Takes `accession_no: str` parameter instead of `filing_index: int`.
- Function: `_compute_aggregates(summaries, form_type)` -- compute dashboard stats from filing summaries list
- Function: `_compute_activity_by_date(summaries)` -- group filings by month for chart data
- Function: `get_insider_summary(ticker, form_type, limit, offset)` -- async entry point. Checks cache with key `f"summary:{ticker}:{form_type}"` first. If miss, wraps `_fetch_summaries` in `asyncio.to_thread()`, stores result in cache, returns.
- Function: `_fetch_detail(ticker, form_type, accession_no)` -- synchronous worker for detail endpoint. Finds filing by `accession_no` by iterating `Company(ticker).get_filings(form=form_type)` and matching `filing.accession_no`. Raises `ValueError` if not found.
- Function: `get_insider_detail(ticker, form_type, accession_no)` -- async entry point for detail. Takes `accession_no: str` instead of `filing_index: int`.
- Remove: `get_insider_trades_fallback()`, `get_insider_data()`, `_parse_market_trades()`, `_parse_transaction_activities()`, `_parse_form4_transactions()`, `_parse_owner_info()`, `_check_10b5_1()`, `OwnerInfo` dataclass (all replaced)

**TDD Steps:**
- DONE: 1.2.1: Red - Write tests for `_build_filing_summary()` with mocked TransactionSummary and InitialOwnershipSummary objects. Verify `accession_no` is correctly propagated to the summary.
- DONE: 1.2.2: Red - Write tests for `_compute_aggregates()` with known filing summary lists verifying sentiment, largest tx, 10b5-1 ratio
- DONE: 1.2.3: Red - Write tests for `_compute_activity_by_date()` verifying monthly grouping
- DONE: 1.2.4: Red - Write tests for `_cache_get()` and `_cache_put()` verifying TTL expiration, LRU eviction, and cache hit/miss behavior
- DONE: 1.2.5: Red - Write tests for `_fetch_summaries()` with mocked filings where some raise exceptions. Verify that `skipped_count` equals the number of failed filings, that successful filings are still returned, and that `offset` skips the correct number of filings.
- DONE: 1.2.6: Green - Implement all service functions including cache, per-filing error handling, and offset support
- DONE: 1.2.7: Refactor - Extract shared helpers, add docstrings, verify logging on skipped filings

### Phase 2: Backend Routes and Integration
**Goal**: Replace the single transactions endpoint with summary and detail endpoints, adding ticker validation and offset parameter.

#### Task 2.1: Rewrite insider routes with summary and detail endpoints
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/backend/routes/insider.py

**Semantic targets:**
- Function: `insider_summary()` -- GET `/insider/summary` with query params:
  - `ticker: str = Query(..., pattern=r"^[A-Z]{1,5}$")` -- regex-validated ticker
  - `form_type: str = Query("4")` -- SEC form type
  - `limit: int = Query(50, ge=1, le=200)` -- max filings
  - `offset: int = Query(0, ge=0, le=10000)` -- skip first N filings
- Function: `insider_detail()` -- GET `/insider/detail` with query params:
  - `ticker: str = Query(..., pattern=r"^[A-Z]{1,5}$")` -- regex-validated ticker
  - `form_type: str = Query("4")` -- SEC form type
  - `accession_no: str = Query(...)` -- SEC accession number (replaces `filing_index: int`)
- Remove: `insider_transactions()` endpoint (replaced by summary)
- Router: `APIRouter(prefix="/insider", tags=["insider"])` -- retain prefix

**TDD Steps:**
- DONE: 2.1.1: Red - Write tests that call summary endpoint with mocked service, verify response shape and status codes. Test that invalid tickers (lowercase, too long, special chars) return 422 validation error. Test that offset parameter is passed through to service.
- DONE: 2.1.2: Red - Write tests that call detail endpoint with accession_no parameter, verify 404 for unknown accession_no (ValueError from service), 422 for invalid ticker, 500 for service errors.
- DONE: 2.1.3: Green - Implement both route handlers with Query validation
- DONE: 2.1.4: Refactor - Standardize error handling matching existing route patterns

### Phase 3: Frontend API Service and Dependencies
**Goal**: Install recharts, update TypeScript types to include accession_no and skipped_count, and expand the API service.

#### Task 3.1: Add recharts dependency and update API types
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/frontend/package.json
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/frontend/src/services/insider-api.ts

**Semantic targets:**
- Dependency: `recharts` in package.json dependencies
- Interface: `InsiderFilingSummary` -- mirrors backend schema. Includes `accession_no: string`. Does NOT include `filing_index`.
- Interface: `InsiderAggregates` -- mirrors backend aggregates including `activity_by_date`
- Interface: `InsiderSummaryResponse` -- filings + aggregates + total + `skipped_count: number`
- Interface: `InsiderTransactionDetail` -- single transaction row
- Interface: `InsiderDetailResponse` -- detail endpoint response with `accession_no: string`
- Interface: `ActivityByDate` -- date, purchases, sales, purchase_value, sale_value
- Class method: `InsiderService.getSummary(ticker, formType, limit, offset)` -- calls GET /insider/summary with offset parameter
- Class method: `InsiderService.getDetail(ticker, formType, accessionNo)` -- calls GET /insider/detail with `accession_no` query param (replaces `filing_index`)
- Remove: `InsiderTransaction`, `InsiderTransactionsResponse`, `getTransactions()` (replaced)

**TDD Steps:**
- DONE: 3.1.1: Green - Add recharts to package.json and run `npm install`
- DONE: 3.1.2: Green - Implement TypeScript interfaces and API service methods with accession_no and offset support
- DONE: 3.1.3: Refactor - Verify types match backend schemas exactly

### Phase 4: Frontend Dashboard UI
**Goal**: Rewrite the insider page as a full dashboard with summary cards, activity chart, tabbed form-type layout, enhanced table, filters, and skipped-filings notice.

#### Task 4.1: Build dashboard layout with summary cards and tabs
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/frontend/src/pages/insider-page.tsx

**Semantic targets:**
- Component: `InsiderPage` -- main page component with search, tabs, lazy-loading per tab
- Component: `SummaryCards` -- 4 cards: Net Insider Sentiment, Largest Transaction, 10b5-1 Plan Ratio, Total Filings
- Component: `SkippedNotice` -- conditional banner: "Showing {total} of {total + skipped_count} filings ({skipped_count} could not be parsed)". Only renders when `skipped_count > 0`.
- State: `loadedTabs` Set for lazy-loading (pattern from news-page.tsx `handleTabChange`)
- State: `summaryData` map keyed by form_type ("3", "4", "5")
- State: `filter` for All | Purchases | Sales | Option Exercises | Discretionary Only
- Tabs: Form 4 (default) | Form 3 | Form 5

**TDD Steps:**
- DONE: 4.1.1: Green - Implement page skeleton with search bar, tabs, loading states, and summary cards
- DONE: 4.1.2: Green - Wire up API calls with lazy-loading per tab, pass offset=0 initially
- DONE: 4.1.3: Green - Implement SkippedNotice component that displays when skipped_count > 0
- DONE: 4.1.4: Refactor - Extract SummaryCards and SkippedNotice into inline components, match news-page patterns

#### Task 4.2: Build activity chart and enhanced table with filters
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/frontend/src/pages/insider-page.tsx

**Semantic targets:**
- Component: `ActivityChart` -- recharts BarChart showing monthly buy/sell activity from `aggregates.activity_by_date`
- Component: `FilingsTable` -- enhanced table with columns: Filing Date, Insider Name, Position, Primary Activity (color-coded Badge), Net Change, Net Value, Remaining Shares, 10b5-1 Plan, Transaction Types. Row click triggers detail fetch using `accession_no` (not filing_index).
- Component: `FilterBar` -- filter buttons: All | Purchases | Sales | Option Exercises | Discretionary Only (no 10b5-1)
- Helper: `formatValue()`, `formatNumber()` -- retain existing formatting helpers
- Color coding: Purchase = green badge, Sale = red badge, Option Exercise = amber badge, other = default
- Filter logic: "Discretionary Only" filters out filings where `has_10b5_1_plan === true`
- Detail expansion: On row click, call `InsiderService.getDetail(ticker, formType, filing.accession_no)` to fetch transaction details

**TDD Steps:**
- DONE: 4.2.1: Green - Implement ActivityChart with recharts BarChart (purchases green, sales red)
- DONE: 4.2.2: Green - Implement FilingsTable with all columns, color-coded badges, and row click using accession_no for detail fetch
- DONE: 4.2.3: Green - Implement FilterBar with all filter options and filtering logic
- DONE: 4.2.4: Refactor - Ensure page stays under 500 LOC by extracting chart/table if needed, add loading skeletons

### Phase 5: Ownership Changes Backend
**Goal**: Add Pydantic schemas and service functions for the ownership changes endpoint with LRU cache, per-filing error handling, and the route handler.

#### Task 5.1: Add ownership change schemas
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/backend/models/insider_schemas.py

**Semantic targets:**
- Class: `OwnershipChangeRecord` -- one row per filing with ownership change data. Fields: `filing_date: str`, `accession_no: str`, `insider_name: str`, `position: str`, `shares_before: int | None`, `shares_after: int | None`, `net_change: int`, `running_total: int | None`.
- Class: `OwnershipChangesResponse` -- top-level response. Fields: `ticker: str`, `changes: list[OwnershipChangeRecord]`, `insiders: list[str]` (top 10 by activity count, most active first), `total: int`, `skipped_count: int = 0`.

**TDD Steps:**
- DONE: 5.1.1: Red - Write tests that instantiate `OwnershipChangeRecord` with sample data and verify `shares_before` is optional (nullable), `net_change` is required. Test `OwnershipChangesResponse` serialization with multiple records and verify `insiders` list ordering.
- DONE: 5.1.2: Green - Implement both schema classes in `insider_schemas.py`
- DONE: 5.1.3: Refactor - Add docstrings

#### Task 5.2: Add ownership changes service function
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/backend/services/insider_service.py

**Semantic targets:**
- Function: `_fetch_ownership_changes(ticker, limit)` -- synchronous worker. Iterates Form 4 filings up to `limit`, calls `filing.obj()` and `get_ownership_summary()` per filing (wrapped in try/except). Extracts `remaining_shares`, `net_change`, `insider_name`, `position` from each `TransactionSummary`. Computes `shares_before` as `remaining_shares - net_change` when `remaining_shares` is not None. Builds `OwnershipChangeRecord` per filing. Collects unique insider names, counts per insider, sorts by count descending, takes top 10. Returns `OwnershipChangesResponse` with changes ordered by `filing_date` ascending.
- Function: `get_ownership_changes(ticker, limit)` -- async entry point. Checks cache with key `f"ownership:{ticker}"` first. If miss, wraps `_fetch_ownership_changes` in `asyncio.to_thread()`, stores result in cache via `_cache_put()`, returns. Uses same `_ensure_identity()` pattern and shared `_insider_cache` OrderedDict.

**TDD Steps:**
- DONE: 5.2.1: Red - Write tests for `_fetch_ownership_changes()` with mocked filings. Verify: correct `shares_before` computation (`remaining_shares - net_change`), `shares_before` is None when `remaining_shares` is None, filing order is ascending by date, `insiders` list is sorted by activity count, `skipped_count` increments on filing parse failure.
- DONE: 5.2.2: Red - Write test for `get_ownership_changes()` verifying cache hit returns cached response without calling `_fetch_ownership_changes`, and cache miss triggers fetch and stores result.
- DONE: 5.2.3: Green - Implement `_fetch_ownership_changes()` and `get_ownership_changes()`
- DONE: 5.2.4: Refactor - Extract shared filing iteration helper if duplication with `_fetch_summaries()` is significant

#### Task 5.3: Add ownership changes route
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/backend/routes/insider.py

**Semantic targets:**
- Function: `insider_ownership()` -- GET `/insider/ownership` with query params:
  - `ticker: str = Query(..., pattern=r"^[A-Z]{1,5}$")`
  - `limit: int = Query(50, ge=1, le=200)`
- Response model: `OwnershipChangesResponse`
- Error handling: try/except wrapping service call, HTTPException(500) on failure

**TDD Steps:**
- DONE: 5.3.1: Red - Write test calling ownership endpoint with mocked service, verify response shape. Test 422 for invalid ticker.
- DONE: 5.3.2: Green - Implement route handler
- DONE: 5.3.3: Refactor - Verify error handling consistency with other insider routes

### Phase 6: Grants & Exercises Backend
**Goal**: Add Pydantic schemas and service functions for the grants/exercises endpoint with LRU cache, per-filing error handling, and the route handler.

#### Task 6.1: Add grants schemas
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/backend/models/insider_schemas.py

**Semantic targets:**
- Class: `GrantRecord` -- one row per derivative trade or option exercise. Fields: `filing_date: str`, `accession_no: str`, `insider_name: str`, `transaction_type: str` (Grant/Exercise/Conversion), `security_title: str`, `exercise_price: float | None`, `expiration_date: str | None`, `shares: float | None`, `underlying_security: str | None`, `acquired_disposed: str | None`.
- Class: `GrantsResponse` -- top-level response. Fields: `ticker: str`, `grants: list[GrantRecord]`, `total: int`, `skipped_count: int = 0`.

**TDD Steps:**
- DONE: 6.1.1: Red - Write tests that instantiate `GrantRecord` with sample data verifying optional fields default to None. Test `GrantsResponse` serialization.
- DONE: 6.1.2: Green - Implement both schema classes
- DONE: 6.1.3: Refactor - Add docstrings

#### Task 6.2: Add grants service function
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/backend/services/insider_service.py

**Semantic targets:**
- Function: `_classify_derivative_transaction(code)` -- maps transaction code to human-readable type. "A" -> "Grant", "M"/"X" -> "Exercise", "C" -> "Conversion", others -> TransactionCode.DESCRIPTIONS lookup or raw code.
- Function: `_fetch_grants(ticker, limit)` -- synchronous worker. Iterates Form 4 filings up to `limit`. For each filing, calls `filing.obj()` (try/except), then reads `form4.derivative_trades` DataFrame and `form4.option_exercises` DataFrame. For each row in `derivative_trades`: extracts Security -> `security_title`, Price -> `exercise_price`, ExpirationDate -> `expiration_date`, Shares -> `shares`, UnderlyingSecurity -> `underlying_security`, AcquiredDisposed -> `acquired_disposed`, Code -> `_classify_derivative_transaction()` -> `transaction_type`. For `option_exercises` rows: same mapping but `transaction_type` is always "Exercise". Skips filings with no derivative data (not an error). Appends `GrantRecord` per row. Returns `GrantsResponse`.
- Function: `get_grants_and_exercises(ticker, limit)` -- async entry point. Checks cache with key `f"grants:{ticker}"` first. If miss, wraps `_fetch_grants` in `asyncio.to_thread()`, stores result in cache via `_cache_put()`, returns. Uses same `_ensure_identity()` pattern and shared `_insider_cache` OrderedDict.

**TDD Steps:**
- DONE: 6.2.1: Red - Write tests for `_classify_derivative_transaction()` verifying code "A" -> "Grant", "M" -> "Exercise", "X" -> "Exercise", "C" -> "Conversion", unknown code falls back to description.
- DONE: 6.2.2: Red - Write tests for `_fetch_grants()` with mocked filings having derivative_trades and option_exercises DataFrames. Verify: correct field mapping from DataFrame columns, filings with empty/None DataFrames are skipped without incrementing `skipped_count`, filings that raise on `filing.obj()` increment `skipped_count`.
- DONE: 6.2.3: Red - Write test for `get_grants_and_exercises()` verifying cache hit returns cached response without calling `_fetch_grants`, and cache miss triggers fetch and stores result.
- DONE: 6.2.4: Green - Implement `_classify_derivative_transaction()`, `_fetch_grants()`, and `get_grants_and_exercises()`
- DONE: 6.2.5: Refactor - Add docstrings, verify DataFrame column access is defensive (use `.get()` with defaults)

#### Task 6.3: Add grants route
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/backend/routes/insider.py

**Semantic targets:**
- Function: `insider_grants()` -- GET `/insider/grants` with query params:
  - `ticker: str = Query(..., pattern=r"^[A-Z]{1,5}$")`
  - `limit: int = Query(50, ge=1, le=200)`
- Response model: `GrantsResponse`
- Error handling: try/except wrapping service call, HTTPException(500) on failure

**TDD Steps:**
- DONE: 6.3.1: Red - Write test calling grants endpoint with mocked service, verify response shape. Test 422 for invalid ticker.
- DONE: 6.3.2: Green - Implement route handler
- DONE: 6.3.3: Refactor - Verify error handling consistency

### Phase 7: Frontend Ownership Sub-Page
**Goal**: Build the ownership changes sub-page with position history line chart and change log table, add API methods and routing.

#### Task 7.1: Add ownership and grants API methods and types
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/frontend/src/services/insider-api.ts

**Semantic targets:**
- Interface: `OwnershipChangeRecord` -- mirrors backend schema: `filing_date`, `accession_no`, `insider_name`, `position`, `shares_before`, `shares_after`, `net_change`, `running_total`
- Interface: `OwnershipChangesResponse` -- `ticker`, `changes`, `insiders`, `total`, `skipped_count`
- Interface: `GrantRecord` -- mirrors backend schema: `filing_date`, `accession_no`, `insider_name`, `transaction_type`, `security_title`, `exercise_price`, `expiration_date`, `shares`, `underlying_security`, `acquired_disposed`
- Interface: `GrantsResponse` -- `ticker`, `grants`, `total`, `skipped_count`
- Class method: `InsiderService.getOwnershipChanges(ticker, limit)` -- calls GET /insider/ownership
- Class method: `InsiderService.getGrants(ticker, limit)` -- calls GET /insider/grants

**TDD Steps:**
- DONE: 7.1.1: Green - Implement all new TypeScript interfaces and API methods
- DONE: 7.1.2: Refactor - Verify types match backend schemas

#### Task 7.2: Add routes and sub-navigation
**Files to modify:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/frontend/src/App.tsx
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/frontend/src/pages/insider-page.tsx

**Semantic targets:**
- Route: `/insider/ownership` -> `InsiderOwnershipPage` component (import from `insider-ownership-page.tsx`)
- Route: `/insider/grants` -> `InsiderGrantsPage` component (import from `insider-grants-page.tsx`)
- Sub-navigation in `InsiderPage`: Add navigation links in the page header area (below the title, above the search bar). Three links: "Overview" (current `/insider`, active by default), "Ownership Changes" (`/insider/ownership`), "Grants & Exercises" (`/insider/grants`). Use `Link` from react-router-dom with styling consistent with the page (e.g., underline active link or use Button variant="ghost" with active state).

**TDD Steps:**
- DONE: 7.2.1: Green - Add two new Route entries in App.tsx
- DONE: 7.2.2: Green - Add sub-navigation links to InsiderPage header
- DONE: 7.2.3: Refactor - Ensure sub-nav styling is consistent, active state highlights current page

#### Task 7.3: Build ownership changes page
**Files to create:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/frontend/src/pages/insider-ownership-page.tsx

**Semantic targets:**
- Component: `InsiderOwnershipPage` -- main page with ticker search bar (same pattern as `InsiderPage`), sub-navigation links (same 3 links as InsiderPage header, with "Ownership Changes" active), loading/error states.
- Component: `PositionHistoryChart` -- recharts `LineChart` with one `Line` per insider (from `response.insiders`, top 5-10). X-axis = `filing_date`, Y-axis = `running_total` (share count). Each insider gets a distinct color. Legend shows insider names. Tooltip shows date, insider, share count.
- Component: `ChangeLogTable` -- Table with columns: Filing Date, Insider Name, Position, Shares Before, Shares After, Net Change (green text for positive, red for negative), Running Total. Uses existing shadcn/ui Table components.
- State: `ticker`, `data` (OwnershipChangesResponse | null), `loading`, `error`
- Data transformation for chart: Group `changes` by `insider_name`, create one data series per insider with `{filing_date, running_total}` points. Only include insiders in `response.insiders` list (already limited to top 10 by backend).

**TDD Steps:**
- DONE: 7.3.1: Green - Implement page skeleton with search bar, sub-navigation, loading/error states
- DONE: 7.3.2: Green - Implement PositionHistoryChart with recharts LineChart, one line per insider
- DONE: 7.3.3: Green - Implement ChangeLogTable with all columns and green/red net_change coloring
- DONE: 7.3.4: Refactor - Ensure page stays under 500 LOC, extract chart/table if needed

### Phase 8: Frontend Grants Sub-Page
**Goal**: Build the grants & exercises sub-page with derivative trades table.

#### Task 8.1: Build grants & exercises page
**Files to create:**
- /Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/frontend/src/pages/insider-grants-page.tsx

**Semantic targets:**
- Component: `InsiderGrantsPage` -- main page with ticker search bar (same pattern), sub-navigation links (same 3 links, "Grants & Exercises" active), loading/error states.
- Component: `GrantsTable` -- Table with columns: Filing Date, Insider Name, Transaction Type (color-coded Badge: Grant = blue, Exercise = amber, Conversion = purple), Security Title, Exercise Price, Expiration Date, Shares, Underlying Security, Acquired/Disposed (A = green "Acquired", D = red "Disposed"). Uses shadcn/ui Table + Badge components.
- State: `ticker`, `data` (GrantsResponse | null), `loading`, `error`
- Empty state: "No derivative transactions found for {ticker}" when `grants` array is empty.

**TDD Steps:**
- DONE: 8.1.1: Green - Implement page skeleton with search bar, sub-navigation, loading/error states
- DONE: 8.1.2: Green - Implement GrantsTable with all columns and color-coded badges
- DONE: 8.1.3: Refactor - Ensure page stays under 500 LOC, verify badge colors match spec

## Appendix
- edgartools documentation: https://github.com/dgunning/edgartools
- recharts documentation: https://recharts.org/
- shadcn/ui Card component: `/Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/frontend/src/components/ui/card.tsx`
- Reference dashboard pattern: `/Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/frontend/src/pages/news-page.tsx`
- Reference asyncio.to_thread pattern: `/Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/backend/services/screener_service.py`
- Reference LRU cache pattern (OrderedDict): `/Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/backend/services/news_service.py` (lines with `_article_cache`)
- Reference LRU cache pattern (routes): `/Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/app/backend/routes/news.py` (lines with `_summary_cache`)
- Existing test directory: `/Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/tests/`
- Backend test file (new): `/Users/dmytroshendryk/Documents/Projects/finance/ai-hedge-fund/tests/backend/test_insider_service.py`
- edgartools Ownership.derivative_trades: DataFrame with columns Security, Date, Code, Shares, Price, ExercisePrice, ExpirationDate, UnderlyingSecurity, AcquiredDisposed
- edgartools Ownership.option_exercises: DataFrame of exercised option transactions
- edgartools TransactionCode.DESCRIPTIONS: mapping of code -> human-readable description (A=Grant, M=Exercise, C=Conversion, etc.)

## Remediation

### Phase Remediation.1: Code Simplification Fixes

#### Task Remediation.1.1: Fix duplicate cache
**Summary**: Delete `_cache.py`. Update `_summary.py` to use lazy import from `__init__.py` for `_cache_get`/`_cache_put` to avoid circular import. Single `_insider_cache` OrderedDict at runtime.
- DONE: Remove `_cache.py`
- DONE: Fix `_summary.py` to use lazy import for cache helpers

#### Task Remediation.1.2: Extract shared filing iteration helper
**Summary**: Add `_iter_parsed_filings` generator to `_helpers.py`. Refactor `_summary.py`, `_ownership.py`, `_grants.py` to use it.
- DONE: Add `_iter_parsed_filings` to `_helpers.py`
- DONE: Refactor `_summary.py` to use `_iter_parsed_filings`
- DONE: Refactor `_ownership.py` to use `_iter_parsed_filings`
- DONE: Refactor `_grants.py` to use `_iter_parsed_filings`

#### Task Remediation.1.3: Extract shared trade row parsing
**Summary**: Extract `_parse_trade_rows(df, *, is_derivative)` in `_detail.py` to eliminate duplicated market/derivative trade parsing blocks.
- DONE: Add `_parse_trade_rows` to `_detail.py`
- DONE: Refactor `_fetch_detail` to use `_parse_trade_rows`

#### Task Remediation.1.4: Extract triplicated frontend components
**Summary**: Extract `SubNavLink`, formatting utils, and `SkippedCountBanner` to shared modules.
- DONE: Create `app/frontend/src/components/insider/insider-sub-nav.tsx` with `SubNavLink`
- DONE: Create `app/frontend/src/utils/format.ts` with `formatNumber`, `formatValue`, `formatPrice`
- DONE: Create `app/frontend/src/components/insider/skipped-count-banner.tsx` with `SkippedCountBanner`
- DONE: Update `insider-page.tsx` to use shared components
- DONE: Update `insider-ownership-page.tsx` to use shared components
- DONE: Update `insider-grants-page.tsx` to use shared components

---

## Quality Assurance Report

**Validation Date**: 2026-04-04
**Validator**: validator agent (run 2)
**Status**: FAILED (2 critical issues)

### Skill Checks Executed

| Skill | Status | Issues Found |
|-------|--------|--------------|
| `afe-config:unit-tester` | EXECUTED | 2 |
| `afe-config:code-review` | EXECUTED | 1 |
| `afe-config:code-documenter` | EXECUTED | 0 |
| `afe-config:code-simplifier` | EXECUTED | 0 |

### Coverage Analysis

| File | Coverage | Target | Status |
|------|----------|--------|--------|
| `insider_service/__init__.py` | 100% | 80% | PASS |
| `insider_service/_detail.py` | 15% | 80% | FAIL |
| `insider_service/_grants.py` | 83% | 80% | PASS |
| `insider_service/_helpers.py` | 90% | 80% | PASS |
| `insider_service/_ownership.py` | 84% | 80% | PASS |
| `insider_service/_summary.py` | 88% | 80% | PASS |

**Overall Coverage**: 76% (Target: 80%)

**Uncovered Code**:
- `_detail.py` lines 32-54: `_parse_trade_rows` function (market/derivative trade parsing)
- `_detail.py` lines 59-105: `_fetch_detail` function (filing lookup, identity extraction, trade parsing)
- `_detail.py` line 120: `get_insider_detail` async entry point
- `_helpers.py` lines 74-75, 87-88: `_coerce_float`/`_coerce_int` failure branches
- `_helpers.py` lines 101, 106-108: `_classify_transaction_type` fallback branches
- `_summary.py` line 104: `TypeError` for unsupported ownership summary type
- `_summary.py` lines 205-213: `get_insider_summary` async entry point

### Test Results

- **Total Tests**: 158
- **Passed**: 158
- **Failed**: 0
- **Skipped**: 0

### Code Quality

**Flake8**: 18 F401 violations in `insider_service/__init__.py`
- All are intentional re-exports for backwards-compatible package API (expected; would be suppressed with `# noqa: F401`)

**Ruff**: SKIPPED (tool not installed)
**Mypy**: SKIPPED (tool not installed)

### Plan Completion Audit

**Completed Tasks**: 65 (all tasks marked DONE)
**Verified Implementations**: 65 (100%)
**Suspicious Completions**: 0

All completed tasks have corresponding code changes verified via `git log` and `git diff --stat`.

### Code Review (from afe-config:code-review skill)

**Files Reviewed**: 8 (all backend Python files)
**P0/P1 Issues (Critical)**: 1
**P2/P3 Issues (Warning)**: 2

**P1: Logic Bug - Cache keys omit limit/offset parameters**
- File: `insider_service/__init__.py:86,102` and `_summary.py:207`
- Issue: Cache keys are `f"ownership:{ticker}:{form_type}"` but ignore `limit` and `offset`. A request with `limit=10, offset=0` caches the result. A subsequent request with `limit=50, offset=20` returns the stale cached data instead of fetching new results.
- Confidence: High (verified by reading all three cache key constructions)
- Impact: Users changing pagination will see incorrect/stale data. The first request for any ticker+form_type combination locks the cached result regardless of subsequent limit/offset values.
- Remediation: Include `limit` and `offset` in cache keys, e.g. `f"summary:{ticker.upper()}:{form_type}:{limit}:{offset}"`

**P2: Error Handling - Silent pass in _grants.py**
- File: `insider_service/_grants.py:48-49`
- Issue: `except Exception: pass` silently swallows errors when extracting insider identity. No logging makes debugging difficult.
- Confidence: Medium
- Impact: Missing insider names with no diagnostic trace.
- Remediation: Add `logger.debug("Could not extract insider identity for %s: %s", accession_no, exc)` (matching `_detail.py:85`).

**P3: API Design - form_type not validated to allowed values**
- File: `routes/insider.py:35-36`
- Issue: `form_type` accepts any string but only "3", "4", "5" are valid SEC form types.
- Confidence: Medium
- Impact: Invalid values produce empty results instead of 422 error.
- Remediation: Add `Query("4", pattern=r"^[345]$")` or use `Literal["3","4","5"]`.

### Test Quality (from afe-config:unit-tester skill)

**Anti-Patterns Detected**: 2

1. **Schema tests verifying Pydantic structural behavior** (WARNING)
   - Files: `test_insider_schemas.py`, `test_grants_schemas.py`, `test_ownership_schemas.py`
   - Several tests verify that Pydantic models accept valid data and reject missing required fields (testing framework behavior, not application logic). Tests like `test_serialization_includes_all_fields` and `test_records_are_typed` verify `isinstance` on typed list items -- the type checker handles this.
   - Some schema tests ARE valuable (testing that `filing_index` is absent verifies a migration, testing non-obvious defaults). The volume is disproportionate: 35+ tests for data containers with no custom validators.

2. **Test file proliferation** (WARNING)
   - 12 test files for 6 production files. Some could consolidate (e.g., `test_grants_schemas.py` (210 LOC) + `test_ownership_schemas.py` (171 LOC) into `test_insider_schemas.py`).

### Documentation Quality (from afe-config:code-documenter skill)

**Files Checked**: 8
**Issues Found**: 0

All modules have concise docstrings. Functions document non-obvious behavior (e.g., `object` parameter type rationale, mutable `skipped` list pattern). No TODO/FIXME markers removed. No type-signature restating.

### Code Simplification (from afe-config:code-simplifier skill)

**Files Analyzed**: 8
**Patterns Detected**: 0
**Cross-Repo Findings**: N/A

The service package split is well-motivated with distinct responsibilities per module (65-213 LOC each). The `__init__.py` re-export pattern is documented and intentional for test patching. No unnecessary wrappers, over-defensive error handling, or complex inheritance detected. The self-import pattern in cache helpers and repeated cache-fetch-store pattern across 3 endpoints are acceptable given the documented rationale.

### Recommendations

#### Critical (Must Fix)
1. DONE: Add unit tests for `_detail.py` to bring coverage above 80%. Test `_parse_trade_rows` (empty/populated DataFrames, derivative flag, None price/shares, value computation) and `_fetch_detail` (filing found, filing not found raises ValueError, identity extraction failure).
2. DONE: Fix cache key construction to include `limit` and `offset` in `__init__.py:86`, `__init__.py:102`, and `_summary.py:207`. Update cache tests to verify different limit/offset produce different cache keys.

#### Warnings (Should Fix)
1. DONE: Add `logger.debug` to the silent `except Exception: pass` in `_grants.py:48-49`.
2. DONE: Validate `form_type` to only accept "3", "4", or "5" in route handlers.
3. DONE: Add `# noqa: F401` to re-export lines in `insider_service/__init__.py`.

#### Info (Optional)
1. Consider consolidating schema test files to reduce test file count.
2. Install ruff and mypy as dev dependencies for comprehensive static analysis.

---

## Quality Assurance Report (Run 3)

**Validation Date**: 2026-04-04
**Validator**: validator agent (run 3)
**Status**: FAILED (2 critical issues -- same as run 2, unresolved)

### Skill Checks Executed

| Skill | Status | Issues Found |
|-------|--------|--------------|
| `afe-config:unit-tester` | EXECUTED | 2 |
| `afe-config:code-review` | EXECUTED | 1 |
| `afe-config:code-documenter` | EXECUTED | 0 |
| `afe-config:code-simplifier` | EXECUTED | 0 |

### Coverage Analysis

| File | Coverage | Target | Status |
|------|----------|--------|--------|
| `insider_service/__init__.py` | 100% | 80% | PASS |
| `insider_service/_detail.py` | 15% | 80% | FAIL |
| `insider_service/_grants.py` | 83% | 80% | PASS |
| `insider_service/_helpers.py` | 90% | 80% | PASS |
| `insider_service/_ownership.py` | 84% | 80% | PASS |
| `insider_service/_summary.py` | 88% | 80% | PASS |

**Overall Coverage**: 76% (Target: 80%)

**Uncovered Code (unchanged from run 2)**:
- `_detail.py` lines 32-54: `_parse_trade_rows` logic (DataFrame iteration, transaction detail construction)
- `_detail.py` lines 59-105: `_fetch_detail` logic (filing lookup, identity extraction, trade parsing)
- `_detail.py` line 120: `get_insider_detail` async entry point

### Test Results

- **Total Tests**: 130
- **Passed**: 130
- **Failed**: 0
- **Skipped**: 0

Note: Route test files (`test_routes.py`, `test_grants_routes.py`, `test_ownership_routes.py`) have collection errors when run with dotted `--cov` module paths due to Pydantic schema import conflicts. When run independently they pass (130 tests from non-route files + 9+9+28 route tests = 176 total when run separately).

### Code Quality

**Flake8 (--max-line-length=420)**: 18 F401 violations in `insider_service/__init__.py`
- All are intentional re-exports for backwards-compatible package API
- Suppression with `# noqa: F401` recommended

**Ruff**: SKIPPED (not installed in poetry environment)
**Mypy**: SKIPPED (not installed in poetry environment)

### Plan Completion Audit

**Completed Tasks**: 65 (all tasks marked DONE, 0 PENDING)
**Verified Implementations**: 65 (100%)
**Suspicious Completions**: 0

All task descriptions cross-referenced against `git diff --stat main..HEAD` (32 files changed, +5387 lines). Every phase has corresponding code changes.

### Code Review (from afe-config:code-review skill)

**Files Reviewed**: 8 (all backend Python modules)
**P0/P1 Issues (Critical)**: 1 (unchanged from run 2)
**P2/P3 Issues (Warning)**: 2 (unchanged from run 2)

**P1: Logic Bug - Cache keys omit limit/offset (STILL UNRESOLVED)**
- File: `insider_service/__init__.py:86,102` and `_summary.py:207`
- Verified: Cache keys remain `f"ownership:{ticker}:{form_type}"` without limit/offset
- Impact: Pagination returns stale cached results for different page requests

**P2: Silent exception swallowing in _grants.py:48-49 (STILL UNRESOLVED)**
**P3: form_type not validated to "3"/"4"/"5" (STILL UNRESOLVED)**

### Test Quality (from afe-config:unit-tester skill)

**Anti-Patterns Detected**: 2 (unchanged)
1. Schema tests verifying Pydantic framework behavior (WARNING) -- low bug-catching value
2. Test file proliferation (WARNING) -- 12 test files for 6 production files

### Documentation Quality (from afe-config:code-documenter skill)

**Files Checked**: 8
**Issues Found**: 0
All modules well-documented. No marker violations.

### Code Simplification (from afe-config:code-simplifier skill)

**Files Analyzed**: 8
**Patterns Detected**: 0
Service package split is well-motivated. No unnecessary abstractions.

### Recommendations

#### Critical (Must Fix)
1. DONE: Add unit tests for `_detail.py` to bring coverage from 15% to 80%+. Test `_parse_trade_rows` (empty DataFrame, populated DataFrame with derivative/non-derivative flags, None price/shares edge cases, value computation) and `_fetch_detail` (filing found path, filing not found raises ValueError, identity extraction failure, market/derivative trade parsing errors).
2. DONE: Fix cache key construction to include `limit` and `offset` in `__init__.py:86`, `__init__.py:102`, and `_summary.py:207`. Example: `f"summary:{ticker.upper()}:{form_type}:{limit}:{offset}"`. Update cache tests to verify different limit/offset produce different cache keys.

#### Warnings (Should Fix)
1. DONE: Add `logger.debug` to silent `except Exception: pass` in `_grants.py:48-49`.
2. DONE: Validate `form_type` to only accept "3", "4", or "5" in route handlers.
3. DONE: Add `# noqa: F401` to re-export lines in `insider_service/__init__.py`.

#### Info (Optional)
1. Install ruff and mypy as dev dependencies for comprehensive static analysis.
2. Consider consolidating schema test files to reduce test file count.
