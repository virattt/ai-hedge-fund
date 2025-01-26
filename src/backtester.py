from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
import os
import questionary
import matplotlib.pyplot as plt
import pandas as pd
import random
from supabase import create_client, Client
from colorama import Fore, Style, init

from utils.analysts import ANALYST_ORDER
from main import run_hedge_fund
from tools.api import (
    get_company_news,
    get_price_data,
    get_prices,
    get_financial_metrics,
    get_insider_trades,
    search_line_items,
)
from utils.display import print_backtest_results, format_backtest_row


# Load environment variables from .env file
load_dotenv()

# Retrieve Supabase URL and Key from environment variables
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

# Initialize Supabase client
supabase: Client = create_client(url, key)
supabase.postgrest.auth(token=key)

init(autoreset=True)

def get_stored_data(supabase, ticker, start_date, end_date):
    """Retrieve stored backtest records and analyst signals for a date range"""
    backtest_data = supabase.table('backtest_records')\
        .select('*')\
        .gte('date', start_date)\
        .lte('date', end_date)\
        .eq('ticker', ticker)\
        .execute()
    
    analyst_signals = supabase.table('analyst_signals')\
        .select('*')\
        .gte('date', start_date)\
        .lte('date', end_date)\
        .eq('ticker', ticker)\
        .execute()
    
    return backtest_data.data, analyst_signals.data

def reconstruct_portfolio_state(stored_data, initial_capital):
    """Reconstruct portfolio state from stored data"""
    if not stored_data:
        return None
    
    latest_record = max(stored_data, key=lambda x: x['date'])
    return {
        "cash": latest_record['cash_balance'],
        "positions": {latest_record['ticker']: latest_record['shares_owned']},
        "realized_gains": {latest_record['ticker']: 0},  # We can't reconstruct this
        "cost_basis": {latest_record['ticker']: latest_record['shares_owned'] * latest_record['price'] if latest_record['shares_owned'] > 0 else 0}
    }

def store_backtest_record(supabase, record):
    """Store a single backtest record"""
    try:
        print(f"Attempting to store record: {record}")  # Debug log
        response = supabase.table('backtest_records').upsert(record).execute()
        print(f"Storage response: {response}")  # Debug log
        return True
    except Exception as e:
        print(f"Error storing backtest record: {e}")
        return False

def store_analyst_signals(supabase, date, ticker, signals):
    """Store analyst signals"""
    for analyst, signal_data in signals.items():
        record = {
            'date': date,
            'ticker': ticker,
            'analyst': analyst,
            'signal': signal_data.get('signal', 'unknown'),
            'confidence': signal_data.get('confidence', 0)
        }
        try:
            print(f"Attempting to store signal: {record}")  # Debug log
            response = supabase.table('analyst_signals').upsert(record).execute()
            print(f"Signal storage response: {response}")  # Debug log
        except Exception as e:
            print(f"Error storing analyst signal: {e}")

def check_existing_data(supabase, date, ticker):
    """Check if data exists for given date and ticker"""
    response = supabase.table('backtest_records').select('*')\
        .eq('date', date)\
        .eq('ticker', ticker)\
        .execute()
    return len(response.data) > 0

def verify_tables():
    random_number_string = str(random.randint(1, 9000))
    try:
        test_record = {
            'date': '2025-01-01',
            'ticker': random_number_string,
            'action': random_number_string,
            'quantity': 0,
            'price': 0,
            'shares_owned': 0,
            'position_value': 0,
            'bullish_count': 0,
            'bearish_count': 0,
            'neutral_count': 0,
            'total_value': 0,
            'return_pct': 0,
            'cash_balance': 0,
            'total_position_value': 0
        }
        response = supabase.table('backtest_records').upsert(test_record).execute()
        print("Database tables verified")
        return True
    except Exception as e:
        print(f"Database table verification failed: {e}")
        return False

if not verify_tables():
    raise Exception("Database tables not properly configured")

def store_analyst_signals(supabase, date, ticker, signals):
    """Store analyst signals"""
    for analyst, signal_data in signals.items():
        record = {
            'date': date,
            'ticker': ticker,
            'analyst': analyst,
            'signal': signal_data.get('signal', 'unknown'),
            'confidence': signal_data.get('confidence', 0)
        }
        try:
            supabase.table('analyst_signals').upsert(record).execute()
        except Exception as e:
            print(f"Error storing analyst signal: {e}")

