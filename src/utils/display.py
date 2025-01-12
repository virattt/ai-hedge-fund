
from colorama import Fore, Style
from tabulate import tabulate
from .analysts import ANALYST_ORDER
from models.outputs import RootResultModel, Signal_Type

SIGNAL_COLOR_MAP: dict[Signal_Type, Fore] = {
    "bullish": Fore.GREEN,
    "bearish": Fore.RED,
    "neutral": Fore.YELLOW,
}


def print_trading_output(result: RootResultModel) -> None:
    """
    Print formatted trading results with colored tables.

    Args:
        result (RootResultModel): Root result model
    """
    decision = result.decision
    if not decision:
        print(f"{Fore.RED}No trading decision available{Style.RESET_ALL}")
        return

    # Prepare analyst signals table
    table_data = []
    for agent in result.analyst_signals.signals:
        signal_color = SIGNAL_COLOR_MAP.get(agent.signal, Fore.WHITE)

        confidence_formatted = f"{agent.confidence:.1f}%" if agent.confidence else "-"
        table_data.append(
            [
                f"{Fore.CYAN}{str(agent)}{Style.RESET_ALL}",
                f"{signal_color}{agent.signal.upper()}{Style.RESET_ALL}",
                f"{Fore.YELLOW}{confidence_formatted}{Style.RESET_ALL}",
            ]
        )

    # Sort the signals according to the predefined order
    table_data = _sort_analyst_signals(table_data)

    print(f"\n{Fore.WHITE}{Style.BRIGHT}ANALYST SIGNALS:{Style.RESET_ALL}")
    print(
        tabulate(
            table_data,
            headers=[f"{Fore.WHITE}Analyst", "Signal", "Confidence"],
            tablefmt="grid",
            colalign=("left", "center", "right"),
        )
    )

    # Print Trading Decision Table
    action = decision.action.upper()
    action_color = {"BUY": Fore.GREEN, "SELL": Fore.RED, "HOLD": Fore.YELLOW}.get(
        action, Fore.WHITE
    )

    decision_data = [
        ["Action", f"{action_color}{action}{Style.RESET_ALL}"],
        ["Quantity", f"{action_color}{decision.quantity}{Style.RESET_ALL}"],
        [
            "Confidence",
            f"{Fore.YELLOW}{decision.confidence:.1f}%{Style.RESET_ALL}",
        ],
    ]

    print(f"\n{Fore.WHITE}{Style.BRIGHT}TRADING DECISION:{Style.RESET_ALL}")
    print(tabulate(decision_data, tablefmt="grid", colalign=("left", "right")))

    # Print Reasoning
    print(
        f"\n{Fore.WHITE}{Style.BRIGHT}Reasoning:{Style.RESET_ALL} {Fore.CYAN}{decision.reasoning}{Style.RESET_ALL}"
    )

def print_backtest_results(table_rows: list[list], clear_screen: bool = True) -> None:
    """
    Print formatted backtest results with colored tables.

    Args:
        table_rows (list[list]): List of rows containing backtest data
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
    if clear_screen:
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
) -> list:
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


def _sort_analyst_signals(signals: list[list[str]]) -> list[list[str]]:
    """Sort analyst signals in a consistent order."""
    # Create order mapping from ANALYST_ORDER
    analyst_order = {display: idx for idx, (display, _) in enumerate(ANALYST_ORDER)}

    return sorted(signals, key=lambda x: analyst_order.get(x[0], 999))
