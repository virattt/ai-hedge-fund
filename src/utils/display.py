from colorama import Fore, Style
from tabulate import tabulate
from .analysts import ANALYST_ORDER

def sort_analyst_signals(signals):
    """Sort analyst signals in a consistent order."""
    # Create order mapping from ANALYST_ORDER
    analyst_order = {display: idx for idx, (display, _) in enumerate(ANALYST_ORDER)}
    analyst_order['Risk Management'] = len(ANALYST_ORDER)  # Add Risk Management at the end

    return sorted(signals, key=lambda x: analyst_order.get(x[0], 999))

def print_trading_output(result: dict) -> None:
    """
    Print formatted trading results with colored tables for multiple tickers.

    Args:
        result (dict): Dictionary containing decisions and analyst signals for multiple tickers
    """
    decisions = result.get("decisions")
    if not decisions:
        print(f"{Fore.RED}No trading decisions available{Style.RESET_ALL}")
        return

    # Print decisions for each ticker
    for ticker, decision in decisions.items():
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Analysis for {Fore.CYAN}{ticker}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}")

        # Prepare analyst signals table for this ticker
        table_data = []
        for agent, signals in result.get("analyst_signals", {}).items():
            if ticker not in signals:
                continue
                
            signal = signals[ticker]
            agent_name = agent.replace("_agent", "").replace("_", " ").title()
            signal_type = signal.get("signal", "").upper()

            signal_color = {
                "BULLISH": Fore.GREEN,
                "BEARISH": Fore.RED,
                "NEUTRAL": Fore.YELLOW,
            }.get(signal_type, Fore.WHITE)

            table_data.append(
                [
                    f"{Fore.CYAN}{agent_name}{Style.RESET_ALL}",
                    f"{signal_color}{signal_type}{Style.RESET_ALL}",
                    f"{Fore.YELLOW}{signal.get('confidence')}%{Style.RESET_ALL}",
                ]
            )

        # Sort the signals according to the predefined order
        table_data = sort_analyst_signals(table_data)

        print(f"\n{Fore.WHITE}{Style.BRIGHT}ANALYST SIGNALS:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(
            tabulate(
                table_data,
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

        print(f"\n{Fore.WHITE}{Style.BRIGHT}TRADING DECISION:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(tabulate(decision_data, tablefmt="grid", colalign=("left", "right")))

        # Print Reasoning
        print(
            f"\n{Fore.WHITE}{Style.BRIGHT}Reasoning:{Style.RESET_ALL} {Fore.CYAN}{decision.get('reasoning')}{Style.RESET_ALL}"
        )

    # Print Portfolio Summary
    print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")
    portfolio_data = []
    for ticker, decision in decisions.items():
        action = decision.get("action", "").upper()
        action_color = {"BUY": Fore.GREEN, "SELL": Fore.RED, "HOLD": Fore.YELLOW}.get(
            action, Fore.WHITE
        )
        portfolio_data.append(
            [
                f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
                f"{action_color}{action}{Style.RESET_ALL}",
                f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}",
                f"{Fore.YELLOW}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
            ]
        )

    print(
        tabulate(
            portfolio_data,
            headers=[
                f"{Fore.WHITE}Ticker",
                "Action",
                "Quantity",
                "Confidence"
            ],
            tablefmt="grid",
            colalign=("left", "center", "right", "right"),
        )
    )


def print_backtest_results(table_rows: list[list[any]], clear_screen: bool = True) -> None:
    """
    Print formatted backtest results with colored tables.

    Args:
        table_rows (list[list[any]]): List of rows containing backtest data
        clear_screen (bool): Whether to clear the screen before printing
    """
    headers = [
        "Date",
        "Ticker",
        "Action",
        "Quantity",
        "Price",
        "Position Value",
        "Cash",
        "Total Value",
        "Return %",
        "Signals (B/S/N)",
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
    position_value: float,
    cash: float,
    total_value: float,
    return_pct: float,
    bullish_count: int,
    bearish_count: int,
    neutral_count: int,
) -> list[any]:
    """
    Format a single row of backtest data with appropriate colors.

    Args:
        date (str): The date of the trade
        ticker (str): The stock ticker
        action (str): The trading action (buy/sell/hold)
        quantity (float): The quantity traded
        price (float): The stock price
        position_value (float): Value of the current position
        cash (float): Available cash
        total_value (float): Total portfolio value
        return_pct (float): Percentage return
        bullish_count (int): Number of bullish signals
        bearish_count (int): Number of bearish signals
        neutral_count (int): Number of neutral signals

    Returns:
        list[any]: Formatted row with color codes
    """
    action_color = {"buy": Fore.GREEN, "sell": Fore.RED, "hold": Fore.YELLOW}.get(
        action.lower(), ""
    )
    
    return_color = Fore.GREEN if return_pct >= 0 else Fore.RED

    return [
        date,
        f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
        f"{action_color}{action}{Style.RESET_ALL}",
        f"{action_color}{quantity}{Style.RESET_ALL}",
        f"{Fore.WHITE}{price:.2f}{Style.RESET_ALL}",
        f"{Fore.WHITE}{position_value:.2f}{Style.RESET_ALL}",
        f"{Fore.YELLOW}{cash:.2f}{Style.RESET_ALL}",
        f"{Fore.YELLOW}{total_value:.2f}{Style.RESET_ALL}",
        f"{return_color}{return_pct:+.2f}%{Style.RESET_ALL}",
        f"{Fore.GREEN}{bullish_count}{Style.RESET_ALL}/{Fore.RED}{bearish_count}{Style.RESET_ALL}/{Fore.BLUE}{neutral_count}{Style.RESET_ALL}",
    ]
