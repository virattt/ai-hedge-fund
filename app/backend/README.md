# AI Hedge Fund - Rust Axum Backend Server

> [!NOTE]
> **Upstream Credit:** This project is a complete high-performance, 100% native Rust port of the original Python-based [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) repository. All credit for the brilliant agentic design, collaborative trading workflows, and educational framework goes to the original upstream repository.

This is the high-performance backend server for the AI Hedge Fund project. Built entirely in native **Rust** using the **Axum** web framework, it manages flow configurations, API keys, and streams daily trading simulations to the visual React dashboard.

## Overview

The backend server is built as an asynchronous web server providing:
- **Flow Management APIs**: Complete CRUD routes to create, read, update, delete, and duplicate visual trading workflows (agent graphs).
- **Live Event Streaming**: Server-Sent Events (SSE) endpoints at `/run` and `/backtest` that stream daily transaction lists, Sharpe ratios, and agent thought-chains using native Tokio channels and async streams.
- **Embedded Database**: Local SQLite connection managed by SQLx, featuring embedded schema migrations that automatically run on startup.
- **Provider Integrations**: Robust adapters to communicate with commercial LLM providers and local Ollama servers.

---

## 🛠️ Installation & Setup

### Prerequisites
- [Rust & Cargo](https://rustup.rs/) (version 1.75+)

### 1. Set Up Environment Variables
Ensure you have a `.env` file created in the project root directory:
```bash
# Create .env from template
cp .env.example .env
```

Open and edit `.env` to include your provider API keys:
```bash
# OpenAI key for default models
OPENAI_API_KEY=your-openai-api-key

# Financial Datasets key to fetch equities pricing and news
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

---

## 🚀 Running the Server

To start the high-performance Rust backend:

```bash
# From the repository root
cargo run --bin app-backend
```

*The server will boot and bind to `http://localhost:8000`. On startup, it will run embedded migrations to ensure your local SQLite database (`hedge_fund.db`) has the necessary tables.*

### API Service Configuration
- **API Base URL**: `http://localhost:8000`
- **Health Check**: `GET /health`
- **Ollama Scanner**: `GET /ollama/models` (scans available local models)

---

## Core API Endpoints

- **Flow Graphs**:
  - `GET /flows`: List all visual workflow graphs
  - `POST /flows`: Create a new agent workflow
  - `GET /flows/:id`: Fetch a specific flow graph
  - `PUT /flows/:id`: Update flow layout and configuration
  - `DELETE /flows/:id`: Delete a flow graph
- **API Keys**:
  - `GET /api-keys`: Fetch key validation states
  - `POST /api-keys`: Register new provider API keys
- **Simulations & Backtests (SSE Streaming)**:
  - `GET /hedge-fund/run`: Streams a single daily run
  - `GET /hedge-fund/backtest`: Streams an interactive backtest run

---

## Rust Backend Architecture

```
app/backend/
├── alembic/                  # Database migration schemas
│   ├── versions/             # DB schema migration versions
│   └── env.rs                # Migration coordinator
├── database/                 # Connection pools and SQLite bindings
│   ├── connection.rs         # Database pool + auto migrations
│   └── models.rs             # ORM DB schemas
├── models/                   # Type-safe API Request/Response schemas
│   ├── db_models.rs          # SQLx representations
│   ├── events.rs             # Serializable SSE stream events
│   └── schemas.rs            # Axum controller models
├── repositories/             # SQLx CRUD database actions
│   ├── api_key_repository.rs
│   ├── flow_repository.rs
│   └── flow_run_repository.rs
├── routes/                   # Axum controllers and router registry
│   ├── api_keys.rs
│   ├── flow_runs.rs
│   ├── flows.rs
│   ├── health.rs
│   ├── hedge_fund.rs         # Live SSE streaming controller
│   └── ollama.rs
├── services/                 # Business logic and agent runners
│   ├── agent_service.rs      # Dispatches calls to individual analysts
│   ├── backtest_service.rs   # Co-ordinates multi-day backtests
│   ├── graph.rs              # Executes React Flow visual workflows
│   └── portfolio.rs          # Portfolio valuation and metrics helpers
├── main.rs                   # App entry point and HTTP server listener
└── mod.rs                    # Module coordinator
```

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No warranties or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions