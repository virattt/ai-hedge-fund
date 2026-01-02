from functools import partial
from typing import Callable
from src.graph.state import AgentState

def create_agent_function(agent_function: Callable, agent_id: str) -> Callable[[AgentState], dict]:
    """
    Creates a new function from an agent function that accepts an agent_id.

    :param agent_function: The agent function to wrap.
    :param agent_id: The ID to be passed to the agent.
    :return: A new function that can be called by LangGraph.
    """
    return partial(agent_function, agent_id=agent_id) 