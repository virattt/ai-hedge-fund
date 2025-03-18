from colorama import Fore, Style
from tabulate import tabulate
from .analysts import ANALYST_ORDER
import os


def sort_analyst_signals(signals):
    """Sort analyst signals in a consistent order."""
    # Create order mapping from ANALYST_ORDER
    analyst_order = {display: idx for idx, (display, _) in enumerate(ANALYST_ORDER)}
    analyst_order["Risk Management"] = len(ANALYST_ORDER)  # Add Risk Management at the end

    return sorted(signals, key=lambda x: analyst_order.get(x[0], 999))


def print_trading_output(result):
    """Print the trading decisions in a nicely formatted table."""
    decisions = result["decisions"]
    analyst_signals = result["analyst_signals"]
    
    # Print the analysis for each ticker
    for ticker in decisions:
        print(f"\nAnalysis for {Fore.GREEN}{ticker}{Style.RESET_ALL}")
        print("=" * 50)
        
        # Get the decision for this ticker
        decision = decisions[ticker]
        action = decision.get("action", "hold")
        quantity = decision.get("quantity", 0)
        confidence = decision.get("confidence")  # This might be None
        
        # Print the analyst signals
        ticker_signals = {}
        for agent_name, signals in analyst_signals.items():
            if ticker in signals:
                ticker_signals[agent_name] = signals[ticker]
        
        if ticker_signals:
            print(f"\n{Fore.CYAN}ANALYST SIGNALS: [{ticker}]{Style.RESET_ALL}")
            headers = ["Analyst", "Signal", "Confidence"]
            rows = []
            
            for agent_name, signal in ticker_signals.items():
                if "signal" in signal:
                    signal_color = Fore.GREEN if signal["signal"] == "bullish" else Fore.RED if signal["signal"] == "bearish" else Fore.YELLOW
                    signal_str = f"{signal_color}{signal['signal'].upper()}{Style.RESET_ALL}"
                    
                    confidence_str = "N/A"
                    if "confidence" in signal and signal["confidence"] is not None:
                        confidence_str = f"{Fore.YELLOW}{signal['confidence']:.1f}%{Style.RESET_ALL}"
                    
                    rows.append([agent_name, signal_str, confidence_str])
            
            print(tabulate(rows, headers=headers, tablefmt="grid"))
        
        # Print the final trading decision
        print(f"\n{Fore.CYAN}TRADING DECISION: [{ticker}]{Style.RESET_ALL}")
        
        # Format the action with color
        action_str = "HOLD"
        if action == "buy":
            action_str = f"{Fore.GREEN}BUY{Style.RESET_ALL}"
        elif action == "sell":
            action_str = f"{Fore.RED}SELL{Style.RESET_ALL}"
        elif action == "short":
            action_str = f"{Fore.MAGENTA}SHORT{Style.RESET_ALL}"
        elif action == "cover":
            action_str = f"{Fore.BLUE}COVER{Style.RESET_ALL}"
        elif action == "hold":
            action_str = f"{Fore.YELLOW}HOLD{Style.RESET_ALL}"
        
        # Format confidence with color if available
        confidence_str = "N/A"
        if confidence is not None:
            confidence_str = f"{Fore.YELLOW}{confidence:.1f}%{Style.RESET_ALL}"
        
        headers = ["Action", "Quantity", "Confidence"]
        rows = [[action_str, quantity, confidence_str]]
        print(tabulate(rows, headers=headers, tablefmt="grid"))


