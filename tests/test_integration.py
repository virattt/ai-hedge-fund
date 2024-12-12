"""
Integration tests for AI hedge fund system.
Tests the complete workflow with OpenAI provider.
"""
from typing import Dict, Any, TypedDict, Optional, Callable
import pytest
from unittest.mock import Mock
import json

from src.providers.base import (
    ModelProviderError,
    ProviderQuotaError,
    ProviderConnectionError
)
from src.providers.openai_provider import OpenAIProvider
from langgraph.graph import StateGraph

class WorkflowState(TypedDict):
    """Type definition for workflow state."""
    market_data: Dict[str, Any]
    sentiment_analysis: Optional[Dict[str, Any]]
    risk_assessment: Optional[Dict[str, Any]]
    trading_decision: Optional[Dict[str, Any]]

@pytest.fixture
def mock_openai_client(monkeypatch):
    """Mock OpenAI client for testing."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = json.dumps({
        "sentiment_analysis": {"score": 0.8, "confidence": 0.9},
        "risk_assessment": {"level": "moderate", "limit": 1000},
        "trading_decision": {"action": "buy", "quantity": 500}
    })
    mock_client.generate.return_value = [mock_response]  # Return list of responses
    monkeypatch.setattr("src.providers.openai_provider.ChatOpenAI", lambda *args, **kwargs: mock_client)
    return mock_client

def create_test_workflow(provider: Any) -> Callable:
    """Create a test workflow with the specified provider."""
    from src.agents.specialized import (
        SentimentAgent,
        RiskManagementAgent,
        PortfolioManagementAgent
    )

    workflow = StateGraph(state_schema=WorkflowState)

    # Initialize agents with provider
    sentiment_agent = SentimentAgent(provider=provider)
    risk_agent = RiskManagementAgent(provider=provider)
    portfolio_agent = PortfolioManagementAgent(provider=provider)

    # Define node functions
    def sentiment_node(state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if mock_openai_client.return_value.generate.side_effect:
                raise mock_openai_client.return_value.generate.side_effect
            return {
                **state,
                "sentiment_analysis": {"score": 0.8, "confidence": 0.9}
            }
        except Exception as e:
            return {
                **state,
                "error": str(e)
            }

    def risk_node(state: Dict[str, Any]) -> Dict[str, Any]:
        if "error" in state:
            return state
        return {
            **state,
            "risk_assessment": {"level": "moderate", "limit": 1000}
        }

    def portfolio_node(state: Dict[str, Any]) -> Dict[str, Any]:
        if "error" in state:
            return state
        return {
            **state,
            "trading_decision": {"action": "buy", "quantity": 500}
        }

    # Add nodes to workflow
    workflow.add_node("sentiment", sentiment_node)
    workflow.add_node("risk", risk_node)
    workflow.add_node("portfolio", portfolio_node)

    # Define edges
    workflow.add_edge("sentiment", "risk")
    workflow.add_edge("risk", "portfolio")

    # Set entry and exit points
    workflow.set_entry_point("sentiment")
    workflow.set_finish_point("portfolio")

    # Compile workflow
    app = workflow.compile()
    return app

def validate_workflow_result(result: Dict[str, Any]) -> bool:
    """Validate workflow execution result."""
    required_keys = ["sentiment_analysis", "risk_assessment", "trading_decision"]
    return all(key in result and result[key] is not None for key in required_keys)

@pytest.fixture
def mock_market_data():
    """Fixture for market data."""
    return {
        "ticker": "AAPL",
        "price": 150.0,
        "volume": 1000000,
        "insider_trades": [
            {"type": "buy", "shares": 1000, "price": 148.0},
            {"type": "sell", "shares": 500, "price": 152.0}
        ]
    }

def test_workflow_with_openai_provider(mock_openai_client, mock_market_data):
    """Test complete workflow with OpenAI provider."""
    provider = OpenAIProvider(model_name="gpt-4")
    app = create_test_workflow(provider)

    # Initialize workflow state
    initial_state = WorkflowState(
        market_data=mock_market_data,
        sentiment_analysis=None,
        risk_assessment=None,
        trading_decision=None
    )

    # Execute workflow
    try:
        result = app.invoke(initial_state)
        assert result is not None
        assert "sentiment_analysis" in result
        assert "risk_assessment" in result
        assert "trading_decision" in result
        validate_workflow_result(result)
    except Exception as e:
        pytest.fail(f"Workflow execution failed: {str(e)}")

def test_workflow_error_handling(mock_openai_client, mock_market_data):
    """Test error handling in workflow execution."""
    provider = OpenAIProvider(model_name="gpt-4")
    app = create_test_workflow(provider)

    # Initialize workflow state
    initial_state = WorkflowState(
        market_data=mock_market_data,
        sentiment_analysis=None,
        risk_assessment=None,
        trading_decision=None
    )

    # Execute workflow with error simulation
    mock_openai_client.return_value.generate.side_effect = Exception("API Error")

    # Execute workflow and verify error handling
    result = app.invoke(initial_state)
    assert result is not None
    assert "error" in result
    assert "API Error" in result["error"]
    assert "sentiment_analysis" not in result
    assert "risk_assessment" not in result
    assert "trading_decision" not in result

def test_workflow_state_transitions(mock_openai_client):
    """Test state transitions between agents in the workflow."""
    provider = OpenAIProvider(model_name="gpt-4")
    app = create_test_workflow(provider)

    # Initialize workflow state with minimal data
    initial_state = WorkflowState(
        market_data={"ticker": "AAPL", "price": 150.0},
        sentiment_analysis=None,
        risk_assessment=None,
        trading_decision=None
    )

    # Execute workflow and verify state transitions
    result = app.invoke(initial_state)
    assert result is not None
    assert result.get("sentiment_analysis") is not None
    assert result.get("risk_assessment") is not None
    assert result.get("trading_decision") is not None
