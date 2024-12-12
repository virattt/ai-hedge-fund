"""
Integration tests for AI hedge fund system.
Tests the complete workflow with OpenAI provider.
"""
import pytest
from unittest.mock import Mock, patch

from src.providers.base import (
    ModelProviderError,
    ProviderQuotaError,
    ProviderConnectionError
)
from src.providers.openai_provider import OpenAIProvider
from langgraph.graph import StateGraph
from typing import Dict, Any

def create_test_workflow(provider: Any) -> StateGraph:
    """Create a test workflow with the specified provider."""
    from src.agents.specialized import (
        SentimentAgent,
        RiskManagementAgent,
        PortfolioManagementAgent
    )

    workflow = StateGraph()

    # Initialize agents with provider
    sentiment_agent = SentimentAgent(provider=provider)
    risk_agent = RiskManagementAgent(provider=provider)
    portfolio_agent = PortfolioManagementAgent(provider=provider)

    # Add nodes to workflow
    workflow.add_node("sentiment", sentiment_agent.analyze_sentiment)
    workflow.add_node("risk", risk_agent.evaluate_risk)
    workflow.add_node("portfolio", portfolio_agent.make_decision)

    # Define edges
    workflow.add_edge("sentiment", "risk")
    workflow.add_edge("risk", "portfolio")

    return workflow

def validate_workflow_result(result: Dict[str, Any]) -> bool:
    """Validate the workflow execution result."""
    required_keys = ["sentiment_score", "risk_level", "trading_decision"]
    return all(key in result for key in required_keys)

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

def test_workflow_with_openai_provider(mock_market_data):
    """Test complete workflow with OpenAI provider."""
    provider = OpenAIProvider(model_name="gpt-4")
    workflow = create_test_workflow(provider)

    with patch('src.providers.openai_provider.OpenAIProvider.generate_response') as mock_generate:
        mock_generate.side_effect = [
            '{"sentiment_score": 0.8, "confidence": 0.9}',
            '{"risk_level": "moderate", "position_limit": 1000}',
            '{"action": "buy", "quantity": 500, "price_limit": 155.0}'
        ]

        result = workflow.run({"market_data": mock_market_data})
        assert validate_workflow_result(result)
        assert "trading_decision" in result
        assert result["risk_level"] == "moderate"

def test_workflow_error_handling(mock_market_data):
    """Test error handling in workflow execution."""
    provider = OpenAIProvider(model_name="gpt-4")
    workflow = create_test_workflow(provider)

    with patch('src.providers.openai_provider.OpenAIProvider.generate_response') as mock_generate:
        mock_generate.side_effect = [
            ProviderQuotaError("Rate limit exceeded", provider="OpenAI"),
            ProviderConnectionError("Connection failed", provider="OpenAI"),
            ModelProviderError("Unknown error", provider="OpenAI")
        ]

        for _ in range(3):
            with pytest.raises((ProviderQuotaError, ProviderConnectionError, ModelProviderError)):
                workflow.run({"market_data": mock_market_data})

def test_workflow_state_transitions():
    """Test state transitions between agents in the workflow."""
    provider = OpenAIProvider(model_name="gpt-4")
    workflow = create_test_workflow(provider)

    # Get workflow nodes and verify transitions
    nodes = workflow.get_nodes()
    assert "sentiment" in nodes
    assert "risk" in nodes
    assert "portfolio" in nodes

    # Verify edge connections
    edges = workflow.get_edges()
    assert ("sentiment", "risk") in edges
    assert ("risk", "portfolio") in edges
