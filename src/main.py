import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from colorama import Fore, Style, init
import questionary
from src.agents.portfolio_manager import portfolio_management_agent
from src.agents.risk_manager import risk_management_agent
from src.agents.fyi_market_context import fyi_market_context_agent
from src.agents.fyi_deep_technical import fyi_deep_technical_agent
from src.agents.fyi_deep_fundamental import fyi_deep_fundamental_agent
from src.graph.state import AgentState
from src.utils.display import print_trading_output
from src.utils.analysts import ANALYST_ORDER, get_analyst_nodes
from src.utils.progress import progress
from src.utils.visualize import save_graph_as_png
from src.utils.stock_snapshot import build_and_print_snapshots
from src.utils.validator import validate_analysis
from src.analysis import generate_snapshot, render_console, render_html
from src.cli.input import (
    parse_cli_inputs,
)

import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
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
    effort: str | None = None,
):
    # Start progress tracking
    progress.start()

    try:
        # Build workflow (default to all analysts when none provided)
        workflow = create_workflow(selected_analysts if selected_analysts else None)
        agent = workflow.compile()

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
                    "effort": effort,
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


_FYI_AGENTS = {
    "fyi_market_context_agent": fyi_market_context_agent,
    "fyi_deep_technical_agent": fyi_deep_technical_agent,
    "fyi_deep_fundamental_agent": fyi_deep_fundamental_agent,
}


def create_workflow(selected_analysts=None):
    """Create the workflow with selected analysts plus always-on FYI agents."""
    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", start)

    analyst_nodes = get_analyst_nodes()

    if selected_analysts is None:
        selected_analysts = list(analyst_nodes.keys())

    for analyst_key in selected_analysts:
        node_name, node_func = analyst_nodes[analyst_key]
        workflow.add_node(node_name, node_func)
        workflow.add_edge("start_node", node_name)

    # Always-on FYI agents (parallel with decision analysts, excluded from PM)
    for fyi_id, fyi_func in _FYI_AGENTS.items():
        workflow.add_node(fyi_id, fyi_func)
        workflow.add_edge("start_node", fyi_id)

    workflow.add_node("risk_management_agent", risk_management_agent)
    workflow.add_node("portfolio_manager", portfolio_management_agent)

    for analyst_key in selected_analysts:
        node_name = analyst_nodes[analyst_key][0]
        workflow.add_edge(node_name, "risk_management_agent")

    for fyi_id in _FYI_AGENTS:
        workflow.add_edge(fyi_id, "risk_management_agent")

    workflow.add_edge("risk_management_agent", "portfolio_manager")
    workflow.add_edge("portfolio_manager", END)

    workflow.set_entry_point("start_node")
    return workflow


if __name__ == "__main__":
    inputs = parse_cli_inputs(
        description="Run the hedge fund trading system",
        require_tickers=True,
        default_months_back=None,
        include_graph_flag=True,
        include_reasoning_flag=True,
    )

    tickers = inputs.tickers
    selected_analysts = inputs.selected_analysts

    # ===== Pre-run: structured ticker snapshot (price + fundamental + technical + analyst) =====
    # This runs BEFORE the LangGraph pipeline. Output goes to the console as rich tables
    # and to ./reports/<TICKER>_snapshot_<date>.html as a single-file HTML dashboard.
    # Self-contained — uses yfinance, no API keys required, no LLM calls.
    if not getattr(inputs, "no_snapshot", False):
        from pathlib import Path as _Path
        from datetime import date as _date

        reports_dir = _Path("reports")
        reports_dir.mkdir(exist_ok=True)
        _today = _date.today().strftime("%Y-%m-%d")
        _quiet = getattr(inputs, "quiet", False)
        for _t in tickers:
            try:
                _report = generate_snapshot(_t)
                if not _quiet:
                    render_console(_report)
                _out = reports_dir / f"{_t}_snapshot_{_today}.html"
                render_html(_report, _out)
                print(f"{Fore.CYAN}Saved snapshot HTML → {_out}{Style.RESET_ALL}")
            except Exception as _e:
                print(f"{Fore.YELLOW}Snapshot failed for {_t}: {_e}{Style.RESET_ALL}")

    # Construct portfolio here
    portfolio = {
        "cash": inputs.initial_cash,
        "margin_requirement": inputs.margin_requirement,
        "margin_used": 0.0,
        "positions": {
            ticker: {
                "long": 0,
                "short": 0,
                "long_cost_basis": 0.0,
                "short_cost_basis": 0.0,
                "short_margin_used": 0.0,
            }
            for ticker in tickers
        },
        "realized_gains": {
            ticker: {
                "long": 0.0,
                "short": 0.0,
            }
            for ticker in tickers
        },
    }

    result = run_hedge_fund(
        tickers=tickers,
        start_date=inputs.start_date,
        end_date=inputs.end_date,
        portfolio=portfolio,
        show_reasoning=inputs.show_reasoning,
        selected_analysts=inputs.selected_analysts,
        model_name=inputs.model_name,
        model_provider=inputs.model_provider,
        effort=inputs.effort,
    )
    print_trading_output(result)

    # Live stock snapshot (always runs)
    # Build a minimal state so the snapshot's LLM call uses the same model as the run
    snapshot_state = {
        "messages": [],
        "data": {},
        "metadata": {
            "model_name": inputs.model_name,
            "model_provider": inputs.model_provider,
            "effort": inputs.effort,
            "show_reasoning": False,
        },
    }
    snapshots = build_and_print_snapshots(
        tickers=tickers,
        result=result,
        start_date=inputs.start_date,
        end_date=inputs.end_date,
        state=snapshot_state,
    )

    # GPT-5.5 validation pass (runs if OPENAI_API_KEY is set)
    validate_analysis(result, snapshots)
