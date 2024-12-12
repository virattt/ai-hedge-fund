"""
Integration tests for AI hedge fund system.
Tests the complete workflow with multiple providers.
"""
from typing import Dict, Any, TypedDict, Optional, Callable
import pytest
from unittest.mock import Mock, patch
import json

from src.providers.base import (
    ModelProviderError,
    ProviderQuotaError,
    ProviderConnectionError
)
from src.providers.openai_provider import OpenAIProvider
from src.providers.anthropic_provider import AnthropicProvider
from langgraph.graph import StateGraph

class WorkflowState(TypedDict):
    """Type definition for workflow state."""
    market_data: Dict[str, Any]
    sentiment_analysis: Optional[Dict[str, Any]]
    risk_assessment: Optional[Dict[str, Any]]
    trading_decision: Optional[Dict[str, Any]]

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    with patch('src.providers.openai_provider.ChatOpenAI') as mock:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps({
            "sentiment": "positive",
            "confidence": 0.8,
            "analysis": "Strong buy signals detected"
        })
        mock_client.invoke.return_value = mock_response
        mock.return_value = mock_client
        yield mock_client

@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing."""
    with patch('src.providers.anthropic_provider.ChatAnthropicMessages') as mock:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps({
            "sentiment": "positive",
            "confidence": 0.8,
            "analysis": "Strong buy signals detected"
        })
        mock_client.invoke.return_value = mock_response
        mock.return_value = mock_client
        yield mock_client

def create_test_workflow(provider: Any) -> Callable:
    """Create a test workflow with the specified provider."""
    from src.agents.specialized import (
        SentimentAgent,
        RiskManagementAgent,
        PortfolioManagementAgent
    )

    def sentiment_node(state: WorkflowState) -> WorkflowState:
        """Process sentiment analysis."""
        agent = SentimentAgent(provider)
        return agent.analyze_sentiment(state)

    def risk_node(state: WorkflowState) -> WorkflowState:
        """Process risk assessment."""
        if "error" in state:
            return state
        agent = RiskManagementAgent(provider)
        return agent.evaluate_risk(state)

    def portfolio_node(state: WorkflowState) -> WorkflowState:
        """Process portfolio decisions."""
        if "error" in state:
            return state
        agent = PortfolioManagementAgent(provider)
        return agent.make_decision(state)

    # Create workflow graph
    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("sentiment", sentiment_node)
    workflow.add_node("risk", risk_node)
    workflow.add_node("portfolio", portfolio_node)

    # Add edges
    workflow.add_edge("sentiment", "risk")
    workflow.add_edge("risk", "portfolio")

    # Set entry and exit
    workflow.set_entry_point("sentiment")
    workflow.set_finish_point("portfolio")

    return workflow.compile()

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

@pytest.mark.parametrize("provider_config", [
    (OpenAIProvider, "gpt-4", "mock_openai_client", {"model_name": "gpt-4"}),
    (AnthropicProvider, "claude-3-opus-20240229", "mock_anthropic_client", {
        "model_name": "claude-3-opus-20240229",
        "settings": {"temperature": 0.7, "max_tokens": 4096}
    })
])
def test_workflow_execution(provider_config, mock_openai_client, mock_anthropic_client, mock_market_data, request):
    """Test complete workflow with different providers."""
    ProviderClass, model, mock_fixture, provider_args = provider_config
    mock_client = request.getfixturevalue(mock_fixture)

    provider = ProviderClass(**provider_args)
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
        assert result["sentiment_analysis"]["sentiment_score"] == 0.8
        assert result["risk_assessment"]["risk_level"] == "moderate"
        assert result["trading_decision"]["action"] == "buy"
    except Exception as e:
        pytest.fail(f"Workflow execution failed with {provider.__class__.__name__}: {str(e)}")

@pytest.mark.parametrize("provider_config", [
    (OpenAIProvider, "gpt-4", "mock_openai_client", {"model_name": "gpt-4"}),
    (AnthropicProvider, "claude-3-opus-20240229", "mock_anthropic_client", {
        "model_name": "claude-3-opus-20240229",
        "settings": {"temperature": 0.7, "max_tokens": 4096}
    })
])
def test_workflow_error_handling(provider_config, mock_openai_client, mock_anthropic_client, mock_market_data, request):
    """Test error handling in workflow execution with different providers."""
    ProviderClass, model, mock_fixture, provider_args = provider_config
    mock_client = request.getfixturevalue(mock_fixture)

    provider = ProviderClass(**provider_args)
    app = create_test_workflow(provider)

    # Initialize workflow state
    initial_state = WorkflowState(
        market_data=mock_market_data,
        sentiment_analysis=None,
        risk_assessment=None,
        trading_decision=None
    )

    # Simulate API error
    error_msg = "API Error"
    if ProviderClass == OpenAIProvider:
        mock_openai_client.chat.completions.create.side_effect = Exception(error_msg)
    else:
        mock_client.invoke.side_effect = Exception(error_msg)

    # Execute workflow and verify error handling
    result = app.invoke(initial_state)
    assert result is not None

    # Verify error state propagation in sentiment analysis
    assert "Error analyzing sentiment" in str(result["sentiment_analysis"]["reasoning"])
    assert result["sentiment_analysis"]["confidence"] == 0
    assert result["sentiment_analysis"]["sentiment_score"] == 0

    # Verify error propagation to risk assessment
    assert "Error evaluating risk" in str(result["risk_assessment"]["reasoning"])
    assert result["risk_assessment"]["risk_level"] == "high"
    assert result["risk_assessment"]["position_limit"] == 0

    # Verify error propagation to trading decision
    assert "Error making decision" in str(result["trading_decision"]["reasoning"])
    assert result["trading_decision"]["action"] == "hold"
    assert result["trading_decision"]["quantity"] == 0

@pytest.mark.parametrize("provider_config", [
    (OpenAIProvider, "gpt-4", "mock_openai_client", {"model_name": "gpt-4"}),
    (AnthropicProvider, "claude-3-opus-20240229", "mock_anthropic_client", {
        "model_name": "claude-3-opus-20240229",
        "settings": {"temperature": 0.7, "max_tokens": 4096}
    })
])
def test_workflow_state_transitions(provider_config, mock_openai_client, mock_anthropic_client, request):
    """Test state transitions between agents with different providers."""
    ProviderClass, model, mock_fixture, provider_args = provider_config
    mock_client = request.getfixturevalue(mock_fixture)

    # Set up mock responses
    sentiment_response = {
        "sentiment_score": 0.8,
        "confidence": 0.8,
        "reasoning": "Strong buy signals detected"
    }
    risk_response = {
        "risk_level": "moderate",
        "position_limit": 1000,
        "reasoning": "Moderate risk based on market conditions"
    }
    trading_response = {
        "action": "buy",
        "quantity": 500,
        "reasoning": "Strong buy recommendation based on signals"
    }

    if ProviderClass == OpenAIProvider:
        mock_openai_client.chat.completions.create.side_effect = [
            Mock(choices=[Mock(message=Mock(content=json.dumps(sentiment_response)))]),
            Mock(choices=[Mock(message=Mock(content=json.dumps(risk_response)))]),
            Mock(choices=[Mock(message=Mock(content=json.dumps(trading_response)))])
        ]
    else:
        mock_client.invoke.side_effect = [
            Mock(content=json.dumps(sentiment_response)),
            Mock(content=json.dumps(risk_response)),
            Mock(content=json.dumps(trading_response))
        ]

    provider = ProviderClass(**provider_args)
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

    # Verify sentiment analysis
    assert result["sentiment_analysis"]["sentiment_score"] == 0.8
    assert result["sentiment_analysis"]["confidence"] == 0.8

    # Verify risk assessment
    assert result["risk_assessment"]["risk_level"] == "moderate"
    assert result["risk_assessment"]["position_limit"] == 1000

    # Verify trading decision
    assert result["trading_decision"]["action"] == "buy"
    assert result["trading_decision"]["quantity"] == 500
