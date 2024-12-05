from typing import Annotated, Any, Dict, Sequence, TypedDict
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from dotenv import load_dotenv
import operator
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai.chat_models import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.tools import (
    calculate_bollinger_bands,
    calculate_macd,
    calculate_obv,
    calculate_rsi,
    get_prices,
    prices_to_df
)

import argparse
from datetime import datetime
import json

# Load environment variables
load_dotenv()

# Initialize the LLM
llm = ChatOpenAI(model="gpt-4", api_key=os.getenv("OPENAI_API_KEY"))

# Define agent state
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    data: Dict[str, Any]

##### 1. Market Data Agent #####
def market_data_agent(state: AgentState):
    """Responsible for gathering and preprocessing market data"""
    messages = state["messages"]
    data = state["data"]

    # Set default dates
    end_date = data["end_date"] or datetime.now().strftime('%Y-%m-%d')
    if not data["start_date"]:
        # Calculate 3 months before end_date
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        start_date = end_date_obj.replace(month=end_date_obj.month - 3) if end_date_obj.month > 3 else \
            end_date_obj.replace(year=end_date_obj.year - 1, month=end_date_obj.month + 9)
        start_date = start_date.strftime('%Y-%m-%d')
    else:
        start_date = data["start_date"]

    # Get the historical price data
    prices = get_prices(data["ticker"], start_date, end_date)

    return {
        "messages": messages,
        "data": {**data, "prices": prices, "start_date": start_date, "end_date": end_date}
    }

##### 2. Quantitative Agent #####
def quant_agent(state: AgentState):
    """Analyzes technical indicators and generates trading signals."""
    show_reasoning = state["messages"][0].additional_kwargs["show_reasoning"]

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
    if macd_line.iloc[-2] < signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]:
        signals.append('bullish')
    elif macd_line.iloc[-2] > signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1]:
        signals.append('bearish')
    else:
        signals.append('neutral')
    
    # RSI signal
    if rsi.iloc[-1] < 30:
        signals.append('bullish')
    elif rsi.iloc[-1] > 70:
        signals.append('bearish')
    else:
        signals.append('neutral')
    
    # Bollinger Bands signal
    current_price = prices_df['close'].iloc[-1]
    if current_price < lower_band.iloc[-1]:
        signals.append('bullish')
    elif current_price > upper_band.iloc[-1]:
        signals.append('bearish')
    else:
        signals.append('neutral')
    
    # OBV signal
    obv_slope = obv.diff().iloc[-5:].mean()
    if obv_slope > 0:
        signals.append('bullish')
    elif obv_slope < 0:
        signals.append('bearish')
    else:
        signals.append('neutral')
    
    # Add reasoning collection
    reasoning = {
        "MACD": {
            "signal": signals[0],
            "details": f"MACD Line crossed {'above' if signals[0] == 'bullish' else 'below' if signals[0] == 'bearish' else 'neither above nor below'} Signal Line"
        },
        "RSI": {
            "signal": signals[1],
            "details": f"RSI is {rsi.iloc[-1]:.2f} ({'oversold' if signals[1] == 'bullish' else 'overbought' if signals[1] == 'bearish' else 'neutral'})"
        },
        "Bollinger": {
            "signal": signals[2],
            "details": f"Price is {'below lower band' if signals[2] == 'bullish' else 'above upper band' if signals[2] == 'bearish' else 'within bands'}"
        },
        "OBV": {
            "signal": signals[3],
            "details": f"OBV slope is {obv_slope:.2f} ({signals[3]})"
        }
    }
    
    # Determine overall signal
    bullish_signals = signals.count('bullish')
    bearish_signals = signals.count('bearish')
    
    if bullish_signals > bearish_signals:
        overall_signal = 'bullish'
    elif bearish_signals > bullish_signals:
        overall_signal = 'bearish'
    else:
        overall_signal = 'neutral'
    
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
            "OBV": reasoning["OBV"]
        }
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
        "messages": state["messages"] + [message],
        "data": data
    }

