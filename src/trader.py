"""Live trading CLI for the AI hedge fund."""

import sys
import argparse
from dotenv import load_dotenv
import questionary
from colorama import Fore, Style, init

from src.trading.trader import create_trader
from src.utils.analysts import ANALYST_ORDER
from src.llm.models import LLM_ORDER, OLLAMA_LLM_ORDER, get_model_info, ModelProvider
from src.utils.ollama import ensure_ollama_and_model

# Load environment variables
load_dotenv()
init(autoreset=True)


def main():
    """Main CLI entry point for live trading."""
    parser = argparse.ArgumentParser(description="Run live trading with AI hedge fund")
    parser.add_argument("--tickers", type=str, help="Comma-separated list of stock ticker symbols")
    parser.add_argument("--dry-run", action="store_true", help="Show decisions but don't execute trades")
    parser.add_argument("--ignore-market-hours", action="store_true", help="Run even when market is closed (useful with --dry-run)")
    parser.add_argument("--continuous", action="store_true", help="Run continuous trading")
    parser.add_argument("--interval", type=int, default=60, help="Trading interval in minutes (default: 60)")
    parser.add_argument("--available-capital", type=float, help="Override available capital (uses broker cash if not specified)")
    parser.add_argument("--margin-requirement", type=float, help="Margin requirement ratio for short positions (uses broker default if not specified)")
    parser.add_argument("--show-reasoning", action="store_true", help="Show reasoning from each agent")
    parser.add_argument("--ollama", action="store_true", help="Use Ollama for local LLM inference")
    parser.add_argument("--analysts", type=str, help="Comma-separated list of analysts to use")
    parser.add_argument("--analysts-all", action="store_true", help="Use all available analysts")
    parser.add_argument("--list-analysts", action="store_true", help="List all available analysts and exit")
    parser.add_argument("--model", type=str, help="LLM model name to use")
    parser.add_argument("--list-models", action="store_true", help="List all available models and exit")

    args = parser.parse_args()

    # Handle list options
    if args.list_analysts:
        print(f"\n{Fore.CYAN}Available Analysts:{Style.RESET_ALL}")
        for display, value in ANALYST_ORDER:
            print(f"  {Fore.GREEN}{value:<25}{Style.RESET_ALL} - {display}")
        print(f"\n{Fore.YELLOW}Usage examples:{Style.RESET_ALL}")
        print(f"  --analysts warren_buffett,michael_burry")
        print(f"  --analysts-all")
        sys.exit(0)

    if args.list_models:
        print(f"\n{Fore.CYAN}Available Models:{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}Cloud Models:{Style.RESET_ALL}")
        for display, name, provider in LLM_ORDER:
            print(f"  {Fore.GREEN}{name:<25}{Style.RESET_ALL} - {display} ({provider})")
        
        print(f"\n{Fore.YELLOW}Ollama Models:{Style.RESET_ALL}")
        for display, name, _ in OLLAMA_LLM_ORDER:
            print(f"  {Fore.GREEN}{name:<25}{Style.RESET_ALL} - {display}")
        
        print(f"\n{Fore.YELLOW}Usage examples:{Style.RESET_ALL}")
        print(f"  --model gpt-4o")
        print(f"  --model claude-3-5-sonnet-20241022")
        print(f"  --ollama --model llama3")
        sys.exit(0)

    # Check if tickers are required
    if not args.tickers:
        print(f"{Fore.RED}Error: --tickers is required for trading operations{Style.RESET_ALL}")
        print("Use --list-analysts or --list-models to see available options")
        sys.exit(1)


    # Parse tickers
    tickers = [ticker.strip().upper() for ticker in args.tickers.split(",")]
    print(f"\n{Fore.CYAN}Trading tickers: {', '.join(tickers)}{Style.RESET_ALL}")


    # Select analysts
    selected_analysts = None
    if args.analysts_all:
        selected_analysts = [a[1] for a in ANALYST_ORDER]
    elif args.analysts:
        selected_analysts = [a.strip() for a in args.analysts.split(",") if a.strip()]
    else:
        selected_analysts = questionary.checkbox(
            "Select your AI analysts:",
            choices=[questionary.Choice(display, value=value) for display, value in ANALYST_ORDER],
            instruction="\n\nInstructions:\n1. Press Space to select/unselect analysts\n2. Press 'a' to select/unselect all\n3. Press Enter when done\n",
            validate=lambda x: len(x) > 0 or "You must select at least one analyst.",
            style=questionary.Style([
                ("checkbox-selected", "fg:green"),
                ("selected", "fg:green noinherit"),
                ("highlighted", "noinherit"),
                ("pointer", "noinherit"),
            ])
        ).ask()

    if not selected_analysts:
        print("\nExiting...")
        sys.exit(0)

    print(f"\nSelected analysts: {', '.join(Fore.GREEN + choice.title().replace('_', ' ') + Style.RESET_ALL for choice in selected_analysts)}")

    # Select LLM model
    model_name = ""
    model_provider = ""

    if args.model:
        # Model specified via CLI
        model_name = args.model
        if args.ollama:
            model_provider = ModelProvider.OLLAMA.value
            if not ensure_ollama_and_model(model_name):
                print(f"{Fore.RED}Cannot proceed without Ollama and the selected model{Style.RESET_ALL}")
                sys.exit(1)
        else:
            # Try to find the model in the LLM_ORDER
            found = False
            for display, name, provider in LLM_ORDER:
                if name == model_name:
                    model_provider = provider
                    found = True
                    break
            if not found:
                print(f"{Fore.RED}Model '{model_name}' not found in available models{Style.RESET_ALL}")
                sys.exit(1)
        print(f"\nUsing model: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL} ({model_provider})")

    elif args.ollama:
        print(f"{Fore.CYAN}Using Ollama for local LLM inference{Style.RESET_ALL}")
        
        model_name = questionary.select(
            "Select your Ollama model:",
            choices=[questionary.Choice(display, value=value) for display, value, _ in OLLAMA_LLM_ORDER],
            style=questionary.Style([
                ("selected", "fg:green bold"),
                ("pointer", "fg:green bold"),
                ("highlighted", "fg:green"),
                ("answer", "fg:green bold"),
            ])
        ).ask()

        if not model_name:
            print("\nExiting...")
            sys.exit(0)

        if model_name == "-":
            model_name = questionary.text("Enter the custom model name:").ask()
            if not model_name:
                print("\nExiting...")
                sys.exit(0)

        if not ensure_ollama_and_model(model_name):
            print(f"{Fore.RED}Cannot proceed without Ollama and the selected model{Style.RESET_ALL}")
            sys.exit(1)

        model_provider = ModelProvider.OLLAMA.value
        print(f"\nSelected {Fore.CYAN}Ollama{Style.RESET_ALL} model: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}")

    else:
        model_choice = questionary.select(
            "Select your LLM model:",
            choices=[questionary.Choice(display, value=(name, provider)) for display, name, provider in LLM_ORDER],
            style=questionary.Style([
                ("selected", "fg:green bold"),
                ("pointer", "fg:green bold"),
                ("highlighted", "fg:green"),
                ("answer", "fg:green bold"),
            ])
        ).ask()

        if not model_choice:
            print("\nExiting...")
            sys.exit(0)

        model_name, model_provider = model_choice

        model_info = get_model_info(model_name, model_provider)
        if model_info and model_info.is_custom():
            model_name = questionary.text("Enter the custom model name:").ask()
            if not model_name:
                print("\nExiting...")
                sys.exit(0)

        print(f"\nSelected {Fore.CYAN}{model_provider}{Style.RESET_ALL} model: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}")

    # Create trader
    print(f"\n{Fore.CYAN}Creating trader...{Style.RESET_ALL}")
    trader = create_trader(
        tickers=tickers,
        selected_analysts=selected_analysts,
        model_name=model_name,
        model_provider=model_provider,
        available_capital=args.available_capital,
        margin_requirement=args.margin_requirement,
        dry_run=args.dry_run,
        ignore_market_hours=args.ignore_market_hours
    )

    # Connect to broker
    print(f"\n{Fore.CYAN}Connecting to broker...{Style.RESET_ALL}")
    if not trader.connect():
        print(f"{Fore.RED}Failed to connect to broker{Style.RESET_ALL}")
        sys.exit(1)
    
    # Get margin requirement from broker if not specified
    if args.margin_requirement is None:
        try:
            # Get account default margin requirement
            broker_margin_req = trader.broker.get_margin_requirement()
            trader.margin_requirement = broker_margin_req
            print(f"{Fore.CYAN}Using broker default margin requirement: {broker_margin_req:.1%}{Style.RESET_ALL}")
            
            # Show ticker-specific margin requirements
            print(f"{Fore.CYAN}Ticker-specific margin requirements:{Style.RESET_ALL}")
            for ticker in tickers:
                try:
                    ticker_margin = trader.broker.get_margin_requirement(ticker)
                    print(f"  {ticker}: {ticker_margin:.1%}")
                except Exception as e:
                    print(f"  {ticker}: {broker_margin_req:.1%} (default - could not get specific requirement)")
        except Exception as e:
            trader.margin_requirement = 0.5  # Default fallback
            print(f"{Fore.YELLOW}Could not get broker margin requirement, using default 50%{Style.RESET_ALL}")
    
    # Show capital usage information
    if args.available_capital:
        print(f"{Fore.CYAN}Using limited capital: ${args.available_capital:,.2f} (maintaining account margin capability){Style.RESET_ALL}")
    
    # Check for live trading warning after connection
    if not trader.broker.is_paper_trading():
        confirm = questionary.confirm(
            f"{Fore.RED}WARNING: Connected to LIVE TRADING account with real money. Are you sure you want to continue?{Style.RESET_ALL}",
            default=False
        ).ask()
        if not confirm:
            print("Exiting...")
            trader.disconnect()
            sys.exit(0)

    try:
        # Show portfolio summary
        trader.print_portfolio_summary()

        # Run trading
        if args.continuous:
            print(f"\n{Fore.BLUE}Starting continuous trading mode...{Style.RESET_ALL}")
            trader.run_continuous_trading(interval_minutes=args.interval)
        else:
            print(f"\n{Fore.BLUE}Running single trading session...{Style.RESET_ALL}")
            trader.run_trading_session()
            
            # Show updated portfolio
            trader.print_portfolio_summary()

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Trading interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Trading failed: {e}{Style.RESET_ALL}")
        sys.exit(1)
    finally:
        trader.disconnect()

    print(f"\n{Fore.GREEN}Trading session completed{Style.RESET_ALL}")


if __name__ == "__main__":
    main()