from colorama import Fore, Style
from tabulate import tabulate
from .analysts import ANALYST_ORDER
import os
import json


def sort_agent_signals(signals):
    """Sort agent signals in a consistent order."""
    # Create order mapping from ANALYST_ORDER
    analyst_order = {display: idx for idx, (display, _) in enumerate(ANALYST_ORDER)}
    analyst_order["Risk Management"] = len(ANALYST_ORDER)  # Add Risk Management at the end

    return sorted(signals, key=lambda x: analyst_order.get(x[0], 999))


def print_trading_output(result: dict) -> None:
    """
    Print formatted trading results with colored tables for multiple tickers.
    Handles missing/empty data gracefully.
    """
    if not result or not isinstance(result, dict):
        print(f"{Fore.RED}No result data available{Style.RESET_ALL}")
        return

    decisions = result.get("decisions") or {}
    analyst_signals = result.get("analyst_signals") or {}

    if not decisions:
        print(f"{Fore.RED}No trading decisions available{Style.RESET_ALL}")
        return

    for ticker, decision in decisions.items():
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Analysis for {Fore.CYAN}{ticker}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}")

        table_data = []
        for agent, signals in analyst_signals.items():
            if not isinstance(signals, dict) or ticker not in signals:
                continue
            if agent == "risk_management_agent":
                continue

            signal = signals[ticker] or {}
            agent_name = agent.replace("_agent", "").replace("_", " ").title()
            signal_type = (signal.get("signal") or "").upper()
            confidence = signal.get("confidence") or 0

            signal_color = {
                "BULLISH": Fore.GREEN,
                "BEARISH": Fore.RED,
                "NEUTRAL": Fore.YELLOW,
            }.get(signal_type, Fore.WHITE)

            reasoning_str = ""
            reasoning = signal.get("reasoning")
            if reasoning:
                if isinstance(reasoning, str):
                    reasoning_str = reasoning
                elif isinstance(reasoning, dict):
                    reasoning_str = json.dumps(reasoning, indent=2)
                else:
                    reasoning_str = str(reasoning)

                # wrap text
                wrapped_reasoning = ""
                current_line = ""
                max_line_length = 60
                for word in reasoning_str.split():
                    if len(current_line) + len(word) + 1 > max_line_length:
                        wrapped_reasoning += current_line + "\n"
                        current_line = word
                    else:
                        current_line = (current_line + " " + word) if current_line else word
                if current_line:
                    wrapped_reasoning += current_line
                reasoning_str = wrapped_reasoning

            table_data.append(
                [
                    f"{Fore.CYAN}{agent_name}{Style.RESET_ALL}",
                    f"{signal_color}{signal_type}{Style.RESET_ALL}",
                    f"{Fore.WHITE}{confidence}%{Style.RESET_ALL}",
                    f"{Fore.WHITE}{reasoning_str}{Style.RESET_ALL}",
                ]
            )

        table_data = sort_agent_signals(table_data)

        if table_data:
            print(f"\n{Fore.WHITE}{Style.BRIGHT}AGENT ANALYSIS:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
            print(
                tabulate(
                    table_data,
                    headers=[f"{Fore.WHITE}Agent", "Signal", "Confidence", "Reasoning"],
                    tablefmt="grid",
                    colalign=("left", "center", "right", "left"),
                )
            )

        action = (decision.get("action") or "").upper()
        action_color = {
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN,
            "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)

        reasoning = decision.get("reasoning") or ""
        wrapped_reasoning = ""
        current_line = ""
        max_line_length = 60
        for word in str(reasoning).split():
            if len(current_line) + len(word) + 1 > max_line_length:
                wrapped_reasoning += current_line + "\n"
                current_line = word
            else:
                current_line = (current_line + " " + word) if current_line else word
        if current_line:
            wrapped_reasoning += current_line

        quantity = decision.get("quantity") or "N/A"
        confidence_val = decision.get("confidence") or 0

        decision_data = [
            ["Action", f"{action_color}{action}{Style.RESET_ALL}"],
            ["Quantity", f"{action_color}{quantity}{Style.RESET_ALL}"],
            ["Confidence", f"{Fore.WHITE}{confidence_val:.1f}%{Style.RESET_ALL}"],
            ["Reasoning", f"{Fore.WHITE}{wrapped_reasoning}{Style.RESET_ALL}"],
        ]

        print(f"\n{Fore.WHITE}{Style.BRIGHT}TRADING DECISION:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(tabulate(decision_data, tablefmt="grid", colalign=("left", "left")))

    # Portfolio summary
    print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")
    portfolio_data = []
    for ticker, decision in decisions.items():
        action = (decision.get("action") or "").upper()
        action_color = {
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN,
            "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)
        portfolio_data.append(
            [
                f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
                f"{action_color}{action}{Style.RESET_ALL}",
                f"{action_color}{decision.get('quantity') or 'N/A'}{Style.RESET_ALL}",
                f"{Fore.WHITE}{decision.get('confidence') or 0:.1f}%{Style.RESET_ALL}",
            ]
        )

    headers = [f"{Fore.WHITE}Ticker", "Action", "Quantity", "Confidence"]
    print(
        tabulate(
            portfolio_data,
            headers=headers,
            tablefmt="grid",
            colalign=("left", "center", "right", "right"),
        )
    )

    # Portfolio reasoning
    portfolio_manager_reasoning = None
    for decision in decisions.values():
        if decision.get("reasoning"):
            portfolio_manager_reasoning = decision.get("reasoning")
            break

    if portfolio_manager_reasoning:
        reasoning_str = ""
        if isinstance(portfolio_manager_reasoning, str):
            reasoning_str = portfolio_manager_reasoning
        elif isinstance(portfolio_manager_reasoning, dict):
            reasoning_str = json.dumps(portfolio_manager_reasoning, indent=2)
        else:
            reasoning_str = str(portfolio_manager_reasoning)

        wrapped_reasoning = ""
        current_line = ""
        max_line_length = 60
        for word in reasoning_str.split():
            if len(current_line) + len(word) + 1 > max_line_length:
                wrapped_reasoning += current_line + "\n"
                current_line = word
            else:
                current_line = (current_line + " " + word) if current_line else word
        if current_line:
            wrapped_reasoning += current_line

        print(f"\n{Fore.WHITE}{Style.BRIGHT}Portfolio Strategy:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{wrapped_reasoning}{Style.RESET_ALL}")


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
        # Pick the most recent summary by date (YYYY-MM-DD)
        latest_summary = max(summary_rows, key=lambda r: r[0])
        print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")

        # Adjusted indexes after adding Long/Short Shares
        position_str = latest_summary[7].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")
        cash_str     = latest_summary[8].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")
        total_str    = latest_summary[9].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")

        print(f"Cash Balance: {Fore.CYAN}${float(cash_str):,.2f}{Style.RESET_ALL}")
        print(f"Total Position Value: {Fore.YELLOW}${float(position_str):,.2f}{Style.RESET_ALL}")
        print(f"Total Value: {Fore.WHITE}${float(total_str):,.2f}{Style.RESET_ALL}")
        print(f"Return: {latest_summary[10]}")

        # Display performance metrics if available
        if latest_summary[11]:  # Sharpe ratio
            print(f"Sharpe Ratio: {latest_summary[11]}")
        if latest_summary[12]:  # Sortino ratio
            print(f"Sortino Ratio: {latest_summary[12]}")
        if latest_summary[13]:  # Max drawdown
            print(f"Max Drawdown: {latest_summary[13]}")

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
                "Long Shares",
                "Short Shares",
                "Position Value",
                "Bullish",
                "Bearish",
                "Neutral",
            ],
            tablefmt="grid",
            colalign=(
                "left",    # Date
                "left",    # Ticker
                "center",  # Action
                "right",   # Quantity
                "right",   # Price
                "right",   # Long Shares
                "right",   # Short Shares
                "right",   # Position Value
                "right",   # Bullish
                "right",   # Bearish
                "right",   # Neutral
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
    long_shares: float = 0,
    short_shares: float = 0,
    position_value: float = 0,
    bullish_count: int = 0,
    bearish_count: int = 0,
    neutral_count: int = 0,
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
        "HOLD": Fore.WHITE,
    }.get(action.upper(), Fore.WHITE)

    if is_summary:
        return_color = Fore.GREEN if return_pct >= 0 else Fore.RED
        return [
            date,
            f"{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY{Style.RESET_ALL}",
            "",  # Action
            "",  # Quantity
            "",  # Price
            "",  # Long Shares
            "",  # Short Shares
            f"{Fore.YELLOW}${total_position_value:,.2f}{Style.RESET_ALL}",  # Total Position Value
            f"{Fore.CYAN}${cash_balance:,.2f}{Style.RESET_ALL}",  # Cash Balance
            f"{Fore.WHITE}${total_value:,.2f}{Style.RESET_ALL}",  # Total Value
            f"{return_color}{return_pct:+.2f}%{Style.RESET_ALL}",  # Return
            f"{Fore.YELLOW}{sharpe_ratio:.2f}{Style.RESET_ALL}" if sharpe_ratio is not None else "",  # Sharpe Ratio
            f"{Fore.YELLOW}{sortino_ratio:.2f}{Style.RESET_ALL}" if sortino_ratio is not None else "",  # Sortino Ratio
            f"{Fore.RED}{abs(max_drawdown):.2f}%{Style.RESET_ALL}" if max_drawdown is not None else "",  # Max Drawdown
        ]
    else:
        return [
            date,
            f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
            f"{action_color}{action.upper()}{Style.RESET_ALL}",
            f"{action_color}{quantity:,.0f}{Style.RESET_ALL}",
            f"{Fore.WHITE}{price:,.2f}{Style.RESET_ALL}",
            f"{Fore.GREEN}{long_shares:,.0f}{Style.RESET_ALL}",   # Long Shares
            f"{Fore.RED}{short_shares:,.0f}{Style.RESET_ALL}",    # Short Shares
            f"{Fore.YELLOW}{position_value:,.2f}{Style.RESET_ALL}",
            f"{Fore.GREEN}{bullish_count}{Style.RESET_ALL}",
            f"{Fore.RED}{bearish_count}{Style.RESET_ALL}",
            f"{Fore.BLUE}{neutral_count}{Style.RESET_ALL}",
        ]
