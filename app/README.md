# Web Application Dashboard

> [!NOTE]
> **Upstream Credit:** This project is a complete high-performance, 100% native Rust port of the original Python-based [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) repository. All credit for the brilliant agentic design, collaborative trading workflows, and educational framework goes to the original upstream repository.

The AI Hedge Fund web app is a full-stack system consisting of a high-performance Rust web backend and a modern React/Vite frontend dashboard. It enables you to construct visual agent DAGs, manage API configurations, and stream live multi-agent runs on your local machine.

<img width="1721" alt="Screenshot 2025-06-28 at 6 41 03 PM" src="https://github.com/user-attachments/assets/b95ab696-c9f4-416c-9ad1-51feb1f5374b" />

## Overview

The web application consists of two main components:
1. **Backend (`app/backend/`)**: A high-performance Axum web server written entirely in native Rust. It exposes REST API endpoints for Flow CRUD operations, API key management, and real-time Server-Sent Events (SSE) streaming for live backtests.
2. **Frontend (`app/frontend/`)**: A responsive React / Vite application implementing a beautiful node graph editor (React Flow) and live simulation dashboards.

---

## 🛠️ Installation & Setup

### Prerequisites
- [Rust & Cargo](https://rustup.rs/) (version 1.75+)
- [Node.js & npm](https://nodejs.org/)

### 1. Configure Environment Variables
Create a `.env` file in the repository root directory:
```bash
# Copy the template from .env.example
cp .env.example .env
```

Open and edit `.env` to add your keys:
```bash
# For running LLMs hosted by OpenAI
OPENAI_API_KEY=your-openai-api-key

# For getting financial datasets to power the hedge fund
FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key
```

---

## 🚀 Running the Application

To run the full-stack web application, you will need to spin up the Rust Axum backend and the React frontend concurrently.

### Step 1: Start the Rust Axum Backend
Navigate to the root directory and start the Axum web API server:
```bash
cargo run --bin app-backend
```
*The server will boot on `http://localhost:8000`. On its first run, it will automatically create and hydrate a local SQLite database (`hedge_fund.db`) with schemas for flows and API keys.*

### Step 2: Start the Vite React Frontend
Open a new terminal window, navigate to the frontend directory, and launch the dev server:
```bash
cd app/frontend
npm install
npm run dev
```
*The development server will launch on `http://localhost:5173`. Open this URL in your web browser to access the dashboard!*

---

## Key Features

- **Visual Agent Graphs**: View, construct, and customize multi-agent analytical chains using React Flow.
- **High-Performance Streaming**: Backtests and fund evaluations stream daily metrics and intermediate agent thoughts in real-time via Server-Sent Events (SSE).
- **Embedded Database**: Local SQLite connection managed by robust SQLx connection pools with automated startup migrations.
- **LLM Integrations**: Deep integrations with OpenAI, Groq, Anthropic, DeepSeek, and local Ollama targets.

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No warranties or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions

By using this software, you agree to use it solely for learning purposes.
