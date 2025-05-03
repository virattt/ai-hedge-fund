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
  cost_value = {}

  # intitialize total portfolio to cash
  total_portfolio_value = portfolio.get("cash", 0)

  # get all pricing and calculate total portfolio value
  for ticker in tickers:
    progress.update_status("risk_management_agent", ticker, "Portfolio calculation with latest price data")

    prices = get_prices(
      ticker=ticker,
      start_date=data["start_date"],
      end_date=data["end_date"],
    )

    if not prices:
      progress.update_status("risk_management_agent", ticker, "Failed: No price data found")
      continue

    prices_df = prices_to_df(prices)
    progress.update_status("risk_management_agent", ticker, "Calculating position limits")

    # Calculate portfolio value
    current_price = prices_df["close"].iloc[-1]
    current_prices[ticker] = current_price  # Store the current price

    # Calculate current position value for this ticker
    current_position_value = portfolio["positions"][ticker]["long"] * current_prices[ticker]

    cost_value[ticker] = portfolio["positions"][ticker]["long"] * portfolio["positions"][ticker]["long_cost_basis"]

    print("Current position value of ", ticker, " is: ", current_position_value)
    print("Cost basis value of ", ticker, " is: ", cost_value[ticker])

    # Calculate total portfolio value using stored prices
    total_portfolio_value = total_portfolio_value + current_position_value

  print("Total portfolio value is: ", total_portfolio_value)

  for ticker in tickers:
    progress.update_status("risk_management_agent", ticker, "Managing position limits")

    current_position_value = portfolio["positions"][ticker]["long"] * current_prices[ticker]

    # Base limit is 20% of portfolio for any single position
    position_limit = total_portfolio_value * 0.20
    print("Position limit for ", ticker, " is: ", position_limit)

    # For existing positions, subtract current position value from limit
    remaining_position_limit = position_limit - current_position_value
    print("Remaining position limit for ", ticker, " is: ", remaining_position_limit)


    # Ensure we don't exceed available cash
    if remaining_position_limit < 0:
      remaining_position_limit = 0

    max_position_size = min(remaining_position_limit, portfolio.get("cash", 0))

    print("Max position size for ", ticker, " is: ", max_position_size)

    risk_analysis[ticker] = {
      "remaining_position_limit": float(max_position_size),
      "current_price": float(current_price),
      "reasoning": {
        "portfolio_value": float(total_portfolio_value),
        "current_position": float(current_position_value),
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
