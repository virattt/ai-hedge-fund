import argparse
import operator
from datetime import datetime
from typing import Annotated, Any, Dict, Sequence, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai.chat_models import ChatOpenAI
from langgraph.graph import END, StateGraph

from ai_hedge_fund.tools.tools import (
    calculate_bollinger_bands,
    calculate_macd,
    calculate_obv,
    calculate_rsi,
    get_prices,
    prices_to_df,
)

llm = ChatOpenAI(model="gpt-4o")


# Define agent state
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    data: Dict[str, Any]


##### 1. Market Data Agent #####
def market_data_agent(state: AgentState):
    """Responsible for gathering and preprocessing market data"""
    messages = state["messages"]
    data = state["data"]

    # Get the historical price data
    prices = get_prices(data["ticker"], data["start_date"], data["end_date"])

    return {"messages": messages, "data": {**data, "prices": prices}}


##### 2. Quantitative Agent #####
def quant_agent(state: AgentState):
    """Analyzes technical indicators and generates trading signals."""
    data = state["data"]
    prices = data["prices"]
    prices_df = prices_to_df(prices)

    # Calculate indicators
    # 1. MACD (Moving Average Convergence Divergence)
    macd_line, signal_line = calculate_macd(prices_df)

    # 2. RSI (Relative Strength Index)
    rsi = calculate_rsi(prices_df)

    # 3. Bollinger Bands (Bollinger Bands)
    upper_band, lower_band = calculate_bollinger_bands(prices_df)

    # 4. OBV (On-Balance Volume)
    obv = calculate_obv(prices_df)

    # Generate individual signals
    signals = []

    # MACD signal
    if (
        macd_line.iloc[-2] < signal_line.iloc[-2]
        and macd_line.iloc[-1] > signal_line.iloc[-1]
    ):
        signals.append("bullish")
    elif (
        macd_line.iloc[-2] > signal_line.iloc[-2]
        and macd_line.iloc[-1] < signal_line.iloc[-1]
    ):
        signals.append("bearish")
    else:
        signals.append("neutral")

    # RSI signal
    if rsi.iloc[-1] < 30:
        signals.append("bullish")
    elif rsi.iloc[-1] > 70:
        signals.append("bearish")
    else:
        signals.append("neutral")

    # Bollinger Bands signal
    current_price = prices_df["close"].iloc[-1]
    if current_price < lower_band.iloc[-1]:
        signals.append("bullish")
    elif current_price > upper_band.iloc[-1]:
        signals.append("bearish")
    else:
        signals.append("neutral")

    # OBV signal
    obv_slope = obv.diff().iloc[-5:].mean()
    if obv_slope > 0:
        signals.append("bullish")
    elif obv_slope < 0:
        signals.append("bearish")
    else:
        signals.append("neutral")

    # Determine overall signal
    bullish_signals = signals.count("bullish")
    bearish_signals = signals.count("bearish")

    if bullish_signals > bearish_signals:
        overall_signal = "bullish"
    elif bearish_signals > bullish_signals:
        overall_signal = "bearish"
    else:
        overall_signal = "neutral"

    # Calculate confidence level based on the proportion of indicators agreeing
    total_signals = len(signals)
    confidence = max(bullish_signals, bearish_signals) / total_signals

    # Create the quant agent's message
    message_content = f"""
    Trading Signal: {overall_signal}
    Confidence (0-1, higher is better): {confidence:.2f}
    """
    message = HumanMessage(
        content=message_content.strip(),
        name="quant_agent",
    )

    return {"messages": state["messages"] + [message], "data": data}


##### 3. Risk Management Agent #####
def risk_management_agent(state: AgentState):
    """Evaluates portfolio risk and sets position limits"""
    portfolio = state["messages"][0].additional_kwargs["portfolio"]
    last_message = state["messages"][-1]

    risk_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a risk management specialist.
                Your job is to take a look at the trading analysis and
                evaluate portfolio exposure and recommend position sizing.
                Provide the following in your output (not as a JSON):
                - max_position_size: <float greater than 0>,
                - risk_score: <integer between 1 and 10>""",
            ),
            MessagesPlaceholder(variable_name="messages"),
            (
                "human",
                f"""Based on the trading analysis below, provide your risk assessment.

                Trading Analysis: {last_message.content}

                Here is the current portfolio:
                Portfolio:
                Cash: ${portfolio['cash']:.2f}
                Current Position: {portfolio['stock']} shares
                
                Only include the max position size and risk score in your output.
                """,
            ),
        ]
    )
    chain = risk_prompt | llm
    result = chain.invoke(state).content
    message = HumanMessage(
        content=f"Here is the risk management recommendation: {result}",
        name="risk_management",
    )
    return {"messages": state["messages"] + [message]}


##### 4. Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState):
    """Makes final trading decisions and generates orders"""
    portfolio = state["messages"][0].additional_kwargs["portfolio"]
    last_message = state["messages"][-1]

    portfolio_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a portfolio manager making final trading decisions.
                Your job is to make a trading decision based on the risk management data.
                Provide the following in your output:
                - "action": "buy" | "sell" | "hold",
                - "quantity": <positive integer>
                Only buy if you have available cash.
                The quantity that you buy must be less than or equal to the max position size.
                Only sell if you have shares in the portfolio to sell.
                The quantity that you sell must be less than or equal to the current position.""",
            ),
            MessagesPlaceholder(variable_name="messages"),
            (
                "human",
                f"""Based on the risk management data below, make your trading decision.

                Risk Management Data: {last_message.content}

                Here is the current portfolio:
                Portfolio:
                Cash: ${portfolio['cash']:.2f}
                Current Position: {portfolio['stock']} shares
                
                Only include the action and quantity in your output as JSON.

                Remember, the action must be either buy, sell, or hold.
                You can only buy if you have available cash.
                You can only sell if you have shares in the portfolio to sell.
                """,
            ),
        ]
    )

    chain = portfolio_prompt | llm
    result = chain.invoke(state).content
    return {"messages": [HumanMessage(content=result, name="portfolio_management")]}


##### Run the Hedge Fund #####
def run_hedge_fund(ticker: str, start_date: str, end_date: str, portfolio: dict):
    final_state = app.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Make a trading decision based on the provided data.",
                    additional_kwargs={
                        "ticker": ticker,
                        "start_date": start_date,
                        "end_date": end_date,
                        "portfolio": portfolio,
                    },
                )
            ],
            "data": {"ticker": ticker, "start_date": start_date, "end_date": end_date},
        },
        config={"configurable": {"thread_id": 42}},
    )
    return final_state["messages"][-1].content


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

app = workflow.compile()

# Add this at the bottom of the file
if __name__ == "__main__":
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
    except ValueError:
        raise ValueError("Dates must be in YYYY-MM-DD format")

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
