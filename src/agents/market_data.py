
from langchain_openai.chat_models import ChatOpenAI

from agents.state import AgentState
from tools.api import search_line_items, get_financial_metrics, get_insider_trades, get_market_cap, get_prices

from datetime import datetime
import calendar

llm = ChatOpenAI(model="gpt-4o")

def market_data_agent(state: AgentState):
    """Responsible for gathering and preprocessing market data"""
    messages = state["messages"]
    data = state["data"]

    # Set default dates
    end_date = data["end_date"] or datetime.now().strftime('%Y-%m-%d')
    if not data["start_date"]:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Calculate 3 months before end_date
        new_month = (end_date_obj.month - 3) % 12 or 12
        new_year = end_date_obj.year - 1 if end_date_obj.month <= 3 else end_date_obj.year
        # Get the last day of the new month to handle edge cases like December 31
        last_day_of_month = calendar.monthrange(new_year, new_month)[1]
        new_day = min(end_date_obj.day, last_day_of_month)
        
        # Create the new date
        start_date_obj = end_date_obj.replace(year=new_year, month=new_month, day=new_day)
        
        # Format the start_date as a string
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
