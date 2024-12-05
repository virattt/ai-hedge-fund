from datetime import datetime, timedelta
import argparse
import sys
from pathlib import Path

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

import pandas as pd
import numpy as np

from src.tools import get_price_data
from src.agents import run_hedge_fund

class Backtester:
    def __init__(self, agent, ticker, start_date, end_date, initial_capital, show_reasoning=False):
        self.agent = agent
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.show_reasoning = show_reasoning
        self.portfolio = {
            "cash": initial_capital,
            "stock": 0,
            "entry_price": 0,    # Track entry price for stop-loss/take-profit
            "stop_loss": 0,      # Track stop-loss level
            "take_profit": 0     # Track take-profit level
        }
        self.portfolio_values = []
        self.trades = []  # Track all trades for analysis
        self.trade_stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "stop_losses_hit": 0,
            "take_profits_hit": 0,
            "total_profit": 0,
            "total_loss": 0
        }

    def parse_action(self, agent_output):
        """Parse the agent's trading decision"""
        try:
            import json
            decision = json.loads(agent_output)
            action = decision["action"]
            quantity = decision["quantity"]
            stop_loss = decision.get("stop_loss", 0)
            take_profit = decision.get("take_profit", 0)
            return action, quantity, stop_loss, take_profit
        except:
            print(f"Error parsing action: {agent_output}")
            return "hold", 0, 0, 0

    def check_stop_loss(self, current_price):
        """Check if stop-loss has been triggered"""
        if self.portfolio["stock"] > 0 and self.portfolio["stop_loss"] > 0:
            if current_price <= self.portfolio["stop_loss"]:
                return True
        return False

    def check_take_profit(self, current_price):
        """Check if take-profit has been triggered"""
        if self.portfolio["stock"] > 0 and self.portfolio["take_profit"] > 0:
            if current_price >= self.portfolio["take_profit"]:
                return True
        return False

    def execute_trade(self, action, quantity, current_price, stop_loss=0, take_profit=0):
        """Execute trades with improved position management"""
        if action == "buy" and quantity > 0:
            cost = quantity * current_price
            if cost <= self.portfolio["cash"]:
                self.portfolio["stock"] += quantity
                self.portfolio["cash"] -= cost
                self.portfolio["entry_price"] = current_price
                self.portfolio["stop_loss"] = stop_loss
                self.portfolio["take_profit"] = take_profit
                self.trade_stats["total_trades"] += 1
                return quantity
            else:
                # Calculate maximum affordable quantity
                max_quantity = self.portfolio["cash"] // current_price
                if max_quantity > 0:
                    self.portfolio["stock"] += max_quantity
                    self.portfolio["cash"] -= max_quantity * current_price
                    self.portfolio["entry_price"] = current_price
                    self.portfolio["stop_loss"] = stop_loss
                    self.portfolio["take_profit"] = take_profit
                    self.trade_stats["total_trades"] += 1
                    return max_quantity
                return 0
        elif action in ["sell", "stop-loss", "take-profit"] and quantity > 0:
            quantity = min(quantity, self.portfolio["stock"])
            if quantity > 0:
                sale_proceeds = quantity * current_price
                self.portfolio["cash"] += sale_proceeds
                self.portfolio["stock"] -= quantity
                
                # Calculate profit/loss
                trade_pl = (current_price - self.portfolio["entry_price"]) * quantity
                if trade_pl > 0:
                    self.trade_stats["winning_trades"] += 1
                    self.trade_stats["total_profit"] += trade_pl
                else:
                    self.trade_stats["losing_trades"] += 1
                    self.trade_stats["total_loss"] += abs(trade_pl)

                if action == "stop-loss":
                    self.trade_stats["stop_losses_hit"] += 1
                elif action == "take-profit":
                    self.trade_stats["take_profits_hit"] += 1

                if self.portfolio["stock"] == 0:
                    # Reset position tracking when fully closed
                    self.portfolio["entry_price"] = 0
                    self.portfolio["stop_loss"] = 0
                    self.portfolio["take_profit"] = 0
                return quantity
            return 0
        return 0

    def log_trade(self, date, action, quantity, price, stop_loss, take_profit):
        """Log detailed trade information"""
        self.trades.append({
            "date": date,
            "action": action,
            "quantity": quantity,
            "price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "cash": self.portfolio["cash"],
            "stock": self.portfolio["stock"],
            "portfolio_value": self.portfolio["cash"] + (self.portfolio["stock"] * price),
            "profit_loss": (price - self.portfolio["entry_price"]) * quantity if self.portfolio["entry_price"] > 0 else 0
        })

    def analyze_trades(self):
        """Analyze trading performance with enhanced metrics"""
        if not self.trades:
            return

        print("\nTrading Performance Analysis:")
        print(f"Total Trades: {self.trade_stats['total_trades']}")
        print(f"Winning Trades: {self.trade_stats['winning_trades']}")
        print(f"Losing Trades: {self.trade_stats['losing_trades']}")
        print(f"Stop-Losses Hit: {self.trade_stats['stop_losses_hit']}")
        print(f"Take-Profits Hit: {self.trade_stats['take_profits_hit']}")
        
        if self.trade_stats['total_trades'] > 0:
            win_rate = (self.trade_stats['winning_trades'] / self.trade_stats['total_trades']) * 100
            print(f"Win Rate: {win_rate:.2f}%")
        
        total_profit = self.trade_stats['total_profit']
        total_loss = self.trade_stats['total_loss']
        if total_loss > 0:
            profit_factor = total_profit / total_loss
            print(f"Profit Factor: {profit_factor:.2f}")
        
        print(f"Total Profit: ${total_profit:,.2f}")
        print(f"Total Loss: ${total_loss:,.2f}")
        print(f"Net Profit/Loss: ${(total_profit - total_loss):,.2f}")
        
        # Calculate max drawdown
        portfolio_values = [t["portfolio_value"] for t in self.trades]
        peak = portfolio_values[0]
        max_drawdown = 0
        
        for value in portfolio_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)
        
        print(f"Maximum Drawdown: {max_drawdown:.2f}%")

    def run_backtest(self):
        dates = pd.date_range(self.start_date, self.end_date, freq="B")

        print("\nStarting backtest...")
        print(f"{'Date':<12} {'Ticker':<6} {'Action':<8} {'Qty':>8} {'Price':>10} {'Stop':>10} {'Target':>10} {'Cash':>12} {'Stock':>8} {'Value':>12}")
        print("-" * 100)

        for current_date in dates:
            lookback_start = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
            current_date_str = current_date.strftime("%Y-%m-%d")

            # Get current price first to check stop-loss/take-profit
            df = get_price_data(self.ticker, lookback_start, current_date_str)
            current_price = df.iloc[-1]['close']

            # Check for stop-loss or take-profit triggers
            stop_loss_triggered = self.check_stop_loss(current_price)
            take_profit_triggered = self.check_take_profit(current_price)
            
            if stop_loss_triggered:
                action = "sell"
                quantity = self.portfolio["stock"]
                stop_loss = 0
                take_profit = 0
                executed_quantity = self.execute_trade(action, quantity, current_price)
                action_type = "stop-loss"
            elif take_profit_triggered:
                action = "sell"
                quantity = self.portfolio["stock"]
                stop_loss = 0
                take_profit = 0
                executed_quantity = self.execute_trade(action, quantity, current_price)
                action_type = "take-profit"
            else:
                agent_output = self.agent(
                    ticker=self.ticker,
                    start_date=lookback_start,
                    end_date=current_date_str,
                    portfolio=self.portfolio,
                    show_reasoning=self.show_reasoning
                )

                action, quantity, stop_loss, take_profit = self.parse_action(agent_output)
                executed_quantity = self.execute_trade(action, quantity, current_price, stop_loss, take_profit)
                action_type = action

            # Update total portfolio value
            total_value = self.portfolio["cash"] + self.portfolio["stock"] * current_price
            self.portfolio["portfolio_value"] = total_value

            # Log the trade if executed
            if executed_quantity > 0 or action_type in ["stop-loss", "take-profit"]:
                self.log_trade(
                    current_date, action_type, executed_quantity, current_price,
                    self.portfolio["stop_loss"], self.portfolio["take_profit"]
                )

            # Log the current state
            print(
                f"{current_date.strftime('%Y-%m-%d'):<12} {self.ticker:<6} {action_type:<8} {executed_quantity:>8} "
                f"{current_price:>10.2f} {self.portfolio['stop_loss']:>10.2f} {self.portfolio['take_profit']:>10.2f} "
                f"{self.portfolio['cash']:>12.2f} {self.portfolio['stock']:>8} {total_value:>12.2f}"
            )

            # Record the portfolio value
            self.portfolio_values.append(
                {"Date": current_date, "Portfolio Value": total_value}
            )

        # Analyze trading performance
        self.analyze_trades()
        return self.analyze_performance()

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
        sharpe_ratio = (mean_daily_return / std_daily_return) * (252 ** 0.5)
        print(f"Sharpe Ratio: {sharpe_ratio:.2f}")

        # Calculate Maximum Drawdown
        rolling_max = performance_df["Portfolio Value"].cummax()
        drawdown = performance_df["Portfolio Value"] / rolling_max - 1
        max_drawdown = drawdown.min()
        print(f"Maximum Drawdown: {max_drawdown * 100:.2f}%")

        return performance_df
    
