import json
import os
import re
from datetime import datetime
from pathlib import Path

from colorama import Fore, Style
from tabulate import tabulate

from .analysts import ANALYST_ORDER


def sort_agent_signals(signals):
    """Sort agent signals in a consistent order."""
    # Create order mapping from ANALYST_ORDER
    analyst_order = {display: idx for idx, (display, _) in enumerate(ANALYST_ORDER)}
    analyst_order["Risk Management"] = len(ANALYST_ORDER)  # Add Risk Management at the end

    return sorted(signals, key=lambda x: analyst_order.get(x[0], 999))


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _stringify_reasoning(reasoning) -> str:
    """Convert reasoning payloads into readable text."""
    if not reasoning:
        return ""

    if isinstance(reasoning, str):
        return reasoning
    if isinstance(reasoning, dict):
        return json.dumps(reasoning, indent=2)
    return str(reasoning)


def _wrap_text(text: str, max_line_length: int = 60) -> str:
    """Wrap long text for terminal display."""
    if not text:
        return ""

    wrapped_lines = []
    current_line = ""
    for word in text.split():
        if len(current_line) + len(word) + 1 > max_line_length:
            wrapped_lines.append(current_line)
            current_line = word
        else:
            current_line = f"{current_line} {word}".strip()

    if current_line:
        wrapped_lines.append(current_line)

    return "\n".join(wrapped_lines)


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def _markdown_safe(text: str) -> str:
    """Make text safe for Markdown tables."""
    return _strip_ansi(str(text)).replace("|", "\\|").replace("\n", "<br>")


def _markdown_list_item(text: str) -> str:
    """Make text safe for simple Markdown bullets."""
    return _strip_ansi(str(text)).replace("\n", " ")


def _format_agent_name(agent: str) -> str:
    return agent.replace("_agent", "").replace("_", " ").title()


def _format_reasoning_markdown(reasoning) -> list[str]:
    """Render reasoning as AI-friendly Markdown blocks."""
    if not reasoning:
        return ["No reasoning provided."]

    if isinstance(reasoning, dict):
        return ["```json", json.dumps(reasoning, indent=2), "```"]

    text = _strip_ansi(str(reasoning)).strip()
    if not text:
        return ["No reasoning provided."]

    return [text]


def _build_report_path(tickers: list[str], report_file: str | None = None) -> Path:
    """Resolve the markdown report output path."""
    if report_file:
        return Path(report_file).expanduser()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ticker_suffix = "-".join(tickers[:5]).lower()
    if len(tickers) > 5:
        ticker_suffix = f"{ticker_suffix}-plus-{len(tickers) - 5}"
    ticker_suffix = re.sub(r"[^a-z0-9_-]+", "-", ticker_suffix).strip("-")

    reports_dir = Path("reports")
    filename = f"analysis-{timestamp}"
    if ticker_suffix:
        filename = f"{filename}-{ticker_suffix}"
    return reports_dir / f"{filename}.md"


def save_trading_output_markdown(result: dict, metadata: dict | None = None, report_file: str | None = None) -> str | None:
    """Persist a trading analysis run to a Markdown report."""
    decisions = result.get("decisions")
    if not decisions:
        return None

    metadata = metadata or {}
    tickers = list(decisions.keys())
    analyst_signals = result.get("analyst_signals", {})

    report_path = _build_report_path(tickers, report_file)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# AI Hedge Fund Analysis Report", "", "## Run Metadata", "", f"- Generated: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"]

    if tickers:
        lines.append(f"- Tickers: `{', '.join(tickers)}`")
    if metadata.get("start_date") and metadata.get("end_date"):
        lines.append(f"- Date range: `{metadata['start_date']}` to `{metadata['end_date']}`")
    if metadata.get("model_provider") and metadata.get("model_name"):
        lines.append(f"- Model: `{metadata['model_provider']}` / `{metadata['model_name']}`")
    if metadata.get("selected_analysts"):
        lines.append(f"- Analysts: `{', '.join(metadata['selected_analysts'])}`")
    elif metadata.get("analysts_all"):
        lines.append("- Analysts: `all`")
    if "show_reasoning" in metadata:
        lines.append(f"- Show reasoning: `{metadata['show_reasoning']}`")

    lines.extend(["", "---", ""])

    portfolio_data = []
    portfolio_manager_reasoning = None

    for _, decision in decisions.items():
        if decision.get("reasoning"):
            portfolio_manager_reasoning = decision.get("reasoning")
            break

    for ticker, decision in decisions.items():
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0

        for _, signals in analyst_signals.items():
            if ticker not in signals:
                continue
            signal = signals[ticker].get("signal", "").upper()
            if signal == "BULLISH":
                bullish_count += 1
            elif signal == "BEARISH":
                bearish_count += 1
            elif signal == "NEUTRAL":
                neutral_count += 1

        portfolio_data.append(
            [
                ticker,
                decision.get("action", "").upper(),
                decision.get("quantity"),
                f"{decision.get('confidence', 0):.1f}%",
                bullish_count,
                bearish_count,
                neutral_count,
            ]
        )

    lines.extend(
        [
            "## Executive Summary",
            "",
            tabulate(
                portfolio_data,
                headers=["Ticker", "Action", "Quantity", "Confidence", "Bullish", "Bearish", "Neutral"],
                tablefmt="github",
            ),
            "",
        ]
    )

    for ticker, decision in decisions.items():
        lines.extend([f"## Analysis for `{ticker}`", ""])

        agent_rows = []
        for agent, signals in analyst_signals.items():
            if ticker not in signals or agent == "risk_management_agent":
                continue

            signal = signals[ticker]
            agent_rows.append(
                [
                    _format_agent_name(agent),
                    signal.get("signal", "").upper(),
                    f"{signal.get('confidence', 0)}%",
                    signal.get("reasoning"),
                ]
            )

        agent_rows = sort_agent_signals(agent_rows)
        lines.extend(
            [
                "### Decision",
                "",
                tabulate(
                    [
                        ["Action", decision.get("action", "").upper()],
                        ["Quantity", decision.get("quantity")],
                        ["Confidence", f"{decision.get('confidence', 0):.1f}%"],
                    ],
                    tablefmt="github",
                ),
                "",
                "### Decision Reasoning",
                "",
                _strip_ansi(_stringify_reasoning(decision.get("reasoning"))),
                "",
                "### Agent Signals",
                "",
                tabulate(
                    [[name, signal, confidence] for name, signal, confidence, _ in agent_rows],
                    headers=["Agent", "Signal", "Confidence"],
                    tablefmt="github",
                ),
                "",
                "### Agent Reasoning",
                "",
            ]
        )

        for agent_name, signal_type, confidence, reasoning in agent_rows:
            lines.extend(
                [
                    f"#### {agent_name}",
                    "",
                    f"- Signal: `{signal_type}`",
                    f"- Confidence: `{confidence}`",
                    "- Reasoning:",
                ]
            )
            lines.extend(_format_reasoning_markdown(reasoning))
            lines.extend(["", ""])

    lines.extend(
        [
            "## Portfolio Summary",
            "",
            tabulate(
                portfolio_data,
                headers=["Ticker", "Action", "Quantity", "Confidence", "Bullish", "Bearish", "Neutral"],
                tablefmt="github",
            ),
            "",
        ]
    )

    if portfolio_manager_reasoning:
        lines.extend(
            [
                "## Portfolio Strategy",
                "",
                _strip_ansi(_stringify_reasoning(portfolio_manager_reasoning)),
                "",
            ]
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return str(report_path)


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
                
            # Skip Risk Management agent in the signals section
            if agent == "risk_management_agent":
                continue

            signal = signals[ticker]
            agent_name = _format_agent_name(agent)
            signal_type = signal.get("signal", "").upper()
            confidence = signal.get("confidence", 0)

            signal_color = {
                "BULLISH": Fore.GREEN,
                "BEARISH": Fore.RED,
                "NEUTRAL": Fore.YELLOW,
            }.get(signal_type, Fore.WHITE)
            
            # Get reasoning if available
            reasoning_str = ""
            if "reasoning" in signal and signal["reasoning"]:
                reasoning_str = _wrap_text(_stringify_reasoning(signal["reasoning"]))

            table_data.append(
                [
                    f"{Fore.CYAN}{agent_name}{Style.RESET_ALL}",
                    f"{signal_color}{signal_type}{Style.RESET_ALL}",
                    f"{Fore.WHITE}{confidence}%{Style.RESET_ALL}",
                    f"{Fore.WHITE}{reasoning_str}{Style.RESET_ALL}",
                ]
            )

        # Sort the signals according to the predefined order
        table_data = sort_agent_signals(table_data)

        print(f"\n{Fore.WHITE}{Style.BRIGHT}AGENT ANALYSIS:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(
            tabulate(
                table_data,
                headers=[f"{Fore.WHITE}Agent", "Signal", "Confidence", "Reasoning"],
                tablefmt="grid",
                colalign=("left", "center", "right", "left"),
            )
        )

        # Print Trading Decision Table
        action = decision.get("action", "").upper()
        action_color = {
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN,
            "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)

        # Get reasoning and format it
        reasoning = decision.get("reasoning", "")
        # Wrap long reasoning text to make it more readable
        wrapped_reasoning = ""
        if reasoning:
            wrapped_reasoning = _wrap_text(_stringify_reasoning(reasoning))

        decision_data = [
            ["Action", f"{action_color}{action}{Style.RESET_ALL}"],
            ["Quantity", f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}"],
            [
                "Confidence",
                f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
            ],
            ["Reasoning", f"{Fore.WHITE}{wrapped_reasoning}{Style.RESET_ALL}"],
        ]
        
        print(f"\n{Fore.WHITE}{Style.BRIGHT}TRADING DECISION:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(tabulate(decision_data, tablefmt="grid", colalign=("left", "left")))

    # Print Portfolio Summary
    print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")
    portfolio_data = []
    
    # Extract portfolio manager reasoning (common for all tickers)
    portfolio_manager_reasoning = None
    for ticker, decision in decisions.items():
        if decision.get("reasoning"):
            portfolio_manager_reasoning = decision.get("reasoning")
            break
            
    analyst_signals = result.get("analyst_signals", {})
    for ticker, decision in decisions.items():
        action = decision.get("action", "").upper()
        action_color = {
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN,
            "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)

        # Calculate analyst signal counts
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        if analyst_signals:
            for agent, signals in analyst_signals.items():
                if ticker in signals:
                    signal = signals[ticker].get("signal", "").upper()
                    if signal == "BULLISH":
                        bullish_count += 1
                    elif signal == "BEARISH":
                        bearish_count += 1
                    elif signal == "NEUTRAL":
                        neutral_count += 1

        portfolio_data.append(
            [
                f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
                f"{action_color}{action}{Style.RESET_ALL}",
                f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}",
                f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
                f"{Fore.GREEN}{bullish_count}{Style.RESET_ALL}",
                f"{Fore.RED}{bearish_count}{Style.RESET_ALL}",
                f"{Fore.YELLOW}{neutral_count}{Style.RESET_ALL}",
            ]
        )

    headers = [
        f"{Fore.WHITE}Ticker",
        f"{Fore.WHITE}Action",
        f"{Fore.WHITE}Quantity",
        f"{Fore.WHITE}Confidence",
        f"{Fore.WHITE}Bullish",
        f"{Fore.WHITE}Bearish",
        f"{Fore.WHITE}Neutral",
    ]
    
    # Print the portfolio summary table
    print(
        tabulate(
            portfolio_data,
            headers=headers,
            tablefmt="grid",
            colalign=("left", "center", "right", "right", "center", "center", "center"),
        )
    )
    
    # Print Portfolio Manager's reasoning if available
    if portfolio_manager_reasoning:
        wrapped_reasoning = _wrap_text(_stringify_reasoning(portfolio_manager_reasoning))

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
        print(f"Portfolio Return: {latest_summary[10]}")
        if len(latest_summary) > 14 and latest_summary[14]:
            print(f"Benchmark Return: {latest_summary[14]}")

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
    is_summary: bool = False,
    total_value: float = None,
    return_pct: float = None,
    cash_balance: float = None,
    total_position_value: float = None,
    sharpe_ratio: float = None,
    sortino_ratio: float = None,
    max_drawdown: float = None,
    benchmark_return_pct: float | None = None,
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
        benchmark_str = ""
        if benchmark_return_pct is not None:
            bench_color = Fore.GREEN if benchmark_return_pct >= 0 else Fore.RED
            benchmark_str = f"{bench_color}{benchmark_return_pct:+.2f}%{Style.RESET_ALL}"
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
            f"{Fore.RED}{max_drawdown:.2f}%{Style.RESET_ALL}" if max_drawdown is not None else "",  # Max Drawdown (signed)
            benchmark_str,  # Benchmark (S&P 500)
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
        ]