##### 3. Risk Management Agent #####
def risk_management_agent(state: AgentState):
    """Evaluates portfolio risk and sets position limits"""
    show_reasoning = state["messages"][0].additional_kwargs["show_reasoning"]
    portfolio = state["messages"][0].additional_kwargs["portfolio"]
    quant_message = state["messages"][-1]

    # Create the prompt template
    template = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are an aggressive yet prudent risk management specialist.
            Your job is to maximize trading opportunities while maintaining strong risk controls.
            
            Provide the following in your output (as a JSON):
            "max_position_size": <float greater than 0>,
            "risk_score": <integer between 1 and 10>,
            "trading_action": <buy | sell | hold>,
            "stop_loss_pct": <float between 0.02 and 0.10>,
            "take_profit_pct": <float between 0.05 and 0.20>,
            "reasoning": <concise explanation of the decision>
            
            Trading Rules:
            1. Position Sizing:
               - High confidence (>0.75): Up to 100% of max position
               - Medium confidence (0.5-0.75): Up to 75% of max position
               - Low confidence (<0.5): Up to 50% of max position
            
            2. Stop-Loss Strategy:
               - High volatility: 2-3% stop-loss
               - Medium volatility: 3-5% stop-loss
               - Low volatility: 5-7% stop-loss
            
            3. Take-Profit Strategy:
               - Strong trend: 15-20% target
               - Medium trend: 10-15% target
               - Weak trend: 5-10% target
            
            4. Risk Score Impact:
               - 1-3: Very Conservative (small positions)
               - 4-6: Moderate (medium positions)
               - 7-10: Aggressive (large positions)
            
            Always look for trading opportunities, but protect capital first."""
        ),
        (
            "human",
            """Based on the trading analysis below, provide your risk assessment.

            Quant Trading Signal: {quant_message}

            Current Portfolio:
            Cash: {portfolio_cash}
            Current Position: {portfolio_stock} shares
            Entry Price: {entry_price}
            Current Stop-Loss: {stop_loss}
            
            Only include the required JSON fields. Do not include any JSON markdown."""
        ),
    ])

    # Generate the prompt
    prompt = template.invoke({
        "quant_message": quant_message.content,
        "portfolio_cash": f"{portfolio['cash']:.2f}",
        "portfolio_stock": portfolio["stock"],
        "entry_price": portfolio["entry_price"],
        "stop_loss": portfolio["stop_loss"]
    })

    # Invoke the LLM
    result = llm.invoke(prompt)
    message = HumanMessage(content=result.content, name="risk_management")

    if show_reasoning:
        show_agent_reasoning(result.content, "Risk Management Agent")

    return {"messages": state["messages"] + [message]}

##### 4. Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState):
    """Makes final trading decisions and generates orders"""
    show_reasoning = state["messages"][0].additional_kwargs["show_reasoning"]
    portfolio = state["messages"][0].additional_kwargs["portfolio"]
    risk_message = state["messages"][-1]
    quant_message = state["messages"][-2]

    template = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are an active portfolio manager focused on maximizing returns while managing risk.
            Your job is to make trading decisions based on the team's analysis.
            
            Provide the following in your output:
            - "action": "buy" | "sell" | "hold"
            - "quantity": <positive integer>
            - "stop_loss": <float or 0>
            - "take_profit": <float or 0>
            - "reasoning": <concise explanation>
            
            Trading Strategy:
            1. Entry Rules:
               - Buy when multiple indicators align bullish
               - Buy on oversold conditions with positive momentum
               - Scale into positions on strong trends
            
            2. Exit Rules:
               - Sell on stop-loss hit
               - Sell on take-profit hit
               - Sell on trend reversal signals
            
            3. Position Management:
               - Scale in on confirmation
               - Scale out on weakness
               - Move stops to breakeven after 5% profit
            
            4. Risk Rules:
               - Never risk more than 2% of portfolio on single trade
               - Use smaller positions in high volatility
               - Use wider stops in lower volatility
            
            Be aggressive in taking opportunities but always protect capital."""
        ),
        (
            "human",
            """Based on the team's analysis below, make your trading decision.

            Quant Team Signal: {quant_message}
            Risk Management Signal: {risk_message}

            Current Portfolio:
            Cash: {portfolio_cash}
            Current Position: {portfolio_stock} shares
            Entry Price: {entry_price}
            Current Stop-Loss: {stop_loss}

            Only include the required JSON fields. Do not include any JSON markdown."""
        ),
    ])

    # Generate the prompt
    prompt = template.invoke({
        "quant_message": quant_message.content,
        "risk_message": risk_message.content,
        "portfolio_cash": f"{portfolio['cash']:.2f}",
        "portfolio_stock": portfolio["stock"],
        "entry_price": portfolio["entry_price"],
        "stop_loss": portfolio["stop_loss"]
    })

    # Invoke the LLM
    result = llm.invoke(prompt)
    message = HumanMessage(content=result.content, name="portfolio_management")

    if show_reasoning:
        show_agent_reasoning(result.content, "Portfolio Management Agent")

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
def run_hedge_fund(ticker: str, start_date: str, end_date: str, portfolio: dict, show_reasoning: bool = False):
    final_state = app.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Make a trading decision based on the provided data.",
                    additional_kwargs={
                        "portfolio": portfolio,
                        "show_reasoning": show_reasoning,
                    },
                )
            ],
            "data": {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date
            },
        },
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
    parser = argparse.ArgumentParser(description='Run the hedge fund trading system')
    parser.add_argument('--ticker', type=str, required=True, help='Stock ticker symbol')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD). Defaults to 3 months before end date')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD). Defaults to today')
    parser.add_argument('--show-reasoning', action='store_true', help='Show reasoning from each agent')
    
    args = parser.parse_args()
    
    # Validate dates if provided
    if args.start_date:
        try:
            datetime.strptime(args.start_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Start date must be in YYYY-MM-DD format")
    
    if args.end_date:
        try:
            datetime.strptime(args.end_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("End date must be in YYYY-MM-DD format")
    
    # Sample portfolio - you might want to make this configurable too
    portfolio = {
        "cash": 100000.0,  # $100,000 initial cash
        "stock": 0,        # No initial stock position
        "entry_price": 0,  # No entry price initially
        "stop_loss": 0     # No stop-loss initially
    }
    
    result = run_hedge_fund(
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date,
        portfolio=portfolio,
        show_reasoning=args.show_reasoning
    )
    print("\nFinal Result:")
    print(result)