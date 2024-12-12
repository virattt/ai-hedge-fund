import argparse
import json
import operator
from datetime import datetime
from typing import Annotated, Any, Dict, Sequence, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai.chat_models import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.tools import (calculate_bollinger_bands, calculate_macd,
                       calculate_obv, calculate_rsi, get_financial_metrics,
                       get_insider_trades, get_prices, prices_to_df)

llm = ChatOpenAI(model="gpt-4o")


def merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    return {**a, **b}


# Define agent state
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    data: Annotated[Dict[str, Any], merge_dicts]
    metadata: Annotated[Dict[str, Any], merge_dicts]


##### Market Data Agent #####
def market_data_agent(state: AgentState):
    """Responsible for gathering and preprocessing market data"""
    messages = state["messages"]
    data = state["data"]

    # Set default dates
    end_date = data["end_date"] or datetime.now().strftime("%Y-%m-%d")
    if not data["start_date"]:
        # Calculate 3 months before end_date
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = (
            end_date_obj.replace(month=end_date_obj.month - 3)
            if end_date_obj.month > 3
            else end_date_obj.replace(
                year=end_date_obj.year - 1, month=end_date_obj.month + 9
            )
        )
        start_date = start_date.strftime("%Y-%m-%d")
    else:
        start_date = data["start_date"]

    # Get the historical price data
    prices = get_prices(
        ticker=data["ticker"],
        start_date=start_date,
        end_date=end_date,
    )

    # Get the financial metrics
    financial_metrics = get_financial_metrics(
        ticker=data["ticker"],
        report_period=end_date,
        period="ttm",
        limit=1,
    )

    # Get the insider trades
    insider_trades = get_insider_trades(
        ticker=data["ticker"],
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "messages": messages,
        "data": {
            **data,
            "prices": prices,
            "start_date": start_date,
            "end_date": end_date,
            "financial_metrics": financial_metrics,
            "insider_trades": insider_trades,
        },
    }


##### Quantitative Agent #####
def quant_agent(state: AgentState):
    """Analyzes technical indicators and generates trading signals."""
    show_reasoning = state["metadata"]["show_reasoning"]

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

    # Add reasoning collection
    reasoning = {
        "MACD": {
            "signal": signals[0],
            "details": f"MACD Line crossed {'above' if signals[0] == 'bullish' else 'below' if signals[0] == 'bearish' else 'neither above nor below'} Signal Line",
        },
        "RSI": {
            "signal": signals[1],
            "details": f"RSI is {rsi.iloc[-1]:.2f} ({'oversold' if signals[1] == 'bullish' else 'overbought' if signals[1] == 'bearish' else 'neutral'})",
        },
        "Bollinger": {
            "signal": signals[2],
            "details": f"Price is {'below lower band' if signals[2] == 'bullish' else 'above upper band' if signals[2] == 'bearish' else 'within bands'}",
        },
        "OBV": {
            "signal": signals[3],
            "details": f"OBV slope is {obv_slope:.2f} ({signals[3]})",
        },
    }

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

    # Generate the message content
    message_content = {
        "signal": overall_signal,
        "confidence": round(confidence, 2),
        "reasoning": {
            "MACD": reasoning["MACD"],
            "RSI": reasoning["RSI"],
            "Bollinger": reasoning["Bollinger"],
            "OBV": reasoning["OBV"],
        },
    }

    # Create the quant message
    message = HumanMessage(
        content=str(message_content),  # Convert dict to string for message content
        name="quant_agent",
    )

    # Print the reasoning if the flag is set
    if show_reasoning:
        show_agent_reasoning(message_content, "Quant Agent")

    return {
        "messages": [message],
        "data": data,
    }


