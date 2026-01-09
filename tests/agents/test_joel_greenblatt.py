import pytest
from unittest.mock import MagicMock, patch
import sys

# Mock langchain modules BEFORE importing the agent
sys.modules["langchain_anthropic"] = MagicMock()
sys.modules["langchain_deepseek"] = MagicMock()
sys.modules["langchain_google_genai"] = MagicMock()
sys.modules["langchain_groq"] = MagicMock()
sys.modules["langchain_xai"] = MagicMock()
sys.modules["langchain_openai"] = MagicMock()
sys.modules["langchain_gigachat"] = MagicMock()
sys.modules["langchain_ollama"] = MagicMock()

# Now it's safe to import
from src.agents.joel_greenblatt import joel_greenblatt_agent, JoelGreenblattSignal
from src.data.models import FinancialMetrics, LineItem

@pytest.fixture
def mock_agent_state():
    return {
        "data": {
            "tickers": ["AAPL"],
            "end_date": "2023-12-31",
            "analyst_signals": {},
        },
        "metadata": {"show_reasoning": False},
    }

@patch("src.agents.joel_greenblatt.get_financial_metrics")
@patch("src.agents.joel_greenblatt.search_line_items")
@patch("src.agents.joel_greenblatt.get_market_cap")
@patch("src.agents.joel_greenblatt.call_llm")
def test_joel_greenblatt_agent_bullish(
    mock_call_llm, mock_get_market_cap, mock_search_line_items, mock_get_financial_metrics, mock_agent_state
):
    # Mock Financial Metrics (High ROIC)
    mock_metrics = MagicMock(spec=FinancialMetrics)
    mock_metrics.enterprise_value = 100_000_000
    mock_metrics.return_on_invested_capital = 0.30  # 30% ROIC
    mock_get_financial_metrics.return_value = [mock_metrics]

    # Mock Line Items (High EBIT)
    mock_item = MagicMock(spec=LineItem)
    mock_item.operating_income = 15_000_000  # 15M EBIT
    # EV = 100M, so Earnings Yield = 15% (Excellent)
    
    # Capital Components for ROC
    mock_item.total_current_assets = 50_000_000
    mock_item.total_current_liabilities = 20_000_000
    mock_item.property_plant_equipment_net = 10_000_000
    # Net Working Capital = 30M
    # Net Fixed Assets = 10M
    # Invested Capital = 40M
    # ROC = 15M / 40M = 37.5% (Excellent)

    mock_search_line_items.return_value = [mock_item]

    # Mock LLM Response
    mock_signal = JoelGreenblattSignal(signal="bullish", confidence=90.0, reasoning="High ROC and High Yield")
    mock_call_llm.return_value = mock_signal

    # Run Agent
    result = joel_greenblatt_agent(mock_agent_state)

    # Verify Signal
    signals = result["data"]["analyst_signals"]
    assert "joel_greenblatt_agent" in signals
    assert signals["joel_greenblatt_agent"]["AAPL"]["signal"] == "bullish"
    assert signals["joel_greenblatt_agent"]["AAPL"]["confidence"] == 90.0

@patch("src.agents.joel_greenblatt.get_financial_metrics")
@patch("src.agents.joel_greenblatt.search_line_items")
@patch("src.agents.joel_greenblatt.get_market_cap")
@patch("src.agents.joel_greenblatt.call_llm")
def test_joel_greenblatt_agent_bearish(
    mock_call_llm, mock_get_market_cap, mock_search_line_items, mock_get_financial_metrics, mock_agent_state
):
    # Mock Financial Metrics (Low ROIC, Low Yield)
    mock_metrics = MagicMock(spec=FinancialMetrics)
    mock_metrics.enterprise_value = 100_000_000
    mock_metrics.return_on_invested_capital = 0.05
    mock_get_financial_metrics.return_value = [mock_metrics]

    mock_item = MagicMock(spec=LineItem)
    mock_item.operating_income = 1_000_000  # 1M EBIT
    # Earnings Yield = 1% (Low)
    
    # Capital Components for ROC
    mock_item.total_current_assets = 50_000_000
    mock_item.total_current_liabilities = 20_000_000
    mock_item.property_plant_equipment_net = 10_000_000
    # Invested Capital = 40M
    # ROC = 1M / 40M = 2.5% (Low)

    mock_search_line_items.return_value = [mock_item]

    mock_signal = JoelGreenblattSignal(signal="bearish", confidence=80.0, reasoning="Low metrics")
    mock_call_llm.return_value = mock_signal

    result = joel_greenblatt_agent(mock_agent_state)
    
    signals = result["data"]["analyst_signals"]
    assert signals["joel_greenblatt_agent"]["AAPL"]["signal"] == "bearish"
