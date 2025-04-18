from typing_extensions import Annotated, Sequence, TypedDict
from typing import Dict, Any, Optional, Union, cast

import operator
from langchain_core.messages import BaseMessage

from new_models.portfolio import OptionPal

import json


def merge_dicts(a: dict[str, any], b: dict[str, any]) -> dict[str, any]:
    return {**a, **b}


# Define agent state
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    data: Annotated[dict[str, any], merge_dicts]
    metadata: Annotated[dict[str, any], merge_dicts]


class EnhancedAgentState:
    """
    Enhanced version of AgentState that provides structured access to hedge fund data
    while maintaining compatibility with LangChain's AgentState.
    """
    def __init__(self, state: AgentState):
        self._state = state
        self._hedge_fund_data: Optional[OptionPal] = None
        
    @property
    def messages(self) -> Sequence[BaseMessage]:
        return self._state["messages"]
    
    @property
    def metadata(self) -> Dict[str, Any]:
        return self._state["metadata"]
    
    @property
    def data(self) -> OptionPal:
        """
        Access the hedge fund data as a structured Pydantic model.
        If the data hasn't been converted to a Pydantic model yet, it will be converted.
        """
        if self._hedge_fund_data is None:
            # Initialize with empty model if no data exists yet
            if "data" not in self._state or not self._state["data"]:
                self._state["data"] = {}
                
            # Convert dict to Pydantic model
            self._hedge_fund_data = OptionPal.parse_obj(self._state["data"])
            
        return self._hedge_fund_data
    
    def to_dict(self) -> AgentState:
        """
        Convert back to a dictionary compatible with LangChain's AgentState.
        This ensures any changes made to the Pydantic models are reflected in the state.
        """
        if self._hedge_fund_data is not None:
            # Update the state with the latest data from the Pydantic model
            self._state["data"] = json.loads(self._hedge_fund_data.json(by_alias=True))
            
        return self._state
    
    @classmethod
    def from_dict(cls, state_dict: AgentState) -> 'EnhancedAgentState':
        """Create an EnhancedAgentState from a dictionary"""
        return cls(state_dict)


def show_agent_reasoning(output, agent_name):
    print(f"\n{'=' * 10} {agent_name.center(28)} {'=' * 10}")

    def convert_to_serializable(obj):
        if hasattr(obj, "to_dict"):  # Handle Pandas Series/DataFrame
            return obj.to_dict()
        elif hasattr(obj, "__dict__"):  # Handle custom objects
            return obj.__dict__
        elif isinstance(obj, (int, float, bool, str)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [convert_to_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: convert_to_serializable(value) for key, value in obj.items()}
        else:
            return str(obj)  # Fallback to string representation

    if isinstance(output, (dict, list)):
        # Convert the output to JSON-serializable format
        serializable_output = convert_to_serializable(output)
        print(json.dumps(serializable_output, indent=2))
    else:
        try:
            # Parse the string as JSON and pretty print it
            parsed_output = json.loads(output)
            print(json.dumps(parsed_output, indent=2))
        except json.JSONDecodeError:
            # Fallback to original string if not valid JSON
            print(output)

    print("=" * 48)
