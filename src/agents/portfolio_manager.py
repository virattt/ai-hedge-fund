import json
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai.chat_models import ChatOpenAI
from config.models import get_chat_model

from graph.state import AgentState, show_agent_reasoning
from pydantic import BaseModel, Field
from typing_extensions import Literal
from utils.progress import progress


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

    # Format signals by ticker
    signals_by_ticker = {}
    for ticker in tickers:
        progress.update_status("portfolio_management_agent", ticker, "Processing analyst signals")
        ticker_signals = {}
        for agent, signals in analyst_signals.items():
            if agent != "risk_management_agent" and ticker in signals:
                ticker_signals[agent] = {
                    "signal": signals[ticker]["signal"],
                    "confidence": signals[ticker]["confidence"]
                }
        signals_by_ticker[ticker] = ticker_signals

    progress.update_status("portfolio_management_agent", None, "Calculating position limits")
    # Format position limits
    position_limits = {
        ticker: analyst_signals.get("risk_management_agent", {}).get(ticker, {}).get("max_position_size", 0)
        for ticker in tickers
    }

    progress.update_status("portfolio_management_agent", None, "Preparing trading strategy")
    # Create the prompt template
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a portfolio manager making final trading decisions.
                Your job is to make trading decisions based on the team's analysis for multiple tickers.

                Trading Rules:
                - Only buy if you have available cash
                - Only sell if you have shares to sell
                - Quantity must be ≤ current position for sells
                - Quantity must be ≤ max_position_size from risk management
                - Total position value across all tickers should not exceed portfolio limits
                
                For each ticker, you must return:
                - action: "buy", "sell", or "hold"
                - quantity: number of shares to trade (integer)
                - confidence: confidence level between 0-100
                - reasoning: brief explanation of the decision""",
            ),
            (
                "human",
                """Based on the team's analysis below, make your trading decisions.

                For each ticker, here are the signals:
                {signals_by_ticker}

                Risk Management Position Limits:
                {position_limits}

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
            "position_limits": json.dumps(position_limits, indent=2),
            "portfolio_cash": f"{portfolio['cash']:.2f}",
            "portfolio_positions": json.dumps(portfolio['positions'], indent=2),
        }
    )

    progress.update_status("portfolio_management_agent", None, "Making trading decisions")
    
    
    provider = state["metadata"].get("model_provider", "openai")
    model = state["metadata"].get("model_name")
    
    # Create the LLM
    llm = get_chat_model(provider=provider, model=model, structure=PortfolioManagerOutput)
    
    try:
        # Invoke the LLM
        result = llm.invoke(prompt)
    except Exception as e:
        progress.update_status("portfolio_management_agent", None, "Error - retrying")
        # Try again with same prompt
        result = llm.invoke(prompt)

    # Create the portfolio management message
    message = HumanMessage(
        content=json.dumps({
            ticker: decision.model_dump()
            for ticker, decision in result.decisions.items()
        }),
        name="portfolio_management",
    )

    # Print the decision if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning({
            ticker: decision.model_dump()
            for ticker, decision in result.decisions.items()
        }, "Portfolio Management Agent")

    progress.update_status("portfolio_management_agent", None, "Done")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }
