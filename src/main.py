import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from colorama import Fore, Style, init
import questionary
from src.agents.portfolio_manager import portfolio_management_agent
from src.agents.risk_manager import risk_management_agent
from src.graph.state import AgentState
from src.utils.display import print_trading_output
from src.utils.analysts import ANALYST_ORDER, get_analyst_nodes
from src.utils.progress import progress
from src.llm.models import LLM_ORDER, OLLAMA_LLM_ORDER, get_model_info, ModelProvider
from src.utils.ollama import ensure_ollama_and_model

import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
from src.utils.visualize import save_graph_as_png
from src.utils.config import get_config
import json

# Load environment variables from .env file
load_dotenv()

init(autoreset=True)


def parse_hedge_fund_response(response):
    """Parses a JSON string and returns a dictionary."""
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}\nResponse: {repr(response)}")
        return None
    except TypeError as e:
        print(f"Invalid response type (expected string, got {type(response).__name__}): {e}")
        return None
    except Exception as e:
        print(f"Unexpected error while parsing response: {e}\nResponse: {repr(response)}")
        return None


##### Run the Hedge Fund #####
def run_hedge_fund(
    tickers: list[str],
    start_date: str,
    end_date: str,
    portfolio: dict,
    show_reasoning: bool = False,
    selected_analysts: list[str] = [],
    model_name: str = "gpt-4.1",
    model_provider: str = "OpenAI",
):
    # Start progress tracking
    progress.start()
    
    # Display price data information
    from src.tools.api import get_prices
    from datetime import datetime, timedelta
    
    print(f"\n{Fore.WHITE}{Style.BRIGHT}PRICE DATA INFORMATION:{Style.RESET_ALL}")
    print(f"Analysis Period: {Fore.CYAN}{start_date}{Style.RESET_ALL} to {Fore.CYAN}{end_date}{Style.RESET_ALL}")
    
    # Check the most recent price data available for each ticker
    for ticker in tickers:
        try:
            # Get the most recent price data (last 7 days to ensure we get the latest)
            recent_end = datetime.now().strftime("%Y-%m-%d")
            recent_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            
            recent_prices = get_prices(ticker, recent_start, recent_end)
            if recent_prices:
                latest_price = recent_prices[-1]  # Most recent price
                latest_time = latest_price.time
                latest_close = latest_price.close
                
                # Parse the timestamp to show a more readable format
                try:
                    if 'T' in latest_time:
                        # ISO format with time
                        dt = datetime.fromisoformat(latest_time.replace('Z', '+00:00'))
                        time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                    else:
                        # Date only format
                        time_str = latest_time
                except:
                    time_str = latest_time
                
                print(f"  {Fore.CYAN}{ticker}{Style.RESET_ALL}: Latest price ${Fore.GREEN}{latest_close:.2f}{Style.RESET_ALL} "
                      f"(as of {Fore.YELLOW}{time_str}{Style.RESET_ALL})")
            else:
                print(f"  {Fore.CYAN}{ticker}{Style.RESET_ALL}: {Fore.RED}No recent price data available{Style.RESET_ALL}")
        except Exception as e:
            print(f"  {Fore.CYAN}{ticker}{Style.RESET_ALL}: {Fore.RED}Error fetching price data: {str(e)[:50]}...{Style.RESET_ALL}")
    
    print()  # Add spacing

    try:
        # Create a new workflow if analysts are customized
        if selected_analysts:
            workflow = create_workflow(selected_analysts)
            agent = workflow.compile()
        else:
            agent = app

        final_state = agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content="Make trading decisions based on the provided data.",
                    )
                ],
                "data": {
                    "tickers": tickers,
                    "portfolio": portfolio,
                    "start_date": start_date,
                    "end_date": end_date,
                    "analyst_signals": {},
                },
                "metadata": {
                    "show_reasoning": show_reasoning,
                    "model_name": model_name,
                    "model_provider": model_provider,
                },
            },
        )

        # Extract current prices and timestamps from the final state
        current_prices = final_state["data"].get("current_prices", {})
        price_timestamps = {}
        
        # Get the most recent timestamps for each ticker
        for ticker in tickers:
            try:
                recent_end = datetime.now().strftime("%Y-%m-%d")
                recent_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                recent_prices = get_prices(ticker, recent_start, recent_end)
                if recent_prices:
                    latest_price = recent_prices[-1]
                    latest_time = latest_price.time
                    
                    # Format timestamp for display
                    try:
                        if 'T' in latest_time:
                            dt = datetime.fromisoformat(latest_time.replace('Z', '+00:00'))
                            time_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                        else:
                            time_str = latest_time
                    except:
                        time_str = latest_time
                    
                    price_timestamps[ticker] = time_str
            except:
                price_timestamps[ticker] = "Unknown"

        return {
            "decisions": parse_hedge_fund_response(final_state["messages"][-1].content),
            "analyst_signals": final_state["data"]["analyst_signals"],
            "current_prices": current_prices,
            "price_timestamps": price_timestamps,
        }
    finally:
        # Stop progress tracking
        progress.stop()


