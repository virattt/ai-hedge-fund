from langchain_core.messages import HumanMessage
from graph.state import AgentState, show_agent_reasoning
from utils.progress import progress
from tools.api import get_prices, prices_to_df
import json


##### Risk Management Agent #####
def risk_management_agent(state: AgentState):
    """Controls position sizing based on real-world risk factors for multiple tickers."""
    portfolio = state["data"]["portfolio"]
    data = state["data"]
    tickers = data["tickers"]
    
    # Initialize risk analysis for each ticker
    risk_analysis = {}
    current_prices = {}  # Store prices here to avoid redundant API calls
    
    for ticker in tickers:
        progress.update_status("risk_management_agent", ticker, "Analyzing price data")
        
        prices = get_prices(
            ticker=ticker,
            start_date=data["start_date"],
            end_date=data["end_date"],
        )
        prices_df = prices_to_df(prices)
        
        progress.update_status("risk_management_agent", ticker, "Calculating position limits")
        
        # Calculate portfolio value
        current_price = prices_df["close"].iloc[-1]
        current_stock_value = portfolio["positions"][ticker] * current_price
        current_prices[ticker] = current_price  # Store the current price
        
        # Calculate total portfolio value using stored prices
        total_portfolio_value = portfolio["cash"] + sum(
            portfolio["positions"][t] * current_prices[t]
            for t in portfolio["positions"]
            if t in current_prices  # Only use prices we've already fetched
        )

        # 1. Liquidity Check
        avg_daily_volume = prices_df["volume"].mean()
        daily_dollar_volume = avg_daily_volume * current_price
        
        # Don't take more than 10% of average daily volume
        liquidity_limit = daily_dollar_volume * 0.10
        
        # 2. Position Size Limits
        # Base limit is 20% of portfolio for any single position
        base_position_limit = total_portfolio_value * 0.20
        
        # Final position size is the minimum of our limits
        max_position_size = min(liquidity_limit, base_position_limit)
        
        risk_analysis[ticker] = {
            "max_position_size": float(max_position_size),
            "reasoning": {
                "daily_volume": float(daily_dollar_volume),
                "portfolio_value": float(total_portfolio_value),
                "current_position": float(current_stock_value),
            }
        }
        
        progress.update_status("risk_management_agent", ticker, "Done")

    message = HumanMessage(
        content=json.dumps(risk_analysis),
        name="risk_management_agent",
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(risk_analysis, "Risk Management Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["risk_management_agent"] = risk_analysis

    return {
        "messages": state["messages"] + [message],
        "data": data,
    }
