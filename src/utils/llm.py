"""Helper functions for LLM"""

import json
import logging
import os

from pydantic import BaseModel

from src.graph.state import AgentState
from src.llm.models import get_model, get_model_info
from src.utils.progress import progress

# ---------------------------------------------------------------------------
# A10a: Observable LLM failures
# ---------------------------------------------------------------------------
# When True, retry-exhausted responses include a tagged ``[LLM_ERROR]``
# reasoning string and are logged at ERROR level so callers (especially the
# portfolio manager) can detect fabricated defaults.
LLM_FAILURE_OBSERVABLE: bool = os.getenv("AHF_OBSERVABLE_LLM_FAILURES", "1") != "0"

_log = logging.getLogger("ahf.llm")


def call_llm(
    prompt: any,
    pydantic_model: type[BaseModel],
    agent_name: str | None = None,
    state: AgentState | None = None,
    max_retries: int = 3,
    default_factory=None,
) -> BaseModel:
    """
    Makes an LLM call with retry logic, handling both JSON supported and non-JSON supported models.

    Args:
        prompt: The prompt to send to the LLM
        pydantic_model: The Pydantic model class to structure the output
        agent_name: Optional name of the agent for progress updates and model config extraction
        state: Optional state object to extract agent-specific model configuration
        max_retries: Maximum number of retries (default: 3)
        default_factory: Optional factory function to create default response on failure

    Returns:
        An instance of the specified Pydantic model
    """

    # Extract model configuration if state is provided and agent_name is available
    if state and agent_name:
        model_name, model_provider = get_agent_model_config(state, agent_name)
    else:
        # Use system defaults when no state or agent_name is provided
        model_name = "gpt-4.1"
        model_provider = "OPENAI"

    # Extract API keys from state if available
    api_keys = None
    if state:
        request = state.get("metadata", {}).get("request")
        if request and hasattr(request, "api_keys"):
            api_keys = request.api_keys

    model_info = get_model_info(model_name, model_provider)
    llm = get_model(model_name, model_provider, api_keys)

    # For non-JSON support models, we can use structured output
    if not (model_info and not model_info.has_json_mode()):
        llm = llm.with_structured_output(
            pydantic_model,
            method="json_mode",
        )

    # Call the LLM with retries
    for attempt in range(max_retries):
        try:
            # Call the LLM
            result = llm.invoke(prompt)

            # For non-JSON support models, we need to extract and parse the JSON manually
            if model_info and not model_info.has_json_mode():
                parsed_result = extract_json_from_response(result.content)
                if parsed_result:
                    return pydantic_model(**parsed_result)
            else:
                return result

        except Exception as e:
            if agent_name:
                progress.update_status(agent_name, None, f"Error - retry {attempt + 1}/{max_retries}")

            if attempt == max_retries - 1:
                _log.error("call_llm exhausted retries", exc_info=e)
                # Use default_factory if provided, otherwise create a basic default
                if default_factory:
                    result = default_factory()
                else:
                    result = create_default_response(pydantic_model)

                # A10a: tag the fabricated response so callers can detect it
                if LLM_FAILURE_OBSERVABLE:
                    result = _tag_llm_error(result, e)
                return result

    # This should never be reached due to the retry logic above
    return create_default_response(pydantic_model)


def _tag_llm_error(response: BaseModel, exc: Exception) -> BaseModel:
    """Stamp *response* with ``[LLM_ERROR]`` markers so downstream code can
    detect that this signal is fabricated.

    Works by mutating the existing instance when the model allows it, or
    reconstructing with updated fields otherwise.
    """
    updates: dict = {}
    if "reasoning" in response.model_fields:
        updates["reasoning"] = f"[LLM_ERROR] {exc!r} — signal is fabricated; treat with extreme caution"
    if "confidence" in response.model_fields:
        updates["confidence"] = 0.0

    if not updates:
        return response

    # Try in-place mutation (works for models with ``model_config = {"extra": "allow"}``).
    try:
        for k, v in updates.items():
            setattr(response, k, v)
        return response
    except (AttributeError, ValueError):
        pass

    # Fall back: reconstruct
    data = response.model_dump()
    data.update(updates)
    return type(response)(**data)


def create_default_response(model_class: type[BaseModel]) -> BaseModel:
    """Creates a safe default response based on the model's fields."""
    default_values = {}
    for field_name, field in model_class.model_fields.items():
        if field.annotation == str:
            default_values[field_name] = "Error in analysis, using default"
        elif field.annotation == float:
            default_values[field_name] = 0.0
        elif field.annotation == int:
            default_values[field_name] = 0
        elif hasattr(field.annotation, "__origin__") and field.annotation.__origin__ == dict:
            default_values[field_name] = {}
        else:
            # For other types (like Literal), try to use the first allowed value
            if hasattr(field.annotation, "__args__"):
                default_values[field_name] = field.annotation.__args__[0]
            else:
                default_values[field_name] = None

    return model_class(**default_values)


def extract_json_from_response(content: str) -> dict | None:
    """Extracts JSON from markdown-formatted response."""
    try:
        json_start = content.find("```json")
        if json_start != -1:
            json_text = content[json_start + 7 :]  # Skip past ```json
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                return json.loads(json_text)
    except Exception as e:
        print(f"Error extracting JSON from response: {e}")
    return None


def get_agent_model_config(state, agent_name):
    """
    Get model configuration for a specific agent from the state.
    Falls back to global model configuration if agent-specific config is not available.
    Always returns valid model_name and model_provider values.
    """
    request = state.get("metadata", {}).get("request")

    if request and hasattr(request, "get_agent_model_config"):
        # Get agent-specific model configuration
        model_name, model_provider = request.get_agent_model_config(agent_name)
        # Ensure we have valid values
        if model_name and model_provider:
            return model_name, model_provider.value if hasattr(model_provider, "value") else str(model_provider)

    # Fall back to global configuration (system defaults)
    model_name = state.get("metadata", {}).get("model_name") or "gpt-4.1"
    model_provider = state.get("metadata", {}).get("model_provider") or "OPENAI"

    # Convert enum to string if necessary
    if hasattr(model_provider, "value"):
        model_provider = model_provider.value

    return model_name, model_provider
