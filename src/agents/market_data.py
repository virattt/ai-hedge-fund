from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

from datetime import datetime
from dateutil.relativedelta import relativedelta  # Add this import

from langchain_openai.chat_models import ChatOpenAI

from agents.state import AgentState
from tools.api import (
    get_financial_metrics,
    get_insider_trades,
    get_market_cap,
    get_prices,
    search_line_items,
)

llm = ChatOpenAI(model="gpt-4o")

def market_data_agent(state: AgentState):
    """Responsible for gathering and preprocessing market data"""
    messages = state["messages"]
    data = state["data"]

    # Set default dates
    end_date = data["end_date"] or datetime.now().strftime('%Y-%m-%d')
    if not data["start_date"]:
        # Calculate 3 months before end_date using relativedelta
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        start_date_obj = end_date_obj - relativedelta(months=3)
        start_date = start_date_obj.strftime('%Y-%m-%d')
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
        period='ttm',
        limit=1,
    )

    # Get the insider trades
    insider_trades = get_insider_trades(
        ticker=data["ticker"],
        end_date=end_date,
        limit=5,
    )

    # Get the market cap
    market_cap = get_market_cap(
        ticker=data["ticker"],
    )

    # Get the line_items
    financial_line_items = search_line_items(
        ticker=data["ticker"],
        line_items=["free_cash_flow", "net_income", "depreciation_and_amortization", "capital_expenditure", "working_capital"],
        period='ttm',
        limit=2,
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
            "market_cap": market_cap,
            "financial_line_items": financial_line_items,
        }
    }