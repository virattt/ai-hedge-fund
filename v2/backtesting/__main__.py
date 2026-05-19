"""Run the PEAD backtester. Screen-record friendly output.

Usage: poetry run python -m v2.backtesting
"""

from __future__ import annotations

import os
import sys
import time

from v2.data import FDClient
from v2.backtesting import BacktestEngine, PEADStrategy

TICKERS = [
    # Tech (21)
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "NFLX", "CRM", "ADBE",
    "ORCL", "INTC", "AMD", "CSCO", "IBM", "UBER", "SHOP", "SNOW", "PLTR", "PANW", "CRWD",
    # Financials (15)
    "JPM", "GS", "BAC", "WFC", "MS", "C", "BLK", "SCHW", "AXP", "COF",
    "USB", "PNC", "TFC", "BK", "CME",
    # Healthcare (15)
    "JNJ", "PFE", "UNH", "MRK", "LLY", "ABBV", "TMO", "ABT", "BMY", "AMGN",
    "GILD", "ISRG", "VRTX", "REGN", "MDT",
    # Energy (7)
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX",
    # Consumer / Retail (15)
    "HD", "LOW", "COST", "WMT", "KO", "PEP", "MCD", "SBUX", "NKE", "TGT",
    "TJX", "ROST", "DG", "DLTR", "YUM",
    # Industrials (10)
    "CAT", "DE", "HON", "UPS", "RTX", "BA", "LMT", "GE", "MMM", "UNP",
    # Media / Telecom (7)
    "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR", "WBD",
    # Other (10)
    "V", "MA", "PYPL", "NEE", "D", "SO", "DUK", "ABNB", "COIN", "NOW",
]

HOLDING_DAYS = 5
CAPITAL = 100_000.0
PER_TRADE = 10_000.0

# Colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
DIM = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"


def clear():
    os.system("clear")


def color_pnl(v: float) -> str:
    c = GREEN if v >= 0 else RED
    return f"{c}${v:>+10,.2f}{RESET}"


def color_pct(v: float) -> str:
    c = GREEN if v >= 0 else RED
    return f"{c}{v:>+7.2%}{RESET}"


def color_direction(d: str) -> str:
    return f"{GREEN}LONG {RESET}" if d == "long" else f"{RED}SHORT{RESET}"


def color_eps(s: str | None) -> str:
    if s == "BEAT":
        return f"{GREEN}BEAT{RESET}"
    if s == "MISS":
        return f"{RED}MISS{RESET}"
    return f"{DIM}  - {RESET}"


def print_header(metrics, equity: float):
    """Print the portfolio summary dashboard."""
    m = metrics
    ret_color = GREEN if m.total_return_pct >= 0 else RED
    sharpe_color = GREEN if m.sharpe_ratio > 1.0 else YELLOW if m.sharpe_ratio > 0 else RED

    print(f"  {BOLD}PEAD Backtest — Long BEATs, Short MISSes, {HOLDING_DAYS}-day hold{RESET}")
    print(f"  {DIM}{'─' * 70}{RESET}")
    print(
        f"  Portfolio: {CYAN}${equity:>12,.2f}{RESET}"
        f"    Return: {ret_color}{m.total_return_pct:>+7.2%}{RESET}"
        f"    Sharpe: {sharpe_color}{m.sharpe_ratio:>5.2f}{RESET}"
        f"    Max DD: {RED}{m.max_drawdown_pct:>6.2%}{RESET}"
    )
    print(
        f"  Trades: {m.n_trades}"
        f"  ({GREEN}{m.n_long} long{RESET}, {RED}{m.n_short} short{RESET})"
        f"    Win Rate: {m.win_rate:.0%}"
        f"    Avg Return: {color_pct(m.avg_return_pct)}"
    )
    print(f"  {DIM}{'─' * 70}{RESET}")
    print()


def print_table_header():
    print(
        f"  {DIM}{'Date':<12} {'Ticker':<6} {'Action':<6} {'EPS':<5}"
        f" {'Entry':>9} {'Exit':>9} {'Shares':>7}"
        f" {'P&L':>12} {'Return':>8}{RESET}"
    )
    print(f"  {DIM}{'─' * 78}{RESET}")


def print_trade_row(t):
    print(
        f"  {t.entry_date:<12} {CYAN}{t.ticker:<6}{RESET}"
        f" {color_direction(t.direction)} {color_eps(t.metadata.get('eps_surprise'))}"
        f" ${t.entry_price:>8.2f} ${t.exit_price:>8.2f} {t.shares:>7.1f}"
        f" {color_pnl(t.pnl)} {color_pct(t.return_pct)}"
    )


def main() -> None:
    import logging
    logging.getLogger("v2.data.client").setLevel(logging.ERROR)

    n = len(TICKERS)

    # Phase 1: Generate signals with progress
    sys.stdout.write(f"  Scanning earnings... [0/{n}]")
    sys.stdout.flush()

    with FDClient() as fd:
        strategy = PEADStrategy(holding_days=HOLDING_DAYS)
        signals = []
        for i, ticker in enumerate(TICKERS):
            sys.stdout.write(f"\r  Scanning earnings... [{i + 1}/{n}] {ticker:<6}")
            sys.stdout.flush()
            ticker_signals = strategy.generate_signals([ticker], fd)
            signals.extend(ticker_signals)

        sys.stdout.write(f"\r  Scanning earnings... {len(signals)} signals found" + " " * 20 + "\n")
        sys.stdout.flush()
        time.sleep(0.5)

        # Phase 2: Execute trades with live display
        engine = BacktestEngine(capital=CAPITAL, per_trade=PER_TRADE)
        result = engine.run_signals(signals, fd)

    if not result.trades or not result.metrics:
        print("  No trades generated.")
        return

    # Phase 3: Display trades one by one with running metrics
    clear()
    trades = result.trades
    equity = CAPITAL
    displayed: list = []

    for i, trade in enumerate(trades):
        equity += trade.pnl
        displayed.append(trade)

        # Rebuild display each trade (like v1's clear-and-reprint)
        clear()

        # Compute running metrics for display
        from v2.backtesting.engine import BacktestEngine as _E
        running_engine = _E(capital=CAPITAL, per_trade=PER_TRADE)
        running_curve = running_engine._build_equity_curve(displayed)
        running_metrics = running_engine._compute_metrics(displayed, running_curve)

        print_header(running_metrics, equity)
        print_table_header()

        # Print all trades so far (newest first)
        for t in reversed(displayed):
            print_trade_row(t)

        print()
        time.sleep(0.4)

    # Final summary
    time.sleep(0.5)
    print(f"  {BOLD}Done.{RESET} {len(trades)} trades executed.\n")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