def start(state: AgentState):
    """Initialize the workflow with the input message."""
    return state


def create_workflow(selected_analysts=None):
    """Create the workflow with selected analysts."""
    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", start)

    # Get analyst nodes from the configuration
    analyst_nodes = get_analyst_nodes()

    # Default to all analysts if none selected
    if selected_analysts is None:
        selected_analysts = list(analyst_nodes.keys())
    # Add selected analyst nodes
    for analyst_key in selected_analysts:
        node_name, node_func = analyst_nodes[analyst_key]
        workflow.add_node(node_name, node_func)
        workflow.add_edge("start_node", node_name)

    # Always add risk and portfolio management
    workflow.add_node("risk_management_agent", risk_management_agent)
    workflow.add_node("portfolio_manager", portfolio_management_agent)

    # Connect selected analysts to risk management
    for analyst_key in selected_analysts:
        node_name = analyst_nodes[analyst_key][0]
        workflow.add_edge(node_name, "risk_management_agent")

    workflow.add_edge("risk_management_agent", "portfolio_manager")
    workflow.add_edge("portfolio_manager", END)

    workflow.set_entry_point("start_node")
    return workflow


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the hedge fund trading system")
    parser.add_argument("--initial-cash", type=float, default=100000.0, help="Initial cash position. Defaults to 100000.0)")
    parser.add_argument("--margin-requirement", type=float, default=0.0, help="Initial margin requirement. Defaults to 0.0")
    parser.add_argument("--tickers", type=str, required=True, help="Comma-separated list of stock ticker symbols")
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD). Defaults to 3 months before end date",
    )
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD). Defaults to today")
    parser.add_argument("--show-reasoning", action="store_true", help="Show reasoning from each agent")
    parser.add_argument("--show-agent-graph", action="store_true", help="Show the agent graph")
    parser.add_argument("--ollama", action="store_true", help="Use Ollama for local LLM inference")

    args = parser.parse_args()

    # Parse tickers from comma-separated string
    tickers = [ticker.strip() for ticker in args.tickers.split(",")]

    # Load configuration
    config = get_config()
    
    # Select analysts
    selected_analysts = None
    analyst_choices = [questionary.Choice(display, value=value) for display, value in ANALYST_ORDER]
    
    if config.has_previous_selection():
        # Add "Same as previous" option
        previous_summary = config.get_config_summary()
        analyst_choices.insert(0, questionary.Choice(
            f"Same as previous ({len(config.get_previous_analysts())} analysts)", 
            value="__previous__"
        ))
        print(f"\n{Fore.CYAN}Previous configuration:{Style.RESET_ALL}")
        print(f"{previous_summary}\n")
    
    choices = questionary.checkbox(
        "Select your AI analysts.",
        choices=analyst_choices,
        instruction="\n\nInstructions: \n1. Press Space to select/unselect analysts.\n2. Press 'a' to select/unselect all.\n3. Press Enter when done to run the hedge fund.\n",
        validate=lambda x: len(x) > 0 or "You must select at least one analyst.",
        style=questionary.Style(
            [
                ("checkbox-selected", "fg:green"),
                ("selected", "fg:green noinherit"),
                ("highlighted", "noinherit"),
                ("pointer", "noinherit"),
            ]
        ),
    ).ask()

    if not choices:
        print("\n\nInterrupt received. Exiting...")
        sys.exit(0)
    else:
        if "__previous__" in choices:
            selected_analysts = config.get_previous_analysts()
            print(f"\nUsing previous analysts: " f"{', '.join(Fore.GREEN + choice.title().replace('_', ' ') + Style.RESET_ALL for choice in selected_analysts)}")
        else:
            selected_analysts = choices
            print(f"\nSelected analysts: " f"{', '.join(Fore.GREEN + choice.title().replace('_', ' ') + Style.RESET_ALL for choice in choices)}")

    # Select LLM model based on whether Ollama is being used
    model_name = ""
    model_provider = ""

    use_previous_model = False

    if args.ollama:
        print(f"{Fore.CYAN}Using Ollama for local LLM inference.{Style.RESET_ALL}")

        # Check if we should use previous Ollama model
        if config.has_previous_selection() and config.get_previous_ollama_flag():
            previous_model = config.get_previous_model()
            use_previous = questionary.confirm(
                f"Use previous Ollama model: {previous_model['name']}?",
                default=True
            ).ask()
            
            if use_previous is None:
                print("\n\nInterrupt received. Exiting...")
                sys.exit(0)
            elif use_previous:
                model_name = previous_model['name']
                use_previous_model = True

        if not use_previous_model:
            # Select from Ollama-specific models
            model_name: str = questionary.select(
                "Select your Ollama model:",
                choices=[questionary.Choice(display, value=value) for display, value, _ in OLLAMA_LLM_ORDER],
                style=questionary.Style(
                    [
                        ("selected", "fg:green bold"),
                        ("pointer", "fg:green bold"),
                        ("highlighted", "fg:green"),
                        ("answer", "fg:green bold"),
                    ]
                ),
            ).ask()

            if not model_name:
                print("\n\nInterrupt received. Exiting...")
                sys.exit(0)

            if model_name == "-":
                model_name = questionary.text("Enter the custom model name:").ask()
                if not model_name:
                    print("\n\nInterrupt received. Exiting...")
                    sys.exit(0)

        # Ensure Ollama is installed, running, and the model is available
        if not ensure_ollama_and_model(model_name):
            print(f"{Fore.RED}Cannot proceed without Ollama and the selected model.{Style.RESET_ALL}")
            sys.exit(1)

        model_provider = ModelProvider.OLLAMA.value
        print(f"\nSelected {Fore.CYAN}Ollama{Style.RESET_ALL} model: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}\n")
    else:
        # Check if we should use previous cloud model
        if config.has_previous_selection() and not config.get_previous_ollama_flag():
            previous_model = config.get_previous_model()
            use_previous = questionary.confirm(
                f"Use previous model: {previous_model['name']} ({previous_model['provider']})?",
                default=True
            ).ask()
            
            if use_previous is None:
                print("\n\nInterrupt received. Exiting...")
                sys.exit(0)
            elif use_previous:
                model_name = previous_model['name']
                model_provider = previous_model['provider']
                use_previous_model = True

        if not use_previous_model:
            # Use the standard cloud-based LLM selection
            model_choice = questionary.select(
                "Select your LLM model:",
                choices=[questionary.Choice(display, value=(name, provider)) for display, name, provider in LLM_ORDER],
                style=questionary.Style(
                    [
                        ("selected", "fg:green bold"),
                        ("pointer", "fg:green bold"),
                        ("highlighted", "fg:green"),
                        ("answer", "fg:green bold"),
                    ]
                ),
            ).ask()

            if not model_choice:
                print("\n\nInterrupt received. Exiting...")
                sys.exit(0)
            
            model_name, model_provider = model_choice

        print(f"\nSelected {Fore.CYAN}{model_provider}{Style.RESET_ALL} model: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}\n")

        model_info = get_model_info(model_name, model_provider)
        if model_info:
            if model_info.is_custom():
                model_name = questionary.text("Enter the custom model name:").ask()
                if not model_name:
                    print("\n\nInterrupt received. Exiting...")
                    sys.exit(0)

            print(f"\nSelected {Fore.CYAN}{model_provider}{Style.RESET_ALL} model: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}\n")
        else:
            model_provider = "Unknown"
            print(f"\nSelected model: {Fore.GREEN + Style.BRIGHT}{model_name}{Style.RESET_ALL}\n")

    # Save current configuration for next time
    config.save_selection(
        analysts=selected_analysts,
        model_name=model_name,
        model_provider=model_provider,
        use_ollama=args.ollama
    )

    # Create the workflow with selected analysts
    workflow = create_workflow(selected_analysts)
    app = workflow.compile()

    if args.show_agent_graph:
        file_path = ""
        if selected_analysts is not None:
            for selected_analyst in selected_analysts:
                file_path += selected_analyst + "_"
            file_path += "graph.png"
        save_graph_as_png(app, file_path)

    # Validate dates if provided
    if args.start_date:
        try:
            datetime.strptime(args.start_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Start date must be in YYYY-MM-DD format")

    if args.end_date:
        try:
            datetime.strptime(args.end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("End date must be in YYYY-MM-DD format")

    # Set the start and end dates - ensure we use the most recent data available
    if args.end_date:
        end_date = args.end_date
    else:
        # Use today's date to get the most recent data
        end_date = datetime.now().strftime("%Y-%m-%d")
        
    if not args.start_date:
        # Calculate 3 months before end_date
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = (end_date_obj - relativedelta(months=3)).strftime("%Y-%m-%d")
    else:
        start_date = args.start_date
        
    # Display information about data freshness
    print(f"\n{Fore.WHITE}{Style.BRIGHT}DATA ANALYSIS CONFIGURATION:{Style.RESET_ALL}")
    print(f"Using data from {Fore.CYAN}{start_date}{Style.RESET_ALL} to {Fore.CYAN}{end_date}{Style.RESET_ALL}")
    
    # Check if we're using today's date (most recent)
    today = datetime.now().strftime("%Y-%m-%d")
    if end_date == today:
        print(f"{Fore.GREEN}✓ Using most recent available data (today: {today}){Style.RESET_ALL}")
    else:
        days_behind = (datetime.now() - datetime.strptime(end_date, "%Y-%m-%d")).days
        print(f"{Fore.YELLOW}⚠ Using data from {days_behind} day(s) ago - consider using --end-date {today} for latest data{Style.RESET_ALL}")

    # Initialize portfolio with cash amount and stock positions
    portfolio = {
        "cash": args.initial_cash,  # Initial cash amount
        "margin_requirement": args.margin_requirement,  # Initial margin requirement
        "margin_used": 0.0,  # total margin usage across all short positions
        "positions": {
            ticker: {
                "long": 0,  # Number of shares held long
                "short": 0,  # Number of shares held short
                "long_cost_basis": 0.0,  # Average cost basis for long positions
                "short_cost_basis": 0.0,  # Average price at which shares were sold short
                "short_margin_used": 0.0,  # Dollars of margin used for this ticker's short
            }
            for ticker in tickers
        },
        "realized_gains": {
            ticker: {
                "long": 0.0,  # Realized gains from long positions
                "short": 0.0,  # Realized gains from short positions
            }
            for ticker in tickers
        },
    }

    # Run the hedge fund
    result = run_hedge_fund(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        portfolio=portfolio,
        show_reasoning=args.show_reasoning,
        selected_analysts=selected_analysts,
        model_name=model_name,
        model_provider=model_provider,
    )
    print_trading_output(result)
