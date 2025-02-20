import aiohttp
import asyncio
import os 
import sys
import time
from typing import Dict
from discord import Webhook, Color, Embed

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from colorama import Fore, Back, Style, init
import questionary
from agents.ben_graham import ben_graham_agent
from agents.bill_ackman import bill_ackman_agent
from agents.fundamentals import fundamentals_agent
from agents.portfolio_manager import portfolio_management_agent
from agents.technicals import technical_analyst_agent
from agents.risk_manager import risk_management_agent
from agents.sentiment import sentiment_agent
from agents.warren_buffett import warren_buffett_agent
from graph.state import AgentState
from agents.valuation import valuation_agent
from utils.display import print_trading_output
from utils.analysts import ANALYST_ORDER, get_analyst_nodes
from utils.progress import progress
from llm.models import LLM_ORDER, get_model_info

import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tabulate import tabulate
from utils.visualize import save_graph_as_png

# Load environment variables from .env file
load_dotenv()

init(autoreset=True)


def parse_hedge_fund_response(response):
    import json

    try:
        return json.loads(response)
    except:
        print(f"Error parsing response: {response}")
        return None


class RateLimiter:
    def __init__(self, calls_per_minute: int = 30):  # Discord usually allows 30 messages per minute
        self.calls_per_minute = calls_per_minute
        self.interval = 60 / calls_per_minute  # Time between calls in seconds
        self.last_call = 0
        self.calls = []  # Track timestamp of each call
        
    async def wait(self):
        now = time.time()
        
        # Remove timestamps older than 1 minute
        self.calls = [call for call in self.calls if now - call < 60]
        
        # If we've hit the rate limit, wait
        if len(self.calls) >= self.calls_per_minute:
            wait_time = 60 - (now - self.calls[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        # If needed, wait for minimum interval between calls
        time_since_last = now - self.last_call
        if time_since_last < self.interval:
            await asyncio.sleep(self.interval - time_since_last)
        
        self.last_call = time.time()
        self.calls.append(self.last_call)


class DiscordNotifier:
    def __init__(self, webhook_url: str = None, enabled: bool = True, calls_per_minute: int = 30):
        self.enabled = enabled
        if not enabled:
            return
            
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK")
        if not self.webhook_url and enabled:
            raise ValueError("Discord webhook URL not provided and DISCORD_WEBHOOK not found in environment")
        
        self.rate_limiter = RateLimiter(calls_per_minute)

    async def send_analysis(self, ticker: str, analyst_signals: Dict, trading_decision: Dict, portfolio_summary: Dict, state: AgentState):
        if not self.enabled:
            return
        
        # Wait for rate limiter before proceeding
        await self.rate_limiter.wait()
        
        async with aiohttp.ClientSession() as session:
            webhook = Webhook.from_url(self.webhook_url, session=session)

            # Predefined order of agents
            agent_order = [
                'fundamentals_agent', 
                'technical_analyst_agent', 
                'valuation_agent', 
                'sentiment_agent', 
                'warren_buffett_agent', 
                'bill_ackman_agent'
            ]

            # Map to ensure consistent naming
            name_mapping = {
                'fundamentals_agent': 'Fundamentals',
                'technical_analyst_agent': 'Technical Analyst',
                'valuation_agent': 'Valuation',
                'sentiment_agent': 'Sentiment',
                'bill_ackman_agent': 'Bill Ackman',
                'warren_buffett_agent': 'Warren Buffett'
            }

            analyst_table = []
            for agent_name in agent_order:
                # Skip if agent is not in analyst_signals
                if agent_name not in analyst_signals:
                    continue
                    
                # Get display name from mapping
                display_name = name_mapping.get(agent_name, agent_name)
                
                # Get agent's specific data for this ticker
                ticker_data = analyst_signals[agent_name].get(ticker, {})
                signal = ticker_data.get('signal', 'NEUTRAL').upper()
                confidence = ticker_data.get('confidence', 0.0)
                
                analyst_table.append(
                    f"{display_name:<20} {signal:<10} {confidence:>6.1f}%"
                )

            # Retrieve quantity from trading decision
            quantity = trading_decision.get('quantity', 0)
            confidence = trading_decision.get('confidence', 0.0)

            message = [
                f"**TRADING DECISION FOR {ticker}**",
                "```",
                f"Action:     {trading_decision.get('action', 'UNKNOWN').upper()}",
                f"Quantity:   {quantity}",
                f"Confidence: {confidence:.2f}%",
                "```",
                
                "```",
                f"{'Analyst':<20} {'Signal':<10} {'Confidence':>8}",
                "-" * 42,
                "\n".join(analyst_table),
                "```",
            ]

            # Determine color based on trading decision action
            action = trading_decision.get('action', '').lower()
            if action == 'buy':
                color = Color.from_rgb(0, 255, 0)  # Green
            elif action == 'sell':
                color = Color.from_rgb(255, 0, 0)  # Red
            elif action == 'hold':
                color = Color.from_rgb(255, 174, 0)  # Yellow
            else:
                color = Color.from_rgb(128, 128, 128)  # Gray

            embed = Embed(
                description="\n".join(message),
                color=color
            )

            try:
                await webhook.send(embed=embed)
                print(f"Analysis sent to Discord for {ticker}")
            except Exception as e:
                print(f"Error sending analysis to Discord: {str(e)}")


##### Run the Hedge Fund #####
def run_hedge_fund(
    tickers: list[str],
    start_date: str,
    end_date: str,
    portfolio: dict,
    show_reasoning: bool = False,
    selected_analysts: list[str] = [],
    model_name: str = "gpt-4o",
    model_provider: str = "OpenAI",
):
    # Start progress tracking
    progress.start()

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

        # Parse the results
        decisions = parse_hedge_fund_response(final_state["messages"][-1].content)
        analyst_signals = final_state["data"]["analyst_signals"]

        # Prepare the result dictionary
        result = {
            "decisions": decisions,
            "analyst_signals": analyst_signals,
        }

        # If Discord webhook is configured, send notifications
        try:
            discord_notifier = DiscordNotifier()
            
            # Iterate through tickers and send Discord notifications
            for ticker in tickers:
                # Get specific decision and signals for this ticker
                ticker_decision = decisions.get(ticker, {})
                ticker_signals = {agent: signals.get(ticker, {}) for agent, signals in analyst_signals.items()}

                # Run the async Discord notification
                import asyncio
                asyncio.run(discord_notifier.send_analysis(
                    ticker=ticker,
                    analyst_signals=analyst_signals,
                    trading_decision=ticker_decision,
                    portfolio_summary={},
                    state=final_state
                ))
        except Exception as e:
            print(f"Discord notification error: {e}")

        return result
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
    workflow.add_node("portfolio_management_agent", portfolio_management_agent)

    # Connect selected analysts to risk management
    for analyst_key in selected_analysts:
        node_name = analyst_nodes[analyst_key][0]
        workflow.add_edge(node_name, "risk_management_agent")

    workflow.add_edge("risk_management_agent", "portfolio_management_agent")
    workflow.add_edge("portfolio_management_agent", END)

    workflow.set_entry_point("start_node")
    return workflow


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the hedge fund trading system")
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=100000.0,
        help="Initial cash position. Defaults to 100000.0)"
    )
    parser.add_argument(
        "--margin-requirement",
        type=float,
        default=0.0,
        help="Initial margin requirement. Defaults to 0.0"
    )
    parser.add_argument("--tickers", type=str, required=True, help="Comma-separated list of stock ticker symbols")
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD). Defaults to 3 months before end date",
    )
    parser.add_argument("--end-date", type=str, help="End date (YYYY-MM-DD). Defaults to today")
    parser.add_argument("--show-reasoning", action="store_true", help="Show reasoning from each agent")
    parser.add_argument(
        "--show-agent-graph", action="store_true", help="Show the agent graph"
    )

    args = parser.parse_args()

    # Parse tickers from comma-separated string
    tickers = [ticker.strip() for ticker in args.tickers.split(",")]

    # Select analysts
    selected_analysts = None
    choices = questionary.checkbox(
        "Select your AI analysts.",
        choices=[questionary.Choice(display, value=value) for display, value in ANALYST_ORDER],
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
        selected_analysts = choices
        print(f"\nSelected analysts: {', '.join(Fore.GREEN + choice.title().replace('_', ' ') + Style.RESET_ALL for choice in choices)}\n")

    # Select LLM model
    model_choice = questionary.select(
        "Select your LLM model:",
        choices=[questionary.Choice(display, value=value) for display, value, _ in LLM_ORDER],
        style=questionary.Style([
            ("selected", "fg:green bold"),
            ("pointer", "fg:green bold"),
            ("highlighted", "fg:green"),
            ("answer", "fg:green bold"),
        ])
    ).ask()

    if not model_choice:
        print("\n\nInterrupt received. Exiting...")
        sys.exit(0)
    else:
        # Get model info using the helper function
        model_info = get_model_info(model_choice)
        if model_info:
            model_provider = model_info.provider.value
            print(f"\nSelected {Fore.CYAN}{model_provider}{Style.RESET_ALL} model: {Fore.GREEN + Style.BRIGHT}{model_choice}{Style.RESET_ALL}\n")
        else:
            model_provider = "Unknown"
            print(f"\nSelected model: {Fore.GREEN + Style.BRIGHT}{model_choice}{Style.RESET_ALL}\n")

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

    # Set the start and end dates
    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    if not args.start_date:
        # Calculate 3 months before end_date
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        start_date = (end_date_obj - relativedelta(months=3)).strftime("%Y-%m-%d")
    else:
        start_date = args.start_date

    # Initialize portfolio with cash amount and stock positions
    portfolio = {
        "cash": args.initial_cash,  # Initial cash amount
        "margin_requirement": args.margin_requirement,  # Initial margin requirement
        "positions": {
            ticker: {
                "long": 0,  # Number of shares held long
                "short": 0,  # Number of shares held short
                "long_cost_basis": 0.0,  # Average cost basis for long positions
                "short_cost_basis": 0.0,  # Average price at which shares were sold short
            } for ticker in tickers
        },
        "realized_gains": {
            ticker: {
                "long": 0.0,  # Realized gains from long positions
                "short": 0.0,  # Realized gains from short positions
            } for ticker in tickers
        }
    }

    # Run the hedge fund
    result = run_hedge_fund(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        portfolio=portfolio,
        show_reasoning=args.show_reasoning,
        selected_analysts=selected_analysts,
        model_name=model_choice,
        model_provider=model_provider,
    )
    print_trading_output(result)
