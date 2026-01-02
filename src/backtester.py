import sys

from colorama import Fore, Style

from src.main import run_hedge_fund
from src.backtesting.engine import BacktestEngine
from src.backtesting.types import PerformanceMetrics
from src.cli.input import (
    parse_cli_inputs,
)


def run_backtest(backtester: BacktestEngine) -> PerformanceMetrics | None:
    """Run the backtest with graceful KeyboardInterrupt handling."""
    try:
        performance_metrics = backtester.run_backtest()
        print(f"\n{Fore.GREEN}Backtest completed successfully!{Style.RESET_ALL}")
        return performance_metrics
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Backtest interrupted by user.{Style.RESET_ALL}")
        
        # Try to show any partial results that were computed
        try:
            portfolio_values = backtester.get_portfolio_values()
            if len(portfolio_values) > 1:
                print(f"{Fore.GREEN}Partial results available.{Style.RESET_ALL}")
                
                # Show basic summary from the available portfolio values
                first_value = portfolio_values[0]["Portfolio Value"]
                last_value = portfolio_values[-1]["Portfolio Value"]
                total_return = ((last_value - first_value) / first_value) * 100
                
                print(f"{Fore.CYAN}Initial Portfolio Value: ${first_value:,.2f}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Final Portfolio Value: ${last_value:,.2f}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}Total Return: {total_return:+.2f}%{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Could not generate partial results: {str(e)}{Style.RESET_ALL}")
        
        sys.exit(0)


### Run the Backtest #####
if __name__ == "__main__":
    inputs = parse_cli_inputs(
        description="Run backtesting simulation",
        require_tickers=False,
        default_months_back=1,
        include_graph_flag=False,
        include_reasoning_flag=False,
    )

    # Create and run the backtester
    backtester = BacktestEngine(
        agent=run_hedge_fund,
        tickers=inputs.tickers,
        start_date=inputs.start_date,
        end_date=inputs.end_date,
        initial_capital=inputs.initial_cash,
        model_name=inputs.model_name,
        model_provider=inputs.model_provider,
        selected_analysts=inputs.selected_analysts,
        initial_margin_requirement=inputs.margin_requirement,
    )

    # Run the backtest with graceful exit handling
    performance_metrics = run_backtest(backtester)
