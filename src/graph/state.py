from typing import Any, Sequence
from typing_extensions import Annotated, TypedDict

import operator
import json
from langchain_core.messages import BaseMessage


def merge_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Merge two dictionaries, giving precedence to values in `b` if keys overlap."""
    return {**a, **b}


# Define agent state
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    data: Annotated[dict[str, Any], merge_dicts]
    metadata: Annotated[dict[str, Any], merge_dicts]


def show_agent_reasoning(output: Any, agent_name: str) -> None:
    """Display agent reasoning in a structured format."""

    print(f"\n{'=' * 10} {agent_name.center(28)} {'=' * 10}")

    def convert_to_serializable(obj: Any) -> Any:
        """Convert an object to a JSON-serializable format."""
        if hasattr(obj, "to_dict"):  # Handle Pandas Series/DataFrame or custom objects
            return obj.to_dict()
        elif isinstance(obj, dict):
            return {key: convert_to_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_to_serializable(item) for item in obj]
        elif isinstance(obj, (int, float, bool, str)):
            return obj  # Already serializable
        elif hasattr(obj, "__dict__"):  # Handle other custom objects
            return {k: convert_to_serializable(v) for k, v in obj.__dict__.items()}
        else:
            return str(obj)  # Fallback to string representation

    try:
        if isinstance(output, (dict, list)):
            # Convert and print JSON output
            serializable_output = convert_to_serializable(output)
            print(json.dumps(serializable_output, indent=2))
        else:
            # Try parsing as JSON string
            parsed_output = json.loads(output)
            print(json.dumps(parsed_output, indent=2))
    except (json.JSONDecodeError, TypeError):
        print(str(output))  # Fallback for non-JSON outputs

    print("=" * 48)
