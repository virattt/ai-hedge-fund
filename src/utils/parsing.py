"""Utility functions for parsing model responses."""
import json
from typing import Any, Optional


def parse_hedge_fund_response(response: str) -> Optional[dict[str, Any]]:
    """Parse a hedge fund JSON response safely.

    Args:
        response: The raw JSON string returned by the agent.

    Returns:
        A dictionary representation of the JSON response or ``None`` if parsing
        fails.
    """
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}\nResponse: {repr(response)}")
        return None
    except TypeError as e:
        print(
            f"Invalid response type (expected string, got {type(response).__name__}): {e}"
        )
        return None
    except Exception as e:  # noqa: BLE001
        print(f"Unexpected error while parsing response: {e}\nResponse: {repr(response)}")
        return None

