# Docker Orchestration for AI Hedge Fund

> [!NOTE]
> **Upstream Credit:** This project is a complete high-performance, 100% native Rust port of the original Python-based [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) repository. All credit for the brilliant agentic design, collaborative trading workflows, and educational framework goes to the original upstream repository.

This directory provides Docker orchestration configurations for building and executing the native **Rust** parallel orchestrator and backtester inside light-weight containers.

---

## Overview

The Docker environment enables:
1. **Isolated Execution**: Package the Rust binaries along with necessary dynamic linking libraries without installing build utilities on your host system.
2. **Integrated local LLMs (Ollama)**: Automatically spin up a containerized Ollama server, pull model binaries (e.g. `llama3` or `mistral`), and wire them up with the hedge fund agent network automatically.
3. **Hardware Acceleration**: Enable Metal GPU acceleration on Apple Silicon (M-series) or NVIDIA GPU access on Linux through custom Compose profiles.

---

## 🛠️ Build and Setup

### Prerequisites
- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed.

### 1. Build the Docker Image
From the project root directory, build the Docker container:
```bash
docker build -t ai-hedge-fund -f docker/Dockerfile .
```
*This uses a multi-stage Docker build to compile all binary targets (`ai-hedge-fund`, `backtester`, `app-backend`, `v2-event-study`, `v2-backtesting`) in a release profile, producing a highly optimized lightweight container.*

### 2. Configure Your Environment Keys
Ensure a `.env` file exists in your repository root with your API keys:
```bash
cp .env.example .env
```

---

## 🚀 Running Containers

You can run commands directly using `docker run` or orchestrate multi-container systems using `docker-compose`.

### Running the AI Hedge Fund (Rust CLI)
Execute the parallel orchestrator directly through Docker:
```bash
docker run -it --rm -v $(pwd)/.env:/app/.env ai-hedge-fund ./ai-hedge-fund --ticker AAPL,MSFT,NVDA
```

### Running the Backtester (Rust CLI)
```bash
docker run -it --rm -v $(pwd)/.env:/app/.env ai-hedge-fund ./backtester --tickers AAPL,MSFT --start-date 2026-01-01 --end-date 2026-02-01
```

### Running the Axum Web Server (Backend API)
Deploy the Axum server in a container mapping port 8000:
```bash
docker run -d --name hedge-backend -p 8000:8000 -v $(pwd)/.env:/app/.env -v $(pwd)/hedge_fund.db:/app/hedge_fund.db ai-hedge-fund ./app-backend
```

---

## Multi-Container Composition (Docker Compose)

The `docker/docker-compose.yml` orchestrates:
- `ollama`: Containerized local LLM instance.
- `hedge-fund`: The Rust orchestrator running with remote API providers.
- `hedge-fund-ollama`: The Rust orchestrator integrated with local LLMs.
- `backtester`: The native backtest runner.

### Start with Embedded Ollama
To spin up both the local LLM server and execute a run:
```bash
docker compose --profile embedded-ollama up --build
```

---

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No warranties or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions
