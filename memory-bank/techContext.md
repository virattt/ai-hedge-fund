# Technical Context: AI Hedge Fund

## Core Technologies

- **Primary Language:** Python (confirmed by `pyproject.toml`, `poetry.lock`, `src/**/*.py` files, and Poetry usage).
- **Dependency Management (Python):** Poetry.
- **Containerization:** Docker (confirmed by `Dockerfile`, `docker-compose.yml`, and `run.sh`/`run.bat` scripts for Docker commands).
- **Frontend/Tooling (Potentially):** Node.js with pnpm (inferred from `package.json`, `pnpm-lock.yaml`, though not explicitly detailed for core simulation in README). This might be for auxiliary tools or a potential web interface not covered in the core simulation README.
- **LLM Interaction:** Direct API calls to various LLM providers.
- **Local LLMs:** Supports Ollama for running local models.

## Development Environment Setup

Two primary methods are documented:

1.  **Using Poetry:**
    *   Clone the repository: `git clone https://github.com/virattt/ai-hedge-fund.git`
    *   Navigate into the directory: `cd ai-hedge-fund`
    *   Install Poetry: `curl -sSL https://install.python-poetry.org | python3 -`
    *   Install dependencies: `poetry install`
    *   Set up environment variables: Copy `.env.example` to `.env` and populate with API keys.

2.  **Using Docker:**
    *   Ensure Docker is installed.
    *   Clone the repository.
    *   Navigate into the directory.
    *   Set up environment variables: Copy `.env.example` to `.env` and populate with API keys.
    *   Build the Docker image: `./run.sh build` (Linux/Mac) or `run.bat build` (Windows).

**Environment Variables (`.env` file):**
- `OPENAI_API_KEY`: For OpenAI models (e.g., GPT-4o).
- `GROQ_API_KEY`: For Groq hosted models (e.g., Llama3).
- `FINANCIAL_DATASETS_API_KEY`: For financial data (required for tickers other than AAPL, GOOGL, MSFT, NVDA, TSLA).
- The README also mentions `ANTHROPIC_API_KEY` and `DEEPSEEK_API_KEY` as important if using models from these providers.

## Technical Constraints

- **API Rate Limits:**
    - **`FinancialDatasets.ai`:** This is the primary focus for the `graceful-rate-limiting` branch.
        - When rate limited, it returns an HTTP `429` status code.
        - The response body is JSON, e.g., `{"detail":"Request was throttled. Expected available in 12 seconds."}`. The number of seconds to wait can be parsed from this message.
        - Current implementation in `src/tools/api.py` raises an exception immediately upon receiving a non-200 status code, including 429, leading to abrupt termination of processes.
    - **LLM APIs (OpenAI, Groq, etc.):** Currently not a concern for rate limiting in this task.
- **API Key Requirements:** At least one LLM API key (OpenAI, Groq, Anthropic, or Deepseek) must be set for the hedge fund to work. `FINANCIAL_DATASETS_API_KEY` is needed for most tickers.
- **Local LLM Performance:** Using Ollama for local LLMs might have performance implications depending on the user's hardware.

## Key Dependencies

- **External Services/APIs:**
    - OpenAI API (for LLMs like GPT-4o)
    - Groq API (for LLMs like Llama3)
    - FinancialDatasets.ai API (for financial data)
    - Anthropic API (mentioned as important for its LLMs)
    - Deepseek API (mentioned as important for its LLMs)
    - Ollama (for local LLM hosting)
