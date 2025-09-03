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
# Install dependencies (✅ ALREADY COMPLETED - requirements.txt installed)
# Complete requirements.txt created with all exact versions
# .venv/Scripts/python.exe -m pip install -r requirements.txt  # DONE

# Or install core packages individually:
.venv/Scripts/python.exe -m pip install numpy pandas matplotlib langchain langgraph
.venv/Scripts/python.exe -m pip install langchain-openai langchain-groq langchain-anthropic
.venv/Scripts/python.exe -m pip install python-dotenv tabulate rich questionary colorama
.venv/Scripts/python.exe -m pip install langchain-deepseek langchain-xai langchain-google-genai langchain-ollama langchain-gigachat

# Run hedge fund analysis (working command)
.venv/Scripts/python.exe -m src.main --ticker AAPL,MSFT,NVDA

# Run with local Ollama models  
.venv/Scripts/python.exe -m src.main --ticker AAPL,MSFT,NVDA --ollama

# Run backtester with CLI arguments (WORKING ✅)
.venv/Scripts/python.exe -m src.backtester --tickers AAPL --start-date 2024-01-01 --end-date 2024-01-15 --analysts-all --initial-capital 10000 --model gpt-4o-mini

# Run backtester with multiple tickers
.venv/Scripts/python.exe -m src.backtester --tickers AAPL,MSFT,NVDA --analysts-all --model gpt-4o-mini

# Run with date range
.venv/Scripts/python.exe -m src.main --ticker AAPL --start-date 2024-01-01 --end-date 2024-03-01

# Code formatting and linting
.venv/Scripts/python.exe -m black src/ tests/ --line-length 420
.venv/Scripts/python.exe -m isort src/ tests/ --profile black
.venv/Scripts/python.exe -m flake8 src/ tests/

# Run tests
.venv/Scripts/python.exe -m pytest tests/
```

### Web Application Development
```bash
# Quick start (recommended for non-technical users)
./run.sh        # Mac/Linux
run.bat         # Windows

# Manual backend setup (✅ Dependencies already installed via requirements.txt)
# IMPORTANT: Run from project root, not app/backend directory
.venv/Scripts/python.exe -m uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000

# If FastAPI/uvicorn missing, install individually:
.venv/Scripts/python.exe -m pip install fastapi==0.104.1
.venv/Scripts/python.exe -m pip install uvicorn[standard]==0.35.0

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
- **Poetry**: ❌ NOT WORKING (permission issues - use pip instead)
- **MinGW-w64 GCC**: 14.2.0 (portable: `/c/Users/cas3526/dev/tools/mingw64/mingw64/`)
- **Dependencies**: Installed in .venv virtual environment using pip directly
- **Requirements.txt**: Complete with 100+ exact versions from poetry.lock analysis

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

**Current Status: ✅ PRODUCTION READY - WEB APP FULLY FUNCTIONAL**

### Key Learnings from Setup:
1. **Poetry**: Use custom directory installation (`/c/Users/cas3526/dev/tools/poetry/`) to avoid permission issues
2. **Dependencies**: Install in Poetry .venv using `.venv/Scripts/python.exe -m pip install` to avoid permission issues
3. **Compiler**: Portable MinGW-w64 GCC installation for package compilation without admin privileges
4. **PATH**: Custom PATH configuration in `~/.bashrc` for persistent tool access
5. **Backtester**: Added `--model` CLI argument to avoid interactive prompts that don't work in Git Bash
6. **Requirements.txt**: Created comprehensive dependency file with exact versions for reproducible builds

### Known Working Commands:
```bash
# Verify environment
python --version  # Should show: Python 3.13.5
poetry --version  # Should show: Poetry (version 2.1.4)  
gcc --version     # Should show: gcc.exe (MinGW-W64... 14.2.0)

# Test dependencies in virtual environment
.venv/Scripts/python.exe -c "from dateutil.relativedelta import relativedelta; import questionary; import colorama; import pandas; import langchain; print('All dependencies working!')"

# Test basic functionality (WORKING ✅)
.venv/Scripts/python.exe -m src.main --ticker AAPL

# Test backtester with full CLI control (WORKING ✅)
.venv/Scripts/python.exe -m src.backtester --tickers AAPL --start-date 2024-01-01 --end-date 2024-01-15 --analysts-all --initial-capital 10000 --model gpt-4o-mini

# Available backtester CLI options:
# --tickers AAPL,MSFT,NVDA
# --start-date YYYY-MM-DD  
# --end-date YYYY-MM-DD
# --analysts-all (or --analysts analyst1,analyst2)
# --initial-capital 50000
# --margin-requirement 0.5
# --model gpt-4o-mini (avoids interactive prompt)
# --ollama (for local models)

# Web Application (WORKING ✅)
# Backend (run from project root):
.venv/Scripts/python.exe -m uvicorn app.backend.main:app --reload --host 127.0.0.1 --port 8000

# Frontend (run from app/frontend/):
cd app/frontend && npm run dev

# Access points:
# - Frontend: http://localhost:5173
# - Backend API: http://localhost:8000  
# - API Docs: http://localhost:8000/docs
```

### Troubleshooting:
- If Poetry permission denied: `chmod +x "/c/Users/cas3526/dev/tools/poetry/bin/poetry"`
- If import errors in .venv: `.venv/Scripts/python.exe -m pip install [package-name]`
- If missing dependencies: `.venv/Scripts/python.exe -m pip install -r requirements.txt`
- If PATH issues: `source ~/.bashrc`
- If backtester interactive prompts fail: Use `--model gpt-4o-mini` and `--analysts-all` arguments
- If financial data API issues: Check `.env` file has valid `FINANCIAL_DATASETS_API_KEY`
- **Web App Specific Issues**:
  - If "No module named 'fastapi'" error: `.venv/Scripts/python.exe -m pip install fastapi==0.104.1 uvicorn[standard]==0.35.0`
  - If backend fails to start: Ensure you're running from project root, not `app/backend/`
  - If "Permission denied" on npm packages: Try `npm audit fix` or delete `node_modules/` and reinstall
  - If ports in use: Kill processes with `taskkill /f /im python.exe` and `taskkill /f /im node.exe` on Windows