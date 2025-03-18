from langchain_core.messages import HumanMessage
from graph.state import AgentState, show_agent_reasoning
from utils.progress import progress
from tools.api import get_prices, prices_to_df
from tools.alpaca_client import AlpacaClient
from datetime import datetime, timedelta
import json
from colorama import Fore, Style
from llm.models import get_model, ModelProvider


##### Risk Management Agent #####
def risk_management_agent(state):
    """Risk Management Agent"""
    # In LangGraph 0.2.56, state might be a dict instead of AgentState object
    # Handle both cases for compatibility
    if isinstance(state, dict):
        data = state["data"]
        metadata = state["metadata"]
    else:
        data = state.data
        metadata = state.metadata
    
    tickers = data["tickers"]
    portfolio = data["portfolio"]
    signals = data["analyst_signals"]
    model_name = metadata.get("model_name", "gpt-4o")
    model_provider = metadata.get("model_provider", "OpenAI")
    
    # Get current date
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Initialize Alpaca client to get trade history
    try:
        alpaca_client = AlpacaClient()
        # Get trade history for all tickers in our portfolio
        trade_history = alpaca_client.get_trade_history(days_back=30, symbols=tickers)
        # Get trading frequency analysis
        trading_frequency = alpaca_client.get_trading_frequency_analysis(days_back=30)
        
        # Add this data to the state for agents to use
        data["trade_history"] = trade_history
        data["trading_frequency"] = trading_frequency
        data["current_date"] = current_date
        
        # Log that we're including trade history in our analysis
        print(f"Including trade history for risk analysis: {len(trade_history)} tickers with trading history")
        
    except Exception as e:
        print(f"Warning: Could not retrieve Alpaca trade history: {e}")
        # Continue without trade history if there's an error
        data["trade_history"] = {}
        data["trading_frequency"] = {
            "total_trades": 0,
            "avg_trades_per_day": 0,
            "today_trade_count": 0
        }
        data["current_date"] = current_date
    
    # Construct the prompt, including trade history information
    prompt = f"""You are the Risk Management Agent of an AI-powered hedge fund.

Current Date: {current_date}

Portfolio:
{json.dumps(portfolio, indent=2)}

Existing Analyst Signals:
{json.dumps(signals, indent=2)}

## Trade History Analysis
{json.dumps(data['trading_frequency'], indent=2)}

Your goal is to analyze the risk of each position and determine position sizing.
For each stock in the portfolio, assess:

1. Market risk - volatility, correlation to broader market
2. Liquidity risk - how easily the position can be exited
3. Concentration risk - avoid overexposure to any single stock
4. Trading frequency risk - avoid overtrading or excessive turnover
5. Recent trade history - consider recent trades before recommending more action on the same ticker

Rules:
1. Maximum allocation to any single position: 25% of portfolio
2. Minimum cash reserve: 10% of portfolio
3. Maximum daily trades: 5 trades per day 
4. No immediate reversal: Don't buy a stock that was sold in the last 3 days (and vice versa)
5. Consistency check: If we recently bought a stock, don't sell it without significant new information

Decision Parameters:
- Limit new trades on any ticker where we've traded in the last 2 days
- Require stronger signals to trade a ticker that's been recently traded
- Maximum of 3 trades per ticker per week
- Today's trade count: {data['trading_frequency'].get('today_trade_count', 0)}

For each ticker in the portfolio, provide: 
1. An adjusted position size (% of portfolio)
2. A risk score (1-10, where 10 is highest risk)
3. Whether any trading frequency limits have been hit
4. Whether the stock has been recently traded (in last 48 hours)

Respond in JSON format:
{{
  "risk_analysis": {{
    "TICKER1": {{
      "risk_score": 5,
      "max_position_size": 10,
      "trading_frequency_limit_hit": false,
      "recently_traded": false,
      "days_since_last_trade": 5,
      "trade_allowed_today": true,
      "reasoning": "Explanation..."
    }},
    "TICKER2": {{ ... }}
  }}
}}
"""

    # Get reasoning and analysis from LLM
    llm = get_model(model_name, ModelProvider(model_provider))
    messages = [
        HumanMessage(content=prompt)
    ]
    try:
        response = llm.invoke(messages)
        reasoning = response.content
        risk_analysis = parse_llm_response(reasoning)
        signals["risk_management_agent"] = risk_analysis
    except Exception as e:
        print(f"Error in risk management agent: {e}")
        risk_analysis = {"error": str(e)}
        signals["risk_management_agent"] = risk_analysis

    # If show_reasoning is enabled, print it
    if isinstance(state, dict) and metadata.get("show_reasoning", False):
        print(f"\n{Fore.YELLOW}Risk Management Agent Reasoning:{Style.RESET_ALL}")
        print(reasoning)

    # Continue to the next agent
    return state

def parse_llm_response(response_text):
    """Parse JSON from LLM response"""
    try:
        # Try to extract JSON content if it's wrapped in markdown code blocks
        if "```json" in response_text:
            start_idx = response_text.find("```json") + 7
            end_idx = response_text.find("```", start_idx)
            json_str = response_text[start_idx:end_idx].strip()
            return json.loads(json_str)
        # Try to parse the entire response as JSON
        else:
            return json.loads(response_text)
    except Exception as e:
        print(f"Error parsing LLM response: {e}")
        return {"error": "Could not parse response"}
