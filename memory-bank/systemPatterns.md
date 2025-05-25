# System Patterns: AI Hedge Fund

## System Architecture Overview

The system is designed as a multi-agent framework where various specialized AI agents collaborate to simulate trading decisions. Key components include:

-   **Individual Investor Agents:** Emulate famous investors (Aswath Damodaran, Ben Graham, Bill Ackman, Cathie Wood, Charlie Munger, Michael Burry, Peter Lynch, Phil Fisher, Stanley Druckenmiller, Warren Buffett). These likely contribute qualitative or strategic insights.
-   **Analytical Agents:** Perform specific financial analyses:
    -   Valuation Agent
    -   Sentiment Agent
    -   Fundamentals Agent
    -   Technicals Agent
-   **Portfolio Management Agents:**
    -   Risk Manager: Calculates risk and sets position limits.
    -   Portfolio Manager: Makes final trading decisions and generates orders.
-   **Core Application Logic:** Orchestrates agent interactions, manages data flow, and runs simulations or backtests.
-   **External API Interfaces:** Modules for interacting with LLM providers and financial data sources.

A simplified view of the interaction could be:
```mermaid
flowchart TD
    subgraph Data_Sources
        FinancialData[FinancialDatasets.ai]
        LLM_APIs[LLM APIs (OpenAI, Groq, etc.)]
    end

    subgraph AI_Hedge_Fund_System
        CoreApp[Core Application Logic / main.py / backtester.py]

        subgraph Investor_Agents
            direction LR
            IA1[Aswath Damodaran Agent]
            IA2[Ben Graham Agent]
            IA_N[... up to 10 investor agents]
        end

        subgraph Analytical_Agents
            direction LR
            AA1[Valuation Agent]
            AA2[Sentiment Agent]
            AA3[Fundamentals Agent]
            AA4[Technicals Agent]
        end
        
        subgraph Management_Agents
            direction LR
            RiskMgr[Risk Manager]
            PortfolioMgr[Portfolio Manager]
        end

        CoreApp --> Investor_Agents
        CoreApp --> Analytical_Agents
        Investor_Agents --> CoreApp
        Analytical_Agents --> CoreApp
        CoreApp --> RiskMgr
        RiskMgr --> PortfolioMgr
        PortfolioMgr --> CoreApp # Simulated Orders

        CoreApp -- Fetches Data --> FinancialData
        
        subgraph LLM_Interaction_Subsystem
            LLM_Util[src/utils/llm.py : call_llm()]
            LLM_Models_Module[src/llm/models.py : get_model()]
            Langchain_Clients[Langchain Provider Clients e.g., ChatOpenAI, ChatGroq]

            LLM_Util -- Uses --> LLM_Models_Module
            LLM_Models_Module -- Instantiates --> Langchain_Clients
            Langchain_Clients -- HTTP Call --> LLM_APIs 
            note right of Langchain_Clients: Actual network call happens here
        end
        
        Investor_Agents -- Calls --> LLM_Util
        Analytical_Agents -- Calls --> LLM_Util
    end

    User[User CLI Interaction] --> CoreApp
    CoreApp --> Output[Console Output / Results]
```
*(This is an initial interpretation and will be refined as the codebase is explored.)*

## Key Technical Decisions

*(To be defined. Document significant architectural and technical choices made during development.)*
    - **Multi-Agent Architecture:** The core design choice is to use a collection of specialized agents. This allows for modularity and the simulation of diverse analytical perspectives.
    - **Externalization of Intelligence:** Heavy reliance on external LLMs for agent reasoning and financial data APIs for market information.
    - **Simulation, Not Real Trading:** A deliberate choice to keep the project educational and avoid real financial transactions.
    - **Configurability via CLI:** Providing command-line arguments for tickers, dates, and operational modes (e.g., `--show-reasoning`, `--ollama`).
    - **Dual Setup Options (Poetry/Docker):** Offering flexibility in how users set up and run the project.
    - **Initial Focus (Graceful Rate Limiting):** The first major development effort is to implement graceful rate limiting for external API interactions. This will likely involve:
        - Identifying all points of external API calls (primarily to LLM providers and FinancialDatasets.ai).
        - Designing a centralized or distributed mechanism to track API usage against known or configurable limits.
        - Implementing strategies for handling exceeded limits (e.g., exponential backoff, retry mechanisms, request queuing, user notification/logging).
        - Ensuring the rate limiting mechanism is configurable and can adapt to different API provider policies.

## Design Patterns in Use

-   **Agent Pattern:** The entire system is based on this, where autonomous agents perform specific tasks and communicate (likely indirectly via the core application).
-   **Strategy Pattern (Potentially):** Different investor agents might represent different strategies for market analysis or decision-making. Analytical agents also embody specific strategies for their domain.
-   **Facade Pattern:**
    -   `src/tools/api.py` acts as a facade for `financialdatasets.ai` API interactions.
    -   `src/utils/llm.py` (specifically `call_llm`) acts as a facade for all LLM API interactions, abstracting away the specifics of different Langchain provider clients.
-   **Strategy Pattern (Potentially):** Different investor agents might represent different strategies for market analysis or decision-making. Analytical agents also embody specific strategies for their domain.
-   **Command Pattern (Potentially):** CLI interactions (`main.py`, `backtester.py` with arguments) could be implemented using a command pattern.
*(Facade pattern for API calls is now confirmed for both financial data and LLMs.)*

## Component Relationships

-   **`main.py` / `backtester.py`:** Act as entry points and orchestrators for agent workflows.
-   **`src/agents/`:** Contains the logic for individual agents.
    -   Depend on `src/tools/api.py` for financial data.
    -   Depend on `src/utils/llm.py` (via `call_llm`) for LLM-based reasoning.
-   **`src/tools/api.py`:** Handles direct communication with `financialdatasets.ai`. This is one key area for rate limiting.
    -   **`src/utils/llm.py`:** Centralizes LLM calls via its `call_llm` function. This function is a primary candidate for rate-limiting logic.
        -   It depends on **`src/llm/models.py`** (specifically its `get_model` function) to obtain instantiated Langchain client objects (e.g., `ChatOpenAI`, `ChatGroq`).
        -   The actual network call (`.invoke()`) to the LLM provider happens within `call_llm` using the client object obtained from `src/llm/models.py`.
-   **`src/llm/models.py`:** Responsible for loading model configurations (from JSON files) and instantiating the correct Langchain client for a given provider, including handling API key retrieval from environment variables.
-   **Configuration (`.env`):** Provides API keys essential for `src/tools/api.py` and for `src/llm/models.py` to configure Langchain clients.
-   The `Portfolio Manager` agent likely depends on inputs from many other agents and the `Risk Manager`.
*(Refer to the updated Mermaid diagram in "System Architecture Overview" for a visual representation.)*

## Initial State
- This document was created on 5/25/2025 as part of initializing the Memory Bank for the 'ai-hedge-fund' project.
- The system architecture and patterns will be documented as they are understood and implemented.
- Current development focus: 'graceful-rate-limiting' branch.
