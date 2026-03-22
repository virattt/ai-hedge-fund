# ARCHITECTURE.md — AI Hedge Fund

---

## 1. PROJECT STRUCTURE

```
ai-hedge-fund/
├── app/
│   ├── backend/                              # FastAPI server
│   │   ├── main.py                           # Application entry point
│   │   ├── alembic/                          # Database migrations
│   │   │   ├── env.py
│   │   │   └── versions/
│   │   │       ├── add_api_keys_table.py
│   │   │       ├── 1b1feba3d897_add_data_column_to_hedge_fund_flows.py
│   │   │       ├── 2f8c5d9e4b1a_add_hedgefundflowrun_table.py
│   │   │       ├── 3f9a6b7c8d2e_add_hedgefundflowruncycle_table.py
│   │   │       └── 5274886e5bee_add_hedgefundflow_table.py
│   │   ├── database/
│   │   │   ├── connection.py                 # SQLAlchemy engine & session factory
│   │   │   └── models.py                     # ORM table definitions
│   │   ├── models/
│   │   │   ├── schemas.py                    # Pydantic request/response models
│   │   │   └── events.py                     # SSE event models
│   │   ├── repositories/
│   │   │   ├── flow_repository.py            # CRUD – flows
│   │   │   ├── flow_run_repository.py        # CRUD – flow runs & cycles
│   │   │   └── api_key_repository.py         # CRUD – API keys
│   │   ├── routes/
│   │   │   ├── __init__.py                   # Router aggregation
│   │   │   ├── health.py                     # GET /, GET /ping
│   │   │   ├── hedge_fund.py                 # POST /hedge-fund/run, /backtest
│   │   │   ├── flows.py                      # Flow CRUD endpoints
│   │   │   ├── flow_runs.py                  # Run tracking endpoints
│   │   │   ├── api_keys.py                   # API key management
│   │   │   ├── language_models.py            # LLM discovery
│   │   │   ├── ollama.py                     # Ollama model lifecycle
│   │   │   └── storage.py                    # JSON file storage
│   │   └── services/
│   │       ├── graph.py                      # LangGraph orchestration
│   │       ├── agent_service.py              # Agent function wrapping
│   │       ├── backtest_service.py           # Historical backtesting
│   │       ├── api_key_service.py            # API key retrieval
│   │       ├── ollama_service.py             # Ollama integration
│   │       └── portfolio.py                  # Portfolio initialization
│   │
│   └── frontend/                             # React SPA
│       ├── public/
│       ├── src/
│       │   ├── App.tsx                       # Root component
│       │   ├── main.tsx                      # Vite entry point
│       │   ├── components/
│       │   │   ├── Layout.tsx                # VSCode-style shell
│       │   │   ├── Flow.tsx                  # React Flow canvas
│       │   │   ├── ui/                       # shadcn/ui primitives
│       │   │   ├── settings/                 # Settings panel (API keys, models, theme)
│       │   │   ├── tabs/                     # Multi-tab interface
│       │   │   ├── layout/                   # Top bar
│       │   │   └── panels/
│       │   │       ├── left/                 # Flow list & management
│       │   │       ├── right/                # Component/node library
│       │   │       └── bottom/               # Output, terminal, debug tabs
│       │   ├── nodes/                        # Custom React Flow node types
│       │   │   └── components/
│       │   │       ├── agent-node.tsx
│       │   │       ├── stock-analyzer-node.tsx
│       │   │       ├── portfolio-start-node.tsx
│       │   │       ├── portfolio-manager-node.tsx
│       │   │       ├── investment-report-node.tsx
│       │   │       └── json-output-node.tsx
│       │   ├── contexts/                     # React Context providers
│       │   │   ├── node-context.tsx          # Agent node state
│       │   │   ├── flow-context.tsx          # Flow CRUD state
│       │   │   ├── layout-context.tsx        # Panel visibility
│       │   │   └── tabs-context.tsx          # Tab lifecycle
│       │   ├── hooks/                        # Custom React hooks
│       │   ├── services/                     # Backend API clients
│       │   │   ├── api.ts                    # SSE streaming + REST calls
│       │   │   ├── backtest-api.ts           # Backtest execution
│       │   │   ├── api-keys-api.ts           # Key management
│       │   │   ├── flow-service.ts           # Flow CRUD
│       │   │   └── tab-service.ts            # Tab state
│       │   ├── data/                         # Static agent/model definitions
│       │   └── utils/                        # Date & text helpers
│       ├── package.json
│       ├── vite.config.ts
│       ├── tailwind.config.ts
│       └── tsconfig.json
│
├── src/                                      # Core engine (shared by CLI + backend)
│   ├── main.py                               # CLI workflow entry point
│   ├── backtester.py                         # Backtesting CLI entry
│   ├── agents/                               # 20 analyst agents + 2 system agents
│   │   ├── warren_buffett.py                 # Value investing – moats, intrinsic value
│   │   ├── ben_graham.py                     # Deep value – margin of safety
│   │   ├── charlie_munger.py                 # Quality at a fair price
│   │   ├── michael_burry.py                  # Contrarian deep value
│   │   ├── mohnish_pabrai.py                 # Dhandho framework
│   │   ├── peter_lynch.py                    # Growth at reasonable price (GARP)
│   │   ├── phil_fisher.py                    # Scuttlebutt growth
│   │   ├── cathie_wood.py                    # Disruptive innovation growth
│   │   ├── bill_ackman.py                    # Activist contrarian
│   │   ├── aswath_damodaran.py               # DCF & valuation models
│   │   ├── stanley_druckenmiller.py          # Macro-driven
│   │   ├── rakesh_jhunjhunwala.py            # Emerging market growth
│   │   ├── rentec.py                         # Quant: Kelly, EV gap, KL-div, Bayesian, LMSR
│   │   ├── technicals.py                     # Technical analysis (deterministic)
│   │   ├── fundamentals.py                   # Financial statement analysis (deterministic)
│   │   ├── valuation.py                      # Multi-model valuation (deterministic)
│   │   ├── sentiment.py                      # Market sentiment (deterministic)
│   │   ├── news_sentiment.py                 # News NLP analysis
│   │   ├── growth_agent.py                   # Growth trend specialist
│   │   ├── risk_manager.py                   # Position limits & volatility (system)
│   │   └── portfolio_manager.py              # Final trade decisions (system)
│   ├── backtesting/
│   │   ├── engine.py                         # Backtest orchestration
│   │   ├── trader.py                         # Trade execution simulator
│   │   ├── portfolio.py                      # Portfolio state
│   │   ├── metrics.py                        # Performance calculations
│   │   ├── benchmarks.py                     # Benchmark comparisons
│   │   ├── controller.py                     # Agent controller
│   │   ├── output.py                         # Results formatting
│   │   └── valuation.py                      # Portfolio valuation
│   ├── graph/
│   │   └── state.py                          # LangGraph AgentState definition
│   ├── data/
│   │   ├── cache.py                          # In-memory API response cache
│   │   └── models.py                         # Pydantic data models (15+ classes)
│   ├── llm/
│   │   ├── models.py                         # LLM provider registry & instantiation
│   │   ├── api_models.json                   # Cloud model definitions
│   │   └── ollama_models.json                # Local model definitions
│   ├── tools/
│   │   └── api.py                            # Financial API client (FinancialDatasets.ai)
│   ├── utils/
│   │   ├── analysts.py                       # ANALYST_CONFIG – agent registry
│   │   ├── llm.py                            # call_llm() helper with retries
│   │   ├── progress.py                       # Progress tracking
│   │   ├── api_key.py                        # API key extraction from state
│   │   ├── display.py                        # Console output formatting
│   │   ├── visualize.py                      # Graph visualization
│   │   ├── docker.py                         # Docker utilities
│   │   └── ollama.py                         # Ollama integration
│   └── cli/
│       └── input.py                          # CLI argument parsing
│
├── docker/
│   ├── Dockerfile                            # Python 3.11-slim + Poetry
│   └── docker-compose.yml                    # Services: hedge-fund, backtester, ollama
│
├── tests/
│   ├── test_api_rate_limiting.py
│   └── backtesting/
│       ├── conftest.py                       # Fixtures
│       ├── test_results.py
│       ├── test_valuation.py
│       ├── test_metrics.py
│       ├── test_portfolio.py
│       ├── test_execution.py
│       ├── test_controller.py
│       └── integration/
│           ├── mocks.py                      # Mock agent responses
│           ├── test_integration_long_short.py
│           ├── test_integration_short_only.py
│           └── test_integration_long_only.py
│
├── outputs/                                  # Saved JSON results
├── pyproject.toml                            # Poetry dependencies
├── .env.example                              # Environment variable template
├── README.md
└── ARCHITECTURE.md                           # This file
```

