from datetime import datetime
import os

from matplotlib.dates import relativedelta
from main import create_workflow, run_hedge_fund
from utils.display import print_trading_output
import json
current_file_path = os.path.dirname(os.path.abspath(__file__))
# 设置服务器的根目录为脚本所在目录
os.chdir(current_file_path + "/../../")
if __name__ == "__main__":

    # Parse tickers from comma-separated string
    tickers = ['NVDA', 'AAPL', 'TSLA']
    # Select analysts
    selected_analysts = [
    "ben_graham",
    "bill_ackman",
    "cathie_wood",
    "charlie_munger",
    "michael_burry",
    "peter_lynch",
    "phil_fisher",
    "stanley_druckenmiller",
    "warren_buffett",
    "technical_analyst",
    "fundamentals_analyst",
    "sentiment_analyst",
    "valuation_analyst"
]
    #selected_analysts = ['ben_graham', 'warren_buffett', "michael_burry"]
    
    # Select LLM model based on whether Ollama is being used
    model_choice = 'deepseek-chat'
    model_provider = 'DeepSeek'
    # Create the workflow with selected analysts
    workflow = create_workflow(selected_analysts)
    app = workflow.compile()

    
    # Set the start and end dates
    end_date = datetime.now().strftime("%Y-%m-%d")
    # Calculate 3 months before end_date
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    start_date = (end_date_obj - relativedelta(months=3)).strftime("%Y-%m-%d")

    # Initialize portfolio with cash amount and stock positions
    portfolio = {
        "cash": 10000,  # Initial cash amount
        "margin_requirement": 0.3,  # Initial margin requirement
        "margin_used": 0.0,  # total margin usage across all short positions
        "positions": {
            ticker: {
                "long": 0,  # Number of shares held long
                "short": 0,  # Number of shares held short
                "long_cost_basis": 0.0,  # Average cost basis for long positions
                "short_cost_basis": 0.0,  # Average price at which shares were sold short
                "short_margin_used": 0.0,  # Dollars of margin used for this ticker's short
            }
            for ticker in tickers
        },
        "realized_gains": {
            ticker: {
                "long": 0.0,  # Realized gains from long positions
                "short": 0.0,  # Realized gains from short positions
            }
            for ticker in tickers
        },
    }
    portfolio = json.load(open("./portfolio.json", 'r'))
    portfolio["margin_requirement"] = 0.3
    portfolio["cash"] = portfolio["CashBalance"]
    # Run the hedge fund
    result = run_hedge_fund(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        portfolio=portfolio,
        show_reasoning=False,
        selected_analysts=selected_analysts,
        model_name=model_choice,
        model_provider=model_provider,
    )
    print("Result:", result)
    print_trading_output(result)

    # Save result to a JSON file
    with open('./result.json', 'w') as json_file:
        json.dump(result, json_file, indent=4)
