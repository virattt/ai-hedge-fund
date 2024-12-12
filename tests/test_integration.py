"""
Integration tests for AI hedge fund system.
Tests the complete workflow with different providers.
"""
import pytest
from unittest.mock import Mock, patch

from src.config import get_model_provider
from src.providers.openai_provider import OpenAIProvider
from src.providers.anthropic_provider import AnthropicProvider
from src.providers.base import ModelProviderError, ProviderQuotaError
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
    provider = OpenAIProvider()
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

def test_workflow_with_anthropic_provider(mock_market_data):
    """Test complete workflow with Anthropic provider."""
    provider = AnthropicProvider()
    workflow = create_test_workflow(provider)

    with patch('src.providers.anthropic_provider.AnthropicProvider.generate_response') as mock_generate:
        mock_generate.side_effect = [
            '{"sentiment_score": 0.7, "confidence": 0.85}',
            '{"risk_level": "low", "position_limit": 2000}',
            '{"action": "buy", "quantity": 1000, "price_limit": 152.0}'
        ]

        result = workflow.run({"market_data": mock_market_data})
        assert validate_workflow_result(result)
        assert "trading_decision" in result
        assert result["risk_level"] == "low"

def test_provider_fallback_mechanism(mock_market_data):
    """Test provider fallback when primary provider fails."""
    primary_provider = AnthropicProvider()
    workflow = create_test_workflow(primary_provider)

    with patch('src.providers.anthropic_provider.AnthropicProvider.generate_response') as mock_primary:
        mock_primary.side_effect = ProviderQuotaError(
            "Quota exceeded",
            provider="anthropic",
            quota_reset_time="2024-03-15T00:00:00Z"
        )

        with patch('src.providers.openai_provider.OpenAIProvider.generate_response') as mock_fallback:
            mock_fallback.return_value = '{"sentiment_score": 0.6, "confidence": 0.8}'

            result = workflow.run({"market_data": mock_market_data})
            assert validate_workflow_result(result)
            mock_fallback.assert_called_once()

def test_workflow_state_transitions():
    """Test state transitions between agents in the workflow."""
    provider = OpenAIProvider()
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

def test_workflow_error_handling():
    """Test error handling in workflow execution."""
    provider = OpenAIProvider()
    workflow = create_test_workflow(provider)

    with patch('src.providers.openai_provider.OpenAIProvider.generate_response') as mock_generate:
        mock_generate.side_effect = ModelProviderError("Test error", provider="openai")

        with pytest.raises(ModelProviderError):
            workflow.run({"market_data": {}})