class Backtester:
    def __init__(
        self,
        agent,
        tickers: list[str],
        start_date,
        end_date,
        initial_capital,
        selected_analysts=None,
        supabase=None
    ):
        self.agent = agent
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.selected_analysts = selected_analysts
        self.supabase = supabase
        self.portfolio = {
            "cash": initial_capital,
            "positions": {ticker: 0 for ticker in tickers},
            "realized_gains": {ticker: 0 for ticker in tickers},
            "cost_basis": {ticker: 0 for ticker in tickers},
        }
        self.portfolio_values = []

    def prefetch_data(self):
        """Pre-fetch all data needed for the backtest period."""
        print("\nPre-fetching data for the entire backtest period...")

        end_date_dt = datetime.strptime(self.end_date, "%Y-%m-%d")
        start_date_dt = end_date_dt - relativedelta(years=1)
        start_date_str = start_date_dt.strftime("%Y-%m-%d")

        for ticker in self.tickers:
            get_prices(ticker, start_date_str, self.end_date)
            get_financial_metrics(ticker, self.end_date, limit=10)
            get_insider_trades(ticker, self.end_date, start_date=self.start_date, limit=1000)
            get_company_news(ticker, self.end_date, start_date=self.start_date, limit=1000)
            search_line_items(
                ticker,
                [
                    "free_cash_flow",
                    "net_income",
                    "depreciation_and_amortization",
                    "capital_expenditure",
                    "working_capital",
                ],
                self.end_date,
                period="ttm",
                limit=2,
            )

        print("Data pre-fetch complete.")

    def parse_agent_response(self, agent_output):
        try:
            import json
            decision = json.loads(agent_output)
            return decision
        except:
            print(f"Error parsing action: {agent_output}")
            return "hold", 0

    def execute_trade(self, ticker: str, action: str, quantity: float, current_price: float):
        """Validate and execute trades based on portfolio constraints"""
        if action == "buy" and quantity > 0:
            cost = quantity * current_price
            if cost <= self.portfolio["cash"]:
                old_shares = self.portfolio["positions"][ticker]
                old_cost_basis = self.portfolio["cost_basis"][ticker]
                new_shares = quantity
                new_cost = cost

                total_shares = old_shares + new_shares
                if total_shares > 0:
                    self.portfolio["cost_basis"][ticker] = ((old_cost_basis * old_shares) + (new_cost * new_shares)) / total_shares

                self.portfolio["positions"][ticker] += quantity
                self.portfolio["cash"] -= cost

                return quantity
            else:
                max_quantity = self.portfolio["cash"] // current_price
                if max_quantity > 0:
                    old_shares = self.portfolio["positions"][ticker]
                    old_cost_basis = self.portfolio["cost_basis"][ticker]
                    new_shares = max_quantity
                    new_cost = max_quantity * current_price

                    total_shares = old_shares + new_shares
                    if total_shares > 0:
                        self.portfolio["cost_basis"][ticker] = ((old_cost_basis * old_shares) + (new_cost * new_shares)) / total_shares

                    self.portfolio["positions"][ticker] += max_quantity
                    self.portfolio["cash"] -= new_cost

                    return max_quantity
                return 0
        elif action == "sell" and quantity > 0:
            quantity = min(quantity, self.portfolio["positions"][ticker])
            if quantity > 0:
                avg_cost_per_share = self.portfolio["cost_basis"][ticker] / self.portfolio["positions"][ticker] if self.portfolio["positions"][ticker] > 0 else 0
                realized_gain = (current_price - avg_cost_per_share) * quantity
                self.portfolio["realized_gains"][ticker] += realized_gain

                self.portfolio["positions"][ticker] -= quantity
                self.portfolio["cash"] += quantity * current_price

                if self.portfolio["positions"][ticker] > 0:
                    remaining_ratio = (self.portfolio["positions"][ticker] - quantity) / self.portfolio["positions"][ticker]
                    self.portfolio["cost_basis"][ticker] *= remaining_ratio
                else:
                    self.portfolio["cost_basis"][ticker] = 0

                return quantity
            return 0
        return 0

    def run_backtest(self):
        self.prefetch_data()
        dates = pd.date_range(self.start_date, self.end_date, freq="B")
        table_rows = []

        print("\nStarting backtest...")

        # Check for existing data for each ticker
        for ticker in self.tickers:
            stored_backtest, stored_signals = get_stored_data(
                self.supabase, 
                ticker, 
                self.start_date, 
                self.end_date
            )
            
            if stored_backtest:
                print(f"Found existing data for {ticker}")
                # Filter and use stored data
                filtered_records = [{
                    'date': record['date'],
                    'ticker': record['ticker'],
                    'action': record['action'],
                    'quantity': record['quantity'],
                    'price': record['price'],
                    'shares_owned': record['shares_owned'],
                    'position_value': record['position_value'],
                    'bullish_count': record['bullish_count'],
                    'bearish_count': record['bearish_count'],
                    'neutral_count': record['neutral_count'],
                    'total_value': record['total_value'],
                    'return_pct': record['return_pct'],
                    'cash_balance': record['cash_balance'],
                    'total_position_value': record['total_position_value']
                } for record in stored_backtest]
                
                # Reconstruct portfolio state
                reconstructed_portfolio = reconstruct_portfolio_state(stored_backtest, self.initial_capital)
                if reconstructed_portfolio:
                    self.portfolio = reconstructed_portfolio
                    table_rows.extend([format_backtest_row(**record) for record in filtered_records])
                    continue

            # Process new dates for this ticker
            for current_date in dates:
                lookback_start = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
                current_date_str = current_date.strftime("%Y-%m-%d")

                # Skip if data exists for this date
                if self.supabase and check_existing_data(self.supabase, current_date_str, ticker):
                    continue

                output = self.agent(
                    tickers=[ticker],  # Process one ticker at a time
                    start_date=lookback_start,
                    end_date=current_date_str,
                    portfolio=self.portfolio,
                    selected_analysts=self.selected_analysts,
                )

                decisions = output["decisions"]
                analyst_signals = output["analyst_signals"]

                executed_trades = {}
                decision = decisions.get(ticker, {"action": "hold", "quantity": 0})
                action, quantity = decision.get("action", "hold"), decision.get("quantity", 0)

                df = get_price_data(ticker, lookback_start, current_date_str)
                current_price = df.iloc[-1]["close"]

                executed_quantity = self.execute_trade(ticker, action, quantity, current_price)
                executed_trades[ticker] = executed_quantity

                total_value = self.portfolio["cash"]
                for t in self.tickers:
                    df = get_price_data(t, lookback_start, current_date_str)
                    current_price = df.iloc[-1]["close"]

                    shares_owned = self.portfolio["positions"][t]
                    position_value = shares_owned * current_price
                    total_value += position_value

                    ticker_signals = {}
                    for agent, signals in analyst_signals.items():
                        if t in signals:
                            ticker_signals[agent] = signals[t]

                    bullish_count = len([s for s in ticker_signals.values() if s.get("signal", "").lower() == "bullish"])
                    bearish_count = len([s for s in ticker_signals.values() if s.get("signal", "").lower() == "bearish"])
                    neutral_count = len([s for s in ticker_signals.values() if s.get("signal", "").lower() == "neutral"])

                    decision = decisions.get(t, {"action": "hold", "quantity": 0})
                    action = decision.get("action", None)
                    quantity = executed_trades.get(t, None)

                    row = format_backtest_row(
                        date=current_date_str,
                        ticker=t,
                        action=action,
                        quantity=quantity,
                        price=current_price,
                        shares_owned=shares_owned,
                        position_value=position_value,
                        bullish_count=bullish_count,
                        bearish_count=bearish_count,
                        neutral_count=neutral_count,
                        total_value=total_value,
                        return_pct=((total_value + sum(self.portfolio["realized_gains"].values())) / self.initial_capital - 1) * 100,
                        cash_balance=self.portfolio["cash"],
                        total_position_value=total_value - self.portfolio["cash"]
                    )
                    table_rows.append(row)

                    # Store data
                    if self.supabase:
                        store_analyst_signals(self.supabase, current_date_str, t, analyst_signals)
                        record = {
                            'date': current_date_str,
                            'ticker': t,
                            'action': action,
                            'quantity': quantity,
                            'price': current_price,
                            'shares_owned': shares_owned,
                            'position_value': position_value,
                            'bullish_count': bullish_count,
                            'bearish_count': bearish_count,
                            'neutral_count': neutral_count,
                            'total_value': total_value,
                            'return_pct': ((total_value + sum(self.portfolio["realized_gains"].values())) / self.initial_capital - 1) * 100,
                            'cash_balance': self.portfolio["cash"],
                            'total_position_value': total_value - self.portfolio["cash"]
                        }
                        store_backtest_record(self.supabase, record)

        # Update portfolio values for performance tracking
        # Extract portfolio values from stored data
        unique_dates = sorted(set(row['date'] for row in filtered_records))
        self.portfolio_values = []
        
        for date in unique_dates:
            records_for_date = [r for r in filtered_records if r['date'] == date]
            if records_for_date:
                self.portfolio_values.append({
                    "Date": pd.to_datetime(date),
                    "Portfolio Value": float(records_for_date[0]['total_value'])
                })
        
        print_backtest_results(table_rows)

    def analyze_performance(self):
        performance_df = pd.DataFrame(self.portfolio_values).set_index("Date")
        final_portfolio_value = performance_df["Portfolio Value"].iloc[-1]
        total_realized_gains = sum(self.portfolio["realized_gains"].values())
        total_return = ((final_portfolio_value - self.initial_capital) / self.initial_capital) * 100

        print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO PERFORMANCE SUMMARY:{Style.RESET_ALL}")
        print(f"Total Return: {Fore.GREEN if total_return >= 0 else Fore.RED}{total_return:.2f}%{Style.RESET_ALL}")
        print(f"Total Realized Gains/Losses: {Fore.GREEN if total_realized_gains >= 0 else Fore.RED}${total_realized_gains:,.2f}{Style.RESET_ALL}")

        plt.figure(figsize=(12, 6))
        plt.plot(performance_df.index, performance_df["Portfolio Value"], color="blue")
        plt.title("Portfolio Value Over Time")
        plt.ylabel("Portfolio Value ($)")
        plt.xlabel("Date")
        plt.grid(True)
        plt.show()

        performance_df["Daily Return"] = performance_df["Portfolio Value"].pct_change()
        mean_daily_return = performance_df["Daily Return"].mean()
        std_daily_return = performance_df["Daily Return"].std()
        sharpe_ratio = (mean_daily_return / std_daily_return) * (252**0.5) if std_daily_return != 0 else 0
        print(f"\nSharpe Ratio: {Fore.YELLOW}{sharpe_ratio:.2f}{Style.RESET_ALL}")

        rolling_max = performance_df["Portfolio Value"].cummax()
        drawdown = performance_df["Portfolio Value"] / rolling_max - 1
        max_drawdown = drawdown.min()
        print(f"Maximum Drawdown: {Fore.RED}{max_drawdown * 100:.2f}%{Style.RESET_ALL}")

        return performance_df



