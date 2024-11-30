import argparse
from datetime import datetime

from langgraph.graph import END, StateGraph

from ai_hedge_fund.agents.agents import (
    AgentState,
    market_data_agent,
    portfolio_management_agent,
    quant_agent,
    risk_management_agent,
    run_hedge_fund,
)

# Add this at the bottom of the file
if __name__ == "__main__":
    # Define the new workflow
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("market_data_agent", market_data_agent)
    workflow.add_node("quant_agent", quant_agent)
    workflow.add_node("risk_management_agent", risk_management_agent)
    workflow.add_node("portfolio_management_agent", portfolio_management_agent)

    # Define the workflow
    workflow.set_entry_point("market_data_agent")
    workflow.add_edge("market_data_agent", "quant_agent")
    workflow.add_edge("quant_agent", "risk_management_agent")
    workflow.add_edge("risk_management_agent", "portfolio_management_agent")
    workflow.add_edge("portfolio_management_agent", END)

    # Check for the parser
    parser = argparse.ArgumentParser(description="Run the hedge fund trading system")
    parser.add_argument("--ticker", type=str, required=True, help="Stock ticker symbol")
    parser.add_argument(
        "--start-date", type=str, required=True, help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date", type=str, required=True, help="End date (YYYY-MM-DD)"
    )

    args = parser.parse_args()

    # Validate dates
    try:
        datetime.strptime(args.start_date, "%Y-%m-%d")
        datetime.strptime(args.end_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError("Dates must be in YYYY-MM-DD format") from e

    # Sample portfolio - you might want to make this configurable too
    portfolio = {
        "cash": 100000.0,  # $100,000 initial cash
        "stock": 0,  # No initial stock position
    }

    result = run_hedge_fund(
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date,
        portfolio=portfolio,
    )
    print(result)
