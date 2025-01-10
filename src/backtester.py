from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import questionary

import matplotlib.pyplot as plt
import pandas as pd
from tabulate import tabulate
from colorama import Fore, Back, Style, init

from main import run_hedge_fund
from tools.api import get_price_data
from utils.display import print_backtest_results, format_backtest_row

init(autoreset=True)


class Backtester:
    def __init__(self, agent, ticker, start_date, end_date, initial_capital, selected_analysts=None):
        self.agent = agent
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.selected_analysts = selected_analysts
        self.portfolio = {"cash": initial_capital, "stock": 0}
        self.portfolio_values = []

    def parse_agent_response(self, agent_output):
        try:
            # Expect JSON output from agent
            import json

            decision = json.loads(agent_output)
            return decision
        except:
            print(f"Error parsing action: {agent_output}")
            return "hold", 0

    def execute_trade(self, action, quantity, current_price):
        """Validate and execute trades based on portfolio constraints"""
        if action == "buy" and quantity > 0:
            cost = quantity * current_price
            if cost <= self.portfolio["cash"]:
                self.portfolio["stock"] += quantity
                self.portfolio["cash"] -= cost
                return quantity
            else:
                # Calculate maximum affordable quantity
                max_quantity = self.portfolio["cash"] // current_price
                if max_quantity > 0:
                    self.portfolio["stock"] += max_quantity
                    self.portfolio["cash"] -= max_quantity * current_price
                    return max_quantity
                return 0
        elif action == "sell" and quantity > 0:
            quantity = min(quantity, self.portfolio["stock"])
            if quantity > 0:
                self.portfolio["cash"] += quantity * current_price
                self.portfolio["stock"] -= quantity
                return quantity
            return 0
        return 0

    def run_backtest(self):
        dates = pd.date_range(self.start_date, self.end_date, freq="B")
        table_rows = []
        
        print("\nStarting backtest...")

        for current_date in dates:
            lookback_start = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
            current_date_str = current_date.strftime("%Y-%m-%d")

            output = self.agent(
                ticker=self.ticker,
                start_date=lookback_start,
                end_date=current_date_str,
                portfolio=self.portfolio,
                selected_analysts=self.selected_analysts,
            )

            agent_decision = output["decision"]
            action, quantity = agent_decision["action"], agent_decision["quantity"]
            df = get_price_data(self.ticker, lookback_start, current_date_str)
            current_price = df.iloc[-1]["close"]

            # Execute the trade with validation
            executed_quantity = self.execute_trade(action, quantity, current_price)

            # Update total portfolio value
            total_value = self.portfolio["cash"] + self.portfolio["stock"] * current_price
            self.portfolio["portfolio_value"] = total_value

            # Count signals from selected analysts only
            analyst_signals = output["analyst_signals"]

            # Count signals
            bullish_count = len([s for s in analyst_signals.values() if s.get("signal", "").lower() == "bullish"])
            bearish_count = len([s for s in analyst_signals.values() if s.get("signal", "").lower() == "bearish"])
            neutral_count = len([s for s in analyst_signals.values() if s.get("signal", "").lower() == "neutral"])
            
            print(f"Signal counts - Bullish: {bullish_count}, Bearish: {bearish_count}, Neutral: {neutral_count}")

            # Format and add row
            table_rows.append(format_backtest_row(
                date=current_date.strftime('%Y-%m-%d'),
                ticker=self.ticker,
                action=action,
                quantity=executed_quantity,
                price=current_price,
                cash=self.portfolio['cash'],
                stock=self.portfolio['stock'],
                total_value=total_value,
                bullish_count=bullish_count,
                bearish_count=bearish_count,
                neutral_count=neutral_count
            ))

            # Display the updated table
            print_backtest_results(table_rows)

            # Record the portfolio value
            self.portfolio_values.append(
                {"Date": current_date, "Portfolio Value": total_value}
            )

    def analyze_performance(self):
        # Convert portfolio values to DataFrame
        performance_df = pd.DataFrame(self.portfolio_values).set_index("Date")

        # Calculate total return
        total_return = (
            self.portfolio["portfolio_value"] - self.initial_capital
        ) / self.initial_capital
        print(f"Total Return: {total_return * 100:.2f}%")

        # Plot the portfolio value over time
        performance_df["Portfolio Value"].plot(
            title="Portfolio Value Over Time", figsize=(12, 6)
        )
        plt.ylabel("Portfolio Value ($)")
        plt.xlabel("Date")
        plt.show()

        # Compute daily returns
        performance_df["Daily Return"] = performance_df["Portfolio Value"].pct_change()

        # Calculate Sharpe Ratio (assuming 252 trading days in a year)
        mean_daily_return = performance_df["Daily Return"].mean()
        std_daily_return = performance_df["Daily Return"].std()
        sharpe_ratio = (mean_daily_return / std_daily_return) * (252**0.5)
        print(f"Sharpe Ratio: {sharpe_ratio:.2f}")

        # Calculate Maximum Drawdown
        rolling_max = performance_df["Portfolio Value"].cummax()
        drawdown = performance_df["Portfolio Value"] / rolling_max - 1
        max_drawdown = drawdown.min()
        print(f"Maximum Drawdown: {max_drawdown * 100:.2f}%")

        return performance_df


### 4. Run the Backtest #####
if __name__ == "__main__":
    import argparse

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Run backtesting simulation")
    parser.add_argument("--ticker", type=str, help="Stock ticker symbol (e.g., AAPL)")
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=(datetime.now() - relativedelta(months=3)).strftime("%Y-%m-%d"),
        help="Start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=100000,
        help="Initial capital amount (default: 100000)",
    )

    args = parser.parse_args()

    selected_analysts = None
    choices = questionary.checkbox(
        "Use the Space bar to select/unselect analysts.",
        choices=[
            questionary.Choice("Technical Analyst", value="technical_analyst"),
            questionary.Choice("Fundamentals Analyst", value="fundamentals_analyst"),
            questionary.Choice("Sentiment Analyst", value="sentiment_analyst"),
            questionary.Choice("Valuation Analyst", value="valuation_analyst"),
        ],
        instruction="\n\nPress 'a' to toggle all.\n\nPress Enter when done to run the hedge fund.",
        validate=lambda x: len(x) > 0 or "You must select at least one analyst.",
        style=questionary.Style([
            ('checkbox-selected', 'fg:green'),       
            ('selected', 'fg:green noinherit'),
            ('highlighted', 'noinherit'),  
            ('pointer', 'noinherit'),             
        ])
    ).ask()
    
    if not choices:
        print("You must select at least one analyst. Using all analysts by default.")
        selected_analysts = None
    else:
        selected_analysts = choices
        print(f"\nSelected analysts: {', '.join(Fore.GREEN + choice.title().replace('_', ' ') + Style.RESET_ALL for choice in choices)}")

    # Create an instance of Backtester
    backtester = Backtester(
        agent=run_hedge_fund,
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        selected_analysts=selected_analysts,
    )

    # Run the backtesting process
    backtester.run_backtest()
    performance_df = backtester.analyze_performance()