---

## 2. HIGH-LEVEL SYSTEM DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USER                                       │
│                    (Browser or CLI terminal)                             │
└──────────────┬──────────────────────────────────┬───────────────────────┘
               │ HTTP/SSE                         │ CLI
               ▼                                  ▼
┌──────────────────────────┐        ┌──────────────────────────┐
│     FRONTEND (React)     │        │     CLI (src/main.py)    │
│  - React Flow canvas     │        │  - argparse interface    │
│  - shadcn/ui + Tailwind  │        │  - rich console output   │
│  - SSE streaming client  │        │  - questionary prompts   │
│  - Multi-tab flow editor │        └────────────┬─────────────┘
└──────────────┬───────────┘                     │
               │ REST + SSE (port 8000)          │ direct import
               ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                                    │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │   Routes     │  │  Services    │  │ Repositories │                  │
│  │  (REST/SSE)  │──│  (business   │──│  (data       │──► SQLite DB    │
│  │              │  │   logic)     │  │   access)    │                  │
│  └──────────────┘  └──────┬───────┘  └──────────────┘                  │
│                           │                                             │
└───────────────────────────┼─────────────────────────────────────────────┘
                            │ invoke
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     CORE ENGINE (src/)                                   │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    LangGraph StateGraph                           │  │
│  │                                                                   │  │
│  │  start_node ──┬──► Agent 1 (Warren Buffett)  ──┐                 │  │
│  │               ├──► Agent 2 (Michael Burry)    ──┤                 │  │
│  │               ├──► Agent 3 (RenTec Quant)     ──┼──► Risk Mgr    │  │
│  │               ├──► Agent N ...                ──┤    ──► Portfolio│  │
│  │               └──► Technical Analyst          ──┘        Manager  │  │
│  │                                                          ──► END  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                           │                                             │
│                           ▼                                             │
│  ┌─────────────────────────────────────────────────────┐               │
│  │              LLM Providers (12 supported)            │               │
│  │  OpenAI │ Anthropic │ Groq │ Google │ DeepSeek │ xAI│               │
│  │  GigaChat │ OpenRouter │ Azure │ Ollama (local)     │               │
│  └─────────────────────────────────────────────────────┘               │
│                           │                                             │
│                           ▼                                             │
│  ┌─────────────────────────────────────────────────────┐               │
│  │          Financial Data (FinancialDatasets.ai)       │               │
│  │  Prices │ Metrics │ Line Items │ Insider Trades │    │               │
│  │  Company News │ Market Cap │ Company Facts          │               │
│  └─────────────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. CORE COMPONENTS

