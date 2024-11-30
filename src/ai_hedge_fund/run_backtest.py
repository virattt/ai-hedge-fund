from ai_hedge_fund.agents.agents import run_hedge_fund
from ai_hedge_fund.backtesting.backtester import Backtester

if __name__ == "__main__":
    # Define parameters
    ticker = "AAPL"  # Example ticker symbol
    start_date = "2024-01-01"  # Adjust as needed
    end_date = "2024-03-31"  # Adjust as needed
    initial_capital = 100000  # $100,000

    # Create an instance of Backtester
    backtester = Backtester(
        agent=run_hedge_fund,
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
    )

    # Run the backtesting process
    backtester.run_backtest()
    performance_df = backtester.analyze_performance()