### 4. Run the Backtest #####
if __name__ == "__main__":
    import argparse

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Run backtesting simulation")
    parser.add_argument(
        "--tickers",
        type=str,
        required=False,
        help="Comma-separated list of stock ticker symbols (e.g., AAPL,MSFT,GOOGL)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=(datetime.now() - relativedelta(months=12)).strftime("%Y-%m-%d"),
        help="Start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=100000,
        help="Initial capital amount (default: 100000)",
    )

    args = parser.parse_args()

    # Parse tickers from comma-separated string
    tickers = [ticker.strip() for ticker in args.tickers.split(",")]
    # tickers = ["AAPL"]
    selected_analysts = None
    choices = questionary.checkbox(
        "Use the Space bar to select/unselect analysts.",
        choices=[questionary.Choice(display, value=value) for display, value in ANALYST_ORDER],
        instruction="\n\nPress 'a' to toggle all.\n\nPress Enter when done to run the hedge fund.",
        validate=lambda x: len(x) > 0 or "You must select at least one analyst.",
        style=questionary.Style(
            [
                ("checkbox-selected", "fg:green"),
                ("selected", "fg:green noinherit"),
                ("highlighted", "noinherit"),
                ("pointer", "noinherit"),
            ]
        ),
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
    tickers=tickers,
    start_date=args.start_date,
    end_date=args.end_date,
    initial_capital=args.initial_capital,
    selected_analysts=selected_analysts,
    supabase=supabase  # Add this line
    )

    # Run the backtesting process
    backtester.run_backtest()
    performance_df = backtester.analyze_performance()
