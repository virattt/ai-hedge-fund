# CLAUDE.md - CLI Source Code

This directory contains the command-line interface implementation for the AI hedge fund.

## Entry Points

- `main.py`: Primary CLI entry point for hedge fund execution
- `backtester.py`: Backtesting system with historical performance analysis

## Key Directories

### `agents/`
Investment personality implementations - each agent follows the same interface:
- Input: Market data, portfolio state, analyst recommendations
- Output: Investment decision with reasoning
- Pattern: All agents inherit common structure but have unique investment philosophies

**Agent Categories:**
- **Legendary Investors**: `warren_buffett.py`, `charlie_munger.py`, `peter_lynch.py`, etc.
- **Analysis Specialists**: `fundamentals.py`, `sentiment.py`, `technicals.py`, `valuation.py` 
- **Decision Makers**: `portfolio_manager.py`, `risk_manager.py`

### `graph/`
LangGraph state management:
- `state.py`: Defines `AgentState` class with portfolio, decisions, and agent communications

### `llm/`
Language model integrations:
- `models.py`: Multi-provider LLM configuration and model selection
- `api_models.json`: API-based model definitions (OpenAI, Anthropic, etc.)
- `ollama_models.json`: Local model definitions

### `tools/`
Financial data fetching and market analysis utilities

### `utils/`
- `analysts.py`: Agent orchestration and execution order
- `display.py`: CLI output formatting and visualization 
- `ollama.py`: Local model management and setup
- `progress.py`: Progress tracking for long-running operations
- `llm.py`: LLM client abstractions

## Development Workflow

### Adding New Agents
1. Create new file in `agents/` following existing patterns
2. Implement required methods: analysis, decision-making, reasoning
3. Register in `utils/analysts.py` `ANALYST_ORDER`
4. Test with: `poetry run python src/main.py --ticker TEST`

### Agent Interface Pattern
```python
def create_agent_node(llm, tools):
    # Agent prompt and reasoning logic
    return agent

# Integration with LangGraph workflow
```

### Running and Testing
```bash
# Run single ticker analysis
poetry run python src/main.py --ticker AAPL

# Test with multiple agents
poetry run python src/main.py --ticker AAPL,MSFT,NVDA

# Backtesting 
poetry run python src/backtester.py --ticker AAPL --start-date 2024-01-01

# Use local models
poetry run python src/main.py --ticker AAPL --ollama
```

### Code Style
- Follow Black formatting (420 char line length)
- Agent prompt engineering in docstrings
- State management through `AgentState` class
- Tool integration via LangGraph patterns