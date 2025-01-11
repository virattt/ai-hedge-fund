
from langchain_core.messages import HumanMessage

from graph.state import AgentState, show_agent_reasoning
from tools.api import get_prices, prices_to_df

import json


##### Risk Management Agent #####
def risk_management_agent(state: AgentState):
    """Controls position sizing based on real-world risk factors."""
    portfolio = state["data"]["portfolio"]
    data = state["data"]
    
    prices = get_prices(
        ticker=data["ticker"],
        start_date=data["start_date"],
        end_date=data["end_date"],
    )
    prices_df = prices_to_df(prices)
    
    # Calculate portfolio value
    current_price = prices_df["close"].iloc[-1]
    current_stock_value = portfolio["stock"] * current_price
    total_portfolio_value = portfolio["cash"] + current_stock_value

    # 1. Liquidity Check
    avg_daily_volume = prices_df["volume"].mean()
    daily_dollar_volume = avg_daily_volume * current_price
    
    # Don't take more than 10% of average daily volume
    liquidity_limit = daily_dollar_volume * 0.10
    
    # 2. Position Size Limits
    # Base limit is 20% of portfolio
    base_position_limit = total_portfolio_value * 0.20
    
    # Final position size is the minimum of our limits
    max_position_size = min(liquidity_limit, base_position_limit)
    
    reasoning = (
        f"Position limit set to ${max_position_size:,.2f} based on:\n"
        f"- Daily volume: ${daily_dollar_volume:,.2f}\n"
        f"- Portfolio size: ${total_portfolio_value:,.2f}"
    )

    message_content = {
        "max_position_size": float(max_position_size),
        "reasoning": reasoning,
    }

    message = HumanMessage(
        content=json.dumps(message_content),
        name="risk_management_agent",
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(message_content, "Risk Management Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["risk_management_agent"] = {
        "max_position_size": message_content["max_position_size"],
        "reasoning": reasoning,
    }

    return {
        "messages": state["messages"] + [message],
        "data": data,
    }
