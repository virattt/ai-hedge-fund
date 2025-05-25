# Project Brief: AI Hedge Fund

## Core Mission

To explore the use of Artificial Intelligence (AI) to make simulated trading decisions for educational and research purposes. The project aims to serve as a proof of concept for an AI-powered hedge fund.

## Project Goals

- Simulate trading decisions using a variety of AI agents, each embodying different investment philosophies or analytical functions.
- Provide a platform for learning and experimenting with AI in the context of financial markets.
- Enable backtesting of AI-driven trading strategies.
- **Current Branch Goal (`graceful-rate-limiting`):** Implement robust and graceful rate limiting for all external API calls (e.g., LLM providers, financial data providers) to prevent service disruptions and manage costs.

## Target Audience/Users

- Individuals interested in AI and its application in finance.
- Students and researchers exploring algorithmic trading and AI-driven investment strategies.
- Developers looking for a sandbox project involving AI agents and financial data.

## Key Features (High-Level)

- **Multi-Agent System:** Employs a diverse set of AI agents (e.g., "Warren Buffett Agent," "Sentiment Agent," "Valuation Agent") to contribute to trading decisions.
- **Trading Simulation:** Simulates trading decisions without executing real trades.
- **Backtesting:** Allows users to backtest trading strategies over historical data.
- **API Integration:** Utilizes external APIs for Large Language Models (OpenAI, Groq, Anthropic, Deepseek, Ollama for local models) and financial data (FinancialDatasets.ai).
- **Configurable Execution:** Supports running with different stock tickers, date ranges, and options to show agent reasoning.
- **Docker Support:** Provides Docker-based setup for ease of deployment and environment consistency.

## Success Metrics

- **Educational Value:** The extent to which the project serves as a useful learning tool.
- **Simulation Accuracy:** (Potentially) The realism or plausibility of the simulated trading decisions and backtesting results (within the educational scope).
- **System Stability:** Reliable operation of the simulation and backtesting tools.
- **Modularity and Extensibility:** Ease of adding new agents or modifying existing ones.
- **For `graceful-rate-limiting` branch:**
    - Effective prevention of API rate limit errors.
    - Clear handling and notification (if applicable) when rate limits are approached or hit.
    - Minimal impact on the core simulation logic due to rate limiting implementation.

## Initial State
- This document was created on 5/25/2025 as part of initializing the Memory Bank for the 'ai-hedge-fund' project.
- The project is a fork, and this Memory Bank is being established to support ongoing development, starting with the 'graceful-rate-limiting' branch.
