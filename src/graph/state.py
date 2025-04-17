from typing_extensions import Annotated, Sequence, TypedDict
import operator
from langchain_core.messages import BaseMessage
import json
import logging

logger = logging.getLogger(__name__)

def merge_dicts(a: dict[str, any], b: dict[str, any]) -> dict[str, any]:
    """Deep merge dictionaries recursively handling nested dicts and lists."""
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_dicts(a[key], b[key])
            elif isinstance(a[key], list) and isinstance(b[key], list):
                a[key].extend(b[key])
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a

# Define agent state
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    data: Annotated[dict[str, any], merge_dicts]
    metadata: Annotated[dict[str, any], merge_dicts]

def show_agent_reasoning(output, agent_name):
    """Display agent reasoning with improved serialization and logging integration."""
    logger.debug(f"Agent reasoning: {agent_name}")
    
    if logger.level <= logging.INFO:
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