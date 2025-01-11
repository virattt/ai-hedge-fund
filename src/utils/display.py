from colorama import Fore, Style
from tabulate import tabulate
from typing import List, Dict
from ..main import ANALYST_ORDER

def sort_analyst_signals(signals):
    """Sort analyst signals in a consistent order."""
    # Create order mapping from ANALYST_ORDER
    analyst_order = {display: idx for idx, (display, _) in enumerate(ANALYST_ORDER)}
    analyst_order['Risk Management'] = len(ANALYST_ORDER)  # Add Risk Management at the end

    return sorted(signals, key=lambda x: analyst_order.get(x[0], 999))

def print_trading_output(result: dict) -> None:
    """
    Print formatted trading results with colored tables.

    Args:
        result (dict): Dictionary containing decision and analyst signals
    """
    decision = result.get("decision")
    if not decision:
        print(f"{Fore.RED}No trading decision available{Style.RESET_ALL}")
        return

    # Prepare analyst signals table
    analyst_signals = []
    for agent, signal in result.get("analyst_signals", {}).items():
        agent_name = agent.replace("_agent", "").replace("_", " ").title()
        signal_type = signal.get("signal", "").upper()

        signal_color = {
            "BULLISH": Fore.GREEN,
            "BEARISH": Fore.RED,
            "NEUTRAL": Fore.YELLOW,
        }.get(signal_type, Fore.WHITE)

        analyst_signals.append(
            [
                f"{Fore.CYAN}{agent_name}{Style.RESET_ALL}",
                f"{signal_color}{signal_type}{Style.RESET_ALL}",
                f"{Fore.YELLOW}{signal.get('confidence')}%{Style.RESET_ALL}",
            ]
        )

    # Sort the signals according to the predefined order
    analyst_signals = sort_analyst_signals(analyst_signals)

    print(f"\n{Fore.WHITE}{Style.BRIGHT}ANALYST SIGNALS:{Style.RESET_ALL}")
    print(
        tabulate(
            analyst_signals,
            headers=[f"{Fore.WHITE}Analyst", "Signal", "Confidence"],
            tablefmt="grid",
            colalign=("left", "center", "right"),
        )
    )

    # Print Trading Decision Table
    action = decision.get("action", "").upper()
    action_color = {"BUY": Fore.GREEN, "SELL": Fore.RED, "HOLD": Fore.YELLOW}.get(
        action, Fore.WHITE
    )

    decision_data = [
        ["Action", f"{action_color}{action}{Style.RESET_ALL}"],
        ["Quantity", f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}"],
        [
            "Confidence",
            f"{Fore.YELLOW}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
        ],
    ]

    print(f"\n{Fore.WHITE}{Style.BRIGHT}TRADING DECISION:{Style.RESET_ALL}")
    print(tabulate(decision_data, tablefmt="grid", colalign=("left", "right")))

    # Print Reasoning
    print(
        f"\n{Fore.WHITE}{Style.BRIGHT}Reasoning:{Style.RESET_ALL} {Fore.CYAN}{decision.get('reasoning')}{Style.RESET_ALL}"
    )


def print_backtest_results(table_rows: List[List], clear_screen: bool = True) -> None:
    """
    Print formatted backtest results with colored tables.

    Args:
        table_rows (List[List]): List of rows containing backtest data
        clear_screen (bool): Whether to clear the screen before printing
    """
    headers = [
        "Date",
        "Ticker",
        "Action",
        "Quantity",
        "Price",
        "Cash",
        "Stock",
        "Total Value",
        "Bullish",
        "Bearish",
        "Neutral",
    ]

    # Clear screen if requested
    if (clear_screen):
        print("\033[H\033[J")

    # Display colored table
    print(f"{tabulate(table_rows, headers=headers, tablefmt='grid')}{Style.RESET_ALL}")


def format_backtest_row(
    date: str,
    ticker: str,
    action: str,
    quantity: float,
    price: float,
    cash: float,
    stock: int,
    total_value: float,
    bullish_count: int,
    bearish_count: int,
    neutral_count: int,
) -> List:
    """
    Format a single row of backtest data with appropriate colors.

    Args:
        date (str): The date of the trade
        ticker (str): The stock ticker
        action (str): The trading action (buy/sell/hold)
        quantity (float): The quantity traded
        price (float): The stock price
        cash (float): Available cash
        stock (int): Stock position
        total_value (float): Total portfolio value
        bullish_count (int): Number of bullish signals
        bearish_count (int): Number of bearish signals
        neutral_count (int): Number of neutral signals

    Returns:
        List: Formatted row with color codes
    """
    action_color = {"buy": Fore.GREEN, "sell": Fore.RED, "hold": Fore.YELLOW}.get(
        action.lower(), ""
    )

    return [
        date,
        f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
        f"{action_color}{action}{Style.RESET_ALL}",
        f"{action_color}{quantity}{Style.RESET_ALL}",
        f"{Fore.WHITE}{price:.2f}{Style.RESET_ALL}",
        f"{Fore.YELLOW}{cash:.2f}{Style.RESET_ALL}",
        f"{Fore.WHITE}{stock}{Style.RESET_ALL}",
        f"{Fore.YELLOW}{total_value:.2f}{Style.RESET_ALL}",
        f"{Fore.GREEN}{bullish_count}{Style.RESET_ALL}",
        f"{Fore.RED}{bearish_count}{Style.RESET_ALL}",
        f"{Fore.BLUE}{neutral_count}{Style.RESET_ALL}",
    ]
