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
    current_prices_map = {}  # Store current prices for all relevant tickers

    # Step 1: Pre-fetch current prices for all tickers in the universe and in portfolio
    all_relevant_tickers = set(tickers) | set(portfolio.get("positions", {}).keys())
    for ticker_symbol in all_relevant_tickers:
        progress.update_status("risk_management_agent", ticker_symbol, "Fetching current price")
        # Fetch only the most recent price, effectively the end_date for this context
        # Assuming get_prices can fetch a single day if start_date and end_date are the same or close.
        # For simplicity, using data["end_date"] to get the latest known price.
        price_data_list = get_prices(
            ticker=ticker_symbol,
            start_date=data["end_date"], # Fetch for the "current" day
            end_date=data["end_date"],
        )
        if price_data_list:
            # Assuming the list is sorted or the last entry is the most recent if multiple are returned for a single day query
            current_prices_map[ticker_symbol] = price_data_list[-1].close 
        else:
            progress.update_status("risk_management_agent", ticker_symbol, "Warning: No current price data found")
            # Consider how to handle missing prices; for now, these tickers won't contribute to market value if missing

    # Step 2: Calculate Net Liquidation Value (NLV)
    progress.update_status("risk_management_agent", None, "Calculating Net Liquidation Value")
    total_portfolio_value = portfolio.get("cash", 0.0)

    for ticker_symbol, position_details in portfolio.get("positions", {}).items():
        market_price = current_prices_map.get(ticker_symbol)
        if market_price is not None:
            long_shares = position_details.get("long", 0)
            short_shares = position_details.get("short", 0)
            total_portfolio_value += long_shares * market_price
            total_portfolio_value -= short_shares * market_price # Subtract market value of short positions
        else:
            # If price is missing for a held ticker, its market value contribution is skipped.
            # Alternative: could use cost basis, but NLV usually requires market prices.
            progress.update_status("risk_management_agent", ticker_symbol, f"Warning: Price unavailable for held ticker {ticker_symbol}, not included in NLV market value calculation.")


    # Step 3: Calculate position limits for each ticker in the trading universe
    progress.update_status("risk_management_agent", None, "Calculating position limits per ticker")
    for ticker in tickers: # Iterate through the universe of tickers for this run
        current_price = current_prices_map.get(ticker)
        if current_price is None:
            progress.update_status("risk_management_agent", ticker, "Failed: No current price data, cannot calculate limits.")
            risk_analysis[ticker] = { # Provide a default/error state for this ticker
                "remaining_position_limit": 0.0,
                "current_price": 0.0,
                "reasoning": {
                    "portfolio_value": float(total_portfolio_value),
                    "error": "Missing current price for ticker, limits cannot be determined."
                }
            }
            continue

        # Calculate current market value of existing position for this specific ticker
        existing_position_details = portfolio.get("positions", {}).get(ticker, {})
        long_value = existing_position_details.get("long", 0) * current_price
        short_value = existing_position_details.get("short", 0) * current_price
        # For position limit calculations, often the gross market value of the specific position is considered.
        # Or, more simply, how much more of this specific ticker can be added.
        # Let's use the absolute value for "current_position_value_for_limit_calc"
        current_position_value_for_limit_calc = abs(long_value - short_value)


        # Base limit is 20% of total_portfolio_value for any single position (absolute exposure)
        single_ticker_max_exposure = total_portfolio_value * 0.20

        # How much more exposure can be added to this ticker
        remaining_exposure_allowance = single_ticker_max_exposure - current_position_value_for_limit_calc
        
        # Convert this remaining exposure allowance to a cash amount for new positions
        # This is the cash value that can be used to establish or increase a position.
        cash_for_new_position = max(0, remaining_exposure_allowance)

        # Ensure this doesn't exceed available cash for new buys/shorts (considering margin for shorts)
        # This part can be complex depending on how margin is handled for new short positions.
        # For simplicity, let's assume for long positions, it's capped by available cash.
        # And for short positions, it's also notionally capped by this amount before margin considerations.
        max_cash_for_ticker_position = min(cash_for_new_position, portfolio.get("cash", 0.0))


        risk_analysis[ticker] = {
            "remaining_position_limit": float(max_cash_for_ticker_position), # This is the cash value limit for new trades on this ticker
            "current_price": float(current_price),
            "reasoning": {
                "total_portfolio_nlv": float(total_portfolio_value),
                "single_ticker_max_exposure_pct": 0.20,
                "single_ticker_max_exposure_value": float(single_ticker_max_exposure),
                "current_ticker_market_value": float(current_position_value_for_limit_calc),
                "remaining_exposure_allowance_for_ticker": float(remaining_exposure_allowance),
                "cash_available_for_new_trades_on_ticker": float(max_cash_for_ticker_position),
                "total_portfolio_cash": float(portfolio.get("cash", 0.0)),
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
