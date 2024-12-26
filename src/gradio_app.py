import gradio as gr
from datetime import datetime
from main import run_hedge_fund

def hedge_fund_interface(initial_budget: float, initial_stock: float, ticker: str, start_date: str, end_date: str, show_reasoning: bool):
    
    if not ticker or not isinstance(ticker, str) or not ticker.strip():
        return "Ticker must not be empty and must be a valid string."

    try:
        initial_budget = float(initial_budget)
        initial_stock = float(initial_stock)
    except ValueError:
        return "Invalid initial value"

    try:
        if start_date:
            datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        return "Dates must be in YYYY-MM-DD format"

    portfolio = {
        "cash": initial_budget,
        "stock": initial_stock
    }
    
    try:
        result = run_hedge_fund(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            portfolio=portfolio,
            show_reasoning=show_reasoning
        )
        return f"Final Result:\n{result}"
    except Exception as e:
        return f"An error occurred: {e}"

if __name__ == '__main__':

    interface = gr.Interface(
        fn=hedge_fund_interface,
        inputs=[
            gr.Textbox(label="Initial Budget", value="100000", type="text"),
            gr.Textbox(label="Initial Stock", value="0", type="text"),
            gr.Textbox(label="Stock Ticker Symbol", value="AAPL", placeholder="e.g., AAPL", type="text"),
            gr.Textbox(label="Start Date (YYYY-MM-DD) - Defaults to 3 months before end date", placeholder="Optional", type="text"),
            gr.Textbox(label="End Date (YYYY-MM-DD) - Defaults to today", placeholder="Optional", type="text"),
            gr.Checkbox(label="Show Reasoning from Each Agent"),
        ],
        outputs="text",
        title="Hedge Fund Trading System",
        description="Run a hedge fund trading system simulation by providing the stock ticker, date range, and whether to display reasoning from agents."
    )
    # Run Gradio interface.
    interface.launch()