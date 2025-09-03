# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered hedge fund system that uses multiple agent personalities (famous investors like Warren Buffett, Charlie Munger, etc.) to make trading decisions. The system is educational only and doesn't execute real trades.

## Architecture

### Core Components

1. **CLI Tool (`src/`)**: Python-based command line interface for running the hedge fund
   - `main.py`: Entry point for hedge fund execution and backtesting
   - `backtester.py`: Backtesting functionality
   - `agents/`: 18 different investment agent personalities (Buffett, Munger, Damodaran, etc.)
   - `graph/`: LangGraph state management and workflow orchestration
   - `tools/`: Financial data fetching and analysis utilities
   - `llm/`: Language model integrations (OpenAI, Groq, Anthropic, Ollama, etc.)

2. **Web Application (`app/`)**: Full-stack web interface
   - `backend/`: FastAPI server with REST endpoints
   - `frontend/`: React/Vite application with modern UI components

### Agent System Architecture

The system uses a multi-agent approach with:
- **Investment Personalities**: 12 famous investor agents (Buffett, Munger, Lynch, etc.)
- **Analysis Agents**: Valuation, Sentiment, Fundamentals, Technicals
- **Decision Agents**: Risk Manager, Portfolio Manager
- **State Management**: LangGraph orchestrates agent workflow and state

## Development Commands

### CLI Development
```bash
# Install dependencies (Windows: using direct pip --user instead of Poetry virtual env)
python -m pip install --user numpy pandas matplotlib langchain langchain-openai
python -m pip install --user python-dotenv tabulate rich questionary langgraph langchain-anthropic langchain-groq
python -m pip install --user langchain-deepseek langchain-xai langchain-google-genai langchain-ollama langchain-gigachat

# Run hedge fund analysis (working command)
python -m src.main --ticker AAPL,MSFT,NVDA

# Run with local Ollama models  
python -m src.main --ticker AAPL,MSFT,NVDA --ollama

# Run backtester
python -m src.backtester --ticker AAPL,MSFT,NVDA

# Run with date range
python -m src.main --ticker AAPL --start-date 2024-01-01 --end-date 2024-03-01

# Code formatting and linting
python -m black src/ tests/ --line-length 420
python -m isort src/ tests/ --profile black
python -m flake8 src/ tests/

# Run tests
python -m pytest tests/
```

### Web Application Development
```bash
# Quick start (recommended for non-technical users)
./run.sh        # Mac/Linux
run.bat         # Windows

# Manual backend setup
cd app/backend
poetry run uvicorn main:app --reload

# Manual frontend setup  
cd app/frontend
npm install
npm run dev

# Frontend linting and build
npm run lint
npm run build
```

### Docker Development
```bash
# Run entire stack with Docker
docker-compose up --build

# Individual services
docker-compose up backend
docker-compose up frontend
```

## Code Style and Standards

- **Python**: Black formatting with 420 character line length, isort for imports
- **TypeScript/React**: ESLint with standard React rules, Tailwind CSS for styling
- **File Organization**: Snake_case for Python files, kebab-case for directories
- **Agent Implementation**: Each agent follows the same interface pattern in `agents/`

## Environment Configuration

**Current Working Setup (Windows 11, Git Bash, Non-Admin):**
- **Python**: 3.13.5 (global installation)
- **Poetry**: 2.1.4 (custom directory: `/c/Users/cas3526/dev/tools/poetry/`)
- **MinGW-w64 GCC**: 14.2.0 (portable: `/c/Users/cas3526/dev/tools/mingw64/mingw64/`)
- **Dependencies**: Installed via `pip --user` (global user installation)

Required environment variables in `.env` (✅ WORKING):
- `OPENAI_API_KEY`: For GPT models (✅ configured)
- `GROQ_API_KEY`: For Groq-hosted models (✅ configured) 
- `ANTHROPIC_API_KEY`: For Claude models (optional)
- `FINANCIAL_DATASETS_API_KEY`: For extended financial data (✅ configured)

## Key Implementation Details

### Agent Workflow
1. Multiple investment personality agents analyze stocks simultaneously
2. Analysis agents (valuation, sentiment, fundamentals, technicals) provide data
3. Risk manager calculates position limits and risk metrics
4. Portfolio manager makes final trading decisions
5. All decisions flow through LangGraph state management

### LLM Integration
- Multi-provider support: OpenAI, Groq, Anthropic, Ollama, DeepSeek, xAI
- Model selection configurable via command line or web interface
- Ollama support for local model execution

### Data Pipeline
- Financial data from multiple sources (Financial Datasets API, free tier for major stocks)
- Real-time and historical data processing
- Caching and rate limiting for API efficiency

## Testing Strategy

- Limited test coverage currently (only API rate limiting tests)
- Manual testing via CLI and web interface
- Backtesting framework for strategy validation

## Deployment Notes

- Web app designed for local development/usage
- Docker containerization available
- No production deployment infrastructure (educational project)
- Shell scripts provided for easy setup across platforms

## Windows-Specific Setup Notes

**Current Status: ✅ READY FOR PRODUCTION TESTING**

### Key Learnings from Setup:
1. **Poetry**: Use custom directory installation (`/c/Users/cas3526/dev/tools/poetry/`) to avoid permission issues
2. **Dependencies**: Use `pip --user` installation instead of Poetry virtual environment due to permission constraints
3. **Compiler**: Portable MinGW-w64 GCC installation for package compilation without admin privileges
4. **PATH**: Custom PATH configuration in `~/.bashrc` for persistent tool access

### Known Working Commands:
```bash
# Verify environment
python --version  # Should show: Python 3.13.5
poetry --version  # Should show: Poetry (version 2.1.4)
gcc --version     # Should show: gcc.exe (MinGW-W64... 14.2.0)

# Test basic functionality (WORKING ✅)
python -m src.main --ticker AAPL

# Successful execution shows agent analysis and trading decisions
```

### Troubleshooting:
- If Poetry permission denied: `chmod +x "/c/Users/cas3526/dev/tools/poetry/bin/poetry"`
- If import errors: `python -m pip install --user --upgrade [package-name]`  
- If PATH issues: `source ~/.bashrc`