### 3.1 Frontend — React SPA

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Visual flow editor for designing and executing multi-agent trading strategies |
| **Technologies** | React 18, TypeScript, Vite 5, Tailwind CSS 3, @xyflow/react 12 (React Flow), shadcn/ui, Radix UI |
| **Key features** | Drag-and-drop node canvas, SSE streaming output, multi-tab interface, per-agent LLM selection, undo/redo, auto-save |
| **State management** | React Context API (4 contexts: Node, Flow, Layout, Tabs) + localStorage persistence |
| **Deployment** | `npm run build` produces static assets; served via Vite dev server locally (port 5173) |

### 3.2 Backend — FastAPI Server

| Attribute | Detail |
|-----------|--------|
| **Purpose** | REST/SSE API serving the frontend, managing flows, executing agent graphs, running backtests |
| **Technologies** | FastAPI, SQLAlchemy, Alembic, Pydantic v2, asyncio |
| **Architecture** | 3-layer: Routes → Services → Repositories |
| **Key endpoints** | `POST /hedge-fund/run` (SSE streaming), `POST /hedge-fund/backtest` (SSE streaming), Flow CRUD, API key management |
| **Deployment** | `uvicorn app.backend.main:app` (port 8000); Docker container available |

### 3.3 Core Engine — Agent Framework (src/)

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Reusable multi-agent trading engine shared by CLI and backend |
| **Technologies** | LangGraph 0.2.56, LangChain 0.3.7, pandas, numpy |
| **Agent types** | 18 analyst agents (13 LLM-based persona agents + 5 deterministic quant agents) + risk manager + portfolio manager |
| **Agent pattern** | Fetch data → Run sub-analyses → Aggregate score → LLM synthesis → Return signal (bullish/bearish/neutral + confidence 0-100 + reasoning) |
| **Graph flow** | `start → [parallel analysts] → risk_manager → portfolio_manager → END` |