- **Python Libraries (from `pyproject.toml`):**
    - `python: ^3.11`
    - **Langchain Ecosystem:**
        - `langchain: 0.3.0`
        - `langchain-anthropic: 0.3.5`
        - `langchain-groq: 0.2.3`
        - `langchain-openai: ^0.3.5`
        - `langchain-deepseek: ^0.1.2`
        - `langchain-ollama: ^0.2.0`
        - `langchain-google-genai: ^2.0.11`
        - `langgraph: 0.2.56`
    - **Data Handling & Numerics:**
        - `pandas: ^2.1.0`
        - `numpy: ^1.24.0`
    - **Utilities & CLI:**
        - `python-dotenv: 1.0.0` (for `.env` file management)
        - `matplotlib: ^3.9.2` (for plotting, likely in backtester/analysis)
        - `tabulate: ^0.9.0` (for creating tables in output)
        - `colorama: ^0.4.6` (for colored terminal output)
        - `questionary: ^2.1.0` (for interactive CLI prompts)
        - `rich: ^13.9.4` (for rich text and beautiful formatting in the terminal)
    - **Backend (FastAPI - likely for `app/`):**
        - `fastapi: ^0.104.0` (with "standard" extras)
        - `fastapi-cli: ^0.0.7`
        - `pydantic: ^2.4.2`
        - `httpx: ^0.27.0` (HTTP client, could be used for API calls if not solely relying on Langchain's clients)
        - `sqlalchemy: ^2.0.22` (ORM, database interaction)
        - `alembic: ^1.12.0` (database migrations)
- **Node.js Libraries (from `package.json`):**
    - `tailwindcss: ^4.1.5` (dev dependency)
    - `postcss: ^8.5.3` (dev dependency)
    - `autoprefixer: ^10.4.21` (dev dependency)
    - **Note:** These are frontend-specific (CSS tooling) and likely pertain to the `app/frontend/` part of the project. They are not expected to be directly involved in the core Python simulation logic or the API calls that require rate limiting.

## Code Style and Conventions

- **Formatting:**
    - `black` is used for code formatting.
        - `line-length: 420` (Note: This is unusually long; typical is 79, 88, or 120)
        - `target-version: ['py311']`
    - `isort` is used for import sorting, with the `black` profile.
        - `force_alphabetical_sort_within_sections = true`
- **Linting:**
    - `flake8` is used for linting.
- **Development Dependencies:**
    - `pytest: ^7.4.0` (for testing)

**Docker Environment Details (from `Dockerfile`):**
- **Base Image:** `python:3.11-slim`
- **Work Directory:** `/app`
- **PYTHONPATH:** Set to `/app`
- **Poetry Installation:** `poetry==1.7.1` is installed via pip.
- **Poetry Configuration:** Configured *not* to create virtual environments (`poetry config virtualenvs.create false`). Dependencies are installed directly into the system Python site-packages within the image.
- **Dependency Installation:** `poetry install --no-interaction --no-ansi`
- **Source Code:** The entire project directory is copied into `/app/` in the image.
- **Default Command:** `CMD ["python", "src/main.py"]` (though this is noted to be typically overridden by Docker Compose).

**Docker Compose Services (from `docker-compose.yml`):**
- **`ollama` service:**
    - Image: `ollama/ollama:latest`
    - Container Name: `ollama`
    - Environment:
        - `OLLAMA_HOST=0.0.0.0`
        - `METAL_DEVICE=on` (for Apple Silicon GPU acceleration)
        - `METAL_DEVICE_INDEX=0`
    - Volumes: `ollama_data:/root/.ollama` (persistent storage for Ollama models)
    - Ports: Maps host `11434` to container `11434`.
    - Restart Policy: `unless-stopped`
- **`hedge-fund` (and variants like `hedge-fund-reasoning`, `hedge-fund-ollama`):**
    - Builds from the local `Dockerfile`.
    - Image Name: `ai-hedge-fund`
    - Depends on: `ollama` service.
    - Volumes: Mounts local `.env` to `/app/.env` in the container.
    - Commands: Overrides Dockerfile's CMD to run `python src/main.py` with different arguments (e.g., `--ticker`, `--show-reasoning`, `--ollama`).
    - Environment:
        - `PYTHONUNBUFFERED=1`
        - `OLLAMA_BASE_URL=http://ollama:11434` (configures the app to use the `ollama` service)
        - `PYTHONPATH=/app`
    - `tty: true`, `stdin_open: true` (for interactive sessions).
- **`backtester` (and `backtester-ollama` variant):**
    - Similar configuration to `hedge-fund` services but runs `python src/backtester.py`.
- **Named Volume:**
    - `ollama_data`: Used by the `ollama` service for model persistence.

**API Interaction Details:**
-   **`financialdatasets.ai` API:**
    -   Interactions are handled in `src/tools/api.py`.
    -   Uses the `requests` Python library for direct HTTP GET/POST calls.
    -   API key `FINANCIAL_DATASETS_API_KEY` is sourced from environment variables.
    -   Implements a caching layer (`src.data.cache`) to reduce redundant calls.
    -   Functions involved: `get_prices`, `get_financial_metrics`, `search_line_items`, `get_insider_trades`, `get_company_news`, `get_market_cap`.
-   **LLM APIs (OpenAI, Groq, Anthropic, Deepseek, Ollama):**
    -   The `src/tools/api.py` file **does not** manage LLM API calls.
    -   **LLM Call Orchestration:**
        -   LLM interactions are centralized through the `call_llm` function in `src/utils/llm.py`.
        -   This function takes a prompt, model name, provider, Pydantic model for output, and handles retries.
        -   It dynamically gets model instances using the `get_model` function from `src/llm/models.py`.
        -   The `src/llm/models.py` module:
            -   Defines an `LLMModel` Pydantic model and `ModelProvider` enum.
            -   Loads model configurations from `api_models.json` and `ollama_models.json`.
            -   The `get_model` function within `src/llm/models.py` instantiates specific Langchain client objects (e.g., `ChatOpenAI`, `ChatGroq`, `ChatOllama`, `ChatAnthropic`, `ChatDeepSeek`, `ChatGoogleGenerativeAI`) based on the provider, fetching necessary API keys from environment variables.
        -   `call_llm` in `src/utils/llm.py` then uses these instantiated Langchain client objects to make the actual `.invoke()` calls to the LLM APIs.
        -   `call_llm` also supports both models with native JSON mode and those requiring manual JSON extraction from text/markdown responses.
        -   The `llm.invoke(prompt)` line within `src/utils/llm.py` (inside the `call_llm` function) is the most direct point of network interaction with LLM APIs and thus a critical focus for rate limiting.
    -   Individual agents (e.g., `warren_buffett_agent`) prepare prompts and invoke `call_llm` from `src/utils/llm.py`.

## Initial State
- This document was created on 5/25/2025 as part of initializing the Memory Bank for the 'ai-hedge-fund' project.
- This context will be filled in as the project's technical landscape is explored.
- Current development focus: 'graceful-rate-limiting' branch.
