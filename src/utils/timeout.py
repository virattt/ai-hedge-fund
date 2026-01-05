"""
Utility for adding timeout to agent functions.
"""
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Callable
import logging
from langchain_core.messages import HumanMessage
import json

from src.graph.state import AgentState
from src.utils.progress import progress

logger = logging.getLogger(__name__)

# Timeout for individual agents (10 minutes = 600 seconds)
AGENT_TIMEOUT_SECONDS = 600


def with_agent_timeout(agent_function: Callable, agent_id: str) -> Callable[[AgentState], dict]:
    """
    Wrap an agent function with a timeout. If the agent takes longer than
    AGENT_TIMEOUT_SECONDS, it will be skipped and neutral signals will be returned.
    
    Args:
        agent_function: The agent function to wrap (should accept state and agent_id)
        agent_id: The ID of the agent
        
    Returns:
        A wrapped function that includes timeout handling
    """
    def agent_with_timeout(state: AgentState) -> dict:
        """
        Execute agent with timeout. If timeout occurs, return neutral signals.
        """
        def run_agent():
            # Agent functions accept (state, agent_id) as parameters
            return agent_function(state, agent_id)
        
        try:
            # Execute agent in a thread pool with timeout
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_agent)
                result = future.result(timeout=AGENT_TIMEOUT_SECONDS)
                return result
        except FutureTimeoutError:
            # Agent timed out - return neutral signals
            logger.warning(f"Agent {agent_id} timed out after {AGENT_TIMEOUT_SECONDS} seconds. Skipping and returning neutral signals.")
            
            # Update progress to show timeout
            tickers = state.get("data", {}).get("tickers", [])
            for ticker in tickers:
                progress.update_status(agent_id, ticker, f"Timeout - skipped", 
                                     analysis=f"Agent timed out after {AGENT_TIMEOUT_SECONDS}s")
            progress.update_status(agent_id, None, "Timeout - skipped")
            
            # Return neutral signals for all tickers
            neutral_signals = {}
            for ticker in tickers:
                neutral_signals[ticker] = {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reasoning": f"Agent timed out after {AGENT_TIMEOUT_SECONDS} seconds and was skipped."
                }
            
            # Return in the same format as agents would
            message = HumanMessage(
                content=json.dumps(neutral_signals),
                name=agent_id
            )
            
            # Store in analyst_signals
            if "analyst_signals" not in state["data"]:
                state["data"]["analyst_signals"] = {}
            state["data"]["analyst_signals"][agent_id] = neutral_signals
            
            return {"messages": [message], "data": state["data"]}
        except Exception as e:
            # Other errors - log and return neutral signals
            logger.error(f"Agent {agent_id} encountered an error: {e}", exc_info=True)
            
            tickers = state.get("data", {}).get("tickers", [])
            for ticker in tickers:
                progress.update_status(agent_id, ticker, f"Error - skipped", 
                                     analysis=f"Agent error: {str(e)}")
            progress.update_status(agent_id, None, "Error - skipped")
            
            # Return neutral signals
            neutral_signals = {}
            for ticker in tickers:
                neutral_signals[ticker] = {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reasoning": f"Agent encountered an error: {str(e)}"
                }
            
            message = HumanMessage(
                content=json.dumps(neutral_signals),
                name=agent_id
            )
            
            if "analyst_signals" not in state["data"]:
                state["data"]["analyst_signals"] = {}
            state["data"]["analyst_signals"][agent_id] = neutral_signals
            
            return {"messages": [message], "data": state["data"]}
    
    return agent_with_timeout

