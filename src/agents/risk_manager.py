from langchain_core.messages import HumanMessage
from graph.state import AgentState, show_agent_reasoning
from utils.progress import progress
from tools.api import get_prices, prices_to_df
import json
from llm.models import get_model, get_model_info
import re  # Import the regex module


##### Risk Management Agent #####
def risk_management_agent(state: AgentState):
    """Controls position sizing based on real-world risk factors for multiple tickers using LLM analysis."""
    portfolio = state["data"]["portfolio"]
    data = state["data"]
    tickers = data["tickers"]
    analyst_signals = state["data"]["analyst_signals"]
    model_name = state["metadata"]["model_name"]
    model_provider = state["metadata"]["model_provider"]

    # Get LLM model
    llm = get_model(model_name, model_provider)
    if not llm:
        raise ValueError(f"Failed to initialize LLM model: {model_name} from {model_provider}")
    model_info = get_model_info(model_name)
    if not model_info:
        raise ValueError(f"Could not retrieve model info for: {model_name}")
    is_deepseek_model = model_info.is_deepseek()

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

        if not prices:
            progress.update_status("risk_management_agent", ticker, "Failed: No price data found")
            continue

        prices_df = prices_to_df(prices)

        progress.update_status("risk_management_agent", ticker, "Calculating position limits with LLM")

        # Calculate portfolio value
        current_price = prices_df["close"].iloc[-1]
        current_prices[ticker] = current_price  # Store the current price

        # Calculate current position value for this ticker
        current_position_value = portfolio.get("positions", {}).get(ticker, {}).get("long_cost_basis", 0) # Changed to use portfolio positions

        # Calculate total portfolio value using stored prices - Corrected to use positions for value calculation
        total_portfolio_value = portfolio.get("cash", 0) + sum(portfolio.get("positions", {}).get(t, {}).get("long_cost_basis", 0) for t in portfolio.get("positions", {}))

        # Construct LLM Prompt for risk analysis
        prompt = f"""
        You are a financial risk analyst. Your task is to determine a suitable maximum position size percentage for the stock ticker {ticker}.

        Here is information to consider:
        - Current Portfolio Value: ${total_portfolio_value:,.2f}
        - Current Position Value in {ticker}: ${current_position_value:,.2f}
        - Signals from other analysts: {analyst_signals.get(ticker, {})}

        Analyze the risk factors and suggest a maximum position size percentage for {ticker} as a percentage of the total portfolio value.
        Consider factors like market sentiment, valuation, and any other relevant information.

        Respond with just a number representing the percentage (e.g., "15" for 15%).  Provide a brief 1-2 sentence reasoning for your suggested percentage.
        """
        if is_deepseek_model: # Adjusted prompt for DeepSeek models.
            prompt = f"""
            [INST]You are a financial risk analyst. Your task is to determine a suitable maximum position size percentage for the stock ticker {ticker}.

            Here is information to consider:
            - Current Portfolio Value: ${total_portfolio_value:,.2f}
            - Current Position Value in {ticker}: ${current_position_value:,.2f}
            - Signals from other analysts: {analyst_signals.get(ticker, {})}

            Analyze the risk factors and suggest a maximum position size percentage for {ticker} as a percentage of the total portfolio value.
            Consider factors like market sentiment, valuation, and any other relevant information.

            Respond with just a number representing the percentage (e.g., "15" for 15%).  Provide a brief 1-2 sentence reasoning for your suggested percentage.[/INST]
            """

        # print(f"\n--- LLM Prompt for {ticker} ---")  # Debugging print statement
        # print(prompt)  # Debugging print statement

        llm_response = llm.invoke([HumanMessage(content=prompt)])
        llm_content = llm_response.content

        # print(f"\n--- LLM Response for {ticker} ---")  # Debugging print statement
        # print(llm_content)  # Debugging print statement

        position_limit_percentage = 0.20  # Default value
        llm_reasoning = f"Default position limit of 20% applied due to parsing error." # Default reasoning

        try:
            # Use regex to find the first number (integer or decimal) in the LLM response
            percentage_match = re.search(r"(\d+(\.\d+)?)", llm_content)
            if percentage_match:
                position_limit_percentage_str = percentage_match.group(1) # Get the matched percentage string
                position_limit_percentage = float(position_limit_percentage_str) / 100.0 # Convert to float and divide by 100
                llm_reasoning = llm_content # Capture the full response as reasoning
            else:
                progress.update_status("risk_management_agent", ticker, f"Warning: No percentage found in LLM response. Defaulting to 0.20.")
        except ValueError as e:
            progress.update_status("risk_management_agent", ticker, f"Warning: Error parsing percentage from LLM response. Defaulting to 0.20. Error: {e}")


        # print(f"\n--- Parsed Percentage and Reasoning for {ticker} ---")  # Debugging print statement
        # print(f"Position Limit Percentage: {position_limit_percentage}")  # Debugging print statement
        # print(f"LLM Reasoning: {llm_reasoning}")  # Debugging print statement


        # Calculate position limit based on LLM percentage
        position_limit = total_portfolio_value * position_limit_percentage

        # For existing positions, subtract current position value from limit
        remaining_position_limit = position_limit - current_position_value

        # Ensure we don't exceed available cash
        max_position_size = min(remaining_position_limit, portfolio.get("cash", 0))

        # Calculate percentage of portfolio for max position size
        max_position_size_percent = (max_position_size / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0
        position_limit_percent_display = position_limit_percentage * 100 # For display, multiply by 100


        risk_analysis[ticker] = {
            "remaining_position_limit": float(max_position_size),
            "current_price": float(current_price),
            "max_position_size": float(max_position_size),  # Add max_position_size to top level
            "position_limit": float(position_limit),        # Add position_limit to top level
            "max_position_size_percent": float(max_position_size_percent), # Add percentage
            "position_limit_percent": float(position_limit_percent_display), # Add LLM suggested percentage
            "reasoning": {
                "llm_prompt": prompt,
                "llm_response": llm_content,
                "llm_reasoning": llm_reasoning,
                "suggested_position_limit_percentage": float(position_limit_percentage),
                "portfolio_value": float(total_portfolio_value),
                "current_position": float(current_position_value),
                "position_limit": float(position_limit),
                "remaining_limit": float(remaining_position_limit),
                "available_cash": float(portfolio.get("cash", 0)),
            },
        }

        progress.update_status("risk_management_agent", ticker, "Done")
        # print(f"\n--- risk_analysis for {ticker} ---") # Debugging print statement
        # print(json.dumps(risk_analysis[ticker], indent=2)) # Debugging print statement


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