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
from src.utils.visualize import save_graph_as_png
from src.cli.input import (
    parse_cli_inputs,
)

import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json
import os
import logging
from pathlib import Path

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


def ensure_database_tables():
    """
    Ensure database tables exist by running Alembic migrations if POSTGRES_URI is set.
    This is safe to run multiple times.
    """
    if not os.getenv("POSTGRES_URI"):
        return  # Skip if not using PostgreSQL
    
    try:
        from alembic import command
        from alembic.config import Config
        
        # Get the path to app/backend directory
        backend_dir = Path(__file__).parent.parent / "app" / "backend"
        alembic_ini_path = backend_dir / "alembic.ini"
        
        if not alembic_ini_path.exists():
            logger.warning(f"Alembic config not found at {alembic_ini_path}, skipping migrations")
            return
        
        logger.info("Running database migrations to ensure tables exist...")
        
        # Create Alembic config
        alembic_cfg = Config(str(alembic_ini_path))
        
        # The script_location in alembic.ini is relative to the ini file location
        # Since alembic.ini is in app/backend, and alembic/ is also in app/backend,
        # the relative path "alembic" should work
        
        # Run migrations to head
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully")
            
    except ImportError:
        logger.warning("Alembic not available, skipping migrations. Tables may not exist.")
    except Exception as e:
        logger.error(f"Error running database migrations: {e}", exc_info=True)
        # Don't fail - continue anyway, tables might already exist or we can use create_all as fallback
        try:
            # Fallback: try to create tables directly
            from app.backend.database.connection import engine
            from app.backend.database.models import Base
            logger.info("Attempting to create tables directly (fallback method)...")
            Base.metadata.create_all(bind=engine)
            logger.info("Tables created using create_all fallback")
        except Exception as fallback_error:
            logger.error(f"Fallback table creation also failed: {fallback_error}", exc_info=True)

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


def save_results_to_database(result, portfolio, tickers, start_date, end_date):
    """
    Save analysis results to PostgreSQL database if POSTGRES_URI is set.
    This is optional and non-blocking - failures won't affect CLI execution.
    """
    try:
        # Import here to avoid dependency issues if database modules aren't available
        from app.backend.database import SessionLocal
        from app.backend.services.agent_data_service import AgentDataService
        from app.backend.services.flow_run_service import FlowRunService
        
        logger.info("Creating database session...")
        # Get database session
        db = SessionLocal()
        try:
            logger.info("Database session created successfully")
            # Extract data for database saving
            analyst_signals_raw = result.get("analyst_signals", {})
            trading_decisions_raw = result.get("decisions", {})
            
            logger.info(f"Extracted {len(analyst_signals_raw)} agent signals and {len(trading_decisions_raw)} trading decisions")
            
            # Format analyst signals for database
            agent_data_service = AgentDataService()
            analyst_signals_summary = agent_data_service.format_analyst_signals_for_db(analyst_signals_raw)
            logger.info(f"Formatted analyst signals: {len(analyst_signals_summary)} agents")
            
            # Create flow run service and save data
            flow_run_service = FlowRunService(db)
            logger.info("FlowRunService created")
            
            # Create or get flow run (will create/use default CLI flow if flow_id is None)
            logger.info("Creating or getting flow run...")
            flow_run = flow_run_service.create_or_get_flow_run(
                flow_id=None,  # None will trigger creation of default CLI flow
                request_data={
                    "tickers": tickers,
                    "start_date": start_date,
                    "end_date": end_date,
                    "source": "CLI"
                }
            )
            
            if flow_run:
                logger.info(f"Flow run created/retrieved: ID={flow_run.id}, flow_id={flow_run.flow_id}")
                # Create cycle
                logger.info("Creating cycle...")
                cycle = flow_run_service.create_cycle(
                    flow_run_id=flow_run.id,
                    trigger_reason="CLI execution"
                )
                
                if cycle:
                    logger.info(f"Cycle created: ID={cycle.id}, cycle_number={cycle.cycle_number}")
                    # Update cycle with results
                    logger.info("Updating cycle with results...")
                    flow_run_service.update_cycle_with_results(
                        cycle_id=cycle.id,
                        analyst_signals=analyst_signals_summary,
                        trading_decisions=trading_decisions_raw,
                        portfolio_snapshot=portfolio
                    )
                    logger.info("Cycle updated with results")
                    
                    # Complete the flow run
                    logger.info("Completing flow run...")
                    flow_run_service.complete_flow_run(
                        flow_run_id=flow_run.id,
                        final_portfolio=portfolio,
                        results={
                            "decisions": trading_decisions_raw,
                            "analyst_signals": analyst_signals_summary
                        }
                    )
                    logger.info(f"✓ Successfully saved CLI execution results to database (flow_run_id: {flow_run.id}, cycle_id: {cycle.id})")
                else:
                    logger.error("Failed to create cycle for CLI execution")
            else:
                logger.error("Failed to create flow run for CLI execution - create_or_get_flow_run returned None")
            
        finally:
            db.close()
            logger.info("Database session closed")
    except ImportError as e:
        logger.warning(f"Database modules not available: {e}")
    except Exception as e:
        logger.error(f"Error saving to database: {e}", exc_info=True)
        # Don't raise - we want CLI to continue even if DB save fails


def create_workflow(selected_analysts=None):
    """Create the workflow with selected analysts."""
    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", start)

    # Get analyst nodes from the configuration
    analyst_nodes = get_analyst_nodes()

    # Default to all analysts if none selected
    if selected_analysts is None:
        selected_analysts = list(analyst_nodes.keys())
    # Add selected analyst nodes with timeout wrapper
    from src.utils.timeout import with_agent_timeout
    for analyst_key in selected_analysts:
        node_name, node_func = analyst_nodes[analyst_key]
        # Wrap agent function with timeout
        wrapped_func = with_agent_timeout(node_func, node_name)
        workflow.add_node(node_name, wrapped_func)
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
    inputs = parse_cli_inputs(
        description="Run the hedge fund trading system",
        require_tickers=True,
        default_months_back=None,
        include_graph_flag=True,
        include_reasoning_flag=True,
    )

    tickers = inputs.tickers
    selected_analysts = inputs.selected_analysts

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
    )
    
    # Optionally save to database if POSTGRES_URI is set
    postgres_uri = os.getenv("POSTGRES_URI")
    if postgres_uri:
        # Mask password in log for security
        masked_uri = postgres_uri.split("@")[0].split(":")[0] + ":****@" + "@".join(postgres_uri.split("@")[1:]) if "@" in postgres_uri else "****"
        logger.info(f"POSTGRES_URI detected ({masked_uri}), attempting to save results to database...")
        try:
            # Ensure database tables exist before saving
            ensure_database_tables()
            
            save_results_to_database(result, portfolio, tickers, inputs.start_date, inputs.end_date)
        except Exception as db_error:
            # Log but don't fail CLI execution if database save fails
            logger.error(f"Failed to save results to database: {db_error}", exc_info=True)
    else:
        logger.warning("POSTGRES_URI not set, skipping database save. Set POSTGRES_URI in .env file to enable database persistence.")
    
    print_trading_output(result)
