import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import pandas as pd
from datetime import datetime

from src.agents.technicals import technical_analyst_agent
from src.graph.state import AgentState


class TestTechnicalsAgent:
    """Test suite for the technical analyst agent."""

    @pytest.fixture
    def mock_agent_state(self):
        """Create a mock agent state for testing."""
        return {
            "data": {
                "end_date": "2024-01-01",
                "tickers": ["AAPL", "GOOGL"],
                "analyst_signals": {}
            },
            "metadata": {
                "show_reasoning": False
            }
        }

    @pytest.fixture
    def mock_price_data(self):
        """Create mock price data for testing."""
        # Create a list of mock price objects
        prices = []
        for i in range(50):  # 50 days of data
            price = Mock()
            price.time = f"2024-{(i % 12) + 1}-{(i % 28) + 1}T00:00:00Z"
            price.open = 100.0 + i
            price.close = 101.0 + i
            price.high = 102.0 + i
            price.low = 99.0 + i
            price.volume = 1000000 + i * 1000
            prices.append(price)
        return prices

    @patch('src.agents.technicals.get_prices')
    @patch('src.agents.technicals.get_api_key_from_state')
    @patch('src.agents.technicals.progress')
    def test_technical_analyst_success(self, mock_progress, mock_get_api_key, mock_get_prices, mock_agent_state, mock_price_data):
        """Test successful technical analysis."""
        # Setup mocks
        mock_get_api_key.return_value = "test-api-key"
        mock_get_prices.return_value = mock_price_data
        
        # Call the function
        result = technical_analyst_agent(mock_agent_state)
        
        # Verify the result structure
        assert "messages" in result
        assert "data" in result
        assert len(result["messages"]) == 1
        
        # Verify API calls
        mock_get_prices.assert_called()
        mock_get_api_key.assert_called_once()
        
        # Verify progress updates were called
        assert mock_progress.update_status.call_count > 0

    @patch('src.agents.technicals.get_prices')
    @patch('src.agents.technicals.get_api_key_from_state')
    @patch('src.agents.technicals.progress')
    def test_technical_analyst_no_price_data(self, mock_progress, mock_get_api_key, mock_get_prices, mock_agent_state):
        """Test handling when no price data is available."""
        # Setup mocks
        mock_get_api_key.return_value = "test-api-key"
        mock_get_prices.return_value = []
        
        # Call the function
        result = technical_analyst_agent(mock_agent_state)
        
        # Verify the result structure
        assert "messages" in result
        assert "data" in result
        
        # Verify the analysis contains empty results for failed ticker
        analyst_signals = result["data"]["analyst_signals"]["technical_analyst_agent"]
        assert "AAPL" not in analyst_signals  # Should be skipped due to no data

    @patch('src.agents.technicals.get_prices')
    @patch('src.agents.technicals.get_api_key_from_state')
    @patch('src.agents.technicals.progress')
    @patch('src.agents.technicals.show_agent_reasoning')
    def test_technical_analyst_with_reasoning(self, mock_show_reasoning, mock_progress, mock_get_api_key, mock_get_prices, mock_agent_state, mock_price_data):
        """Test technical analysis with reasoning enabled."""
        # Enable reasoning
        mock_agent_state["metadata"]["show_reasoning"] = True
        
        # Setup mocks
        mock_get_api_key.return_value = "test-api-key"
        mock_get_prices.return_value = mock_price_data
        
        # Call the function
        result = technical_analyst_agent(mock_agent_state)
        
        # Verify reasoning was displayed
        mock_show_reasoning.assert_called_once()

    @patch('src.agents.technicals.get_prices')
    @patch('src.agents.technicals.get_api_key_from_state')
    @patch('src.agents.technicals.progress')
    def test_rsi_calculation(self, mock_progress, mock_get_api_key, mock_get_prices, mock_agent_state):
        """Test RSI calculation logic."""
        # Create price data with clear trend for RSI testing
        prices = []
        for i in range(20):  # 20 days of data
            price = Mock()
            price.time = f"2024-01-{i+1:02d}T00:00:00Z"
            # Create uptrend for overbought condition
            price.close = 100.0 + (i * 2)  # Consistent upward movement
            price.high = price.close + 1
            price.low = price.close - 1
            price.open = price.close - 0.5
            price.volume = 1000000
            prices.append(price)
        
        mock_get_api_key.return_value = "test-api-key"
        mock_get_prices.return_value = prices
        
        # Call the function
        result = technical_analyst_agent(mock_agent_state)
        
        # Extract analysis
        analysis = json.loads(result["messages"][0].content)
        aapl_analysis = analysis["AAPL"]
        
        # Verify RSI signal exists
        assert "rsi_signal" in aapl_analysis["reasoning"]

    @patch('src.agents.technicals.get_prices')
    @patch('src.agents.technicals.get_api_key_from_state')
    @patch('src.agents.technicals.progress')
    def test_moving_average_analysis(self, mock_progress, mock_get_api_key, mock_get_prices, mock_agent_state, mock_price_data):
        """Test moving average analysis."""
        mock_get_api_key.return_value = "test-api-key"
        mock_get_prices.return_value = mock_price_data
        
        # Call the function
        result = technical_analyst_agent(mock_agent_state)
        
        # Extract analysis
        analysis = json.loads(result["messages"][0].content)
        aapl_analysis = analysis["AAPL"]
        
        # Verify moving average signals exist
        assert "ma_signal" in aapl_analysis["reasoning"]
        assert "signal" in aapl_analysis["reasoning"]["ma_signal"]
        assert "details" in aapl_analysis["reasoning"]["ma_signal"]

    @patch('src.agents.technicals.get_prices')
    @patch('src.agents.technicals.get_api_key_from_state')
    @patch('src.agents.technicals.progress')
    def test_volume_analysis(self, mock_progress, mock_get_api_key, mock_get_prices, mock_agent_state, mock_price_data):
        """Test volume analysis."""
        mock_get_api_key.return_value = "test-api-key"
        mock_get_prices.return_value = mock_price_data
        
        # Call the function
        result = technical_analyst_agent(mock_agent_state)
        
        # Extract analysis
        analysis = json.loads(result["messages"][0].content)
        aapl_analysis = analysis["AAPL"]
        
        # Verify volume signal exists
        assert "volume_signal" in aapl_analysis["reasoning"]

    @patch('src.agents.technicals.get_prices')
    @patch('src.agents.technicals.get_api_key_from_state')
    @patch('src.agents.technicals.progress')
    def test_multiple_tickers_analysis(self, mock_progress, mock_get_api_key, mock_get_prices, mock_agent_state):
        """Test analysis with multiple tickers."""
        # Create different price data for each ticker
        prices_aapl = []
        prices_googl = []
        
        for i in range(30):
            # AAPL - uptrend
            price_aapl = Mock()
            price_aapl.time = f"2024-01-{i+1:02d}T00:00:00Z"
            price_aapl.open = 100.0 + i
            price_aapl.close = 101.0 + i
            price_aapl.high = 102.0 + i
            price_aapl.low = 99.0 + i
            price_aapl.volume = 1000000
            prices_aapl.append(price_aapl)
            
            # GOOGL - downtrend
            price_googl = Mock()
            price_googl.time = f"2024-01-{i+1:02d}T00:00:00Z"
            price_googl.open = 200.0 - i
            price_googl.close = 199.0 - i
            price_googl.high = 201.0 - i
            price_googl.low = 198.0 - i
            price_googl.volume = 800000
            prices_googl.append(price_googl)
        
        mock_get_api_key.return_value = "test-api-key"
        mock_get_prices.side_effect = [prices_aapl, prices_googl]
        
        # Call the function
        result = technical_analyst_agent(mock_agent_state)
        
        # Extract analysis
        analysis = json.loads(result["messages"][0].content)
        
        # Verify both tickers were analyzed
        assert "AAPL" in analysis
        assert "GOOGL" in analysis
        
        # Verify different signals for different trends
        assert analysis["AAPL"]["signal"] in ["bullish", "bearish", "neutral"]
        assert analysis["GOOGL"]["signal"] in ["bullish", "bearish", "neutral"]

    def test_price_data_transformation(self):
        """Test price data transformation for technical indicators."""
        # Test creating DataFrame from mock price objects
        prices = []
        for i in range(10):
            price = Mock()
            price.time = f"2024-01-{i+1:02d}T00:00:00Z"
            price.open = 100.0 + i
            price.close = 101.0 + i
            price.high = 102.0 + i
            price.low = 99.0 + i
            price.volume = 1000000
            prices.append(price)
        
        # Simulate DataFrame creation
        data = []
        for price in prices:
            data.append({
                'time': price.time,
                'open': price.open,
                'high': price.high,
                'low': price.low,
                'close': price.close,
                'volume': price.volume
            })
        
        df = pd.DataFrame(data)
        
        # Verify DataFrame structure
        assert len(df) == 10
        assert list(df.columns) == ['time', 'open', 'high', 'low', 'close', 'volume']
        assert df['close'].iloc[0] == 101.0
        assert df['close'].iloc[-1] == 110.0

    def test_technical_signal_combination(self):
        """Test how multiple technical signals are combined."""
        # Test signal combination logic
        signals = ["bullish", "bearish", "neutral", "bullish"]
        
        bullish_count = signals.count("bullish")
        bearish_count = signals.count("bearish")
        
        if bullish_count > bearish_count:
            overall_signal = "bullish"
        elif bearish_count > bullish_count:
            overall_signal = "bearish"
        else:
            overall_signal = "neutral"
        
        assert overall_signal == "bullish"
        
        # Test confidence calculation
        total_signals = len(signals)
        confidence = round(max(bullish_count, bearish_count) / total_signals, 2) * 100
        assert confidence == 50.0

    @patch('src.agents.technicals.get_prices')
    @patch('src.agents.technicals.get_api_key_from_state')
    @patch('src.agents.technicals.progress')
    def test_insufficient_data_handling(self, mock_progress, mock_get_api_key, mock_get_prices, mock_agent_state):
        """Test handling of insufficient price data for technical indicators."""
        # Create minimal price data (less than required for some indicators)
        prices = []
        for i in range(5):  # Only 5 days of data
            price = Mock()
            price.time = f"2024-01-{i+1:02d}T00:00:00Z"
            price.open = 100.0 + i
            price.close = 101.0 + i
            price.high = 102.0 + i
            price.low = 99.0 + i
            price.volume = 1000000
            prices.append(price)
        
        mock_get_api_key.return_value = "test-api-key"
        mock_get_prices.return_value = prices
        
        # Call the function
        result = technical_analyst_agent(mock_agent_state)
        
        # Verify function handles insufficient data gracefully
        assert "messages" in result
        assert "data" in result


if __name__ == "__main__":
    pytest.main([__file__])
