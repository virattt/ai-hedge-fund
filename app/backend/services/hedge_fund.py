from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
from src.main import run_hedge_fund
from src.utils.progress import progress
from dateutil.relativedelta import relativedelta
from app.backend.models.schemas import AgentInfo

class HedgeFundService:
    @staticmethod
    async def run_hedge_fund(
        tickers: List[str],
        selected_agents: List[str],
        initial_cash: float,
        margin_requirement: float,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        model_name: str = "gpt-4",
        model_provider: str = "openai",
        show_reasoning: bool = False,
    ) -> Dict[str, Any]:
        """
        Run the hedge fund with the given parameters.
        
        Args:
            tickers: List of stock tickers to analyze
            selected_agents: List of agent names to use
            initial_cash: Initial cash amount
            margin_requirement: Margin requirement as a decimal
            start_date: Optional start date for analysis
            end_date: Optional end date for analysis
            model_name: Name of the LLM model to use
            model_provider: Provider of the LLM model
            show_reasoning: Whether to show agent reasoning
            
        Returns:
            Dict containing the hedge fund decisions and analysis
        """
        try:
            # Create a queue for progress updates
            progress_queue = asyncio.Queue()
            
            # Define progress handler
            def progress_handler(agent_name, ticker, status, analysis, timestamp):
                progress_queue.put_nowait({
                    "agent": agent_name,
                    "ticker": ticker,
                    "status": status,
                    "analysis": analysis,
                    "timestamp": timestamp
                })
            
            # Register progress handler
            progress.register_handler(progress_handler)
            
            # Construct portfolio dictionary
            portfolio = {
                "cash": initial_cash,
                "margin_requirement": margin_requirement,
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
            
            # Set default dates if not provided
            if end_date is None:
                end_date = datetime.now()
            if start_date is None:
                # Default to 3 months before end_date
                start_date = end_date - relativedelta(months=3)
            
            # Convert dates to strings
            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")
            
            # Run the hedge fund
            result = run_hedge_fund(
                tickers=tickers,
                start_date=start_date_str,
                end_date=end_date_str,
                portfolio=portfolio,
                show_reasoning=show_reasoning,
                selected_agents=selected_agents,
                model_name=model_name,
                model_provider=model_provider
            )
            
            # Unregister progress handler
            progress.unregister_handler(progress_handler)
            
            return result
            
        except Exception as e:
            raise Exception(f"Error running hedge fund: {str(e)}")
    
    @staticmethod
    def get_available_agents() -> List[AgentInfo]:
        """
        Get a list of available agents with their descriptions.
        
        Returns:
            List of AgentInfo objects containing agent information
        """
        return [
            AgentInfo(
                name="aswath_damodaran",
                description="The Dean of Valuation, focuses on story, numbers, and disciplined valuation"
            ),
            AgentInfo(
                name="ben_graham",
                description="The godfather of value investing, only buys hidden gems with a margin of safety"
            ),
            AgentInfo(
                name="bill_ackman",
                description="An activist investor, takes bold positions and pushes for change"
            ),
            AgentInfo(
                name="cathie_wood",
                description="The queen of growth investing, believes in the power of innovation and disruption"
            ),
            AgentInfo(
                name="charlie_munger",
                description="Warren Buffett's partner, only buys wonderful businesses at fair prices"
            ),
            AgentInfo(
                name="michael_burry",
                description="The Big Short contrarian who hunts for deep value"
            ),
            AgentInfo(
                name="peter_lynch",
                description="Practical investor who seeks 'ten-baggers' in everyday businesses"
            ),
            AgentInfo(
                name="phil_fisher",
                description="Meticulous growth investor who uses deep 'scuttlebutt' research"
            ),
            AgentInfo(
                name="stanley_druckenmiller",
                description="Macro legend who hunts for asymmetric opportunities with growth potential"
            ),
            AgentInfo(
                name="warren_buffett",
                description="The oracle of Omaha, seeks wonderful companies at a fair price"
            )
        ] 