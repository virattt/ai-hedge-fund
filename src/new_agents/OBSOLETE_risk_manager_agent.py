from langchain_core.messages import HumanMessage
from new_graph.state import AgentState, EnhancedAgentState, show_agent_reasoning
from utils.progress import progress
from tools.api import get_prices, prices_to_df
import json


##### Risk Management Agent #####
def risk_management_agent(state: AgentState):
    """
    Controls position sizing based on risk parameters and portfolio constraints.
    
    This agent analyzes the risk profile of each strategy in the portfolio and
    determines appropriate position sizes based on risk limits, margin requirements,
    and expected moves.
    """
    # Convert to enhanced state for structured access
    enhanced_state = EnhancedAgentState(state)
    
    # Access data using dot notation
    portfolio = enhanced_state.data.portfolio
    market_conditions = enhanced_state.data.market_conditions
    profile = enhanced_state.data.profile
    
    # Initialize risk analysis dictionary
    risk_analysis = {}
    current_prices = {}  # Store prices to avoid redundant API calls
    
    # Process each strategy in the portfolio
    for i, strategy in enumerate(portfolio.strategies):
        ticker = strategy.ticker
        progress.update_status("risk_management_agent", ticker, "Analyzing risk profile")
        
        # Get price data
        prices = get_prices(
            ticker=ticker,
            start_date=enhanced_state.data.date,  # Use current date as reference
            end_date=enhanced_state.data.date,    # Same day for current prices
        )
        
        if not prices:
            progress.update_status("risk_management_agent", ticker, "Failed: No price data found")
            continue
            
        prices_df = prices_to_df(prices)
        
        # Calculate risk metrics
        progress.update_status("risk_management_agent", ticker, "Calculating position limits")
        
        # Get current price
        current_price = prices_df["close"].iloc[-1]
        current_prices[ticker] = current_price
        
        # Calculate position limits based on risk profile
        max_position_pct = profile.max_size_position
        
        # Adjust position limit based on risk category
        if strategy.risk_profile.risk_category == "defined":
            # For defined risk strategies, we can use full allocation
            position_limit_pct = max_position_pct
        else:
            # For undefined risk, be more conservative unless aggressive style
            if profile.management_style == 3:  # Aggressive
                position_limit_pct = max_position_pct
            elif profile.management_style == 2:  # Moderate
                position_limit_pct = max_position_pct * 0.75
            else:  # Conservative
                position_limit_pct = max_position_pct * 0.5
        
        # Calculate dollar amount for position
        position_limit_amount = portfolio.net_liquidation_value * position_limit_pct
        
        # Ensure we don't exceed available cash
        max_position_size = min(position_limit_amount, portfolio.cash)
        
        # Calculate number of contracts based on margin requirements
        if strategy.risk_profile.margin > 0:
            max_contracts = int(max_position_size / strategy.risk_profile.margin)
        else:
            max_contracts = 0
            
        # Store analysis results
        risk_analysis[ticker] = {
            "max_contracts": max_contracts,
            "current_price": float(current_price),
            "position_limit_amount": float(position_limit_amount),
            "reasoning": {
                "portfolio_value": float(portfolio.net_liquidation_value),
                "position_limit_pct": float(position_limit_pct),
                "available_cash": float(portfolio.cash),
                "risk_category": strategy.risk_profile.risk_category,
                "management_style": profile.management_style,
                "margin_requirement": float(strategy.risk_profile.margin),
            },
        }
        
        progress.update_status("risk_management_agent", ticker, "Done")
    
    # Create message with analysis results
    message = HumanMessage(
        content=json.dumps(risk_analysis),
        name="risk_management_agent",
    )
    
    # Show reasoning if enabled
    if state["metadata"].get("show_reasoning", False):
        show_agent_reasoning(risk_analysis, "Risk Management Agent")
    
    # Update state with risk analysis
    enhanced_state.data.analyst_signals["risk_management_agent"] = risk_analysis
    
    # Convert back to dictionary format for LangChain
    updated_state = enhanced_state.to_dict()
    
    return {
        "messages": updated_state["messages"] + [message],
        "data": updated_state["data"],
        "metadata": updated_state["metadata"],
    }
