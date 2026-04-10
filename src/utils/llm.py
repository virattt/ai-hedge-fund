"""Helper functions for LLM"""

import json
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from pydantic import BaseModel
from src.llm.models import get_model, get_model_info
from src.utils.progress import progress
from src.graph.state import AgentState
from src.llm.models import ModelProvider


@dataclass
class ResolvedModelConfig:
    """Resolved model name and provider string for LLM calls."""
    model_name: str
    model_provider: str


@runtime_checkable
class HasAgentModelConfig(Protocol):
    """Protocol for objects that provide per-agent model configuration."""
    def get_agent_model_config(self, agent_id: str) -> object: ...


@runtime_checkable
class HasApiKeys(Protocol):
    """Protocol for objects that expose API keys."""
    api_keys: dict[str, str] | None


def call_llm(
    prompt: object,
    pydantic_model: type[BaseModel],
    agent_name: str | None = None,
    state: AgentState | None = None,
    max_retries: int = 3,
    default_factory: object = None,
) -> BaseModel:
    """Make an LLM call with retry logic, handling JSON and non-JSON supported models.

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
        resolved = get_agent_model_config(state, agent_name)
        model_name = resolved.model_name
        model_provider = resolved.model_provider
    else:
        # Use system defaults when no state or agent_name is provided
        model_name = "gpt-4.1"
        model_provider = "OPENAI"

    # Extract API keys from state if available
    api_keys = None
    if state:
        request = state.get("metadata", {}).get("request")
        if isinstance(request, HasApiKeys):
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
            result = llm.invoke(prompt)

            # For non-JSON support models, extract and parse the JSON manually
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
                print(f"Error in LLM call after {max_retries} attempts: {e}")
                if callable(default_factory):
                    return default_factory()
                return create_default_response(pydantic_model)

    # This should never be reached due to the retry logic above
    return create_default_response(pydantic_model)


def create_default_response(model_class: type[BaseModel]) -> BaseModel:
    """Create a safe default response based on the model's fields."""
    default_values = {}
    for field_name, field in model_class.model_fields.items():
        if field.annotation == str:
            default_values[field_name] = "Error in analysis, using default"
        elif field.annotation == float:
            default_values[field_name] = 0.0
        elif field.annotation == int:
            default_values[field_name] = 0
        elif isinstance(field.annotation, type) and issubclass(field.annotation, dict):
            default_values[field_name] = {}
        else:
            # For Literal and other complex annotations, fall back to None
            default_values[field_name] = None

    return model_class(**default_values)


def extract_json_from_response(content: str) -> dict | None:
    """Extract JSON from a markdown-formatted response."""
    try:
        json_start = content.find("```json")
        if json_start != -1:
            json_text = content[json_start + 7:]  # Skip past ```json
            json_end = json_text.find("```")
            if json_end != -1:
                json_text = json_text[:json_end].strip()
                return json.loads(json_text)
    except Exception as e:
        print(f"Error extracting JSON from response: {e}")
    return None


def get_agent_model_config(state: AgentState, agent_name: str) -> ResolvedModelConfig:
    """Get model configuration for a specific agent from the state.

    Falls back to global model configuration if agent-specific config is not available.
    Always returns a ResolvedModelConfig with valid string values.
    """
    from app.backend.models.schemas import AgentModelSelection  # noqa: PLC0415 - deferred to avoid circular import

    request = state.get("metadata", {}).get("request")

    if isinstance(request, HasAgentModelConfig):
        selection = request.get_agent_model_config(agent_name)
        if isinstance(selection, AgentModelSelection) and selection.model_name and selection.model_provider:
            provider_str = (
                selection.model_provider.value
                if isinstance(selection.model_provider, ModelProvider)
                else str(selection.model_provider)
            )
            return ResolvedModelConfig(model_name=selection.model_name, model_provider=provider_str)

    # Fall back to global configuration (system defaults)
    model_name = state.get("metadata", {}).get("model_name") or "gpt-4.1"
    model_provider_raw = state.get("metadata", {}).get("model_provider") or "OPENAI"
    provider_str = (
        model_provider_raw.value
        if isinstance(model_provider_raw, ModelProvider)
        else str(model_provider_raw)
    )
    return ResolvedModelConfig(model_name=model_name, model_provider=provider_str)
