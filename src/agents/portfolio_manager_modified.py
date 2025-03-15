import json
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai.chat_models import ChatOpenAI

from graph.state import AgentState, show_agent_reasoning
from pydantic import BaseModel, Field
from typing_extensions import Literal
from utils.progress import progress
from utils.llm import call_llm


class PortfolioDecision(BaseModel):
    action: Literal["buy", "sell", "hold"]
    quantity: int = Field(description="Number of shares to trade")
    confidence: float = Field(description="Confidence in the decision, between 0.0 and 100.0")
    reasoning: str = Field(description="Reasoning for the decision")


class PortfolioManagerOutput(BaseModel):
    decisions: dict[str, PortfolioDecision] = Field(description="Dictionary of ticker to trading decisions")


##### Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState):
    """Makes final trading decisions and generates orders for multiple tickers"""

    # Get the portfolio and analyst signals
    portfolio = state["data"]["portfolio"]
    analyst_signals = state["data"]["analyst_signals"]
    tickers = state["data"]["tickers"]

    progress.update_status("portfolio_management_agent", None, "Analyzing signals")

    # Get position limits, current prices, and signals for every ticker
    position_limits = {}
    current_prices = {}
    max_shares = {}
    signals_by_ticker = {}
    for ticker in tickers:
        progress.update_status("portfolio_management_agent", ticker, "Processing analyst signals")

        # Get position limits and current prices for the ticker
        risk_data = analyst_signals.get("risk_management_agent", {}).get(ticker, {})
        position_limits[ticker] = risk_data.get("remaining_position_limit", 0)
        current_prices[ticker] = risk_data.get("current_price", 0)

        # Calculate maximum shares allowed based on position limit and price
        if current_prices[ticker] > 0:
            max_shares[ticker] = int(position_limits[ticker] / current_prices[ticker])
        else:
            max_shares[ticker] = 0

        # Get signals for the ticker
        ticker_signals = {}
        for agent, signals in analyst_signals.items():
            if agent != "risk_management_agent" and ticker in signals:
                ticker_signals[agent] = {"signal": signals[ticker]["signal"], "confidence": signals[ticker]["confidence"]}
        signals_by_ticker[ticker] = ticker_signals

    progress.update_status("portfolio_management_agent", None, "Preparing trading strategy")
    # Create the prompt template
    previous_result = ""
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a portfolio manager making final trading decisions.
                Your job is to make trading decisions based on the team's analysis for multiple tickers.

                Trading Rules:
                - Only buy if you have available cash
                - Only sell if you have shares to sell, otherwise hold
                - For sells: quantity must be ≤ current position shares
                - For buys: quantity must be ≤ max_shares provided for each ticker
                - The max_shares values are pre-calculated to respect position limits
                - When you adding all the buy descitions, they should not exceed the available cash plus the sum of all the sells, this is TOTALLY required. 
                
                Inputs:
                - signals_by_ticker: dictionary of ticker to signals from analysts
                - max_shares: maximum number of shares allowed for each ticker
                - portfolio_cash: current cash in portfolio
                - portfolio_positions: current positions in portfolio
                - portfolio_cost_basis: cost basis for each position that is currently held
                - current_prices: current price for each ticker
                
                Output:
                - action: "buy", "sell", or "hold"
                - quantity: number of shares to trade (integer)
                - confidence: confidence level between 0-100
                - reasoning: brief explanation of the decision""",
            ),
            (
                "human",
                """{previous_result}Based on the team's analysis below, make your trading decisions.

                For each ticker, here are the signals:
                {signals_by_ticker}

                Current Prices:
                {current_prices}

                Maximum Shares Allowed For Any Purchase:
                {max_shares}

                Here is the current portfolio:
                Cash: {portfolio_cash}
                Current Positions: {portfolio_positions}
                Current Cost Basis: {portfolio_cost_basis}

                Return a decision for each ticker in the following format:
                {{
                    "decisions": {{
                        "TICKER1": {{
                            "action": "buy/sell/hold",
                            "quantity": integer,
                            "confidence": float,
                            "reasoning": "string"
                        }},
                        "TICKER2": {{ ... }},
                        ...
                    }}
                }}
                """,
            ),
        ]
    )

    # Generate the prompt
    prompt = template.invoke(
        {
            "previous_result": previous_result,
            "signals_by_ticker": json.dumps(signals_by_ticker, indent=2),
            "current_prices": json.dumps(current_prices, indent=2),
            "max_shares": json.dumps(max_shares, indent=2),
            "portfolio_cash": f"{portfolio['cash']:.2f}",
            "portfolio_positions": json.dumps(portfolio["positions"], indent=2),
            "portfolio_cost_basis": json.dumps(portfolio["cost_basis"], indent=2),
        }
    )

    progress.update_status("portfolio_management_agent", None, "Making trading decisions")

    # new logic for portfolio retrys
    max_retries = 3
    for attempt in range(max_retries):
        result = make_decision(prompt, tickers)
        # Add review from decision, that comply with the rules (mainly available cash) TODO MOVE TO FUNCION OR AGENT
        new_total_value = portfolio["cash"]
        for ticker, decision in result.decisions.items():
            if decision.action == "buy":
                new_total_value -= decision.quantity * current_prices[ticker]
            elif decision.action == "sell":
                new_total_value += decision.quantity * current_prices[ticker]
        if new_total_value >= 0:
            break
        else:
            progress.update_status("portfolio_management_agent", None, f"Error: The total value of the portfolio would be negative, retry {attempt + 1}/{max_retries}")
            previous_result = f"The previous result needed more cash than it was available resulting in a negative cash need of {new_total_value}. Please adjunt your previous decision {result}\n"
            prompt = template.invoke(
                {
                    "previous_result": previous_result,
                    "signals_by_ticker": json.dumps(signals_by_ticker, indent=2),
                    "current_prices": json.dumps(current_prices, indent=2),
                    "max_shares": json.dumps(max_shares, indent=2),
                    "portfolio_cash": f"{portfolio['cash']:.2f}",
                    "portfolio_positions": json.dumps(portfolio["positions"], indent=2),
                    "portfolio_cost_basis": json.dumps(portfolio["cost_basis"], indent=2),
                }
            )
            if attempt == max_retries - 1:
                # On final attempt, return a safe default
                progress.update_status("portfolio_management_agent", None, "Error: The total value of the portfolio would be negative, This was the final try, did not find a solution")

    # result = make_decision(prompt, tickers)

    # Create the portfolio management message
    message = HumanMessage(
        content=json.dumps({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}),
        name="portfolio_management",
    )

    # Print the decision if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning({ticker: decision.model_dump() for ticker, decision in result.decisions.items()}, "Portfolio Management Agent")

    progress.update_status("portfolio_management_agent", None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }


def make_decision(prompt, tickers):
    """Attempts to get a decision from the LLM with retry logic"""
    llm = ChatOpenAI(model="gpt-4o").with_structured_output(
        PortfolioManagerOutput,
        method="function_calling",
    )
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = llm.invoke(prompt)
            return result
        except Exception as e:
            progress.update_status("portfolio_management_agent", None, f"Error - retry {attempt + 1}/{max_retries}")
            if attempt == max_retries - 1:
                # On final attempt, return a safe default
                return PortfolioManagerOutput(decisions={ticker: PortfolioDecision(action="hold", quantity=0, confidence=0.0, reasoning=f"Error in portfolio management, defaulting to hold - Error: {e}") for ticker in tickers})