### 4. Run the Backtest #####
if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description='Run backtesting simulation')
        parser.add_argument('--ticker', type=str, required=True, help='Stock ticker symbol (e.g., AAPL)')
        parser.add_argument('--start-date', type=str, default=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'), help='Start date in YYYY-MM-DD format')
        parser.add_argument('--end-date', type=str, default=datetime.now().strftime('%Y-%m-%d'), help='End date in YYYY-MM-DD format')
        parser.add_argument('--initial-capital', type=float, default=100000, help='Initial capital amount (default: 100000)')
        parser.add_argument('--show-reasoning', action='store_true', help='Show reasoning from each agent')
        
        args = parser.parse_args()
        
        print(f"\nStarting backtest with following parameters:")
        print(f"Ticker: {args.ticker}")
        print(f"Start Date: {args.start_date}")
        print(f"End Date: {args.end_date}")
        print(f"Initial Capital: ${args.initial_capital:,.2f}")
        print(f"Show Reasoning: {args.show_reasoning}")
        
        # Create an instance of Backtester
        backtester = Backtester(
            agent=run_hedge_fund,
            ticker=args.ticker,
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            show_reasoning=args.show_reasoning
        )
        
        # Run the backtesting process
        print("\nRunning backtest...")
        performance_df = backtester.run_backtest()
        
    except Exception as e:
        import traceback
        print(f"\nError occurred during backtesting:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print("\nTraceback:")
        traceback.print_exc()
