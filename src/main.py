import sys

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
from datetime import datetime, timedelta
from tabulate import tabulate
from utils.visualize import save_graph_as_png
from utils.logger_config import setup_logger, get_logger
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
    agent: any,
    market: str,
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
        # Create a new workflow if analysts are customized ////// Try not use this logic
        # if selected_analysts:
        #     workflow = create_workflow(selected_analysts)
        #     agent = workflow.compile()
        # else:
        #     agent = app

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
                    "market": market,
                },
            },
        )

        return {
            "decisions": parse_hedge_fund_response(final_state["messages"][-1].content),
            "analyst_signals": final_state["data"]["analyst_signals"],
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
    workflow.add_node("start_node", start) # dummy start node
    
    # Always add risk and portfolio management
    workflow.add_node("risk_management_agent", risk_management_agent)
    workflow.add_node("portfolio_management_agent", portfolio_management_agent)

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
        workflow.add_edge(node_name, "risk_management_agent")

    workflow.add_edge("risk_management_agent", "portfolio_management_agent")
    workflow.add_edge("portfolio_management_agent", END)

    workflow.set_entry_point("start_node")
    return workflow


if __name__ == "__main__":
    # Initialize logging system
    logger = get_logger()
    logger.info("启动StockAgent...")
    
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
    parser.add_argument(
        "--tickers",
        type=str,
        required=True,
        help="Comma-separated list of stock ticker symbols")
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD). Defaults to 3 months before end date",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD). Defaults to today")
    parser.add_argument(
        "--show-reasoning",
        action="store_true",
        help="Show reasoning from each agent")
    parser.add_argument(
        "--show-agent-graph",
        action="store_true",
        help="Show the agent graph"
    )

    args = parser.parse_args()
    
    logger.info("系统入参:")
    for arg_name, arg_value in vars(args).items():
        logger.info("    {} = {}".format(arg_name, arg_value))

    # Parse tickers from comma-separated string
    tickers = [ticker.strip() for ticker in args.tickers.split(",")]

    # 市场分类逻辑，不同市场的数据获取方式不同
    def classify_stock_market(ticker: str) -> str:
        """根据股票代码格式判断市场"""
        if len(ticker) == 6 and ticker.isdigit():
            return "CN" # "中国A股"
        elif len(ticker) == 5 and ticker.isdigit():
            return "HK" # "中国港股"
        elif 1 <= len(ticker) <= 4 and ticker.isalpha():
            return "US" # "美股"
        return "Others"

    # Classify stocks
    market_classification = {}
    for ticker in tickers:
        market = classify_stock_market(ticker)
        if market not in market_classification:
            market_classification[market] = []
        market_classification[market].append(ticker)
    logger.info(f"市场分类结果:")
    for market, tickers in market_classification.items():
        logger.info(f"    {market}: {', '.join(tickers)}")
    
    # Select analysts
    selected_analysts = None
    choices = questionary.checkbox(
        "Select your AI analysts.",
        choices=[questionary.Choice(display, value=value) for display, value in ANALYST_ORDER],
        instruction="\n\n操作指南: \n1. 按空格键选择/取消分析师\n2. 按 'A' 全选/取消全选\n3. 按回车确认并运行对冲基金策略。\n\n Instructions: \n1. Press Space to select/unselect analysts.\n2. Press 'a' to select/unselect all.\n3. Press Enter when done to run the hedge fund.\n",
        validate=lambda x: len(x) > 0 or "必须选择至少一位分析师 // You must select at least one analyst.",
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
        logger.error("无有效选择，退出... // Interrupt received. Exiting...")
        sys.exit(0)
    else:
        selected_analysts = choices
        logger.info(f"Selected analysts: {', '.join(Fore.GREEN + choice.title().replace('_', ' ') + Style.RESET_ALL for choice in choices)}.")

    # Select LLM model
    model_choice = questionary.select(
        "选择你希望使用的LLM模型： // Select your LLM model:",
        choices=[questionary.Choice(display, value=value) for display, value, _ in LLM_ORDER],
        style=questionary.Style([
            ("selected", "fg:green bold"),
            ("pointer", "fg:green bold"),
            ("highlighted", "fg:green"),
            ("answer", "fg:green bold"),
        ])
    ).ask()

    if not model_choice:
        logger.error("无有效选择，退出... // Interrupt received. Exiting...")
        sys.exit(0)
    else:
        # Get model info using the helper function
        model_info = get_model_info(model_choice)
        if model_info:
            model_provider = model_info.provider.value
            logger.info(f"Selected {Fore.CYAN}{model_provider}{Style.RESET_ALL} model: {Fore.GREEN + Style.BRIGHT}{model_choice}{Style.RESET_ALL}.")
        else:
            model_provider = "Unknown"
            logger.info(f"Selected model: {Fore.GREEN + Style.BRIGHT}{model_choice}{Style.RESET_ALL}.")

    # Create the workflow with selected analysts
    workflow = create_workflow(selected_analysts)
    app = workflow.compile()

    if args.show_agent_graph:
        file_path = "logs/"
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

    # Set end date to yesterday if not specified
    current_date = datetime.now()
    yesterday = current_date - timedelta(days=1)
    end_date = yesterday if not args.end_date else min(
        datetime.strptime(args.end_date, '%Y-%m-%d'), yesterday)

    # Set start date to one year before end date if not specified
    if not args.start_date:
        start_date = end_date - timedelta(days=365)  # 默认获取一年的数据
    else:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        
    # Format double check
    start_date = start_date.strftime('%Y-%m-%d')
    end_date = end_date.strftime('%Y-%m-%d')

    # Validate dates
    if start_date > end_date:
        raise ValueError("Start date cannot be after end date")

    logger.info("start_date: {}".format(start_date))
    logger.info("end_date: {}".format(end_date))

    for cur_market, cur_tickers in market_classification.items():
        # Run the hedge fund for different markets
        logger.info(f"{Fore.CYAN}Running hedge fund for {cur_market} market...{Style.RESET_ALL}")
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
                } for ticker in cur_tickers
            },
            "realized_gains": {
                ticker: {
                    "long": 0.0,  # Realized gains from long positions
                    "short": 0.0,  # Realized gains from short positions
                } for ticker in cur_tickers
            }
        }

        # Run the hedge fund
        result = run_hedge_fund(
            agent=app,
            market=cur_market,
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
