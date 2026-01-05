from functools import partial
from typing import Callable
from src.graph.state import AgentState
from src.utils.timeout import with_agent_timeout

def create_agent_function(agent_function: Callable, agent_id: str) -> Callable[[AgentState], dict]:
    """
    Creates a new function from an agent function that accepts an agent_id.
    Wraps the agent with a timeout to prevent it from blocking execution.

    :param agent_function: The agent function to wrap.
    :param agent_id: The ID to be passed to the agent.
    :return: A new function that can be called by LangGraph.
    """
    # Use the shared timeout wrapper
    return with_agent_timeout(agent_function, agent_id) 