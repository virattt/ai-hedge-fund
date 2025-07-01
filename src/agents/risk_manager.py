from langchain_core.messages import HumanMessage
from src.graph.state import AgentState, show_agent_reasoning
from src.utils.progress import progress
from src.tools.api import get_prices, prices_to_df
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

    # First, fetch prices for all relevant tickers
    all_tickers = set(tickers) | set(portfolio.get("positions", {}).keys())
    
    for ticker in all_tickers:
        progress.update_status("risk_management_agent", ticker, "Fetching price data")
        
        prices = get_prices(
            ticker=ticker,
            start_date=data["start_date"],
            end_date=data["end_date"],
        )

        if not prices:
            progress.update_status("risk_management_agent", ticker, "Warning: No price data found")
            continue

        prices_df = prices_to_df(prices)
        
        if not prices_df.empty:
            current_price = prices_df["close"].iloc[-1]
            current_prices[ticker] = current_price
            progress.update_status("risk_management_agent", ticker, f"Current price: {current_price}")
        else:
            progress.update_status("risk_management_agent", ticker, "Warning: Empty price data")

    # Calculate total portfolio value based on current market prices (Net Liquidation Value)
    total_portfolio_value = portfolio.get("cash", 0.0)
    
    for ticker, position in portfolio.get("positions", {}).items():
        if ticker in current_prices:
            # Add market value of long positions
            total_portfolio_value += position.get("long", 0) * current_prices[ticker]
            # Subtract market value of short positions
            total_portfolio_value -= position.get("short", 0) * current_prices[ticker]
    
    progress.update_status("risk_management_agent", None, f"Total portfolio value: {total_portfolio_value}")

    # Calculate risk limits for each ticker in the universe
    for ticker in tickers:
        progress.update_status("risk_management_agent", ticker, "Calculating position limits")
        
        if ticker not in current_prices:
            progress.update_status("risk_management_agent", ticker, "Failed: No price data available")
            risk_analysis[ticker] = {
                "remaining_position_limit": 0.0,
                "current_price": 0.0,
                "reasoning": {
                    "error": "Missing price data for risk calculation"
                }
            }
            continue
            
        current_price = current_prices[ticker]
        
        # Calculate current market value of this position
        position = portfolio.get("positions", {}).get(ticker, {})
        long_value = position.get("long", 0) * current_price
        short_value = position.get("short", 0) * current_price
        current_position_value = abs(long_value - short_value)  # Use absolute exposure
        
        # Calculate position limit (20% of total portfolio)
        position_limit = total_portfolio_value * 0.20
        
        # Calculate remaining limit for this position
        remaining_position_limit = position_limit - current_position_value
        
        # Ensure we don't exceed available cash
        max_position_size = min(remaining_position_limit, portfolio.get("cash", 0))
        
        risk_analysis[ticker] = {
            "remaining_position_limit": float(max_position_size),
            "current_price": float(current_price),
            "reasoning": {
                "portfolio_value": float(total_portfolio_value),
                "current_position_value": float(current_position_value),
                "position_limit": float(position_limit),
                "remaining_limit": float(remaining_position_limit),
                "available_cash": float(portfolio.get("cash", 0)),
            },
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