##### Fundamental Agent #####
def fundamentals_agent(state: AgentState):
    """Analyzes fundamental data and generates trading signals."""
    show_reasoning = state["metadata"]["show_reasoning"]
    data = state["data"]
    metrics = data["financial_metrics"][0]  # Get the most recent metrics

    # Initialize signals list for different fundamental aspects
    signals = []
    reasoning = {}

    # 1. Profitability Analysis
    profitability_score = 0
    if metrics["return_on_equity"] > 0.15:  # Strong ROE above 15%
        profitability_score += 1
    if metrics["net_margin"] > 0.20:  # Healthy profit margins
        profitability_score += 1
    if metrics["operating_margin"] > 0.15:  # Strong operating efficiency
        profitability_score += 1

    signals.append(
        "bullish"
        if profitability_score >= 2
        else "bearish"
        if profitability_score == 0
        else "neutral"
    )
    reasoning["Profitability"] = {
        "signal": signals[0],
        "details": f"ROE: {metrics['return_on_equity']:.2%}, Net Margin: {metrics['net_margin']:.2%}, Op Margin: {metrics['operating_margin']:.2%}",
    }

    # 2. Growth Analysis
    growth_score = 0
    if metrics["revenue_growth"] > 0.10:  # 10% revenue growth
        growth_score += 1
    if metrics["earnings_growth"] > 0.10:  # 10% earnings growth
        growth_score += 1
    if metrics["book_value_growth"] > 0.10:  # 10% book value growth
        growth_score += 1

    signals.append(
        "bullish"
        if growth_score >= 2
        else "bearish"
        if growth_score == 0
        else "neutral"
    )
    reasoning["Growth"] = {
        "signal": signals[1],
        "details": f"Revenue Growth: {metrics['revenue_growth']:.2%}, Earnings Growth: {metrics['earnings_growth']:.2%}",
    }

    # 3. Financial Health
    health_score = 0
    if metrics["current_ratio"] > 1.5:  # Strong liquidity
        health_score += 1
    if metrics["debt_to_equity"] < 0.5:  # Conservative debt levels
        health_score += 1
    if (
        metrics["free_cash_flow_per_share"] > metrics["earnings_per_share"] * 0.8
    ):  # Strong FCF conversion
        health_score += 1

    signals.append(
        "bullish"
        if health_score >= 2
        else "bearish"
        if health_score == 0
        else "neutral"
    )
    reasoning["Financial_Health"] = {
        "signal": signals[2],
        "details": f"Current Ratio: {metrics['current_ratio']:.2f}, D/E: {metrics['debt_to_equity']:.2f}",
    }

    # 4. Valuation
    pe_ratio = metrics["price_to_earnings_ratio"]
    pb_ratio = metrics["price_to_book_ratio"]
    ps_ratio = metrics["price_to_sales_ratio"]

    valuation_score = 0
    if pe_ratio < 25:  # Reasonable P/E ratio
        valuation_score += 1
    if pb_ratio < 3:  # Reasonable P/B ratio
        valuation_score += 1
    if ps_ratio < 5:  # Reasonable P/S ratio
        valuation_score += 1

    signals.append(
        "bullish"
        if valuation_score >= 2
        else "bearish"
        if valuation_score == 0
        else "neutral"
    )
    reasoning["Valuation"] = {
        "signal": signals[3],
        "details": f"P/E: {pe_ratio:.2f}, P/B: {pb_ratio:.2f}, P/S: {ps_ratio:.2f}",
    }

    # Determine overall signal
    bullish_signals = signals.count("bullish")
    bearish_signals = signals.count("bearish")

    if bullish_signals > bearish_signals:
        overall_signal = "bullish"
    elif bearish_signals > bullish_signals:
        overall_signal = "bearish"
    else:
        overall_signal = "neutral"

    # Calculate confidence level
    total_signals = len(signals)
    confidence = max(bullish_signals, bearish_signals) / total_signals

    message_content = {
        "signal": overall_signal,
        "confidence": round(confidence, 2),
        "reasoning": reasoning,
    }

    # Create the fundamental analysis message
    message = HumanMessage(
        content=str(message_content),
        name="fundamentals_agent",
    )

    # Print the reasoning if the flag is set
    if show_reasoning:
        show_agent_reasoning(message_content, "Fundamental Analysis Agent")

    return {
        "messages": [message],
        "data": data,
    }


