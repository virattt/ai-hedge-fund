# Open Hedge - React Frontend Dashboard

> [!NOTE]
> **Upstream Credit:** This project is a complete high-performance, 100% native Rust port of the original Python-based [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) repository. All credit for the brilliant agentic design, collaborative trading workflows, and educational framework goes to the original upstream repository.

This is the interactive frontend application for **Open Hedge**. Built using React and Vite, it provides a premium, user-friendly interface to visualize and control the parallel multi-agent trading system and backtesting engine.

---

## Overview

The frontend dashboard serves as the visual control room for Open Hedge:
- **Node Graph Editor**: Visually build and configure your analyst agent DAG workflows using React Flow.
- **Backtesting Dashboard**: Configure tickers, dates, initial amounts, and select active analysts to trigger backtest runs.
- **Daily Simulation Dashboard**: Run single-day orchestrations and view live outputs.
- **SSE Streaming Console**: Watch real-time streaming daily metrics, logs, and intermediate agent reasoning steps as they are processed by the Axum backend.

---

## 🛠️ Installation & Setup

### Prerequisites
- [Node.js & npm](https://nodejs.org/)

### 1. Install Dependencies
Navigate to the frontend directory and install the packages:
```bash
cd app/frontend
npm install
```

### 2. Configure Environment Variables
Create a `.env` file inside the `app/frontend/` directory (or rely on the proxy default pointing to `http://localhost:8000`):
```bash
VITE_API_URL=http://localhost:8000
```

---

## 🚀 Running the Application

To launch the frontend development server:

```bash
# From the frontend directory
npm run dev
```

*The dashboard will be served at `http://localhost:5173`. Open this address in your web browser to start visualizing your agentic hedge fund!*

---

## Disclaimer

This project is for **educational and research purposes only**.

- Not intended for real trading or investment
- No warranties or guarantees provided
- Creator assumes no liability for financial losses
- Consult a financial advisor for investment decisions