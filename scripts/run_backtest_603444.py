"""Non-interactive backtest runner for 603444.SH.

Wraps BacktestEngine directly so we can pass model/analysts without going
through the interactive questionary prompts in src/backtesting/cli.py.
"""
from __future__ import annotations

from datetime import datetime
from dateutil.relativedelta import relativedelta

from colorama import Fore, Style, init

from src.backtesting.engine import BacktestEngine
from src.main import run_hedge_fund
from src.utils.analysts import ANALYST_ORDER


def main() -> int:
    init(autoreset=True)

    end_date = "2026-07-16"
    start_date = "2026-01-16"
    ticker = "603444.SH"
    model_name = "deepseek-v4-pro"
    model_provider = "DeepSeek"
    selected_analysts = [key for _, key in ANALYST_ORDER]  # all 19
    initial_capital = 100_000.0

    print(
        f"{Fore.CYAN}Backtest{Style.RESET_ALL} {ticker} "
        f"{start_date} → {end_date} "
        f"| {Fore.GREEN}{model_provider} / {model_name}{Style.RESET_ALL} "
        f"| {len(selected_analysts)} analysts "
        f"| initial capital {initial_capital:,.0f}"
    )

    engine = BacktestEngine(
        agent=run_hedge_fund,
        tickers=[ticker],
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        model_name=model_name,
        model_provider=model_provider,
        selected_analysts=selected_analysts,
        initial_margin_requirement=0.0,
    )

    metrics = engine.run_backtest()
    values = engine.get_portfolio_values()

    print(f"\n{Fore.WHITE}{Style.BRIGHT}BACKTEST COMPLETE{Style.RESET_ALL}")
    if values:
        last_value = values[-1]["Portfolio Value"]
        start_value = values[0]["Portfolio Value"]
        total_return = (last_value / start_value - 1.0) * 100.0 if start_value else 0.0
        print(
            f"Start portfolio: {start_value:>14,.2f}\n"
            f"End portfolio:   {last_value:>14,.2f}\n"
            f"Total Return:    {Fore.GREEN if total_return >= 0 else Fore.RED}{total_return:+.2f}%{Style.RESET_ALL}"
        )
    if metrics.get("sharpe_ratio") is not None:
        print(f"Sharpe:   {metrics['sharpe_ratio']:.3f}")
    if metrics.get("sortino_ratio") is not None:
        print(f"Sortino:  {metrics['sortino_ratio']:.3f}")
    if metrics.get("max_drawdown") is not None:
        md = abs(metrics["max_drawdown"]) if metrics["max_drawdown"] is not None else 0.0
        if metrics.get("max_drawdown_date"):
            print(f"Max DD:   {md:.2f}% on {metrics['max_drawdown_date']}")
        else:
            print(f"Max DD:   {md:.2f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
