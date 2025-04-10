# Enhanced State Management

This implementation provides a structured approach to state management using Pydantic models while maintaining compatibility with LangChain's AgentState.

## Key Features

- **Dot Notation Access**: Access nested data with `state.data.portfolio.strategy(0).risk_profile`
- **Type Safety**: Pydantic models provide type validation and autocompletion
- **Backwards Compatibility**: Works with existing LangChain state management
- **Serialization**: Easily convert between structured models and dictionaries

## Directory Structure

- `new_models/`: Pydantic models for portfolio, strategies, and risk profiles
- `new_graph/`: Enhanced state management with LangChain compatibility
- `new_agents/`: Updated agent implementations using the enhanced state

## Usage Example

```python
# Create an enhanced state from a regular AgentState dictionary
enhanced_state = EnhancedAgentState(state)

# Access data with dot notation
portfolio = enhanced_state.data.portfolio
strategy = portfolio.strategy(0)  # Get first strategy
risk_profile = strategy.risk_profile

# Make changes
strategy.risk_profile.expected_delta_move = 0.15

# Convert back to dictionary for LangChain compatibility
updated_state = enhanced_state.to_dict()
```

See `example_usage.py` for a complete working example.

## Benefits

1. **Cleaner Code**: Dot notation is more readable than nested dictionary access
2. **Better IDE Support**: Type hints provide autocompletion and documentation
3. **Validation**: Pydantic validates data types and provides helpful error messages
4. **Extensibility**: Easy to add new fields and models as needed

## Integration with Existing Code

To use this enhanced state management with existing agents:

1. Import the EnhancedAgentState: `from new_graph.state import EnhancedAgentState`
2. Wrap the state at the beginning of your agent: `enhanced_state = EnhancedAgentState(state)`
3. Use dot notation to access data: `enhanced_state.data.portfolio.strategies`
4. Convert back to dictionary before returning: `updated_state = enhanced_state.to_dict()`