### 3.4 Backtesting Engine

| Attribute | Detail |
|-----------|--------|
| **Purpose** | Historical simulation of agent strategies across date ranges |
| **Technologies** | Custom engine in `src/backtesting/` |
| **Key features** | Long/short execution, margin tracking, benchmark comparisons, performance metrics (Sharpe, drawdown, etc.) |
| **Entry points** | CLI via `poetry run backtester`, web via `POST /hedge-fund/backtest` |

---

## 4. DATA STORES

### 4.1 SQLite Database

| Attribute | Detail |
|-----------|--------|
| **Type** | SQLite (file-based) |
| **Location** | `app/backend/hedge_fund.db` |
| **ORM** | SQLAlchemy with declarative models |
| **Migrations** | Alembic (5 migration scripts) |
| **Purpose** | Persistent storage for flows, runs, cycles, and API keys |

**Tables:**

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `hedge_fund_flows` | React Flow graph configurations | id, name, description, nodes (JSON), edges (JSON), viewport (JSON), tags, is_template |
| `hedge_fund_flow_runs` | Execution tracking | id, flow_id, status (IDLE/IN_PROGRESS/COMPLETE/ERROR), request_data, initial_portfolio, final_portfolio, results, run_number |
| `hedge_fund_flow_run_cycles` | Per-cycle backtest data | id, flow_run_id, cycle_number, analyst_signals, trading_decisions, executed_trades, performance_metrics, portfolio_snapshot, llm_calls_count, estimated_cost |
| `api_keys` | API credential storage | id, provider (unique), key_value, is_active, last_used |

### 4.2 In-Memory Cache

| Attribute | Detail |
|-----------|--------|
| **Type** | Python dictionary (in-process) |
| **Location** | `src/data/cache.py` |
| **Purpose** | De-duplicate API responses within a single run (prices, metrics, line items, insider trades, news) |
| **Persistence** | None — cleared on process restart |
| **Eviction** | None — grows for session lifetime |

### 4.3 LocalStorage (Frontend)

| Attribute | Detail |
|-----------|--------|
| **Type** | Browser localStorage |
| **Purpose** | Persist UI state: open tabs, sidebar collapse states, theme preference |

---

## 5. EXTERNAL INTEGRATIONS

| Service | Purpose | Integration Method |
|---------|---------|-------------------|
| **FinancialDatasets.ai** | Stock prices, financial metrics, line items, insider trades, company news, market cap, company facts | REST API with `X-API-KEY` header; rate-limit retry (429 → 60s backoff) |
| **OpenAI API** | GPT-4o, GPT-4o-mini LLM inference | LangChain `ChatOpenAI`; `OPENAI_API_KEY` |
| **Anthropic API** | Claude Opus, Sonnet, Haiku LLM inference | LangChain `ChatAnthropic`; `ANTHROPIC_API_KEY` |
| **Google Gemini API** | Gemini 2.5 Pro/Flash LLM inference | LangChain `ChatGoogleGenerativeAI`; `GOOGLE_API_KEY` |
| **Groq API** | Llama 3.1, Mixtral, DeepSeek (fast inference) | LangChain `ChatGroq`; `GROQ_API_KEY` |
| **DeepSeek API** | DeepSeek Chat & Reasoner | LangChain `ChatDeepSeek`; `DEEPSEEK_API_KEY` |
| **xAI API** | Grok-4, Grok-2 | LangChain `ChatXAI`; `XAI_API_KEY` |
| **GigaChat API** | GigaChat (Russian market LLM) | LangChain `GigaChat`; `GIGACHAT_API_KEY` |
| **OpenRouter API** | 200+ models via unified API | LangChain `ChatOpenAI` (custom base URL); `OPENROUTER_API_KEY` |
| **Azure OpenAI** | Managed GPT-4o | LangChain `AzureChatOpenAI`; `AZURE_OPENAI_API_KEY` + endpoint |
| **Ollama** | Local open-source LLMs (Llama, Mistral, etc.) | HTTP API at `localhost:11434`; no auth required |