##### Sentiment Agent #####
def sentiment_agent(state: AgentState):
    """Analyzes market sentiment and generates trading signals."""
    data = state["data"]
    insider_trades = data["insider_trades"]
    show_reasoning = state["metadata"]["show_reasoning"]

    # Create the prompt template
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
                You are a market sentiment analyst.
                Your job is to analyze the insider trades of a company and provide a sentiment analysis.
                The insider trades are a list of transactions made by company insiders.
                - If the insider is buying, the sentiment may be bullish. 
                - If the insider is selling, the sentiment may be bearish.
                - If the insider is neutral, the sentiment may be neutral.
                The sentiment is amplified if the insider is buying or selling a large amount of shares.
                Also, the sentiment is amplified if the insider is a high-level executive (e.g. CEO, CFO, etc.) or board member.
                For each insider trade, provide the following in your output (as a JSON):
                "sentiment": <bullish | bearish | neutral>,
                "reasoning": <concise explanation of the decision>
                """,
            ),
            (
                "human",
                """
                Based on the following insider trades, provide your sentiment analysis.
                {insider_trades}

                Only include the sentiment and reasoning in your JSON output.  Do not include any JSON markdown.
                """,
            ),
        ]
    )

    # Generate the prompt
    prompt = template.invoke({"insider_trades": insider_trades})

    # Invoke the LLM
    result = llm.invoke(prompt)

    # Extract the sentiment and reasoning from the result, safely
    try:
        message_content = json.loads(result.content)
    except json.JSONDecodeError:
        message_content = {
            "sentiment": "neutral",
            "reasoning": "Unable to parse JSON output of market sentiment analysis",
        }

    # Create the market sentiment message
    message = HumanMessage(
        content=str(message_content),
        name="sentiment_agent",
    )

    # Print the reasoning if the flag is set
    if show_reasoning:
        show_agent_reasoning(message_content, "Sentiment Analysis Agent")

    return {
        "messages": [message],
        "data": data,
    }


##### Risk Management Agent #####
def risk_management_agent(state: AgentState):
    """Evaluates portfolio risk and sets position limits"""
    show_reasoning = state["metadata"]["show_reasoning"]
    portfolio = state["data"]["portfolio"]

    # Find the quant message by looking for the message with name "quant_agent"
    quant_message = next(msg for msg in state["messages"] if msg.name == "quant_agent")
    fundamentals_message = next(
        msg for msg in state["messages"] if msg.name == "fundamentals_agent"
    )
    sentiment_message = next(
        msg for msg in state["messages"] if msg.name == "sentiment_agent"
    )
    # Create the prompt template
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a risk management specialist.
                Your job is to take a look at the trading analysis and
                evaluate portfolio exposure and recommend position sizing.
                Provide the following in your output (as a JSON):
                "max_position_size": <float greater than 0>,
                "risk_score": <integer between 1 and 10>,
                "trading_action": <buy | sell | hold>,
                "reasoning": <concise explanation of the decision>
                """,
            ),
            (
                "human",
                """Based on the trading analysis below, provide your risk assessment.

                Quant Analysis Trading Signal: {quant_message}
                Fundamental Analysis Trading Signal: {fundamentals_message}
                Sentiment Analysis Trading Signal: {sentiment_message}
                Here is the current portfolio:
                Portfolio:
                Cash: {portfolio_cash}
                Current Position: {portfolio_stock} shares
                
                Only include the max position size, risk score, trading action, and reasoning in your JSON output.  Do not include any JSON markdown.
                """,
            ),
        ]
    )

    # Generate the prompt
    prompt = template.invoke(
        {
            "quant_message": quant_message.content,
            "fundamentals_message": fundamentals_message.content,
            "sentiment_message": sentiment_message.content,
            "portfolio_cash": f"{portfolio['cash']:.2f}",
            "portfolio_stock": portfolio["stock"],
        }
    )

    # Invoke the LLM
    result = llm.invoke(prompt)
    message = HumanMessage(
        content=result.content,
        name="risk_management_agent",
    )

    # Print the decision if the flag is set
    if show_reasoning:
        show_agent_reasoning(message.content, "Risk Management Agent")

    return {"messages": state["messages"] + [message]}


##### Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState):
    """Makes final trading decisions and generates orders"""
    show_reasoning = state["metadata"]["show_reasoning"]
    portfolio = state["data"]["portfolio"]

    # Get the quant agent, fundamentals agent, and risk management agent messages
    quant_message = next(msg for msg in state["messages"] if msg.name == "quant_agent")
    fundamentals_message = next(
        msg for msg in state["messages"] if msg.name == "fundamentals_agent"
    )
    sentiment_message = next(
        msg for msg in state["messages"] if msg.name == "sentiment_agent"
    )
    risk_message = next(
        msg for msg in state["messages"] if msg.name == "risk_management_agent"
    )

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
                - "reasoning": <concise explanation of the decision>
                Only buy if you have available cash.
                The quantity that you buy must be less than or equal to the max position size.
                Only sell if you have shares in the portfolio to sell.
                The quantity that you sell must be less than or equal to the current position.""",
            ),
            (
                "human",
                """Based on the team's analysis below, make your trading decision.

                Quant Analysis Trading Signal: {quant_message}
                Fundamental Analysis Trading Signal: {fundamentals_message}
                Sentiment Analysis Trading Signal: {sentiment_message}
                Risk Management Trading Signal: {risk_message}

                Here is the current portfolio:
                Portfolio:
                Cash: {portfolio_cash}
                Current Position: {portfolio_stock} shares

                Only include the action, quantity, and reasoning in your output as JSON.  Do not include any JSON markdown.

                Remember, the action must be either buy, sell, or hold.
                You can only buy if you have available cash.
                You can only sell if you have shares in the portfolio to sell.
                """,
            ),
        ]
    )

    # Generate the prompt
    prompt = template.invoke(
        {
            "quant_message": quant_message.content,
            "fundamentals_message": fundamentals_message.content,
            "sentiment_message": sentiment_message.content,
            "risk_message": risk_message.content,
            "portfolio_cash": f"{portfolio['cash']:.2f}",
            "portfolio_stock": portfolio["stock"],
        }
    )
    # Invoke the LLM
    result = llm.invoke(prompt)

    # Create the portfolio management message
    message = HumanMessage(
        content=result.content,
        name="portfolio_management",
    )

    # Print the decision if the flag is set
    if show_reasoning:
        show_agent_reasoning(message.content, "Portfolio Management Agent")

    return {"messages": state["messages"] + [message]}


def show_agent_reasoning(output, agent_name):
    print(f"\n{'=' * 10} {agent_name.center(28)} {'=' * 10}")
    if isinstance(output, (dict, list)):
        # If output is already a dictionary or list, just pretty print it
        print(json.dumps(output, indent=2))
    else:
        try:
            # Parse the string as JSON and pretty print it
            parsed_output = json.loads(output)
            print(json.dumps(parsed_output, indent=2))
        except json.JSONDecodeError:
            # Fallback to original string if not valid JSON
            print(output)
    print("=" * 48)


##### Run the Hedge Fund #####
def run_hedge_fund(
    ticker: str,
    start_date: str,
    end_date: str,
    portfolio: dict,
    show_reasoning: bool = False,
):
    final_state = app.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Make a trading decision based on the provided data.",
                )
            ],
            "data": {
                "ticker": ticker,
                "portfolio": portfolio,
                "start_date": start_date,
                "end_date": end_date,
            },
            "metadata": {
                "show_reasoning": show_reasoning,
            },
        },
    )
    return final_state["messages"][-1].content


# Define the new workflow
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("market_data_agent", market_data_agent)
workflow.add_node("quant_agent", quant_agent)
workflow.add_node("fundamentals_agent", fundamentals_agent)
workflow.add_node("sentiment_agent", sentiment_agent)
workflow.add_node("risk_management_agent", risk_management_agent)
workflow.add_node("portfolio_management_agent", portfolio_management_agent)

# Define the workflow
workflow.set_entry_point("market_data_agent")
workflow.add_edge("market_data_agent", "quant_agent")
workflow.add_edge("market_data_agent", "fundamentals_agent")
workflow.add_edge("market_data_agent", "sentiment_agent")
workflow.add_edge("quant_agent", "risk_management_agent")
workflow.add_edge("fundamentals_agent", "risk_management_agent")
workflow.add_edge("sentiment_agent", "risk_management_agent")
workflow.add_edge("risk_management_agent", "portfolio_management_agent")
workflow.add_edge("portfolio_management_agent", END)

app = workflow.compile()

# Add this at the bottom of the file
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the hedge fund trading system")
    parser.add_argument("--ticker", type=str, required=True, help="Stock ticker symbol")
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD). Defaults to 3 months before end date",
    )
    parser.add_argument(
        "--end-date", type=str, help="End date (YYYY-MM-DD). Defaults to today"
    )
    parser.add_argument(
        "--show-reasoning", action="store_true", help="Show reasoning from each agent"
    )

    args = parser.parse_args()

    # Validate dates if provided
    if args.start_date:
        try:
            datetime.strptime(args.start_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Start date must be in YYYY-MM-DD format")

    if args.end_date:
        try:
            datetime.strptime(args.end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("End date must be in YYYY-MM-DD format")

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
        show_reasoning=args.show_reasoning,
    )
    print("\nFinal Result:")
    print(result)
