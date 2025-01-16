from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai.chat_models import ChatOpenAI

from graph.state import AgentState, show_agent_reasoning


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

                Provide the following in your output:
                - "action": "buy" | "sell" | "hold",
                - "quantity": <positive integer>
                - "confidence": <float between 0 and 1>
                - "reasoning": <concise explanation of the decision including how you weighted the signals>

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

                Only include the action, quantity, reasoning, and confidence in your output as JSON.  Do not include any JSON markdown.

                Remember, the action must be either buy, sell, or hold.
                You can only buy if you have available cash.
                You can only sell if you have shares in the portfolio to sell.
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
            "technical_signal": analyst_signals.get("technical_analyst_agent", {}).get("signal", ""),
            "fundamentals_signal": analyst_signals.get("fundamentals_agent", {}).get("signal", ""),
            "sentiment_signal": analyst_signals.get("sentiment_agent", {}).get("signal", ""),
            "valuation_signal": analyst_signals.get("valuation_agent", {}).get("signal", ""),
            "max_position_size": analyst_signals.get("risk_management_agent", {}).get("max_position_size", 0),
            "portfolio_cash": f"{portfolio['cash']:.2f}",
            "portfolio_stock": portfolio["stock"],
        }
    )
    # Invoke the LLM
    llm = ChatOpenAI(model="gpt-4o-mini")
    result = llm.invoke(prompt)

    # Create the portfolio management message
    message = HumanMessage(
        content=result.content,
        name="portfolio_management",
    )

    # Print the decision if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(message.content, "Portfolio Management Agent")

    return {
        "messages": state["messages"] + [message],
        "data": state["data"],
    }