---

## 6. DEPLOYMENT & INFRASTRUCTURE

### 6.1 Local Development

```
Frontend:  npm run dev        → Vite dev server (port 5173)
Backend:   uvicorn app.backend.main:app --reload  → FastAPI (port 8000)
CLI:       poetry run python src/main.py --ticker AAPL,MSFT
Backtest:  poetry run backtester
```

### 6.2 Docker

| File | Detail |
|------|--------|
| `docker/Dockerfile` | Python 3.11-slim, Poetry 1.7.1, copies source, runs `src/main.py` |
| `docker/docker-compose.yml` | 6 service variants: `hedge-fund`, `hedge-fund-reasoning`, `hedge-fund-ollama`, `backtester`, `backtester-ollama`, `ollama` |

**Ollama container**: Exposes port 11434, Apple Metal GPU pass-through on macOS.

### 6.3 Cloud Provider

No cloud deployment configuration is present. The application runs locally or in Docker containers.

### 6.4 CI/CD

No CI/CD pipeline is configured. The `.github/` directory contains only issue templates.

### 6.5 Monitoring

No monitoring, logging aggregation, or alerting tools are integrated. The backend uses Python `logging` at INFO level and console output via `rich`.

---

## 7. SECURITY CONSIDERATIONS

### 7.1 Authentication & Authorization

| Aspect | Status |
|--------|--------|
| **User authentication** | None — no login, JWT, OAuth, or API gateway |
| **Authorization / RBAC** | None — all endpoints are publicly accessible |
| **API key storage** | Stored in SQLite `api_keys` table; summary endpoints omit `key_value` field |
| **CORS** | Restricted to `http://localhost:5173` and `http://127.0.0.1:5173` |

### 7.2 Data Protection

| Aspect | Detail |
|--------|--------|
| **Transport** | HTTP only (no TLS configured); assumed behind reverse proxy in production |
| **At-rest encryption** | None — SQLite file is unencrypted |
| **Secrets management** | `.env` file for CLI; `/api-keys/` endpoints for web UI; `.env.example` provided |

### 7.3 Input Validation

- Pydantic v2 enforces type and constraint checking on all request/response models
- FastAPI validates query parameters (pagination limits, date formats)
- No rate limiting on API endpoints

### 7.4 Known Gaps

- No authentication layer (intended as a local/educational tool)
- API keys potentially stored in plain text in SQLite
- No request body size limits
- No audit logging

---

## 8. DEVELOPMENT & TESTING

### 8.1 Local Setup

```bash
# Prerequisites: Python 3.11+, Node.js 18+, Poetry

# 1. Clone and configure
git clone git@github.com:ianalrahwan/ai-hedge-fund.git
cd ai-hedge-fund
cp .env.example .env
# Add your API keys to .env

# 2. Backend
poetry install

# 3. Frontend
cd app/frontend
npm install

# 4. Run
poetry run python src/main.py --ticker AAPL,MSFT,NVDA     # CLI mode
# or
uvicorn app.backend.main:app --reload &                    # Backend
cd app/frontend && npm run dev                             # Frontend
```

### 8.2 Testing

| Tool | Scope | Command |
|------|-------|---------|
| **pytest** | Unit + integration tests | `poetry run pytest` |
| **Test fixtures** | `tests/backtesting/conftest.py` | Mock portfolios, agents, price data |
| **Integration tests** | Long-only, short-only, long/short strategies | `tests/backtesting/integration/` |
| **Coverage areas** | Backtest engine, portfolio management, trade execution, metrics, valuation, API rate limiting | |

### 8.3 Code Quality

| Tool | Purpose | Config |
|------|---------|--------|
| **black** | Code formatting | pyproject.toml (dev dependency) |
| **isort** | Import sorting | pyproject.toml (dev dependency) |
| **flake8** | Linting | pyproject.toml (dev dependency) |
| **TypeScript strict mode** | Frontend type safety | tsconfig.json `strict: true` |
| **ESLint** | Frontend linting | Vite default config |

---

## 9. FUTURE CONSIDERATIONS

### 9.1 Known Technical Debt

- **No authentication**: The app has zero auth; any user on the network can access all endpoints and stored API keys
- **SQLite limitations**: Single-writer, file-based; will not scale for concurrent users
- **In-memory cache**: No eviction or persistence; grows unbounded during long sessions
- **Hardcoded CORS origins**: Only `localhost:5173` is allowed; production deployment would require configuration
- **No rate limiting**: Backend endpoints have no throttling
- **No CI/CD pipeline**: No automated testing, linting, or deployment on push

### 9.2 Planned Migrations

- The Alembic migration infrastructure is in place, indicating an expectation that the schema will evolve
- Multiple LLM provider integrations suggest potential for provider-agnostic abstraction layer

### 9.3 Potential Roadmap Items

- Production-grade database (PostgreSQL)
- User authentication and multi-tenancy
- Real-time market data feeds (WebSocket)
- Live paper trading integration
- Agent performance leaderboard and analytics
- Cloud deployment (Kubernetes / serverless)
- CI/CD pipeline with automated tests

---

## 10. GLOSSARY

| Term | Definition |
|------|------------|
| **Agent** | An autonomous analysis module that evaluates stocks using a specific investing philosophy or quantitative method |
| **Analyst Signal** | The output of an agent: a bullish/bearish/neutral signal with confidence (0-100) and reasoning |
| **ANALYST_CONFIG** | The single source of truth registry in `src/utils/analysts.py` mapping agent keys to their functions and metadata |
| **AgentState** | The LangGraph TypedDict shared across all agents containing messages, data (tickers, portfolio, analyst_signals), and metadata |
| **Backtest** | A historical simulation that runs the agent pipeline across a date range, executing trades and tracking performance |
| **EV Gap** | Expected Value Gap — the percentage difference between a model-derived fair value and the market price |
| **Flow** | A saved React Flow graph configuration representing a specific arrangement of agents and connections |
| **Kelly Criterion** | A formula `f* = (p*b - q) / b` for optimal bet/position sizing based on edge and win probability |
| **KL-Divergence** | Kullback-Leibler divergence — a measure of statistical distance between two probability distributions |
| **LangGraph** | A framework for building stateful, multi-actor workflows as directed graphs |
| **LMSR** | Logarithmic Market Scoring Rule — a pricing mechanism for prediction markets; adapted here for liquidity/impact estimation |
| **Ollama** | An open-source tool for running LLMs locally without cloud API keys |
| **Portfolio Manager** | The terminal agent that synthesizes all analyst signals and risk limits into final buy/sell/short/cover/hold decisions |
| **React Flow** | A library for building node-based graph editors in React (@xyflow/react) |
| **Risk Manager** | A system agent that computes position limits based on volatility, correlations, and portfolio constraints |
| **SSE** | Server-Sent Events — a protocol for real-time server-to-client streaming over HTTP |
| **StateGraph** | A LangGraph construct that defines agent nodes, edges, and the shared state they operate on |

---

## 11. PROJECT IDENTIFICATION

| Field | Value |
|-------|-------|
| **Project name** | AI Hedge Fund |
| **Repository** | `git@github.com:ianalrahwan/ai-hedge-fund.git` |
| **Primary branch** | `main` |
| **Language** | Python 3.11+ (backend/engine), TypeScript (frontend) |
| **Package manager** | Poetry (Python), npm (frontend) |
| **License** | See repository |
| **Last updated** | 2026-03-22 |