def print_backtest_results(table_rows: list) -> None:
    """Print the backtest results in a nicely formatted table"""
    # Clear the screen
    os.system("cls" if os.name == "nt" else "clear")

    # Split rows into ticker rows and summary rows
    ticker_rows = []
    summary_rows = []

    for row in table_rows:
        if isinstance(row[1], str) and "PORTFOLIO SUMMARY" in row[1]:
            summary_rows.append(row)
        else:
            ticker_rows.append(row)

    
    # Display latest portfolio summary
    if summary_rows:
        latest_summary = summary_rows[-1]
        print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")

        # Extract values and remove commas before converting to float
        cash_str = latest_summary[7].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")
        position_str = latest_summary[6].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")
        total_str = latest_summary[8].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")

        print(f"Cash Balance: {Fore.CYAN}${float(cash_str):,.2f}{Style.RESET_ALL}")
        print(f"Total Position Value: {Fore.YELLOW}${float(position_str):,.2f}{Style.RESET_ALL}")
        print(f"Total Value: {Fore.WHITE}${float(total_str):,.2f}{Style.RESET_ALL}")
        print(f"Return: {latest_summary[9]}")
        
        # Display performance metrics if available
        if latest_summary[10]:  # Sharpe ratio
            print(f"Sharpe Ratio: {latest_summary[10]}")
        if latest_summary[11]:  # Sortino ratio
            print(f"Sortino Ratio: {latest_summary[11]}")
        if latest_summary[12]:  # Max drawdown
            print(f"Max Drawdown: {latest_summary[12]}")

    # Add vertical spacing
    print("\n" * 2)

    # Print the table with just ticker rows
    print(
        tabulate(
            ticker_rows,
            headers=[
                "Date",
                "Ticker",
                "Action",
                "Quantity",
                "Price",
                "Shares",
                "Position Value",
                "Bullish",
                "Bearish",
                "Neutral",
            ],
            tablefmt="grid",
            colalign=(
                "left",  # Date
                "left",  # Ticker
                "center",  # Action
                "right",  # Quantity
                "right",  # Price
                "right",  # Shares
                "right",  # Position Value
                "right",  # Bullish
                "right",  # Bearish
                "right",  # Neutral
            ),
        )
    )

    # Add vertical spacing
    print("\n" * 4)


def format_backtest_row(
    date: str,
    ticker: str,
    action: str,
    quantity: float,
    price: float,
    shares_owned: float,
    position_value: float,
    bullish_count: int,
    bearish_count: int,
    neutral_count: int,
    is_summary: bool = False,
    total_value: float = None,
    return_pct: float = None,
    cash_balance: float = None,
    total_position_value: float = None,
    sharpe_ratio: float = None,
    sortino_ratio: float = None,
    max_drawdown: float = None,
) -> list[any]:
    """Format a row for the backtest results table"""
    # Color the action
    action_color = {
        "BUY": Fore.GREEN,
        "COVER": Fore.GREEN,
        "SELL": Fore.RED,
        "SHORT": Fore.RED,
        "HOLD": Fore.YELLOW,
    }.get(action.upper(), Fore.WHITE)

    if is_summary:
        return_color = Fore.GREEN if return_pct >= 0 else Fore.RED
        return [
            date,
            f"{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY{Style.RESET_ALL}",
            "",  # Action
            "",  # Quantity
            "",  # Price
            "",  # Shares
            f"{Fore.YELLOW}${total_position_value:,.2f}{Style.RESET_ALL}",  # Total Position Value
            f"{Fore.CYAN}${cash_balance:,.2f}{Style.RESET_ALL}",  # Cash Balance
            f"{Fore.WHITE}${total_value:,.2f}{Style.RESET_ALL}",  # Total Value
            f"{return_color}{return_pct:+.2f}%{Style.RESET_ALL}",  # Return
            f"{Fore.YELLOW}{sharpe_ratio:.2f}{Style.RESET_ALL}" if sharpe_ratio is not None else "",  # Sharpe Ratio
            f"{Fore.YELLOW}{sortino_ratio:.2f}{Style.RESET_ALL}" if sortino_ratio is not None else "",  # Sortino Ratio
            f"{Fore.RED}{max_drawdown:.2f}%{Style.RESET_ALL}" if max_drawdown is not None else "",  # Max Drawdown
        ]
    else:
        return [
            date,
            f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
            f"{action_color}{action.upper()}{Style.RESET_ALL}",
            f"{action_color}{quantity:,.0f}{Style.RESET_ALL}",
            f"{Fore.WHITE}{price:,.2f}{Style.RESET_ALL}",
            f"{Fore.WHITE}{shares_owned:,.0f}{Style.RESET_ALL}",
            f"{Fore.YELLOW}{position_value:,.2f}{Style.RESET_ALL}",
            f"{Fore.GREEN}{bullish_count}{Style.RESET_ALL}",
            f"{Fore.RED}{bearish_count}{Style.RESET_ALL}",
            f"{Fore.BLUE}{neutral_count}{Style.RESET_ALL}",
        ]
