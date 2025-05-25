# Product Context: AI Hedge Fund

## Problem Statement

- Exploring and understanding how AI can be applied to financial trading decisions in a simulated environment.
- Providing a hands-on educational tool for learning about different investment philosophies (via various agents) and AI's role in financial analysis.
- Addressing the need for a configurable and extensible platform for experimenting with AI-driven trading strategies without real financial risk.
- **For `graceful-rate-limiting` branch:** The potential for frequent API calls to LLM providers and financial data services to hit rate limits, disrupting simulations and incurring unnecessary costs or delays.

## Proposed Solution

A multi-agent AI system that simulates hedge fund operations:
- **Diverse Agents:** Different agents specialize in various aspects of investment (valuation, sentiment, fundamentals, technicals, risk management, specific investor philosophies).
- **Simulated Trading:** The system makes trading decisions but does not execute real trades, focusing on the decision-making process.
- **Backtesting Capability:** Allows users to test strategies against historical data.
- **API Integration:** Leverages LLMs (OpenAI, Groq, etc.) for agent reasoning and FinancialDatasets.ai for market data.
- **Educational Focus:** Clearly disclaims real investment advice, emphasizing its role as a learning tool.
- **For `graceful-rate-limiting` branch:** Implement a system-wide mechanism to monitor and manage API call frequency, employing strategies like backoff, retry, and potentially queuing to handle API limits smoothly.

## Target User Experience

- **Ease of Setup:** Users should be able to set up and run the simulation with clear instructions, using either Poetry or Docker.
- **Configurability:** Users should be able to easily configure simulations (tickers, dates, agent parameters like `--show-reasoning` or `--ollama`).
- **Insightful Output:** The simulation and backtester should provide clear and understandable output regarding trading decisions, agent reasoning (if enabled), and performance metrics.
- **Educational:** Users should feel they are learning about AI in finance and different investment approaches.
- **Reliability (re: rate limits):** Users should experience smooth, uninterrupted simulations without abrupt failures due to API rate limits being hit. If limits are approached, the system should handle it gracefully.

## Key Use Cases

1.  **Learning AI in Finance:** A student or enthusiast sets up the project to understand how different AI agents can analyze financial data and make trading decisions.
2.  **Strategy Experimentation:** A researcher uses the backtester to evaluate the performance of a custom agent or a new combination of existing agents.
3.  **Understanding Investment Philosophies:** A user runs simulations focusing on specific agents (e.g., Warren Buffett vs. Cathie Wood) to see how their modeled strategies differ.
4.  **Developing AI Agents:** A developer forks the project to create and integrate a new type of financial analysis agent.
5.  **Running Extended Simulations/Backtests:** A user runs a long simulation or backtest that involves many API calls, relying on the graceful rate limiting to complete without interruption.

## Initial State
- This document was created on 5/25/2025 as part of initializing the Memory Bank for the 'ai-hedge-fund' project.
- This file is intended to evolve as the project's purpose and user interactions become clearer.
- Current development focus: 'graceful-rate-limiting' branch.
