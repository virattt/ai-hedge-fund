import json
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate

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

    progress.update_status("portfolio_management_agent", None, "Making trading decisions")

    # Generate the trading decision
    result = generate_trading_decision(
        tickers=tickers,
        signals_by_ticker=signals_by_ticker,
        current_prices=current_prices,
        max_shares=max_shares,
        portfolio=portfolio,
        model_name=state["metadata"]["model_name"],
        model_provider=state["metadata"]["model_provider"],
    )

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


def generate_trading_decision(
    tickers: list[str],
    signals_by_ticker: dict[str, dict],
    current_prices: dict[str, float],
    max_shares: dict[str, int],
    portfolio: dict[str, float],
    model_name: str,
    model_provider: str,
) -> PortfolioManagerOutput:
    """Attempts to get a decision from the LLM with retry logic"""
    # Create the prompt template
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
                
                Inputs:
                - signals_by_ticker: dictionary of ticker to signals from analysts
                - max_shares: maximum number of shares allowed for each ticker
                - portfolio_cash: current cash in portfolio
                - portfolio_positions: current positions in portfolio
                - current_prices: current price for each ticker
                
                Output (must be in JSON format):
                - action: "buy", "sell", or "hold"
                - quantity: number of shares to trade (integer)
                - confidence: confidence level between 0-100
                - reasoning: brief explanation of the decision

                IMPORTANT: Only output the final decision in a JSON format like so:
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
            (
                "human",
                """Based on the team's analysis below, make your trading decisions.

                For each ticker, here are the signals:
                {signals_by_ticker}

                Current Prices:
                {current_prices}

                Maximum Shares Allowed For Any Purchase:
                {max_shares}

                Here is the current portfolio:
                Cash: {portfolio_cash}
                Current Positions: {portfolio_positions}

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
            "signals_by_ticker": json.dumps(signals_by_ticker, indent=2),
            "current_prices": json.dumps(current_prices, indent=2),
            "max_shares": json.dumps(max_shares, indent=2),
            "portfolio_cash": f"{portfolio['cash']:.2f}",
            "portfolio_positions": json.dumps(portfolio["positions"], indent=2),
        }
    )

    # Create default factory for PortfolioManagerOutput
    def create_default_portfolio_output():
        return PortfolioManagerOutput(
            decisions={
                ticker: PortfolioDecision(
                    action="hold",
                    quantity=0,
                    confidence=0.0,
                    reasoning="Error in portfolio management, defaulting to hold"
                ) for ticker in tickers
            }
        )

    return call_llm(
        prompt=prompt,
        model_name=model_name,
        model_provider=model_provider,
        pydantic_model=PortfolioManagerOutput,
        agent_name="portfolio_management_agent",
        default_factory=create_default_portfolio_output
    )
