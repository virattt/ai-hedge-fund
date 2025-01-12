import json
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai.chat_models import ChatOpenAI

from graph.state import AgentState, show_agent_reasoning
from pydantic import BaseModel, Field
from typing import Literal


class PortfolioManagerOutput(BaseModel):
    action: Literal["buy", "sell", "hold"]
    quantity: int = Field(description="Number of shares to trade")
    confidence: float = Field(description="Confidence in the decision, between 0.0 and 100.0")
    reasoning: str = Field(description="Reasoning for the decision")


##### Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState):
    """Makes final trading decisions and generates orders"""

    # Create the prompt template
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a portfolio manager making final trading decisions.
                Your job is to make a trading decision based on the team's analysis.

                Trading Rules:
                - Only buy if you have available cash
                - Only sell if you have shares to sell
                - Quantity must be ≤ current position for sells
                - Quantity must be ≤ max_position_size from risk management""",
            ),
            (
                "human",
                """Based on the team's analysis below, make your trading decision.

                Technical Analysis Trading Signal: {technical_signal}
                Fundamental Analysis Trading Signal: {fundamentals_signal}
                Sentiment Analysis Trading Signal: {sentiment_signal}
                Valuation Analysis Trading Signal: {valuation_signal}
                Risk Management Position Limit: {max_position_size}
                Here is the current portfolio:
                Portfolio:
                Cash: {portfolio_cash}
                Current Position: {portfolio_stock} shares
                """,
            ),
        ]
    )

    # Get the portfolio and analyst signals
    portfolio = state["data"]["portfolio"]
    analyst_signals = state["data"]["analyst_signals"]

    # Generate the prompt
    prompt = template.invoke(
        {
            "technical_signal": analyst_signals.get("technical_analyst_agent", {}).get(
                "signal", ""
            ),
            "fundamentals_signal": analyst_signals.get("fundamentals_agent", {}).get(
                "signal", ""
            ),
            "sentiment_signal": analyst_signals.get("sentiment_agent", {}).get(
                "signal", ""
            ),
            "valuation_signal": analyst_signals.get("valuation_agent", {}).get(
                "signal", ""
            ),
            "max_position_size": analyst_signals.get("risk_management_agent", {}).get(
                "max_position_size", 0
            ),
            "portfolio_cash": f"{portfolio['cash']:.2f}",
            "portfolio_stock": portfolio["stock"],
        }
    )
    # Create the LLM
    llm = ChatOpenAI(model="gpt-4").with_structured_output(
        PortfolioManagerOutput,
        method="function_calling",
    )

    try:
        # Invoke the LLM
        result = llm.invoke(prompt)
    except Exception as e:
        # Try again with same prompt
        result = llm.invoke(prompt)

    message_content = {
        "action": result.action.lower(),
        "quantity": int(result.quantity),
        "confidence": float(result.confidence),
        "reasoning": result.reasoning,
    }

    # Create the portfolio management message
    message = HumanMessage(
        content=json.dumps(message_content),
        name="portfolio_management",
    )

    # Print the decision if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(message_content, "Portfolio Management Agent")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }
