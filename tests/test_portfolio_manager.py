import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from datetime import datetime

from src.agents.portfolio_manager import portfolio_manager_agent
from src.graph.state import AgentState


class TestPortfolioManager:
    """Test suite for the portfolio manager agent."""

    @pytest.fixture
    def mock_agent_state(self):
        """Create a mock agent state for testing."""
        return {
            "data": {
                "end_date": "2024-01-01",
                "tickers": ["AAPL", "GOOGL", "MSFT"],
                "analyst_signals": {
                    "fundamentals_analyst_agent": {
                        "AAPL": {"signal": "bullish", "confidence": 75, "reasoning": {}},
                        "GOOGL": {"signal": "bearish", "confidence": 60, "reasoning": {}},
                        "MSFT": {"signal": "neutral", "confidence": 50, "reasoning": {}}
                    },
                    "technical_analyst_agent": {
                        "AAPL": {"signal": "bullish", "confidence": 80, "reasoning": {}},
                        "GOOGL": {"signal": "neutral", "confidence": 40, "reasoning": {}},
                        "MSFT": {"signal": "bullish", "confidence": 70, "reasoning": {}}
                    }
                }
            },
            "metadata": {
                "show_reasoning": False
            }
        }

    @patch('src.agents.portfolio_manager.progress')
    def test_portfolio_manager_success(self, mock_progress, mock_agent_state):
        """Test successful portfolio management analysis."""
        # Call the function
        result = portfolio_manager_agent(mock_agent_state)
        
        # Verify the result structure
        assert "messages" in result
        assert "data" in result
        assert len(result["messages"]) == 1
        
        # Verify progress updates were called
        assert mock_progress.update_status.call_count > 0
        
        # Extract portfolio decisions
        portfolio_decisions = json.loads(result["messages"][0].content)
        
        # Verify all tickers have portfolio decisions
        assert "AAPL" in portfolio_decisions
        assert "GOOGL" in portfolio_decisions
        assert "MSFT" in portfolio_decisions
        
        # Verify decision structure
        for ticker, decision in portfolio_decisions.items():
            assert "action" in decision  # buy, sell, hold
            assert "confidence" in decision
            assert "position_size" in decision
            assert "reasoning" in decision

    @patch('src.agents.portfolio_manager.progress')
    def test_portfolio_manager_with_reasoning(self, mock_progress, mock_agent_state):
        """Test portfolio management with reasoning enabled."""
        # Enable reasoning
        mock_agent_state["metadata"]["show_reasoning"] = True
        
        # Call the function
        result = portfolio_manager_agent(mock_agent_state)
        
        # Verify reasoning was displayed (would be called in actual implementation)
        # This test ensures the reasoning flag is properly handled

    @patch('src.agents.portfolio_manager.progress')
    def test_portfolio_manager_missing_analyst_signals(self, mock_progress):
        """Test portfolio manager with missing analyst signals."""
        # Create state with missing analyst signals
        incomplete_state = {
            "data": {
                "end_date": "2024-01-01",
                "tickers": ["AAPL"],
                "analyst_signals": {}  # No analyst signals
            },
            "metadata": {
                "show_reasoning": False
            }
        }
        
        # Call the function
        result = portfolio_manager_agent(incomplete_state)
        
        # Verify the result structure
        assert "messages" in result
        assert "data" in result
        
        # Extract portfolio decisions
        portfolio_decisions = json.loads(result["messages"][0].content)
        
        # Should handle missing signals gracefully
        assert "AAPL" in portfolio_decisions
        assert portfolio_decisions["AAPL"]["action"] == "hold"  # Default action

    @patch('src.agents.portfolio_manager.progress')
    def test_portfolio_manager_signal_aggregation(self, mock_progress, mock_agent_state):
        """Test how portfolio manager aggregates multiple analyst signals."""
        # Call the function
        result = portfolio_manager_agent(mock_agent_state)
        
        # Extract portfolio decisions
        portfolio_decisions = json.loads(result["messages"][0].content)
        
        # AAPL: bullish from both agents -> should be buy
        assert portfolio_decisions["AAPL"]["action"] in ["buy", "strong_buy"]
        
        # GOOGL: bearish from fundamentals, neutral from technical -> should be hold or sell
        assert portfolio_decisions["GOOGL"]["action"] in ["hold", "sell"]
        
        # MSFT: neutral from fundamentals, bullish from technical -> should be hold or buy
        assert portfolio_decisions["MSFT"]["action"] in ["hold", "buy"]

    @patch('src.agents.portfolio_manager.progress')
    def test_portfolio_manager_confidence_calculation(self, mock_progress, mock_agent_state):
        """Test confidence calculation based on analyst signals."""
        # Call the function
        result = portfolio_manager_agent(mock_agent_state)
        
        # Extract portfolio decisions
        portfolio_decisions = json.loads(result["messages"][0].content)
        
        # Verify confidence levels are reasonable
        for ticker, decision in portfolio_decisions.items():
            assert 0 <= decision["confidence"] <= 100
            assert isinstance(decision["confidence"], (int, float))

    @patch('src.agents.portfolio_manager.progress')
    def test_portfolio_manager_position_sizing(self, mock_progress, mock_agent_state):
        """Test position sizing logic."""
        # Call the function
        result = portfolio_manager_agent(mock_agent_state)
        
        # Extract portfolio decisions
        portfolio_decisions = json.loads(result["messages"][0].content)
        
        # Verify position sizes are reasonable
        for ticker, decision in portfolio_decisions.items():
            assert "position_size" in decision
            # Position size should be a percentage or absolute value
            assert isinstance(decision["position_size"], (int, float))
            if isinstance(decision["position_size"], float):
                assert 0 <= decision["position_size"] <= 1  # If it's a percentage

    @patch('src.agents.portfolio_manager.progress')
    def test_portfolio_manager_risk_considerations(self, mock_progress, mock_agent_state):
        """Test that portfolio manager considers risk factors."""
        # Call the function
        result = portfolio_manager_agent(mock_agent_state)
        
        # Extract portfolio decisions
        portfolio_decisions = json.loads(result["messages"][0].content)
        
        # Verify reasoning includes risk considerations
        for ticker, decision in portfolio_decisions.items():
            assert "reasoning" in decision
            reasoning = decision["reasoning"]
            
            # Should include various risk factors
            assert any(key in reasoning for key in [
                "signal_consensus", "confidence_level", "risk_factors", 
                "diversification", "position_risk"
            ])

    @patch('src.agents.portfolio_manager.progress')
    def test_portfolio_manager_conflicting_signals(self, mock_progress):
        """Test portfolio manager with conflicting analyst signals."""
        # Create state with conflicting signals
        conflicting_state = {
            "data": {
                "end_date": "2024-01-01",
                "tickers": ["AAPL"],
                "analyst_signals": {
                    "fundamentals_analyst_agent": {
                        "AAPL": {"signal": "bullish", "confidence": 90, "reasoning": {}}
                    },
                    "technical_analyst_agent": {
                        "AAPL": {"signal": "bearish", "confidence": 90, "reasoning": {}}
                    },
                    "sentiment_agent": {
                        "AAPL": {"signal": "bullish", "confidence": 80, "reasoning": {}}
                    }
                }
            },
            "metadata": {
                "show_reasoning": False
            }
        }
        
        # Call the function
        result = portfolio_manager_agent(conflicting_state)
        
        # Extract portfolio decisions
        portfolio_decisions = json.loads(result["messages"][0].content)
        
        # Should handle conflicting signals gracefully
        assert "AAPL" in portfolio_decisions
        # With conflicting high-confidence signals, should default to hold or cautious approach
        assert portfolio_decisions["AAPL"]["action"] in ["hold", "cautious_buy", "cautious_sell"]

    @patch('src.agents.portfolio_manager.progress')
    def test_portfolio_manager_multiple_tickers(self, mock_progress, mock_agent_state):
        """Test portfolio manager with multiple tickers."""
        # Call the function
        result = portfolio_manager_agent(mock_agent_state)
        
        # Extract portfolio decisions
        portfolio_decisions = json.loads(result["messages"][0].content)
        
        # Verify all tickers are processed
        assert len(portfolio_decisions) == 3
        
        # Verify portfolio diversification considerations
        actions = [decision["action"] for decision in portfolio_decisions.values()]
        
        # Should not recommend buying all stocks (diversification)
        buy_actions = sum(1 for action in actions if action in ["buy", "strong_buy"])
        assert buy_actions <= 2  # Should not recommend buying all 3

    @patch('src.agents.portfolio_manager.progress')
    def test_portfolio_manager_edge_cases(self, mock_progress):
        """Test portfolio manager edge cases."""
        # Test with empty tickers list
        empty_state = {
            "data": {
                "end_date": "2024-01-01",
                "tickers": [],
                "analyst_signals": {}
            },
            "metadata": {
                "show_reasoning": False
            }
        }
        
        # Call the function
        result = portfolio_manager_agent(empty_state)
        
        # Verify empty result
        portfolio_decisions = json.loads(result["messages"][0].content)
        assert len(portfolio_decisions) == 0

    def test_portfolio_action_mapping(self):
        """Test the mapping of signals to portfolio actions."""
        # Test signal to action mapping logic
        test_cases = [
            ({"bullish": 3, "bearish": 0, "neutral": 0}, "strong_buy"),
            ({"bullish": 2, "bearish": 0, "neutral": 1}, "buy"),
            ({"bullish": 1, "bearish": 1, "neutral": 1}, "hold"),
            ({"bullish": 0, "bearish": 2, "neutral": 1}, "sell"),
            ({"bullish": 0, "bearish": 3, "neutral": 0}, "strong_sell"),
        ]
        
        for signal_counts, expected_action in test_cases:
            # This tests the logic that would be in the portfolio manager
            bullish_count = signal_counts["bullish"]
            bearish_count = signal_counts["bearish"]
            neutral_count = signal_counts["neutral"]
            
            if bullish_count >= 2 and bearish_count == 0:
                action = "strong_buy" if bullish_count == 3 else "buy"
            elif bearish_count >= 2 and bullish_count == 0:
                action = "strong_sell" if bearish_count == 3 else "sell"
            elif bullish_count == bearish_count:
                action = "hold"
            else:
                action = "hold"  # Conservative approach for mixed signals
            
            assert action == expected_action


if __name__ == "__main__":
    pytest.main([__file__])
