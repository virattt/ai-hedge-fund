# CLAUDE.md - Testing

Test suite for the AI hedge fund system (currently minimal coverage).

## Current Tests

### `test_api_rate_limiting.py`
Tests for API rate limiting functionality to ensure proper throttling of external API calls.

## Test Structure

- **Framework**: pytest (configured in pyproject.toml)
- **Coverage**: Limited to specific functionality testing
- **Focus**: API integration and rate limiting

## Running Tests

```bash
# Run all tests
poetry run pytest tests/

# Run specific test file
poetry run pytest tests/test_api_rate_limiting.py

# Run with verbose output
poetry run pytest tests/ -v

# Run with coverage
poetry run pytest tests/ --cov=src
```

## Test Development Guidelines

### Adding New Tests
1. Create test files following `test_*.py` naming convention
2. Use pytest fixtures for common setup/teardown
3. Mock external API calls to avoid rate limits
4. Test both success and failure scenarios

### Test Categories Needed
- **Agent Testing**: Individual agent decision-making logic
- **Integration Testing**: End-to-end hedge fund execution
- **Data Pipeline Testing**: Financial data fetching and processing
- **LLM Integration Testing**: Model response parsing and error handling
- **Web API Testing**: FastAPI backend endpoint validation

### Mocking Strategy
- Mock external APIs (OpenAI, financial data providers)
- Use fixtures for consistent test data
- Mock LLM responses for deterministic testing
- Mock database operations for unit tests

## Future Test Improvements

The test suite needs expansion in these areas:
- Agent personality testing
- Portfolio management logic
- Risk calculation validation
- Backtesting accuracy
- Error handling and edge cases